"""Action and navigation policy enforcement."""

from __future__ import annotations

from urllib.parse import urlparse

from .schema import Action, RiskLevel, SafetyPolicy


class SafetyViolation(ValueError):
    pass


def action_risk(action: Action) -> RiskLevel:
    return RiskLevel.SAFE_WRITE if action.action_type == "type" else RiskLevel.READ


def validate_action(action: Action, policy: SafetyPolicy, current_url: str = "") -> None:
    if action.action_type not in policy.allowed_actions:
        raise SafetyViolation(f"Action is not allowed: {action.action_type}")
    if action_risk(action) in policy.require_human_for_risk:
        raise SafetyViolation(f"Action requires human confirmation: {action.action_type}")
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
