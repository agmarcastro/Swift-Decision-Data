"""
Embed and upsert InfoAgent knowledge documents into Qdrant.

Usage:
    python -m contextualize.qdrant_ingest.ingest

Environment variables:
    QDRANT_HOST        Qdrant service hostname (default: qdrant)
    QDRANT_PORT        Qdrant service port     (default: 6333)
    QDRANT_COLLECTION  Target collection name  (default: infoagent_knowledge)

Knowledge files indexed:
    contextualize/knowledge/kpi_definitions.md    — 10 KPI definitions with formulas
    contextualize/knowledge/data_dictionary.md    — Column definitions for all 6 tables
    contextualize/knowledge/few_shot_examples.md  — 13 executive Q&A SQL examples

Embedding model:
    BAAI/bge-small-en-v1.5 (HuggingFace, no API key required)
    Vector size: 384 dimensions, cosine similarity
"""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from llama_index.core import Settings, SimpleDirectoryReader, StorageContext, VectorStoreIndex
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import Distance, VectorParams

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

KNOWLEDGE_DIR = Path(__file__).parent.parent / "knowledge"

# Maps a stable doc_type label to each source file.
# The doc_type is stored as document metadata so the RAG agent can filter
# by knowledge category at query time.
KNOWLEDGE_FILES: dict[str, Path] = {
    "kpi_definitions": KNOWLEDGE_DIR / "kpi_definitions.md",
    "data_dictionary": KNOWLEDGE_DIR / "data_dictionary.md",
    "few_shot_examples": KNOWLEDGE_DIR / "few_shot_examples.md",
}

# BAAI/bge-small-en-v1.5 produces 384-dimensional embeddings.
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
VECTOR_SIZE = 384

# Retry policy for Qdrant connection at startup.
_MAX_RETRIES = 3
_RETRY_DELAY_SECONDS = 5


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_qdrant_client(host: str, port: int) -> QdrantClient:
    """Return a connected QdrantClient, retrying up to _MAX_RETRIES times.

    Raises:
        ConnectionError: if all retry attempts are exhausted.
    """
    last_exc: Exception | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            client = QdrantClient(host=host, port=port)
            # Perform a lightweight probe to verify the connection is live.
            client.get_collections()
            logger.info("Connected to Qdrant at %s:%d", host, port)
            return client
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt < _MAX_RETRIES:
                logger.warning(
                    "Qdrant not ready (attempt %d/%d): %s — retrying in %ds",
                    attempt,
                    _MAX_RETRIES,
                    exc,
                    _RETRY_DELAY_SECONDS,
                )
                time.sleep(_RETRY_DELAY_SECONDS)
            else:
                logger.error(
                    "Qdrant unreachable after %d attempts: %s",
                    _MAX_RETRIES,
                    exc,
                )

    raise ConnectionError(
        f"Could not connect to Qdrant at {host}:{port} after {_MAX_RETRIES} attempts."
    ) from last_exc


def _ensure_collection(client: QdrantClient, collection: str) -> None:
    """Create the Qdrant collection if it does not already exist."""
    existing = {c.name for c in client.get_collections().collections}
    if collection not in existing:
        client.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )
        logger.info("Created Qdrant collection '%s' (dim=%d, cosine)", collection, VECTOR_SIZE)
    else:
        logger.info("Qdrant collection '%s' already exists — upserting into it", collection)


