# State Machines

> **Purpose**: Model stateful entity lifecycles with `stateMachine` transitions and weights
> **Confidence**: 0.95
> **MCP Validated**: 2026-04-24

## Overview

The `stateMachine` generator tracks a current state per entity and emits values according to
that state. Transitions are either a map (state → next state) or an array with `weight` for
probabilistic branching. Transitioning to `null` terminates the machine for that entity.
When placed at the top level of a generator's `value`, state values are merged into the
full event body rather than replacing a single field.

## The Pattern

```json
{
  "topic": "order-events",
  "key": { "_gen": "uuid" },
  "value": {
    "order_id": { "_gen": "uuid" },
    "status": {
      "_gen": "stateMachine",
      "initial": "CREATED",
      "states": {
        "CREATED":    { "status": "CREATED" },
        "PROCESSING": { "status": "PROCESSING" },
        "SHIPPED":    { "status": "SHIPPED" },
        "DELIVERED":  { "status": "DELIVERED" },
        "CANCELLED":  { "status": "CANCELLED" }
      },
      "transitions": {
        "CREATED":    [
          { "to": "PROCESSING", "weight": 90 },
          { "to": "CANCELLED",  "weight": 10 }
        ],
        "PROCESSING": [
          { "to": "SHIPPED",    "weight": 85 },
          { "to": "CANCELLED",  "weight": 15 }
        ],
        "SHIPPED":    [{ "to": "DELIVERED", "weight": 95 }, { "to": "null", "weight": 5 }],
        "DELIVERED":  null,
        "CANCELLED":  null
      }
    },
    "updated_at": { "_gen": "now" }
  }
}
```

## Quick Reference

| Parameter | Required | Description |
|-----------|----------|-------------|
| `initial` | yes | Starting state name |
| `states` | yes | Map of state name → emitted value |
| `transitions` | yes | Map or array defining state progression |
| `merge` | no | `{"previous": true}` to carry forward prior event fields |

## Transition Styles

**Weighted map (probabilistic)**
```json
"transitions": {
  "A": [{ "to": "B", "weight": 70 }, { "to": "C", "weight": 30 }],
  "B": [{ "to": "D", "weight": 100 }],
  "C": null,
  "D": null
}
```

**Sequential array (deterministic)**
```json
"transitions": ["CREATED", "PROCESSING", "SHIPPED", "DELIVERED"]
```

**Terminal state** — set transition value to `null`:
```json
"transitions": { "DELIVERED": null, "CANCELLED": null }
```

## Per-State Throttle Override

Each state can override `throttleMs` and `delay` via `localConfigs`:

```json
"states": {
  "PROCESSING": {
    "status": "PROCESSING",
    "localConfigs": { "throttleMs": 5000 }
  }
}
```

## Key Binding with Fork

Use `fork` to clone the generator once per entity so each instance has its own state:

```json
{
  "topic": "sessions",
  "fork": {
    "key": { "_gen": "uuid" },
    "maxForks": 50
  },
  "value": {
    "session_id": { "_gen": "var", "var": "forkKey" },
    "state": {
      "_gen": "stateMachine",
      "initial": "ACTIVE",
      "states": { ... },
      "transitions": { ... }
    }
  }
}
```

## Common Mistakes

### Wrong — terminal state has an empty object instead of null

```json
"transitions": { "DELIVERED": {} }
```

### Correct — use `null` to terminate the state machine

```json
"transitions": { "DELIVERED": null }
```

## Related

- [generators.md](generators.md)
- [local-pool.md](local-pool.md)
- [order-lifecycle-state-machine.md](../patterns/order-lifecycle-state-machine.md)
