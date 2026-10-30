# Acceptance Criteria

These are proposed requirements. The team must review them and create linked
GitHub Issues before implementation. Criteria are not considered complete
because this document exists.

| ID | Acceptance criterion | Required evidence |
|---|---|---|
| HG-01 | Inventory items can be created, read, updated, and deactivated; data persists in PostgreSQL. | API integration test and UI demonstration |
| HG-02 | Stock movements validate quantity and preserve movement history. | Unit and integration tests |
| HG-03 | Waste records capture quantity, reason, time, and defined cost basis. | Validation tests and persisted record |
| HG-04 | Dashboard metrics derive from stored data and have documented units and time windows. | Calculation tests and UI |
| HG-05 | Frontend and backend use a documented OpenAPI contract. | OpenAPI validation and frontend API tests |
| HG-06 | Unit, frontend, and integration tests run using documented commands and pass in CI. | CI run link and test report |
| HG-07 | Docker Compose starts the application and database with one command. | Clean-start demonstration |
| HG-08 | A public deployment or clear accessible demo supports the primary user journey. | Public URL and smoke-test evidence |
| HG-09 | Pull requests trigger automated quality checks and tests. | Successful GitHub Actions run |
| HG-10 | Development deployment is automated; production promotion requires approval. | Workflow configuration and deployment evidence |
| HG-11 | A documented rollback procedure restores a previous compatible release. | Controlled rollback drill |
| HG-12 | Primary user requests emit correlated metrics, structured logs, and traces. | Trace ID visible across signals |
| HG-13 | Telemetry is collected and viewable in a UI without secrets or unnecessary personal data. | Dashboard and telemetry privacy checks |
| HG-14 | A reproducible failure in a key user journey triggers an alert. | Alert rule and triggered-alert evidence |
| HG-15 | The responder agent investigates an alert and chooses only allowlisted actions. | Agent test and incident audit |
| HG-16 | The responder verifies recovery independently and records success or escalation. | Recovery drill, negative test, and audit record |
| HG-17 | Public Issues define acceptance criteria and link to implementation evidence. | Public issue and pull-request links |
| HG-18 | AGENTS.md links to modular docs and describes the actual agent workflow. | Documentation review |

## Definition of done

A criterion is done only when:
- Its implementation is merged or otherwise reproducibly available.
- Required automated tests pass.
- Relevant manual checks are recorded.
- Documentation matches actual behavior.
- Evidence is linked from the corresponding GitHub Issue.


## Observability: Live Alert Delivery and Cleanup

**Acceptance status: PASS**

Verified October 30, 2026, using live Prometheus and Alertmanager services.

| Acceptance requirement | Result |
|---|---|
| Prometheus loads the temporary synthetic alert rule | PASS |
| Alert transitions from pending to firing | PASS |
| Alertmanager receives the matching alert | PASS |
| Prometheus clears the synthetic alert | PASS |
| Alertmanager no longer lists the synthetic alert | PASS |
| Original four production rules restored | PASS |
| Prometheus and Alertmanager readiness verified | PASS |

**Test reference:** `hg-live-20261030070721`

**Evidence:** `docs/implementation-evidence.md`

**Limitation:** External email, Telegram, and webhook notification delivery are not included in this verification. The tested receiver was `local-review-only`.

This acceptance result applies to the live alert-delivery and cleanup capability. It does not imply that every HarvestGuard project acceptance criterion is complete.
