# Implementation Journey & Engineering Decisions

This document is the authoritative record of the technical challenges faced, trade-offs evaluated, and architectural decisions made during development. It is intended for technical reviewers who want to understand the **why** behind the code, not just what it does.

---

## 1. The Concurrency Problem & Decision

### The "Race Condition" Trap

A naive implementation of a request counter looks like this:

```python
# BAD: Classic Read-Modify-Write Race Condition
current_usage = get_usage(org_id)
if current_usage < limit:
    set_usage(org_id, current_usage + 1)
```

If two requests arrive simultaneously, they both read the same `current_usage` (e.g., 99), and both write `100`. The actual usage should be `101`. In a metering context, this is silent billing failure — the system under-charges without any error or log.

### Evaluated Options

| Option                         | Pros                                                   | Cons                                                                      |
| ------------------------------ | ------------------------------------------------------ | ------------------------------------------------------------------------- |
| **Redis `INCR`**               | Fastest possible counter                               | Persistence trade-offs (AOF vs. RDB), sync lag risk, extra infrastructure |
| **PostgreSQL atomic `UPDATE`** | ACID compliant, single source of truth, no extra infra | Higher per-request latency than in-memory                                 |

### Decision: PostgreSQL Atomic Update

```sql
UPDATE usage_records
SET request_count = request_count + 1
WHERE organization_id = :org_id
  AND period_start   = :period_start
  AND request_count  < :limit
RETURNING request_count;
```

The database engine serializes concurrent writes at the row level. If the row doesn't update (returns `NULL`), the limit has been hit. No application-level locking is needed. The constraint is pushed down to where it can be enforced atomically.

Additionally, to safely initialize a new period record without a race condition on insert, I use:

```sql
INSERT INTO usage_records (organization_id, period_start, request_count)
VALUES (:org_id, :period_start, 0)
ON CONFLICT (organization_id, period_start) DO NOTHING;
```

This guarantees only one row per (org, period) window regardless of concurrency.

---

## 2. Challenges & Adaptations

### Challenge A: The "Reset Logic" Fragility

- **Initial Thought:** Use a cron job (Celery/APScheduler) to reset counters at midnight.
- **The Flaw:** If the cron job fails or the server is down at reset time, users remain blocked indefinitely, or worse — their quota never resets. This is a silent operational failure.
- **The Adaptation: "Self-Healing Rolling Windows"**
  - Instead of mutating existing rows, usage is stored as **time-bucket rows** (e.g., `period_start = 2024-10-01 00:00:00`).
  - On every request, the current bucket is calculated from `datetime.now()`.
  - If a record for that bucket exists, it is incremented. If not, a new one is created atomically.
  - **Benefit:** No background workers required. After any downtime, the system starts a fresh bucket and operates correctly without intervention.

### Challenge B: Developer Experience for Rate-Limited APIs

- **Observation:** A bare `429 Too Many Requests` frustrates API consumers who don't know when to retry.
- **Solution:** I inject standard rate-limit headers on every response:
  - `X-RateLimit-Limit` — total quota for the period
  - `X-RateLimit-Used` — requests consumed so far
  - `X-RateLimit-Remaining` — remaining requests
  - The `429` response body also includes a precise countdown: _"Rate limit exceeded. Try again in 43 seconds."_, calculated from the start of the next window.

### Challenge C: Testing Time-Dependent Logic

- **Problem:** Testing monthly billing resets is impossible without waiting 30 days.
- **Solution:** I parameterized the window logic via a `DEMO_MODE` environment variable.
  - `DEMO_MODE=true` → 5-minute rolling windows (fast enough to observe and test)
  - `DEMO_MODE=false` → Monthly windows (production billing behaviour)
- This allows full end-to-end verification of the reset logic in real-time without mocking `datetime.now()`.

---

## 3. Notable Design Choices

### Modular Monolith Architecture

I chose a **Modular Monolith** over Microservices deliberately:

- Microservices add network latency, distributed transaction complexity, and operational overhead that isn't justified at this scale.
- However, the code is structured so the metering engine (`core/metering.py`) is fully decoupled from user management (`api/`). No shared state, no circular imports. It can be extracted into a standalone service later without architecture changes.

### Security Layers

| Layer     | Implementation                                | Reason                                                                |
| --------- | --------------------------------------------- | --------------------------------------------------------------------- |
| Secrets   | All via environment variables, no defaults    | Prevents credential leaks in source control                           |
| Container | Multi-stage Dockerfile, non-root user         | Reduces attack surface and image size                                 |
| Passwords | Argon2 hashing                                | Best-in-class; resistant to GPU cracking                              |
| Auth      | JWT with configurable expiry                  | Stateless; no server-side session storage needed                      |
| CORS      | Configurable `BACKEND_CORS_ORIGINS` allowlist | Prevents cross-origin abuse                                           |
| Schema    | Strict Pydantic models on all I/O             | Validation at the boundary; prevents garbage data entering the system |

### Async Throughout

The entire stack uses Python's `asyncio` — FastAPI, SQLAlchemy (with `asyncpg`), and `httpx` in tests. This means a single worker process can handle many concurrent requests without thread switching overhead, which is critical for a high-concurrency metering service.

---

## 4. Future Roadmap

If this were to scale to millions of requests per minute:

1. **Redis caching layer:** Use Redis `INCR` for the hot counter with Lua scripts for atomicity, and async-flush to PostgreSQL for permanent billing records. Keeps the interface identical.
2. **Tiered credit costs:** Allow different endpoints to consume different quota amounts (e.g., a compute-heavy endpoint costs 5 credits, a lookup costs 1).
3. **Webhook integration:** Add a Stripe/Paddle webhook handler — on payment success, update `organization.plan_id` to a higher tier. The metering engine picks up the new limit on the next request automatically.

---

**Author:** Murali Krishna Pendyala
