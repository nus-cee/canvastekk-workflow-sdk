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

- [ ] `WorkflowRunner.__init__` accepts optional `output_dir: Path | None = None`
- [ ] When `output_dir` is `None`, a temp directory is created per run
- [ ] Every `ExecutionContext` created during the run has `output_dir` set to the shared run directory
- [ ] Auto-created temp dirs are cleaned up after run completes (configurable with `cleanup: bool = True`)
- [ ] Existing `test_workflow_runner.py` tests continue to pass
- [ ] New test: multi-node workflow where node A writes a file and node B reads it
- [ ] New test: user-supplied `output_dir` is used and not cleaned up

---

## Phase 1: Add `output_dir` parameter to `WorkflowRunner.__init__`

**File**: `python/canvastekk_workflow_sdk/workflow/runner.py`

- [ ] Add `output_dir: Path | None = None` keyword parameter to `__init__`
- [ ] Add `cleanup: bool = True` keyword parameter to `__init__`
- [ ] Store both as instance attributes (`self._output_dir`, `self._cleanup`)
- [ ] Add `from pathlib import Path` and `import tempfile` to imports (if not already present)

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

- [ ] In `run_async()`, before the level loop:
  - If `self._output_dir` is set, use it directly as the shared run output directory
  - If `self._output_dir` is `None`, create a temp directory via `tempfile.mkdtemp(prefix="wf-runner-")`
  - Track whether the directory was auto-created (for cleanup logic)
- [ ] Update both `ExecutionContext` construction sites (line ~154 for control-flow, line ~218 for user nodes) to pass `output_dir=<shared_dir>`
  - The shared dir should be the same `Path` object for all nodes in the run
  - Each `ExecutionContext` still gets its own `run_id` and `node_id`
- [ ] After the level loop completes (before returning `WorkflowRunResult`):
  - If directory was auto-created AND `self._cleanup` is `True`, remove the temp directory tree via `shutil.rmtree()`
  - Wrap cleanup in a `try/except` to avoid masking execution errors
- [ ] Use a `finally`-style pattern so cleanup happens even on exceptions

### Key design decisions:
- **Shared, not per-node**: All nodes in one run write to the same directory. This enables node A to write `result.csv` and node B to read it via `context.output_dir / "result.csv"`.
- **User-supplied dirs are never cleaned up**: Only auto-created temp dirs are removed.
- **Cleanup is configurable**: `cleanup=False` lets users inspect intermediate outputs after the run.

---

## Phase 3: Tests

**File**: `python/tests/test_workflow_runner.py`

### Verify existing tests still pass:
- [ ] Run full existing test suite — all 15 tests in `test_workflow_runner.py` must pass without modification
- [ ] Existing tests don't use `output_dir`, so the default behavior (temp dir created and cleaned up) should be transparent

### New tests:

- [ ] **`test_file_passing_between_nodes`**: Multi-node workflow where node A writes a file and node B reads it
  - Create a `FileWriterNode` that writes `context.output_path("data.txt").write_text("hello from A")` and returns `{"file_path": str(context.output_path("data.txt"))}`
  - Create a `FileReaderNode` that reads the file from `inputs["file_path"]` and returns `{"content": Path(inputs["file_path"]).read_text()}`
  - Build a linear workflow: START → writer → reader → END
  - Wire `file_path` output from writer to reader
  - Assert `result.final_outputs["content"] == "hello from A"`
  - Assert `result.status == "completed"`

- [ ] **`test_user_supplied_output_dir_not_cleaned_up`**: User provides explicit `output_dir`
  - Create a temp directory manually
  - Create `WorkflowRunner(executor, output_dir=my_temp_dir, cleanup=True)`
  - Run a simple workflow
  - Assert the temp directory still exists after run completes
  - Assert node wrote files into the user-supplied directory

- [ ] **`test_auto_created_temp_dir_cleaned_up`**: Default behavior cleans up
  - Create `WorkflowRunner(executor)` (no `output_dir`)
  - Run a simple workflow
  - Capture the output_dir path during execution (e.g., via a node that stores `context.output_dir` in its output)
  - Assert the directory does NOT exist after run completes

- [ ] **`test_cleanup_false_preserves_temp_dir`**: Cleanup disabled
  - Create `WorkflowRunner(executor, cleanup=False)`
  - Run a simple workflow
  - Capture the output_dir path during execution
  - Assert the directory still exists after run completes

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
| `python/tests/test_workflow_runner.py` | Add 4 new test methods; 2 new node classes (`FileWriterNode`, `FileReaderNode`) |

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

## Risks & Mitigation

| Risk | Mitigation |
|------|------------|
| Breaking existing tests | Default behavior creates a temp dir transparently — existing tests that don't use `output_dir` are unaffected |
| Temp dir leak on exception | Use try/finally pattern for cleanup, never mask the original error |
| Path collisions in parallel runs | `tempfile.mkdtemp()` creates unique dirs; user-supplied dirs are user's responsibility |
| Node assumes per-node dir | The shared dir is intentional — the whole point is file passing between nodes |

---

## Success Metrics

- All existing tests pass (`poetry run pytest python/tests/test_workflow_runner.py -v`)
- 4 new tests pass
- Ruff linting clean (`poetry run ruff check canvastekk_workflow_sdk/ tests/`)
- File-writing nodes work in multi-step workflows without manual path management
