"""DOM event instrumentation; deliberately excludes input values."""

TRACKING_SCRIPT = r"""
(() => {
  if (window.__handoffTrackingInstalled) return;
  window.__handoffTrackingInstalled = true;
  for (const kind of ['click', 'change', 'submit']) {
    document.addEventListener(kind, event => {
      if (!event.isTrusted) return;
      const el = event.target.closest('input,textarea,select,button,a,form,[role]') || event.target;
      const editable = el.matches('input,textarea,select,[contenteditable]');
      const name = el.getAttribute('aria-label') || el.labels?.[0]?.innerText ||
        (!editable && el.matches('button,a') ? el.innerText : '') || '';
      window.__recordHumanEvent({
        kind, tag: el.tagName.toLowerCase(),
        role: el.getAttribute('role') || '', name: name.slice(0, 120),
        value: editable ? '[NOT RECORDED]' : null
      }).catch(() => {});
    }, true);
  }
})();
"""
