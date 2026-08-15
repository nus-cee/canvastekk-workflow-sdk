# PLAN-DA-1711 — Security & Robustness Hardening

**Issue**: [DA-1711](https://betekk.atlassian.net/browse/DA-1711) — Security & robustness hardening: download SSRF/size-cap, runner crash, path traversal, auth defaults
**Branch**: `DA-1711`
**Created**: 2026-08-15
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

- [ ] **1.1** Add shared URL policy helper: Python `canvastekk_workflow_sdk/_url.py` and TS `src/url-policy.ts` — validate scheme (`https` in production mode), block resolved loopback/private/link-local/metadata IPs, re-validate each redirect hop (or `redirect:"error"` + explicit hop re-fetch), allowlist hook for storage endpoints.
    — **Why:** Every URL fetch (download + upload) currently trusts the caller completely (PY-1/TS-1/ARCH-1, PY-4/TS-6); one helper fixes all call sites in both languages and keeps parity.
    — **Done when:** Unit tests cover private-IP block, metadata-IP block, redirect-to-internal rejection, https-only in production; `ruff check` + `npx tsc --noEmit` pass.
    — **Consumers affected:** `base.py` download loop, `uploads.py`, `base-node.ts`, `uploads.ts`.

- [ ] **1.2** Python: enforce byte caps mid-stream in `base.py:241-292` — reject early when `Content-Length` exceeds `x-maxSizeBytes`, abort + unlink when running bytes exceed it, apply a default cap (e.g. 1 GiB) when `x-maxSizeBytes` absent.
    — **Why:** Size is validated only after the full body hits disk (PY-2/ARCH-2) — disk-exhaustion primitive; absent `x-maxSizeBytes` fields have no cap at all.
    — **Done when:** Test downloads a body larger than the declared cap and asserts abort before completion + no leftover file; absent-cap field hits the default.
    — **Consumers affected:** all Python nodes with file inputs.

- [ ] **1.3** TypeScript: rewrite download to stream-to-disk (`Readable.fromWeb(resp.body)` → `createWriteStream`) with the same mid-stream cap logic as 1.2, replacing whole-body RAM buffering (`base-node.ts:240-259`).
    — **Why:** TS buffers the entire response in memory before any size check (TS-9) — single-response OOM primitive; parity with 1.2.
    — **Done when:** Vitest asserts oversized body aborts mid-stream with no leftover file; memory no longer scales with body size (code inspection); `npx tsc --noEmit` passes.
    — **Consumers affected:** all TS nodes with file inputs.

- [ ] **1.4** Track and clean partial downloads: register `local_path` for cleanup *before* streaming (Python `base.py:260-297`; TS already cleans on failure — align) so failed/oversized downloads never leave files behind.
    — **Why:** `downloaded.append()` runs only after successful validation (PY-9/ARCH-12); combined with 1.2's abort, partials would otherwise accumulate in `/tmp`.
    — **Done when:** Failure-path tests assert downloads dir is empty after every failure mode.
    — **Consumers affected:** `BaseNode.run()` cleanup path (both languages).

- [ ] **1.5** Derive download timeout from the node's `timeout_seconds` (or a documented default) instead of hardcoded `30.0` / `30_000` (`base.py:250`, `base-node.ts:223`).
    — **Why:** A 300 s node gets 30 s downloads; a 10 s node gets 30 s downloads (ARCH-6/TS-17) — wrong in both directions.
    — **Done when:** Configurable timeout plumbed and documented; existing tests pass with default unchanged for backwards compatibility.
    — **Consumers affected:** all nodes with file inputs.

### Phase 2 — WorkflowRunner correctness (H3 + shared dirs)

- [ ] **2.1** Fix START seeding: in `runner.py:164-193` and `runner.ts:87-139`, skip re-running the `__start__` control handler when its outputs were already seeded from run inputs.
    — **Why:** Live-verified crash (ARCH-3): the handler re-run overwrites seeded inputs with `{}`, so `resolver.py:83` throws `KeyError` and the exception escapes `run()` entirely — the runner's headline contract `run(spec, inputs={...})` is broken with non-empty inputs in BOTH languages.
    — **Done when:** Regression test in both languages: workflow with wired `start→node→end` and non-empty `inputs` completes and the node receives the seeded values.
    — **Consumers affected:** every local `WorkflowRunner` user.

- [ ] **2.2** Wrap per-node `resolve_inputs` in try/except → `NodeResult(status="failed", error=...)` instead of letting `ResolverError`/`KeyError` escape `run()` (`runner.py` level loop, `runner.ts:176`).
    — **Why:** One bad `from_output` key currently crashes the whole run instead of failing one node (ARCH-3/TS-16) — inconsistent with how execute errors are already handled per-node.
    — **Done when:** Test with a mis-wired edge yields `WorkflowRunResult` with a failed node, no raised exception.
    — **Consumers affected:** `WorkflowRunner.run()` callers.

- [ ] **2.3** Give each node a per-node subdirectory for outputs/downloads by default (`run_output_dir/<node_id>/`) with an explicitly documented shared hand-off mechanism for inter-node file passing (Py `runner.py:152-157`, `context.py:86-111`; TS `runner.ts:91,117,177`, `context.ts:78-84`).
    — **Why:** Parallel same-level nodes writing the same filename silently overwrite each other, and identically-named file fields race on `{field}_{filename}` downloads (PY-12/TS-13/ARCH-16).
    — **Done when:** Existing file-passing tests still pass (shared hand-off preserved); new test proves two parallel nodes writing the same filename don't clobber each other.
    — **Consumers affected:** local runner users relying on `output_dir` file hand-off — behavior change must be in release notes.

### Phase 3 — Request validation & auth posture (M1/M2/M3)

- [ ] **3.1** Add slug-pattern validators to `run_id`/`node_id` (`request.py:21-22` pydantic pattern; `request.ts:4-5` zod regex `^[A-Za-z0-9._-]+$`, no `..`), plus defense-in-depth `basename()` + resolved-path containment assertion in `ExecutionContext` (`context.py:51-53,86-99`; `context.ts:43-48,74-84`).
    — **Why:** Request-controlled identifiers are joined into `/tmp` paths unchecked (PY-3/TS-3/ARCH-7) — `run_id="../../…"` creates arbitrary directories; `output_path("../…")` escapes the sandbox.
    — **Done when:** Tests reject traversal payloads at validation layer in both languages; context containment asserts on `Path(filename).name` style escapes.
    — **Consumers affected:** `/execute` servers, `ExecutionContext` consumers.

- [ ] **3.2** Python `/execute`: enforce configurable request body size limit (parity with TS 50 MB) and map `ValidationError`/`TypeError` from body parsing to 400/422 instead of 500 (`app.py:174-181,367-376`).
    — **Why:** Unbounded JSON body → memory DoS on Python nodes (ARCH-4); wrong status codes mask client errors as server faults (PY-18).
    — **Done when:** Test posts >limit body → 413; malformed/list body → 400/422.
    — **Consumers affected:** Python node servers.

- [ ] **3.3** Auth posture: loud startup warning when no auth is configured in production mode AND when `CANVASTEKK_DEV_MODE` bypass is active (`app.py`, `auth.py:42-43`; `app.ts`, `auth.ts:10-14`); redact unexpected-exception detail from responses (generic message + `execution_id`, full detail logged server-side) (`app.py:367-376`, `base.py:421-429`, `app.ts:206-221`).
    — **Why:** Auth is opt-in with a silent global env bypass (ARCH-5/TS-2/PY-6); `str(exc)` echoes internals/paths to callers (PY-5/TS-7). Breaking change to require auth outright is out of scope — warnings + redaction are the safe increment.
    — **Done when:** Tests capture startup warnings in both modes; error responses contain no exception text beyond a generic message + correlation id.
    — **Consumers affected:** all node servers; external authors (doc update in 5.1).

### Phase 4 — Uploads, resolvers, executors (M4/M5/M6/M9 subset)

- [ ] **4.1** Report upload failures in the `/execute` response (per-field upload status) or fail the execution when a declared file output couldn't be uploaded (`uploads.py:94-98`, `uploads.ts:69-71`); add explicit upload timeout + retry (PY-14/TS-11).
    — **Why:** Failed uploads are logged and swallowed — engine receives `status:"pass"` with local `/tmp` paths it can't fetch (PY-10/TS-12/ARCH-9); silent artifact loss.
    — **Done when:** Test with a failing upload URL returns a response that surface the failure; no silent-pass.
    — **Consumers affected:** engine consumers of file outputs.

- [ ] **4.2** TS resolver hardening (`resolver.ts:67,69,94,126`): reject `__proto__`/`constructor`/`prototype` keys in `to_input` and on merge; use `Object.hasOwn` instead of `in`; merge via create-data-property helper instead of assignment.
    — **Why:** Hostile workflow definitions can set the resolved-inputs object's prototype, and `in`-operator lookups "resolve" builtins like `toString` (TS-4/TS-5).
    — **Done when:** Vitest cases: `to_input:"__proto__"` rejected, `"toString"` not resolvable as an output, merge doesn't propagate own `__proto__`.
    — **Consumers affected:** TS `WorkflowRunner` users.

- [ ] **4.3** HttpExecutor: validate remote responses with `NodeExecutionResponseSchema.safeParse` (TS `executor.ts:116-120`, drop bare `as Record` cast); Python: shared `AsyncClient` + bounded response reads + retry/backoff (`executor.py:118-126`); add a small per-level concurrency cap in both runners.
    — **Why:** A non-object JSON response crashes with `TypeError` (TS-15); fresh client per call with no retries is fragile and slow (PY-13); unbounded per-level concurrency overwhelms local and remote resources (TS-14).
    — **Done when:** Unit tests: malformed remote JSON yields a clean node failure; concurrency cap observable (no more than N simultaneous execs).
    — **Consumers affected:** `HttpExecutor` users, local runner.

- [ ] **4.4** Python hygiene batch: `re.fullmatch` for slug/semver patterns (`definition.py:23-24,177,186`); fix `extra` log-field merging (`logging.py:85`); sanitize `node_id` in logger names (`logging.py:164-174`); per-execution temp-dir cleanup on the HTTP server path after upload (`context.py:46-54` / `app.py`).
    — **Why:** `re.match` with `$` accepts trailing newlines into `id`s and registry payloads (PY-15); documented structured log fields never appear (PY-16); logger objects accumulate per unique `node_id` (PY-17); server-side `/tmp/{run}/{node}` dirs are never deleted — disk fill (ARCH-10).
    — **Done when:** `pytest -v` green with new unit tests for each; disk-cleanup test asserts post-request temp removal.
    — **Consumers affected:** registry payloads, node loggers, long-running node servers.

### Phase 5 — Example, docs, parity, release

- [ ] **5.1** Fix `examples/echo_node/handler.py:53-59` to consume `inputs["input_file"]` directly (it's already a local path post-auto-download) and fix its tests to not hit the real network (`tests/test_echo_node.py:33-58,84-114`).
    — **Why:** The canonical example contradicts the SDK's auto-download contract — it double-downloads and would fail without mocks (PY-20/ARCH-16); it's what every external author copies.
    — **Done when:** Echo tests pass with network access disabled (`httpx` transport blocked in test).
    — **Consumers affected:** all readers of `examples/echo_node/`, external authors.

- [ ] **5.2** Sync `docs/EXTERNAL-AUTHOR-GUIDE.md`, `python/README.md`, `typescript/README.md` for behavior changes: URL policy (allowlist hook), default size cap, per-node output subdirs (2.3), upload status in response, auth startup warnings; add release-notes breaking-change notice for 2.3.
    — **Why:** AGENTS.md mandates doc sync for SDK changes; 2.3 changes observable runner behavior and needs a `BREAKING CHANGE:` footer or migration note.
    — **Done when:** Docs mention each new behavior; grep finds no stale claims contradicting new defaults.
    — **Consumers affected:** external node authors, engine consumers.

- [ ] **5.3** Add cross-language parity test suite: same scenarios (SSRF block, size-cap abort, traversal reject, START-inputs run, upload-failure surfacing) asserted in both `python/tests/` and `typescript/tests/`.
    — **Why:** Reviews repeatedly found the weaker language exploited (TS RAM buffering vs Py streaming; body-limit gap) — parity tests prevent regression drift (ARCH-16).
    — **Done when:** Both suites green; parity scenario list checked into `PLANS/` or test helper comment.
    — **Consumers affected:** future SDK contributors.

- [ ] **5.4** Final gate: `poetry run ruff check canvastekk_workflow_sdk/ tests/`, `poetry run pytest -v`, `npx tsc --noEmit`, `npx vitest run`, `npx tsup` all green; conventional commits with `fix:`/`feat!:` per the automated release flow (2.3 likely `feat!:` or `BREAKING CHANGE:` footer).
    — **Why:** AGENTS.md verification gates + git-cliff derives the release version from commit types — wrong type = wrong version.
    — **Done when:** All five commands pass on the PR branch; commit messages reviewed for correct types.
    — **Consumers affected:** release pipeline, downstream `canvastekk-workflow-nodes` rebuild (DA-1546 dispatch chain).

---

## Technical Notes

- URL policy must resolve DNS before connecting AND pin the connection to the resolved IP (httpx transport / undici lookup hook) to block DNS-rebinding.
- Default size cap value (1 GiB proposed) should be a named constant, overridable via the policy hook — hardware/files in this domain are multi-GB point clouds (TS-17: 30 s fixed timeout too small for legitimate large files; make both cap and timeout configurable).
- 2.3 is the only intentionally breaking change; keep it isolated in its own commit with `BREAKING CHANGE:` footer.
- Vibeguard-masked lines (`__VG_SECRET_ASSIGNMENT_*` in TS token-usage plumbing) were not reviewed verbatim — re-read those files unmasked before touching them.

## Dependencies

- None external. All work is in-repo. Coordinate with `canvastekk-workflow-engine` consumers for the 2.3 output-dir layout change (dispatch chain per AGENTS.md DA-1546).

## Risks & Mitigation

| Risk | Mitigation |
|---|---|
| URL policy breaks legit presigned-URL flows (redirects via storage domains) | Allowlist hook + keeplist of storage endpoint suffixes; test against real S3 presigned URLs in staging |
| Mid-stream abort leaves partials on slow networks | 1.4 finally-block cleanup |
| Per-node output subdirs break existing workflows | 5.2 migration note + `BREAKING CHANGE:` footer; keep shared hand-off documented |
| Timeout derivation changes behavior of deployed nodes | Default preserves current 30 s when `timeout_seconds` unset |

## Success Metrics

- Zero High findings from this review remain open at merge.
- All regression tests (non-empty inputs run, traversal reject, size-cap abort) present in both languages and green.
- No new test hits the real network.
