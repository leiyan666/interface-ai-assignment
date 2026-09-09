"""Goal-specific verification for the single savings lookup demo."""

import re
from decimal import Decimal

from .schema import Action, ActionResult, Observation


def verified_savings_balance(
    action: Action, result: ActionResult, observation: Observation,
) -> Decimal | None:
    """Accept a complete money value from a semantically identified savings target."""
    if action.action_type != "extract" or action.output_name != "savings_balance":
        return None
    if not result.ok or observation.dialog_present or not action.target:
        return None
    labels = (action.target.name, action.target.text, action.target.near_text)
    if not any(label and label.strip().rstrip(":").casefold() == "savings account" for label in labels):
        return None
    if not re.search(r"\bSavings Account\b", observation.visible_text, re.IGNORECASE):
        return None
    if any(outcome in observation.visible_text.casefold() for outcome in
           ("no savings account", "member not found", "permission denied")):
        return None
    if not isinstance(result.value, str):
        return None
    # Full match prevents accepting names, member numbers, or a whole table dump.
    value = result.value.strip()
    if not re.fullmatch(r"\$?(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)\.[0-9]{2}", value):
        return None
    return Decimal(value.removeprefix("$").replace(",", ""))
