# Local Pool and Lookup

> **Purpose**: Cross-generator referential integrity via history pools and the `lookup` function
> **Confidence**: 0.95
> **MCP Validated**: 2026-04-24

## Overview

When ShadowTraffic runs a generator it retains a sliding window of recently produced events in
an in-memory history. The `lookup` function queries that history, returning a random (or
first/last) event from any named topic or table. This is the primary mechanism for creating
foreign-key style relationships across topics. `maxHistoryEvents` bounds the pool size;
`discard.retainHistory` lets dropped events still populate the pool for consumers.

## The Pattern

```json
{
  "generators": [
    {
      "topic": "customers",
      "key": { "_gen": "uuid" },
      "value": {
        "customer_id": { "_gen": "uuid" },
        "name":        { "_gen": "string", "expr": "#{Name.full_name}" },
        "email":       { "_gen": "string", "expr": "#{Internet.email_address}" }
      },
      "localConfigs": {
        "throttleMs": 1000,
        "maxHistoryEvents": 200
      }
    },
    {
      "topic": "orders",
      "key": { "_gen": "uuid" },
      "value": {
        "order_id":    { "_gen": "uuid" },
        "customer_id": {
          "_gen": "lookup",
          "topic": "customers",
          "path": ["value", "customer_id"]
        },
        "amount": { "_gen": "uniformDistribution", "bounds": [5.0, 999.99] },
        "placed_at": { "_gen": "now" }
      },
      "localConfigs": { "throttleMs": 200 }
    }
  ]
}
```

## Quick Reference

| Parameter | Required | Description |
|-----------|----------|-------------|
| `topic` | yes* | Source topic name to look up from |
| `table` | yes* | Source table name (Postgres variant) |
| `path` | no | Array drill-path into the event, e.g. `["value", "id"]` |
| `strategy` | no | `"random"` (default), `"first"`, `"last"` |
| `histogram` | no | Weighted selection distribution |

*Use `topic` for Kafka sources, `table` for Postgres sources.

## Path Drilling

The full event object stored in history has shape `{key: ..., value: ..., vars: ...}`.
Use `path` to extract nested fields:

```json
{ "_gen": "lookup", "topic": "users", "path": ["value", "user_id"] }
{ "_gen": "lookup", "topic": "users", "path": ["key"] }
{ "_gen": "lookup", "topic": "users", "path": ["vars", "myVar"] }
```

## Multiple Lookups in One Generator

A single generator should not call `lookup` twice against the same topic — results will be
inconsistent. Store one lookup in a variable and extract fields:

```json
"vars": {
  "parentEvent": { "_gen": "lookup", "topic": "customers" }
},
"value": {
  "customer_id":   { "_gen": "var", "var": "parentEvent", "path": ["value", "customer_id"] },
  "customer_name": { "_gen": "var", "var": "parentEvent", "path": ["value", "name"] }
}
```

## Pool Size Tuning

`maxHistoryEvents` on the parent generator controls how many events are available for lookup.
Larger pools mean more realistic fan-out (many orders per unique customer):

```json
"localConfigs": { "maxHistoryEvents": 500 }
```

## Common Mistakes

### Wrong — calling lookup twice against the same topic

```json
"value": {
  "id":   { "_gen": "lookup", "topic": "users", "path": ["value", "id"] },
  "name": { "_gen": "lookup", "topic": "users", "path": ["value", "name"] }
}
```

### Correct — use a variable for a single lookup, then extract fields

```json
"vars": {
  "u": { "_gen": "lookup", "topic": "users" }
},
"value": {
  "id":   { "_gen": "var", "var": "u", "path": ["value", "id"] },
  "name": { "_gen": "var", "var": "u", "path": ["value", "name"] }
}
```

## Related

- [generators.md](generators.md)
- [state-machines.md](state-machines.md)
- [cross-topic-relationships.md](../patterns/cross-topic-relationships.md)
