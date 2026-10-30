"""Deterministic responder authorization. No shell or SQL execution exists here."""
from dataclasses import dataclass
from enum import StrEnum

class Risk(StrEnum):
    LOW = "low"
    HIGH = "high"

@dataclass(frozen=True)
class RecoveryAction:
    name: str
    risk: Risk
    requires_production_approval: bool

ALLOWLIST: dict[str, RecoveryAction] = {
    "restart_demo_api": RecoveryAction("restart_demo_api", Risk.LOW, True),
    "clear_demo_cache": RecoveryAction("clear_demo_cache", Risk.HIGH, True),
}

@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str
    action: RecoveryAction | None = None

def authorize_action(action_name: str, *, evidence_complete: bool,
                     production: bool, human_approved: bool) -> Decision:
    if not evidence_complete:
        return Decision(False, "Insufficient diagnostic evidence")
    action = ALLOWLIST.get(action_name)
    if action is None:
        return Decision(False, "Action is not allowlisted")
    if action.risk == Risk.HIGH and not human_approved:
        return Decision(False, "High-risk action requires human approval")
    if production and action.requires_production_approval and not human_approved:
        return Decision(False, "Production action requires human approval")
    return Decision(True, "Authorized by deterministic policy", action)
