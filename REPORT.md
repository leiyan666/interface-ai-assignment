# 1. Architecture

Discovery and replay are intentionally separate execution modes. Discovery observes a compact representation of the browser, asks the OpenAI adapter for one structured action, validates it against policy, executes it through `SurfaceAdapter`, and records the raw trajectory. The recorder/compiler then emits a small canonical capability artifact. Replay loads only that artifact and calls the Playwright surface directly; its code path contains no model decision call.

`PlaywrightSurface` owns browser details such as iframe access, semantic locator resolution, screenshots, and actions. The policy layer runs before execution, while `JsonlLogger` and screenshots preserve debugging evidence with redaction at the persistence boundary. The implementation is deliberately small because the take-home asks for a real vertical slice, not distributed orchestration or an operator product.

# 2. Artifact schema

`Capability` is a Pydantic model with a schema version, identity, target application metadata, typed inputs/outputs, ordered steps, checkpoints, business outcomes, safety policy, and metadata. Targets describe role, accessible name, visible text, nearby text, frame hint, and optional narrowly scoped fallbacks; they do not make raw Playwright selectors the source of truth. The surface maps those semantics to runtime locators.

The demo input is saved as `{{member_id}}`, and replay performs explicit regex substitution with no `eval`. Checkpoints include visible text, value, output, URL, and boolean composition. The artifact is not a raw transcript: it is reviewable, parameterized, versioned, and independent of model conversation details.

# 3. Determinism & error handling

Replay validates the artifact and inputs, opens the declared app, executes steps in order, retries configured steps a small number of times, checks each checkpoint, extracts declared outputs, and returns a typed `RunResult`. Semantic role/name and label targeting is more resilient than a single CSS selector, while the iframe hint handles this app’s legacy boundary. UI drift outside the supported semantic/fallback descriptions still becomes a hard failure with the failed step, message, and screenshot.

`MEMBER_NOT_FOUND`, `NO_SAVINGS_ACCOUNT`, and `PERMISSION_DENIED` are business outcomes because the application explicitly reports them as legitimate servicing results. Timeouts and failed checkpoints are hard failures after retry exhaustion; the policy and handoff path provide escalation for blockers. The transient test input is deterministic and the retry mechanism is intentionally simple rather than a workflow engine.

# 4. Heterogeneity & multi-tenant

The future seam is the surface abstraction:

```text
SurfaceAdapter
├── Browser/Playwright
├── Accessibility
├── Screenshot/coordinates
└── Desktop
```

Only the browser implementation exists today. Cross-tenant reuse would use a base vendor capability plus tenant-specific configuration/overrides, app-version metadata, locator overrides, and validation/stability checks before promotion. This design is proposed, not implemented.

# 5. Escalation & handoff

The surface records browser dialogs as a blocker. Discovery can also accept an explicit `escalate` action. Handoff captures a screenshot, logs the request, leaves the same visible browser context open, transfers control to `human`, waits for terminal confirmation, then logs completion and returns control to `automation` before re-observing. This demonstrates the control-transfer seam without building a co-browsing dashboard.

# 6. Safety

The policy allowlists localhost hosts and the small action vocabulary. Navigation is checked against allowed hosts and blocked routes; action risk is classified as read, safe-write, or irreversible, with irreversible actions requiring human confirmation. Redaction masks configured environment secrets and common token/password/authorization patterns before JSONL persistence. The local app uses synthetic data only. Limitations include no production identity system, no durable audit store, and no comprehensive PII classifier.

# 7. Cuts

This submission does not implement a desktop adapter, a real bank system, multi-tenant infrastructure, a full operator/co-browsing console, production authorization, distributed workers, or automatic artifact approval. It has one capability and a deliberately narrow checkpoint/locator vocabulary. Next steps would be stronger artifact review/version promotion, richer accessibility adapters, authenticated policy decisions, persistent run storage, and broader drift/stability validation.
