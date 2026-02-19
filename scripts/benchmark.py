import asyncio
import time
import httpx
import statistics
from collections import Counter

# --- Configuration ---
BASE_URL = "http://localhost:8000"
CONCURRENT_REQUESTS = 50   # True simultaneous requests in flight at once
TOTAL_REQUESTS = 500        # Total to fire
EMAIL = "admin@example.com"
PASSWORD = "admin"

async def get_token(client: httpx.AsyncClient) -> str | None:
    try:
        response = await client.post(
            f"{BASE_URL}/api/v1/login/access-token",
            data={"username": EMAIL, "password": PASSWORD},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()["access_token"]
    except Exception as e:
        print(f"[ERROR] Login failed: {e}")
        return None


async def single_request(sem: asyncio.Semaphore, client: httpx.AsyncClient, headers: dict) -> tuple[float, int]:
    """Fire one request, gated by semaphore for concurrency control."""
    async with sem:
        start = time.perf_counter()
        try:
            resp = await client.get(f"{BASE_URL}/api/v1/widgets/", headers=headers, timeout=10)
            status = resp.status_code
        except Exception:
            status = 0
        elapsed_ms = (time.perf_counter() - start) * 1000
        return elapsed_ms, status


async def main():
    print(f"--- Starting Benchmark ---")
    print(f"Target:           {BASE_URL}")
    print(f"Total Requests:   {TOTAL_REQUESTS}")
    print(f"Concurrency:      {CONCURRENT_REQUESTS} simultaneous")
    print()

    async with httpx.AsyncClient() as client:
        token = await get_token(client)
        if not token:
            print("Aborting: could not authenticate.")
            return

        headers = {"Authorization": f"Bearer {token}"}
        sem = asyncio.Semaphore(CONCURRENT_REQUESTS)

        # Fire all requests concurrently, gated by semaphore
        start_total = time.perf_counter()
        tasks = [single_request(sem, client, headers) for _ in range(TOTAL_REQUESTS)]
        results = await asyncio.gather(*tasks)
        total_time = time.perf_counter() - start_total

    latencies = [r[0] for r in results]
    statuses  = [r[1] for r in results]

    print(f"--- Results ---")
    print(f"Total Time:       {total_time:.2f}s")
    print(f"Throughput:       {TOTAL_REQUESTS / total_time:.1f} req/s")
    print()
    print(f"Latency (ms):")
    print(f"  Min:            {min(latencies):.1f}")
    print(f"  Mean:           {statistics.mean(latencies):.1f}")
    p95_idx = int(len(latencies) * 0.95)
    print(f"  P95:            {sorted(latencies)[p95_idx]:.1f}")
    print(f"  Max:            {max(latencies):.1f}")
    print()
    print(f"Status Codes:")
    for code, count in sorted(Counter(statuses).items()):
        pct = count / TOTAL_REQUESTS * 100
        print(f"  {code}: {count} ({pct:.1f}%)")

if __name__ == "__main__":
    asyncio.run(main())
