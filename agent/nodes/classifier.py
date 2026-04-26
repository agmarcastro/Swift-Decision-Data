from __future__ import annotations

import logging
import os
import time
from pathlib import Path

import anthropic
from pydantic import BaseModel

from agent.state import AgentState

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "classifier.txt"
MODEL = "claude-sonnet-4-6"


class ClassifierOutput(BaseModel):
    query_type: str
    kpi_name: str | None = None
    confidence: float


def classify_query(state: AgentState) -> dict:
    """LangGraph node: classify the user's question into one of 3 query types.

    For type2_kpi_sql, also fetches the KPI definition from Qdrant and stores
    it in state.kpi_context so the SQL agent can use it.
    """
    started = time.perf_counter()
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    system_prompt = PROMPT_PATH.read_text()

    user_message = state.messages[-1].content if state.messages else ""

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=256,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
    except (anthropic.RateLimitError, anthropic.APITimeoutError) as exc:
        logger.error("classify_query: anthropic error type=%s err=%s", type(exc).__name__, exc)
        return {
            "query_type": "type1_sql",
            "kpi_name": None,
            "kpi_context": None,
            "final_answer": (
                "I am temporarily unable to reach the language model "
                "(rate limit or timeout). Please retry in a moment."
            ),
        }

    try:
        output = ClassifierOutput.model_validate_json(response.content[0].text)
    except Exception as exc:
        logger.error("classify_query: invalid JSON from model err=%s raw=%r", exc, response.content)
        return {
            "query_type": "type1_sql",
            "kpi_name": None,
            "kpi_context": None,
        }

    elapsed_ms = (time.perf_counter() - started) * 1000
    logger.info(
        "classify_query: type=%s kpi=%s confidence=%.2f elapsed_ms=%.1f",
        output.query_type,
        output.kpi_name,
        output.confidence,
        elapsed_ms,
    )

    kpi_context: str | None = None
    if output.query_type == "type2_kpi_sql" and output.kpi_name:
        kpi_context = _fetch_kpi_context(output.kpi_name)

    return {
        "query_type": output.query_type,
        "kpi_name": output.kpi_name,
        "kpi_context": kpi_context,
    }


def _fetch_kpi_context(kpi_name: str) -> str | None:
    """Retrieve KPI definition text from Qdrant."""
    try:
        from llama_index.core import Settings, StorageContext, VectorStoreIndex
        from llama_index.embeddings.huggingface import HuggingFaceEmbedding
        from llama_index.vector_stores.qdrant import QdrantVectorStore
        from qdrant_client import QdrantClient

        Settings.embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")
        Settings.llm = None

        host = os.environ.get("QDRANT_HOST", "qdrant")
        port = int(os.environ.get("QDRANT_PORT", "6333"))
        collection = os.environ.get("QDRANT_COLLECTION", "infoagent_knowledge")

        client = QdrantClient(host=host, port=port)
        vector_store = QdrantVectorStore(client=client, collection_name=collection)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        index = VectorStoreIndex.from_vector_store(vector_store, storage_context=storage_context)

        retriever = index.as_retriever(similarity_top_k=2)
        nodes = retriever.retrieve(kpi_name)

        if nodes:
            context = "\n\n".join(n.get_content() for n in nodes)
            logger.info("Fetched KPI context for '%s' (%d chunks)", kpi_name, len(nodes))
            return context
    except Exception as exc:
        logger.warning("Could not fetch KPI context for '%s': %s", kpi_name, exc)
    return None
