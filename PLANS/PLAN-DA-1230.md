# PLAN-DA-1230: SDK model updates for uniform node design (DA-1227 follow-up)

> **JIRA Ticket:** [DA-1230](https://betekk.atlassian.net/browse/DA-1230)
> **Branch:** `feature/DA-1230`
> **Status:** In Progress — Phases 1-4 complete, Phase 5 in progress
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
| 5 | Rename `WorkflowNodeDefinition` → `WorkflowNodeManifest` | In Progress |
| 6 | Documentation updates | Pending |
| 7 | Version bump | Pending |
| 8 | Final verification | Pending |

### Naming Convention (Parent→Child)

All models follow a parent→child naming pattern aligned with the workflow engine:

| Artifact | Name | Parent Concept |
|----------|------|----------------|
| Node registration manifest | `WorkflowNodeManifest` | `WorkflowNodeRegistry` (engine) |
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

**Known gap (deferred to Phase 5A):** `app.py:258` docstring still references `is_control_flow`

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

## Phase 5A: Complete Python WorkflowNodeManifest rename — IN PROGRESS

The class rename from `WorkflowNodeDefinition` → `WorkflowNodeManifest` was applied to source files in Phase 5, but **two critical gaps remain**:

### 5A.1 Add missing backward-compat alias

- [ ] In `definition.py`: Add `WorkflowNodeDefinition = WorkflowNodeManifest` after existing `NodeDefinition = WorkflowNodeManifest` (line 353)
  - Current state: Only `NodeDefinition` alias exists. `WorkflowNodeDefinition` alias is missing.
  - 6 test files import `WorkflowNodeDefinition` from the top-level package — they will get `ImportError` without this alias.

### 5A.2 Re-export alias from package root

- [ ] In `__init__.py`: Add `WorkflowNodeDefinition` to the import block from `definition` (line 57-65)
- [ ] In `__init__.py`: Add `"WorkflowNodeDefinition"` to `__all__` list (around line 167)

### 5A.3 Fix stale docstring

- [ ] In `app.py`: Fix line 258 docstring — replace `is_control_flow` with `role` in the manifest field list
  - Current: `"- Metadata (category, timeout, is_control_flow)"`
  - Should be: `"- Metadata (category, timeout, role)"`

### 5A.4 Update test files still using old name

These 6 test files still import `WorkflowNodeDefinition`. After the alias is added (5A.1-5A.2), they will work via alias. Decide: update to `WorkflowNodeManifest` or leave on alias?

- [ ] `python/tests/test_validation.py` (lines 5, 9, 31) — update to `WorkflowNodeManifest`
- [ ] `python/tests/test_middleware.py` (lines 9, 16, 30) — update to `WorkflowNodeManifest`
- [ ] `python/tests/test_main.py` (lines 20, 22, 25, 27, 54, 57, 59, 89, 92, 94) — update to `WorkflowNodeManifest`
- [ ] `python/tests/test_router.py` (lines 7, 12, 26, 40) — update to `WorkflowNodeManifest`
- [ ] `python/tests/test_app.py` (lines 13, 19, 42, 84, 100, 268, 297, 898, 920) — update to `WorkflowNodeManifest`
- [ ] `python/tests/test_registry.py` (lines 11, 24, 409, 419) — update to `WorkflowNodeManifest`

### 5A.5 Verify

- [ ] Run `poetry run ruff check canvastekk_workflow_sdk/ tests/` — must pass
- [ ] Run `poetry run pytest -v` — all tests pass (542+)
- [ ] Verify `from canvastekk_workflow_sdk import WorkflowNodeManifest, WorkflowNodeDefinition, NodeDefinition` all work

---

## Phase 5B: TypeScript WorkflowNodeManifest rename — PENDING

### 5B.1 Rename schema and type in definition.ts

- [ ] Rename `WorkflowNodeDefinitionSchema` → `WorkflowNodeManifestSchema` (line 86)
- [ ] Rename `type WorkflowNodeDefinition` → `type WorkflowNodeManifest` (line 129)
- [ ] Update `NodeDefinition` alias: `type NodeDefinition = WorkflowNodeManifest` (line 131, currently `= WorkflowNodeDefinition`)
- [ ] Add backward-compat alias: `type WorkflowNodeDefinition = WorkflowNodeManifest`
- [ ] Update function signatures that reference `WorkflowNodeDefinition`:
  - `getNodeId()` (line 133)
  - `getFileInputFields()` (line 145)
  - `getFileOutputFields()` (line 163)
  - `validateFileInput()` (line 186)

### 5B.2 Update base-node.ts

- [ ] Update import: `import type { WorkflowNodeManifest } from "./definition.js"` (line 7)
- [ ] Update import: `import { WorkflowNodeManifestSchema, getFileInputFields, validateFileInput } from "./definition.js"` (line 8)
- [ ] Update class docstring reference (line 110)
- [ ] Update `abstract definition: WorkflowNodeManifest` (line 136)
- [ ] Update `private _validatedDefinition: WorkflowNodeManifest | null` (line 140)
- [ ] Update `get nodeDefinition(): WorkflowNodeManifest` (line 146)
- [ ] Update `protected getDefinition(): WorkflowNodeManifest` (line 154)
- [ ] Update `WorkflowNodeManifestSchema.parse(...)` (line 156)

### 5B.3 Update registry.ts

- [ ] Update import: `import type { WorkflowNodeManifest } from "./definition.js"` (line 3)
- [ ] Update `buildRegistryPayload` param type (line 48)
- [ ] Update `registerNode` param type (line 124)
- [ ] Update `exportDefinition` param type (line 214)

### 5B.4 Update index.ts

- [ ] Rename export: `WorkflowNodeManifestSchema` (line 19, currently `WorkflowNodeDefinitionSchema`)
- [ ] Rename export: `type WorkflowNodeManifest` (line 28, currently `type WorkflowNodeDefinition`)
- [ ] Add `type WorkflowNodeDefinition` backward-compat export

### 5B.5 Update test files

- [ ] `tests/definition.test.ts`:
  - Rename import `WorkflowNodeDefinitionSchema` → `WorkflowNodeManifestSchema` (line 3)
  - Update describe block name (line 31)
  - Update all `WorkflowNodeDefinitionSchema.parse(...)` calls (lines 33, 46, 52, 58, 64, 70, 84, 97, 116, 128, 136, 146, 164, 179, 186, 202, 221, 238)
  - Update test description strings (lines 266, 271)
- [ ] `tests/app.test.ts`:
  - Fix import: `import type { WorkflowNodeManifest } from "../src/definition.js"` (line 5, currently broken `WorkflowWorkflowNodeDefinition`)
  - Update all `definition: WorkflowNodeDefinition` → `definition: WorkflowNodeManifest` (lines 10, 31)
- [ ] `tests/registry.test.ts`:
  - Fix import: `import type { WorkflowNodeManifest } from "../src/definition.js"` (line 8, currently broken `WorkflowWorkflowNodeDefinition`)
  - Update `const testDef: WorkflowNodeDefinition` → `const testDef: WorkflowNodeManifest` (line 10)
- [ ] `tests/base-node.test.ts`:
  - Fix import: `import type { WorkflowNodeManifest } from "../src/definition.js"` (line 3, currently broken `WorkflowWorkflowNodeDefinition`)
  - Update all `definition: WorkflowNodeDefinition` → `definition: WorkflowNodeManifest` (lines 9, 32, 47)

### 5B.6 Verify

- [ ] Run `npx tsc --noEmit` — must pass
- [ ] Run `npx vitest run` — all tests pass (204+)
- [ ] Verify imports: `import { WorkflowNodeManifestSchema, type WorkflowNodeManifest, type WorkflowNodeDefinition } from "canvastekk-workflow-sdk"` all resolve

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
| `python/canvastekk_workflow_sdk/definition.py` | 1, 5A | Partial | Add `NodeRole`; rename class → `WorkflowNodeManifest`; **add missing `WorkflowNodeDefinition` alias** |
| `python/canvastekk_workflow_sdk/__init__.py` | 1, 3, 4, 5A | Partial | Add `NodeRole`; rename models; **add missing `WorkflowNodeDefinition` re-export** |
| `python/canvastekk_workflow_sdk/base.py` | 1, 5A | Done | Remove `is_control_flow`; update type hints to `WorkflowNodeManifest` |
| `python/canvastekk_workflow_sdk/registry.py` | 1, 5A | Done | Include `role`; update type hints to `WorkflowNodeManifest` |
| `python/canvastekk_workflow_sdk/app.py` | 5A | **Not done** | **Fix stale `is_control_flow` in docstring (line 258)** |
| `python/canvastekk_workflow_sdk/__main__.py` | 5A | Done | Update type checks to `WorkflowNodeManifest` |
| `python/canvastekk_workflow_sdk/workflow/models.py` | 2, 3, 4 | Done | `WorkflowDefinitionNode`, `WorkflowEdgeDefinition`, `WorkflowDefinitionSpec` |
| `python/canvastekk_workflow_sdk/workflow/__init__.py` | 3, 4 | Done | Remove `ResolutionStrategy`, rename exports |
| `python/canvastekk_workflow_sdk/workflow/builder.py` | 2, 3, 4 | Done | Accept new fields, remove `resolution_strategy`, rename return type |
| `python/canvastekk_workflow_sdk/workflow/resolver.py` | 3, 4 | Done | Remove strategy logic, rename |
| `python/canvastekk_workflow_sdk/workflow/runner.py` | 4 | Done | Rename |
| `python/canvastekk_workflow_sdk/workflow/validation.py` | 4 | Done | Rename |
| `python/canvastekk_workflow_sdk/workflow/level.py` | 4 | Done | Rename |
| **Python Tests** | | | |
| `python/tests/test_definition.py` | 1, 5A | Done | `WorkflowNodeManifest` used |
| `python/tests/test_base.py` | 1, 5A | Done | `WorkflowNodeManifest` used |
| `python/tests/test_file_download.py` | 5A | Done | `WorkflowNodeManifest` used |
| `python/tests/test_observability.py` | 5A | Done | `WorkflowNodeManifest` used |
| `python/tests/test_workflow_runner.py` | 5A | Done | `WorkflowNodeManifest` used |
| `python/tests/test_testing.py` | 5A | Done | `WorkflowNodeManifest` used |
| `python/tests/test_validation.py` | 5A | **Not done** | **Still uses `WorkflowNodeDefinition`** |
| `python/tests/test_middleware.py` | 5A | **Not done** | **Still uses `WorkflowNodeDefinition`** |
| `python/tests/test_main.py` | 5A | **Not done** | **Still uses `WorkflowNodeDefinition`** |
| `python/tests/test_router.py` | 5A | **Not done** | **Still uses `WorkflowNodeDefinition`** |
| `python/tests/test_app.py` | 5A | **Not done** | **Still uses `WorkflowNodeDefinition`** |
| `python/tests/test_registry.py` | 5A | **Not done** | **Still uses `WorkflowNodeDefinition`** |
| `python/tests/test_workflow_models.py` | 2, 3, 4 | Done | Updated model constructions |
| `python/tests/test_workflow_builder.py` | 2, 3 | Done | Updated builder calls |
| `python/tests/test_workflow_validation.py` | 2, 3, 4 | Done | Updated models |
| **TypeScript SDK Source** | | | |
| `typescript/src/definition.ts` | 5B | **Not done** | Rename schema + type → `WorkflowNodeManifest` |
| `typescript/src/index.ts` | 5B | **Not done** | Update exports |
| `typescript/src/base-node.ts` | 5B | **Not done** | Update imports + type annotations |
| `typescript/src/registry.ts` | 5B | **Not done** | Update imports + type annotations |
| `typescript/src/workflow/models.ts` | 2, 3, 4 | Done | Renamed models |
| `typescript/src/workflow/index.ts` | 3, 4 | Done | Updated exports |
| `typescript/src/workflow/builder.ts` | 2, 3, 4 | Done | Updated |
| `typescript/src/workflow/resolver.ts` | 3, 4 | Done | Updated |
| `typescript/src/workflow/runner.ts` | 4 | Done | Updated |
| `typescript/src/workflow/validation.ts` | 4 | Done | Updated |
| `typescript/src/workflow/level.ts` | 4 | Done | Updated |
| `typescript/src/workflow/executor.ts` | 4 | Done | Updated |
| **TypeScript Tests** | | | |
| `typescript/tests/definition.test.ts` | 5B | **Not done** | Rename schema references |
| `typescript/tests/base-node.test.ts` | 5B | **Not done** | Fix import typo + rename |
| `typescript/tests/registry.test.ts` | 5B | **Not done** | Fix import typo + rename |
| `typescript/tests/app.test.ts` | 5B | **Not done** | Fix import typo + rename |
| `typescript/tests/workflow-builder.test.ts` | 2, 3, 4 | Done | Updated |
| `typescript/tests/workflow-runner.test.ts` | 2, 3, 4 | Done | Updated |
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
- All backward-compat aliases functional (`NodeDefinition`, `WorkflowNodeDefinition`, `WorkflowNode`, `WorkflowEdge`, `WorkflowSpec`)
- All tests green: Python (542+) and TypeScript (204+)
- Minor version bumped
- Documentation fully updated
