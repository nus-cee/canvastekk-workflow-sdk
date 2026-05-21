# PLAN-DA-1016: Fix register_node() field mapping for new engine API

**JIRA Ticket**: [DA-1016](https://betekk.atlassian.net/browse/DA-1016)
**Branch**: `DA-1016`
**Created**: 2026-05-21
**Status**: Planning Complete

---

## Overview

The CanvasTEKK Workflow Engine (v1.0.1-dev) updated its node registration endpoint to a new `RegisterNodeRequest` schema. The SDK's `register_node()` sends SDK-native field names that don't match the engine API, causing registration failures.

## Critical Mismatches

| # | Issue | Severity | Field |
|---|-------|----------|-------|
| 1 | SDK sends `title`, API expects `label` | CRITICAL (blocking) | `title` → `label` |
| 2 | Response wrapper changed `data` → `node` | High | `_extract_node_data()` |
| 3 | Extra fields sent (`id`, `default_retry`) | Medium | Payload filtering |
| 4 | Missing `tags` parameter | Low | New optional param |

## Implementation Phases

### Phase 1: Setup & Analysis
- [ ] Review current `registry.py` implementation
- [ ] Review `definition.py` for `export_definition()` pattern reference
- [ ] Confirm engine API `RegisterNodeRequest` schema from Confluence analysis
- [ ] Check existing tests for `register_node()` and `_extract_node_data()`

### Phase 2: Core Implementation — `registry.py`
- [ ] Refactor `register_node()` to build payload inline with explicit field mapping
  - Map `definition.title` → `"label"` (CRITICAL fix)
  - Map `definition.default_retry` → `"retry"`
  - Remove `id` field from payload
  - Add `styles`, `category`, `token_cost`, `timeout_seconds`, `is_control_flow`
- [ ] Add `tags: list[str] | None = None` parameter to `register_node()`
- [ ] Include `tags` in the manifest payload
- [ ] Update `_extract_node_data()` to handle both `{"node": ...}` and `{"data": ...}` response wrappers
- [ ] Ensure backward compatibility with old response format

### Phase 3: Testing
- [ ] Update existing unit tests for `register_node()` with new payload shape
- [ ] Add test for `_extract_node_data()` with new `{"node": ...}` response format
- [ ] Add test for `_extract_node_data()` with old `{"data": ...}` response format (backward compat)
- [ ] Add test for `tags` parameter (default empty, custom tags)
- [ ] Verify `poetry run ruff check canvastekk_workflow_sdk/ tests/` passes
- [ ] Verify `poetry run pytest -v` passes

### Phase 4: Documentation & Examples
- [ ] Update `docs/EXTERNAL-AUTHOR-GUIDE.md` with correct field mapping documentation
- [ ] Update `examples/echo_node/` registration example if needed
- [ ] Ensure docstrings on `register_node()` reflect the new `tags` parameter

### Phase 5: Final Validation
- [ ] Run full test suite: `poetry run pytest -v`
- [ ] Run linter: `poetry run ruff check canvastekk_workflow_sdk/ tests/`
- [ ] Verify all acceptance criteria from DA-1016 are met
- [ ] Code review preparation

## Acceptance Criteria

- [ ] `register_node()` sends `label` field (mapped from `definition.title`)
- [ ] `register_node()` sends `retry` field (mapped from `definition.default_retry`)
- [ ] `register_node()` no longer sends `id` field in the payload
- [ ] `_extract_node_data()` handles both old and new response wrappers
- [ ] `register_node()` accepts an optional `tags` parameter
- [ ] Linting passes
- [ ] All tests pass
- [ ] Documentation updated

## Confluence Reference

Full analysis: [SDK-to-Engine API Mismatch Analysis Upgrade Guide](https://betekk.atlassian.net/wiki/spaces/CanvasTEKK/pages/100990979/SDK-to-Engine+API+Mismatch+Analysis+Upgrade+Guide)

---
*Tracking progress with ticket-plan-workflow-skill*
