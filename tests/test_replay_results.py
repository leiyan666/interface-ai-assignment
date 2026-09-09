from computer_use.schema import RunResult, RunStatus


def test_business_outcome_is_distinct_from_hard_failure() -> None:
    business = RunResult(status=RunStatus.BUSINESS_OUTCOME, business_outcome="MEMBER_NOT_FOUND")
    failure = RunResult(status=RunStatus.HARD_FAILURE, message="timeout")
    assert business.status != failure.status
    assert business.business_outcome == "MEMBER_NOT_FOUND"
