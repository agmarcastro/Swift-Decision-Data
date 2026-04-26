from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class DepartamentoEnum(str, Enum):
    COMPUTING = "Computing"
    TELEPHONY = "Telephony"
    TV_AUDIO = "TV/Audio"
    GAMING = "Gaming"
    HOME_APPLIANCES = "Home Appliances"
    PRINTING = "Printing"


class ModeloDimProduto(BaseModel):
    id_produto: int
    sku: str
    nome_produto: str
    marca: str
    departamento: DepartamentoEnum
    categoria: str
