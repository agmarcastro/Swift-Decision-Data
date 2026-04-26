from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class CategoriaClienteEnum(str, Enum):
    BRONZE = "Bronze"
    SILVER = "Silver"
    GOLD = "Gold"


class GeneroEnum(str, Enum):
    M = "M"
    F = "F"
    NAO_INFORMADO = "NI"


class ModeloDimCliente(BaseModel):
    id_cliente: int
    categoria_clube_info: CategoriaClienteEnum
    estado: str
    cidade: str
    genero: GeneroEnum
    faixa_etaria: str
