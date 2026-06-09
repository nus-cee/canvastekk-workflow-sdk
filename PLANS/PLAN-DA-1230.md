# PLAN-DA-1230: SDK model updates for uniform node design (DA-1227 follow-up)

> **JIRA Ticket:** [DA-1230](https://betekk.atlassian.net/browse/DA-1230)
> **Branch:** `feature/DA-1230`
> **Status:** In Progress — Phases 1-5D complete, Phase 6-8 pending
> **Created:** 2026-06-09
> **Updated:** 2026-06-09
> **Version Bump:** **Minor** (pre-production, all changes breaking but acceptable)

## Overview

Implement all DA-1230 ticket items as breaking changes across both Python and TypeScript SDKs, plus align naming conventions with the workflow engine using a parent→child pattern. The engine handles backward compatibility on its side; the SDK drives the migration — all nodes must upgrade to the new model contracts.

### Breaking Changes Summary

| # | Change | Status |
|---|--------|--------|
| 1 | Add `NodeRole` enum + `role` field, remove `is_control_flow` | Done |
| 2 | Rename `WorkflowNode` → `WorkflowDefinitionNode`, add `workflow_node_id`/`config_schema`, make `slug` optional | Done |
| 3 | Remove `ResolutionStrategy`, rename `WorkflowEdge` → `WorkflowEdgeDefinition` | Done |
| 4 | Rename `WorkflowSpec` → `WorkflowDefinitionSpec`, remove `name` | Done |
| 5 | Rename `WorkflowNodeDefinition` → `WorkflowNodeManifest` | Done |
| 5C | Code review fixes (WARN-1, WARN-2, NOTE-4 through NOTE-9) | Done |
| 5D | Rename sub-components: `NodeStyles` → `WorkflowNodeStyles`, `NodeRole` → `WorkflowNodeRole` | Done |
| 6 | Documentation updates | Pending |
| 7 | Version bump | Pending |
| 8 | Final verification | Pending |

### Naming Convention (Parent→Child)

All models follow a parent→child naming pattern aligned with the workflow engine:

| Artifact | Name | Parent Concept |
|----------|------|----------------|
| Node registration manifest | `WorkflowNodeManifest` | `WorkflowNodeRegistry` (engine) |
| Node role enum | `WorkflowNodeRole` | `WorkflowNodeManifest` |
| Node styles model | `WorkflowNodeStyles` | `WorkflowNodeManifest` |
| Workflow DAG | `WorkflowDefinition` | — |
| Node in DAG | `WorkflowDefinitionNode` | `WorkflowDefinition` |
| Edge in DAG | `WorkflowEdgeDefinition` | `WorkflowDefinition` |
| Full spec | `WorkflowDefinitionSpec` | `WorkflowDefinition` |

### Backward-Compat Aliases

All old names kept as type aliases for transition:

| Old Name | New Name | Alias |
|----------|----------|-------|
| `NodeDefinition` | `WorkflowNodeManifest` | `NodeDefinition = WorkflowNodeManifest` |
| `WorkflowNodeDefinition` | `WorkflowNodeManifest` | `WorkflowNodeDefinition = WorkflowNodeManifest` |
| `WorkflowNode` | `WorkflowDefinitionNode` | `WorkflowNode = WorkflowDefinitionNode` |
| `WorkflowEdge` | `WorkflowEdgeDefinition` | `WorkflowEdge = WorkflowEdgeDefinition` |
| `WorkflowSpec` | `WorkflowDefinitionSpec` | `WorkflowSpec = WorkflowDefinitionSpec` |
| `NodeStyles` | `WorkflowNodeStyles` | `NodeStyles = WorkflowNodeStyles` |
| `NodeRole` | `WorkflowNodeRole` | `NodeRole = WorkflowNodeRole` |

### Excluded Fields

> `is_singleton` and `is_control_flow` excluded from SDK. Both are engine-internal:
> - `is_singleton`: Only `__start__` gets `True`, hardcoded in engine seeding. Never enforced.
> - `is_control_flow`: All SDK nodes are HTTP (62 of 66 nodes in live registry). Only engine built-ins (`__start__`, `__end__`, `if`, `stop-error`) are `in-process`. Engine derives `invoke_type` from its own registry.
> - Both fields remain in engine DB with defaults `False` for SDK-registered nodes.

---

## Phase 1: NodeRole enum + role field, remove is_control_flow — DONE

- [x] Python: Add `NodeRole` `StrEnum` (`start`, `end`, `error_gate`, `operation`) to `definition.py`
- [x] Python: Add `role: NodeRole = NodeRole.OPERATION` field to manifest class
- [x] Python: Remove `is_control_flow` from source files (definition.py, base.py, registry.py)
- [x] Python: Update `__init__.py` re-exports — add `NodeRole`
- [x] Python: Update `registry.py` — include `node_role` in registration payload
- [x] Python: Update test files (test_definition.py, test_base.py, test_file_download.py, test_observability.py, test_workflow_runner.py, test_testing.py)
- [x] TypeScript: Add `NodeRole` type and `nodeRoleSchema` to `definition.ts`
- [x] TypeScript: Add `role: nodeRoleSchema` to manifest schema
- [x] TypeScript: Remove `is_control_flow` from source files (definition.ts, base-node.ts, registry.ts)
- [x] TypeScript: Update `index.ts` re-exports — add `NodeRole`
- [x] TypeScript: Update `registry.ts` — include `role` in registration
- [x] TypeScript: Update test files (definition.test.ts, base-node.test.ts, registry.test.ts, app.test.ts)
- [x] All tests passing: Python 542, TypeScript 204

**Fixed in Phase 5A.3:** `app.py:258` docstring `is_control_flow` → `role`

---

## Phase 2: WorkflowDefinitionNode — add fields, make slug optional — DONE

- [x] Python: Rename `WorkflowNode` → `WorkflowDefinitionNode` in `workflow/models.py`
- [x] Python: Add `workflow_node_id: str | None = None`
- [x] Python: Make `slug: str | None = None` (was required)
- [x] Python: Add `config_schema: dict[str, Any] | None = None`
- [x] Python: Update `builder.py` — `add_start()`, `add_end()`, `add_node()` accept new params
- [x] Python: Update `workflow/__init__.py` and top-level `__init__.py` exports
- [x] Python: Update test files (test_workflow_models.py, test_workflow_builder.py, test_workflow_runner.py, test_workflow_validation.py)
- [x] TypeScript: Rename `WorkflowNode` → `WorkflowDefinitionNode` in `workflow/models.ts`
- [x] TypeScript: Add `workflow_node_id`, `config_schema` fields; make `slug` optional
- [x] TypeScript: Update `builder.ts` — accept new params
- [x] TypeScript: Update `workflow/index.ts` and top-level `index.ts` exports
- [x] TypeScript: Update test files (workflow-builder.test.ts, workflow-runner.test.ts, workflow-validation.test.ts, workflow-level.test.ts)
- [x] All tests passing

---

## Phase 3: Remove ResolutionStrategy, rename WorkflowEdgeDefinition — DONE

- [x] Python: Remove `ResolutionStrategy` enum from `workflow/models.py`
- [x] Python: Remove `resolution_strategy` field from edge class
- [x] Python: Rename `WorkflowEdge` → `WorkflowEdgeDefinition`
- [x] Python: Simplify `resolver.py` — remove all strategy matching, always use dot-path
- [x] Python: Remove `resolution_strategy` from `connect()` in `builder.py`
- [x] Python: Update `workflow/__init__.py` and top-level `__init__.py` — remove `ResolutionStrategy`, add `WorkflowEdgeDefinition`
- [x] Python: Update test files (test_workflow_models.py, test_workflow_builder.py, test_workflow_runner.py, test_workflow_validation.py)
- [x] TypeScript: Remove `ResolutionStrategy` type from `workflow/models.ts`
- [x] TypeScript: Remove `resolutionStrategy` field from edge interface
- [x] TypeScript: Rename `WorkflowEdge` → `WorkflowEdgeDefinition`
- [x] TypeScript: Simplify resolver — remove strategy matching
- [x] TypeScript: Remove `resolutionStrategy` from `connect()` in `builder.ts`
- [x] TypeScript: Update `workflow/index.ts` and top-level `index.ts` exports
- [x] TypeScript: Update test files (workflow-builder.test.ts, workflow-runner.test.ts, workflow-validation.test.ts, workflow-resolver.test.ts, workflow-level.test.ts)
- [x] All tests passing

---

## Phase 4: Rename WorkflowDefinitionSpec, remove name — DONE

- [x] Python: Rename `WorkflowSpec` → `WorkflowDefinitionSpec` in `workflow/models.py`
- [x] Python: Remove `name` field
- [x] Python: Update `builder.py` — `build()` returns `WorkflowDefinitionSpec`
- [x] Python: Update `runner.py`, `resolver.py`, `validation.py`, `level.py` — all references
- [x] Python: Update `workflow/__init__.py` and top-level `__init__.py` exports
- [x] Python: Update test files (test_workflow_models.py, test_workflow_builder.py, test_workflow_runner.py, test_workflow_validation.py)
- [x] TypeScript: Rename `WorkflowSpec` → `WorkflowDefinitionSpec` in `workflow/models.ts`
- [x] TypeScript: Remove `name` field
- [x] TypeScript: Update `builder.ts`, `runner.ts`, `resolver.ts`, `validation.ts`, `level.ts`, `executor.ts`
- [x] TypeScript: Update `workflow/index.ts` and top-level `index.ts` exports
- [x] TypeScript: Update test files (workflow-builder.test.ts, workflow-runner.test.ts, workflow-validation.test.ts, workflow-resolver.test.ts, workflow-level.test.ts)
- [x] All tests passing

---

## Phase 5A: Complete Python WorkflowNodeManifest rename — DONE

The class rename from `WorkflowNodeDefinition` → `WorkflowNodeManifest` was applied to source files in Phase 5, but **two critical gaps remain**:

### 5A.1 Add missing backward-compat alias

- [x] In `definition.py`: Add `WorkflowNodeDefinition = WorkflowNodeManifest` after existing `NodeDefinition = WorkflowNodeManifest` (line 353)
  - Current state: Only `NodeDefinition` alias exists. `WorkflowNodeDefinition` alias is missing.
  - 6 test files import `WorkflowNodeDefinition` from the top-level package — they will get `ImportError` without this alias.

### 5A.2 Re-export alias from package root

- [x] In `__init__.py`: Add `WorkflowNodeDefinition` to the import block from `definition` (line 57-65)
- [x] In `__init__.py`: Add `"WorkflowNodeDefinition"` to `__all__` list (around line 167)

### 5A.3 Fix stale docstring

- [x] In `app.py`: Fix line 258 docstring — replace `is_control_flow` with `role` in the manifest field list
  - Current: `"- Metadata (category, timeout, is_control_flow)"`
  - Should be: `"- Metadata (category, timeout, role)"`

### 5A.4 Update test files still using old name

These 6 test files still import `WorkflowNodeDefinition`. After the alias is added (5A.1-5A.2), they will work via alias. Decide: update to `WorkflowNodeManifest` or leave on alias?

- [x] `python/tests/test_validation.py`
- [x] `python/tests/test_middleware.py`
- [x] `python/tests/test_main.py`
- [x] `python/tests/test_router.py`
- [x] `python/tests/test_app.py`
- [x] `python/tests/test_registry.py`

### 5A.5 Verify

- [x] Run `poetry run ruff check canvastekk_workflow_sdk/ tests/` — must pass
- [x] Run `poetry run pytest -v` — all tests pass (542+)
- [x] Verify `from canvastekk_workflow_sdk import WorkflowNodeManifest, WorkflowNodeDefinition, NodeDefinition` all work

---

## Phase 5B: TypeScript WorkflowNodeManifest rename — DONE

### 5B.1 Rename schema and type in definition.ts

- [x] Rename `WorkflowNodeDefinitionSchema` → `WorkflowNodeManifestSchema` (line 86)
- [x] Rename `type WorkflowNodeDefinition` → `type WorkflowNodeManifest` (line 129)
- [x] Update `NodeDefinition` alias: `type NodeDefinition = WorkflowNodeManifest` (line 131, currently `= WorkflowNodeDefinition`)
- [x] Add backward-compat alias: `type WorkflowNodeDefinition = WorkflowNodeManifest`
- [x] Update function signatures that reference `WorkflowNodeDefinition`:
  - `getNodeId()` (line 133)
  - `getFileInputFields()` (line 145)
  - `getFileOutputFields()` (line 163)
  - `validateFileInput()` (line 186)

### 5B.2 Update base-node.ts

- [x] Update import: `import type { WorkflowNodeManifest } from "./definition.js"` (line 7)
- [x] Update import: `import { WorkflowNodeManifestSchema, getFileInputFields, validateFileInput } from "./definition.js"` (line 8)
- [x] Update class docstring reference (line 110)
- [x] Update `abstract definition: WorkflowNodeManifest` (line 136)
- [x] Update `private _validatedDefinition: WorkflowNodeManifest | null` (line 140)
- [x] Update `get nodeDefinition(): WorkflowNodeManifest` (line 146)
- [x] Update `protected getDefinition(): WorkflowNodeManifest` (line 154)
- [x] Update `WorkflowNodeManifestSchema.parse(...)` (line 156)

### 5B.3 Update registry.ts

- [x] Update import: `import type { WorkflowNodeManifest } from "./definition.js"` (line 3)
- [x] Update `buildRegistryPayload` param type (line 48)
- [x] Update `registerNode` param type (line 124)
- [x] Update `exportDefinition` param type (line 214)

### 5B.4 Update index.ts

- [x] Rename export: `WorkflowNodeManifestSchema` (line 19, currently `WorkflowNodeDefinitionSchema`)
- [x] Rename export: `type WorkflowNodeManifest` (line 28, currently `type WorkflowNodeDefinition`)
- [x] Add `type WorkflowNodeDefinition` backward-compat export

### 5B.5 Update test files

- [x] `tests/definition.test.ts`:
  - Rename import `WorkflowNodeDefinitionSchema` → `WorkflowNodeManifestSchema` (line 3)
  - Update describe block name (line 31)
  - Update all `WorkflowNodeDefinitionSchema.parse(...)` calls (lines 33, 46, 52, 58, 64, 70, 84, 97, 116, 128, 136, 146, 164, 179, 186, 202, 221, 238)
  - Update test description strings (lines 266, 271)
- [x] `tests/app.test.ts`:
  - Fix import: `import type { WorkflowNodeManifest } from "../src/definition.js"` (line 5, currently broken `WorkflowWorkflowNodeDefinition`)
  - Update all `definition: WorkflowNodeDefinition` → `definition: WorkflowNodeManifest` (lines 10, 31)
- [x] `tests/registry.test.ts`:
  - Fix import: `import type { WorkflowNodeManifest } from "../src/definition.js"` (line 8, currently broken `WorkflowWorkflowNodeDefinition`)
  - Update `const testDef: WorkflowNodeDefinition` → `const testDef: WorkflowNodeManifest` (line 10)
- [x] `tests/base-node.test.ts`:
  - Fix import: `import type { WorkflowNodeManifest } from "../src/definition.js"` (line 3, currently broken `WorkflowWorkflowNodeDefinition`)
  - Update all `definition: WorkflowNodeDefinition` → `definition: WorkflowNodeManifest` (lines 9, 32, 47)

### 5B.6 Verify

- [x] Run `npx tsc --noEmit` — must pass
- [x] Run `npx vitest run` — all tests pass (204+)
- [x] Verify imports: `import { WorkflowNodeManifestSchema, type WorkflowNodeManifest, type WorkflowNodeDefinition } from "canvastekk-workflow-sdk"` all resolve

---

## Phase 5C: Code Review Fixes — DONE

Code review identified 0 critical, 3 major, 7 minor issues. All fixed:

- [x] WARN-1: Deduplicate `__all__` in `python/__init__.py` — 8 duplicate entries removed
- [x] WARN-2: Remove unused `name` param from `WorkflowBuilder.__init__` — both Python and TypeScript
- [x] NOTE-4: Wrap resolver `StopIteration` with descriptive `KeyError` in `resolver.py`
- [x] NOTE-5: Move backward-compat aliases above `__all__` in `python/workflow/__init__.py`
- [x] NOTE-6: Rename `nodeRoleSchema` → `NodeRoleSchema` in TypeScript
- [x] NOTE-7: Remove `config_schema` duplication from TS `addStart()` — was in both `inputs` and top-level field
- [x] NOTE-8: Remove redundant re-imports in `test_definition.py`
- [x] NOTE-9: Add backward-compat alias tests in TypeScript (2 new tests)
- [x] All tests passing: Python 542, TypeScript 205
- [x] `ruff check` clean, `tsc --noEmit` clean

---

## Phase 5D: Sub-Component Renames (WorkflowNodeStyles, WorkflowNodeRole) — DONE

Sub-component types on `WorkflowNodeManifest` follow the `WorkflowNode*` parent stem.

### 5D.1 Python: Rename `NodeStyles` → `WorkflowNodeStyles`

- [x] In `definition.py`: Rename class `NodeStyles` → `WorkflowNodeStyles` (line 47)
- [x] In `definition.py`: Add backward-compat alias `NodeStyles = WorkflowNodeStyles`
- [x] In `definition.py`: Update `WorkflowNodeManifest.styles` field type annotation (line 165)
- [x] In `__init__.py`: Add `WorkflowNodeStyles` to imports and `__all__`; keep `NodeStyles` alias export

### 5D.2 Python: Rename `NodeRole` → `WorkflowNodeRole`

- [x] In `definition.py`: Rename class `NodeRole` → `WorkflowNodeRole` (line 89)
- [x] In `definition.py`: Add backward-compat alias `NodeRole = WorkflowNodeRole`
- [x] In `definition.py`: Update `WorkflowNodeManifest.role` field type annotation (line 159)
- [x] In `__init__.py`: Add `WorkflowNodeRole` to imports and `__all__`; keep `NodeRole` alias export

### 5D.3 TypeScript: Rename `NodeStyles` → `WorkflowNodeStyles`

- [x] In `definition.ts`: Rename `NodeStylesSchema` → `WorkflowNodeStylesSchema` (line 39)
- [x] In `definition.ts`: Rename `type NodeStyles` → `type WorkflowNodeStyles` (line 44)
- [x] In `definition.ts`: Add backward-compat aliases: `type NodeStyles`, `const NodeStylesSchema`
- [x] In `definition.ts`: Update `WorkflowNodeManifestSchema` styles field reference (line 105)
- [x] In `index.ts`: Add `WorkflowNodeStylesSchema`, `type WorkflowNodeStyles`; keep `NodeStyles` alias

### 5D.4 TypeScript: Rename `NodeRole` → `WorkflowNodeRole`

- [x] In `definition.ts`: Rename `NodeRoleSchema` → `WorkflowNodeRoleSchema` (line 57)
- [x] In `definition.ts`: Rename `type NodeRole` → `type WorkflowNodeRole` (line 60)
- [x] In `definition.ts`: Add backward-compat aliases: `type NodeRole`, `const NodeRoleSchema`
- [x] In `definition.ts`: Update `WorkflowNodeManifestSchema` role field reference (line 104)
- [x] In `index.ts`: Add `WorkflowNodeRoleSchema`, `type WorkflowNodeRole`; keep `NodeRole` alias

### 5D.5 Verify

- [x] Run `poetry run ruff check canvastekk_workflow_sdk/ tests/` — passed
- [x] Run `poetry run pytest -v` — 542 passed
- [x] Run `npx tsc --noEmit` — passed
- [x] Run `npx vitest run` — 205 passed

---

## Phase 6: Documentation — PENDING

### 6.1 Python README

- [ ] `python/README.md`:
  - Remove `is_control_flow` from example code (line 782) and field table (line 795)
  - Add `role` field with `NodeRole` enum documentation
  - Replace `WorkflowNodeDefinition` → `WorkflowNodeManifest`
  - Replace `WorkflowNode` → `WorkflowDefinitionNode` (DAG context)
  - Replace `WorkflowEdge` → `WorkflowEdgeDefinition`
  - Replace `WorkflowSpec` → `WorkflowDefinitionSpec`
  - Update `WorkflowBuilder` API docs: `connect()` drops `resolution_strategy`
  - Document new fields: `workflow_node_id`, `config_schema`

### 6.2 TypeScript README

- [ ] `typescript/README.md`:
  - Remove `is_control_flow` from example code (line 493) and field table (line 506)
  - Add `role` field with `NodeRole` type documentation
  - Same model renames as Python README

### 6.3 External author guide

- [ ] `docs/EXTERNAL-AUTHOR-GUIDE.md`:
  - Update all model references to new names
  - Add naming convention table
  - Remove `is_control_flow` references
  - Update `WorkflowBuilder` examples

### 6.4 Root README

- [ ] `README.md`:
  - Update model references
  - Update any code examples

### 6.5 AGENTS.md

- [ ] `AGENTS.md`:
  - Update Workflow Builder table with new model names
  - Update node creation conventions

### 6.6 Skills files

- [ ] `.opencode/skills/canvastekk-node-builder/SKILL.md`:
  - Remove `is_control_flow=False` from code examples (line 144)
  - Add `role=NodeRole.OPERATION` (or omit since it's the default)
  - Replace `NodeDefinition` → `WorkflowNodeManifest` in examples (or keep `NodeDefinition` alias)
- [ ] `python/canvastekk_workflow_sdk/data/skills/canvastekk-node-builder/SKILL.md`:
  - Same changes as above (line 145)

### 6.7 Example node

- [ ] `examples/echo_node/handler.py`:
  - Currently uses `NodeDefinition` alias — no change needed (alias already points to `WorkflowNodeManifest`)
  - Verify `role` field defaults correctly

---

## Phase 7: Version Bump — PENDING

- [ ] Bump Python SDK version:
  - `python/canvastekk_workflow_sdk/__init__.py` (`__version__`)
  - `python/pyproject.toml` (`version`)
- [ ] Bump TypeScript SDK version:
  - `typescript/src/version.ts`
  - `typescript/package.json` (`version`)

---

## Phase 8: Final Verification — PENDING

- [ ] Run `poetry run ruff check canvastekk_workflow_sdk/ tests/` from `python/`
- [ ] Run `poetry run pytest -v` from `python/` — all tests pass
- [ ] Run `npx tsc --noEmit` from `typescript/`
- [ ] Run `npx vitest run` from `typescript/` — all tests pass
- [ ] Grep for stale `is_control_flow` in source (not docs): `grep -rn "is_control_flow" python/canvastekk_workflow_sdk/ typescript/src/ --include="*.py" --include="*.ts"` — zero results
- [ ] Grep for stale `ResolutionStrategy`: `grep -rn "ResolutionStrategy" python/ typescript/ --include="*.py" --include="*.ts"` — zero results
- [ ] Grep for `WorkflowNodeDefinition` in source: only alias declarations should remain
- [ ] Verify top-level imports work in both SDKs:
  - Python: `from canvastekk_workflow_sdk import WorkflowNodeManifest, WorkflowNodeDefinition, NodeDefinition, NodeRole`
  - TypeScript: `import { WorkflowNodeManifestSchema, type WorkflowNodeManifest, type WorkflowNodeDefinition }`
- [ ] Verify all backward-compat aliases: `NodeDefinition`, `WorkflowNodeDefinition`, `WorkflowNode`, `WorkflowEdge`, `WorkflowSpec`
- [ ] Post completion comment to [DA-1230](https://betekk.atlassian.net/browse/DA-1230)

---

## File Change Summary

| File | Phase | Status | Changes |
|------|-------|--------|---------|
| **Python SDK Source** | | | |
| `python/canvastekk_workflow_sdk/definition.py` | 1, 5A | Done | Add `NodeRole`; rename class → `WorkflowNodeManifest`; add `WorkflowNodeDefinition` alias |
| `python/canvastekk_workflow_sdk/__init__.py` | 1, 3, 4, 5A, 5C | Done | Deduplicate `__all__` entries |
| `python/canvastekk_workflow_sdk/base.py` | 1, 5A | Done | Remove `is_control_flow`; update type hints to `WorkflowNodeManifest` |
| `python/canvastekk_workflow_sdk/registry.py` | 1, 5A | Done | Include `role`; update type hints to `WorkflowNodeManifest` |
| `python/canvastekk_workflow_sdk/app.py` | 5A | Done | Fix stale `is_control_flow` in docstring |
| `python/canvastekk_workflow_sdk/__main__.py` | 5A | Done | Update type checks to `WorkflowNodeManifest` |
| `python/canvastekk_workflow_sdk/workflow/models.py` | 2, 3, 4 | Done | `WorkflowDefinitionNode`, `WorkflowEdgeDefinition`, `WorkflowDefinitionSpec` |
| `python/canvastekk_workflow_sdk/workflow/__init__.py` | 3, 4, 5C | Done | Move aliases above `__all__` |
| `python/canvastekk_workflow_sdk/workflow/builder.py` | 2, 3, 4, 5C | Done | Remove unused `name` param |
| `python/canvastekk_workflow_sdk/workflow/resolver.py` | 3, 4, 5C | Done | Wrap `StopIteration` |
| `python/canvastekk_workflow_sdk/workflow/runner.py` | 4 | Done | Rename |
| `python/canvastekk_workflow_sdk/workflow/validation.py` | 4 | Done | Rename |
| `python/canvastekk_workflow_sdk/workflow/level.py` | 4 | Done | Rename |
| **Python Tests** | | | |
| `python/tests/test_definition.py` | 1, 5A, 5C | Done | Remove redundant re-imports; top-level `NodeStyles` import |
| `python/tests/test_base.py` | 1, 5A | Done | `WorkflowNodeManifest` used |
| `python/tests/test_file_download.py` | 5A | Done | `WorkflowNodeManifest` used |
| `python/tests/test_observability.py` | 5A | Done | `WorkflowNodeManifest` used |
| `python/tests/test_workflow_runner.py` | 5A | Done | `WorkflowNodeManifest` used |
| `python/tests/test_testing.py` | 5A | Done | `WorkflowNodeManifest` used |
| `python/tests/test_validation.py` | 5A | Done | `WorkflowNodeManifest` used |
| `python/tests/test_middleware.py` | 5A | Done | `WorkflowNodeManifest` used |
| `python/tests/test_main.py` | 5A | Done | `WorkflowNodeManifest` used |
| `python/tests/test_router.py` | 5A | Done | `WorkflowNodeManifest` used |
| `python/tests/test_app.py` | 5A | Done | `WorkflowNodeManifest` used |
| `python/tests/test_registry.py` | 5A | Done | `WorkflowNodeManifest` used |
| `python/tests/test_workflow_models.py` | 2, 3, 4 | Done | Updated model constructions |
| `python/tests/test_workflow_builder.py` | 2, 3, 5C | Done | Remove `name` arg from `WorkflowBuilder()` |
| `python/tests/test_workflow_validation.py` | 2, 3, 4 | Done | Updated models |
| **TypeScript SDK Source** | | | |
| `typescript/src/definition.ts` | 5B, 5C | Done | Rename `nodeRoleSchema` → `NodeRoleSchema` |
| `typescript/src/index.ts` | 5B | Done | Update exports |
| `typescript/src/base-node.ts` | 5B | Done | Update imports + type annotations |
| `typescript/src/registry.ts` | 5B | Done | Update imports + type annotations |
| `typescript/src/workflow/models.ts` | 2, 3, 4 | Done | Renamed models |
| `typescript/src/workflow/index.ts` | 3, 4 | Done | Updated exports |
| `typescript/src/workflow/builder.ts` | 2, 3, 4, 5C | Done | Remove unused `name` param; fix `config_schema` duplication |
| `typescript/src/workflow/resolver.ts` | 3, 4 | Done | Updated |
| `typescript/src/workflow/runner.ts` | 4 | Done | Updated |
| `typescript/src/workflow/validation.ts` | 4 | Done | Updated |
| `typescript/src/workflow/level.ts` | 4 | Done | Updated |
| `typescript/src/workflow/executor.ts` | 4 | Done | Updated |
| **TypeScript Tests** | | | |
| `typescript/tests/definition.test.ts` | 5B, 5C | Done | Rename `NodeRoleSchema`; add backward-compat alias tests |
| `typescript/tests/base-node.test.ts` | 5B | Done | Fix import typo + rename |
| `typescript/tests/registry.test.ts` | 5B | Done | Fix import typo + rename |
| `typescript/tests/app.test.ts` | 5B | Done | Fix import typo + rename |
| `typescript/tests/workflow-builder.test.ts` | 2, 3, 4, 5C | Done | Remove `name` arg; fix `config_schema` assertion |
| `typescript/tests/workflow-runner.test.ts` | 2, 3, 4, 5C | Done | Remove `name` arg |
| `typescript/tests/workflow-validation.test.ts` | 3, 4 | Done | Updated |
| `typescript/tests/workflow-resolver.test.ts` | 3, 4 | Done | Updated |
| `typescript/tests/workflow-level.test.ts` | 4 | Done | Updated |
| **Docs & Config** | | | |
| `python/README.md` | 6 | **Not done** | Remove `is_control_flow`; update model names |
| `typescript/README.md` | 6 | **Not done** | Remove `is_control_flow`; update model names |
| `docs/EXTERNAL-AUTHOR-GUIDE.md` | 6 | **Not done** | Update all model references |
| `README.md` | 6 | **Not done** | Update model references |
| `AGENTS.md` | 6 | **Not done** | Update model references |
| `.opencode/skills/canvastekk-node-builder/SKILL.md` | 6 | **Not done** | Remove `is_control_flow`; update examples |
| `python/.../data/skills/canvastekk-node-builder/SKILL.md` | 6 | **Not done** | Remove `is_control_flow`; update examples |
| `examples/echo_node/handler.py` | 6 | No change | Uses `NodeDefinition` alias — works as-is |
| `python/pyproject.toml` | 7 | **Not done** | Version bump |
| `python/.../__init__.py` (version line) | 7 | **Not done** | Version bump |
| `typescript/package.json` | 7 | **Not done** | Version bump |
| `typescript/src/version.ts` | 7 | **Not done** | Version bump |

---

## Engine Follow-Up (Separate Ticket Required)

The SDK changes in DA-1230 require corresponding updates in `canvastekk-workflow-engine`. These are **not** part of the SDK ticket but must be tracked as a separate engine ticket:

### Engine Changes Needed

| # | Change | Details |
|---|--------|---------|
| 1 | `from_sdk()` converter: default `invoke_type=HTTP` | The converter currently reads `is_control_flow` from SDK payload to set `invoke_type`. Since `is_control_flow` is removed from SDK, the converter must default to `HTTP` for all SDK-registered nodes. The 4 built-in nodes (`__start__`, `__end__`, `if`, `stop-error`) are seeded directly by the engine, not via SDK registration, so they are unaffected. |
| 2 | Accept `node_role` field from SDK registration payload | The engine DB already has `node_role` on every registry entry (live registry shows all 66 nodes have it). The `RegisterNodeRequest` schema and `from_sdk()` converter should accept `node_role` from the SDK payload and store it. Currently the engine may ignore or overwrite it. |
| 3 | Consider adding `workflow_node_id` + `config_schema` to engine's `WorkflowDefinitionNode` model | The SDK now sends these fields in workflow specs. If the engine's `SaveWorkflowRequest.spec` schema doesn't accept them, they'll be silently dropped. Verify engine's `WorkflowDefinitionNode` model has these fields or add them. |
| 4 | Remove `is_control_flow` from `RegisterNodeRequest` schema (optional) | The engine's API schema for node registration likely still expects `is_control_flow`. After SDK stops sending it, the engine should either make it optional or remove it. The DB column can remain with default `False`. |
| 5 | Remove `ResolutionStrategy` / `resolution_strategy` from engine edge model (optional) | If the engine's edge model has `resolution_strategy`, consider aligning with the SDK's simplified approach. Lower priority since this is engine-internal. |
| 6 | Standardize `config_schema` format to JSON Schema Draft 7 | `config_schema` on `WorkflowDefinitionNode` currently uses a non-standard flat dict format (`{field_name: {type, description, default?}}`). The engine's `README_ANALYZE.md` Phase 4 recommends converting to standard JSON Schema Draft 7 (`{"type": "object", "properties": {...}, "required": [...]}`) to reuse `_extract_schema_defaults()` and `_validate_inputs()` instead of the custom `_extract_config_schema_defaults()`. **SDK impact**: `WorkflowBuilder.add_start(outputs=...)` currently generates flat dict — would need to output JSON Schema format instead. Data migration required for existing stored specs. |

### `config_schema` — SDK Role

`config_schema` is **not used by the local runner** — the runner passes START inputs through directly. It IS needed when building `WorkflowDefinitionSpec` objects to POST to the engine API (`/api/workflows/definitions`). The engine expects `config_schema` on START nodes to know what fields the workflow accepts as inputs and to extract defaults.

The SDK keeps `config_schema` on `WorkflowDefinitionNode` for wire compatibility. Format standardization is an engine-side change (Phase 4 of engine refactor per `README_ANALYZE.md`).

### Impact Assessment

- **Items 1-2 are blocking**: Without them, new SDK nodes cannot register correctly (wrong `invoke_type`) and `node_role` may not propagate.
- **Item 3 is important**: Without it, `workflow_node_id` and `config_schema` are lost when specs are saved via the engine API.
- **Items 4-5 are cleanup**: Can be done later, low risk since DB columns have defaults.

### Proposed Ticket

Create a new JIRA ticket (e.g., `DA-1231`) in the engine repo:
- Title: "Align engine with SDK DA-1230 model changes"
- Blocks on: DA-1230 (this ticket)
- Scope: `canvastekk-workflow-engine` repo

---

## Key Decisions Log

| Decision | Rationale |
|----------|-----------|
| `is_singleton` excluded from SDK | Only `__start__` gets `True`, hardcoded in engine seeding, never enforced |
| `is_control_flow` excluded from SDK | All 62 SDK nodes are HTTP; only 4 engine built-ins are in-process; engine derives `invoke_type` from own registry |
| `ResolutionStrategy` fully removed | All resolution is dot-path; the enum added complexity with no real use case |
| Minor version bump (not major) | Pre-production; breaking changes are acceptable |
| `WorkflowNodeManifest` over `WorkflowNodeDefinition` | "Definition" overloaded with `WorkflowDefinition`; "Manifest" semantically precise for registration artifact |
| `WorkflowDefinition*` naming for DAG models | Parent→child pattern: things inside a `WorkflowDefinition` are `WorkflowDefinitionNode`, `WorkflowEdgeDefinition`, `WorkflowDefinitionSpec` |
| Backward-compat type aliases kept | Old names point to new names for smooth migration |
| `NodeStyles` → `WorkflowNodeStyles` | Sub-component of `WorkflowNodeManifest`; follows parent stem |
| `NodeRole` → `WorkflowNodeRole` | Sub-component of `WorkflowNodeManifest`; follows parent stem |
| `RetryConfig` kept as-is | Generic enough to stand alone; not exclusively tied to `WorkflowNodeManifest` |
| Engine `from_sdk()` converter | Needs separate ticket to default `invoke_type=HTTP` instead of reading removed `is_control_flow` |

---

## Risks & Mitigation

| Risk | Mitigation |
|------|------------|
| Nodes break on upgrade — missing `role` | Default `role=operation` so existing nodes work without changes |
| Removing `is_control_flow` from SDK payload | Engine DB column unaffected — defaults to `False` for SDK nodes. Separate engine ticket for `from_sdk()` |
| Removing `ResolutionStrategy` breaks resolver | Simplified to single resolution path (dot-path, the current AUTO default) |
| Renames cause import errors across ecosystem | Backward-compat aliases kept; pre-production so acceptable |
| `slug` becoming optional on `WorkflowDefinitionNode` may confuse builders | Document `workflow_node_id` as preferred; `slug` still works |
| Missing `WorkflowNodeDefinition` alias breaks test files | Phase 5A adds the alias before verification |
| TypeScript test import typo `WorkflowWorkflowNodeDefinition` | Phase 5B fixes imports to use `WorkflowNodeManifest` directly |

---

## Success Metrics

- All 8 phases completed
- Zero references to `is_control_flow` in SDK source code (Python + TypeScript)
- Zero references to `ResolutionStrategy` anywhere
- `NodeRole` enum and `WorkflowNodeManifest` exported from top-level in both SDKs
- All backward-compat aliases functional (`NodeDefinition`, `WorkflowNodeDefinition`, `WorkflowNode`, `WorkflowEdge`, `WorkflowSpec`, `NodeStyles`, `NodeRole`)
- All tests green: Python (542+) and TypeScript (205+)
- Minor version bumped
- Documentation fully updated
