# PLAN-DA-931: SDK register_node() service token support

**Jira Ticket**: [DA-931](https://betekk.atlassian.net/browse/DA-931)
**Epic**: [DA-929](https://betekk.atlassian.net/browse/DA-929) — Automated Node Registration & Workflow Config Seeding
**Branch**: `feature/DA-931`
**Repo**: `canvastekk-workflow-sdk`
**Priority**: P1 (blocks DA-938: T11 Create register_nodes.py CI/CD script)
**Size**: S
**Status**: Done

---

## Problem

The SDK's `register_node()` function in `canvastekk_workflow_sdk/registry.py` currently only supports `api_key` authentication. The new automated node registration system (DA-929) requires a `service_token` auth mode for CI/CD pipelines where nodes register themselves without individual API keys.

## Context

Part of the **DA-929** epic replacing the static `node-manifest.json` approach with API-based node registration. The SDK ships only the function signature — it never contains actual token values. The real token lives in GitHub Secrets of the nodes repo, injected at CI runtime only.

### Architecture (SDK = Envelope)

- **SDK** knows _how_ to send the `X-Service-Token` header (the envelope)
- **Nodes CI/CD** has the secret (the courier)
- **Engine** validates the token (the verifier)

---

## Files to Change

| File | Change |
|------|--------|
| `canvastekk_workflow_sdk/registry.py` | Add `service_token` param to `register_node()`, send as `X-Service-Token` header |
| `canvastekk_workflow_sdk/registry.py` | Update return type hint to handle both `RegistryNodeDefinition` and `RegisterNodeResponse` wrapper |
| `tests/test_registry.py` (or equivalent) | Unit tests for both auth modes |

---

## Acceptance Criteria

- [x] `register_node(node, url, service_token="svs_xxx")` sends `X-Service-Token` header
- [x] `service_token` defaults to `None` — no hardcoded or example values anywhere
- [x] Backward compatible: `api_key` param still works as before
- [x] Can handle both old response format (`RegistryNodeDefinition` directly) and new format (`RegisterNodeResponse` wrapper)
- [x] Unit tests for both auth modes

---

## Implementation Phases

### Phase 1: Update `register_node()` signature and auth header logic

- [x] Add `service_token: str | None = None` parameter to `register_node()`
- [x] When `service_token` is provided, add `X-Service-Token` header to the HTTP request
- [x] Ensure `service_token` defaults to `None` — never hardcode or log token values
- [x] Validate that at least one auth method is provided (`api_key` or `service_token`), raise `ValueError` if neither
- [x] `service_token` takes precedence over `api_key` when both are provided

### Phase 2: Update response handling for new wrapper format

- [x] Add `_extract_node_data()` helper for response normalization
- [x] Handle both old format (`RegistryNodeDefinition` directly) and new format (`RegisterNodeResponse` wrapper with `data` key)

### Phase 3: Unit tests

- [x] Test `register_node()` with `api_key` auth (existing behavior, regression check)
- [x] Test `register_node()` with `service_token` auth (new behavior)
- [x] Test that `X-Service-Token` header is sent when `service_token` is provided
- [x] Test that `ValueError` is raised when neither `api_key` nor `service_token` is provided
- [x] Test `_extract_node_data()` for both old and new response formats
- [x] Test `service_token` precedence over `api_key`
- [x] 24 tests total, all passing

---

## Dependencies

- **None** — can be done in parallel with DA-930 (T1), DA-933 (T2), DA-932 (T6)

## Blocked By

- DA-938 (T11) and DA-943 (T15) are blocked by this ticket

## Security Notes

- Never add a default or example token value in the SDK
- Keep `service_token` param `None` by default so callers must provide it explicitly
- This prevents accidental token leakage through debug logs or default configs
