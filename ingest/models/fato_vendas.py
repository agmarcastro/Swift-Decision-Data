from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, Field, model_validator


class ModeloFatoVendas(BaseModel):
    id_venda: int
    id_produto: int
    id_cliente: int
    id_loja: int
    id_tempo: int
    data_venda: date
    quantidade: int = Field(gt=0)
    valor_unitario: Decimal = Field(gt=0, decimal_places=2)
    valor_total: Decimal = Field(gt=0, decimal_places=2)
    custo_total: Decimal = Field(ge=0, decimal_places=2)
    valor_desconto: Decimal = Field(ge=0, decimal_places=2)

    @model_validator(mode="after")
    def validar_consistencia_valor_total(self) -> Self:
        esperado = self.quantidade * self.valor_unitario - self.valor_desconto
        if abs(self.valor_total - esperado) > Decimal("0.02"):
            raise ValueError(
                f"valor_total inconsistente: esperado {esperado}, recebido {self.valor_total}"
            )
        return self
