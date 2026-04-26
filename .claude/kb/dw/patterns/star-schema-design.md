# Star Schema Design

> **Purpose**: Complete DDL for an orders star schema with surrogate keys and FK relationships
> **MCP Validated**: 2026-04-24

## When to Use

- Designing the physical schema for a new fact table in BigQuery
- Establishing naming conventions for a DW project
- Defining the grain, dimensions, and measures before writing ETL

## Implementation

```sql
-- ============================================================
-- STAR SCHEMA: Orders Domain
-- Grain: one row per order line item
-- Dimensions: date, customer, product, store
-- ============================================================

-- ── Dimension: Date ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS `project.dw.dim_date` (
    date_key          INT64   NOT NULL,   -- YYYYMMDD integer surrogate key
    full_date         DATE    NOT NULL,
    calendar_year     INT64   NOT NULL,
    calendar_quarter  INT64   NOT NULL,   -- 1–4
    month_number      INT64   NOT NULL,   -- 1–12
    month_name        STRING  NOT NULL,
    week_of_year      INT64   NOT NULL,
    day_of_week       INT64   NOT NULL,   -- 1=Mon … 7=Sun
    day_name          STRING  NOT NULL,
    is_weekend        BOOL    NOT NULL,
    is_holiday        BOOL    NOT NULL    -- populated via holiday calendar
)
PARTITION BY full_date
OPTIONS (description = 'Calendar dimension. grain: one row per calendar day.');

-- ── Dimension: Customer (SCD2) ───────────────────────────────
CREATE TABLE IF NOT EXISTS `project.dw.dim_customer` (
    customer_key         INT64    NOT NULL,   -- surrogate PK
    customer_natural_key STRING   NOT NULL,   -- source CRM ID
    full_name            STRING,
    email                STRING,
    city                 STRING,
    state_code           STRING,
    country_code         STRING,
    loyalty_tier         STRING,              -- 'bronze','silver','gold','platinum'
    valid_from           DATE     NOT NULL,
    valid_to             DATE,                -- NULL = current record
    is_current           BOOL     NOT NULL,
    row_hash             STRING   NOT NULL    -- MD5(full_name||email||city||loyalty_tier)
)
OPTIONS (description = 'Customer dimension with SCD Type 2 history.');

-- ── Dimension: Product ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS `project.dw.dim_product` (
    product_key          INT64   NOT NULL,   -- surrogate PK
    product_natural_key  STRING  NOT NULL,   -- source SKU
    product_name         STRING,
    category_name        STRING,
    subcategory_name     STRING,
    brand_name           STRING,
    unit_cost            NUMERIC,
    is_active            BOOL    NOT NULL
)
OPTIONS (description = 'Product dimension. grain: one row per active product SKU.');

-- ── Dimension: Store ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS `project.dw.dim_store` (
    store_key       INT64   NOT NULL,
    store_code      STRING  NOT NULL,
    store_name      STRING,
    city            STRING,
    state_code      STRING,
    country_code    STRING,
    region          STRING,
    opened_date     DATE
)
OPTIONS (description = 'Store / fulfillment center dimension.');

-- ── Fact: Order Lines ────────────────────────────────────────
-- grain: one row per order line item
CREATE TABLE IF NOT EXISTS `project.dw.fct_order_lines` (
    -- Surrogate key
    order_line_key      INT64    NOT NULL,

    -- Foreign keys to dimensions
    order_date_key      INT64    NOT NULL,   -- FK → dim_date.date_key
    customer_key        INT64    NOT NULL,   -- FK → dim_customer.customer_key
    product_key         INT64    NOT NULL,   -- FK → dim_product.product_key
    store_key           INT64    NOT NULL,   -- FK → dim_store.store_key

    -- Degenerate dimensions
    order_id            STRING   NOT NULL,
    order_line_number   INT64    NOT NULL,

    -- Additive measures
    quantity_ordered    INT64,
    unit_price          NUMERIC,
    extended_amount     NUMERIC,
    discount_amount     NUMERIC,
    tax_amount          NUMERIC,
    net_amount          NUMERIC,

    -- Audit
    _source_system      STRING,
    _loaded_at          TIMESTAMP
)
PARTITION BY DATE(_loaded_at)
CLUSTER BY order_date_key, customer_key, product_key
OPTIONS (description = 'Order lines fact table. grain: one row per order line item.');
```

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| Partition column | `_loaded_at` | Enables time-window pruning on loads |
| Cluster columns | `order_date_key, customer_key, product_key` | Top 3 filter/join columns |
| Surrogate key type | `INT64` | 8-byte integer; fastest JOIN in BigQuery |
| SCD2 dim | `dim_customer` | Tracks loyalty_tier and address changes |

## Example Usage

```sql
-- Revenue by loyalty tier and product category (last 90 days)
SELECT
    c.loyalty_tier,
    p.category_name,
    SUM(ol.net_amount)      AS net_revenue,
    COUNT(DISTINCT ol.order_id) AS order_count
FROM `project.dw.fct_order_lines` ol
JOIN `project.dw.dim_customer` c ON ol.customer_key  = c.customer_key
                                 AND c.is_current = TRUE
JOIN `project.dw.dim_product`  p ON ol.product_key   = p.product_key
JOIN `project.dw.dim_date`     d ON ol.order_date_key = d.date_key
WHERE d.full_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
GROUP BY 1, 2
ORDER BY net_revenue DESC;
```

## See Also

- [concepts/dimensional-modeling.md](../concepts/dimensional-modeling.md)
- [concepts/scd-types.md](../concepts/scd-types.md)
- [patterns/scd2-implementation.md](scd2-implementation.md)