def _load_documents() -> list:
    """Load the 3 knowledge markdown files and tag each document with its doc_type.

    Returns:
        A flat list of LlamaIndex Document objects across all 3 source files.
    """
    all_docs = []
    for doc_type, path in KNOWLEDGE_FILES.items():
        if not path.exists():
            raise FileNotFoundError(
                f"Knowledge file not found: {path}\n"
                "Ensure the file exists before running the ingestion pipeline."
            )
        reader = SimpleDirectoryReader(input_files=[str(path)])
        file_docs = reader.load_data()
        for doc in file_docs:
            doc.metadata["doc_type"] = doc_type
            # Persist the source filename so retrieval results are traceable.
            doc.metadata["source_file"] = path.name
        all_docs.extend(file_docs)
        logger.info(
            "Loaded %d chunk(s) from '%s' [doc_type=%s]",
            len(file_docs),
            path.name,
            doc_type,
        )
    return all_docs


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_index() -> VectorStoreIndex:
    """Embed the InfoAgent knowledge documents and upsert them into Qdrant.

    Reads QDRANT_HOST, QDRANT_PORT, and QDRANT_COLLECTION from the environment
    (with sensible defaults) so the function works identically in Docker Compose
    and in local development overrides.

    Returns:
        A LlamaIndex VectorStoreIndex backed by the Qdrant collection.
        The returned index can be used directly by the RAG agent to run queries:

            retriever = index.as_retriever(similarity_top_k=3)
            nodes = retriever.retrieve("What is the gross profit margin formula?")

    Raises:
        ConnectionError: if Qdrant is not reachable after retries.
        FileNotFoundError: if any of the knowledge markdown files is missing.
    """
    host = os.environ.get("QDRANT_HOST", "qdrant")
    port = int(os.environ.get("QDRANT_PORT", "6333"))
    collection = os.environ.get("QDRANT_COLLECTION", "infoagent_knowledge")

    logger.info("Starting InfoAgent knowledge ingestion pipeline")
    logger.info("  Qdrant: %s:%d  |  collection: %s", host, port, collection)
    logger.info("  Embedding model: %s  (dim=%d)", EMBEDDING_MODEL, VECTOR_SIZE)

    # 1. Configure the embedding model globally for all LlamaIndex operations.
    #    HuggingFace embeddings require no API key and download the model weights
    #    on first use (cached under ~/.cache/huggingface by default).
    Settings.embed_model = HuggingFaceEmbedding(model_name=EMBEDDING_MODEL)
    # Disable the default LLM — this pipeline is embed-only; no generation needed.
    Settings.llm = None

    # 2. Connect to Qdrant (with retry).
    client = _get_qdrant_client(host, port)

    # 3. Create the collection when it is absent.
    _ensure_collection(client, collection)

    # 4. Load and tag all 3 knowledge documents.
    docs = _load_documents()
    logger.info("Total documents loaded: %d", len(docs))

    # 5. Build the LlamaIndex vector store backed by Qdrant and index all docs.
    #    VectorStoreIndex.from_documents() handles chunking, embedding, and upsert
    #    in a single call.  Existing vectors with matching IDs are overwritten,
    #    making repeated runs idempotent.
    vector_store = QdrantVectorStore(client=client, collection_name=collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    logger.info("Embedding and upserting documents — this may take a moment on first run...")
    index = VectorStoreIndex.from_documents(
        docs,
        storage_context=storage_context,
        show_progress=True,
    )

    logger.info(
        "Ingestion complete. %d document(s) indexed into collection '%s'.",
        len(docs),
        collection,
    )
    return index


def build_reviews_index():
    """Embed PostgreSQL reviews.texto_review rows into Qdrant collection 'reviews'."""
    import psycopg2
    from psycopg2.extras import RealDictCursor
    from llama_index.core import Document

    Settings.embed_model = HuggingFaceEmbedding(model_name=EMBEDDING_MODEL)
    Settings.llm = None

    host = os.environ.get("QDRANT_HOST", "qdrant")
    port = int(os.environ.get("QDRANT_PORT", "6333"))
    client = _get_qdrant_client(host, port)
    _ensure_collection(client, "reviews")

    pg_url = os.environ["POSTGRES_ADMIN_URL"]
    docs: list[Document] = []
    with psycopg2.connect(pg_url) as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT r.id_review, r.id_produto, r.id_cliente, r.nota, r.sentimento,
                   r.texto_review, p.nome_produto, p.marca, p.categoria
            FROM reviews r
            JOIN dim_produto p ON p.id_produto = r.id_produto
            """
        )
        for row in cur:
            docs.append(
                Document(
                    text=row["texto_review"],
                    metadata={
                        "doc_type": "review",
                        "id_review": row["id_review"],
                        "id_produto": row["id_produto"],
                        "nota": row["nota"],
                        "sentimento": row["sentimento"],
                        "produto": row["nome_produto"],
                        "marca": row["marca"],
                        "categoria": row["categoria"],
                    },
                )
            )

    if not docs:
        logger.warning("reviews table is empty — skipping reviews index build")
        return None

    vector_store = QdrantVectorStore(client=client, collection_name="reviews")
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    logger.info("Embedding %d review documents into collection 'reviews'...", len(docs))
    return VectorStoreIndex.from_documents(docs, storage_context=storage_context, show_progress=True)


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the ingestion pipeline and print a confirmation to stdout.

    Intended to be invoked as:
        python -m contextualize.qdrant_ingest.ingest
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)-8s %(name)s %(message)s",
    )

    collection = os.environ.get("QDRANT_COLLECTION", "infoagent_knowledge")

    print("InfoAgent — Qdrant Knowledge Base Ingestion")
    print(f"Collection : {collection}")
    print(f"Source dir : {KNOWLEDGE_DIR}")
    print(f"Files      : {', '.join(KNOWLEDGE_FILES.keys())}")
    print("-" * 60)

    index = build_index()

    print("-" * 60)
    print(f"Knowledge base ready. Collection: {collection}")
    print(
        "Indexed knowledge types: "
        + ", ".join(KNOWLEDGE_FILES.keys())
    )

    print("-" * 60)
    print("Building reviews collection...")
    build_reviews_index()
    print("Reviews collection ready.")


if __name__ == "__main__":
    main()
