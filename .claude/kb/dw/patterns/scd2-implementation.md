# SCD2 Implementation

> **Purpose**: MERGE-based SCD2 upsert in BigQuery — detect changes, insert new versions, close old
> **MCP Validated**: 2026-04-24

## When to Use

- Loading a slowly changing dimension with full history requirements
- Re-running the pipeline idempotently (MERGE is safe to re-execute)
- Detecting attribute changes via row hash to avoid false positives

## Implementation

```sql
-- ============================================================
-- SCD Type 2 MERGE for dim_customer in BigQuery
-- Source: staging.stg_customers (raw CRM extract, deduped)
-- Target: dw.dim_customer (SCD2 with valid_from/valid_to/is_current)
-- ============================================================

-- Step 1: Identify changed records using row hash
-- ─────────────────────────────────────────────────────────────
WITH source_with_hash AS (
    SELECT
        customer_natural_key,
        full_name,
        email,
        city,
        state_code,
        country_code,
        loyalty_tier,
        -- Hash only the attributes we want to track for changes
        TO_HEX(MD5(CONCAT(
            COALESCE(full_name,    ''),
            COALESCE(email,        ''),
            COALESCE(city,         ''),
            COALESCE(loyalty_tier, '')
        ))) AS row_hash
    FROM `project.staging.stg_customers`
),

-- Step 2: Join source to current dimension rows to detect changes
changed_records AS (
    SELECT
        s.customer_natural_key,
        s.full_name,
        s.email,
        s.city,
        s.state_code,
        s.country_code,
        s.loyalty_tier,
        s.row_hash,
        d.customer_key AS existing_key,
        CASE
            WHEN d.customer_key IS NULL     THEN 'new'
            WHEN d.row_hash != s.row_hash   THEN 'changed'
            ELSE                                 'unchanged'
        END AS change_type
    FROM source_with_hash s
    LEFT JOIN `project.dw.dim_customer` d
        ON  s.customer_natural_key = d.customer_natural_key
        AND d.is_current = TRUE
),

-- Step 3: Build rows to expire (close old version)
rows_to_expire AS (
    SELECT existing_key
    FROM changed_records
    WHERE change_type = 'changed'
),

-- Step 4: Build new rows to insert (new + changed entities)
rows_to_insert AS (
    SELECT
        -- Surrogate key: farm_fingerprint gives a stable INT64 from natural key + timestamp
        FARM_FINGERPRINT(CONCAT(customer_natural_key, CAST(CURRENT_TIMESTAMP() AS STRING)))
            AS customer_key,
        customer_natural_key,
        full_name,
        email,
        city,
        state_code,
        country_code,
        loyalty_tier,
        CURRENT_DATE()  AS valid_from,
        NULL            AS valid_to,
        TRUE            AS is_current,
        row_hash
    FROM changed_records
    WHERE change_type IN ('new', 'changed')
)

-- Step 5: Execute the MERGE
-- ─────────────────────────────────────────────────────────────
MERGE `project.dw.dim_customer` AS target
USING (
    -- Union: expired rows + new rows
    SELECT
        r.existing_key          AS customer_key,
        NULL                    AS customer_natural_key,
        NULL AS full_name, NULL AS email, NULL AS city,
        NULL AS state_code, NULL AS country_code, NULL AS loyalty_tier,
        DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY) AS valid_to,
        FALSE   AS is_current,
        'expire' AS action
    FROM rows_to_expire r

    UNION ALL

    SELECT
        i.customer_key,
        i.customer_natural_key,
        i.full_name, i.email, i.city,
        i.state_code, i.country_code, i.loyalty_tier,
        NULL    AS valid_to,
        TRUE    AS is_current,
        'insert' AS action
    FROM rows_to_insert i
) AS source
ON target.customer_key = source.customer_key

-- Close the old version
WHEN MATCHED AND source.action = 'expire' THEN
    UPDATE SET
        target.valid_to    = source.valid_to,
        target.is_current  = FALSE

-- Insert new / changed version
WHEN NOT MATCHED AND source.action = 'insert' THEN
    INSERT (
        customer_key, customer_natural_key,
        full_name, email, city, state_code, country_code, loyalty_tier,
        valid_from, valid_to, is_current, row_hash
    )
    VALUES (
        source.customer_key, source.customer_natural_key,
        source.full_name, source.email, source.city,
        source.state_code, source.country_code, source.loyalty_tier,
        CURRENT_DATE(), NULL, TRUE,
        (SELECT row_hash FROM rows_to_insert WHERE customer_key = source.customer_key)
    );
```

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| Hash function | `MD5` | Fast, sufficient for change detection (not cryptographic) |
| Surrogate key | `FARM_FINGERPRINT` | Deterministic INT64 from natural key + timestamp |
| valid_to on expire | `CURRENT_DATE() - 1 day` | Prevents gap; last valid day is yesterday |
| Tracked attributes | full_name, email, city, loyalty_tier | Exclude audit cols from hash |

## Example Usage

```sql
-- Verify no duplicate current rows after SCD2 load
SELECT customer_natural_key, COUNT(*) AS current_versions
FROM `project.dw.dim_customer`
WHERE is_current = TRUE
GROUP BY 1
HAVING COUNT(*) > 1;
-- Should return zero rows

-- Verify version chain integrity
SELECT
    customer_natural_key,
    valid_from,
    valid_to,
    is_current,
    loyalty_tier
FROM `project.dw.dim_customer`
WHERE customer_natural_key = 'CUST-001'
ORDER BY valid_from;
```

## See Also

- [concepts/scd-types.md](../concepts/scd-types.md)
- [patterns/star-schema-design.md](star-schema-design.md)
- [concepts/dimension-tables.md](../concepts/dimension-tables.md)
