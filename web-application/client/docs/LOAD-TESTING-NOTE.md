# Load Testing - Future Stages Note

## Status: Blocked (No API Gateway)

The Gold API layer currently consists of **6 frozen parquet files** with no deployed API gateway. Load testing requires a running backend to measure真实 performance.

## When API Gateway is Deployed

### Prerequisites
- FastAPI/Express API gateway serving Gold-layer data
- GraphQL endpoints for all 6 marts (dim_title, dim_person, fact_title_principal, fact_performance, fact_episode, fact_title_rating)

### Test Plan

**Target Metrics:**
- 100 concurrent users
- p95 response time < 500ms
- Error rate < 1%
- Throughput > 50 req/s

**Critical Paths to Load Test:**
1. Homepage (`GET /graphql` - trending, featured, top rated)
2. Title Detail (`GET /graphql?tconst=...`)
3. Person Detail (`GET /graphql?nconst=...`)
4. Search (`GET /graphql?q=...`)
5. Browse with filters (`GET /graphql?type=...&genre=...`)

**Recommended Tools:**
- k6 (Grafana) - scriptable load testing
- Artillery - real-time monitoring
- Locust - Python-based distributed testing

**Test Configuration:**
```javascript
// k6 example
export const options = {
  stages: [
    { duration: '30s', target: 20 },   // ramp up
    { duration: '1m', target: 100 },    // sustained load
    { duration: '30s', target: 0 },     // ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'],
    http_req_failed: ['rate<0.01'],
  },
};
```

**Monitoring Points:**
- Frontend: Lighthouse CI, Core Web Vitals
- Backend: Database query times, connection pool usage
- Infrastructure: CPU, memory, network I/O

## Current Frontend Performance (Lighthouse)

| Metric | Score | Target | Status |
|---|---|---|---|
| Performance | 84 | >90 | Close |
| Accessibility | 100 | >95 | ✅ |
| Best Practices | 100 | >90 | ✅ |
| SEO | 100 | >90 | ✅ |

**Performance Notes:**
- Score of 84 is expected for a placeholder homepage with no real data
- Once real API calls are connected, the unused JavaScript audit will improve
- The `vendor` chunk (44KB gzip) will be justified when queries are active
