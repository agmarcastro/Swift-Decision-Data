-- =============================================================================
-- InfoAgent Star Schema - PostgreSQL DDL
-- Brazilian Technology Retail Company
-- =============================================================================
-- Table creation order: dimensions first, then facts (respects FK constraints)
-- =============================================================================


-- =============================================================================
-- DIMENSION TABLES
-- =============================================================================

-- -----------------------------------------------------------------------------
-- DIM_PRODUTO: Product catalog dimension
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_produto (
    id_produto       SERIAL          PRIMARY KEY,
    sku              VARCHAR(50)     UNIQUE NOT NULL,
    nome_produto     VARCHAR(200)    NOT NULL,
    marca            VARCHAR(100)    NOT NULL,
    departamento     VARCHAR(50)     NOT NULL
                     CHECK (departamento IN (
                         'Computing',
                         'Telephony',
                         'TV/Audio',
                         'Gaming',
                         'Home Appliances',
                         'Printing'
                     )),
    categoria        VARCHAR(100)    NOT NULL
);


-- -----------------------------------------------------------------------------
-- DIM_CLIENTE: Customer dimension
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_cliente (
    id_cliente           SERIAL      PRIMARY KEY,
    categoria_clube_info VARCHAR(10) NOT NULL
                         CHECK (categoria_clube_info IN ('Bronze', 'Silver', 'Gold')),
    estado               CHAR(2)     NOT NULL,
    cidade               VARCHAR(100) NOT NULL,
    genero               CHAR(2)     NOT NULL
                         CHECK (genero IN ('M', 'F', 'NI')),
    faixa_etaria         VARCHAR(20) NOT NULL
);


-- -----------------------------------------------------------------------------
-- DIM_LOJA: Store dimension
-- Note: 'mall' in nome_loja identifies locations within shopping centers.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_loja (
    id_loja    SERIAL          PRIMARY KEY,
    nome_loja  VARCHAR(100)    NOT NULL,
    regiao     VARCHAR(50)     NOT NULL,
    gerente    VARCHAR(100)    NOT NULL
);


-- -----------------------------------------------------------------------------
-- DIM_TEMPO: Date/time dimension
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_tempo (
    id_tempo    SERIAL          PRIMARY KEY,
    data        DATE            UNIQUE NOT NULL,
    dia_semana  VARCHAR(15)     NOT NULL,
    mes         INTEGER         NOT NULL CHECK (mes BETWEEN 1 AND 12),
    ano         INTEGER         NOT NULL,
    flg_feriado BOOLEAN         NOT NULL DEFAULT FALSE
);

CREATE INDEX idx_dim_tempo_data ON dim_tempo(data);


-- =============================================================================
-- FACT TABLES
-- =============================================================================

-- -----------------------------------------------------------------------------
-- FATO_VENDAS: Sales transaction fact table
-- Grain: one row per individual sales transaction line
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fato_vendas (
    id_venda        SERIAL          PRIMARY KEY,
    id_produto      INTEGER         NOT NULL REFERENCES dim_produto(id_produto),
    id_cliente      INTEGER         NOT NULL REFERENCES dim_cliente(id_cliente),
    id_loja         INTEGER         NOT NULL REFERENCES dim_loja(id_loja),
    id_tempo        INTEGER         NOT NULL REFERENCES dim_tempo(id_tempo),
    data_venda      DATE            NOT NULL,
    quantidade      INTEGER         NOT NULL CHECK (quantidade > 0),
    valor_unitario  NUMERIC(12,2)   NOT NULL CHECK (valor_unitario > 0),
    valor_total     NUMERIC(12,2)   NOT NULL CHECK (valor_total > 0),
    custo_total     NUMERIC(12,2)   NOT NULL CHECK (custo_total >= 0),
    valor_desconto  NUMERIC(12,2)   NOT NULL DEFAULT 0 CHECK (valor_desconto >= 0)
);

CREATE INDEX idx_fato_vendas_data         ON fato_vendas(data_venda);
CREATE INDEX idx_fato_vendas_produto_tempo ON fato_vendas(id_produto, id_tempo);
CREATE INDEX idx_fato_vendas_loja_tempo    ON fato_vendas(id_loja, id_tempo);


-- -----------------------------------------------------------------------------
-- FATO_ESTOQUE: Inventory periodic snapshot fact table
-- Grain: one row per product, per store, per calendar date (daily snapshot)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fato_estoque (
    id_estoque      SERIAL      PRIMARY KEY,
    id_produto      INTEGER     NOT NULL REFERENCES dim_produto(id_produto),
    id_loja         INTEGER     NOT NULL REFERENCES dim_loja(id_loja),
    data_posicao    DATE        NOT NULL,
    qtd_disponivel  INTEGER     NOT NULL CHECK (qtd_disponivel >= 0),
    qtd_transito    INTEGER     NOT NULL DEFAULT 0 CHECK (qtd_transito >= 0),
    UNIQUE (id_produto, id_loja, data_posicao)
);

CREATE INDEX idx_fato_estoque_produto_loja ON fato_estoque(id_produto, id_loja, data_posicao);

-- -----------------------------------------------------------------------------
-- REVIEWS: Customer review fact-like table (synthetic via ShadowTraffic)
-- Grain: one row per customer review of a product
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS reviews (
    id_review     SERIAL          PRIMARY KEY,
    id_produto    INTEGER         NOT NULL REFERENCES dim_produto(id_produto),
    id_cliente    INTEGER         NOT NULL REFERENCES dim_cliente(id_cliente),
    data_review   DATE            NOT NULL,
    nota          INTEGER         NOT NULL CHECK (nota BETWEEN 1 AND 5),
    sentimento    VARCHAR(10)     NOT NULL
                  CHECK (sentimento IN ('positivo', 'neutro', 'negativo')),
    texto_review  TEXT            NOT NULL CHECK (length(texto_review) >= 20)
);

CREATE INDEX idx_reviews_produto    ON reviews(id_produto);
CREATE INDEX idx_reviews_cliente    ON reviews(id_cliente);
CREATE INDEX idx_reviews_data       ON reviews(data_review);
CREATE INDEX idx_reviews_sentimento ON reviews(sentimento);
