# PLAN: Return freed heap to OS at end of node invocation (DA-3009)

**Branch**: feat/DA-3009
**Issue**: https://betekk.atlassian.net/browse/DA-3009
**Base**: main

## Acceptance Criteria

- [x] Trim invoked exactly once per `/execute` request that passes validation — once per execution, on both success and failure of the execution section. Validation-rejected requests (400/422) return before the execution section, allocate no execution heap, and do not trim (pinned by test; requirements relay DA-3009 resolution).
- [x] `CANVASTEKK_SDK_MEMORY_TRIM=0` disables it; non-glibc platforms silently no-op
- [x] Unit tests cover loader branches (found / fallback / missing symbol / opt-out / exception swallowed)
- [x] Manual verification: after a heavy allocation + release, RSS returns near baseline (local repro showed 628 → 179 MB after trim)
- [x] Conventional commit type `feat(python):` so git-cliff mints a minor version bump

## Dependency & Consumer Map

| Node (file/module) | Depends on (must precede) | Consumers (who depends on this) | Change risk |
|---------------------|---------------------------|---------------------------------|-------------|
| `python/canvastekk_workflow_sdk/app.py` (`_release_freed_heap` + `execute()` wiring) | — | every node lambda using `create_app`/`create_authed_app` (47 workflow-nodes + 4 report-service + 26 ifc python handlers) | low (additive, env-gated, exception-guarded) |
| `python/tests/test_app.py` (or new `test_memory_trim.py`) | helper exists | CI coverage gate | low |

Consumer map is thin (no in-repo downstream modules — consumers are external node repos, unchanged). Code review backstops; no architecture review selected.

## Implementation Phases

### Phase 1: Trim helper + execute() wiring

- [x] **1.1** Add module imports (`gc`, `sys`) and `_release_freed_heap()` helper in `python/canvastekk_workflow_sdk/app.py`: memoized `ctypes.CDLL` load (`ctypes.util.find_library("c")` → fallback `"libc.so.6"`), `hasattr(libc, "malloc_trim")` guard, `sys.platform != "linux"` early return, `CANVASTEKK_SDK_MEMORY_TRIM=0` opt-out, all exceptions swallowed at debug level.
    — **Done:** helper `_release_freed_heap` added (memoized CDLL, find_library→libc.so.6 fallback, hasattr guard, linux-only, env opt-out); files: python/canvastekk_workflow_sdk/app.py; fixes: none
    — **Why:** the helper must exist and be import-safe on every platform before the handler can call it.
    — **Done when:** `python3 -c "from canvastekk_workflow_sdk.app import _release_freed_heap"` succeeds and ruff passes.
    — **Consumers affected:** none yet (helper unused until 1.2).

- [x] **1.2** Wrap the `execute()` execution section — from `timeout = node.definition.timeout_seconds` through `return response` — in `try: … finally: _release_freed_heap()` so both success and exception paths trim exactly once. Early 400/422 validation returns stay outside (nothing allocated).
    — **Done:** execution section (timeout → return response) wrapped in try/finally with single trim; files: python/canvastekk_workflow_sdk/app.py; fixes: initial wrap script dropped the `return response` line (slice bug) — caught by gate, restored
    — **Why:** heavy allocations happen inside `node.run()`; both success and error unwinds leave freed-but-retained glibc heap that poisons warm Lambda sandboxes (DA-3009 evidence: 8 MB of 453 MB returned by gc alone).
    — **Done when:** `rg -n "_release_freed_heap" python/canvastekk_workflow_sdk/app.py` shows the call inside a `finally:` reached by both the success `return response` and exception propagation.
    — **Consumers affected:** all node lambdas (behavior: one extra gc+trim after each execution; env-gated opt-out).

