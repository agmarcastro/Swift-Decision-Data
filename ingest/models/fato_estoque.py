from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class ModeloFatoEstoque(BaseModel):
    id_produto: int
    id_loja: int
    data_posicao: date
    qtd_disponivel: int = Field(ge=0)
    qtd_transito: int = Field(ge=0)
