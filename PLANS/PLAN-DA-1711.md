# PLAN-DA-1711 — Security & Robustness Hardening

**Issue**: [DA-1711](https://betekk.atlassian.net/browse/DA-1711) — Security & robustness hardening: download SSRF/size-cap, runner crash, path traversal, auth defaults
**Branch**: `DA-1711`
**Created**: 2026-08-15
**Amended**: 2026-08-15 — applied plan-review findings PLAN-1..PLAN-12 (architecture review of this plan)
**Status**: Not started

## Review Basis

Three-way review of main @ `1036831` (v0.21.0): architecture review, Python review, TypeScript review. All High findings re-verified against current checkout. Finding IDs below: `ARCH-*` (architecture), `PY-*` (Python), `TS-*` (TypeScript) — deduplicated into work items.

---

## Dependency & Consumer Map

| Node (file/module) | Depends on (must precede) | Consumers (who depends on this) | Change risk |
|---|---|---|---|
| `python/…/base.py` (download loop) | URL policy helper (new `_url.py`) | `BaseNode.run()`, all node authors; `examples/echo_node` | high |
| `typescript/src/base-node.ts` (download) | URL policy helper (new `url-policy.ts`) | `BaseNode.run()`, all TS node authors | high |
| `python/…/request.py` / `typescript/src/request.ts` | — | `app.py`/`app.ts` `/execute`, `ExecutionContext`, `executor.py`/`executor.ts` | med |
| `python/…/context.py` / `typescript/src/context.ts` | request validators (M1) | `ExecutionContext.output_path()`, uploads, all nodes | high |
| `python/…/workflow/runner.py` / `typescript/src/workflow/runner.ts` | — | `WorkflowRunner.run()`, workflow tests | high |
| `python/…/workflow/resolver.py` / `typescript/src/workflow/resolver.ts` | — | runner, `resolve_inputs` | med |
| `python/…/app.py` / `typescript/src/app.ts` | request validators, context containment | node HTTP servers, engine | high |
| `python/…/uploads.py` / `typescript/src/uploads.ts` | URL policy helper | `app.py`/`app.ts` post-execute upload | med |
| `python/…/auth.py` / `typescript/src/auth.ts` | — | `app.py`/`app.ts` dependency wiring | low |
| `docs/EXTERNAL-AUTHOR-GUIDE.md` | auth/download behavior changes (Phases 1–3) | external node authors | low |

---

## Implementation Phases

### Phase 1 — Download pipeline (H1 SSRF + H2 size caps + partial-file cleanup)

- [x] **1.1** Add shared URL policy helper: Python `canvastekk_workflow_sdk/_url.py` and TS `src/url-policy.ts` — validate scheme (`https` in production mode), block resolved loopback/private/link-local/metadata IPs, re-validate every redirect hop via an explicit hop loop with a redirect cap (NOT `redirect:"error"` — S3 presigned GETs can legitimately 3xx via bucket website endpoints/CloudFront), plus an allowlist hook for storage endpoints. Required baseline: resolve-and-validate DNS before connect + per-hop re-validation (defeats naive SSRF; leaves only a small rebinding window). Connection pinning to the resolved IP is best-effort per client (httpx needs a custom transport — no first-class support; undici `Agent connect.lookup` is feasible).
    — **Why:** Every URL fetch (download + upload) currently trusts the caller completely (PY-1/TS-1/ARCH-1, PY-4/TS-6); one helper fixes all call sites in both languages and keeps parity.
    — **Done when:** Unit tests cover private-IP block, metadata-IP block, redirect-to-internal rejection, https-only in production; `ruff check` + `npx tsc --noEmit` pass.
    — **Consumers affected:** `base.py` download loop, `uploads.py`, `base-node.ts`, `uploads.ts`.
    — **Done:** Implemented _url.py + url-policy.ts (scheme policy w/ dev-mode http, metadata hosts, private/loopback/link-local/CGNAT/reserved/multicast blocklists, IPv4-mapped unwrap, CANVASTEKK_URL_ALLOWLIST suffix bypass, injectable resolver, unresolvable pass-through); redirect hop-loop re-validation (cap 5) wired into both download paths; DNS pinning documented best-effort; files: python/canvastekk_workflow_sdk/_url.py, typescript/src/url-policy.ts, base.py, base-node.ts; tests: test_url_policy.py (17), url-policy.test.ts (17); fixes: Node BlockList v4/v6 mixing bug worked around via separate blockedV4/blockedV6 lists; empty-host check ordered before dev-mode early return

- [x] **1.2** Python: enforce byte caps mid-stream in `base.py:241-292` — treat `Content-Length` early-reject strictly as an optimization (chunked responses have no Content-Length and it can understate; the running-byte counter is the authoritative enforcement), abort + unlink when running bytes exceed the cap, and apply an env-configurable default cap (`CANVASTEKK_MAX_DOWNLOAD_BYTES`, default 10 GiB) when `x-maxSizeBytes` is absent — this domain's files are multi-GB point clouds, so a 1 GiB default would break legitimate undeclared nodes.
    — **Why:** Size is validated only after the full body hits disk (PY-2/ARCH-2) — disk-exhaustion primitive; absent `x-maxSizeBytes` fields have no cap at all.
    — **Done when:** Test downloads a body larger than the declared cap and asserts abort before completion + no leftover file; absent-cap field hits the default.
    — **Consumers affected:** all Python nodes with file inputs.
    — **Done:** Python download rewritten to httpx.get manual hop loop; Content-Length early-reject as optimization only; running byte counter authoritative w/ mid-stream abort + unlink; _max_download_bytes resolves x-maxSizeBytes -> CANVASTEKK_MAX_DOWNLOAD_BYTES -> 10 GiB default; files: python/canvastekk_workflow_sdk/base.py, tests/test_file_download.py; fixes: none (gate green first run after mock migration)

- [x] **1.3** TypeScript: rewrite download to stream-to-disk (`Readable.fromWeb(resp.body)` → `createWriteStream`) with the same mid-stream cap logic as 1.2, replacing whole-body RAM buffering (`base-node.ts:240-259`).
    — **Why:** TS buffers the entire response in memory before any size check (TS-9) — single-response OOM primitive; parity with 1.2.
    — **Done when:** Vitest asserts oversized body aborts mid-stream with no leftover file; memory no longer scales with body size (code inspection); `npx tsc --noEmit` passes.
    — **Consumers affected:** all TS nodes with file inputs.
    — **Done:** TS download streams body.getReader() chunks through createWriteStream w/ drain backpressure; mid-stream cap + deadline checks per chunk; partial file unlinked on any failure; whole-body buffering removed; files: typescript/src/base-node.ts, tests/base-node.test.ts; fixes: none

- [x] **1.4** Track and clean partial downloads: in BOTH languages, register `local_path` for cleanup *before* opening the stream (Python `base.py:260-297`; TS only avoids partials today because whole-body buffering defers the write — after 1.3's stream-to-disk rewrite it will produce partials too), so failed/oversized downloads never leave files behind. Also replace the fragile `"local_path" in dir()` checks in `base.py:267-277` error paths.
    — **Why:** `downloaded.append()` runs only after successful validation (PY-9/ARCH-12); combined with 1.2's abort, partials would otherwise accumulate in `/tmp`.
    — **Done when:** Failure-path tests assert downloads dir is empty after every failure mode.
    — **Consumers affected:** `BaseNode.run()` cleanup path (both languages).
    — **Done:** Both languages register local_path for cleanup before validation/streaming: Py downloaded.append before validate_file_input + BaseException unlink in _download_one; TS downloaded.push before validateFileInput + catch->unlinkSync; dir() hack removed from base.py error paths; files: python/canvastekk_workflow_sdk/base.py, typescript/src/base-node.ts; fixes: none

- [x] **1.5** Replace the hardcoded `30.0` / `30_000` download timeouts (`base.py:250`, `base-node.ts:223`) with a TOTAL per-download deadline derived from the node's `timeout_seconds` (Py `httpx` timeout is per-operation — a slow-drip chunk stream never trips it; TS `AbortSignal.timeout` is already total — align Py via elapsed checks in the chunk loop). Budget shared across all file inputs with time reserved for `execute()`. Note `timeout_seconds` defaults to 30 in both manifests (`definition.py:190-194`, `definition.ts:120`) — it is never unset. Additionally propagate cooperative cancellation into the download loop (Py: context-held cancel event checked per chunk; TS: `AbortSignal` threaded through `run()`), so a timed-out `/execute` request stops in-flight downloads; document that `execute()` itself remains non-cancellable (Py thread / TS promise cannot be aborted).
    — **Why:** A 300 s node gets 30 s downloads; a 10 s node gets 30 s downloads (ARCH-6/TS-17) — wrong in both directions.
    — **Done when:** Total-deadline behavior test (stream slower than deadline → abort); cancellation test (timed-out request stops download loop); default deadline documented; existing tests pass unchanged for the 30 s default.
    — **Consumers affected:** all nodes with file inputs.
    — **Done:** TOTAL download deadline = timeout_seconds*0.8 (min 30s) in _download_deadline/downloadDeadline, checked per chunk (defeats Py per-op timeout slow-drip); cooperative cancellation: Py app.py timeout branch creates threading.Event, cancels on wait_for timeout, context.cancel_event checked per chunk; TS app.ts threads AbortController.signal via node.setCancelSignal into context.cancelSignal; execute() remains non-cancellable (documented in docstrings); files: python/canvastekk_workflow_sdk/{app.py,base.py,context.py}, typescript/src/{app.ts,base-node.ts,context.ts}, tests both langs; fixes: NodeExecutionRequest has no execution_id field — used id(exec_request) as _ACTIVE_CANCELS key

### Phase 2 — WorkflowRunner correctness (H3 + shared dirs)

- [ ] **2.1** Fix START seeding with MERGE semantics: in `runner.py:164-193` and `runner.ts:86-95,112-139`, the level-loop control handler computes `outputs = {**resolved_static, **seeded_run_inputs}` instead of the identity `start_handler` re-run clobbering the seed with `{}` (`_control_flow.py:17-22`, `control-flow.ts:24`). Do NOT simply skip the handler — that would discard static inputs declared on the start node and omit `__start__`'s NodeResult.
    — **Why:** Live-verified crash (ARCH-3): the handler re-run overwrites seeded inputs with `{}`, so `resolver.py:83` throws `KeyError` and the exception escapes `run()` entirely — the runner's headline contract `run(spec, inputs={...})` is broken with non-empty inputs in BOTH languages.
    — **Done when:** Regression test in both languages: workflow with wired `start→node→end` and non-empty `inputs` completes and the node receives the seeded values; a static start input coexisting with seeded inputs yields merged outputs.
    — **Consumers affected:** every local `WorkflowRunner` user.

- [ ] **2.2** Wrap per-node `resolve_inputs` in try/except → `NodeResult(status="failed", error=...)` at BOTH resolve sites in each runner — the user-node site (`runner.py:252`, `runner.ts:176`) AND the control-node site (`runner.py:186`, `runner.ts:116`), which is equally outside its try block today.
    — **Why:** One bad `from_output` key currently crashes the whole run instead of failing one node (ARCH-3/TS-16) — inconsistent with how execute errors are already handled per-node.
    — **Done when:** Test with a mis-wired edge yields `WorkflowRunResult` with a failed node, no raised exception — for both a user node and a control node.
    — **Consumers affected:** `WorkflowRunner.run()` callers.

- [ ] **2.3** Give each node a per-node subdirectory for outputs/downloads by default (`run_output_dir/<node_id>/`); document that inter-node file hand-off ALREADY works via absolute-path strings passed through edge output values (`test_workflow_runner.py:460-484` FileWriter/Reader) — per-node subdirs preserve this, so no new hand-off machinery (YAGNI). The only breakage is code globbing the `run_output_dir` root (Py `runner.py:152-157`, `context.py:86-111`; TS `runner.ts:91,117,177`, `context.ts:78-84`).
    — **Why:** Parallel same-level nodes writing the same filename silently overwrite each other, and identically-named file fields race on `{field}_{filename}` downloads (PY-12/TS-13/ARCH-16).
    — **Done when:** Existing absolute-path file-passing tests still pass unchanged; new test proves two parallel nodes writing the same filename don't clobber each other; docs state the absolute-path hand-off contract.
    — **Consumers affected:** local runner users relying on `output_dir` file hand-off — behavior change must be in release notes.

### Phase 3 — Request validation & auth posture (M1/M2/M3)

- [ ] **3.1** Add slug-pattern validators to `run_id`/`node_id` (`request.py:21-22` pydantic; `request.ts:4-5` zod): charset `^[A-Za-z0-9._-]+$` PLUS explicit dot-segment rejection (reject any value containing `..` or matching `^\.$`/`^\.\+$`) — the charset regex alone still permits `..` segments. Defense-in-depth: resolved-path containment (`resolve()` + `is_relative_to(base)`) in `ExecutionContext` is the authoritative check (`context.py:51-53,86-99`; `context.ts:43-48,74-84`).
    — **Why:** Request-controlled identifiers are joined into `/tmp` paths unchecked (PY-3/TS-3/ARCH-7) — `run_id="../../…"` creates arbitrary directories; `output_path("../…")` escapes the sandbox.
    — **Done when:** Tests reject traversal payloads at validation layer in both languages; regex validated against real engine-generated `run_id`/`node_id` formats (rejecting a legitimate ID = 422 on every request); context containment asserts on escapes that pass validation.
    — **Consumers affected:** `/execute` servers, `ExecutionContext` consumers.

- [ ] **3.2** Python: enforce configurable request body size limit as ASGI/FastAPI middleware covering ALL JSON endpoints (`/execute`, `/hook` at `app.py:296` — both call `request.json()` unguarded), matching TS's global `express.json` 50 MB limit (`app.ts:36`); map `ValidationError`/`TypeError` from body parsing to 400/422 instead of 500 (`app.py:174-181,367-376`).
    — **Why:** Unbounded JSON body → memory DoS on Python nodes (ARCH-4); wrong status codes mask client errors as server faults (PY-18).
    — **Done when:** Test posts >limit body → 413 on both `/execute` and `/hook`; malformed/list body → 400/422.
    — **Consumers affected:** Python node servers.

- [ ] **3.3** Auth posture: loud startup warning when no auth is configured in production mode AND when `CANVASTEKK_DEV_MODE` bypass is active (`app.py`, `auth.py:42-43`; `app.ts`, `auth.ts:10-14`); redact unexpected-exception detail from responses (generic message + `execution_id`, full detail logged server-side) (`app.py:367-376`, `base.py:421-429`, `app.ts:206-221`).
    — **Why:** Auth is opt-in with a silent global env bypass (ARCH-5/TS-2/PY-6); `str(exc)` echoes internals/paths to callers (PY-5/TS-7). Breaking change to require auth outright is out of scope — warnings + redaction are the safe increment.
    — **Done when:** Tests capture startup warnings in both modes; error responses contain no exception text beyond a generic message + correlation id.
    — **Consumers affected:** all node servers; external authors (doc update in 5.2).

### Phase 4 — Uploads, resolvers, executors (M4/M5/M6/M9 subset)

- [ ] **4.1** Upload failure surfacing (`uploads.py:94-98`, `uploads.ts:69-71`): PRIMARY fix = fail the execution on upload failure (`status:"fail"` + `error_code:"UPLOAD_FAILED"` — NO response schema change). Per-field upload status is an OPTIONAL additive field, gated on verifying the engine (canvastekk-workflow-engine, the consumer of the `/execute` wire contract) tolerates unknown response fields — `NodeExecutionResponse` (`response.py:14-49`, `response.ts:3-12`) has no room for it today. Add explicit upload timeout + retry: TS switch `readFileSync` to stream upload (`fs.createReadStream` → fetch body — whole-file RAM read is the same OOM primitive as TS-9 for multi-GB outputs); Py `httpx.put` currently inherits the 5 s default timeout (large uploads likely fail today).
    — **Why:** Failed uploads are logged and swallowed — engine receives `status:"pass"` with local `/tmp` paths it can't fetch (PY-10/TS-12/ARCH-9); silent artifact loss. Response-field variant changes the engine wire contract and must be verified cross-repo first.
    — **Done when:** Test with a failing upload URL returns `status:"fail"` with `UPLOAD_FAILED` (no silent-pass); if the optional field is taken, engine response parser verified to accept it; stream-upload test passes without whole-file read.
    — **Consumers affected:** engine consumers of file outputs (wire contract — coordinate per Dependencies).

- [ ] **4.2** TS resolver hardening (`resolver.ts:67,69,94,126`): reject `__proto__`/`constructor`/`prototype` keys in `to_input` and on merge; use `Object.hasOwn` instead of `in`; merge via create-data-property helper instead of assignment.
    — **Why:** Hostile workflow definitions can set the resolved-inputs object's prototype, and `in`-operator lookups "resolve" builtins like `toString` (TS-4/TS-5).
    — **Done when:** Vitest cases: `to_input:"__proto__"` rejected, `"toString"` not resolvable as an output, merge doesn't propagate own `__proto__`.
    — **Consumers affected:** TS `WorkflowRunner` users.

- [ ] **4.3** HttpExecutor: validate remote responses with `NodeExecutionResponseSchema.safeParse` (TS `executor.ts:116-120`, drop bare `as Record` cast); Python: shared `AsyncClient` + bounded response reads + retry/backoff (`executor.py:118-126`); add a small per-level concurrency cap in both runners.
    — **Why:** A non-object JSON response crashes with `TypeError` (TS-15); fresh client per call with no retries is fragile and slow (PY-13); unbounded per-level concurrency overwhelms local and remote resources (TS-14).
    — **Done when:** Unit tests: malformed remote JSON yields a clean node failure; concurrency cap observable (no more than N simultaneous execs).
    — **Consumers affected:** `HttpExecutor` users, local runner.

- [ ] **4.4** Python hygiene batch: `re.fullmatch` for slug/semver patterns (`definition.py:25-26` pattern definitions; `.match()` uses at `definition.py:238,247`); fix `extra` log-field merging (`logging.py:85`); sanitize `node_id` in logger names (`logging.py:164-174`); per-execution temp-dir cleanup on the HTTP server path after upload (`context.py:46-54` / `app.py`).
    — **Why:** `re.match` with `$` accepts trailing newlines into `id`s and registry payloads (PY-15); documented structured log fields never appear (PY-16); logger objects accumulate per unique `node_id` (PY-17); server-side `/tmp/{run}/{node}` dirs are never deleted — disk fill (ARCH-10).
    — **Done when:** `pytest -v` green with new unit tests for each; disk-cleanup test asserts post-request temp removal.
    — **Consumers affected:** registry payloads, node loggers, long-running node servers.

### Phase 5 — Example, docs, parity, release

- [ ] **5.1** Fix `examples/echo_node/handler.py:53-59` to consume `inputs["input_file"]` directly (it's already a local path post-auto-download) and fix its tests to not hit the real network (`tests/test_echo_node.py:33-58,84-114`).
    — **Why:** The canonical example contradicts the SDK's auto-download contract — it double-downloads and would fail without mocks (PY-20/ARCH-16); it's what every external author copies.
    — **Done when:** Echo tests pass with network access disabled (`httpx` transport blocked in test).
    — **Consumers affected:** all readers of `examples/echo_node/`, external authors.

- [ ] **5.2** Sync `docs/EXTERNAL-AUTHOR-GUIDE.md`, `python/README.md`, `typescript/README.md` for behavior changes: URL policy (allowlist hook) + release-notes line that https-only-in-production (1.1) breaks existing `http://` input URLs, default size cap (`CANVASTEKK_MAX_DOWNLOAD_BYTES`), per-node output subdirs (2.3), upload-failure response semantics (4.1), auth startup warnings; add release-notes breaking-change notice for 2.3.
    — **Why:** AGENTS.md mandates doc sync for SDK changes; 2.3 changes observable runner behavior and needs a `BREAKING CHANGE:` footer or migration note.
    — **Done when:** Docs mention each new behavior; grep finds no stale claims contradicting new defaults.
    — **Consumers affected:** external node authors, engine consumers.

- [ ] **5.3** Add cross-language parity test suite: same scenarios (SSRF block, size-cap abort, traversal reject, START-inputs run, upload-failure surfacing) asserted in both `python/tests/` and `typescript/tests/`. Optional improvement: land each scenario per-phase alongside its implementation rather than all at the end, to catch drift earlier.
    — **Why:** Reviews repeatedly found the weaker language exploited (TS RAM buffering vs Py streaming; body-limit gap) — parity tests prevent regression drift (ARCH-16).
    — **Done when:** Both suites green; parity scenario list checked into `PLANS/` or test helper comment.
    — **Consumers affected:** future SDK contributors.

- [ ] **5.4** Final gate: `poetry run ruff check canvastekk_workflow_sdk/ tests/`, `poetry run pytest -v`, `npx tsc --noEmit`, `npx vitest run`, `npx tsup` all green; conventional commits with `fix:`/`feat!:` per the automated release flow (2.3 likely `feat!:` or `BREAKING CHANGE:` footer).
    — **Why:** AGENTS.md verification gates + git-cliff derives the release version from commit types — wrong type = wrong version.
    — **Done when:** All five commands pass on the PR branch; commit messages reviewed for correct types.
    — **Consumers affected:** release pipeline, downstream `canvastekk-workflow-nodes` rebuild (DA-1546 dispatch chain).

---

## Technical Notes

- URL policy baseline is resolve-and-validate before connect + per-hop redirect re-validation; DNS pinning is best-effort per client (httpx needs a custom transport — no first-class per-request IP pinning; undici `Agent connect.lookup` is feasible). See 1.1.
- Default download cap is env-configurable (`CANVASTEKK_MAX_DOWNLOAD_BYTES`, 10 GiB default) — files in this domain are multi-GB point clouds; make cap and download timeout both configurable (TS-17).
- 2.3 is the only intentionally breaking change; keep it isolated in its own commit with `BREAKING CHANGE:` footer on the CODE commit (git-cliff reads commit footers, not PLAN files).
- Vibeguard-masked lines (`__VG_SECRET_ASSIGNMENT_*` in TS token-usage plumbing) were not reviewed verbatim — re-read those files unmasked before touching them.

## Dependencies

- None external. All work is in-repo. Cross-repo coordination with `canvastekk-workflow-engine` belongs to step 4.1 ONLY (the optional per-field response variant changes the `/execute` wire contract the engine consumes); the engine never consumes the local `WorkflowRunner`, so 2.3 needs no engine coordination (dispatch chain per AGENTS.md DA-1546).

## Delivery & Commit Strategy

- **PR 1** — Phases 1–2 (download pipeline + runner crash fixes): all `fix:` commits.
- **PR 2** — Phases 3–4 (validation, auth posture, uploads, executors): `fix:` commits; `feat:` if 4.1's optional response field is taken; `feat:` for 4.3 retries.
- **PR 3** — Phase 5 docs/parity + the isolated 2.3 `feat!:` code commit with `BREAKING CHANGE:` footer. `docs:`/`test:`/`chore:` commits alone do NOT trigger a release — the `fix:`/`feat!:` code commits carry it.
- Most deferrable item if triage is needed: 4.3's per-level concurrency cap tail.

## Risks & Mitigation

| Risk | Mitigation |
|---|---|
| URL policy breaks legit presigned-URL flows (redirects via storage domains) | Allowlist hook + keeplist of storage endpoint suffixes; hop-loop re-validation (not `redirect:"error"`); test against real S3 presigned URLs in staging |
| Mid-stream abort leaves partials on slow networks | 1.4 finally-block cleanup |
| Per-node output subdirs break existing workflows | 5.2 migration note + `BREAKING CHANGE:` footer; absolute-path hand-off contract documented (2.3) |
| Timeout derivation changes behavior of deployed nodes | `timeout_seconds` defaults to 30 in both manifests (never unset); default deadline preserves current 30 s behavior |
| 1.1 https-only-in-production breaks `http://` input URLs | Release-notes migration line in 5.2; allowlist hook as escape hatch |

## Success Metrics

- Zero High findings from this review remain open at merge.
- All regression tests (non-empty inputs run, traversal reject, size-cap abort) present in both languages and green.
- No new test hits the real network.
