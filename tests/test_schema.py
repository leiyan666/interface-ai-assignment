from computer_use.executor import substitute
from computer_use.recorder import compile_lookup_capability
from computer_use.schema import Capability


def test_capability_round_trip_and_parameterization() -> None:
    trajectory = [
        {"action": {"action_type": "type", "target": {"role": "textbox", "name": "Member Number"}, "value": "10001", "reason": "fill"}, "result": {"ok": True}},
        {"action": {"action_type": "click", "target": {"role": "button", "name": "Search"}, "reason": "submit"}, "result": {"ok": True}},
        {"action": {"action_type": "extract", "target": {"near_text": "Savings Account"}, "reason": "read balance"}, "result": {"ok": True, "value": "$4250.32"}},
    ]
    capability = compile_lookup_capability("http://127.0.0.1:8000/", trajectory)
    restored = Capability.model_validate_json(capability.model_dump_json())
    assert restored.schema_version == "1.0"
    assert restored.steps[0].value == "{{member_id}}"
    assert restored.inputs[0].name == "member_id"
    assert [step.action for step in restored.steps] == ["type", "click", "extract"]


def test_parameter_substitution_is_explicit() -> None:
    assert substitute("member={{member_id}}", {"member_id": "10002"}) == "member=10002"
