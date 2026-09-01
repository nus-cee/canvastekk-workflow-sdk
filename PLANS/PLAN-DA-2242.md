# PLAN: DA-2242 — workflow-sdk: propagate X-Account-Id header into node execution context

**Ticket:** DA-2242 (blocks DA-2236)
**Branch:** feat/DA-2242 (base: `main`)
**Repo:** canvastekk-workflow-sdk

## Overview

The workflow engine already forwards the caller's account as an
`X-Account-Id` HTTP header on every node `/execute` POST
(`canvastekk-workflow-engine` `temporal/activities.py:596`), but the SDK's
`/execute` handler parses only the JSON body — the header is dropped, and
`NodeExecutionRequest`/`ExecutionContext` carry no `account_id`. Downstream,
`project-file-publisher` (DA-2236) cannot forward the account to CDS and gets
`403 no_active_account`.

This PLAN adds `account_id` transport to the SDK: header capture in
`/execute`, a new optional field on `NodeExecutionRequest`, and an
`ExecutionContext.account_id` accessor. Merge to `main` auto-releases
v0.24.0 (feat: → minor, `.github/workflows/release.yml`).

## Acceptance Criteria

- [ ] `NodeExecutionRequest` accepts an optional `account_id: int | None`
      (default `None`, absent = local/back-compat runs).
- [ ] `ExecutionContext.account_id` returns the request's value (or `None`
      when no request is attached).
- [ ] `/execute` reads the `X-Account-Id` header; valid integer → set on the
      request; malformed (non-integer) → HTTP 400; absent → `None`.
- [ ] Tests cover field parsing, context property, and all three header
      cases.
- [ ] `docs/EXTERNAL-AUTHOR-GUIDE.md` and `python/README.md` document the new
      context surface.
- [ ] `poetry run ruff check canvastekk_workflow_sdk/ tests/` and
      `poetry run pytest -v` both green in `python/`.

## Scope

**Python SDK only.** The repo's parallel TypeScript SDK (`typescript/src/app.ts`) also drops the header today — out of scope for DA-2242 (the DA-2236 publisher is a Python node); TS parity gets a follow-up ticket before any TS node needs account context. Non-goal: callback/`/hook` flows — the engine only sends the header on the `/execute` POST; `callback_url` is node→engine.

- `python/canvastekk_workflow_sdk/request.py`
- `python/canvastekk_workflow_sdk/context.py`
- `python/canvastekk_workflow_sdk/app.py`
- `python/tests/test_request.py`, `test_context.py`, `test_app.py`
- `docs/EXTERNAL-AUTHOR-GUIDE.md`, `python/README.md`

## Technical Notes

- **`account_id` is engine-controlled.** The HTTP header is the EXCLUSIVE source: `/execute` strips any body-supplied `account_id` before validation and injects the header value via the constructor. Body-only `account_id` → `None` (no spoof path).
- **Header parsing (fail-fast 400):** read via Starlette `request.headers.get("x-account-id")` (case-insensitive). Absent or empty-after-strip → `None`. Otherwise the stripped value must match `^\d+$` and satisfy `1 <= v <= 2**63-1`; anything else → HTTP 400 (never silently drop account context — that recreates the DA-2236 silent-403 class).
- Field bounds pinned on the model too: `Field(default=None, ge=1, le=2**63-1)` (defense for direct construction).
- `model_config = ConfigDict(extra="ignore", json_schema_extra=...)` — pin the cross-version compat contract explicitly (today it rests on the pydantic default).
- Header capture ordering: after body JSON parse, injected into `NodeExecutionRequest(**...)` validation, before `node.run()` (`app.py:305/:321`).
- The engine omits the header when `account_id` is `None` (`canvastekk-workflow-engine fastapi_app/temporal/activities.py:595-596`); absent is never an error (local runs via `workflow/runner.py` and direct `BaseNode.run()` have no header).
- Docs must state `account_id` is engine-asserted identity for routing, **not** an auth credential (NodeAuth still gates the endpoint).
- No manual version bump — git-cliff; merge commit MUST be `feat:` type.

## Dependency & Consumer Map

| Node (file/module) | Depends on | Consumers | Change risk |
|---|---|---|---|
| `request.py` NodeExecutionRequest.account_id | — | app.py /execute, context.py, all node handlers (via context) | low (additive optional) |
| `context.py` ExecutionContext.account_id | request.py field | canvastekk-workflow-nodes handlers (DA-2236) | low (additive property) |
| `app.py` /execute header capture | request.py field | every node's runtime; must sit between body validation and `node.run` | med (request path; 400 on malformed only) |
| `base.py:575` `_record_error` context | (unchanged) | `on_error` middleware gains the field for free — same request object | none |
| `workflow/runner.py:250/:337` request-less contexts | (unchanged) | local runs → `account_id=None` by design; DA-2236 no-op-on-None contract covers it | none |
| tests (3 files) | the above | CI gate | low |
| docs (2 files) | the above | node authors | low |

## Implementation Phases

### Phase 1: transport field + context accessor

