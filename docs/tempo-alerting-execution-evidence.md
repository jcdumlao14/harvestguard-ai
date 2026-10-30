# Tempo and Alertmanager Integration Evidence

Date: 2026-10-30
Backup: C:\Users\kambar\harvestguard-ai\backups\tempo-alerting-20261030-173448

## Verified configuration

- Tempo Compose service: configured
- Dedicated tempo_data volume: configured
- API OTLP/HTTP exporter endpoint: configured
- Grafana Tempo datasource UID: tempo
- Authenticated Alertmanager webhook: configured
- Local responder token: stored in ignored files
- Automatic remediation: disabled

## Runtime verification

- Tempo readiness: PASS
- API readiness: PASS
- Alertmanager readiness: PASS
- Grafana Tempo datasource: PASS
- Tempo trace search: PASS
- Trace result count: 
- Synthetic alert submission: PASS
- Authenticated webhook delivery: PASS
- API webhook response: HTTP 200
- On-call incident recorded: PASS
- Automatic remediation: DISABLED
- PostgreSQL restart: NOT PERFORMED
- Database volume deletion: NOT PERFORMED
- Git commit/push: NOT PERFORMED

The synthetic alert used the allowlisted HarvestGuardHighApiLatency name.
No production remediation was triggered.