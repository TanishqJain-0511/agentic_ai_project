import os
import yaml
from typing import List

from backend.app.schemas.policy import PolicyCheckRequest, PolicyCheckResponse, PolicyViolation

_RULES_PATH = os.path.join(os.path.dirname(__file__), "..", "policies", "policy_rules.yaml")

# Load rules once at module import time — no per-request I/O.
with open(_RULES_PATH, "r") as _f:
    _RULES: List[dict] = yaml.safe_load(_f)["rules"]


def check_policy(data: PolicyCheckRequest) -> PolicyCheckResponse:
    allocation = {
        "equity_pct": data.equity_pct,
        "debt_pct": data.debt_pct,
        "gold_pct": data.gold_pct,
    }
    violations: List[PolicyViolation] = []

    for rule in _RULES:
        if not _rule_applies(rule, data):
            continue

        asset = rule["asset"]
        actual = allocation[asset]
        limit = float(rule["limit"])
        rule_type = rule["rule_type"]

        breached = (rule_type == "max" and actual > limit) or \
                   (rule_type == "min" and actual < limit)

        if breached:
            violations.append(PolicyViolation(
                rule_id=rule["id"],
                description=rule["description"],
                asset=asset,
                rule_type=rule_type,
                limit=limit,
                actual=actual,
            ))

    # Internal sanity check: allocations must sum to ~100
    total = data.equity_pct + data.debt_pct + data.gold_pct
    if abs(total - 100.0) > 0.5:
        violations.append(PolicyViolation(
            rule_id="total_allocation_check",
            description=f"equity + debt + gold must equal 100% (got {total:.1f}%)",
            asset="total",
            rule_type="exact",
            limit=100.0,
            actual=total,
        ))

    return PolicyCheckResponse(
        passed=len(violations) == 0,
        violations_count=len(violations),
        violations=violations,
    )


def _rule_applies(rule: dict, data: PolicyCheckRequest) -> bool:
    # Tier filter
    tiers = rule.get("applies_to_tiers")
    if tiers and data.risk_tier not in tiers:
        return False

    # Horizon filter
    horizon_lt = rule.get("applies_when_horizon_lt")
    if horizon_lt is not None and data.goal_horizon_years >= horizon_lt:
        return False

    return True
