from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from agent.nodes.sql_agent import _execute_tool


# ---------------------------------------------------------------------------
# list_tables
# ---------------------------------------------------------------------------


class TestExecuteToolListTables:
    def test_returns_all_table_names(self, mock_pg_conn) -> None:
        conn, cursor = mock_pg_conn
        cursor.fetchall.return_value = [("dim_produto",), ("fato_vendas",)]

        result = _execute_tool("list_tables", {}, conn)

        assert "dim_produto" in result
        assert "fato_vendas" in result

    def test_returns_empty_list_when_no_tables(self, mock_pg_conn) -> None:
        conn, cursor = mock_pg_conn
        cursor.fetchall.return_value = []

        result = _execute_tool("list_tables", {}, conn)

        assert result == "[]"

    def test_executes_information_schema_query(self, mock_pg_conn) -> None:
        conn, cursor = mock_pg_conn
        cursor.fetchall.return_value = []

        _execute_tool("list_tables", {}, conn)

        sql_called = cursor.execute.call_args[0][0]
        assert "information_schema.tables" in sql_called


# ---------------------------------------------------------------------------
# describe_schema
# ---------------------------------------------------------------------------


class TestExecuteToolDescribeSchema:
    def test_returns_column_info(self, mock_pg_conn) -> None:
        conn, cursor = mock_pg_conn
        cursor.fetchall.return_value = [("id_venda", "integer", "NO")]

        result = _execute_tool("describe_schema", {"table_name": "FATO_VENDAS"}, conn)

        assert "id_venda" in result

    def test_lowercases_table_name(self, mock_pg_conn) -> None:
        conn, cursor = mock_pg_conn
        cursor.fetchall.return_value = []

        _execute_tool("describe_schema", {"table_name": "FATO_VENDAS"}, conn)

        _sql, params = cursor.execute.call_args[0]
        assert params == ("fato_vendas",)

    def test_queries_information_schema_columns(self, mock_pg_conn) -> None:
        conn, cursor = mock_pg_conn
        cursor.fetchall.return_value = []

        _execute_tool("describe_schema", {"table_name": "dim_produto"}, conn)

        sql_called = cursor.execute.call_args[0][0]
        assert "information_schema.columns" in sql_called


# ---------------------------------------------------------------------------
# execute_read_only_query — SELECT accepted
# ---------------------------------------------------------------------------


class TestExecuteToolSelectAccepted:
    def test_select_returns_json_string(self, mock_pg_conn) -> None:
        conn, cursor = mock_pg_conn
        cursor.fetchmany.return_value = [{"total": 100}]

        result = _execute_tool(
            "execute_read_only_query",
            {"sql": "SELECT COUNT(*) FROM fato_vendas"},
            conn,
        )

        assert result  # non-empty
        assert "100" in result

    def test_select_result_is_valid_json(self, mock_pg_conn) -> None:
        import json

        conn, cursor = mock_pg_conn
        cursor.fetchmany.return_value = [{"id_venda": 1, "valor_total": "1000.00"}]

        result = _execute_tool(
            "execute_read_only_query",
            {"sql": "SELECT id_venda, valor_total FROM fato_vendas LIMIT 1"},
            conn,
        )

        parsed = json.loads(result)
        assert isinstance(parsed, list)

    def test_select_empty_result_returns_empty_json_array(self, mock_pg_conn) -> None:
        import json

        conn, cursor = mock_pg_conn
        cursor.fetchmany.return_value = []

        result = _execute_tool(
            "execute_read_only_query",
            {"sql": "SELECT * FROM fato_vendas WHERE 1=0"},
            conn,
        )

        assert json.loads(result) == []

    def test_select_with_leading_whitespace_accepted(self, mock_pg_conn) -> None:
        conn, cursor = mock_pg_conn
        cursor.fetchmany.return_value = []

        result = _execute_tool(
            "execute_read_only_query",
            {"sql": "  SELECT 1"},
            conn,
        )

        assert result is not None

    def test_select_case_insensitive_accepted(self, mock_pg_conn) -> None:
        conn, cursor = mock_pg_conn
        cursor.fetchmany.return_value = []

        result = _execute_tool(
            "execute_read_only_query",
            {"sql": "select * from dim_loja"},
            conn,
        )

        assert result is not None


# ---------------------------------------------------------------------------
# execute_read_only_query — mutations rejected
# ---------------------------------------------------------------------------


class TestExecuteToolMutationsRejected:
    @pytest.mark.parametrize(
        "bad_sql",
        [
            "INSERT INTO fato_vendas VALUES (1)",
            "DROP TABLE fato_vendas",
            "UPDATE dim_loja SET gerente = 'hacker'",
            "DELETE FROM fato_vendas",
            "ALTER TABLE fato_vendas ADD COLUMN x INT",
            "CREATE TABLE pwned (id INT)",
            "TRUNCATE fato_vendas",
        ],
    )
    def test_non_select_raises_value_error(self, mock_pg_conn, bad_sql: str) -> None:
        conn, _ = mock_pg_conn

        with pytest.raises(ValueError, match="Only SELECT"):
            _execute_tool("execute_read_only_query", {"sql": bad_sql}, conn)

    def test_insert_rejected(self, mock_pg_conn) -> None:
        conn, _ = mock_pg_conn

        with pytest.raises(ValueError, match="Only SELECT"):
            _execute_tool(
                "execute_read_only_query",
                {"sql": "INSERT INTO fato_vendas VALUES (1)"},
                conn,
            )

    def test_drop_rejected(self, mock_pg_conn) -> None:
        conn, _ = mock_pg_conn

        with pytest.raises(ValueError, match="Only SELECT"):
            _execute_tool(
                "execute_read_only_query",
                {"sql": "DROP TABLE fato_vendas"},
                conn,
            )


# ---------------------------------------------------------------------------
# unknown tool
# ---------------------------------------------------------------------------


class TestExecuteToolUnknown:
    def test_unknown_tool_raises_value_error(self, mock_pg_conn) -> None:
        conn, _ = mock_pg_conn

        with pytest.raises(ValueError, match="Unknown tool"):
            _execute_tool("does_not_exist", {}, conn)
