"""Minimal same-session human control transfer."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4
from queue import Queue
from threading import Thread

from .logging_utils import JsonlLogger
from .surface import PlaywrightSurface


def handoff(surface: PlaywrightSurface, logger: JsonlLogger, screenshot_path: str) -> None:
    handoff_id = uuid4().hex[:10]
    destination = Path(screenshot_path)
    after_path = str(destination.with_name(f"{destination.stem}_{handoff_id}_after{destination.suffix}"))
    before = surface.observe()
    surface.screenshot(screenshot_path)
    logger.event("handoff_requested", handoff_id=handoff_id, control_owner="automation",
                 evidence=screenshot_path, observation=before.model_dump(mode="json"))
    logger.event("control_transferred_to_human", handoff_id=handoff_id, control_owner="human")
    print(f"Automation paused. Inspect the visible browser and fix the blocker. Evidence: {screenshot_path}")
    simulated = os.getenv("CI_AUTO_HANDOFF") == "1"
    action_count = 0

    def record(action: dict) -> None:
        nonlocal action_count
        action_count += 1
        logger.event("human_action", handoff_id=handoff_id, control_owner="human",
                     sequence=action_count, source="browser_events", action=action)

    if simulated:
        summary = "CI bypass; no human actions recorded."
    else:
        # Playwright's synchronous event loop must keep running while stdin waits.
        # Only stdin runs in a thread; all browser operations stay on this thread.
        response: Queue[BaseException | None] = Queue()
        def wait_for_enter() -> None:
            try:
                input("Press ENTER after human intervention to resume automation... ")
                response.put(None)
            except (EOFError, KeyboardInterrupt) as exc:
                response.put(exc)
        surface.start_human_tracking(record)
        try:
            Thread(target=wait_for_enter, daemon=True).start()
            while response.empty():
                surface.pump_events()
            error = response.get()
            if error is not None:
                raise error
            surface.pump_events()
        except (EOFError, KeyboardInterrupt):
            logger.event("handoff_cancelled", handoff_id=handoff_id, control_owner="human")
            raise RuntimeError("Handoff cancelled before confirmation") from None
        finally:
            surface.stop_human_tracking()
        summary = f"Recorded {action_count} browser events during human control."
    after = surface.observe()
    surface.screenshot(after_path)
    logger.event("human_intervention_completed", handoff_id=handoff_id, control_owner="human",
                 summary=summary, summary_source="simulation" if simulated else "browser_events", action_count=action_count,
                 simulated=simulated, observation=after.model_dump(mode="json"), evidence=after_path)
    logger.event("control_returned_to_automation", handoff_id=handoff_id, control_owner="automation")
