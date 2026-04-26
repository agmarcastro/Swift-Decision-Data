# One Big Table (OBT)

> **Purpose**: Pre-join all dimensions into a single wide mart table for zero-join BI consumption
> **MCP Validated**: 2026-04-24

## When to Use

- Building a mart layer for BI tools (Looker, Metabase, Tableau) that struggle with complex joins
- Pre-computing expensive joins that analysts repeat constantly
- Flattening a star schema for embedded analytics or API serving
- Consolidating nested/repeated attributes using BigQuery STRUCTs

## Implementation

```sql
-- ============================================================
-- One Big Table: mart_orders
-- Source: fct_order_lines + all dimension tables
-- Consumers: BI dashboards, self-service analytics
-- Refresh: scheduled REPLACE TABLE (full refresh) or incremental
-- ============================================================

CREATE OR REPLACE TABLE `project.mart.obt_orders`
PARTITION BY order_date
CLUSTER BY customer_loyalty_tier, product_category_name
OPTIONS (
    description = 'Orders OBT: pre-joined mart for BI consumption. grain: one row per order line.',
    partition_expiration_days = 730
)
AS
SELECT
    -- ── Order identifiers ──────────────────────────────────
    ol.order_id,
    ol.order_line_number,
    ol.order_date_key,

    -- ── Date attributes (denormalized) ────────────────────
    d.full_date             AS order_date,
    d.calendar_year         AS order_year,
    d.calendar_quarter      AS order_quarter,
    d.month_number          AS order_month_number,
    d.month_name            AS order_month_name,
    d.week_of_year          AS order_week,
    d.day_name              AS order_day_name,
    d.is_weekend            AS is_weekend_order,

    -- ── Customer attributes (current snapshot) ────────────
    c.customer_natural_key,
    c.full_name             AS customer_name,
    c.city                  AS customer_city,
    c.state_code            AS customer_state,
    c.country_code          AS customer_country,
    c.loyalty_tier          AS customer_loyalty_tier,

    -- ── Product attributes ────────────────────────────────
    p.product_natural_key,
    p.product_name,
    p.category_name         AS product_category_name,
    p.subcategory_name      AS product_subcategory_name,
    p.brand_name,

    -- ── Store attributes ─────────────────────────────────
    s.store_code,
    s.store_name,
    s.city                  AS store_city,
    s.region                AS store_region,

    -- ── Measures ─────────────────────────────────────────
    ol.quantity_ordered,
    ol.unit_price,
    ol.extended_amount,
    ol.discount_amount,
    ol.tax_amount,
    ol.net_amount,

    -- ── Nested STRUCT: customer address as atomic unit ───
    STRUCT(
        c.city         AS city,
        c.state_code   AS state,
        c.country_code AS country
    ) AS customer_address,

    -- ── Nested STRUCT: product taxonomy ──────────────────
    STRUCT(
        p.category_name    AS category,
        p.subcategory_name AS subcategory,
        p.brand_name       AS brand
    ) AS product_taxonomy,

    -- ── Audit ─────────────────────────────────────────────
    ol._loaded_at

FROM `project.dw.fct_order_lines` ol

JOIN `project.dw.dim_date`     d  ON ol.order_date_key = d.date_key

-- Use is_current = TRUE to get snapshot-at-load-time customer state
JOIN `project.dw.dim_customer` c  ON ol.customer_key   = c.customer_key
                                  AND c.is_current = TRUE

JOIN `project.dw.dim_product`  p  ON ol.product_key    = p.product_key

JOIN `project.dw.dim_store`    s  ON ol.store_key      = s.store_key;
```

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| Refresh strategy | Full replace | Safe, idempotent; switch to incremental for large tables |
| Partition column | `order_date` | Allows BI tools to push date filters |
| Cluster columns | `customer_loyalty_tier, product_category_name` | Most common filter axes |
| STRUCT usage | customer_address, product_taxonomy | Groups related attrs; accessible as `.city` |

## Example Usage

```sql
-- BI tool query: zero joins required
SELECT
    customer_loyalty_tier,
    product_category_name,
    order_year,
    order_quarter,
    SUM(net_amount)             AS net_revenue,
    COUNT(DISTINCT order_id)    AS order_count,
    AVG(net_amount)             AS avg_order_value
FROM `project.mart.obt_orders`
WHERE order_date BETWEEN '2024-01-01' AND '2024-12-31'
GROUP BY 1, 2, 3, 4
ORDER BY net_revenue DESC;

-- Access nested STRUCT fields
SELECT
    order_id,
    customer_address.city,
    customer_address.country,
    product_taxonomy.category
FROM `project.mart.obt_orders`
WHERE order_date = '2024-06-15';
```

## See Also

- [concepts/star-vs-snowflake.md](../concepts/star-vs-snowflake.md)
- [patterns/star-schema-design.md](star-schema-design.md)
- [concepts/dimensional-modeling.md](../concepts/dimensional-modeling.md)
