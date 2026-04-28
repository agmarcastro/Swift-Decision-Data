from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import pytest


class TestSqlToolMutationsRejected:
    @pytest.mark.parametrize(
        "bad_sql",
        [
            "DELETE FROM fato_vendas",
            "INSERT INTO fato_vendas VALUES (1,1,1,1,1,'2024-01-01',1,100,100,70,0)",
            "DROP TABLE dim_produto",
            "UPDATE dim_loja SET gerente = 'hacker'",
            "ALTER TABLE fato_vendas ADD COLUMN x INT",
            "CREATE TABLE pwned (id INT)",
            "TRUNCATE fato_vendas",
        ],
    )
    def test_non_select_raises(self, bad_sql: str, monkeypatch) -> None:
        monkeypatch.setenv("POSTGRES_READONLY_URL", "postgresql://x:x@localhost/x")
        from agent.tools import sql_tool

        with pytest.raises(ValueError, match="READ-ONLY"):
            sql_tool.invoke({"sql": bad_sql})

    def test_select_returns_json(self, monkeypatch) -> None:
        monkeypatch.setenv("POSTGRES_READONLY_URL", "postgresql://x:x@localhost/x")
        row = {"id_venda": 1, "valor_total": "1000.00"}

        mock_cursor = MagicMock()
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchmany.return_value = [row]

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("agent.tools.psycopg2.connect", return_value=mock_conn):
            from agent.tools import sql_tool

            result = sql_tool.invoke({"sql": "SELECT id_venda FROM fato_vendas LIMIT 1"})

        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert parsed[0]["id_venda"] == 1

    def test_row_cap_applied(self, monkeypatch) -> None:
        monkeypatch.setenv("POSTGRES_READONLY_URL", "postgresql://x:x@localhost/x")
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchmany.return_value = []

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("agent.tools.psycopg2.connect", return_value=mock_conn):
            from agent import tools

            tools.sql_tool.invoke({"sql": "SELECT 1"})
            mock_cursor.fetchmany.assert_called_once_with(500)


class TestRagToolCallShape:
    def test_rag_tool_returns_string(self, monkeypatch) -> None:
        monkeypatch.setenv("QDRANT_HOST", "localhost")
        monkeypatch.setenv("QDRANT_PORT", "6333")

        mock_node = MagicMock()
        mock_node.get_content.return_value = "KPI definition text"

        mock_retriever = MagicMock()
        mock_retriever.retrieve.return_value = [mock_node]

        mock_index = MagicMock()
        mock_index.as_retriever.return_value = mock_retriever

        with (
            patch("agent.tools.QdrantClient"),
            patch("agent.tools.QdrantVectorStore"),
            patch("agent.tools.VectorStoreIndex.from_vector_store", return_value=mock_index),
            patch("agent.tools.HuggingFaceEmbedding"),
            patch("agent.tools.Settings"),
        ):
            from agent.tools import rag_tool

            result = rag_tool.invoke({"query": "margem bruta"})

        assert isinstance(result, str)
        assert len(result) > 0
