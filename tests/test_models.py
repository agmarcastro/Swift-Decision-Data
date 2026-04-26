from __future__ import annotations

import pytest
from pydantic import ValidationError

from ingest.models import (
    CategoriaClienteEnum,
    DepartamentoEnum,
    GeneroEnum,
    ModeloDimCliente,
    ModeloDimProduto,
    ModeloDimTempo,
    ModeloFatoEstoque,
    ModeloFatoVendas,
)


# ---------------------------------------------------------------------------
# ModeloFatoVendas
# ---------------------------------------------------------------------------


class TestModeloFatoVendas:
    def test_valid_record(self, minimal_fato_vendas_row: dict) -> None:
        record = ModeloFatoVendas.model_validate(minimal_fato_vendas_row)
        assert record.id_venda == 1
        assert record.quantidade == 2
        assert str(record.valor_total) == "1000.00"

    def test_valor_total_consistency_passes(self, minimal_fato_vendas_row: dict) -> None:
        row = {**minimal_fato_vendas_row, "valor_total": "1000.01"}
        record = ModeloFatoVendas.model_validate(row)
        assert record.valor_total is not None

    def test_valor_total_consistency_fails(self, minimal_fato_vendas_row: dict) -> None:
        row = {**minimal_fato_vendas_row, "valor_total": "900.00"}
        with pytest.raises(ValidationError, match="valor_total inconsistente"):
            ModeloFatoVendas.model_validate(row)

    def test_valor_total_with_discount(self) -> None:
        # 3 * 100 - 10 = 290
        record = ModeloFatoVendas.model_validate(
            {
                "id_venda": 2,
                "id_produto": 1,
                "id_cliente": 1,
                "id_loja": 1,
                "id_tempo": 1,
                "data_venda": "2024-06-15",
                "quantidade": 3,
                "valor_unitario": "100.00",
                "valor_total": "290.00",
                "custo_total": "210.00",
                "valor_desconto": "10.00",
            }
        )
        assert str(record.valor_total) == "290.00"

    def test_negative_quantidade_fails(self, minimal_fato_vendas_row: dict) -> None:
        row = {**minimal_fato_vendas_row, "quantidade": 0}
        with pytest.raises(ValidationError):
            ModeloFatoVendas.model_validate(row)

    def test_negative_valor_unitario_fails(self, minimal_fato_vendas_row: dict) -> None:
        row = {**minimal_fato_vendas_row, "valor_unitario": "0.00"}
        with pytest.raises(ValidationError):
            ModeloFatoVendas.model_validate(row)


# ---------------------------------------------------------------------------
# ModeloDimProduto
# ---------------------------------------------------------------------------


class TestModeloDimProduto:
    _VALID_BASE = {
        "id_produto": 1,
        "sku": "SKU-001",
        "nome_produto": "Notebook Pro",
        "marca": "Acme",
        "categoria": "Laptops",
    }

    @pytest.mark.parametrize(
        "dept",
        [
            "Computing",
            "Telephony",
            "TV/Audio",
            "Gaming",
            "Home Appliances",
            "Printing",
        ],
    )
    def test_valid_departamento_enum(self, dept: str) -> None:
        record = ModeloDimProduto.model_validate({**self._VALID_BASE, "departamento": dept})
        assert record.departamento == DepartamentoEnum(dept)

    def test_invalid_departamento_fails(self) -> None:
        with pytest.raises(ValidationError):
            ModeloDimProduto.model_validate({**self._VALID_BASE, "departamento": "Electronics"})


# ---------------------------------------------------------------------------
# ModeloDimCliente
# ---------------------------------------------------------------------------


class TestModeloDimCliente:
    _VALID_BASE = {
        "id_cliente": 1,
        "estado": "SP",
        "cidade": "São Paulo",
        "faixa_etaria": "25-34",
    }

    @pytest.mark.parametrize("categoria", ["Bronze", "Silver", "Gold"])
    def test_valid_categoria_clube_info(self, categoria: str) -> None:
        record = ModeloDimCliente.model_validate(
            {**self._VALID_BASE, "categoria_clube_info": categoria, "genero": "M"}
        )
        assert record.categoria_clube_info == CategoriaClienteEnum(categoria)

    def test_invalid_categoria_clube_info_fails(self) -> None:
        with pytest.raises(ValidationError):
            ModeloDimCliente.model_validate(
                {**self._VALID_BASE, "categoria_clube_info": "Platinum", "genero": "M"}
            )

    @pytest.mark.parametrize("genero", ["M", "F", "NI"])
    def test_valid_genero(self, genero: str) -> None:
        record = ModeloDimCliente.model_validate(
            {**self._VALID_BASE, "categoria_clube_info": "Gold", "genero": genero}
        )
        assert record.genero == GeneroEnum(genero)

    def test_invalid_genero_fails(self) -> None:
        with pytest.raises(ValidationError):
            ModeloDimCliente.model_validate(
                {**self._VALID_BASE, "categoria_clube_info": "Gold", "genero": "X"}
            )


# ---------------------------------------------------------------------------
# ModeloDimTempo
# ---------------------------------------------------------------------------


class TestModeloDimTempo:
    _VALID_BASE = {
        "id_tempo": 1,
        "data": "2024-06-15",
        "dia_semana": "Saturday",
        "mes": 6,
        "ano": 2024,
    }

    @pytest.mark.parametrize("flg", [True, False, 1, 0])
    def test_flg_feriado_boolean(self, flg: bool | int) -> None:
        record = ModeloDimTempo.model_validate({**self._VALID_BASE, "flg_feriado": flg})
        assert isinstance(record.flg_feriado, bool)


# ---------------------------------------------------------------------------
# ModeloFatoEstoque
# ---------------------------------------------------------------------------


class TestModeloFatoEstoque:
    _VALID_BASE = {
        "id_produto": 1,
        "id_loja": 1,
        "data_posicao": "2024-06-15",
        "qtd_transito": 5,
    }

    def test_negative_qtd_fails(self) -> None:
        with pytest.raises(ValidationError):
            ModeloFatoEstoque.model_validate({**self._VALID_BASE, "qtd_disponivel": -1})

    def test_zero_qtd_passes(self) -> None:
        record = ModeloFatoEstoque.model_validate({**self._VALID_BASE, "qtd_disponivel": 0})
        assert record.qtd_disponivel == 0
