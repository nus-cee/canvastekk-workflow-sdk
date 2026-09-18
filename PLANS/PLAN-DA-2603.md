# PLAN: SDK code_digest in /manifest, register CLI, local probe harness

**Branch**: feat/DA-2603
**Issue**: https://betekk.atlassian.net/browse/DA-2603
**Base**: main (4a41bdd — v0.27.0; canonical slug/name manifest vocabulary from DA-2627)

## Acceptance Criteria

- [x] `/manifest` serves `code_digest` (hash of the handler module computed at startup, auto-injected exactly like `sdk_version`/`mode` — never author-settable, i.e. NOT a model field); mutating handler code changes it; `sdk_version`/`mode`/`X-SDK-Version` behavior unchanged
- [x] Register CLI publishes the manifest to the engine registration endpoint from CI with a service credential — mirroring the proven nodes-repo path (`X-Service-Token` header, POST `/api/workflows/nodes/`, by-name verification), mapping to engine request vocabulary (`name`=slug value, `label`=display, `description`; DA-2666 adapter semantics)
- [x] Local probe harness runs OFFLINE and runs the same canned contract probes the registry runs (manifest model validation + Draft-7 schema checks + engine request-shape mirror) — "passes locally ⇔ passes registration"
- [x] Both python and typescript packages carry all three features; released with aligned versions (automated `feat:` → 0.28.0)
- [x] Gates green: python `ruff check canvastekk_workflow_sdk/ tests/` + `pytest -v`; typescript `tsc --noEmit` + `vitest run` + `tsup`

## Dependency & Consumer Map

| Node (file/module) | Depends on | Consumers | Change risk |
|--------------------|-----------|------------|-------------|
| `python/.../app.py` `/manifest` endpoint (+ startup digest computation) | — | engine reconciliation (future ticket, reads code_digest when available); CI register CLI; DA-2604/2605 verification ACs | low — additive response key, injected exactly like `sdk_version`/`mode` |
| digest helper (sha256 of handler module source; `ponytail:` single-module ceiling documented) | — | /manifest endpoint (python + ts) | low — deterministic, cached at startup |
| `python/.../__main__.py` `register` subcommand + request mapping | engine request schema (DA-2666 semantics) | DA-2604/2605 CI pipelines (replace hand-rolled rewrite), external authors | medium — wire mapping must match engine boundary exactly (`name`=slug, `label`=display; client-sent `slug` engine-rejected) |
| `python/.../__main__.py` `probe` subcommand (extends `validate`) | manifest model + engine request-shape mirror | same users as `validate` (offline pre-flight) | low |
| `typescript/src/app.ts` (+ digest util) + `bin` entry + probe script | mirrors python | ts-package node hosts | medium — ts needs a new `bin` in package.json + tsup config |
| docs (`EXTERNAL-AUTHOR-GUIDE.md`, READMEs ×3, skills) | code | node authors, DA-2604/2605 implementers | low — mandatory sync |
| Release (`feat:` → 0.28.0 both packages) | all above merged | node repos (exact URL pins — no auto-adopt; adoption deliberate via DA-2604/2605) | controlled — same exact-pin invariant as DA-2627 |

## Implementation Phases

### Phase 1: Python — code_digest in /manifest

- [x] **1.1** Add `_handler_code_digest(node)` helper: sha256 hex over the source-file bytes of the module that defines the node's handler (resolved via `inspect.getsourcefile`/`type(node).__module__`; cached on first computation). Inject `content["code_digest"] = ...` in the `/manifest` endpoint next to `sdk_version`/`mode`. NOT a `WorkflowNodeManifest` field — authors cannot set it; document the `ponytail:` single-module ceiling (upgrade to package-walk if nodes grow multi-file).
    — **Why:** ticket item 1 — engine reconciliation needs a code-change signal; endpoint injection is the established pattern (`sdk_version`, `mode`) and keeps the field un-settable by construction
    — **Done when:** `/manifest` response carries `code_digest` (64-hex); touching the handler module's bytes changes it; `sdk_version`/`mode`/`X-SDK-Version` tests unchanged and green
    — **Consumers affected:** future engine reconciliation, CI register flows, DA-2604/2605 verification

### Phase 2: Python — register CLI + probe harness

- [x] **2.1** `python -m canvastekk_workflow_sdk register <module:attr> --engine-url URL [--invoke-url URL] [--name-suffix S]`: build the engine request from the local manifest (`name=slug`(+suffix), `label=name`, `description`, version/schemas/category/tags/styles/constraints/token_cost/timeout_seconds/retry as the engine accepts, `invoke_url` override when given), `POST` with `X-Service-Token: $CANVASTEKK_REGISTRY_TOKEN` (env), then GET `by-name/{name}` to verify; non-zero exit on any failure with the HTTP status in the message.
    — **Why:** ticket item 2 — replaces the hand-rolled YAML-rewrite registration in node CI (the DA-2604 same-commit AC depends on this CLI existing); mirrors the proven `deploy-lambda.yml` auth path
    — **Done when:** registering a sample node against a local engine instance succeeds end-to-end (AC: "CLI registers a sample node against a local engine"); exit codes distinguish auth/4xx/5xx/network
    — **Consumers affected:** DA-2604/2605 pipelines, external authors publishing from CI
