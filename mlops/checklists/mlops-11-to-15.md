# MLOPS.11–15 — Security, Compliance, Documentation, Disaster Recovery, Continuous Improvement

## MLOPS.11 — Security
- [ ] No secrets in Docker images (use environment variables / secrets manager)
- [ ] All containers run as non-root user
- [ ] TLS 1.3 configured for public endpoints
- [ ] Trivy scan passes in CI (no CRITICAL, no HIGH)
- [ ] Network policies restrict inter-service communication

## MLOPS.12 — Compliance
- [ ] Data retention policies documented
- [ ] PII handling documented (user passwords, emails)
- [ ] RBAC configured for K8s and cloud resources
- [ ] Audit logging enabled (who accessed what and when)

## MLOPS.13 — Documentation
- [ ] `mlops/README.md` written and up-to-date
- [ ] `mlops/docs/implementation-plan.md` covers all 12 sections
- [ ] Runbooks exist for all DR scenarios
- [ ] Architecture diagram included
- [ ] Integration map documents all service connections

## MLOPS.14 — Disaster Recovery
- [ ] Backup strategy documented and automated
- [ ] Point-in-time recovery tested this quarter
- [ ] Model rollback tested this quarter
- [ ] Quarterly drills scheduled and results documented
- [ ] RPO/RTO targets documented and met

## MLOPS.15 — Continuous Improvement
- [ ] Quarterly review process documented
- [ ] Post-mortem template available in `runbooks/`
- [ ] Checklists reviewed and updated within last 90 days
- [ ] Action items from previous quarter resolved
- [ ] Feedback loop to DS/DE/SWE teams established
