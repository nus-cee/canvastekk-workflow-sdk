# PLAN: DA-1302 — Published v0.15.0 Wheel Stale (Missing Model Renames)

**Ticket**: [DA-1302](https://betekk.atlassian.net/browse/DA-1302)
**Created**: 2026-06-14
**Status**: In Progress

---

## Overview

The published GitHub release wheel for SDK v0.15.0 (`canvastekk_workflow_sdk-0.15.0-py3-none-any.whl`) was built **before** commit `f5bb04e` (`feat!: SDK model renames with parent→child naming convention [DA-1230]`). The source code at tag `v0.15.0` is correct, but the wheel artifact is stale.

## Root Cause

| Artifact | Has Renames? |
|---|---|
| SDK source (`main` branch) | Yes |
| SDK source (tag `v0.15.0`) | Yes |
| Published wheel (`v0.15.0` GitHub release) | **No** — built from pre-rename commit |

The wheel was published from an earlier build, not from the tagged commit. The installed package `definition.py` ends at `export_definition()` — missing the class definitions (`WorkflowNodeManifest`, `WorkflowNodeStyles`, `WorkflowNodeRole`) and backward-compat aliases (`NodeDefinition = WorkflowNodeManifest`, etc.).

## Impact

All consumers (e.g., `canvastekk-workflow-nodes`) that import the new canonical names fail:

```python
>>> from canvastekk_workflow_sdk import WorkflowNodeManifest
ImportError: cannot import name 'WorkflowNodeManifest'
```

- 59 mypy errors across 50 handler files in `canvastekk-workflow-nodes`
- Test collection fails for every handler module
- Lambda and EC2 deployments break if handlers import new names

## Acceptance Criteria

- [ ] Corrected wheel published to GitHub release
- [ ] `from canvastekk_workflow_sdk import WorkflowNodeManifest` works from published wheel
- [ ] Backward-compat aliases (`NodeDefinition`, `NodeStyles`, `NodeRole`) also work
- [ ] Consumer repos can `poetry install` and resolve all imports without local rebuild

---

## Phase 1: Verify Source Correctness

- [x] `definition.py` defines `WorkflowNodeManifest` (line 96), `WorkflowNodeStyles` (line 47), `WorkflowNodeRole` (line 89)
- [x] Backward-compat aliases present (lines 353-356):
  ```python
  NodeDefinition = WorkflowNodeManifest
  WorkflowNodeDefinition = WorkflowNodeManifest
  NodeStyles = WorkflowNodeStyles
  NodeRole = WorkflowNodeRole
  ```
- [x] `__init__.py` imports and exports both old and new names
- [x] `__all__` includes both old and new names
- [x] `__version__ = "0.15.0"`

## Phase 2: Rebuild & Republish Wheel

### Option A: Replace stale v0.15.0 wheel (preferred — no consumer changes)

- [ ] Build wheel from `main`:
  ```bash
  cd python && poetry build
  ```
- [ ] Verify wheel contains renamed classes:
  ```bash
  unzip -p dist/canvastekk_workflow_sdk-0.15.0-py3-none-any.whl \
    canvastekk_workflow_sdk/definition.py | grep WorkflowNodeManifest
  ```
- [ ] Delete old wheel asset from GitHub release v0.15.0
- [ ] Upload corrected wheel to GitHub release v0.15.0

### Option B: Publish v0.15.1 (requires consumer pyproject.toml bump)

- [ ] Bump version in `python/pyproject.toml` to `0.15.1`
- [ ] Update `__version__` in `__init__.py`
- [ ] Commit: `chore(release): prepare v0.15.1`
- [ ] Tag: `git tag v0.15.1`
- [ ] Build and push tag
- [ ] Create GitHub release v0.15.1 with wheel
- [ ] Update `canvastekk-workflow-nodes` `pyproject.toml` to `v0.15.1`

## Phase 3: Verify Published Wheel

- [ ] Fresh `pip install` from GitHub release URL resolves new names
- [ ] `from canvastekk_workflow_sdk import WorkflowNodeManifest` works
- [ ] `from canvastekk_workflow_sdk.definition import WorkflowNodeStyles, RetryConfig` works
- [ ] `NodeDefinition` alias still works for backward compat
- [ ] Consumer repo (`canvastekk-workflow-nodes`) passes test collection

---

## Dependencies

- **Origin**: [DA-1230](https://betekk.atlassian.net/browse/DA-1230) — SDK model renames (commit `f5bb04e`)
- **Affected**: [DA-1299](https://betekk.atlassian.net/browse/DA-1299) — workflow-nodes env var documentation (blocked by import failures)
- **Affected**: `canvastekk-workflow-nodes` — 59 mypy errors, broken test collection

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Replacing published wheel breaks CI caches | Use Option B (v0.15.1) for cache-busting |
| Consumers pin exact wheel hash | Unlikely — pinned by URL version, not hash |
| Other consumers besides workflow-nodes affected | Check `canvastekk-workflow-engine`, `canvastekk-floor-flatness-app`, etc. |

## Success Metrics

- Zero `ImportError` for `WorkflowNodeManifest` across all consumer repos
- All consumer handler tests collect and pass
- mypy errors in `canvastekk-workflow-nodes` reduced from 59 to 0 (for SDK naming issues)