- [x] **2.2** `python -m canvastekk_workflow_sdk probe <module:attr>` (offline): run the canned contract probes the registry runs — manifest model validation (slug pattern, semver, display fields, schemas present), Draft-7 validity of input/output schemas (existing `validate` machinery), AND an engine-request mirror check (mapped payload validates against the engine's request shape: required keys present, no client-`slug` key, whitelisted keys only). Exit non-zero on any probe failure.
    — **Why:** ticket item 3 — "passes locally ⇔ passes registration" catches drift before CI; offline by construction (no HTTP)
    — **Done when:** a deliberately broken manifest fails `probe` with a per-probe report; a valid one passes; no network calls (test asserts offline behavior)
    — **Consumers affected:** node authors, CI pre-flight

### Phase 3: TypeScript — mirror

- [x] **3.1** ts `code_digest` in the `/manifest` handler (same sha256-over-handler-source computation, node `crypto`; injected next to `sdk_version`/`mode`); `register` CLI (`typescript/bin/register.ts` + `bin` entry in package.json + tsup build config) with identical flags/auth/mapping; `probe` script mirroring 2.2 (zod parse + schema probes + engine-shape mirror).
    — **Why:** AC — both language packages carry all three features with aligned behavior
    — **Done when:** ts tests cover digest change-on-mutation, register mapping, probe pass/fail parity with python rules; `tsc`/`vitest`/`tsup` green; `npx canvastekk-workflow-sdk register --help` works from the built package
    — **Consumers affected:** ts-package node hosts

### Phase 4: Docs + release safety + gates

- [x] **4.1** Docs sync (EXTERNAL-AUTHOR-GUIDE, READMEs ×3, embedded skills): `code_digest` behavior (what it is, when it changes, why it's not settable), `register` usage (env credential, flags, engine mapping table), `probe` usage; migration note for CI pipelines currently hand-rolling registration (deploy-lambda rewrite is DA-2604's same-commit AC, not this repo).
    — **Why:** repo rule — docs stay in sync; DA-2604/2605 implementers will read these docs to plan adoption
    — **Done when:** guide + READMEs show all three features with correct vocabulary (slug/name); no stale examples
    — **Consumers affected:** external authors, adoption tickets
- [x] **4.2** Final gates both packages from clean trees; merge commit carries `feat:` (→ 0.28.0, never patch — exact-pin invariant unchanged: node repos adopt deliberately); verify no consumer repo pin floats.
    — **Why:** AC — aligned release; the exact-wheel-pin invariant from DA-2627 stays the deploy-safety mechanism
    — **Done when:** all gates green; version math verified (cliff `features_always_bump_minor`); PR body documents the release expectation
    — **Consumers affected:** node repos, engine reconciliation ticket

## Technical Notes

- Engine consumes `code_digest` in a FUTURE ticket (verified: zero refs in engine today) — this PR only serves it.
- Auth: `X-Service-Token` header (the proven engine service-identity path, `deploy-lambda.yml:545`); token from `CANVASTEKK_REGISTRY_TOKEN` env (documented; never a CLI arg — keep secrets out of process lists).
- Vocabulary: manifest is canonical (DA-2627, v0.27+); the CLI maps to the ENGINE's request vocabulary (`name`=slug value, `label`=display) — same semantics the engine's own `from_sdk` now uses (DA-2666).
- `sdk_version`/`mode`/`X-SDK-Version` must remain byte-identical in behavior (AC) — existing tests pin them; do not touch.
- ts digest: hash the compiled entry's handler source — same "module that defines the handler" rule; `ponytail:` single-file ceiling documented identically.

## Dependencies

- None (ticket: "No engine dependency — can start immediately"). Unblocks DA-2604/2605 fully (their last open prerequisite after DA-2666).

## Risks & Mitigations

- **Digest instability** (hash changes without code change — e.g. hashing absolute paths or pyc) — hash ONLY source bytes of the resolved module file; determinism pinned by tests (same bytes → same digest across calls/instances).
- **Register mapping drift vs engine boundary** — probe's engine-shape mirror + integration test against a local engine (AC) + the mapping table in docs; DA-2604 adoption re-verifies end-to-end.
- **ts/python behavior divergence** — parity test list shared in the PLAN (digest mutation, register mapping, probe rules); review cross-checks.
- **Secret leakage** — token only via env; CLI redacts it from error output (tests assert).

## Execution trace (2026-09-19)

- Phase 1 (py code_digest): startup sha256 of node-class module, endpoint-injected;
  tests present/stable/mutation-sensitive. Gates green.
- Phase 2 (py CLI): register (X-Service-Token path, by-name verify, typed exit
  codes, token never printed) + probe (offline engine-request mirror).
  701 py tests green.
- Phase 3 (ts parity): code_digest via structured-stack caller resolution;
  bin canvastekk-workflow-sdk (register/probe). 324 ts tests green; bin smoke-
  tested from dist.
- Phase 4: guide + 3 READMEs updated; release rides `feat:` commits (>= 0.28.0,
  exact-pin invariant unchanged).

## Review + live-AC trace (2026-09-19)

- Code review: 0 BLOCK / 3 WARN / 6 NOTE — all WARNs fixed (both CLIs delegate
  to build_registry_payload/buildRegistryPayload; probe mirrors the engine's
  VALUE domain — category enum, timeout ceiling, name pattern; py probe exit
  codes aligned with ts). Cheap NOTEs taken (suffix validation, 2xx alignment,
  pathToFileURL, PLAN route prose, guide bundler note).
- Live local-engine register (AC 2.1): integration compose (Postgres 15432 +
  Temporal 17233), alembic to head (046), engine on :8123 with
  DEV_MODE + REGISTRY_SERVICE_TOKEN. `python -m canvastekk_workflow_sdk register
  tests.test_cli_register:_manifest_module_marker --engine-url http://localhost:8123
  --invoke-url ... --name-suffix -live` → exit 0. Engine row verified via
  by-name: name=echo-live, label=Echo, version=1.0.0, invoke_url override,
  category=utility (id a26938f7-...). Stack torn down after.
- Final gates: py ruff + 704 passed; ts tsc + 327 passed + tsup + eslint.
