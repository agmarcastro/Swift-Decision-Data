from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor
from langchain_core.tools import tool
from llama_index.core import Settings, StorageContext, VectorStoreIndex
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import QdrantClient

logger = logging.getLogger(__name__)

ALLOWED_STMT = re.compile(r"^\s*SELECT\b", re.IGNORECASE)
ROW_CAP = 500

_SQL_DOC = (Path(__file__).parent / "prompts" / "sql_tool.txt").read_text(encoding="utf-8")
_RAG_DOC = (Path(__file__).parent / "prompts" / "rag_tool.txt").read_text(encoding="utf-8")


@tool(description=_SQL_DOC)
def sql_tool(sql: str) -> str:
    """Executa uma consulta SQL SELECT somente-leitura no banco de vendas
    (PostgreSQL star schema: fato_vendas, fato_estoque, dim_produto,
    dim_cliente, dim_loja, dim_tempo). Use para perguntas sobre números:
    vendas totais, estoque, margens, ranking de lojas, etc.
    Retorna no máximo 500 linhas em JSON.
    """
    if not ALLOWED_STMT.match(sql):
        raise ValueError("Apenas SELECT é permitido — esta ferramenta é READ-ONLY.")

    conn = psycopg2.connect(os.environ["POSTGRES_READONLY_URL"])
    conn.autocommit = True
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql)
            rows = cur.fetchmany(ROW_CAP)
            return json.dumps([dict(r) for r in rows], default=str, ensure_ascii=False)
    except psycopg2.OperationalError as exc:
        logger.error("sql_tool: db connection error: %s", exc)
        return "Erro ao conectar ao banco — tente novamente."
    finally:
        conn.close()


@tool(description=_RAG_DOC)
def rag_tool(query: str) -> str:
    """Busca semântica em duas coleções Qdrant:
    (1) infoagent_knowledge — definições de KPIs, dicionário de dados, exemplos;
    (2) reviews — opiniões reais de clientes em PT-BR sobre produtos.
    Use para perguntas sobre fórmulas de KPI, regras de negócio,
    sentimento ou reclamações de clientes.
    """
    Settings.embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")
    Settings.llm = None

    try:
        client = QdrantClient(
            host=os.environ.get("QDRANT_HOST", "qdrant"),
            port=int(os.environ.get("QDRANT_PORT", "6333")),
        )

        chunks: list[str] = []
        for collection in ("infoagent_knowledge", "reviews"):
            vs = QdrantVectorStore(client=client, collection_name=collection)
            index = VectorStoreIndex.from_vector_store(
                vs,
                storage_context=StorageContext.from_defaults(vector_store=vs),
            )
            nodes = index.as_retriever(similarity_top_k=3).retrieve(query)
            for n in nodes:
                chunks.append(f"[{collection}] {n.get_content()}")

        return "\n\n---\n\n".join(chunks) if chunks else "Nenhum trecho relevante encontrado."
    except Exception as exc:  # noqa: BLE001
        logger.error("rag_tool: error: %s", exc)
        return "Não foi possível acessar a base de conhecimento."