- [ ] **1.1** Add `account_id: int | None = Field(default=None, ge=1, le=2**63-1)` to `NodeExecutionRequest` and pin `extra="ignore"` in `model_config`
    — **Why:** the header value needs a typed, bounded home (DB int64 downstream); explicit `extra="ignore"` pins the cross-version compat contract that today rests on a pydantic default.
    — **Done when:** `NodeExecutionRequest(run_id="r", node_id="n")` validates with `account_id=None`; `account_id=42` round-trips; `0`/`-1`/`2**63` raise ValidationError.
    — **Consumers affected:** `app.py` /execute, `context.py`.
- [ ] **1.2** Add `account_id` property to `ExecutionContext` in `context.py`
    — **Why:** node handlers only ever see the context (publisher's `execute(inputs, context)`), so this is the surface DA-2236 consumes; reading from `self._request` keeps it in sync with the parsed request (mirrors the `run_id` property pattern, `context.py:83-87`).
    — **Done when:** context built with a request carrying `account_id=7` returns `7`; request-less context returns `None`.
    — **Consumers affected:** canvastekk-workflow-nodes handlers (DA-2236).

### Phase 2: header capture in /execute

- [ ] **2.1** Capture `X-Account-Id` in `app.py` `/execute`; header is the exclusive source (body-supplied `account_id` stripped), inject via constructor
    — **Why:** the engine sends the account as a header, never in the body; leaving the body field live would let any caller forge account identity (`NodeExecutionRequest(**body)` at `app.py:287`) — defeating the ticket's purpose. Fail-fast 400 on malformed instead of silently dropping context. Ordering: after body JSON parse, before `node.run`.
    — **Done when:** valid header → context sees the int; malformed/negative/out-of-range → HTTP 400; absent or empty-after-strip → `None`; body-only `account_id` → `None`; conflicting body+header → header wins. OpenAPI 400 description mentions the header case.
    — **Consumers affected:** every node's runtime path (engine → node).

### Phase 3: tests

- [ ] **3.1** Extend `tests/test_request.py` for the new field
    — **Why:** pins the additive-optional + bounded contract against regressions.
    — **Done when:** tests assert default `None`, int accepted, `0`/negative/`2**63` rejected.
    — **Consumers affected:** none (CI gate).
- [ ] **3.2** Extend `tests/test_context.py` for the property
    — **Why:** the property is the public surface nodes consume; both request-attached and request-less paths must be pinned.
    — **Done when:** tests assert property returns the request value and `None` without a request.
    — **Consumers affected:** none (CI gate).
- [ ] **3.3** Extend `tests/test_app.py` for header capture (TestClient `headers={...}` precedent exists in auth/413 tests) using a context-capturing echo node (mirrors `FileProcessingNode` → derived outputs pattern)
    — **Why:** the /execute wiring is the whole point of the ticket; header cases AND the body-spoof guard need HTTP-level coverage.
    — **Done when:** tests assert (a) valid header → context value in outputs, (b) malformed → 400, (c) empty-after-strip → absent/`None`, (d) absent → `None`, (e) body-only `account_id` → context sees `None`, (f) conflicting body+header → header wins, (g) lowercase `x-account-id` variant works (Starlette headers are case-insensitive), (h) one boundary: `0` → 400.
    — **Consumers affected:** none (CI gate).

### Phase 4: docs + gates

- [ ] **4.1** Document `context.account_id` in `docs/EXTERNAL-AUTHOR-GUIDE.md` and `python/README.md`
    — **Why:** repo AGENTS.md makes docs sync mandatory for auth/node-workflow changes; docs must state the header → context flow, `None` semantics for local runs, that `account_id` is engine-asserted routing identity (not a credential), and show the `NodeExecutionRequest(..., account_id=7)` unit-test pattern for node authors (DA-2236).
    — **Done when:** both docs cover those four points.
    — **Consumers affected:** node authors.
- [ ] **4.2** Run `poetry run ruff check canvastekk_workflow_sdk/ tests/` and `poetry run pytest -v` in `python/`
    — **Why:** repo-mandated pre-merge gates.
    — **Done when:** both exit 0.
    — **Consumers affected:** CI / release automation.
- [ ] **4.3** Commit as `feat(sdk): propagate X-Account-Id into node execution context (DA-2242)`
    — **Why:** git-cliff maps `feat:` to a minor bump — merge to `main` auto-releases v0.24.0 and dispatches `sdk-released` to canvastekk-workflow-nodes; a non-feat type would ship nothing.
    — **Done when:** commit message type is `feat`; PR merged to `main`; release workflow publishes the v0.24.0 wheel.
    — **Consumers affected:** canvastekk-workflow-nodes pin bump (DA-2236).

## Dependencies

- Blocks **DA-2236** (nodes pin bump + publisher header forward).
- Companion **DA-2243** (CDS interceptor SA branch) is independent of this SDK change.

## Risks & Mitigation

- **Risk:** engine deployments that predate the header forwarding — nodes see `account_id=None`. **Mitigation:** field is optional end-to-end; DA-2236's publisher must no-op (not fail) when absent.
- **Risk:** malformed header 400 could break a hypothetical proxy that injects junk. **Mitigation:** fail-fast is the intended behavior; engine always sends a canonical int.

## Success Metrics

- v0.24.0 wheel published on merge; DA-2236 can consume `context.account_id`.
