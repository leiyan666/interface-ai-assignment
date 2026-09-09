"""Playwright implementation of the surface abstraction."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol
from collections.abc import Callable
from urllib.parse import urlsplit, urlunsplit

from playwright.sync_api import Browser, BrowserContext, Locator, Page, sync_playwright

from .schema import Action, ActionResult, Observation, ObservationElement, Target
from .human_tracking import TRACKING_SCRIPT


class SurfaceAdapter(Protocol):
    def observe(self) -> Observation: ...
    def execute(self, action: Action) -> ActionResult: ...
    def screenshot(self, path: str) -> str: ...
    def current_url(self) -> str: ...
    def wait_for_dialog(self, timeout_ms: int = 500) -> bool: ...


class PlaywrightSurface:
    def __init__(self, entry_point: str, headless: bool = False) -> None:
        self._playwright = sync_playwright().start()
        # The explicit flags keep Chromium usable in restricted CI/container runtimes.
        self.browser: Browser = self._playwright.chromium.launch(
            headless=headless, args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        self.context: BrowserContext = self.browser.new_context()
        self._human_sink: Callable[[dict], None] | None = None
        self.context.expose_binding("__recordHumanEvent", self._human_event)
        self.context.add_init_script(TRACKING_SCRIPT)
        self.context.on("page", self._track_page)
        self.page: Page = self.context.new_page()
        self.entry_point = entry_point
        self.dialog_message: str | None = None
        self.page.on("dialog", self._on_dialog)

    @staticmethod
    def _safe_event_url(url: str) -> str:
        parsed = urlsplit(url)
        return urlunsplit((parsed.scheme, parsed.hostname or "", parsed.path, "", ""))

    def _human_event(self, source: dict, payload: dict) -> None:
        if self._human_sink and isinstance(payload, dict) and payload.get("kind") in {"click", "change", "submit"}:
            self._human_sink({
                "kind": payload["kind"],
                "target": {key: str(payload.get(key, ""))[:120] for key in ("tag", "role", "name")},
                "frame_url": self._safe_event_url(source["frame"].url),
                "value": "[NOT RECORDED]",
            })

    def _track_page(self, page: Page) -> None:
        def navigated(frame):
            if self._human_sink:
                self._human_sink({"kind": "navigation", "frame_url": self._safe_event_url(frame.url)})
        page.on("framenavigated", navigated)

    def start_human_tracking(self, sink: Callable[[dict], None]) -> None:
        self._human_sink = sink

    def stop_human_tracking(self) -> None:
        self._human_sink = None

    def pump_events(self) -> None:
        self.page.wait_for_timeout(100)

    def _on_dialog(self, dialog) -> None:
        self.dialog_message = dialog.message
        dialog.dismiss()

    def start(self) -> None:
        self.page.goto(self.entry_point, wait_until="domcontentloaded")

    def close(self) -> None:
        self.context.close()
        self.browser.close()
        self._playwright.stop()

    def wait_for_dialog(self, timeout_ms: int = 500) -> bool:
        self.page.wait_for_timeout(timeout_ms)
        return self.dialog_message is not None

    def _root(self, target: Target | None = None):
        if target and target.frame_hint:
            return self.page.frame_locator(f'iframe[title="{target.frame_hint}"]')
        return self.page

    def _roots(self, target: Target):
        if target.frame_hint:
            return [self._root(target)]
        roots = [self.page]
        if self.page.locator('iframe[title="Member Lookup"]').count():
            roots.append(self.page.frame_locator('iframe[title="Member Lookup"]'))
        return roots

    def resolve(self, target: Target) -> Locator:
        for root in self._roots(target):
            if target.role and target.name:
                locator = root.get_by_role(target.role, name=target.name, exact=False)
                if locator.count():
                    return locator.first
            if target.name:
                locator = root.get_by_label(target.name, exact=False)
                if locator.count():
                    return locator.first
                # Legacy tables often expose a value label as a pseudo-control.
                row = root.locator("tr").filter(has_text=target.name)
                if row.count():
                    cells = row.first.locator("td")
                    if cells.count():
                        return cells.last
            if target.near_text:
                row = root.locator("tr").filter(has_text=target.near_text)
                if row.count():
                    cells = row.first.locator("td")
                    if cells.count():
                        return cells.last
            if target.text:
                locator = root.get_by_text(target.text, exact=True)
                if locator.count():
                    return locator.first
            for fallback in target.fallbacks:
                locator = root.locator(fallback.value) if fallback.strategy != "text" else root.get_by_text(fallback.value)
                if locator.count():
                    return locator.first
        raise LookupError(f"Could not resolve semantic target: {target.model_dump_json()}")

    def observe(self) -> Observation:
        elements: list[ObservationElement] = []
        frame = self.page.locator('iframe[title="Member Lookup"]')
        roots = [self.page] + ([self.page.frame_locator('iframe[title="Member Lookup"]')] if frame.count() else [])
        for root_index, root in enumerate(roots):
            for index, locator in enumerate(root.locator("input, button, a, [role]").all()):
                try:
                    role = locator.get_attribute("role") or ("textbox" if locator.evaluate("e => e.tagName") == "INPUT" else "button")
                    name = locator.get_attribute("aria-label") or locator.evaluate("e => e.labels?.[0]?.innerText?.trim()") or locator.inner_text().strip() or locator.get_attribute("name") or None
                    elements.append(ObservationElement(ref=f"e{root_index}_{index}", role=role, name=name, value=locator.input_value() if role == "textbox" else None, text=locator.inner_text().strip() or None))
                except Exception:
                    continue
        visible_text = self.page.locator("body").inner_text()
        if frame.count():
            visible_text += "\n" + frame.content_frame.locator("body").inner_text()
        dialog_present = self.dialog_message is not None
        self.dialog_message = None
        return Observation(url=self.current_url(), title=self.page.title(), elements=elements, visible_text=visible_text[:4000], dialog_present=dialog_present)

    def execute(self, action: Action) -> ActionResult:
        if action.action_type == "navigate":
            self.page.goto(action.value or self.entry_point, wait_until="domcontentloaded")
        elif action.action_type == "click":
            if not action.target:
                raise ValueError("click requires target")
            self.resolve(action.target).click()
        elif action.action_type == "type":
            if not action.target:
                raise ValueError("type requires target")
            self.resolve(action.target).fill(action.value or "")
        elif action.action_type == "extract":
            if not action.target:
                raise ValueError("extract requires target")
            return ActionResult(ok=True, value=self.resolve(action.target).inner_text())
        elif action.action_type == "wait":
            self.page.wait_for_timeout(min(int(action.value or "250"), 5000))
        elif action.action_type in {"finish", "escalate"}:
            return ActionResult(ok=True)
        return ActionResult(ok=True)

    def screenshot(self, path: str) -> str:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        self.page.screenshot(path=str(destination), full_page=True)
        return str(destination)

    def current_url(self) -> str:
        return self.page.url
