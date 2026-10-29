# Rollback Plan

## Application rollback
1. Stop promotion if health checks or smoke tests fail.
2. Identify the previous known-good immutable release.
3. Redeploy it using the hosting platform's supported mechanism.
4. Run health checks and a representative user-journey test.
5. Confirm user-impact metrics recover.
6. Record the incident, release identifiers, and outcome.

## Database changes
Application rollback does not automatically reverse a schema migration.
Prefer backward-compatible expand-and-contract migrations. Destructive schema
changes require a separate reviewed recovery plan and a verified backup.

## Responder rollback
Disable automatic remediation using the documented operator control if the
agent behaves unexpectedly. Preserve incident evidence and escalate.

## Required drill
Perform a controlled failed-release or simulated deployment drill in a
non-production environment. Record the exact steps and observed results.
Never claim rollback has been tested until the drill succeeds.
