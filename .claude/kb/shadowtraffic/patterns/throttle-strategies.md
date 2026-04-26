# Throttle Strategies

> **Purpose**: Rate control recipes for different throughput scenarios
> **MCP Validated**: 2026-04-24

## When to Use

- Matching a production event rate for realistic load testing
- Capping data volume to avoid overwhelming a local Kafka broker
- Time-bounding a simulation run for CI pipelines
- Simulating bursty traffic patterns (quiet periods followed by spikes)

## Implementation

```json
{
  "generators": [

    {
      "topic": "steady-stream",
      "value": { "id": { "_gen": "uuid" } },
      "localConfigs": {
        "throttleMs": 100
      }
    },

    {
      "topic": "high-throughput",
      "value": { "id": { "_gen": "uuid" } },
      "localConfigs": {
        "throughput": 500
      }
    },

    {
      "topic": "variable-rate",
      "value": { "id": { "_gen": "uuid" } },
      "localConfigs": {
        "throttleMs": {
          "_gen": "uniformDistribution",
          "bounds": [50, 500]
        }
      }
    },

    {
      "topic": "capped-volume",
      "value": { "id": { "_gen": "uuid" } },
      "localConfigs": {
        "throttleMs": 50,
        "maxEvents": 10000
      }
    },

    {
      "topic": "delayed-start",
      "value": { "id": { "_gen": "uuid" } },
      "localConfigs": {
        "throttleMs": 200,
        "delay": 5000
      }
    },

    {
      "topic": "sparse-events",
      "value": { "id": { "_gen": "uuid" } },
      "localConfigs": {
        "throttleMs": 10000
      }
    }

  ],
  "globalConfigs": {
    "maxMs": 120000
  },
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

## Configuration

| Strategy | Config | Approx Rate |
|----------|--------|-------------|
| Steady stream | `"throttleMs": 100` | ~10 events/sec |
| High throughput | `"throughput": 500` | 500 events/sec |
| Variable rate | `"throttleMs": {"_gen": "uniformDistribution", "bounds": [50,500]}` | 2–20 events/sec |
| Capped volume | `"maxEvents": 10000` | Stops at N events |
| Delayed start | `"delay": 5000` | Begins 5s after run start |
| Sparse/IOT-style | `"throttleMs": 10000` | 1 event per 10s |
| Time-bounded | `"globalConfigs": {"maxMs": 120000}` | All generators stop at 2min |

## Example Usage

Simulate 60 seconds of production-like traffic with three different topic rates:

```json
{
  "generators": [
    {
      "topic": "user-events",
      "value": { "id": { "_gen": "uuid" }, "event": { "_gen": "oneOf", "choices": ["click","view","scroll"] } },
      "localConfigs": { "throughput": 200 }
    },
    {
      "topic": "transactions",
      "value": { "id": { "_gen": "uuid" }, "amount": { "_gen": "normalDistribution", "mean": 45, "sd": 20 } },
      "localConfigs": { "throttleMs": 300 }
    },
    {
      "topic": "heartbeats",
      "value": { "service": { "_gen": "oneOf", "choices": ["api","worker","scheduler"] }, "ts": { "_gen": "now" } },
      "localConfigs": { "throttleMs": 5000 }
    }
  ],
  "globalConfigs": { "maxMs": 60000 },
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

## See Also

- [throttle.md](../concepts/throttle.md)
- [kafka-topic-generator.md](kafka-topic-generator.md)
- [order-lifecycle-state-machine.md](order-lifecycle-state-machine.md)
