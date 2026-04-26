from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def minimal_fato_vendas_row() -> dict:
    """Minimal valid FATO_VENDAS row dict."""
    return {
        "id_venda": 1,
        "id_produto": 1,
        "id_cliente": 1,
        "id_loja": 1,
        "id_tempo": 1,
        "data_venda": "2024-06-15",
        "quantidade": 2,
        "valor_unitario": "500.00",
        "valor_total": "1000.00",
        "custo_total": "700.00",
        "valor_desconto": "0.00",
    }


@pytest.fixture
def mock_pg_conn():
    """Mock psycopg2 connection for unit tests that don't need a real DB.

    The cursor context manager is wired so that:
    - ``conn.cursor()`` and ``conn.cursor(cursor_factory=...)`` both return the same
      cursor mock via the context-manager protocol.
    - The caller can configure ``cursor.fetchall``, ``cursor.fetchmany``, and
      iteration (``__iter__``) independently per test.
    """
    conn = MagicMock()
    cursor = MagicMock()

    cursor_ctx = MagicMock()
    cursor_ctx.__enter__ = MagicMock(return_value=cursor)
    cursor_ctx.__exit__ = MagicMock(return_value=False)

    conn.cursor.return_value = cursor_ctx

    return conn, cursor
