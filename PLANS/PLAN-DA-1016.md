# PLAN-DA-1016: Fix register_node() field mapping for new engine API

**JIRA Ticket**: [DA-1016](https://betekk.atlassian.net/browse/DA-1016)
**Branch**: `DA-1016`
**Created**: 2026-05-21
**Updated**: 2026-05-21 (architecture review)
**Status**: Planning Complete

---

## Overview

The CanvasTEKK Workflow Engine (v1.0.1-dev) updated its node registration endpoint to a new `RegisterNodeRequest` schema. The SDK's `register_node()` sends SDK-native field names that don't match the engine API, causing registration failures.

### Root Cause

**DRY violation** — `register_node()` and `export_definition()` maintain independent field mapping logic. `export_definition()` already maps correctly (`title`→`label`, `default_retry`→`retry`), but `register_node()` bypasses it by calling `node.definition.to_dict()` which outputs raw SDK field names.

## Critical Mismatches

| # | Issue | Severity | Field |
|---|-------|----------|-------|
| 1 | SDK sends `title`, API expects `label` | CRITICAL (blocking) | `title` → `label` |
| 2 | Response wrapper changed `data` → `node` | High | `_extract_node_data()` |
| 3 | Extra fields sent (`id`, `default_retry`) | Medium | Payload filtering |
| 4 | Missing `tags` parameter | Low | New optional param |

## Architecture Review Findings

### AFR-1: DRY Violation — Shared Mapping Required
`register_node()` and `export_definition()` both map `NodeDefinition` → registry payload format independently. The fix must extract a shared `build_registry_payload()` function to prevent future drift.

### AFR-2: Response Metadata Silently Discarded
New `RegisterNodeResponse` returns `revision_id`, `previous_version`, `changes` but the SDK only returns the inner node dict. These should at minimum be logged, ideally exposed via a typed response model.

### AFR-3: No Enum Validation on `invoke_type`
`invoke_type` accepts any string but the API only accepts `http | lambda | sagemaker | in-process`. SDK provides no client-side validation.

### AFR-4: Existing Tests Assert Wrong Field Names
`test_posts_correct_manifest_json` asserts `title` (the wrong field). Must be fixed to assert `label`.

### AFR-5: Documentation Desync
Three doc layers need updating, not just one: `docs/EXTERNAL-AUTHOR-GUIDE.md`, `python/README.md`, and `examples/echo_node/`. The GUIDE's curl examples will break against the new engine API.

### AFR-6: No `RegisterNodeResponse` Typed Model
The SDK returns `dict[str, Any]` from `register_node()`. The new response structure is rich enough to warrant a typed model (`node`, `action`, `revision_id`, `previous_version`, `changes`).

## Implementation Phases

### Phase 1: Setup & Analysis
- [ ] Review current `registry.py` implementation
- [ ] Review `definition.py` for `export_definition()` pattern reference
- [ ] Confirm engine API `RegisterNodeRequest` schema from Confluence analysis
- [ ] Check existing tests for `register_node()` and `_extract_node_data()`
- [ ] Map all differences between `register_node()` and `export_definition()` payloads

### Phase 2: Core Implementation — `registry.py`
- [ ] Extract `build_registry_payload()` shared helper function (DRY fix)
  - Centralize field mapping: `title`→`label`, `default_retry`→`retry`
  - Omit `id` from payload
  - Include all standard fields: `styles`, `category`, `token_cost`, `timeout_seconds`, `is_control_flow`
  - Accept optional `tags`, `invoke_config`, `constraints` params
- [ ] Refactor `register_node()` to use `build_registry_payload()`
- [ ] Refactor `export_definition()` to use `build_registry_payload()` (eliminate duplicate)
- [ ] Add `tags: list[str] | None = None` parameter to `register_node()`
- [ ] Add `invoke_config: dict[str, Any] | None = None` parameter to `register_node()`
- [ ] Add `InvokeType` string literal or enum validation (`http`, `lambda`, `sagemaker`, `in-process`)
- [ ] Update `_extract_node_data()` to handle both `{"node": ...}` and `{"data": ...}` response wrappers
- [ ] Log response metadata (`action`, `revision_id`, `previous_version`, `changes`) at INFO level
- [ ] Ensure backward compatibility with old response format

### Phase 3: Response Model (Optional Enhancement)
- [ ] Add `RegisterNodeResponse` typed model in `registry.py`:
  ```python
  class RegisterNodeResponse(BaseModel):
      node: dict[str, Any]
      action: Literal["created", "updated", "unchanged"]
      revision_id: str
      previous_version: str | None = None
      changes: list[str] | None = None
  ```
- [ ] Consider changing `register_node()` return type from `dict` to `RegisterNodeResponse` (with backward-compat deprecation path)

### Phase 4: Testing
- [ ] Fix `test_posts_correct_manifest_json` — assert `label` not `title`
- [ ] Update existing unit tests for `register_node()` with new payload shape
- [ ] Add test for `_extract_node_data()` with new `{"node": ...}` response format
- [ ] Add test for `_extract_node_data()` with old `{"data": ...}` response format (backward compat)
- [ ] Add test for `tags` parameter (default empty, custom tags)
- [ ] Add test for `invoke_config` parameter
- [ ] Add test for `InvokeType` validation (reject invalid values)
- [ ] Add test for `None` styles (ensure omitted, not sent as null)
- [ ] Add test verifying `id` is NOT in the payload
- [ ] Add test verifying `default_retry` key is NOT in the payload (replaced by `retry`)
- [ ] Add test for `build_registry_payload()` shared helper directly
- [ ] Add test that `export_definition()` produces identical field mapping
- [ ] Verify `poetry run ruff check canvastekk_workflow_sdk/ tests/` passes
- [ ] Verify `poetry run pytest -v` passes

### Phase 5: Documentation & Examples
- [ ] Update `docs/EXTERNAL-AUTHOR-GUIDE.md`:
  - Fix curl examples for new field names (`label` not `title`)
  - Document new `tags` parameter
  - Document new `invoke_config` parameter
  - Update registry URL to `/api/workflows/nodes/`
- [ ] Update `python/README.md` API reference for `register_node()` signature changes
- [ ] Update `examples/echo_node/` registration example
- [ ] Ensure docstrings on `register_node()` reflect all new parameters

### Phase 6: Final Validation
- [ ] Run full test suite: `poetry run pytest -v`
- [ ] Run linter: `poetry run ruff check canvastekk_workflow_sdk/ tests/`
- [ ] Verify all acceptance criteria from DA-1016 are met
- [ ] Verify architecture review findings (AFR-1 through AFR-6) are addressed
- [ ] Code review preparation

## Acceptance Criteria

### P0 — Blocking
- [ ] `register_node()` sends `label` field (mapped from `definition.title`)
- [ ] `register_node()` sends `retry` field (mapped from `definition.default_retry`)
- [ ] `register_node()` no longer sends `id` field in the payload
- [ ] `_extract_node_data()` handles both old and new response wrappers
- [ ] `build_registry_payload()` shared helper extracted (DRY fix for AFR-1)
- [ ] Response metadata logged at INFO level (AFR-2)

### P1 — Required
- [ ] `register_node()` accepts optional `tags` parameter
- [ ] `register_node()` accepts optional `invoke_config` parameter
- [ ] `InvokeType` validation added (AFR-3)
- [ ] Existing test assertions fixed for `label` (AFR-4)
- [ ] Test for `id` NOT in payload
- [ ] Test for `retry` key (not `default_retry`)
- [ ] Test for `InvokeType` validation

### P2 — Recommended
- [ ] `RegisterNodeResponse` typed model (AFR-6)
- [ ] `export_definition()` refactored to use `build_registry_payload()`
- [ ] All 3 doc layers updated (AFR-5)
- [ ] `python/README.md` API reference updated

### P3 — Future Consideration
- [ ] Return type migration from `dict` to `RegisterNodeResponse` with deprecation path
- [ ] Version negotiation / capability detection between SDK and engine

## Confluence Reference

Full analysis: [SDK-to-Engine API Mismatch Analysis Upgrade Guide](https://betekk.atlassian.net/wiki/spaces/CanvasTEKK/pages/100990979/SDK-to-Engine+API+Mismatch+Analysis+Upgrade+Guide)

---
*Tracking progress with ticket-plan-workflow-skill*
