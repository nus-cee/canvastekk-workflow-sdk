# PLAN: WorkflowRunner should set output_dir on ExecutionContext for file-writing nodes

**JIRA Ticket**: [DA-1102](https://betekk.atlassian.net/browse/DA-1102)
**Branch**: `DA-1102`
**Issue Type**: Task
**Priority**: Medium

---

## Overview

The `WorkflowRunner` (added in DA-1087 / v0.12.0) creates `ExecutionContext` without setting `output_dir`, which means each node gets an isolated per-node directory under `/tmp/local/{node_id}`. This prevents file-passing between nodes in multi-step pipelines — node A writes to `/tmp/local/nodeA/`, but node B's `output_dir` points to `/tmp/local/nodeB/` and cannot see A's output.

### Problem Detail

In `runner.py`, lines 154 and 218:

```python
context = ExecutionContext(run_id="local", node_id=nid)
```

While `ExecutionContext` does create a fallback directory (it's not `None`), the directories are per-node — not shared across the run. Any node that writes files via `context.output_path("filename.ext")` places them in an isolated directory that downstream nodes cannot access via their own `context.output_dir`.

### Proposed Fix

Add a per-run shared output directory to `WorkflowRunner` that gets passed into every `ExecutionContext`. Nodes in a multi-step pipeline write to and read from the same directory.

---

## Acceptance Criteria

- [x] `WorkflowRunner.__init__` accepts optional `output_dir: Path | None = None`
- [x] When `output_dir` is `None`, a temp directory is created per run
- [x] Every `ExecutionContext` created during the run has `output_dir` set to the shared run directory
- [x] Auto-created temp dirs are cleaned up after run completes (configurable with `cleanup: bool = True`)
- [x] Existing `test_workflow_runner.py` tests continue to pass
- [x] New test: multi-node workflow where node A writes a file and node B reads it
- [x] New test: user-supplied `output_dir` is used and not cleaned up
- [x] New test: auto-created temp dir is cleaned up even on node exception
- [x] `WorkflowRunResult` exposes `output_dir: Path | None`
- [x] Docstring documents HttpExecutor limitation and file collision behavior

---

## Phase 1: Add `output_dir` parameter to `WorkflowRunner.__init__`

**File**: `python/canvastekk_workflow_sdk/workflow/runner.py`

- [x] Add `output_dir: Path | None = None` keyword parameter to `__init__`
- [x] Add `cleanup: bool = True` keyword parameter to `__init__`
- [x] Store both as instance attributes (`self._output_dir`, `self._cleanup`)
- [x] Add `from pathlib import Path` and `import tempfile` to imports (if not already present)

### Current signature:
```python
def __init__(
    self,
    executor: NodeExecutor,
    *,
    error_policy: ErrorPolicy = ErrorPolicy.FAIL_FAST,
) -> None:
```

### Target signature:
```python
def __init__(
    self,
    executor: NodeExecutor,
    *,
    error_policy: ErrorPolicy = ErrorPolicy.FAIL_FAST,
    output_dir: Path | None = None,
    cleanup: bool = True,
) -> None:
```

---

## Phase 2: Create shared output directory and pass to ExecutionContext

**File**: `python/canvastekk_workflow_sdk/workflow/runner.py`

- [x] In `run_async()`, before the level loop:
  - If `self._output_dir` is set, use it directly as the shared run output directory
  - If `self._output_dir` is `None`, create a temp directory via `tempfile.mkdtemp(prefix="wf-runner-")`
  - Track whether the directory was auto-created (for cleanup logic)
- [x] Update both `ExecutionContext` construction sites (line ~154 for control-flow, line ~218 for user nodes) to pass `output_dir=<shared_dir>`
  - The shared dir should be the same `Path` object for all nodes in the run
  - Each `ExecutionContext` still gets its own `run_id` and `node_id`
- [x] After the level loop completes (before returning `WorkflowRunResult`):
  - If directory was auto-created AND `self._cleanup` is `True`, remove the temp directory tree via `shutil.rmtree()`
  - Wrap cleanup in a `try/except` to avoid masking execution errors
- [x] Use a `finally`-style pattern so cleanup happens even on exceptions

### Key design decisions:
- **Shared, not per-node**: All nodes in one run write to the same directory. This enables node A to write `result.csv` and node B to read it via `context.output_dir / "result.csv"`.
- **User-supplied dirs are never cleaned up**: Only auto-created temp dirs are removed.
- **Cleanup is configurable**: `cleanup=False` lets users inspect intermediate outputs after the run.

---

## Phase 3: Tests

**File**: `python/tests/test_workflow_runner.py`

### Verify existing tests still pass:
- [x] Run full existing test suite — all 15 tests in `test_workflow_runner.py` must pass without modification
- [x] Existing tests don't use `output_dir`, so the default behavior (temp dir created and cleaned up) should be transparent

### New tests:

- [x] **`test_file_passing_between_nodes`**: Multi-node workflow where node A writes a file and node B reads it
  - Create a `FileWriterNode` that writes `context.output_path("data.txt").write_text("hello from A")` and returns `{"file_path": str(context.output_path("data.txt"))}`
  - Create a `FileReaderNode` that reads the file from `inputs["file_path"]` and returns `{"content": Path(inputs["file_path"]).read_text()}`
  - Build a linear workflow: START → writer → reader → END
  - Wire `file_path` output from writer to reader
  - Assert `result.final_outputs["content"] == "hello from A"`
  - Assert `result.status == "completed"`

- [x] **`test_user_supplied_output_dir_not_cleaned_up`**: User provides explicit `output_dir`
  - Create a temp directory manually
  - Create `WorkflowRunner(executor, output_dir=my_temp_dir, cleanup=True)`
  - Run a simple workflow
  - Assert the temp directory still exists after run completes
  - Assert node wrote files into the user-supplied directory

- [x] **`test_auto_created_temp_dir_cleaned_up`**: Default behavior cleans up
  - Create `WorkflowRunner(executor)` (no `output_dir`)
  - Run a simple workflow
  - Capture the output_dir path during execution (e.g., via a node that stores `context.output_dir` in its output)
  - Assert the directory does NOT exist after run completes

- [x] **`test_cleanup_false_preserves_temp_dir`**: Cleanup disabled
  - Create `WorkflowRunner(executor, cleanup=False)`
  - Run a simple workflow
  - Capture the output_dir path during execution
  - Assert the directory still exists after run completes

- [x] **`test_auto_temp_dir_cleaned_up_on_exception`**: Cleanup on exception path
  - Create `WorkflowRunner(executor)` (no `output_dir`)
  - Run a workflow containing a `FailingNode`
  - Capture the output_dir path during execution (via a preceding node that stores `context.output_dir` in its output)
  - Assert the directory does NOT exist after run completes (cleanup happens even on failure)

- [x] **`test_result_exposes_output_dir_when_not_cleaned`**: WorkflowRunResult.output_dir
  - Create `WorkflowRunner(executor, output_dir=my_dir)`
  - Run a simple workflow
  - Assert `result.output_dir == my_dir`

- [x] **`test_result_output_dir_none_when_auto_cleaned`**: Auto-cleaned result
  - Create `WorkflowRunner(executor)` (auto temp dir with cleanup)
  - Run a simple workflow
  - Assert `result.output_dir is None` (cleaned up, not exposed)

---

## Architecture

```
WorkflowRunner
  ├── __init__(executor, output_dir=None, cleanup=True)
  ├── run_async(spec, inputs)
  │     ├── resolve output_dir (user-supplied or tempdir)
  │     ├── for each level:
  │     │     ├── control-flow nodes → ExecutionContext(output_dir=shared_dir, ...)
  │     │     └── user nodes → ExecutionContext(output_dir=shared_dir, ...)
  │     └── cleanup tempdir if auto-created and cleanup=True
  └── run(spec, inputs)  # sync wrapper
```

### Changes to existing code:

| File | Change |
|------|--------|
| `python/canvastekk_workflow_sdk/workflow/runner.py` | Add `output_dir`, `cleanup` params; create shared dir; pass to `ExecutionContext`; cleanup logic |
| `python/tests/test_workflow_runner.py` | Add 7 new test methods; 3 new node classes (`FileWriterNode`, `FileReaderNode`, `OutputDirCaptureNode`) |
| `python/canvastekk_workflow_sdk/testing.py` | NEW — `LocalFileServer` test utility for simulating presigned URL downloads |
| `python/tests/test_testing.py` | NEW — 12 tests for `LocalFileServer` including full SDK download pipeline |

### Files NOT changed:
- `context.py` — `ExecutionContext` already supports `output_dir` parameter, no changes needed
- `executor.py` — `NodeExecutor` interface unchanged
- `resolver.py` — Input resolution unchanged
- `models.py` — `WorkflowSpec` unchanged

---

## Dependencies

No new dependencies. Uses:
- `pathlib.Path` (stdlib, already imported)
- `tempfile` (stdlib, new import in runner.py)
- `shutil` (stdlib, new import in runner.py)

---

## Phase 4: Architecture Review Findings (from review session)

- [x] **File collision documentation**: Document that parallel nodes at the same level writing the same filename to the shared directory is undefined behavior — callers must ensure unique filenames or avoid same-level parallel file writes
- [x] **HttpExecutor limitation documentation**: Add docstring note that shared `output_dir` only works with `InProcessExecutor`. `HttpExecutor` calls remote `/execute` endpoints that don't share the local filesystem
- [x] **Cleanup-on-exception test**: Add `test_auto_temp_dir_cleaned_up_on_exception` — verify temp dir is cleaned up even when a node raises mid-run
- [x] **Expose output_dir on WorkflowRunResult**: Add optional `output_dir: Path | None` field to `WorkflowRunResult` so callers can inspect outputs after the run (set to `None` if auto-created and cleaned up)

## Phase 5: Code Review Fixes (from code-review + code-quality subagents)

- [x] **C1: Fix UnboundLocalError risk**: Initialize `status`, `final_outputs`, `duration_ms`, `result_output_dir` before `try` block in `run_async()` — prevents crash if unexpected exception fires before line 283
- [x] **M1: Remove dead code + simplify finally**: Collapsed 3-branch `finally` to 2 branches, removed dead assignment `result_output_dir = run_output_dir` inside `try`
- [x] **M3: Rename builtin shadow**: Renamed `format` → `fmt` in `_Handler.log_message()` to avoid shadowing Python builtin
- [x] **M6+M7: Consolidate duplicate test nodes**: Replaced 3 inline `CaptureDirNode` classes with the module-level `OutputDirCaptureNode` (added `capture_list` constructor param for state capture)
- [x] **M4: Add threading.Lock**: Added `threading.Lock` to `LocalFileServer.start()`/`stop()` to prevent TOCTOU race conditions
- [x] **M5: Simplify serve_files**: Replaced manual `start`/`try`/`finally`/`stop` with delegation to `LocalFileServer.__enter__`/`__exit__`
- [x] **Add binary file test**: `test_serves_binary_file_byte_for_byte` verifies byte-for-byte equality for binary content
- [x] **Add path traversal test**: `test_rejects_path_traversal` verifies `../../etc/passwd` is rejected (403/404)

## Risks & Mitigation

| Risk | Mitigation |
|------|------------|
| Breaking existing tests | Default behavior creates a temp dir transparently — existing tests that don't use `output_dir` are unaffected |
| Temp dir leak on exception | Use try/finally pattern for cleanup, never mask the original error |
| Path collisions in parallel runs | `tempfile.mkdtemp()` creates unique dirs; user-supplied dirs are user's responsibility |
| Node assumes per-node dir | The shared dir is intentional — the whole point is file passing between nodes |
| Parallel nodes writing same filename | Document as undefined behavior; callers must ensure unique filenames |
| HttpExecutor doesn't share local dir | Document that shared `output_dir` only works with `InProcessExecutor` |

---

## Success Metrics

- [x] All existing tests pass (`poetry run pytest python/tests/test_workflow_runner.py -v`)
- [x] 7 new tests pass
- [x] 14 LocalFileServer tests pass (including binary + path traversal)
- [x] Ruff linting clean (`poetry run ruff check canvastekk_workflow_sdk/ tests/`)
- [x] File-writing nodes work in multi-step workflows without manual path management
- [x] Documentation updated (README.md, AGENTS.md, EXTERNAL-AUTHOR-GUIDE.md)
