from computer_use.executor import substitute
from computer_use.recorder import compile_lookup_capability
from computer_use.schema import Capability


def test_capability_round_trip_and_parameterization() -> None:
    capability = compile_lookup_capability("http://127.0.0.1:8000/", [])
    restored = Capability.model_validate_json(capability.model_dump_json())
    assert restored.schema_version == "1.0"
    assert restored.steps[0].value == "{{member_id}}"
    assert restored.inputs[0].name == "member_id"


def test_parameter_substitution_is_explicit() -> None:
    assert substitute("member={{member_id}}", {"member_id": "10002"}) == "member=10002"
