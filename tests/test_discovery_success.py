from decimal import Decimal
import json

import pytest

from computer_use.discovery import discover
from computer_use.schema import Action, ActionResult, Observation, Target
from computer_use.success import verified_savings_balance


def extraction(**changes):
    return Action(action_type="extract", target=Target(near_text="Savings Account"),
                  output_name="savings_balance", reason="read").model_copy(update=changes)


@pytest.mark.parametrize("value,expected", [("$4,250.32", Decimal("4250.32")), ("$0.00", Decimal("0")), (0, Decimal("0")), (4250.32, Decimal("4250.32")), ("4250", Decimal("4250"))])
def test_valid_money(value, expected):
    assert verified_savings_balance(extraction(), ActionResult(ok=True, value=value),
                                    Observation(url="local", title="", visible_text="Savings Account")) == expected


@pytest.mark.parametrize("value", ["Alice Chen", "", "$4,25.32", "NaN", "Savings Account $4250.32", None, True, float("inf"), float("nan")])
def test_invalid_value(value):
    assert verified_savings_balance(extraction(), ActionResult(ok=True, value=value),
                                    Observation(url="local", title="", visible_text="Savings Account")) is None


@pytest.mark.parametrize("changes,text,ok", [
    ({"output_name": "Member Savings Balance"}, "Savings Account", True),
    ({"target": Target(near_text="Checking Account")}, "Savings Account", True),
    ({}, "No savings account", True),
    ({}, "Savings Account", False),
])
def test_contract_and_page_required(changes, text, ok):
    assert verified_savings_balance(extraction(**changes), ActionResult(ok=ok, value="$4250.32"),
                                    Observation(url="local", title="", visible_text=text)) is None


@pytest.mark.parametrize("value,output_name", [("Alice Chen", "savings_balance"), ("$4250.32", "member_name"), ("", "savings_balance")])
def test_premature_finish_does_not_write_artifact(monkeypatch, tmp_path, value, output_name):
    monkeypatch.chdir(tmp_path)

    class Surface:
        def __init__(self, *args, **kwargs): pass
        def start(self): pass
        def close(self): pass
        def current_url(self): return "http://127.0.0.1:8000/"
        def observe(self): return Observation(url=self.current_url(), title="", visible_text="Savings Account")
        def execute(self, action): return ActionResult(ok=True, value=value)

    class Client:
        def decide(self, goal, observation, history):
            return extraction(output_name=output_name) if not history else Action(action_type="finish", reason="done")

    monkeypatch.setattr("computer_use.discovery.PlaywrightSurface", Surface)
    with pytest.raises(RuntimeError, match="without a verified savings balance"):
        discover("return savings balance", "http://127.0.0.1:8000/", Client(), max_steps=2)
    assert not (tmp_path / "artifacts/lookup_savings_balance.json").exists()
    events = [json.loads(line) for line in (tmp_path / "evidence/discovery_success.jsonl").read_text().splitlines()]
    assert sum(event["event"] == "success_checkpoint_rejected" for event in events) == 2


@pytest.mark.parametrize("value", ["$4250.32", 0])
def test_verified_workflow_writes_compiled_artifact(monkeypatch, tmp_path, value):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("computer_use.discovery.time.sleep", lambda _: None)
    actions = iter([
        Action(action_type="type", target=Target(name="Member Number"), value="10001", reason="fill"),
        Action(action_type="click", target=Target(name="Search"), reason="search"),
        extraction(),
    ])

    class Surface:
        def __init__(self, *args, **kwargs): pass
        def start(self): pass
        def close(self): pass
        def current_url(self): return "http://127.0.0.1:8000/"
        def observe(self): return Observation(url=self.current_url(), title="", visible_text="Savings Account")
        def execute(self, action): return ActionResult(ok=True, value=value if action.action_type == "extract" else None)

    class Client:
        def decide(self, goal, observation, history): return next(actions)

    monkeypatch.setattr("computer_use.discovery.PlaywrightSurface", Surface)
    artifact = discover("return savings balance", "http://127.0.0.1:8000/", Client(), max_steps=3)
    data = json.loads(artifact.read_text())
    assert [s["action"] for s in data["steps"]] == ["type", "click", "extract"]
    assert data["steps"][0]["value"] == "{{member_id}}"
    assert data["steps"][-1]["output_name"] == "savings_balance"
