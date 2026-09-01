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

- `python/canvastekk_workflow_sdk/request.py`
- `python/canvastekk_workflow_sdk/context.py`
- `python/canvastekk_workflow_sdk/app.py`
- `python/tests/test_request.py`, `test_context.py`, `test_app.py`
- `docs/EXTERNAL-AUTHOR-GUIDE.md`, `python/README.md`

## Technical Notes

- Pydantic default `extra="ignore"` on `NodeExecutionRequest` keeps old
  engines/new SDKs and new engines/old SDKs compatible in both directions.
- No manual version bump — releases are automated via git-cliff on
  conventional commits; the merge commit MUST be `feat:` type.
- The engine omits the header entirely when `account_id` is `None`; the SDK
  must never treat "absent" as an error (local `run_server` runs have no
  header).

## Dependency & Consumer Map

| Node (file/module) | Depends on | Consumers | Change risk |
|---|---|---|---|
| `request.py` NodeExecutionRequest.account_id | — | app.py /execute, context.py, all node handlers (via context) | low (additive optional) |
| `context.py` ExecutionContext.account_id | request.py field | canvastekk-workflow-nodes handlers (DA-2236) | low (additive property) |
| `app.py` /execute header capture | request.py field | every node's runtime | med (request path; 400 on malformed only) |
| tests (3 files) | the above | CI gate | low |
| docs (2 files) | the above | node authors | low |

## Implementation Phases

### Phase 1: transport field + context accessor

- [ ] **1.1** Add `account_id: int | None = None` to `NodeExecutionRequest` in `request.py`
    — **Why:** the header value needs a typed home the rest of the SDK can read; optional-with-None keeps local runs and old callers valid.
    — **Done when:** `NodeExecutionRequest(run_id="r", node_id="n")` still validates; `account_id=42` round-trips through the model.
    — **Consumers affected:** `app.py` /execute, `context.py`.
- [ ] **1.2** Add `account_id` property to `ExecutionContext` in `context.py`
    — **Why:** node handlers only ever see the context (publisher's `execute(inputs, context)`), so this is the surface DA-2236 consumes; reading from `self._request` keeps it in sync with the parsed request.
    — **Done when:** context built with a request carrying `account_id=7` returns `7`; request-less context returns `None`.
    — **Consumers affected:** canvastekk-workflow-nodes handlers (DA-2236).

### Phase 2: header capture in /execute

- [ ] **2.1** Capture `X-Account-Id` in `app.py` `/execute` and set it on `exec_request`
    — **Why:** the engine sends the account as a header, never in the body — without this step the field from 1.1 is never populated at runtime. Malformed values must fail fast (400) rather than silently drop account context (that recreates the DA-2236 silent-403 class of bug).
    — **Done when:** POST /execute with `X-Account-Id: 42` results in the node's context seeing `account_id == 42`; `X-Account-Id: abc` returns HTTP 400; no header → `None`.
    — **Consumers affected:** every node's runtime path (engine → node).

### Phase 3: tests

- [ ] **3.1** Extend `tests/test_request.py` for the new field
    — **Why:** pins the additive-optional contract (present/absent) against future regressions.
    — **Done when:** tests assert `account_id` defaults to `None` and accepts an int.
    — **Consumers affected:** none (CI gate).
- [ ] **3.2** Extend `tests/test_context.py` for the property
    — **Why:** the property is the public surface nodes consume; both request-attached and request-less paths must be pinned.
    — **Done when:** tests assert property returns the request value and `None` without a request.
    — **Consumers affected:** none (CI gate).
- [ ] **3.3** Extend `tests/test_app.py` for header capture
    — **Why:** the /execute wiring is the whole point of the ticket; all three header cases (valid/malformed/absent) need HTTP-level coverage.
    — **Done when:** tests assert 200+context value for a valid header, 400 for malformed, and `None` when absent.
    — **Consumers affected:** none (CI gate).

### Phase 4: docs + gates

- [ ] **4.1** Document `context.account_id` in `docs/EXTERNAL-AUTHOR-GUIDE.md` and `python/README.md`
    — **Why:** repo AGENTS.md makes docs sync mandatory for auth/node-workflow changes; external node authors must discover the field without reading source.
    — **Done when:** both docs mention the header → context flow and the `None` semantics for local runs.
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
