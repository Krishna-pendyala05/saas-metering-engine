# Multi-Tenant SaaS Subscription & Usage Metering Platform

A high-performance, concurrency-safe API backend designed to solve the critical "Metered Billing" problem for SaaS companies.

---

## 1. The Problem

In the modern API economy (e.g., OpenAI, Twilio, Stripe), pricing is rarely flat. It is **usage-based** (pay-per-call, pay-per-minute).
Building a system that counts requests accurately at scale is difficult:

- **Race Conditions:** If two users hit the API at the exact same microsecond, a naive counter will only count 1 instead of 2. This leads to **revenue leakage**.
- **Latency:** Checking limits on every request can slow down the API.
- **Complexity:** Managing Multi-Tenancy (Organizations vs Users) and reset logic (Monthly vs Daily) is non-trivial.

## 2. Stakeholders

- **SaaS Founders:** Need a way to monetize their API products immediately.
- **API Developers:** Need a drop-in middleware that handles "Rate Limiting" and "Metering" so they can focus on business logic.
- **Product Managers:** Need visibility into who is using the platform and how much.

## 3. Our Solution

We provide a **Modular Monolith** backend that acts as a "Metering Engine".

- **Atomic Accounting:** Uses database-level locking and atomic increments (`UPDATE ... SET count = count + 1`) to guarantee 100% accuracy, even under high concurrency.
- **Zero-Latency Overhead:** Optimized SQL queries ensure limit checks happen in milliseconds.
- **Tenant Isolation:** Built-in concept of "Organizations", allowing teams to share a quota.
- **Dynamic Enforcement:** Validates limits in real-time. If a user exceeds their plan, they are instantly blocked with a `429 Too Many Requests`.

---

## 4. Architecture

The system follows a clean **"Modular Monolith"** architecture, separating concerns into distinct layers:

<img src="architecture.png" width="100%" alt="Architecture Diagram">

### Key Components:

1.  **`api/deps.py`**: The "Gatekeeper". Every request goes through `check_usage_limits`.
2.  **`core/metering.py`**: The "Accountant". Handles the atomic math and window calculations (currently 5-minute rolling windows).
3.  **`models/`**: The "Truth". SQLAlchemy models defining the relationship between Users, Organizations, Plans, and Usage.

---

## 5. Technology Stack & Motivation

| Technology       | Role             | Why we chose it?                                                                                                                             |
| :--------------- | :--------------- | :------------------------------------------------------------------------------------------------------------------------------------------- |
| **FastAPI**      | Web Framework    | **Performance.** It is one of the fastest Python frameworks available (AsyncIO based) and provides automatic Swagger documentation.          |
| **PostgreSQL**   | Database         | **Reliability & ACID Compliance.** For billing data, we cannot afford "eventual consistency" (NoSQL). We need strict transaction guarantees. |
| **SQLAlchemy**   | ORM              | **Type Safety.** Provides a robust way to model complex relationships (1-to-many) without writing raw SQL for everything.                    |
| **Docker**       | Containerization | **Portability.** Ensures the app "just works" on any machine, eliminating "it works on my machine" bugs.                                     |
| **Argon2 / JWT** | Security         | **Industry Standard.** Best-in-class password hashing and stateless authentication.                                                          |

---

## 6. How to Use

### Prerequisites

- Docker & Docker Compose installed.

### Setup & Run

1.  **Clone the repository.**
2.  **Start the System:**
    ```bash
    docker-compose up -d --build
    ```
3.  **Access the API:**
    Open your browser to: **[http://localhost:8000/docs](http://localhost:8000/docs)**

### Testing the Metering (Walkthrough)

1.  **Sign Up:** Use `POST /api/v1/users/` to create an admin account.
2.  **Authorize:** Click "Authorize" at the top right of Swagger UI and log in.
3.  **Check Profile:** Call `GET /api/v1/users/me` to see your **Organization ID** and Plan.
4.  **Use the Service:** Call `GET /api/v1/widgets/`.
    - **Header Check:** Look at `X-RateLimit-Remaining` in the response headers.
    - **Hit the Limit:** Keep calling it until you exceed the quota (default: 5 requests / 5 mins).
    - **Observe Block:** You will receive a `429 Too Many Requests` error with a countdown timer.

---

## 7. Common Errors & Troubleshooting

### `Error: port is already allocated`

- **Cause:** You likely have another PostgreSQL running on port `5432` or the app is already running.
- **Fix:**
  - Stop other services: `docker-compose down`
  - Or change ports in `docker-compose.yml` (e.g., `5435:5432`). _Note: Our config defaults to 5435 for DB to avoid conflicts._

### `alembic: command not found` (inside container)

- **Cause:** Dependency installation issues.
- **Fix:** Ensure `poetry` or `pip` installed `alembic`. Run `docker-compose build` again.

### `Authentication Failed` (401)

- **Cause:** You forgot to put the token in the header.
- **Fix:** Use the "Authorize" button in Swagger UI. It handles the `Authorization: Bearer <token>` header automatically.

---

---

## 8. Implementation Journey

For a detailed breakdown of the engineering challenges, architectural decisions (e.g., why Postgres over Redis), and adaptations made during development, please see the **[Implementation Journey & Design Decisions](IMPLEMENTATION_JOURNEY.md)** document.

---

## 9. For Enterprise Integration (Customization)

This project is built as a **White-Label Engine**.

- **Integration:** You can import this logic into your existing Django/Flask/Node app by connecting to the same PostgreSQL database and using the same queries.
- **Payment Gateways:** To go "Live", simply add a webhook handler for Stripe/Paddle. When a payment succeeds, update the `subscription_plans` table or move the user's `organization.plan_id` to the "Pro" plan.
- **Scaling:** For millions of requests, this architecture can be upgraded to use **Redis** for the counters (faster, but slightly less durable) using the exact same logic structure.

---

**Developed and Maintained by:** Murali Krishna Pendyala
