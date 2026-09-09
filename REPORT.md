# 1. Architecture

Discovery and replay are separate execution modes. Discovery observes a compact DOM-derived representation, asks the OpenAI adapter for one structured action, validates policy, executes it through the Playwright surface, and records the trajectory. The recorder/compiler derives artifact steps from those actions. Replay loads the artifact and executes its saved decisions without a model call. Python, FastAPI/Jinja2, Playwright, Pydantic and the official OpenAI SDK keep this single-browser vertical slice inspectable.

`PlaywrightSurface` owns iframe access, semantic locator resolution, screenshots and actions. The implementation is tailored to the mock console, including the Member Lookup iframe and table-cell extraction; it is not a general legacy-browser engine. JSONL events are redacted at the logging boundary. Raw trajectory JSON and screenshots do not have equivalent redaction guarantees and must contain synthetic data only.

# 2. Artifact schema

`Capability` is a Pydantic model with a schema version, identity, target application metadata, typed inputs/outputs, ordered steps, checkpoints, business outcomes, safety policy, and metadata. Targets describe role, accessible name, visible text, nearby text, frame hint, and optional narrowly scoped fallbacks; they do not make raw Playwright selectors the source of truth. The surface maps those semantics to runtime locators.

The demo input is saved as `{{member_id}}`, and replay performs explicit regex substitution with no `eval`. Checkpoints include visible text, value, output, URL, and boolean composition. The artifact is not a raw transcript: it is reviewable, parameterized, versioned, and independent of model conversation details.

The compiler reads trajectory actions in order, excludes explicitly unsuccessful results and non-replay control actions, retains semantic targets, and deduplicates extraction targets. It uses the first typed value as the member parameter and normalizes extraction output names to `savings_balance`. Effective action risk is retained in each step. Capability metadata, business outcomes and action-based checkpoint templates remain demo-specific. In particular, the compiler assumes the first typed field is the member number and uses lookup result checkpoints for clicks; multi-form workflows need more explicit bindings and checkpoint derivation. It is trajectory-driven but not a generic learning compiler.

# 3. Determinism & error handling

Replay validates the artifact and inputs, opens the declared app, executes steps in order, retries configured steps a small number of times, checks each checkpoint, extracts declared outputs, and returns a typed `RunResult`. Semantic role/name and label targeting is more resilient than a single CSS selector, while the iframe hint handles this app’s legacy boundary. UI drift outside the supported semantic/fallback descriptions still becomes a hard failure with the failed step, message, and screenshot.

Discovery completes only after a successful extract named `savings_balance` targets Savings Account, the page shows that label with no known business error or dialog, and the result fully matches a money string. Zero is valid; names and member IDs are rejected. A bare model `finish` cannot establish success. Rejected extractions are marked unsuccessful in history so they do not enter the compiled workflow. The loop has a 12-step default limit, but no overall wall-clock deadline. Replay currently uses its own dollar-value extraction and saved checkpoints rather than the entire discovery verifier; comprehensive input/output type and member-identity validation remain cuts.

`MEMBER_NOT_FOUND`, `NO_SAVINGS_ACCOUNT`, and `PERMISSION_DENIED` are business outcomes because the application explicitly reports them as legitimate servicing results. The known read-only member lookup retries busy/unavailable responses and Playwright timeouts three times after the initial attempt, restoring the member input before each submission. Every retry is logged. Exhaustion requests same-session human handoff; continuation still requires checkpoints to pass. Unknown blocked operations go directly to handoff because safe resubmission is not established. Other failed checkpoints remain hard failures. Headless runs return ESCALATED when human intervention is required; RECOVERABLE_ERROR remains a reserved enum, not a returned result.

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

The adapter boundary is incomplete: checkpoint code still calls browser-specific locator methods such as `input_value()`. New surface implementations would require moving checkpoint evaluation behind that boundary as well as supplying their own observations and targeting. Nested-frame discovery and arbitrary legacy table layouts are not generalized.

# 5. Escalation & handoff

The surface flags and dismisses native dialogs as blockers. Discovery can also accept an explicit `escalate` action. Handoff captures observations and screenshots before and after intervention in the same browser session. During human control, injected DOM listeners record trusted clicks, committed input changes and submissions; Playwright records frame navigation. Instrumentation is installed in new documents and iframes. Input values are omitted from human event payloads, and event URLs exclude query strings and fragments. Events are redacted and linked by a handoff ID and sequence number. The operator presses ENTER to resume, with no written summary required; the browser event loop continues pumping while terminal input waits in a separate thread. Collection stops before automation resumes. Native dialogs, browser chrome and individual keystrokes are not audited. Cancellation does not log completion. The CI bypass is explicitly marked as simulated. Screenshots are not redacted and are restricted to the synthetic demo context.

The persistent `30000` busy fixture exercises three retries after the initial submission, then handoff. The `40000` dialog fixture exercises direct handoff. Manually querying `10002` in either demo changes the lookup subject: the returned balance belongs to that selected member, not the original test ID. The current replay does not validate member identity after human intervention, so this demonstrates control transfer rather than safe production servicing.

# 6. Safety

The policy allowlists localhost hosts and the small action vocabulary. Navigation is checked against allowed hosts and blocked routes. Action risk survives discovery, compilation and replay through `Action.risk` and `CapabilityStep.risk`. Effective risk is the maximum of the declared risk, semantic inference and optional policy `target_risks` (exact case-insensitive label matches). Search clicks are treated as read; other clicks and typing have a safe-write minimum. Destructive labels such as Delete Account raise click risk to irreversible even if the action declares read. These are demo heuristics, not a general intent classifier. The default policy blocks irreversible actions before execution; terminal handoff confirmation does not authorize or bypass that block. Replay currently reports policy blocks as hard failures; a dedicated risky-action approval flow is not implemented. Redaction masks configured environment secrets and common token/password/authorization patterns before JSONL persistence. The local app uses synthetic data only. Limitations include no production identity system, no durable audit store, and no comprehensive PII classifier.

# 7. Cuts

This submission does not implement a desktop adapter, a real bank system, multi-tenant infrastructure, a full operator/co-browsing console, production authorization, distributed workers, or automatic artifact approval. It has one capability and a deliberately narrow checkpoint/locator vocabulary. Next steps would be stronger artifact review/version promotion, richer accessibility adapters, authenticated policy decisions, persistent run storage, and broader drift/stability validation.

Other explicit cuts are a returned RECOVERABLE_ERROR path, comprehensive network/redirect enforcement, end-to-end PII redaction, generic workflow compilation and fully surface-independent checkpoints. Initial app navigation and browser subrequests are not comprehensively covered by the action allowlist. Existing evidence includes development and simulated runs; old artifacts and logs are not automatically regenerated when code changes. Verification covers unit tests for success rejection, risk propagation, retries and handoff, plus a Chromium instrumentation smoke test. A fresh live discovery/replay/handoff run is needed to produce submission evidence for the latest implementation.
