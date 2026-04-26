# Throttle

> **Purpose**: Control event generation rate, total volume, and simulation duration
> **Confidence**: 0.95
> **MCP Validated**: 2026-04-24

## Overview

Throttle settings live in `localConfigs` (per-generator) or `globalConfigs` (all generators).
They answer three questions: how fast, how many, and for how long. The most common control is
`throttleMs` — the minimum milliseconds between successive events from one generator.

## The Pattern

```json
{
  "generators": [
    {
      "topic": "orders",
      "value": { "id": { "_gen": "uuid" } },
      "localConfigs": {
        "throttleMs": 100,
        "maxEvents":  5000
      }
    }
  ],
  "globalConfigs": {
    "maxMs": 60000
  }
}
```

## Quick Reference

| Setting | Scope | Type | Description |
|---------|-------|------|-------------|
| `throttleMs` | local / global | number or `_gen` | Min ms between events |
| `throughput` | local / global | number | Target events per second |
| `maxEvents` | local / global | number | Stop after N events |
| `maxMs` | local / global | number | Stop after N milliseconds |
| `delay` | local | number | ms to wait before first event |
| `discard.rate` | local | 0.0–1.0 | Fraction of events to drop silently |
| `maxHistoryEvents` | local | number | Max events retained in lookup pool |

## Dynamic Throttle

`throttleMs` accepts a `_gen` expression for variance:

```json
"localConfigs": {
  "throttleMs": {
    "_gen": "uniformDistribution",
    "bounds": [50, 300]
  }
}
```

## Rate-Based (throughput)

```json
"localConfigs": {
  "throughput": 100
}
```

Generates approximately 100 events per second. Cannot be combined with `throttleMs` on the
same generator — choose one approach.

## Capping Total Volume

```json
"localConfigs": {
  "maxEvents": 10000
}
```

Generator becomes dormant after 10 000 events.

## Time-Bounded Simulation

```json
"globalConfigs": {
  "maxMs": 300000
}
```

All generators stop after 5 minutes of wall-clock time.

## Burst with Delay

Use `delay` to stagger when generators start producing:

```json
"localConfigs": {
  "throttleMs": 50,
  "delay": 2000
}
```

Second generator starts 2 seconds after ShadowTraffic begins.

## Common Mistakes

### Wrong — `throttleMs` at generator root (not in `localConfigs`)

```json
{
  "topic": "events",
  "throttleMs": 100
}
```

### Correct

```json
{
  "topic": "events",
  "localConfigs": { "throttleMs": 100 }
}
```

## Related

- [generators.md](generators.md)
- [throttle-strategies.md](../patterns/throttle-strategies.md)
- [kafka-topic-generator.md](../patterns/kafka-topic-generator.md)
