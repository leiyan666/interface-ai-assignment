"""Action and navigation policy enforcement."""

from __future__ import annotations

from urllib.parse import urlparse
import re

from .schema import Action, RiskLevel, SafetyPolicy


class SafetyViolation(ValueError):
    pass


def action_risk(action: Action, policy: SafetyPolicy | None = None) -> RiskLevel:
    """Declarations and semantic policy can raise, but never lower, inferred risk."""
    levels = [RiskLevel.READ, RiskLevel.SAFE_WRITE, RiskLevel.IRREVERSIBLE]
    inferred = RiskLevel.SAFE_WRITE if action.action_type in {"type", "click"} else RiskLevel.READ
    names = [] if not action.target else [
        value.strip().casefold() for value in
        (action.target.name, action.target.text, action.target.near_text) if value
    ]
    if action.action_type == "click":
        if names and all(name == "search" for name in names):
            inferred = RiskLevel.READ
        if any(re.search(r"\b(delete|remove|transfer|withdraw|pay|send|close account)\b", name) for name in names):
            inferred = RiskLevel.IRREVERSIBLE
    risks = [action.risk, inferred]
    if policy:
        risks.extend(risk for name, risk in policy.target_risks.items() if name.strip().casefold() in names)
    return max(risks, key=levels.index)


def validate_action(action: Action, policy: SafetyPolicy, current_url: str = "") -> None:
    if action.action_type not in policy.allowed_actions:
        raise SafetyViolation(f"Action is not allowed: {action.action_type}")
    risk = action_risk(action, policy)
    if risk in policy.require_human_for_risk:
        raise SafetyViolation(f"Action blocked pending human authorization: {action.action_type}, risk={risk.value}")
    if action.action_type == "navigate" and action.value:
        parsed = urlparse(action.value)
        if parsed.hostname not in policy.allowed_hosts:
            raise SafetyViolation(f"Host is not allowlisted: {parsed.hostname}")
        if any(route in parsed.path for route in policy.blocked_routes):
            raise SafetyViolation(f"Route is blocked: {parsed.path}")
    if current_url:
        host = urlparse(current_url).hostname
        if host and host not in policy.allowed_hosts:
            raise SafetyViolation(f"Current host is not allowlisted: {host}")
