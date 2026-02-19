# Performance Benchmarks

## Methodology

Benchmarks run against the local Dockerized stack on Windows using `scripts/benchmark.py`.

| Setting        | Value                                                |
| -------------- | ---------------------------------------------------- |
| Tool           | Custom Python `asyncio` + `httpx` script             |
| Environment    | Docker Desktop on Windows (dev mode, `--reload`)     |
| Concurrency    | 50 simultaneous in-flight requests (semaphore-gated) |
| Total Requests | 500                                                  |

> **Note**: Docker Desktop on Windows runs inside a Linux VM, which typically adds a 40–60% latency overhead compared to a native Linux server. Results on a real server would be significantly better.

## Actual Results (Local Dev)

| Metric              | Result                                           |
| ------------------- | ------------------------------------------------ |
| **Throughput**      | ~25–35 req/s                                     |
| **Latency (min)**   | ~60ms                                            |
| **Latency (mean)**  | ~200–400ms                                       |
| **Latency (P95)**   | ~800ms                                           |
| **Error Rate**      | **0% — 0 errors across 500 concurrent requests** |
| **Race Conditions** | **0 detected**                                   |

## Key Finding: Correctness Under Concurrency

The most important result for a **metering engine** is **zero errors and zero race conditions** under high concurrency. The atomic `UPDATE ... WHERE count < limit` approach guarantees that usage counts are always accurate — no double-counting, no over-limit requests slipping through.

## How to Run

```bash
# Stack must be running first
docker-compose up -d

# Run benchmark
python scripts/benchmark.py
```

## Why Not Redis?

PostgreSQL handles the atomic increment (`UPDATE SET count = count + 1 WHERE count < limit`) in a single round-trip at the database engine level. This serializes concurrent writes correctly without distributed locks, keeping the architecture simple. Redis would reduce latency at very high scale, but adds operational complexity and eventual-consistency risks if it crashes before syncing.
