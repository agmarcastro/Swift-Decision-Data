# BigQuery Optimization Knowledge Base

> **Purpose**: BigQuery partitioning, clustering, cost management, and materialized views
> **MCP Validated**: 2026-04-24

## Quick Navigation

### Concepts (< 150 lines each)

| File | Purpose |
|------|---------|
| [concepts/partitioning.md](concepts/partitioning.md) | Partition strategies, types, expiration, require_partition_filter |
| [concepts/clustering.md](concepts/clustering.md) | Cluster key selection, cardinality rules, interaction with partitions |
| [concepts/slots-and-cost.md](concepts/slots-and-cost.md) | On-demand vs capacity, cost estimation, dry_run controls |
| [concepts/materialized-views.md](concepts/materialized-views.md) | When to use, incremental refresh, staleness, supported aggregates |

### Patterns (< 200 lines each)

| File | Purpose |
|------|---------|
| [patterns/partitioned-clustered-table.md](patterns/partitioned-clustered-table.md) | Full DDL for partitioned + clustered fact table |
| [patterns/incremental-load-merge.md](patterns/incremental-load-merge.md) | MERGE pattern for DW incremental loads with deduplication |
| [patterns/cost-optimized-query.md](patterns/cost-optimized-query.md) | Query optimization: column selection, partition filters, approximations |

---

## Quick Reference

- [quick-reference.md](quick-reference.md) - Partitioning decision table, cluster rules, DDL options

---

## Key Concepts

| Concept | Description |
|---------|-------------|
| **Partition pruning** | BigQuery skips entire partitions when WHERE clause filters on partition column |
| **Cluster sorting** | Data within a partition is physically sorted by cluster columns for block pruning |
| **Slot** | Unit of BigQuery compute (CPU + memory); on-demand auto-scales, capacity is reserved |
| **Bytes processed** | Primary cost driver; estimated before execution via dry run |
| **Materialized view** | Pre-computed result that auto-refreshes incrementally; reduces query cost |

---

## Learning Path

| Level | Files |
|-------|-------|
| **Beginner** | concepts/partitioning.md, concepts/clustering.md |
| **Intermediate** | concepts/slots-and-cost.md, patterns/partitioned-clustered-table.md |
| **Advanced** | concepts/materialized-views.md, patterns/incremental-load-merge.md, patterns/cost-optimized-query.md |

---

## Agent Usage

| Agent | Primary Files | Use Case |
|-------|---------------|----------|
| dw-specialist | concepts/partitioning.md, patterns/partitioned-clustered-table.md | Design physical table layout |
| dw-specialist | concepts/slots-and-cost.md, patterns/cost-optimized-query.md | Optimize query cost |
| dw-specialist | patterns/incremental-load-merge.md | Build idempotent DW loads |
