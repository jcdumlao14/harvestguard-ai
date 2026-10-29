# Testing Strategy

## Unit tests
Test validation, stock calculations, expiry rules, waste cost calculations,
recommendation rules, incident policies, and remediation eligibility.

## Frontend tests
Test inventory forms, validation messages, dashboard loading/error states,
and user-visible confirmation of persisted changes.

## API integration tests
Use a disposable test database. Exercise request validation, persistence,
transactions, error handling, and migrations.

## End-to-end checks
Verify a user can create an item, retrieve it after a new request, record waste,
and see updated dashboard values.

## Responder tests
Test valid and invalid alerts, action allowlists, idempotency, timeout behavior,
failed verification, escalation, and audit records.

## Commands
The exact test commands will be added after dependency and project files exist.
CI must run the documented test suite from a clean checkout.

Never point tests at production data or rely on external paid services for
ordinary unit tests.
