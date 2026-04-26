# ShadowTraffic Quick Reference

> Fast lookup tables. For code examples, see linked files.
> **MCP Validated**: 2026-04-24

## Generator DSL Cheat Sheet

| Generator | Syntax Sketch | Output Type |
|-----------|--------------|-------------|
| `uuid` | `{"_gen":"uuid"}` | UUID string |
| `string` | `{"_gen":"string","expr":"#{Name.full_name}"}` | Faker string |
| `boolean` | `{"_gen":"boolean"}` | `true` / `false` |
| `now` | `{"_gen":"now"}` | Epoch ms (long) |
| `uniformDistribution` | `{"_gen":"uniformDistribution","bounds":[1,100]}` | Float in range |
| `normalDistribution` | `{"_gen":"normalDistribution","mean":50,"sd":10}` | Gaussian float |
| `oneOf` | `{"_gen":"oneOf","choices":["A","B","C"]}` | Random element |
| `weightedOneOf` | `{"_gen":"weightedOneOf","choices":[{"weight":80,"value":"A"},...]}` | Weighted pick |
| `someOf` | `{"_gen":"someOf","choices":[...],"min":1,"max":3}` | Random subset |
| `sequentialInteger` | `{"_gen":"sequentialInteger","startingFrom":1}` | 1, 2, 3… |
| `lookup` | `{"_gen":"lookup","topic":"t","path":["value","id"]}` | From history |
| `stateMachine` | `{"_gen":"stateMachine","initial":"S1","states":{},"transitions":{}}` | State value |
| `var` | `{"_gen":"var","var":"myVar"}` | Previously stored value |

## Faker Namespace Reference

| Namespace | Useful Methods |
|-----------|----------------|
| `Name` | `full_name`, `first_name`, `last_name` |
| `Internet` | `email_address`, `url`, `ip_v4_address` |
| `Address` | `city`, `country`, `zip_code`, `full_address` |
| `Company` | `name`, `industry`, `bs` |
| `Finance` | `credit_card`, `iban` |
| `PhoneNumber` | `cell_phone`, `phone_number` |
| `Lorem` | `sentence`, `word`, `paragraph` |
| `Commerce` | `product_name`, `department` |
| `Number` | `number_between '1','100'` |

Format: `"#{ClassName.methodName}"` — always wrap in `#{}`.

## Throttle Decision Matrix

| Use Case | Config |
|----------|--------|
| ~10 events/sec | `"localConfigs": {"throttleMs": 100}` |
| Exact rate (e.g. 500/sec) | `"localConfigs": {"throughput": 500}` |
| Random rate (bursty) | `"localConfigs": {"throttleMs": {"_gen":"uniformDistribution","bounds":[50,500]}}` |
| Stop after N events | `"localConfigs": {"maxEvents": 10000}` |
| Stop after N seconds | `"globalConfigs": {"maxMs": 60000}` |
| Delay generator start | `"localConfigs": {"delay": 3000}` |

## Minimal Config Skeleton

```json
{
  "generators": [
    {
      "topic": "my-topic",
      "key": { "_gen": "uuid" },
      "value": {
        "id":         { "_gen": "uuid" },
        "name":       { "_gen": "string", "expr": "#{Name.full_name}" },
        "created_at": { "_gen": "now" }
      },
      "localConfigs": { "throttleMs": 500 }
    }
  ],
  "connections": {
    "localKafka": {
      "kind": "kafka",
      "producerConfigs": {
        "bootstrap.servers": "localhost:9092",
        "key.serializer":   "io.shadowtraffic.kafka.serdes.JsonSerializer",
        "value.serializer": "io.shadowtraffic.kafka.serdes.JsonSerializer"
      }
    }
  }
}
```

## Common Pitfalls

| Do Not | Do Instead |
|--------|------------|
| `"expr": "Name.full_name"` | `"expr": "#{Name.full_name}"` |
| Put `throttleMs` at generator root | Nest inside `localConfigs` |
| Call `lookup` twice in same generator | Store one lookup in `vars`, extract fields with `var` |
| Leave terminal states without `null` transition | Set `"DELIVERED": null` in `transitions` |
| Omit `maxHistoryEvents` on high-volume parent | Set `"maxHistoryEvents": 200+` |

## Related Documentation

| Topic | Path |
|-------|------|
| Generator primitives | `concepts/generators.md` |
| Connection config | `concepts/connections.md` |
| Throttle controls | `concepts/throttle.md` |
| State machines | `concepts/state-machines.md` |
| Cross-topic lookup | `concepts/local-pool.md` |
| Full Index | `index.md` |
