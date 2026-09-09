"""Minimal same-session human control transfer."""

from __future__ import annotations

import os

from .logging_utils import JsonlLogger
from .surface import PlaywrightSurface


def handoff(surface: PlaywrightSurface, logger: JsonlLogger, screenshot_path: str) -> None:
    surface.screenshot(screenshot_path)
    logger.event("handoff_requested", control_owner="automation", evidence=screenshot_path)
    logger.event("control_transferred_to_human", control_owner="human")
    print(f"Automation paused. Inspect the visible browser and fix the blocker. Evidence: {screenshot_path}")
    if os.getenv("CI_AUTO_HANDOFF") != "1":
        input("Press ENTER after human intervention to resume automation... ")
    logger.event("human_intervention_completed", control_owner="human")
    logger.event("control_returned_to_automation", control_owner="automation")
