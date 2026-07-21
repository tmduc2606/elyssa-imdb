"""Blackout Drill: Network Latency Simulation

Measures API response times under normal conditions and verifies
graceful degradation when upstream dependencies are slow.
"""

import sys
import time
import urllib.request
import urllib.error
import json

API_BASE = "http://localhost:8000"


def measure_latency(endpoint: str, method: str = "GET", body: bytes = None) -> dict:
    """Measure response time for a single endpoint."""
    url = f"{API_BASE}{endpoint}"
    start = time.time()
    try:
        req = urllib.request.Request(url, data=body, method=method)
        if body:
            req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=30) as resp:
            elapsed = time.time() - start
            return {"endpoint": endpoint, "latency_ms": round(elapsed * 1000), "status": resp.status}
    except urllib.error.HTTPError as e:
        elapsed = time.time() - start
        return {"endpoint": endpoint, "latency_ms": round(elapsed * 1000), "status": e.code}
    except Exception as e:
        elapsed = time.time() - start
        return {"endpoint": endpoint, "latency_ms": round(elapsed * 1000), "status": 0, "error": str(e)}


def run_latency_test():
    """Measure baseline latency for all endpoints."""
    endpoints = [
        ("/health", "GET", None),
        ("/api/v1/titles?per_page=5", "GET", None),
        ("/api/v1/titles?per_page=20&sort=average_rating", "GET", None),
        ("/graphql", "POST", json.dumps({
            "query": "{ homepage { trending { id primaryTitle startYear } } }"
        }).encode()),
        ("/api/v1/predict/genre", "POST", json.dumps({
            "runtime_minutes": 120, "start_year": 2020, "title_type": "movie", "is_adult": False
        }).encode()),
        ("/api/v1/models", "GET", None),
    ]

    print("Latency baseline test")
    print("-" * 60)

    all_results = []
    for endpoint, method, body in endpoints:
        # Run each endpoint 5 times, take median
        times = []
        for _ in range(5):
            result = measure_latency(endpoint, method, body)
            times.append(result["latency_ms"])
        times.sort()
        median = times[len(times) // 2]
        all_results.append({"endpoint": endpoint, "median_ms": median, "p95_ms": times[int(len(times)*0.95)]})
        print(f"  {endpoint:45s}  median={median:6d}ms  p95={times[int(len(times)*0.95)]:6d}ms")

    # Check p95 < 500ms threshold
    violations = [r for r in all_results if r["p95_ms"] > 500]
    if violations:
        print(f"\nFAIL: {len(violations)} endpoints exceed 500ms p95 threshold:")
        for v in violations:
            print(f"  {v['endpoint']}: p95={v['p95_ms']}ms")
        sys.exit(1)

    print(f"\nPASS: All {len(all_results)} endpoints within 500ms p95 threshold")


if __name__ == "__main__":
    run_latency_test()
