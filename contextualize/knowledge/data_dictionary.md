# InfoAgent Data Dictionary

**Schema:** PostgreSQL Star Schema  
**Domain:** Brazilian Technology Retail  
**Last updated:** 2026-04-24

This document describes every table and column in the InfoAgent analytical star schema. The schema contains 4 dimension tables and 2 fact tables. All monetary values are stored in Brazilian Reais (BRL). All date columns follow the `YYYY-MM-DD` calendar.

---

## Table of Contents

1. [DIM_PRODUTO](#dim_produto)
2. [DIM_CLIENTE](#dim_cliente)
3. [DIM_LOJA](#dim_loja)
4. [DIM_TEMPO](#dim_tempo)
5. [FATO_VENDAS](#fato_vendas)
6. [FATO_ESTOQUE](#fato_estoque)

---

## DIM_PRODUTO

**Type:** Dimension (SCD Type 1)  
**Description:** Product catalog for all SKUs sold or stocked by the retailer. Each row represents one distinct, sellable product. The `departamento` column organises products into the six top-level merchandising areas used by the business. `categoria` provides a finer-grained classification within each department. This dimension is the target of foreign keys in both fact tables.

| Column Name  | Data Type    | Nullable | Description |
|--------------|--------------|----------|-------------|
| id_produto   | SERIAL (INT) | NOT NULL | Surrogate primary key, auto-incremented by the database. |
| sku          | VARCHAR(50)  | NOT NULL | Stock Keeping Unit — the natural business key assigned by the product team. Unique across the catalogue. |
| nome_produto | VARCHAR(200) | NOT NULL | Full commercial product name as displayed to customers and used in reports. |
| marca        | VARCHAR(100) | NOT NULL | Brand or manufacturer name (e.g., "Samsung", "Apple", "Multilaser"). |
| departamento | VARCHAR(50)  | NOT NULL | Top-level merchandising department. Allowed values: `'Computing'`, `'Telephony'`, `'TV/Audio'`, `'Gaming'`, `'Home Appliances'`, `'Printing'`. Enforced by CHECK constraint. |
| categoria    | VARCHAR(100) | NOT NULL | Sub-category within the department (e.g., "Notebooks", "Smartphones", "Smart TVs"). Free-text; no CHECK constraint — values are maintained by the product team. |

---

## DIM_CLIENTE

**Type:** Dimension (SCD Type 1)  
**Description:** Anonymised customer profile dimension. Each row represents one registered customer in the InfoClub loyalty programme. No personally identifiable information (PII) such as name, CPF, or email is stored in the analytical layer. Geography is captured at the city and state level. The `faixa_etaria` age band is assigned at registration time and is not recalculated automatically when a customer ages into a new band.

| Column Name          | Data Type   | Nullable | Description |
|----------------------|-------------|----------|-------------|
| id_cliente           | SERIAL (INT) | NOT NULL | Surrogate primary key, auto-incremented by the database. |
| categoria_clube_info | VARCHAR(10) | NOT NULL | Loyalty tier in the InfoClub programme. Allowed values: `'Bronze'`, `'Silver'`, `'Gold'`. Tier is determined by cumulative annual spend. Enforced by CHECK constraint. |
| estado               | CHAR(2)     | NOT NULL | Brazilian state abbreviation (UF) of the customer's registered address (e.g., `'SP'`, `'RJ'`, `'MG'`). |
| cidade               | VARCHAR(100)| NOT NULL | City of the customer's registered address. |
| genero               | CHAR(2)     | NOT NULL | Customer's self-declared gender. Allowed values: `'M'` (male), `'F'` (female), `'NI'` (not informed / prefer not to say). Enforced by CHECK constraint. |
| faixa_etaria         | VARCHAR(20) | NOT NULL | Age band at registration time (e.g., `'18-24'`, `'25-34'`, `'35-44'`, `'45-54'`, `'55+'`). Exact band labels are defined by the CRM team. |

---

## DIM_LOJA

**Type:** Dimension (SCD Type 1)  
**Description:** Physical and virtual store dimension. Each row represents one retail location or sales channel operated by the company. The `regiao` column maps stores to the company's internal regional sales territories, which do not necessarily correspond to Brazilian geographic regions. `gerente` holds the name of the current store manager and is overwritten (SCD1) when a management change occurs.

> **Note:** Stores with the word `'mall'` in `nome_loja` are located inside shopping centres (*shoppings*) and are subject to different operating hours, holiday trading rules, and cost structures than street-facing stores.

| Column Name | Data Type    | Nullable | Description |
|-------------|--------------|----------|-------------|
| id_loja     | SERIAL (INT) | NOT NULL | Surrogate primary key, auto-incremented by the database. |
| nome_loja   | VARCHAR(100) | NOT NULL | Display name of the store. Names containing `'mall'` indicate a shopping centre location. |
| regiao      | VARCHAR(50)  | NOT NULL | Internal commercial region to which the store belongs (e.g., `'Sudeste'`, `'Sul'`, `'Norte'`). |
| gerente     | VARCHAR(100) | NOT NULL | Full name of the current store manager. Updated in place when the manager changes (SCD Type 1). |

---

## DIM_TEMPO

**Type:** Dimension (Static calendar — populated once, never updated)  
**Description:** Date dimension pre-populated with one row per calendar day for the analytical time range supported by the schema. Fact tables join to this dimension via `id_tempo` to enable consistent time-based slicing without performing date arithmetic directly in queries. The `flg_feriado` flag is populated from the official Brazilian national public holiday calendar; state-level and municipal holidays are **not** included unless explicitly loaded by the data engineering team.

> **Brazilian public holidays note:** `flg_feriado = TRUE` marks nationally observed holidays such as Carnaval, Tiradentes, Corpus Christi, Independencia, Finados, Proclamacao da Republica, Natal, and Ano Novo. Regional holidays (e.g., *Revolução Constitucionalista* in SP) are **not** flagged by default. Confirm coverage scope with the data engineering team before building holiday-based analyses.

| Column Name | Data Type    | Nullable | Description |
|-------------|--------------|----------|-------------|
| id_tempo    | SERIAL (INT) | NOT NULL | Surrogate primary key, auto-incremented by the database. |
| data        | DATE         | NOT NULL | Calendar date in `YYYY-MM-DD` format. Unique per row. Indexed via `idx_dim_tempo_data` for fast date-range lookups. |
| dia_semana  | VARCHAR(15)  | NOT NULL | Full name of the day of the week in Portuguese (e.g., `'Segunda-feira'`, `'Sabado'`, `'Domingo'`). |
| mes         | INTEGER      | NOT NULL | Month number (1 = January through 12 = December). Enforced by CHECK constraint `BETWEEN 1 AND 12`. |
| ano         | INTEGER      | NOT NULL | Four-digit calendar year (e.g., `2025`). |
| flg_feriado | BOOLEAN      | NOT NULL | `TRUE` if the date is a Brazilian national public holiday; `FALSE` otherwise. Defaults to `FALSE`. See note above regarding coverage scope. |

---

## FATO_VENDAS

**Type:** Fact — Transaction  
**Grain:** One row per individual sales transaction line (one product sold to one customer at one store on one date).  
**Description:** Central sales fact table capturing every completed sales transaction. Each row records the quantity and financial values for a single product line within a sale. Revenue analysis, margin analysis, discount tracking, and customer purchase behaviour are all served from this table. `valor_total` should equal `(quantidade * valor_unitario) - valor_desconto`; this relationship is enforced at ingestion time by the ETL pipeline, not by a database constraint.

**Foreign Keys:**

| FK Column  | References Table | References Column |
|------------|-----------------|-------------------|
| id_produto | dim_produto     | id_produto        |
| id_cliente | dim_cliente     | id_cliente        |
| id_loja    | dim_loja        | id_loja           |
| id_tempo   | dim_tempo       | id_tempo          |

| Column Name    | Data Type     | Nullable | Description |
|----------------|---------------|----------|-------------|
| id_venda       | SERIAL (INT)  | NOT NULL | Surrogate primary key, auto-incremented by the database. |
| id_produto     | INTEGER       | NOT NULL | Foreign key to `dim_produto.id_produto`. Identifies the product sold. |
| id_cliente     | INTEGER       | NOT NULL | Foreign key to `dim_cliente.id_cliente`. Identifies the purchasing customer. |
| id_loja        | INTEGER       | NOT NULL | Foreign key to `dim_loja.id_loja`. Identifies the store where the sale occurred. |
| id_tempo       | INTEGER       | NOT NULL | Foreign key to `dim_tempo.id_tempo`. Links to the calendar date record for the sale. |
| data_venda     | DATE          | NOT NULL | Calendar date of the sale in `YYYY-MM-DD` format. Denormalised from `dim_tempo` for direct date filtering without a join. Indexed via `idx_fato_vendas_data`. |
| quantidade     | INTEGER       | NOT NULL | Number of units sold in this transaction line. Must be greater than 0 (CHECK constraint). |
| valor_unitario | NUMERIC(12,2) | NOT NULL | List price per unit in BRL at the time of sale. Must be greater than 0 (CHECK constraint). |
| valor_total    | NUMERIC(12,2) | NOT NULL | Net transaction value in BRL after discounts: `(quantidade * valor_unitario) - valor_desconto`. Must be greater than 0 (CHECK constraint). |
| custo_total    | NUMERIC(12,2) | NOT NULL | Total cost of goods sold (COGS) in BRL for this line. Used for gross margin calculation: `valor_total - custo_total`. Must be >= 0 (CHECK constraint). |
| valor_desconto | NUMERIC(12,2) | NOT NULL | Monetary discount applied to this transaction line in BRL. Zero when no discount was applied. Always >= 0 (CHECK constraint). Defaults to `0`. |

---

## FATO_ESTOQUE

**Type:** Fact — Periodic Snapshot  
**Grain:** One row per product, per store, per calendar date (daily end-of-day inventory position).  
**Description:** Daily inventory snapshot fact table. Each row records the stock position for one product at one store at the close of business on a given date. This table supports stock availability analysis, stockout detection, and in-transit inventory tracking. Because this is a periodic snapshot, quantities are semi-additive: they can be summed across products and stores for a single date, but should **not** be summed across multiple dates (use the latest snapshot date or an average instead). The composite unique constraint on `(id_produto, id_loja, data_posicao)` prevents duplicate daily snapshots.

**Foreign Keys:**

| FK Column  | References Table | References Column |
|------------|-----------------|-------------------|
| id_produto | dim_produto     | id_produto        |
| id_loja    | dim_loja        | id_loja           |

| Column Name     | Data Type    | Nullable | Description |
|-----------------|--------------|----------|-------------|
| id_estoque      | SERIAL (INT) | NOT NULL | Surrogate primary key, auto-incremented by the database. |
| id_produto      | INTEGER      | NOT NULL | Foreign key to `dim_produto.id_produto`. Identifies the product being tracked. |
| id_loja         | INTEGER      | NOT NULL | Foreign key to `dim_loja.id_loja`. Identifies the store holding or expecting the stock. |
| data_posicao    | DATE         | NOT NULL | The calendar date for which this snapshot was taken (`YYYY-MM-DD`). Represents end-of-day position. Part of the composite unique key `(id_produto, id_loja, data_posicao)`. |
| qtd_disponivel  | INTEGER      | NOT NULL | Units physically on hand and available for sale at the store as of `data_posicao`. Must be >= 0 (CHECK constraint). A value of `0` indicates a stockout condition. |
| qtd_transito    | INTEGER      | NOT NULL | Units ordered from the distribution centre that are in transit to the store but not yet received as of `data_posicao`. Must be >= 0 (CHECK constraint). Defaults to `0`. Total expected stock can be estimated as `qtd_disponivel + qtd_transito`. |
