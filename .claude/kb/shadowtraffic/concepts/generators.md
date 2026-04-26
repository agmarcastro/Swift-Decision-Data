# Generators — The `_gen` DSL

> **Purpose**: Atomic reference for every `_gen` primitive available in ShadowTraffic
> **Confidence**: 0.95
> **MCP Validated**: 2026-04-24

## Overview

ShadowTraffic's core design principle is "replace concrete values with functions." Every field value
in a generator config can be a `_gen` expression. Functions are plain JSON maps with a `_gen` key;
all other keys are parameters. Functions compose freely — any parameter that accepts a value also
accepts another `_gen` expression.

## The Pattern

```json
{
  "topic": "events",
  "value": {
    "id":         { "_gen": "uuid" },
    "name":       { "_gen": "string", "expr": "#{Name.full_name}" },
    "age":        { "_gen": "uniformDistribution", "bounds": [18, 80] },
    "score":      { "_gen": "normalDistribution", "mean": 50, "sd": 10 },
    "active":     { "_gen": "boolean" },
    "created_at": { "_gen": "now" },
    "status":     { "_gen": "oneOf", "choices": ["NEW", "ACTIVE", "CLOSED"] },
    "tags":       { "_gen": "someOf", "choices": ["a", "b", "c"], "min": 1, "max": 2 },
    "seq_id":     { "_gen": "sequentialInteger", "startingFrom": 1000 },
    "maybe_note": {
      "_gen": "weightedOneOf",
      "choices": [
        { "weight": 80, "value": null },
        { "weight": 20, "value": { "_gen": "string", "expr": "#{Lorem.sentence}" } }
      ]
    }
  }
}
```

## Quick Reference

| Generator | Key Parameters | Output |
|-----------|----------------|--------|
| `uuid` | — | Random UUID string |
| `string` | `expr` (Faker pattern) | Fake text via Java Faker |
| `uniformDistribution` | `bounds: [min, max]` | Random float in range |
| `normalDistribution` | `mean`, `sd` | Gaussian float |
| `boolean` | — | `true` or `false` |
| `now` | — | Current epoch milliseconds |
| `formatDateTime` | `format` (Java pattern) | Formatted date string |
| `oneOf` | `choices: [...]` | Random equal-probability pick |
| `weightedOneOf` | `choices: [{weight, value}]` | Weighted random pick |
| `someOf` | `choices`, `min`, `max` | Random subset array |
| `sequentialInteger` | `startingFrom` | Monotonically increasing int |
| `lookup` | `topic`, `path` | Value from another topic's history |
| `stateMachine` | `initial`, `states`, `transitions` | State-driven value |

## Producing Nulls with Weight

Use `weightedOneOf` to emit nulls at a specified probability:

```json
{
  "_gen": "weightedOneOf",
  "choices": [
    { "weight": 10, "value": null },
    { "weight": 90, "value": { "_gen": "string", "expr": "#{Internet.email_address}" } }
  ]
}
```

## Faker Expression Format

```json
{ "_gen": "string", "expr": "#{Namespace.method}" }
```

Key namespaces: `Name`, `Internet`, `Address`, `Company`, `Finance`, `PhoneNumber`, `Lorem`.
Expression syntax is always `#{ClassName.methodName}` — the `#` prefix and curly braces are required.

## Common Mistakes

### Wrong

```json
{ "_gen": "string", "expr": "Name.full_name" }
```

### Correct

```json
{ "_gen": "string", "expr": "#{Name.full_name}" }
```

## Related

- [connections.md](connections.md)
- [throttle.md](throttle.md)
- [kafka-topic-generator.md](../patterns/kafka-topic-generator.md)
- [quick-reference.md](../quick-reference.md)
