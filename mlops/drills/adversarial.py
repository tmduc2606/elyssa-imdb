"""Blackout Drill: Adversarial Query Simulation

Sends malformed, edge-case, and adversarial requests to test API
input validation, error handling, and security hardening.
"""

import sys
import urllib.request
import urllib.error
import json

API_BASE = "http://localhost:8000"

ADVERSARIAL_REQUESTS = [
    # SQL injection attempts
    {"endpoint": "/api/v1/titles?q='; DROP TABLE--", "method": "GET"},
    {"endpoint": "/api/v1/titles?q=%27+OR+1%3D1--", "method": "GET"},

    # XSS attempts
    {"endpoint": "/api/v1/titles?q=<script>alert(1)</script>", "method": "GET"},
    {"endpoint": "/api/v1/search?q=<img+src=x+onerror=alert(1)>", "method": "GET"},

    # Path traversal
    {"endpoint": "/api/v1/titles/../../etc/passwd", "method": "GET"},
    {"endpoint": "/api/v1/titles/..%2F..%2Fetc%2Fpasswd", "method": "GET"},

    # Overflow / extreme values
    {"endpoint": "/api/v1/titles?per_page=999999", "method": "GET"},
    {"endpoint": "/api/v1/titles?per_page=-1", "method": "GET"},
    {"endpoint": "/api/v1/titles?page=999999", "method": "GET"},

    # Missing required fields
    {"endpoint": "/api/v1/predict/genre", "method": "POST", "body": "{}"},
    {"endpoint": "/api/v1/predict/genre", "method": "POST", "body": '{"runtime_minutes": "not_a_number"}'},

    # Auth bypass attempts
    {"endpoint": "/auth/me", "method": "GET"},
    {"endpoint": "/api/v1/watchlist", "method": "GET"},

    # GraphQL introspection abuse
    {"endpoint": "/graphql", "method": "POST",
     "body": json.dumps({"query": "{ __schema { types { name } } }"})},

    # Large payload
    {"endpoint": "/api/v1/predict/genre", "method": "POST",
     "body": json.dumps({"runtime_minutes": 999999999, "start_year": 9999, "title_type": "x" * 10000})},
]


def run_adversarial():
    """Send all adversarial requests and check that none cause 500 errors."""
    print(f"Adversarial test: {len(ADVERSARIAL_REQUESTS)} malicious requests")
    failures = []

    for i, req in enumerate(ADVERSARIAL_REQUESTS):
        url = f"{API_BASE}{req['endpoint']}"
        body = req.get("body", "").encode() if req.get("body") else None
        try:
            http_req = urllib.request.Request(url, data=body, method=req["method"])
            if body:
                http_req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(http_req, timeout=10) as resp:
                if resp.status >= 500:
                    failures.append((i, req["endpoint"], resp.status, "Server error on adversarial input"))
        except urllib.error.HTTPError as e:
            if e.code >= 500:
                failures.append((i, req["endpoint"], e.code, "Server error on adversarial input"))
            # 4xx errors are expected and acceptable
        except Exception as e:
            failures.append((i, req["endpoint"], 0, str(e)))

    if failures:
        print(f"\nFAIL: {len(failures)} requests caused server errors:")
        for idx, endpoint, status, msg in failures:
            print(f"  [{idx}] {endpoint} -> {status}: {msg}")
        sys.exit(1)

    print(f"PASS: All {len(ADVERSARIAL_REQUESTS)} adversarial requests handled gracefully (no 5xx)")


if __name__ == "__main__":
    run_adversarial()
