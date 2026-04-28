from __future__ import annotations

import logging

import pytest

from ingest.loaders.postgres_loader import validate_all_tables, validate_table
from ingest.models import ModeloFatoVendas


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_ROW = {
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

_INVALID_ROW = {
    **_VALID_ROW,
    "id_venda": 2,
    "valor_total": "9999.00",  # inconsistent: 2*500-0 = 1000, not 9999
}


def _make_cursor_iter(cursor_mock, rows: list[dict]) -> None:
    """Configure cursor_mock to iterate over rows (simulates RealDictCursor)."""
    cursor_mock.__iter__ = lambda self: iter(rows)


# ---------------------------------------------------------------------------
# validate_table
# ---------------------------------------------------------------------------


class TestValidateTable:
    def test_all_valid_rows(self, mock_pg_conn) -> None:
        conn, cursor = mock_pg_conn
        _make_cursor_iter(cursor, [_VALID_ROW, _VALID_ROW])

        result = validate_table(conn, "fato_vendas", ModeloFatoVendas)

        assert result["table"] == "fato_vendas"
        assert result["total"] == 2
        assert result["valid"] == 2
        assert result["invalid"] == 0

    def test_validate_table_counts_valid_and_invalid(self, mock_pg_conn) -> None:
        conn, cursor = mock_pg_conn
        _make_cursor_iter(cursor, [_VALID_ROW, _INVALID_ROW])

        result = validate_table(conn, "fato_vendas", ModeloFatoVendas)

        assert result["total"] == 2
        assert result["valid"] == 1
        assert result["invalid"] == 1

    def test_empty_table_returns_zero_counts(self, mock_pg_conn) -> None:
        conn, cursor = mock_pg_conn
        _make_cursor_iter(cursor, [])

        result = validate_table(conn, "fato_vendas", ModeloFatoVendas)

        assert result["total"] == 0
        assert result["valid"] == 0
        assert result["invalid"] == 0

    def test_invalid_row_logged_as_warning(self, mock_pg_conn, caplog) -> None:
        conn, cursor = mock_pg_conn
        _make_cursor_iter(cursor, [_INVALID_ROW])

        with caplog.at_level(logging.WARNING, logger="ingest.loaders.postgres_loader"):
            validate_table(conn, "fato_vendas", ModeloFatoVendas)

        assert any("Invalid row" in r.message for r in caplog.records)

    def test_pk_column_appears_in_warning(self, mock_pg_conn, caplog) -> None:
        conn, cursor = mock_pg_conn
        _make_cursor_iter(cursor, [_INVALID_ROW])

        with caplog.at_level(logging.WARNING, logger="ingest.loaders.postgres_loader"):
            validate_table(conn, "fato_vendas", ModeloFatoVendas)

        warning_text = " ".join(r.message for r in caplog.records)
        assert "id_venda" in warning_text or "fato_vendas" in warning_text


# ---------------------------------------------------------------------------
# validate_all_tables
# ---------------------------------------------------------------------------


class TestValidateAllTables:
    def test_validate_all_tables_returns_six_results(self, mock_pg_conn) -> None:
        conn, cursor = mock_pg_conn
        # All tables empty — iteration yields nothing
        cursor.__iter__ = lambda self: iter([])

        results = validate_all_tables(conn)

        assert len(results) == 7

    def test_validate_all_tables_result_keys(self, mock_pg_conn) -> None:
        conn, cursor = mock_pg_conn
        cursor.__iter__ = lambda self: iter([])

        results = validate_all_tables(conn)

        for result in results:
            assert {"table", "total", "valid", "invalid"} == set(result.keys())

    def test_validate_all_tables_table_names(self, mock_pg_conn) -> None:
        conn, cursor = mock_pg_conn
        cursor.__iter__ = lambda self: iter([])

        results = validate_all_tables(conn)
        table_names = {r["table"] for r in results}

        expected = {
            "fato_vendas",
            "fato_estoque",
            "dim_produto",
            "dim_cliente",
            "dim_loja",
            "dim_tempo",
            "reviews",
        }
        assert table_names == expected
