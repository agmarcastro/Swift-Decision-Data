from __future__ import annotations

import pytest

from contextualize.mcp_server.tools import ALLOWED_STMT, list_tools


# ---------------------------------------------------------------------------
# ALLOWED_STMT regex — no external dependencies
# ---------------------------------------------------------------------------


class TestAllowedStmt:
    @pytest.mark.parametrize(
        "sql",
        [
            "SELECT * FROM fato_vendas",
            "  select id from dim_produto",
            "SELECT\nid FROM dim_tempo",
            "\t SELECT COUNT(*) FROM fato_estoque",
            "SELECT id_venda, valor_total FROM fato_vendas WHERE ano = 2024",
        ],
    )
    def test_allowed_stmt_accepts_select(self, sql: str) -> None:
        assert ALLOWED_STMT.match(sql)

    @pytest.mark.parametrize(
        "sql",
        [
            "INSERT INTO fato_vendas VALUES (1)",
            "DROP TABLE fato_vendas",
            "UPDATE dim_loja SET gerente = 'x'",
            "DELETE FROM fato_vendas",
            "ALTER TABLE fato_vendas ADD COLUMN x INT",
            "CREATE TABLE pwned (id INT)",
            "TRUNCATE fato_vendas",
            "; SELECT * FROM fato_vendas",
            "",
        ],
    )
    def test_allowed_stmt_rejects_non_select(self, sql: str) -> None:
        assert not ALLOWED_STMT.match(sql)


# ---------------------------------------------------------------------------
# list_tools — verifies tool catalogue without a live server
# ---------------------------------------------------------------------------


class TestListTools:
    def test_list_tools_returns_three_tools(self) -> None:
        tools = list_tools()
        assert len(tools) == 3

    def test_list_tools_correct_names(self) -> None:
        names = {t.name for t in list_tools()}
        assert names == {"list_tables", "describe_schema", "execute_read_only_query"}

    def test_describe_schema_has_required_table_name_param(self) -> None:
        tool = next(t for t in list_tools() if t.name == "describe_schema")
        assert "table_name" in tool.inputSchema["required"]

    def test_execute_read_only_query_has_required_sql_param(self) -> None:
        tool = next(t for t in list_tools() if t.name == "execute_read_only_query")
        assert "sql" in tool.inputSchema["required"]

    def test_list_tables_has_no_required_params(self) -> None:
        tool = next(t for t in list_tools() if t.name == "list_tables")
        assert tool.inputSchema.get("required", []) == []

    def test_all_tools_have_descriptions(self) -> None:
        for tool in list_tools():
            assert tool.description, f"Tool '{tool.name}' is missing a description"


# ---------------------------------------------------------------------------
# register_tools — READ-ONLY guard exercised via the internal call_tool handler
#
# The MCP Server stores the decorated handler differently across versions.
# We locate it with a best-effort approach; skip if unavailable.
# ---------------------------------------------------------------------------


def _get_registered_handler(app):
    """Return a callable compatible with (name, arguments) for the MCP call_tool handler."""
    for attr in ("_tool_handler", "_call_tool_handler", "call_tool_handler"):
        handler = getattr(app, attr, None)
        if handler is not None:
            return handler

    # MCP 1.x stores the outer handler in request_handlers[CallToolRequest].
    # Wrap it so callers can still use (name, arguments) semantics.
    for key, val in getattr(app, "request_handlers", {}).items():
        if "CallToolRequest" in str(key):
            async def _compat(name: str, arguments: dict, _h=val):
                from mcp.types import CallToolRequest, CallToolRequestParams

                req = CallToolRequest(
                    method="tools/call",
                    params=CallToolRequestParams(name=name, arguments=arguments),
                )
                res = await _h(req)
                if hasattr(res, "root") and getattr(res.root, "isError", False):
                    raise ValueError(res.root.content[0].text)
                return res

            return _compat

    return None


@pytest.mark.asyncio
async def test_execute_read_only_rejects_non_select(mock_pg_conn) -> None:
    """execute_read_only_query raises an error for non-SELECT via the registered handler."""
    pytest.importorskip("mcp")

    from mcp.server import Server

    from contextualize.mcp_server.tools import register_tools

    conn, _ = mock_pg_conn
    app = Server("test-server")
    register_tools(app, conn)

    handler = _get_registered_handler(app)
    if handler is None:
        pytest.skip("Could not locate registered call_tool handler — MCP internals changed")

    with pytest.raises((ValueError, Exception), match="[Oo]nly SELECT|permitted"):
        await handler("execute_read_only_query", {"sql": "DROP TABLE fato_vendas"})


@pytest.mark.asyncio
async def test_execute_read_only_accepts_select(mock_pg_conn) -> None:
    """execute_read_only_query returns TextContent for a valid SELECT statement."""
    pytest.importorskip("mcp")

    from unittest.mock import MagicMock

    from mcp.server import Server

    from contextualize.mcp_server.tools import register_tools

    conn, cursor = mock_pg_conn
    cursor.fetchmany.return_value = []
    col_desc = MagicMock()
    col_desc.__getitem__ = MagicMock(return_value="total")
    cursor.description = [col_desc]

    app = Server("test-server")
    register_tools(app, conn)

    handler = _get_registered_handler(app)
    if handler is None:
        pytest.skip("Could not locate registered call_tool handler — MCP internals changed")

    result = await handler("execute_read_only_query", {"sql": "SELECT COUNT(*) FROM fato_vendas"})
    assert result is not None