- [x] **1.3** Add unit tests (new `python/tests/test_memory_trim.py`): opt-out env skips trim; non-linux platform skips; glibc path calls `malloc_trim` once after `gc.collect` (fake CDLL via monkeypatch); missing `malloc_trim` symbol no-ops; exception inside helper is swallowed. Plus one integration-flavored test: a trivial node app served via the SDK app factory triggers the helper exactly once per `/execute` call (monkeypatched helper counter).
    — **Done:** 10 tests in python/tests/test_memory_trim.py (5 loader branches + fallback + exactly-once success/error/validation-short-circuit + real-glibc smoke); files: python/tests/test_memory_trim.py; fixes: fake-libc lambda never counted calls (bound method now); error path asserts status=fail body (SDK returns HTTP 200 fail envelope)
    — **Why:** AC demands branch coverage and exactly-once semantics; the exactly-once test guards the finally placement against future refactors.
    — **Done when:** `poetry run pytest tests/test_memory_trim.py -v` green with all five loader branches + exactly-once assertion.
    — **Consumers affected:** CI coverage gate.

### Phase 2: Verification + exit gate

- [x] **2.1** Manual RSS verification per AC: script allocates ~500 MB, drops it, runs `_release_freed_heap()`, asserts RSS after trim is ≥100 MB lower than before (run with repo venv; record numbers in PLAN trace).
    — **Done:** arena-retention repro through the SDK helper — 10k×64KB C buffers: peak 673.6 MB, after free+gc 672.6 MB (1 MB returned by gc), after trim 46.9 MB (**625.7 MB returned to OS**); fixes: first repro used a single 500 MB mmap allocation (auto-unmapped, no retention) — redone with sub-mmap-threshold allocations
    — **Why:** the unit tests prove call semantics; this proves the actual OS-level effect the ticket exists for.
    — **Done when:** recorded before/after RSS numbers show the drop; command output pasted into the PLAN trace block.
    — **Consumers affected:** none.

- [x] **2.2** Exit gate (full): `poetry run ruff check canvastekk_workflow_sdk/ tests/` + `poetry run pytest -v --cov=canvastekk_workflow_sdk` (mirrors `.github/workflows/ci-python.yml`). Append gate memo `GATE <short-sha> tier=full` to the PLAN trace block.
    — **Done:** ruff clean (whole sdk + tests), pytest 729 passed, coverage 84%; files: gate memo below; fixes: none
    — **Why:** pipeline Step 10 requires a green `tier=full` memo on the final pushed SHA.
    — **Done when:** both commands exit 0 and the memo line is appended.
    — **Consumers affected:** PR CI parity.

## Technical Notes

- Insertion point verified on origin/main v0.29.2: `execute()` handler body, `python/canvastekk_workflow_sdk/app.py`.
- CDLL handle memoized in a module global; ctypes imported lazily inside the helper so non-linux keeps import cost at zero.
- gc.collect() cost scales with live-object count; it runs after the response is built but before return — acceptable billed-duration cost, opt-out available.
- No TypeScript changes (V8 returns JS heap; WASM tracked in DA-3010).

## Dependencies

None (first ticket of the wave). Consumers: DA-3013/3014/3015/3016/3017 pin bumps (blocked-by this ticket).

## Risks & Mitigation

| Risk | Mitigation |
|------|------------|
| `ctypes.CDLL` fails on exotic platforms | Exception guard + debug log; silent no-op |
| gc pause on huge heaps adds latency | Runs post-response-build, env opt-out; documented |
| Reindent of `execute()` section creates noisy diff | Mechanical, single concern; code review with computed diff |

## Trace

GATE 9a1f2c3 tier=light lint=t typecheck=n.a. unit=t e2e=n.a. (phase 1 — scoped: app.py, test_memory_trim.py, test_app.py; 81 passed)
WORK LOG: phase 1 is pure additive backend — light tier selected per plan; full gate at 2.2.
GATE 4f1e314 tier=full lint=t typecheck=n.a. build=n.a. unit=t(729) e2e=n.a. (backend-only; no Playwright in repo)
WORK LOG: RSS verification numbers (2.1) recorded above — AC met (625.7 MB ≥ 100 MB threshold).
WORK LOG: code review APPROVE (0 Major, 7 NOTE) — fixes applied: memoization dlopen-once assertion, timeout-path exactly-once test (production scenario), benign-race docstring note, AC1 amended per requirements relay, dead .gitignore anchor removed. AC checkboxes ticked.
GATE d1d8c70 tier=full lint=t typecheck=n.a. build=n.a. unit=t e2e=n.a. (re-run after review fixes)
