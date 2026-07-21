# Quarterly MLOps Drill Runbook

**Purpose:** Regularly exercise DR procedures to ensure readiness.

**Schedule:** First Saturday of each quarter, 10:00 AM UTC
**Participants:** DE, DS, SWE leads (minimum 1 from each team)
**Duration:** 30-60 minutes

---

## Drill Rotation

| Quarter | Scenario                         | Lead Team |
|---------|----------------------------------|-----------|
| Q1      | Full database restore from backup| DE        |
| Q2      | Model rollback + canary deploy   | DS        |
| Q3      | Kubernetes node failure simulation| SWE      |
| Q4      | Data corruption recovery         | DE        |

## Before the Drill

```markdown
## [ ] Preparation Checklist

- [ ] Drill scenario selected and reviewed
- [ ] All participants confirmed
- [ ] Backup verified as restorable
- [ ] Rollback model version tagged
- [ ] Monitoring dashboards accessible
- [ ] Communication channel (Slack) open
- [ ] Timer ready
```

## During the Drill

1. Announce drill start in Slack `#mlops-drills`
2. Run scenario (inject failure / simulate condition)
3. Time each step of the recovery procedure
4. Document any unexpected behavior
5. Announce drill end once services healthy

## After the Drill

```markdown
## Post-Mortem Template

**Date:** YYYY-MM-DD
**Scenario:** [database restore / model rollback / node failure / data corruption]
**Participants:** [names]
**Duration:** [minutes]

### Timeline
- HH:MM — Drill started
- HH:MM — First observation
- HH:MM — Recovery action taken
- HH:MM — Services healthy

### Observations
- What went well:
- What went wrong:
- Unexpected issues:

### Metrics
- Time to detect: [minutes]
- Time to recover (RTO): [minutes]
- Data loss (RPO): [minutes]

### Action Items
- [ ] Owner: Description
```

## Quarterly Review Meeting

- Review all action items from previous quarter
- Update runbooks if procedures changed
- Verify monitoring alert thresholds
- Review MLOPS criteria compliance
- Plan next quarter's drill scenario
