from copy import deepcopy

import pytest

from computer_use.recorder import compile_lookup_capability


@pytest.fixture
def trajectory():
    return [
        {"action": {"action_type": "type", "target": {"name": "Member Number", "frame_hint": "Custom frame"}, "value": "10001"}, "result": {"ok": True}},
        {"action": {"action_type": "click", "target": {"role": "button", "name": "Find member", "fallbacks": [{"strategy": "text", "value": "Find member"}]}}, "result": {"ok": True}},
        {"action": {"action_type": "extract", "target": {"near_text": "Savings Account"}}, "result": {"ok": True, "value": "$4250.32"}},
    ]


def test_steps_come_from_trajectory_with_targets_preserved(trajectory):
    trajectory.insert(2, {"action": {"action_type": "click", "target": {"text": "Account details"}}, "result": {"ok": True}})
    original = deepcopy(trajectory)
    capability = compile_lookup_capability("http://127.0.0.1:8000/", trajectory)
    assert [s.action for s in capability.steps] == ["type", "click", "click", "extract"]
    for step, entry in zip(capability.steps, trajectory):
        for key, value in entry["action"]["target"].items():
            assert step.target.model_dump()[key] == value
    assert capability.steps[0].value == "{{member_id}}"
    assert capability.steps[0].checkpoint.value == "{{member_id}}"
    assert capability.steps[-1].output_name == "savings_balance"
    assert all(step.output_name is None for step in capability.steps[:-1])
    assert trajectory == original


@pytest.mark.parametrize("indices", [[], [0], [1, 2], [0, 2], [0, 1], [2, 0, 1]])
def test_incomplete_or_out_of_order_workflow_rejected(trajectory, indices):
    with pytest.raises(ValueError):
        compile_lookup_capability("local", [trajectory[i] for i in indices])


@pytest.mark.parametrize("result", [{}, {"ok": False}, {"ok": "true"}])
def test_required_step_without_explicit_success_rejected(trajectory, result):
    trajectory[1]["result"] = result
    with pytest.raises(ValueError):
        compile_lookup_capability("local", trajectory)


@pytest.mark.parametrize("value", [None, "", "Alice Chen", "NaN"])
def test_invalid_extraction_rejected(trajectory, value):
    trajectory[-1]["result"]["value"] = value
    with pytest.raises(ValueError, match="monetary"):
        compile_lookup_capability("local", trajectory)


def test_failed_actions_ignored_without_inventing_steps(trajectory):
    failed = deepcopy(trajectory[0])
    failed["result"]["ok"] = False
    failed["action"]["value"] = "99999"
    trajectory.insert(0, failed)
    capability = compile_lookup_capability("local", trajectory)
    assert [s.action for s in capability.steps] == ["type", "click", "extract"]


def test_targetless_action_rejected(trajectory):
    trajectory[1]["action"]["target"] = None
    with pytest.raises(ValueError, match="target"):
        compile_lookup_capability("local", trajectory)
