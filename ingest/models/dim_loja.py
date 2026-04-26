from __future__ import annotations

from pydantic import BaseModel


class ModeloDimLoja(BaseModel):
    id_loja: int
    nome_loja: str
    regiao: str
    gerente: str
