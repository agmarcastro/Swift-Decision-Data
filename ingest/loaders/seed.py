#!/usr/bin/env python3
"""Seed CLI: apply schema, validate loaded data.

Usage: python -m ingest.loaders.seed
Env:   POSTGRES_ADMIN_URL (required)

Note: ShadowTraffic writes data directly to PostgreSQL. This script applies
      DDL and validates data quality via Pydantic after ShadowTraffic runs.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import psycopg2

from ingest.loaders.postgres_loader import validate_all_tables

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

SQL_DIR = Path(__file__).parent.parent / "sql"


def apply_sql_file(conn: psycopg2.extensions.connection, path: Path) -> None:
    sql = path.read_text()
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()


def main() -> None:
    url = os.environ.get("POSTGRES_ADMIN_URL")
    if not url:
        logger.error("POSTGRES_ADMIN_URL not set")
        sys.exit(1)

    conn = psycopg2.connect(url)
    try:
        logger.info("Applying schema...")
        apply_sql_file(conn, SQL_DIR / "schema.sql")
        apply_sql_file(conn, SQL_DIR / "create_readonly_user.sql")

        logger.info("Validating data quality...")
        results = validate_all_tables(conn)

        print("\n=== InfoAgent Seed Validation Report ===")
        print(f"{'Table':<25} {'Total':>8} {'Valid':>8} {'Invalid':>8}")
        print("-" * 55)
        for r in results:
            print(f"{r['table']:<25} {r['total']:>8} {r['valid']:>8} {r['invalid']:>8}")

        total_invalid = sum(r["invalid"] for r in results)
        if total_invalid > 0:
            logger.warning("%d invalid records found across all tables", total_invalid)
        else:
            logger.info("All records passed Pydantic validation")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
