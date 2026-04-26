from __future__ import annotations

import asyncio
import logging
import os

import psycopg2
from mcp.server import Server
from mcp.server.stdio import stdio_server

from contextualize.mcp_server.tools import list_tools, register_tools

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

app = Server("infoagent-mcp")


@app.list_tools()
async def handle_list_tools():
    return list_tools()


async def main() -> None:
    url = os.environ["POSTGRES_READONLY_URL"]
    conn = psycopg2.connect(url)
    conn.autocommit = True
    logger.info("Connected to PostgreSQL (read-only)")
    register_tools(app, conn)
    async with stdio_server() as (read_stream, write_stream):
        logger.info("MCP server infoagent-mcp started on stdio")
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
