import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from computer_use.recovery import execute_lookup_with_recovery, safe_lookup_submission
from computer_use.schema import Action, ActionResult, Observation, SafetyPolicy, Target


SEARCH = Action(action_type="click", target=Target(name="Search"), reason="lookup")
MEMBER = Action(action_type="type", target=Target(name="Member Number"), value="30000", reason="fill")


class Logger:
    def __init__(self): self.events = []
    def event(self, name, **fields): self.events.append((name, fields))


class Surface:
    def __init__(self, failures, timeout=False):
        self.failures = failures
        self.timeout = timeout
        self.submissions = 0
        self.refills = 0
        self.text = ""
    def current_url(self): return "http://127.0.0.1:8000/"
    def execute(self, action):
        if action.action_type == "type":
            assert action.value == "30000"
            self.refills += 1
        else:
            self.submissions += 1
            self.text = "temporarily busy" if self.submissions <= self.failures else "Savings Account"
            if self.timeout and self.submissions <= self.failures:
                raise PlaywrightTimeoutError("slow load")
        return ActionResult(ok=True)
    def wait_for_dialog(self): return False
    def observe(self): return Observation(url=self.current_url(), title="", visible_text=self.text)


@pytest.mark.parametrize("timeout", [False, True])
def test_recovery_succeeds_before_budget_exhausted(monkeypatch, timeout):
    monkeypatch.setattr("computer_use.recovery.time.sleep", lambda _: None)
    surface, logger = Surface(2, timeout), Logger()
    def intervene(reason): pytest.fail("Recovered lookup must not request handoff")
    execute_lookup_with_recovery(SEARCH, MEMBER, surface, SafetyPolicy(), logger, "step_2", intervene)
    assert (surface.submissions, surface.refills) == (3, 2)


def test_exactly_three_retries_then_same_session_handoff(monkeypatch):
    monkeypatch.setattr("computer_use.recovery.time.sleep", lambda _: None)
    surface, logger = Surface(100), Logger()
    interventions = []
    def intervene(reason):
        assert surface.submissions == 4
        interventions.append(reason)
        surface.text = "Savings Account"
    execute_lookup_with_recovery(SEARCH, MEMBER, surface, SafetyPolicy(), logger, "step_2", intervene)
    assert surface.refills == 3
    assert len(interventions) == 1
    assert [fields["retry"] for event, fields in logger.events if event == "retry"] == [1, 2, 3]


def test_still_busy_after_handoff_fails(monkeypatch):
    monkeypatch.setattr("computer_use.recovery.time.sleep", lambda _: None)
    with pytest.raises(RuntimeError, match="remains busy"):
        execute_lookup_with_recovery(SEARCH, MEMBER, Surface(100), SafetyPolicy(), Logger(), "step_2", lambda _: None)


def test_only_known_read_only_lookup_is_retryable():
    assert safe_lookup_submission("mock_credit_union", SEARCH, MEMBER)
    assert not safe_lookup_submission("other_app", SEARCH, MEMBER)
    assert not safe_lookup_submission("mock_credit_union", SEARCH.model_copy(update={"target": Target(name="Transfer")}), MEMBER)
    assert not safe_lookup_submission("mock_credit_union", SEARCH, None)
