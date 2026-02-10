# Implementation Journey & Engineering Decisions

This document chronicles the development process of the **SaaS Metering Platform**, highlighting the technical challenges faced, the trade-offs considered, and the architectural decisions made. It is intended for technical reviewers and recruiters interested in the "why" behind the code.

---

## 1. Research & The Concurrency Problem

The core challenge of any metering system is **accuracy under load**.

### The "Race Condition" Trap

A naive implementation might look like this:

```python
# BAD: Classic Read-Modify-Write Race Condition
current_usage = get_usage(org_id)
if current_usage < limit:
    set_usage(org_id, current_usage + 1)
```

If two requests arrive simultaneously, they both read the same `current_usage` (e.g., 99), and both write `100`. The actual usage should be `101`. In a high-volume API, this leads to significant **revenue leakage**.

### The Decision: PostgreSQL Atomic Updates

I evaluated two solutions:

1.  **Redis (INCR):** Extremely fast, but simple key-value storage. Persistence can be tricky (AOF vs RDB trade-offs).
2.  **PostgreSQL (UPDATE ... RETURNING):** ACID compliant, guaranteeing data integrity.

**Verdict:** I chose **PostgreSQL**.

- **Why?** Billing data requires strict consistency over raw speed.
- **Implementation:** I used an atomic query:
  ```sql
  UPDATE usage_records
  SET request_count = request_count + 1
  WHERE organization_id = :org_id AND request_count < :limit
  RETURNING request_count
  ```
  This pushes the locking logic to the database engine, ensuring 100% accuracy without complex application-level locking.

---

## 2. Challenges & Adaptations

### Challenge A: The "Reset Logic" Fragility

- **Initial Thought:** Use a cron job (Celery/APScheduler) to reset counters at midnight.
- **The Flaw:** If the cron job fails or the server is down at 00:00, usage never resets. Users remain blocked indefinitely.
- **The Adaptation:** **"Lazy Rolling Windows"**.
  - Instead of resetting a row, we conceptualize usage as time buckets (e.g., `2023-10-27 10:00:00`).
  - When a request comes in, we calculate the _current_ bucket.
  - If a record for that bucket exists, we increment it.
  - If not, we create it.
  - **Benefit:** The system is self-healing. No background workers are required. If the system is down for an hour, it simply starts a fresh bucket when it comes back up.

### Challenge B: Improving Developer Experience (DX)

- **Observation:** A simple `429 Too Many Requests` status code often frustrates users because they don't know _when_ to retry.
- **Solution:** I enhanced the `Dependency` to inject standardization headers:
  - `X-RateLimit-Limit`: Total allowed.
  - `X-RateLimit-Remaining`: How many left.
  - **Smart Error Messages:** Calculated the exact seconds remaining in the current window (`timedelta`) and returned a helpful message: _"Rate limit exceeded. Try again in 43 seconds."_

---

## 3. Notable Design Choices

### Modular Monolith Architecture

- I avoided Microservices to keep the operational complexity low.
- However, I structured the code (`core`, `api`, `models`, `schemas`) so that the "Metering Engine" is decoupled from the "User Management" logic. This allows for easy extraction into a microservice in the future if scaling requires it.

### Testing Time-Dependent Logic

- Testing "Monthly" resets is hard. Waiting 30 days for a test to pass is impossible.
- **Solution:** I parameterized the metering window logic. During development/testing, I switched the logic to use **5-minute windows**. This allowed me to verify the "Reset" behavior manually and via integration tests in real-time.

---

## 4. Future Roadmap

If this were to go into high-scale production (millions of RPM), I would:

1.  **Redis Caching Layer:** Use Lua scripts in Redis for the counters to reduce DB load, and asynchronously sync to Postgres for permanent billing records.
2.  **Tiered limits:** Allow different rate limits for different endpoints (e.g., "heavy" endpoints cost 5 credits, "light" endpoints cost 1).

---

**Author:** Murali Krishna Pendyala
