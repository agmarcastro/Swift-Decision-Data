# SCD Types

> **Purpose**: Slowly Changing Dimension strategies — mechanics and selection rules
> **Confidence**: 0.95
> **MCP Validated**: 2026-04-24

## Overview

Slowly Changing Dimensions (SCDs) handle the problem of dimension attributes that
change over time. The strategy chosen controls whether historical values are preserved
and how queries must be written to retrieve current vs point-in-time attribute values.
Type 2 is the most common production choice when history matters.

## SCD Type 1 — Overwrite

History is lost. The current value replaces the old value in-place. Use when only
the current state matters and historical accuracy is not required.

```sql
-- SCD Type 1: simple UPDATE, history lost
UPDATE dim_customer
SET
    email         = 'newemail@example.com',
    phone_number  = '555-9999',
    _updated_at   = CURRENT_TIMESTAMP()
WHERE customer_natural_key = 'CUST-001';
-- Prior email is gone; historical reports will show new email retroactively
```

## SCD Type 2 — Versioned Rows

Full history preserved as additional rows. Each change creates a new row with a new
surrogate key. Required columns: `valid_from`, `valid_to`, `is_current`, `row_hash`.

```sql
-- SCD Type 2 structure
CREATE TABLE dim_customer (
    customer_key         INT64    NOT NULL,  -- surrogate PK (new per version)
    customer_natural_key STRING   NOT NULL,  -- source system ID (stable)

    -- Tracked attributes
    full_name            STRING,
    email                STRING,
    city                 STRING,
    loyalty_tier         STRING,

    -- Version control columns
    valid_from           DATE     NOT NULL,
    valid_to             DATE,               -- NULL means current record
    is_current           BOOL     NOT NULL,
    row_hash             STRING   NOT NULL   -- MD5 of tracked attributes
);

-- Query: get current state
SELECT * FROM dim_customer WHERE is_current = TRUE;

-- Query: point-in-time (what was customer's tier on 2023-06-01?)
SELECT *
FROM dim_customer
WHERE customer_natural_key = 'CUST-001'
  AND valid_from <= '2023-06-01'
  AND (valid_to > '2023-06-01' OR valid_to IS NULL);
```

## SCD Type 3 — Prior Value Columns

Only the immediately prior value is preserved as an additional column. Simpler than
Type 2 but limited: you can only look back one change.

```sql
-- SCD Type 3: current + one prior column
CREATE TABLE dim_customer_type3 (
    customer_key             INT64,
    customer_natural_key     STRING,
    current_loyalty_tier     STRING,         -- current value
    prior_loyalty_tier       STRING,         -- one prior value (NULL if no change)
    tier_changed_at          TIMESTAMP
);

-- Limitation: a second tier change overwrites the prior_loyalty_tier,
-- permanently losing the oldest historical value.
```

## SCD Type 4 — Mini-Dimension

Rapidly changing attributes are split into a separate "mini-dimension" to avoid
exploding the main dimension with high-churn SCD2 rows.

```sql
-- High-churn attributes (purchase_frequency, credit_score_band) go in mini-dim
CREATE TABLE dim_customer_behavior (
    customer_behavior_key   INT64,
    purchase_frequency_band STRING,   -- 'low','medium','high','vip'
    credit_score_band       STRING,
    preferred_channel       STRING,
    valid_from              DATE,
    valid_to                DATE,
    is_current              BOOL
);

-- Stable attributes stay in main dim (Type 1)
CREATE TABLE dim_customer (
    customer_key             INT64,
    customer_natural_key     STRING,
    full_name                STRING,
    date_of_birth            DATE,
    current_behavior_key     INT64    -- FK to mini-dimension current row
);
```

## Quick Reference

| Type | History | Columns Added | Row Count Impact |
|------|---------|---------------|-----------------|
| 1 | Lost | None | Stable |
| 2 | Full | valid_from, valid_to, is_current, row_hash | Grows per change |
| 3 | 1 prior | prior_{col} per tracked attr | Stable |
| 4 | Full (mini-dim) | Separate table + FK | Two tables grow |
| 6 | Full + current | All of 2+3 | Grows per change |

## Common Mistakes

### Wrong

```sql
-- Forgetting to close the previous SCD2 row before inserting new one
INSERT INTO dim_customer (customer_key, ..., valid_from, valid_to, is_current)
VALUES (NEW_KEY, ..., CURRENT_DATE(), NULL, TRUE);
-- Old row still has is_current = TRUE → two current rows for same entity!
```

### Correct

```sql
-- Always expire old row AND insert new row in the same transaction (or MERGE)
UPDATE dim_customer
SET valid_to = DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY), is_current = FALSE
WHERE customer_natural_key = 'CUST-001' AND is_current = TRUE;

INSERT INTO dim_customer (..., valid_from, valid_to, is_current)
VALUES (..., CURRENT_DATE(), NULL, TRUE);
```

## Related

- [dimension-tables.md](dimension-tables.md)
- [patterns/scd2-implementation.md](../patterns/scd2-implementation.md)
