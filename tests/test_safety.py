import pytest

from computer_use.safety import SafetyViolation, validate_action, action_risk
from computer_use.schema import Action, SafetyPolicy, RiskLevel, Target


def test_local_navigation_is_allowed() -> None:
    validate_action(Action(action_type="navigate", value="http://127.0.0.1:8000/", reason="start"), SafetyPolicy())


def test_external_navigation_is_blocked() -> None:
    with pytest.raises(SafetyViolation):
        validate_action(Action(action_type="navigate", value="https://example.com", reason="leave app"), SafetyPolicy())


@pytest.mark.parametrize("name,risk", [
    ("Delete Account", RiskLevel.IRREVERSIBLE),
    ("Search", RiskLevel.READ),
    ("Unknown operation", RiskLevel.SAFE_WRITE),
])
def test_target_sets_minimum_risk(name, risk):
    assert action_risk(Action(action_type="click", target=Target(name=name), reason="test")) == risk


def test_declared_risk_cannot_be_downgraded_by_read_target():
    action = Action(action_type="click", target=Target(name="Search"), risk=RiskLevel.IRREVERSIBLE, reason="test")
    with pytest.raises(SafetyViolation, match="irreversible"):
        validate_action(action, SafetyPolicy())


def test_policy_can_mark_arbitrary_target_high_risk():
    action = Action(action_type="click", target=Target(name="Finalize"), reason="test")
    with pytest.raises(SafetyViolation):
        validate_action(action, SafetyPolicy(target_risks={"Finalize": RiskLevel.IRREVERSIBLE}))


def test_compiler_preserves_declared_risk():
    from computer_use.recorder import compile_lookup_capability
    action = Action(action_type="click", target=Target(name="Search"), risk=RiskLevel.IRREVERSIBLE, reason="test")
    capability = compile_lookup_capability("http://127.0.0.1:8000/", [{"action": action.model_dump(), "result": {"ok": True}}])
    assert capability.steps[0].risk == RiskLevel.IRREVERSIBLE


def test_replay_enforces_artifact_risk_before_execution(monkeypatch, tmp_path):
    from pathlib import Path
    from computer_use.schema import Capability
    from replay import replay

    capability = Capability.model_validate_json(Path("artifacts/lookup_savings_balance.json").read_text())
    capability.steps[0].risk = RiskLevel.IRREVERSIBLE
    artifact = tmp_path / "capability.json"
    artifact.write_text(capability.model_dump_json())

    class Surface:
        def __init__(self, *args, **kwargs): pass
        def start(self): pass
        def close(self): pass
        def current_url(self): return "http://127.0.0.1:8000/"
        def execute(self, action): pytest.fail("Blocked action must never execute")
        def screenshot(self, path): return path

    monkeypatch.setattr("replay.PlaywrightSurface", Surface)
    monkeypatch.chdir(tmp_path)
    result = replay(str(artifact), {"member_id": "10002"}, headless=True)
    assert result.status.value == "hard_failure"
    assert "risk=irreversible" in result.message
    assert result.failed_step_id == capability.steps[0].id
