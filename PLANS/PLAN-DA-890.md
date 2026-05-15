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
- [ ] Add `dependencies` parameter to `create_node_app()` in `app.py` (list of FastAPI `Depends()` items)
- [ ] Apply dependencies globally via `app.include_router()` or per-endpoint
- [ ] Ensure backward-compatible: default is `None` (no auth)
- [ ] Add test: custom dependency is invoked on each endpoint

### 2.2 Auth module (layered, optional)
- [ ] Create `canvastekk_workflow_sdk/auth.py` with layered auth strategy
- [ ] **Layer 0 (default): No auth** — nodes work out of the box, zero config
- [ ] **Layer 1 (simple): API key** — `NodeAuth.api_key(key_env_var="CANVASTEKK_API_KEY")` validates `X-API-Key` header. Shared secret between engine and node. Simplest for customers.
- [ ] **Layer 2 (signed): JWT** — `NodeAuth.jwt(secret_env_var="CANVASTEKK_JWT_SECRET")` validates HMAC-signed tokens from engine. No Keycloak dependency needed.
- [ ] **Layer 3 (enterprise): Keycloak OIDC** — `NodeAuth.keycloak(server_url=..., realm=..., audience=...)` validates RS256 JWT with JWKS caching (optional, for customers with existing Keycloak)
- [ ] All layers expose `.as_dependency()` returning FastAPI `Depends()` callable
- [ ] Dev-mode bypass: skip validation when `CANVASTEKK_DEV_MODE=true`
- [ ] Add `PyJWT` as optional dependency in `pyproject.toml` (for Layer 2+)
- [ ] Add tests: each layer works independently, dev-mode bypass, invalid credentials rejected

### 2.3 Extra routes support
- [ ] Add `extra_routes` parameter to `create_node_app()` accepting list of FastAPI `APIRouter` instances
- [ ] Include each router on the app during creation
- [ ] Add test: custom route is accessible on the created app

### 2.4 Lifecycle hooks
- [ ] Add `on_startup()` and `on_shutdown()` async methods to `BaseNode` in `base.py`
- [ ] Register as FastAPI lifespan events in `create_node_app()`
- [ ] Default implementations are no-ops (backward-compatible)
- [ ] Add test: `on_startup` fires on app start, `on_shutdown` fires on app stop

---

## Phase 3: Deployment & Developer Experience (P2 — ~1.5 days)

### 3.1 Registry helper
- [ ] Create `canvastekk_workflow_sdk/registry.py` with `register_node()` function
- [ ] Accept node instance, registry URL, and auth credentials
- [ ] POST node manifest (from `export_definition()`) to registry endpoint
- [ ] Verify `invoke_url` field mapping matches engine registry contract
- [ ] Add tests with mocked HTTP calls

### 3.2 Multi-node router
- [ ] Create `canvastekk_workflow_sdk/router.py` with `create_multi_node_app()` function
- [ ] Accept dict of `{prefix: BaseNode}` and create a single FastAPI app mounting each node under its prefix
- [ ] Each node gets its own set of 6 endpoints under `/prefix/execute`, `/prefix/health`, etc.
- [ ] Add test: two nodes on same app, both respond independently

### 3.3 Verify export_definition() contract
- [ ] Compare `NodeDefinition.to_dict()` output with engine's `node-manifest.json` schema
- [ ] Verify `invoke_url` field is present and correctly populated
- [ ] Add any missing fields required by engine registry
- [ ] Add test for registry-compatible manifest output

### 3.4 Deployment documentation
- [ ] Add Dockerfile pattern to `python/README.md` (multi-stage build, uvicorn entrypoint)
- [ ] Add Traefik/reverse-proxy config example
- [ ] Add serverless deployment notes (AWS Lambda, GCP Cloud Run)
- [ ] Document auth configuration (layered: API key → JWT → Keycloak)
- [ ] Document `CANVASTEKK_OUTPUT_DIR`, `CANVASTEKK_API_KEY`, and new env vars

### 3.5 Remove global MetricsCollector singleton
- [ ] Remove `_default_collector` module-level singleton from `observability.py`
- [ ] Remove `get_default_collector()` function
- [ ] Each `BaseNode` instance creates its own `MetricsCollector()` in `__init__()`
- [ ] Ensure existing tests that rely on shared collector still pass (update as needed)

---

## Phase 4: Testing & Validation

- [ ] All existing tests pass without modification (backward compatibility)
- [ ] New modules (`auth.py`, `uploads.py`, `registry.py`, `router.py`) have test coverage >= 80%
- [ ] Ruff lint passes clean: `ruff check python/`
- [ ] Type checking passes: `mypy python/` (if configured) or verify type hints
- [ ] Integration test: full lifecycle — create node with auth, execute, verify JWT, upload output
- [ ] Verify `node.run()` does not block async event loop
- [ ] Verify thread safety of `MetricsCollector` under concurrent load

---

## Acceptance Criteria

- [ ] `node.run()` does not block the async event loop (verified via `asyncio.to_thread`)
- [ ] `MetricsCollector.record()` is thread-safe
- [ ] Output validation against `output_schema` catches contract violations
- [ ] S3 upload logic extracted to testable `OutputUploader` protocol
- [ ] `create_node_app()` accepts `dependencies=[Depends(auth)]` for JWT validation
- [ ] Nodes can validate Keycloak JWTs matching DA-869's auth pattern
- [ ] `on_startup()` / `on_shutdown()` lifecycle hooks work on FastAPI app events
- [ ] Output directory configurable via `CANVASTEKK_OUTPUT_DIR` env var
- [ ] All existing tests pass without modification (backward compatibility)
- [ ] New modules have test coverage >= 80%
- [ ] Ruff lint + mypy pass clean

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
```
