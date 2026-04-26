# Incremental Load MERGE Pattern

> **Purpose**: BigQuery MERGE for incremental DW loads — upsert by surrogate key, dedup CTE, idempotency
> **MCP Validated**: 2026-04-24

## When to Use

- Loading new and updated rows from a staging table into a fact or dimension table
- Ensuring the load is idempotent (safe to re-run without creating duplicates)
- Deduplicating source data before merging to prevent duplicate keys in the target

## Implementation

```sql
-- ============================================================
-- Incremental MERGE: staging → dw.fct_order_lines
-- Idempotent: re-running produces the same result
-- Deduplication: source CTE handles duplicate events from upstream
-- ============================================================

-- Step 1: Deduplicated source
-- The staging table may contain duplicate order_line_key due to
-- event replays or ELT retries. Deduplicate before MERGE.
WITH deduped_source AS (
    SELECT *
    FROM (
        SELECT
            -- Surrogate key: deterministic hash of natural key
            TO_HEX(MD5(CONCAT(
                CAST(order_id      AS STRING), '|',
                CAST(line_number   AS STRING)
            )))                                     AS order_line_key,

            order_id,
            line_number                             AS order_line_number,
            CAST(order_date      AS DATE)           AS order_date,
            CAST(customer_id     AS INT64)          AS customer_id,
            CAST(product_id      AS INT64)          AS product_id,
            CAST(store_id        AS INT64)          AS store_id,
            CAST(quantity        AS INT64)          AS quantity_ordered,
            CAST(unit_price      AS NUMERIC)        AS unit_price,
            CAST(line_total      AS NUMERIC)        AS extended_amount,
            CAST(discount_amount AS NUMERIC)        AS discount_amount,
            CAST(tax_amount      AS NUMERIC)        AS tax_amount,
            CAST(net_amount      AS NUMERIC)        AS net_amount,
            order_status,
            'shopify'                               AS _source_system,
            CURRENT_TIMESTAMP()                     AS _loaded_at,

            -- Row number for deduplication: keep latest event per key
            ROW_NUMBER() OVER (
                PARTITION BY order_id, line_number
                ORDER BY updated_at DESC
            ) AS _row_num

        FROM `project.staging.stg_shopify__order_lines`
        -- Incremental window: only process recent data
        -- Adjust look-back window to match your SLA for late-arriving events
        WHERE order_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
    )
    WHERE _row_num = 1
)

-- Step 2: MERGE into target table
MERGE `project.dw.fct_order_lines` AS target
USING deduped_source AS source
    ON target.order_line_key = source.order_line_key

-- Update existing rows that have changed (e.g., order_status correction)
WHEN MATCHED AND (
    target.order_status    != source.order_status    OR
    target.net_amount      != source.net_amount      OR
    target.quantity_ordered != source.quantity_ordered
) THEN
    UPDATE SET
        target.quantity_ordered = source.quantity_ordered,
        target.unit_price       = source.unit_price,
        target.extended_amount  = source.extended_amount,
        target.discount_amount  = source.discount_amount,
        target.tax_amount       = source.tax_amount,
        target.net_amount       = source.net_amount,
        target.order_status     = source.order_status,
        target._loaded_at       = source._loaded_at

-- Insert new rows not yet in target
WHEN NOT MATCHED THEN
    INSERT (
        order_line_key, order_date,
        customer_id, product_id, store_id,
        order_id, order_line_number,
        quantity_ordered, unit_price, extended_amount,
        discount_amount, tax_amount, net_amount,
        order_status, _source_system, _loaded_at
    )
    VALUES (
        source.order_line_key, source.order_date,
        source.customer_id, source.product_id, source.store_id,
        source.order_id, source.order_line_number,
        source.quantity_ordered, source.unit_price, source.extended_amount,
        source.discount_amount, source.tax_amount, source.net_amount,
        source.order_status, source._source_system, source._loaded_at
    );
```

## Idempotency Design

```sql
-- Idempotency check: verify re-running produces the same row count
-- Run once → count rows
-- Run again → count should not change (rows updated in place, not duplicated)

SELECT COUNT(*) AS total_rows, COUNT(DISTINCT order_line_key) AS unique_keys
FROM `project.dw.fct_order_lines`
WHERE order_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY);
-- total_rows should equal unique_keys after any number of MERGE re-runs
```

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| Merge key | `order_line_key` (MD5 hash) | Must be unique per grain |
| Look-back window | 7 days | Covers late-arriving events and corrections |
| Dedup strategy | `ROW_NUMBER() ... ORDER BY updated_at DESC` | Keep latest version |
| WHEN MATCHED condition | Changed columns only | Avoids unnecessary write amplification |

## Example Usage

```sql
-- Post-merge validation: check for duplicates
SELECT order_line_key, COUNT(*) AS cnt
FROM `project.dw.fct_order_lines`
GROUP BY 1
HAVING cnt > 1;
-- Should return zero rows if MERGE worked correctly

-- Check recent loads
SELECT
    order_date,
    COUNT(*) AS rows_loaded,
    MAX(_loaded_at) AS last_load_time
FROM `project.dw.fct_order_lines`
WHERE order_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
GROUP BY 1
ORDER BY 1 DESC;
```

## See Also

- [patterns/partitioned-clustered-table.md](partitioned-clustered-table.md)
- [concepts/partitioning.md](../concepts/partitioning.md)
- [concepts/slots-and-cost.md](../concepts/slots-and-cost.md)
