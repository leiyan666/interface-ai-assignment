import pytest

from computer_use.safety import SafetyViolation, validate_action
from computer_use.schema import Action, SafetyPolicy


def test_local_navigation_is_allowed() -> None:
    validate_action(Action(action_type="navigate", value="http://127.0.0.1:8000/", reason="start"), SafetyPolicy())


def test_external_navigation_is_blocked() -> None:
    with pytest.raises(SafetyViolation):
        validate_action(Action(action_type="navigate", value="https://example.com", reason="leave app"), SafetyPolicy())
