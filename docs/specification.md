# Product Specification — HarvestGuard AI

Version: 1.0-draft
Status: Proposed; review before implementation.

## 1. Problem

Small restaurants, cafes, and other food businesses need a simple way to
manage perishable stock, identify expiry and low-stock risks, and understand
food waste. They also need confidence that inventory operations remain usable.

## 2. Users

- Owner: reviews inventory and waste trends.
- Inventory staff: maintains items and stock movements.
- Kitchen staff: records discarded food and reasons.
- Operator: reviews service incidents and responder actions.

Authentication and role permissions must be specified before exposing
business records to multiple users.

## 3. Product scope

### Inventory
Create, view, update, and deactivate inventory items. Track units,
quantities, reorder thresholds, and expiry dates where applicable.

### Stock movements
Record receipts, usage, adjustments, and other explicitly supported
movements. Validate quantities and prevent invalid state transitions.

### Waste tracking
Record an item, quantity, unit, timestamp, reason, and cost basis.
Keep historical records when an item is deactivated.

### Dashboard
Calculate low-stock counts, upcoming expiry indicators, and waste totals
from persisted records. Define time windows and units consistently.
Clearly label synthetic demonstration data.

### Recommendations
Use deterministic, explainable rules for initial expiry and stock
recommendations. Recommendations are advisory and do not silently change stock.

### Reliability center
Show incidents, alert state, relevant trace identifiers, remediation actions,
verification results, and an audit trail.

## 4. Primary user journey

1. A user opens the inventory dashboard.
2. The user creates or updates an inventory item.
3. The API validates the request and persists it in PostgreSQL.
4. The UI displays the persisted result.
5. Metrics, structured logs, and traces record the request with a shared
   trace ID, without exposing secrets or unnecessary personal information.
6. A controlled fault causes a user-impact alert.
7. The responder gathers evidence and selects an allowlisted action.
8. The system independently verifies whether the affected journey recovered.
9. The incident and remediation outcome are stored for review.

## 5. Non-functional requirements

- Deterministic tests and reproducible local setup.
- Input validation and explicit API error responses.
- Database migrations and documented recovery procedures.
- Least-privilege access and secret management.
- Health checks and bounded request timeouts.
- Traceable releases and rollback instructions.
- No arbitrary autonomous production commands.
- English documentation.

## 6. Out of scope for the first version

- Automatic purchasing or supplier payments.
- Unverified AI-generated inventory changes.
- Predictive machine learning requiring a large real-world dataset.
- Autonomous destructive database repair.
- Claims of measured waste reduction without an appropriate evaluation.

## 7. Acceptance

The implementation is accepted only when the corresponding criteria in
`acceptance-criteria.md` have evidence from tests, deployment checks, or a
repeatable demonstration.
