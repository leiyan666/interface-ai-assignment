from decimal import Decimal
import json

import pytest

from computer_use.discovery import discover
from computer_use.schema import Action, ActionResult, Observation, Target
from computer_use.success import verified_savings_balance


def extraction(**changes):
    return Action(action_type="extract", target=Target(near_text="Savings Account"),
                  output_name="savings_balance", reason="read").model_copy(update=changes)


@pytest.mark.parametrize("value,expected", [("$4,250.32", Decimal("4250.32")), ("$0.00", Decimal("0"))])
def test_valid_money(value, expected):
    assert verified_savings_balance(extraction(), ActionResult(ok=True, value=value),
                                    Observation(url="local", title="", visible_text="Savings Account")) == expected


@pytest.mark.parametrize("value", ["Alice Chen", "10001", "", "$4,25.32", "NaN", "Savings Account $4250.32"])
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


def test_premature_finish_does_not_write_artifact(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    class Surface:
        def __init__(self, *args, **kwargs): pass
        def start(self): pass
        def close(self): pass
        def current_url(self): return "http://127.0.0.1:8000/"
        def observe(self): return Observation(url=self.current_url(), title="", visible_text="Savings Account")
        def execute(self, action): return ActionResult(ok=True, value="Alice Chen")

    class Client:
        def decide(self, goal, observation, history):
            return extraction() if not history else Action(action_type="finish", reason="done")

    monkeypatch.setattr("computer_use.discovery.PlaywrightSurface", Surface)
    with pytest.raises(RuntimeError, match="without a verified savings balance"):
        discover("return savings balance", "http://127.0.0.1:8000/", Client(), max_steps=2)
    assert not (tmp_path / "artifacts/lookup_savings_balance.json").exists()
    events = [json.loads(line) for line in (tmp_path / "evidence/discovery_success.jsonl").read_text().splitlines()]
    assert sum(event["event"] == "success_checkpoint_rejected" for event in events) == 2
