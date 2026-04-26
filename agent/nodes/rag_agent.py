from __future__ import annotations

import logging
import os
import time
from pathlib import Path

import anthropic

from agent.state import AgentState

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "rag_agent.txt"
MODEL = "claude-sonnet-4-6"


def _retrieve_context(query: str) -> str:
    """Retrieve relevant context from Qdrant for the given query."""
    try:
        from llama_index.core import Settings, StorageContext, VectorStoreIndex
        from llama_index.embeddings.huggingface import HuggingFaceEmbedding
        from llama_index.vector_stores.qdrant import QdrantVectorStore
        from qdrant_client import QdrantClient

        Settings.embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")
        Settings.llm = None

        client = QdrantClient(
            host=os.environ.get("QDRANT_HOST", "qdrant"),
            port=int(os.environ.get("QDRANT_PORT", "6333")),
        )
        vector_store = QdrantVectorStore(
            client=client,
            collection_name=os.environ.get("QDRANT_COLLECTION", "infoagent_knowledge"),
        )
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        index = VectorStoreIndex.from_vector_store(vector_store, storage_context=storage_context)
        retriever = index.as_retriever(similarity_top_k=3)
        nodes = retriever.retrieve(query)
        logger.info("rag_agent: retrieved %d chunks for query", len(nodes))
        return "\n\n---\n\n".join(n.get_content() for n in nodes) if nodes else ""
    except Exception as exc:
        logger.warning("RAG retrieval failed: %s", exc)
        return ""


def rag_agent_node(state: AgentState) -> dict:
    """LangGraph node: retrieve KPI context from Qdrant + synthesise with Claude."""
    started = time.perf_counter()
    user_message = state.messages[-1].content if state.messages else ""
    context = _retrieve_context(user_message)

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    system_prompt = PROMPT_PATH.read_text()

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": f"Question: {user_message}\n\nRelevant context:\n{context}",
                }
            ],
        )
    except (anthropic.RateLimitError, anthropic.APITimeoutError) as exc:
        logger.error("rag_agent_node: anthropic error type=%s err=%s", type(exc).__name__, exc)
        return {
            "kpi_context": "",
            "final_answer": (
                "I am temporarily unable to reach the language model "
                "(rate limit or timeout). Please retry in a moment."
            ),
        }

    elapsed_ms = (time.perf_counter() - started) * 1000
    logger.info("rag_agent_node: elapsed_ms=%.1f", elapsed_ms)

    return {"kpi_context": response.content[0].text}
