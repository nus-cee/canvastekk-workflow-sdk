# PLAN-DA-1028: Align SDK Naming with WorkflowNode / WorkflowDefinitionNode Model

**JIRA Ticket**: [DA-1028](https://betekk.atlassian.net/browse/DA-1028)
**Parent Epic**: [DA-1025](https://betekk.atlassian.net/browse/DA-1025) — Separate WorkflowNode and WorkflowDefinitionNode models
**Branch**: `DA-1028`
**Created**: 2026-05-22
**Status**: Implementation Complete

---

## Overview

The workflow engine (DA-1026) is separating `WorkflowNode` (registry node type) from `WorkflowDefinitionNode` (node instance in a workflow definition). The SDK must align naming conventions and update models to match the new engine API contract.

**Current state**: The SDK has **no** `WorkflowNode`, `WorkflowEdge`, or `WorkflowSpec` types. The only workflow-adjacent model is `NodeDefinition` (registry-level), which has `version: str` (semver). **The SDK's `version` is author-facing only** — the engine has its own independent versioning system (revision chain from DA-1007). The SDK version field does NOT need to change type.

**Sibling tickets**:
- DA-1026 — Engine refactor (models, migration, seed data)
- DA-1027 — Frontend contract updates
- DA-1029 — canvastekk-workflow-nodes: `version` str→int
- DA-1030 — canvastekk-floor-flatness-app: `workflow_node_id` references

---

## Impact Analysis

### Files Affected

| File | Change | Severity |
|------|--------|----------|
| `python/canvastekk_workflow_sdk/registry.py` | Align payload naming with engine conventions if needed | Medium |
| `python/canvastekk_workflow_sdk/definition.py` | Docstring updates for version semantics (author-facing only) | Low |
| `python/canvastekk_workflow_sdk/__init__.py` | Version bump | Low |
| `python/pyproject.toml` | Version bump | Low |
| `docs/EXTERNAL-AUTHOR-GUIDE.md` | Document version semantics, naming conventions | Low |
| `examples/echo_node/handler.py` | Inline comment clarifying version semantics | Low |

### NOT Affected (no changes needed)

- `definition.py` model — `version` stays as `str` (semver); it's author-facing only, independent of engine versioning
- `contracts.py` — No workflow-related types; pure data contracts
- `context.py` — Uses `node_id` (instance ID), unrelated
- `auth.py`, `middleware.py`, `observability.py` — Unrelated
- `request.py`, `response.py`, `router.py`, `uploads.py` — Unrelated
- `python/tests/` — No test changes needed (model stays the same)

---

## Key Decisions

### Decision 1: `version` — SDK field stays as `str` (semver), engine versioning is independent

The SDK's `NodeDefinition.version` is an **author-facing label** only. The engine assigns its own version (monotonically increasing `int`) when nodes register or update via `register_node()`. These are two completely independent versioning systems:

- **SDK `version`** — author's own semver label (e.g. `"1.2.0"`), stays as `str`, no change needed
- **Engine version** — assigned by the engine on each registration/update call, managed via revision chain (DA-1007), SDK never controls this

**No `version` type change needed in the SDK.** The DA-1028 ticket's "Update `version` field type from `str` to `int`" task does not apply to the SDK — it applies to the engine (DA-1026) and the nodes repo (DA-1029).

### Decision 2: `id` computed field changes format

Currently `id = f"{name}-v{version}"` → e.g. `"echo-v1.0.0"`. With `int` version: `"echo-v1"`.

The engine already derives its own ID from `(name, version)`. The SDK's computed `id` field is informational only — the registry ignores it (was removed from payload in DA-1016).

### Decision 3: No WorkflowDefinitionNode/WorkflowSpec types needed yet

The SDK does **not** currently provide workflow definition construction helpers. The engine's `WorkflowDefinitionNode` and `WorkflowDefinitionEdge` types live in the engine repo. The SDK only deals with **registry-level** node definitions (`NodeDefinition`).

**If** the SDK adds workflow definition building in the future, those types should follow the engine's naming (`WorkflowDefinitionNode`, `WorkflowDefinitionEdge`, `WorkflowSpec`). But that's out of scope for this ticket.

### Decision 4: `NodeDefinition` naming stays

`NodeDefinition` maps to the engine's registry-level `WorkflowNode` (renamed from `RegistryNodeDefinition`). The SDK name `NodeDefinition` is clear and doesn't conflict. Renaming to `WorkflowNode` would create confusion with the engine's `WorkflowDefinitionNode`. **No rename needed**.

---

## Implementation Phases

### Phase 1: Audit & Verify Registry Payload Alignment

- [x] Verify `build_registry_payload()` sends correct field names for engine's updated `RegisterNodeRequest` schema
- [x] Confirm engine ignores/overrides `version` in the payload (engine assigns its own)
- [x] Confirm `name` (slug) is still the correct node identifier field
- [x] Verify no payload fields conflict with engine's new `WorkflowNode` / `WorkflowDefinitionNode` naming

### Phase 2: Node Definition Documentation Realignment

- [x] Update `python/canvastekk_workflow_sdk/definition.py` docstrings:
  - [x] Clarify `version` is author-facing only (semver label for the node author's own use)
  - [x] Clarify engine versioning is independent and auto-assigned on registration
  - [x] Clarify `NodeDefinition` maps to the engine's registry-level node type (not `WorkflowDefinitionNode`)
  - [x] Update `NodeDefinition` class docstring to explain its role in the ecosystem
  - [x] Update `export_definition()` docstring to reflect engine naming conventions
- [x] Update `docs/EXTERNAL-AUTHOR-GUIDE.md`:
  - [x] Document two separate versioning concepts (SDK author version vs engine revision version)
  - [x] Document naming conventions: SDK `NodeDefinition` = registry-level, engine has separate `WorkflowDefinitionNode`
  - [x] Clarify that `register_node()` triggers engine version assignment
  - [x] Add section explaining the relationship between SDK types and engine types
  - [x] Update any field mapping tables to reflect engine's new `WorkflowNode` / `WorkflowDefinitionNode` naming
- [x] Update `python/README.md`:
  - [x] Document `NodeDefinition` role and version semantics
  - [x] Clarify engine vs SDK naming conventions
  - [x] Update API reference for any naming changes
- [x] Update `README.md` (repo root):
  - [x] Update architecture section to reference engine's `WorkflowNode` / `WorkflowDefinitionNode` separation
  - [x] Clarify SDK's role in the ecosystem
- [x] Update `examples/echo_node/`:
  - [x] Add comments in `handler.py` explaining `version` field is author-facing
  - [x] Ensure example reflects current best practices for node definition authoring

### Phase 3: Version Bump

- [x] Bump SDK version as **feat minor** (e.g. `0.9.1` → `0.10.0`) in `python/canvastekk_workflow_sdk/__init__.py` and `python/pyproject.toml`

### Phase 4: Final Validation

- [x] `poetry run ruff check canvastekk_workflow_sdk/ tests/` passes
- [x] `poetry run pytest -v` passes — 427 passed
- [x] Verify all acceptance criteria from DA-1028 are met

---

## Acceptance Criteria

### P0 — Blocking

- [x] SDK naming conventions documented and consistent with engine: `NodeDefinition` = registry-level, `WorkflowDefinitionNode` = engine-side
- [x] Registry payload (`build_registry_payload()`) confirmed compatible with engine's updated API
- [x] Documentation clearly separates SDK author version (semver str) from engine version (auto-assigned int)

### P1 — Required

- [x] Docstrings updated to clarify version semantics
- [x] SDK version bumped as feat minor (pre-production)
- [x] `poetry run ruff check` and `poetry run pytest` pass

### P2 — Recommended

- [x] Clear documentation for node authors explaining that `NodeDefinition.version` is their own label, engine handles actual versioning

### P3 — Future (Out of Scope)

- [ ] Add `WorkflowDefinitionNode` / `WorkflowSpec` builder types (only if SDK needs workflow definition construction)
- [ ] Rename `NodeDefinition` → `WorkflowNode` to match engine (confusing; defer)
- [ ] Add `name`, `description`, `position` fields for workflow definition node instances (SDK doesn't build workflow definitions)
- [ ] Change `version` type in SDK (only if engine later requires `int` in the registration payload — currently not needed)

---

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Engine registration payload changes may require SDK field mapping updates | Medium — verify against DA-1026 engine changes | Test registration against engine after DA-1026 merges |
| Confusion between SDK version and engine version | Low — documentation concern | Clear docstrings and EXTERNAL-AUTHOR-GUIDE update |
| Engine DA-1026 not yet merged | Low — SDK changes are documentation-only | Can merge SDK change independently |

---

## Confluence Reference

- Parent epic: [DA-1025](https://betekk.atlassian.net/browse/DA-1025)
- Engine design doc: `docs/REVIEW.md` (in canvastekk-workflow-engine repo)

---
*Tracking progress with ticket-plan-workflow-skill*
