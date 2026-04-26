from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class ModeloDimTempo(BaseModel):
    id_tempo: int
    data: date
    dia_semana: str
    mes: int = Field(ge=1, le=12)
    ano: int = Field(ge=2020)
    flg_feriado: bool
