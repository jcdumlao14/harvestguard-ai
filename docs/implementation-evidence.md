# HarvestGuard implementation evidence register

This register is not proof of completion. For each criterion, record actual
GitHub Issue/PR/Actions URLs, commit SHA, commands, test results, manual checks,
security/migration considerations, and remaining work.

| Criterion | Current state | Evidence to attach |
|---|---|---|
| HG-17 public tracker | Verify/create public Issues | Issue URLs and linked PRs |
| HG-18 modular context | Existing docs; verify links | AGENTS.md review |
| HG-07 Compose | Files scaffolded by bootstrap; run required | clean-start log |
| HG-09 PR CI | Workflow scaffolded | successful Actions run |
| HG-10 CD | Provider integration still required | dev deploy + protected production approval |
| HG-12/13 observability | Metrics/log scaffolding; traces/UI validation required | dashboard and correlated trace |
| HG-14 alert | Rule scaffolded; trigger drill required | firing alert evidence |
| HG-15/16 responder | Policy scaffolded; integration and recovery drill required | audit and verification evidence |

Never mark a row complete without its evidence.


## Live Alert Delivery and Cleanup Verification

**Status: PASS — verified through the live test and subsequent read-only diagnostics.**

- Verification date: October 30, 2026.
- Synthetic test run ID: `hg-live-20261030070721`.
- Original alert-rule backup: `backups/alerts-live-e2e-hg-live-20261030070721.bak`.
- Original backup SHA256 was verified against the restored production rules file.
- Temporary synthetic Prometheus rule passed `promtool check rules`.
- Prometheus successfully reloaded the temporary rule using SIGHUP.
- Synthetic alert lifecycle was observed in Prometheus: PENDING, then FIRING.
- Alertmanager received the matching alert name and run ID.
- Confirmed receiver: `local-review-only`.
- Prometheus subsequently reported no matching synthetic alert.
- Alertmanager subsequently returned no matching synthetic alert in its active alerts, inactive alerts, or alert groups.
- Original four production rules were restored and verified:
  - `HarvestGuardApiUnavailable`
  - `HarvestGuardPrometheusTargetMissing`
  - `HarvestGuardHighHttp5xxRate`
  - `HarvestGuardHighApiLatency`
- Prometheus and Alertmanager readiness checks passed after restoration.

**Acceptance result:** PASS — live Prometheus-to-Alertmanager delivery, firing, clearing, and cleanup verified.

**Evidence qualification:** The original E2E script ended with 10/12 checks verified because its clearing timeout occurred before cleanup completed. Subsequent read-only diagnostics confirmed that Prometheus cleared the alert and Alertmanager no longer listed it. This is a combined result from the original test and follow-up verification, not a retroactive change to the original script output.

**Notification limitation:** The verified receiver is local-only. External email, Telegram, or webhook delivery was not tested.

**Safety:** No application or database records were intentionally modified, and no Docker containers were restarted during this test.
