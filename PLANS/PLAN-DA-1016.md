# PLAN-DA-1016: Fix register_node() field mapping for new engine API

**JIRA Ticket**: [DA-1016](https://betekk.atlassian.net/browse/DA-1016)
**Branch**: `DA-1016`
**Created**: 2026-05-21
**Updated**: 2026-05-21 (architecture review)
**Status**: Implementation Complete

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
- [x] Review current `registry.py` implementation
- [x] Review `definition.py` for `export_definition()` pattern reference
- [x] Confirm engine API `RegisterNodeRequest` schema from Confluence analysis
- [x] Check existing tests for `register_node()` and `_extract_node_data()`
- [x] Map all differences between `register_node()` and `export_definition()` payloads

### Phase 2: Core Implementation — `registry.py`
- [x] Extract `build_registry_payload()` shared helper function (DRY fix)
  - Centralize field mapping: `title`→`label`, `default_retry`→`retry`
  - Omit `id` from payload
  - Include all standard fields: `styles`, `category`, `token_cost`, `timeout_seconds`, `is_control_flow`
  - Accept optional `tags`, `invoke_config`, `constraints` params
- [x] Refactor `register_node()` to use `build_registry_payload()`
- [x] Refactor `export_definition()` to use `build_registry_payload()` (eliminate duplicate)
- [x] Add `tags: list[str] | None = None` parameter to `register_node()`
- [x] Add `invoke_config: dict[str, Any] | None = None` parameter to `register_node()`
- [x] Add `InvokeType` string literal or enum validation (`http`, `lambda`, `sagemaker`, `in-process`)
- [x] Update `_extract_node_data()` to handle both `{"node": ...}` and `{"data": ...}` response wrappers
- [x] Log response metadata (`action`, `revision_id`, `previous_version`, `changes`) at INFO level
- [x] Ensure backward compatibility with old response format

### Phase 3: Response Model (Optional Enhancement)
- [x] Add `RegisterNodeResult` typed model in `registry.py` (named Result instead of Response to indicate it's not an API response model)
- [ ] Consider changing `register_node()` return type from `dict` to `RegisterNodeResult` (deferred — backward-compat deprecation path)

### Phase 4: Testing
- [x] Fix `test_posts_correct_manifest_json` — assert `label` not `title`
- [x] Update existing unit tests for `register_node()` with new payload shape
- [x] Add test for `_extract_node_data()` with new `{"node": ...}` response format
- [x] Add test for `_extract_node_data()` with old `{"data": ...}` response format (backward compat)
- [x] Add test for `tags` parameter (default empty, custom tags)
- [x] Add test for `invoke_config` parameter
- [x] Add test for `InvokeType` validation (reject invalid values)
- [x] Add test for `None` styles (ensure omitted, not sent as null)
- [x] Add test verifying `id` is NOT in the payload
- [x] Add test verifying `default_retry` key is NOT in the payload (replaced by `retry`)
- [x] Add test for `build_registry_payload()` shared helper directly
- [ ] Add test that `export_definition()` produces identical field mapping (deferred — covered by integration)
- [x] Verify `poetry run ruff check canvastekk_workflow_sdk/ tests/` passes
- [x] Verify `poetry run pytest -v` passes

### Phase 5: Documentation & Examples
- [x] Update `docs/EXTERNAL-AUTHOR-GUIDE.md`:
  - Fix curl examples for new field names (`label` not `title`)
  - Document new `tags` parameter
  - Document new `invoke_config` parameter
  - Update registry URL to `/api/workflows/nodes/`
- [x] Update `python/README.md` API reference for `register_node()` signature changes (no register_node API section exists — covered by EXTERNAL-AUTHOR-GUIDE.md)
- [x] Update `examples/echo_node/` registration example (no changes needed — example doesn't call register_node directly)
- [x] Ensure docstrings on `register_node()` reflect all new parameters

### Phase 6: Final Validation
- [x] Run full test suite: `poetry run pytest -v` — 427 passed
- [x] Run linter: `poetry run ruff check canvastekk_workflow_sdk/ tests/` — all checks passed
- [x] Verify all acceptance criteria from DA-1016 are met
- [x] Verify architecture review findings (AFR-1 through AFR-6) are addressed
- [x] Code review preparation

## Acceptance Criteria

### P0 — Blocking
- [x] `register_node()` sends `label` field (mapped from `definition.title`)
- [x] `register_node()` sends `retry` field (mapped from `definition.default_retry`)
- [x] `register_node()` no longer sends `id` field in the payload
- [x] `_extract_node_data()` handles both old and new response wrappers
- [x] `build_registry_payload()` shared helper extracted (DRY fix for AFR-1)
- [x] Response metadata logged at INFO level (AFR-2)

### P1 — Required
- [x] `register_node()` accepts optional `tags` parameter
- [x] `register_node()` accepts optional `invoke_config` parameter
- [x] `InvokeType` validation added (AFR-3)
- [x] Existing test assertions fixed for `label` (AFR-4)
- [x] Test for `id` NOT in payload
- [x] Test for `retry` key (not `default_retry`)
- [x] Test for `InvokeType` validation

### P2 — Recommended
- [x] `RegisterNodeResult` typed model (AFR-6)
- [x] `export_definition()` refactored to use `build_registry_payload()`
- [x] All 3 doc layers updated (AFR-5)
- [x] `python/README.md` API reference updated (no register_node section — covered by EXTERNAL-AUTHOR-GUIDE.md)

### P3 — Future Consideration
- [ ] Version negotiation / capability detection between SDK and engine

---

## Code Review Fixes (Phase 7)

Post-review fixes identified by code-review-subagent.

### Review Fix #1: Make `register_node()` return `RegisterNodeResult` (Major)
- [x] Change `register_node()` return type from `dict[str, Any]` to `RegisterNodeResult`
- [x] Populate all `RegisterNodeResult` fields from response data
- [x] Maintain backward compat: callers accessing dict keys still work (Pydantic model supports `__getitem__`)
- [x] Update docstring return type annotation
- [x] Update `__init__.py` exports if needed

### Review Fix #2: Document `_extract_node_data()` priority (Major)
- [x] Add docstring note: `"node"` key takes precedence over `"data"` when both are present

### Review Fix #3: Derive `VALID_INVOKE_TYPES` from `InvokeType` (Minor)
- [x] Use `typing.get_args()` to derive `VALID_INVOKE_TYPES` from the `InvokeType` Literal
- [x] Removes manual sync burden between the two definitions

### Review Fix #4: Omit `invoke_url` when `None` in payload (Minor)
- [x] Conditionally include `invoke_url` only when a value is provided
- [x] Avoids sending semantically meaningless `null` for in-process nodes

### Review Fix #5: Type `build_registry_payload()` `invoke_type` as `InvokeType` (Minor)
- [x] Change `invoke_type: str` to `invoke_type: InvokeType` for IDE autocompletion and type safety
- [x] Update docstring accordingly

### Post-Fix Validation
- [x] Update tests for `RegisterNodeResult` return type
- [x] Update test for omitted `invoke_url` when None
- [x] `poetry run ruff check canvastekk_workflow_sdk/ tests/` — all checks passed
- [x] `poetry run pytest -v` — 427 passed

## Confluence Reference

Full analysis: [SDK-to-Engine API Mismatch Analysis Upgrade Guide](https://betekk.atlassian.net/wiki/spaces/CanvasTEKK/pages/100990979/SDK-to-Engine+API+Mismatch+Analysis+Upgrade+Guide)

---
*Tracking progress with ticket-plan-workflow-skill*
