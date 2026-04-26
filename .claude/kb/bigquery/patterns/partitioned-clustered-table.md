# Partitioned and Clustered Table

> **Purpose**: Full DDL for a partitioned + clustered fact table with OPTIONS and partition pruning query
> **MCP Validated**: 2026-04-24

## When to Use

- Creating any fact table expected to exceed 1 GB in BigQuery
- Designing a table that will be filtered by date and 2-4 additional dimension keys
- Enforcing partition filter requirements to prevent accidental full-table scans

## Implementation

```sql
-- ============================================================
-- Production fact table: partitioned by date, clustered by top filter columns
-- Table: project.dw.fct_order_lines
-- Partition: order_date (DAY granularity)
-- Cluster: customer_id, product_id, store_id (top 3 filter/join columns)
-- ============================================================

CREATE TABLE IF NOT EXISTS `project.dw.fct_order_lines` (
    -- Surrogate primary key
    order_line_key      INT64       NOT NULL    OPTIONS(description="Surrogate PK"),

    -- Partition column (must be DATE or TIMESTAMP for date partitioning)
    order_date          DATE        NOT NULL    OPTIONS(description="Order date. Partition column."),

    -- Foreign keys (also used as cluster columns)
    customer_id         INT64       NOT NULL    OPTIONS(description="FK to dim_customer"),
    product_id          INT64       NOT NULL    OPTIONS(description="FK to dim_product"),
    store_id            INT64       NOT NULL    OPTIONS(description="FK to dim_store"),

    -- Degenerate dimensions
    order_id            STRING      NOT NULL,
    order_line_number   INT64       NOT NULL,

    -- Additive measures
    quantity_ordered    INT64,
    unit_price          NUMERIC,
    extended_amount     NUMERIC     OPTIONS(description="unit_price * quantity_ordered"),
    discount_amount     NUMERIC,
    tax_amount          NUMERIC,
    net_amount          NUMERIC     OPTIONS(description="extended - discount + tax"),

    -- Status
    order_status        STRING,

    -- Audit
    _source_system      STRING,
    _loaded_at          TIMESTAMP   NOT NULL
)

-- Partitioning: coarse filter eliminates entire day partitions
PARTITION BY order_date

-- Clustering: fine filter eliminates data blocks within a partition
-- Rule: most selective WHERE/JOIN column first
CLUSTER BY customer_id, product_id, store_id

OPTIONS (
    description                = 'Order lines fact table. grain: one row per order line item.',
    partition_expiration_days  = 730,    -- keep 2 years of data; auto-expire older partitions
    require_partition_filter   = true,   -- queries MUST include WHERE order_date = ...
    labels                     = [('domain', 'commerce'), ('team', 'data-engineering')]
);
```

## Adding Column-Level Descriptions After Creation

```sql
-- Add or update column descriptions via ALTER TABLE
ALTER TABLE `project.dw.fct_order_lines`
    ALTER COLUMN order_status SET OPTIONS (description = 'placed|processing|shipped|delivered|cancelled');

ALTER TABLE `project.dw.fct_order_lines`
    ALTER COLUMN net_amount SET OPTIONS (description = 'Final net revenue. Additive across all dimensions.');
```

## Verification Query

```sql
-- Confirm partition + cluster configuration
SELECT
    table_name,
    partition_expiration_ms / 86400000 AS partition_expiration_days,
    require_partition_filter,
    clustering_fields
FROM `project.dw.INFORMATION_SCHEMA.TABLES`
WHERE table_name = 'fct_order_lines';
```

## Configuration

| Setting | Value | Description |
|---------|-------|-------------|
| Partition type | `DATE` | DAY granularity (default) |
| Partition expiration | 730 days | Auto-delete partitions >2 years old |
| require_partition_filter | `true` | Force partition predicate in all queries |
| Cluster columns | customer_id, product_id, store_id | Top 3 filter/join keys |
| Max cluster columns | 4 | BigQuery hard limit |

## Example Usage

```sql
-- Partition pruning: scans only Jan 2024 partitions
-- Cluster pruning: scans only blocks for customer 12345
SELECT
    order_id,
    product_id,
    net_amount
FROM `project.dw.fct_order_lines`
WHERE order_date BETWEEN '2024-01-01' AND '2024-01-31'  -- partition filter (required)
  AND customer_id = 12345                                -- cluster filter
  AND product_id IN (101, 202);                         -- cluster filter

-- Verify partition pruning via EXPLAIN or dry run
-- bq query --dry_run 'SELECT ... WHERE order_date = "2024-01-15"'
```

## See Also

- [concepts/partitioning.md](../concepts/partitioning.md)
- [concepts/clustering.md](../concepts/clustering.md)
- [patterns/incremental-load-merge.md](incremental-load-merge.md)
