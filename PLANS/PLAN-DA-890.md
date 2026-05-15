# PLAN — DA-890: Enable public-endpoint deployment for canvastekk-workflow-sdk nodes (v0.5.0 hardening)

**Branch:** `DA-890`
**Jira:** [DA-890](https://betekk.atlassian.net/browse/DA-890)
**Repo:** https://github.com/nus-cee/canvastekk-workflow-sdk
**Priority:** High
**Target Version:** `0.5.0` (minor bump from `0.4.9`)
**Effort:** ~5.5 days

---

## Context

All changes are **additive and backward-compatible**. Existing `BaseNode` subclasses with `.create_app()` continue to work without modification. The `execute(inputs, context)` contract, all 6 endpoints, and the public API surface remain unchanged.

### Dependencies

| Dependency | Ticket | Status | Impact on SDK |
| --- | --- | --- | --- |
| Engine Keycloak JWT auth | DA-869 | Done | SDK must validate JWT tokens from orchestrator |
| Engine CORS config | DA-867 | In Progress | SDK should support configurable CORS |
| Engine `POST /api/runs` | DA-869 | Done | SDK `/manifest` must produce registry-compatible definitions |
| SDK monorepo restructuring | DA-876 | Done | SDK already lives in `python/` subdirectory |
| SDK semantic versioning | DA-881 | Done | `git-cliff` automated releases already in place |
| SDK wheel migration | DA-884 | Backlog | Nodes will consume SDK from published wheel |

---

## Phase 1: Core SDK Stability Fixes (P0 — ~2 days)

### 1.1 Fix async event loop blocking
- [x] Wrap `node.run()` in `asyncio.to_thread()` inside the `POST /execute` async endpoint in `app.py`
- [x] Verify `run()` is never called directly from an async context without thread offloading
- [x] Add test: confirm async endpoint does not block the event loop during long `execute()`

### 1.2 Thread-safe MetricsCollector
- [x] Add `threading.Lock` to `MetricsCollector.record()` in `observability.py`
- [x] Add `threading.Lock` to `MetricsCollector.get_summary()` and `clear()`
- [x] Add concurrent stress test: multiple threads calling `record()` simultaneously
- [x] Verify `get_summary()` returns consistent results under concurrent writes

### 1.3 Output schema validation
- [x] Add `_validate_outputs()` method to `BaseNode` in `base.py`, mirroring existing `_validate_inputs()`
- [x] Validate return value of `execute()` against `output_schema` in `run()` method
- [x] Raise `NodeOutputValidationError` on contract violations (add to `exceptions.py`)
- [x] Add tests: valid output passes, invalid output raises, missing required fields caught

### 1.4 Extract S3 upload logic
- [x] Create `canvastekk_workflow_sdk/uploads.py` with `OutputUploader` protocol
- [x] Implement `S3PresignedUploader` class (extract from `_upload_to_presigned` and `_upload_outputs_to_s3` in `app.py`)
- [x] Handle edge case: S3 upload failure after successful `execute()` should not report entire execution as failed — log warning instead
- [x] Add tests for `S3PresignedUploader` with mocked urllib requests
- [x] Slim down `app.py` — replace inline S3 logic with uploader instance

### 1.5 Configurable output directory
- [x] Add `CANVASTEKK_OUTPUT_DIR` env var support to `ExecutionContext` in `context.py`
- [x] Fall back to existing `/tmp/{run_id}/{node_id}` if env var not set
- [x] Add test for env var override

---

## Phase 2: Auth & Security Integration (P1 — ~2 days)

### 2.1 FastAPI dependency injection point
- [x] Add `dependencies` parameter to `create_node_app()` in `app.py` (list of FastAPI `Depends()` items)
- [x] Apply dependencies globally via `APIRouter(dependencies=...)` + `app.include_router(router)`
- [x] Ensure backward-compatible: default is `None` (no auth)
- [x] Add test: custom dependency is invoked on each endpoint

### 2.2 Auth module (layered, optional)
- [x] Create `canvastekk_workflow_sdk/auth.py` with layered auth strategy
- [x] **Layer 0 (default): No auth** — nodes work out of the box, zero config
- [x] **Layer 1 (simple): API key** — `NodeAuth.api_key(key_env_var="CANVASTEKK_API_KEY")` validates `X-API-Key` header. Shared secret between engine and node. Simplest for customers.
- [x] **Layer 2 (signed): JWT** — `NodeAuth.jwt(secret_env_var="CANVASTEKK_JWT_SECRET")` validates HMAC-signed tokens from engine. No Keycloak dependency needed.
- [x] **Layer 3 (enterprise): Keycloak OIDC** — `NodeAuth.keycloak(server_url=..., realm=..., audience=...)` validates RS256 JWT with JWKS caching (optional, for customers with existing Keycloak)
- [x] All layers expose `.as_dependency()` returning FastAPI `Depends()` callable
- [x] Dev-mode bypass: skip validation when `CANVASTEKK_DEV_MODE=true`
- [x] Add `PyJWT` as optional dependency in `pyproject.toml` (for Layer 2+)
- [x] Add tests: each layer works independently, dev-mode bypass, invalid credentials rejected

### 2.3 Extra routes support
- [x] Add `extra_routes` parameter to `create_node_app()` accepting list of FastAPI `APIRouter` instances
- [x] Include each router on the app during creation
- [x] Add test: custom route is accessible on the created app

### 2.4 Lifecycle hooks
- [x] Add `on_startup()` and `on_shutdown()` async methods to `BaseNode` in `base.py`
- [x] Register as FastAPI lifespan events in `create_node_app()`
- [x] Default implementations are no-ops (backward-compatible)
- [x] Add test: `on_startup` fires on app start, `on_shutdown` fires on app stop

---

## Phase 3: Deployment & Developer Experience (P2 — ~1.5 days)

### 3.1 Registry helper
- [x] Create `canvastekk_workflow_sdk/registry.py` with `register_node()` function
- [x] Accept node instance, registry URL, and auth credentials
- [x] POST node manifest (from `export_definition()`) to registry endpoint
- [x] Verify `invoke_url` field mapping matches engine registry contract
- [x] Add tests with mocked HTTP calls

### 3.2 Multi-node router
- [x] Create `canvastekk_workflow_sdk/router.py` with `create_multi_node_app()` function
- [x] Accept dict of `{prefix: BaseNode}` and create a single FastAPI app mounting each node under its prefix
- [x] Each node gets its own set of 6 endpoints under `/prefix/execute`, `/prefix/health`, etc.
- [x] Add test: two nodes on same app, both respond independently

### 3.3 Verify export_definition() contract
- [x] Compare `NodeDefinition.to_dict()` output with engine's `node-manifest.json` schema
- [x] Verify `invoke_url` field is present and correctly populated
- [x] Add any missing fields required by engine registry
- [x] Add test for registry-compatible manifest output

### ~~3.4 Deployment documentation~~ (removed)
Deployment docs (Dockerfile, Traefik, serverless) belong in a node-template repo, not the SDK itself. Customers install the SDK via pip — they don't deploy it.

### 3.5 Remove global MetricsCollector singleton
- [x] Remove `_default_collector` module-level singleton from `observability.py`
- [x] Remove `get_default_collector()` function
- [x] Each `BaseNode` instance creates its own `MetricsCollector()` in `__init__()`
- [x] Ensure existing tests that rely on shared collector still pass (update as needed)

---

## Phase 4: Testing & Validation

- [x] All existing tests pass without modification (backward compatibility)
- [x] New modules (`auth.py`, `uploads.py`, `registry.py`, `router.py`) have test coverage >= 80%
- [x] Ruff lint passes clean: `ruff check python/`
- [x] Type checking passes: `mypy python/` (if configured) or verify type hints
- [x] Integration test: full lifecycle — create node with auth, execute, verify JWT, upload output
- [x] Verify `node.run()` does not block async event loop
- [x] Verify thread safety of `MetricsCollector` under concurrent load

---

## Acceptance Criteria

- [x] `node.run()` does not block the async event loop (verified via `asyncio.to_thread`)
- [x] `MetricsCollector.record()` is thread-safe
- [x] Output validation against `output_schema` catches contract violations
- [x] S3 upload logic extracted to testable `OutputUploader` protocol
- [x] `create_node_app()` accepts `dependencies=[Depends(auth)]` for JWT validation
- [x] Nodes can validate Keycloak JWTs matching DA-869's auth pattern
- [x] `on_startup()` / `on_shutdown()` lifecycle hooks work on FastAPI app events
- [x] Output directory configurable via `CANVASTEKK_OUTPUT_DIR` env var
- [x] All existing tests pass without modification (backward compatibility)
- [x] New modules have test coverage >= 80%
- [x] Ruff lint + mypy pass clean

---

## Phase 5: Code Review Fixes

### 5.1 Fix racy timeout enforcement (Critical)
- [x] Remove post-hoc `time.perf_counter()` timeout heuristic from `base.py:run()`
- [x] Use `asyncio.wait_for()` in `app.py:253` to actively enforce timeout around `asyncio.to_thread(node.run, ...)`
- [x] Update existing timeout tests to verify active enforcement
- [x] Verify no exception misclassification (e.g., `ValueError` near timeout threshold)

### 5.2 Constant-time API key comparison (Major — Security)
- [x] Replace `!=` string comparison in `auth.py:80` with `hmac.compare_digest()`
- [x] Add test for timing-safe comparison

### 5.3 JWKS caching with TTL (Major — Performance)
- [x] Add TTL-based JWKS cache to `_KeycloakAuth` (5-minute TTL)
- [x] Cache `_jwks_data` and `_jwks_fetched_at` as instance attributes
- [x] Update tests to verify caching behavior (single fetch across multiple requests)

### 5.4 Fix OutputUploader protocol mismatch (Major — Design)
- [x] Add `upload_file()` method to `OutputUploader` protocol
- [x] Update return type of `get_default_uploader()` to `OutputUploader`
- [x] Verify custom uploader implementations work with both protocol methods

### 5.5 Fix fastapi_kwargs typing in app.py (Major — Types)
- [x] Change `**fastapi_kwargs: object` to `**fastapi_kwargs: Any` in `app.py:create_node_app()`
- [x] Verify mypy passes

---

## New Files

| File | Purpose |
| --- | --- |
| `canvastekk_workflow_sdk/auth.py` | Layered auth (optional): API key, JWT, Keycloak |
| `canvastekk_workflow_sdk/uploads.py` | `OutputUploader` protocol + `S3PresignedUploader` |
| `canvastekk_workflow_sdk/registry.py` | `register_node()` CI/CD convenience function |
| `canvastekk_workflow_sdk/router.py` | Multi-node app factory |

## Modified Files

| File | Changes |
| --- | --- |
| `app.py` | Slim down (remove S3 logic), add `dependencies` and `extra_routes` params |
| `base.py` | Add `on_startup()`/`on_shutdown()` hooks, fix async blocking, add `_validate_outputs()` |
| `observability.py` | Thread-safe `MetricsCollector`, remove global singleton |
| `context.py` | Configurable output directory via `CANVASTEKK_OUTPUT_DIR` |
| `exceptions.py` | Add `OutputValidationError` |
| `pyproject.toml` | Bump to `0.5.0`, add optional auth dependencies |

---

## Flow

```
Phase 1 (P0): Core Stability
  → Fix async blocking (asyncio.to_thread)
  → Thread-safe MetricsCollector (threading.Lock)
  → Output validation (_validate_outputs)
  → Extract S3 uploads (OutputUploader protocol)
  → Configurable output dir (env var)

Phase 2 (P1): Auth & Security
  → FastAPI dependency injection (dependencies param)
  → Keycloak JWT auth module (auth.py)
  → Extra routes support
  → Lifecycle hooks (on_startup/on_shutdown)

Phase 3 (P2): Deployment & DX
  → Registry helper (register_node)
  → Multi-node router (create_multi_node_app)
  → Verify manifest contract
  → Deployment docs
  → Remove global singleton

Phase 4: Testing & Validation
  → All existing tests pass
  → New modules >= 80% coverage
  → Ruff + mypy clean
  → Integration test (auth + execute + upload)

Phase 5: Code Review Fixes
  → Critical: Fix racy timeout enforcement (asyncio.wait_for)
  → Major: Constant-time API key comparison (hmac.compare_digest)
  → Major: JWKS caching with TTL in _KeycloakAuth
  → Major: Fix OutputUploader protocol / upload_file mismatch
  → Major: Fix fastapi_kwargs typing in app.py
```
