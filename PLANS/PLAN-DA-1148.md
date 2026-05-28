# PLAN-DA-1148: Create TypeScript SDK Replica

> **JIRA Ticket:** [DA-1148](https://betekk.atlassian.net/browse/DA-1148)
> **Branch:** `DA-1148`
> **Status:** Planning
> **Created:** 2026-05-28

## Overview

Create an exact TypeScript replica of the CanvasTEKK Workflow SDK (`python/canvastekk_workflow_sdk/`) under `typescript/` with full feature parity. The TypeScript SDK must produce the same node contract (HTTP endpoints, request/response shapes, manifest format) so that the engine cannot distinguish between a Python node and a TypeScript node.

**Target Version:** `0.13.0`

**Stack:** Node 24+, Express 5, Zod, Ajv, tsup, Vitest, TypeScript 5.8+ strict

**Estimated Files:** ~44 (30 source, 7 test, 5 config, 1 CI, 1 example)

---

## Phase 1: Foundation — Types, Validation, Exceptions

- [ ] Create `typescript/` directory structure with `src/` layout
- [ ] Create `src/version.ts` — SDK version constant (`0.13.0`)
- [ ] Create `src/definition.ts` — Zod schemas for `NodeDefinition`, `RetryConfig`, `NodeStyles`, `ColorPreset` (22 values)
- [ ] Create `src/definition.ts` — `getNodeId(def)` computed function → `"name-v1.0.0"`
- [ ] Create `src/definition.ts` — `getFileInputFields()`, `getFileOutputFields()`, `validateFileInput()` helpers
- [ ] Create `src/definition.ts` — Schema validation: reject `format: "binary"`, enforce `type: "string"` for file fields
- [ ] Create `src/exceptions.ts` — Full error hierarchy: `NodeExecutionError`, `NodeTimeoutError`, `NodeValidationError`, `NodeOutputValidationError`, `NodeIOError`, `NodeConfigurationError`, `WorkflowExecutionError`, `WorkflowValidationError`, `RegistrationError`
- [ ] Create `src/exceptions.ts` — `ERROR_CODE_TO_HTTP_STATUS` mapping, `getHttpStatusForError()` function
- [ ] Create `src/request.ts` — Zod schema for `NodeExecutionRequest`
- [ ] Create `src/response.ts` — Zod schemas for `NodeExecutionResponse`, `HealthResponse`
- [ ] Write unit tests for schema validation (valid/invalid cases, file field constraints)
- [ ] Write unit tests for error hierarchy and HTTP status mapping

**Acceptance Criteria:**
- `NodeDefinitionSchema.parse()` validates name (slug), version (semver), file field constraints
- Each exception has correct `errorCode` and `toDict()` serialization
- `getHttpStatusForError()` maps every error code to correct HTTP status
- Unit tests pass for all schema validation cases

---

## Phase 2: BaseNode + Execution Pipeline + Middleware

- [ ] Create `src/context.ts` — `ExecutionContext` with `outputDir`, `downloadsDir` (lazy), `outputPath()`, `reportProgress()`, `recordTokenUsage()`, `metadata`
- [ ] Create `src/middleware.ts` — `NodeMiddleware` interface: `onBeforeExecute()`, `onAfterExecute()`, `onError()`
- [ ] Create `src/middleware.ts` — Built-in: `LoggingMiddleware`, `TimingMiddleware`
- [ ] Create `src/observability.ts` — `MetricsCollector` with `record()`, `getSummary()`
- [ ] Create `src/base-node.ts` — `BaseNode` abstract class with constructor-time definition validation
- [ ] Create `src/base-node.ts` — Full `run()` pipeline: validate inputs → create context → download file inputs → middleware before → execute → validate outputs → middleware after → metrics → response
- [ ] Implement file download using native `fetch` with streaming
- [ ] Write unit tests for `ExecutionContext`
- [ ] Write unit tests for middleware hooks (before/after/error)
- [ ] Write unit tests for `MetricsCollector.getSummary()`
- [ ] Write integration tests for `BaseNode.run()` full pipeline

**Acceptance Criteria:**
- `BaseNode` constructor validates `definition` — throws on invalid
- `run()` pipeline executes: validate → download → execute → validate output → response
- Middleware hooks fire correctly (before/after/error)
- `MetricsCollector.getSummary()` returns correct statistics

---

## Phase 3: Express HTTP Server

- [ ] Create `src/app.ts` — `createNodeApp(node, opts)` Express factory with `X-SDK-Version` header
- [ ] Implement `POST /execute` — validate body, enforce timeout (`AbortSignal.timeout()`), run node, upload outputs
- [ ] Implement `GET /health` — HealthResponse
- [ ] Implement `GET /manifest` — NodeDefinition + `sdkVersion` + `mode`
- [ ] Implement `GET /definition` — 301 redirect to `/manifest`
- [ ] Implement `POST /hook` — 501 if not overridden
- [ ] Implement `GET /metrics` — MetricsCollector summary
- [ ] Implement `GET /live` — liveness probe
- [ ] Implement `GET /ready` — readiness probe (503 on failed checks)
- [ ] Create `src/auth.ts` — `NodeAuth` factory: `apiKey()`, `jwt()`, `keycloak()` (Express middleware)
- [ ] Create `src/auth.ts` — Dev mode bypass (`CANVASTEKK_DEV_MODE`)
- [ ] Create `src/uploads.ts` — `S3PresignedUploader` using native `fetch` for PUT
- [ ] Create `src/router.ts` — `createMultiNodeApp(nodes)` for mounting multiple nodes under URL prefixes
- [ ] Implement error handler mapping `NodeExecutionError` → HTTP status codes
- [ ] Write integration tests for all 8 endpoints
- [ ] Write tests for auth middleware (API key, dev mode bypass)
- [ ] Write tests for error handler mapping

**Acceptance Criteria:**
- All 8 endpoints respond correctly
- Timeout enforcement via `AbortSignal.timeout()`
- Auth middleware works (API key, dev mode bypass)
- Error handler maps exceptions to correct HTTP status codes
- `X-SDK-Version` header present on all responses

---

## Phase 4: Data Contracts + Registry

- [ ] Create `src/contracts/point3d.ts` — `Point3D`, `BoundingBox3D` with Zod schemas
- [ ] Create `src/contracts/instance.ts` — `Instance`, `InstanceSet` with helper methods (`getInstancesByClass()`)
- [ ] Create `src/contracts/measurement.ts` — `Measurement`, `MeasurementSet` with `getMeasurement()` helper
- [ ] Create `src/contracts/plane.ts` — `Plane`, `PlaneSet` with `getPlaneByLabel()` helper
- [ ] Create `src/registry.ts` — `buildRegistryPayload()` with field mapping: `title→label`, `defaultRetry→retry`, omit `id`
- [ ] Create `src/registry.ts` — `registerNode()` POST to engine registry with native `fetch`
- [ ] Create `src/registry.ts` — `exportDefinition()` write registry JSON to file
- [ ] Write unit tests for all contract Zod schemas
- [ ] Write unit tests for `buildRegistryPayload()` field mapping
- [ ] Write integration tests for `registerNode()` with correct auth headers

**Acceptance Criteria:**
- All contract schemas validate with Zod
- `buildRegistryPayload()` maps `title→label`, `defaultRetry→retry`, omits `id`
- `registerNode()` sends correct auth headers
- `S3PresignedUploader` uploads via native `fetch`

---

## Phase 5: Workflow Builder + Runner

- [ ] Create `src/workflow/models.ts` — Enums: `EdgeType`, `ResolutionStrategy`; types: `WorkflowSpec`, `WorkflowNode`, `WorkflowEdge`, `ErrorPolicy`
- [ ] Create `src/workflow/builder.ts` — `WorkflowBuilder` fluent API: `addStart()`, `addEnd()`, `addNode()`, `connect()`, `build()`
- [ ] Create `src/workflow/executor.ts` — `InProcessExecutor` (runs `BaseNode.execute()` directly) + `HttpExecutor` (POST to `/execute`)
- [ ] Create `src/workflow/level.ts` — `computeLevels()` BFS topological level computation
- [ ] Create `src/workflow/resolver.ts` — Input resolver with dot-path traversal (`data.url` → `data["data"]["url"]`)
- [ ] Create `src/workflow/validation.ts` — Graph validation: node ID uniqueness, edge references, START/END constraints, cycle detection (Kahn's), connectivity
- [ ] Create `src/workflow/control-flow.ts` — Control flow: `__start__`, `__end__`, `__if__`, `__stop-error__`
- [ ] Create `src/workflow/runner.ts` — `WorkflowRunner` with `ErrorPolicy`, `outputDir`, `cleanup`, BFS level-based execution, `Promise.allSettled()` for parallel within levels
- [ ] Document: parallel nodes writing same filename = undefined behavior (JSDoc)
- [ ] Document: `outputDir` only works with `InProcessExecutor` (JSDoc)
- [ ] Write unit tests for `WorkflowBuilder` (valid specs, validation errors)
- [ ] Write unit tests for `computeLevels()` topological ordering
- [ ] Write unit tests for input resolver (dot-path traversal)
- [ ] Write unit tests for graph validation (cycles, missing nodes, connectivity)
- [ ] Write integration tests for `WorkflowRunner` (sequential, parallel, error policies, cleanup)

**Acceptance Criteria:**
- `WorkflowBuilder` produces valid `WorkflowSpec`
- `computeLevels()` returns correct topological levels
- `WorkflowRunner` executes levels in order, parallel within levels
- Shared `outputDir` enables file-passing between nodes
- `fail_fast` stops on first failure; `continue` runs all levels
- Auto-created temp dirs are cleaned up (even on exceptions)

---

## Phase 6: Testing, CLI, Packaging, CI/CD

- [ ] Create `src/testing/index.ts` — `LocalFileServer` using Node `http.createServer` with `Symbol.dispose`/`Symbol.asyncDispose`
- [ ] Implement path traversal protection in `LocalFileServer`
- [ ] Create `src/cli.ts` — CLI: `npx canvastekk-sdk validate <file:export> [--json]`, `npx canvastekk-sdk init`, `--version`
- [ ] Create `src/index.ts` — Barrel export matching Python's `__all__` (70+ exports)
- [ ] Create `package.json` — Project config with `canvastekk-workflow-sdk` name, GitHub Packages registry, scripts (build, test, lint, typecheck)
- [ ] Create `tsconfig.json` — TypeScript 5.8+ strict config with ESM target
- [ ] Create `tsup.config.ts` — ESM + CJS dual output + `.d.ts` generation
- [ ] Create `vitest.config.ts` — Vitest configuration
- [ ] Verify `npm run build` produces working ESM + CJS + `.d.ts` in `dist/`
- [ ] Verify `npm run test` passes full test suite
- [ ] Create `.github/workflows/ci-typescript.yml` — Node 24, npm ci, lint, typecheck, test (triggered on `typescript/**` paths)
- [ ] Update `.github/workflows/release.yml` — Add TypeScript SDK build + publish steps (conditional on `typescript/package.json` existing)
- [ ] Create `examples/echo-node-typescript/` — Canonical TypeScript reference implementation
- [ ] Final feature parity audit: every Python export has TypeScript equivalent

**Acceptance Criteria:**
- `npm run build` produces working ESM + CJS + `.d.ts` in `dist/`
- `npm run test` passes full test suite
- `LocalFileServer` serves files + path traversal protection
- CLI `validate` reports file field warnings
- `ci-typescript.yml` runs on `typescript/**` path changes
- `release.yml` builds, publishes, and uploads TypeScript SDK

---

## Key Constraints

- **Node `id` is auto-derived** from `name-v{version}` — never manual. Warn if user provides `id`.
- **File fields must use `format: "file"` + `type: "string"`** — reject `format: "binary"` from day one.
- **`registerNode()` payload** must match engine `RegisterNodeRequest` exactly: `title→label`, `defaultRetry→retry`, omit `id`.
- **Dev mode auth bypass** (`CANVASTEKK_DEV_MODE`) included in all auth backends.
- **Initialize result variables before try blocks** — avoid undefined references.
- **Feature parity guarantee** — all 70+ Python exports must have TypeScript equivalents.
- **API shapes** must be byte-identical to Python SDK output.
