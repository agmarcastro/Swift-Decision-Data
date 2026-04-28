from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class ModeloReview(BaseModel):
    id_review: int
    id_produto: int
    id_cliente: int
    data_review: date
    nota: int = Field(ge=1, le=5)
    sentimento: str = Field(pattern=r"^(positivo|neutro|negativo)$")
    texto_review: str = Field(min_length=20, max_length=1000)
