from __future__ import annotations

import hashlib
import logging
import re
import time

import psycopg2
import psycopg2.extensions
from mcp.server import Server
from mcp.types import TextContent, Tool

logger = logging.getLogger(__name__)

ALLOWED_STMT = re.compile(r"^\s*SELECT\b", re.IGNORECASE)
ROW_CAP = 500


def list_tools() -> list[Tool]:
    return [
        Tool(
            name="list_tables",
            description="List all tables in the public schema of the PostgreSQL database.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="describe_schema",
            description=(
                "Return column names, data types, and nullability for a given table. "
                "Accepts both uppercase and lowercase table names."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "Name of the table to describe (case-insensitive).",
                    }
                },
                "required": ["table_name"],
            },
        ),
        Tool(
            name="execute_read_only_query",
            description=(
                "Execute a SELECT statement against the database. "
                "Only SELECT statements are permitted. Returns at most 500 rows."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "A SELECT SQL statement to execute.",
                    }
                },
                "required": ["sql"],
            },
        ),
    ]


def register_tools(app: Server, conn: psycopg2.extensions.connection) -> None:

    @app.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        start = time.perf_counter()
        try:
            match name:
                case "list_tables":
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT table_name FROM information_schema.tables "
                            "WHERE table_schema = 'public' ORDER BY table_name"
                        )
                        tables = [row[0] for row in cur.fetchall()]
                    duration = time.perf_counter() - start
                    logger.info(
                        "tool=%s duration_ms=%.1f table_count=%d",
                        name,
                        duration * 1000,
                        len(tables),
                    )
                    return [TextContent(type="text", text=str(tables))]

                case "describe_schema":
                    table_name = arguments["table_name"].lower()
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT column_name, data_type, is_nullable "
                            "FROM information_schema.columns "
                            "WHERE table_name = %s ORDER BY ordinal_position",
                            (table_name,),
                        )
                        cols = cur.fetchall()
                    duration = time.perf_counter() - start
                    logger.info(
                        "tool=%s table=%s duration_ms=%.1f col_count=%d",
                        name,
                        table_name,
                        duration * 1000,
                        len(cols),
                    )
                    return [TextContent(type="text", text=str(cols))]

                case "execute_read_only_query":
                    sql = arguments["sql"]
                    if not ALLOWED_STMT.match(sql):
                        raise ValueError("Only SELECT statements are permitted.")
                    sql_hash = hashlib.sha256(sql.encode()).hexdigest()[:12]
                    with conn.cursor() as cur:
                        cur.execute(sql)
                        rows = cur.fetchmany(ROW_CAP)
                        col_names = [d[0] for d in cur.description]
                    duration = time.perf_counter() - start
                    logger.info(
                        "tool=%s sql_hash=%s duration_ms=%.1f row_count=%d",
                        name,
                        sql_hash,
                        duration * 1000,
                        len(rows),
                    )
                    return [
                        TextContent(
                            type="text",
                            text=str([dict(zip(col_names, row)) for row in rows]),
                        )
                    ]

                case _:
                    raise ValueError(f"Unknown tool: {name}")

        except ValueError:
            raise
        except Exception as exc:
            duration = time.perf_counter() - start
            logger.error("tool=%s duration_ms=%.1f error=%s", name, duration * 1000, exc)
            return [TextContent(type="text", text=f"Error executing {name}: {exc}")]
