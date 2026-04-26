# Incremental Model Pattern

> **Purpose**: Incremental fct_ model with is_incremental() macro, BigQuery MERGE, late-arriving data
> **MCP Validated**: 2026-04-24

## When to Use

- Building fact tables on large event streams (orders, clicks, payments)
- Source tables grow daily and full rebuilds exceed acceptable run time
- Late-arriving events need to be captured within a lookback window

## Implementation

```sql
-- models/marts/core/fct_order_lines.sql
-- Layer: marts/core
-- Materialization: incremental (merge strategy on BigQuery)
-- Grain: one row per order line item
-- Late-arriving: 3-day lookback window handles delayed event delivery

{{
    config(
        materialized         = 'incremental',
        unique_key           = 'order_line_key',
        incremental_strategy = 'merge',
        on_schema_change     = 'append_new_columns',
        partition_by         = {
            'field': 'ordered_at',
            'data_type': 'timestamp',
            'granularity': 'day'
        },
        cluster_by           = ['order_date_key', 'customer_key'],
        tags                 = ['marts', 'core', 'daily']
    )
}}

WITH staged_orders AS (
    SELECT * FROM {{ ref('stg_shopify__order_lines') }}

    {% if is_incremental() %}
    -- Late-arriving data window: process rows from the last 3 days
    -- This handles delayed events and allows re-processing corrections
    WHERE ordered_at >= TIMESTAMP_SUB(
        (SELECT MAX(ordered_at) FROM {{ this }}),
        INTERVAL 3 DAY
    )
    {% endif %}
),

-- Surrogate key: deterministic hash of natural key columns
with_surrogate_key AS (
    SELECT
        {{ dbt_utils.generate_surrogate_key(['order_id', 'line_number']) }}
            AS order_line_key,

        order_id,
        line_number                 AS order_line_number,
        customer_id,
        product_sku,
        ordered_at,

        -- Derive date key for dim_date join
        CAST(FORMAT_TIMESTAMP('%Y%m%d', ordered_at) AS INT64) AS order_date_key,

        -- Measures
        CAST(quantity     AS INT64)   AS quantity_ordered,
        CAST(unit_price   AS NUMERIC) AS unit_price,
        CAST(line_total   AS NUMERIC) AS extended_amount,
        CAST(discount_amt AS NUMERIC) AS discount_amount,
        CAST(tax_amount   AS NUMERIC) AS tax_amount,
        CAST(net_amount   AS NUMERIC) AS net_amount,

        -- Status
        order_status,
        fulfillment_status,

        -- Audit
        CURRENT_TIMESTAMP()           AS _dbt_loaded_at

    FROM staged_orders
)

SELECT * FROM with_surrogate_key
```

```yaml
# models/marts/core/_core__models.yml (incremental model section)
  - name: fct_order_lines
    description: "Order lines fact table. Incremental load. grain: one row per order line item."
    config:
      materialized: incremental
    columns:
      - name: order_line_key
        tests: [unique, not_null]
      - name: ordered_at
        tests: [not_null]
      - name: net_amount
        tests:
          - not_null
          - dbt_utils.accepted_range:
              min_value: 0
```

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `incremental_strategy` | `merge` | BigQuery MERGE; upserts by unique_key |
| `unique_key` | `order_line_key` | Merge key; must be truly unique per grain |
| Lookback window | 3 days | Capture late-arriving events from last 3 days |
| `on_schema_change` | `append_new_columns` | Safe for adding new columns |
| `partition_by` | `ordered_at` (day) | Partition pruning on MERGE reduces cost |

## Example Usage

```bash
# Full refresh (rebuild entire table — use rarely)
dbt run --select fct_order_lines --full-refresh

# Normal incremental run
dbt run --select fct_order_lines

# Run with upstream staging models first
dbt run --select +fct_order_lines

# Test after run
dbt test --select fct_order_lines
```

## See Also

- [concepts/materializations.md](../concepts/materializations.md)
- [patterns/staging-model.md](staging-model.md)
- [patterns/model-yaml-tests.md](model-yaml-tests.md)
