"""Blackout Drill: 200% Data Surge Simulation

Sends 2x normal request volume to the API to test rate limiting,
error handling, and performance under load.
"""

import sys
import time
import urllib.request
import urllib.error
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

API_BASE = "http://localhost:8000"
ENDPOINTS = [
    "/health",
    "/api/v1/titles?per_page=20",
    "/api/v1/titles?per_page=20&sort=average_rating",
    "/graphql",
]
PAYLOADS = {
    "/graphql": json.dumps({
        "query": "{ homepage { trending { id primaryTitle startYear } } }"
    }).encode(),
}


def send_request(endpoint: str) -> dict:
    """Send a single request and return status info."""
    url = f"{API_BASE}{endpoint}"
    body = PAYLOADS.get(endpoint)
    method = "POST" if body else "GET"
    start = time.time()
    try:
        req = urllib.request.Request(url, data=body, method=method)
        if body:
            req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=30) as resp:
            elapsed = time.time() - start
            return {"status": resp.status, "latency_ms": round(elapsed * 1000), "endpoint": endpoint}
    except urllib.error.HTTPError as e:
        elapsed = time.time() - start
        return {"status": e.code, "latency_ms": round(elapsed * 1000), "endpoint": endpoint}
    except Exception as e:
        elapsed = time.time() - start
        return {"status": 0, "latency_ms": round(elapsed * 1000), "endpoint": endpoint, "error": str(e)}


def run_surge(concurrency: int = 50, duration_seconds: int = 60):
    """Run surge test with given concurrency for specified duration."""
    print(f"Surge test: {concurrency} concurrent workers, {duration_seconds}s duration")
    results = []
    start = time.time()

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = []
        while time.time() - start < duration_seconds:
            for endpoint in ENDPOINTS:
                futures.append(executor.submit(send_request, endpoint))
            time.sleep(0.1)

        for future in as_completed(futures):
            results.append(future.result())

    total = len(results)
    statuses = {}
    latencies = []
    for r in results:
        s = r["status"]
        statuses[s] = statuses.get(s, 0) + 1
        latencies.append(r["latency_ms"])

    latencies.sort()
    print(f"\nResults: {total} requests in {duration_seconds}s")
    print(f"Status codes: {statuses}")
    print(f"Latency p50: {latencies[len(latencies)//2]}ms")
    print(f"Latency p95: {latencies[int(len(latencies)*0.95)]}ms")
    print(f"Latency p99: {latencies[int(len(latencies)*0.99)]}ms")

    error_rate = statuses.get(0, 0) + sum(v for k, v in statuses.items() if k >= 500)
    if error_rate / max(total, 1) > 0.01:
        print(f"FAIL: Error rate {error_rate/max(total,1):.2%} > 1% threshold")
        sys.exit(1)
    print("PASS: Error rate within threshold")


if __name__ == "__main__":
    concurrency = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    duration = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    run_surge(concurrency, duration)
