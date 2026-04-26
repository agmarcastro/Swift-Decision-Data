from __future__ import annotations

import logging
from typing import Type

import psycopg2
import psycopg2.extensions
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel, ValidationError

from ingest.models import (
    ModeloFatoVendas,
    ModeloFatoEstoque,
    ModeloDimProduto,
    ModeloDimCliente,
    ModeloDimLoja,
    ModeloDimTempo,
)

logger = logging.getLogger(__name__)

_TABLE_MODEL_MAP: dict[str, Type[BaseModel]] = {
    "fato_vendas": ModeloFatoVendas,
    "fato_estoque": ModeloFatoEstoque,
    "dim_produto": ModeloDimProduto,
    "dim_cliente": ModeloDimCliente,
    "dim_loja": ModeloDimLoja,
    "dim_tempo": ModeloDimTempo,
}

_TABLE_PK_MAP: dict[str, str] = {
    "fato_vendas": "id_venda",
    "fato_estoque": "id_estoque",
    "dim_produto": "id_produto",
    "dim_cliente": "id_cliente",
    "dim_loja": "id_loja",
    "dim_tempo": "id_tempo",
}


def validate_table(
    conn: psycopg2.extensions.connection,
    table: str,
    model: Type[BaseModel],
) -> dict[str, int | str]:
    total = valid = invalid = 0
    pk = _TABLE_PK_MAP.get(table, "id")

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(f"SELECT * FROM {table}")
        for row in cur:
            total += 1
            try:
                model.model_validate(dict(row))
                valid += 1
            except ValidationError as e:
                invalid += 1
                logger.warning(
                    "Invalid row in %s (%s=%s): %s",
                    table,
                    pk,
                    row.get(pk, "?"),
                    e,
                )

    return {"table": table, "total": total, "valid": valid, "invalid": invalid}


def validate_all_tables(
    conn: psycopg2.extensions.connection,
) -> list[dict[str, int | str]]:
    return [
        validate_table(conn, table, model)
        for table, model in _TABLE_MODEL_MAP.items()
    ]
