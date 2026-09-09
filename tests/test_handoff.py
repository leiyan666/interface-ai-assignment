import json

import pytest

from computer_use.handoff import handoff
from computer_use.logging_utils import JsonlLogger
from computer_use.schema import Observation


class Surface:
    def __init__(self):
        self.text = "Operator confirmation required"
        self.screenshots = []

    def observe(self):
        return Observation(url="http://127.0.0.1:8000/", title="Mock", visible_text=self.text)

    def screenshot(self, path):
        self.screenshots.append((path, self.text))
        return path

    def start_human_tracking(self, sink): self.sink = sink
    def stop_human_tracking(self): self.sink = None
    def pump_events(self): pass


def events(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_browser_events_and_before_after_states_are_redacted(monkeypatch, tmp_path):
    monkeypatch.delenv("CI_AUTO_HANDOFF", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "test-environment-secret")
    surface = Surface()

    def answer(prompt):
        surface.text = "Savings Account $8921.10"
        surface.sink({"kind": "click", "name": "password=hidden sk-example-token test-environment-secret"})
        return ""

    monkeypatch.setattr("builtins.input", answer)
    path = tmp_path / "handoff.jsonl"
    handoff(surface, JsonlLogger(path, "test", "replay"), str(tmp_path / "before.png"))
    records = events(path)
    assert [record["event"] for record in records] == [
        "handoff_requested", "control_transferred_to_human",
        "human_action",
        "human_intervention_completed", "control_returned_to_automation",
    ]
    assert len({record["handoff_id"] for record in records}) == 1
    assert records[0]["observation"]["visible_text"] == "Operator confirmation required"
    completed = records[3]
    assert completed["observation"]["visible_text"] == "Savings Account $8921.10"
    assert completed["summary_source"] == "browser_events"
    assert completed["simulated"] is False
    assert completed["action_count"] == 1
    assert surface.sink is None
    assert len(surface.screenshots) == 2
    assert surface.screenshots[0][0] != surface.screenshots[1][0]
    for secret in ("hidden", "sk-example-token", "test-environment-secret"):
        assert secret not in path.read_text()


def test_cancel_does_not_claim_completion(monkeypatch, tmp_path):
    monkeypatch.delenv("CI_AUTO_HANDOFF", raising=False)

    def cancel(prompt):
        raise EOFError

    monkeypatch.setattr("builtins.input", cancel)
    path = tmp_path / "handoff.jsonl"
    with pytest.raises(RuntimeError, match="cancelled"):
        handoff(Surface(), JsonlLogger(path, "test", "replay"), "before.png")
    assert events(path)[-1]["event"] == "handoff_cancelled"
    assert not any(record["event"] == "human_intervention_completed" for record in events(path))


def test_ci_bypass_is_explicit_simulation(monkeypatch, tmp_path):
    monkeypatch.setenv("CI_AUTO_HANDOFF", "1")
    path = tmp_path / "handoff.jsonl"
    handoff(Surface(), JsonlLogger(path, "test", "replay"), "before.png")
    completed = events(path)[2]
    assert completed["summary_source"] == "simulation"
    assert completed["simulated"] is True
    assert "no human actions recorded" in completed["summary"]
