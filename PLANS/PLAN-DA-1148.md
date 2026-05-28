# PLAN-DA-1148: Create TypeScript SDK Replica

> **JIRA Ticket:** [DA-1148](https://betekk.atlassian.net/browse/DA-1148)
> **Branch:** `DA-1148`
> **Status:** Planning (Revised after architecture review)
> **Created:** 2026-05-28
> **Revised:** 2026-05-28

## Overview

Create an exact TypeScript replica of the CanvasTEKK Workflow SDK (`python/canvastekk_workflow_sdk/`) under `typescript/` with full feature parity. The TypeScript SDK must produce the same node contract (HTTP endpoints, request/response shapes, manifest format) so that the engine cannot distinguish between a Python node and a TypeScript node.

**Target Version:** `0.13.0`

**Stack:** Node 24+, Express 4, Zod, Ajv (Draft 7), tsup, Vitest, TypeScript 5.8+ strict

**Estimated Files:** ~60 (37 source, 10 test, 5 config, 1 CI, 1 example)

### Behavioral Differences (Documented Parity Exceptions)

| Python Behavior | TypeScript Equivalent | Why Different |
|----------------|----------------------|---------------|
| `__init_subclass__` validates `definition` at class definition time (import time) | Constructor-time validation in `BaseNode` constructor | TypeScript has no class-definition-time hooks; validation deferred to `new` |
| `asyncio.to_thread()` offloads blocking `execute()` to thread pool | `worker_threads` offload for CPU-heavy `execute()` (opt-in) | Node.js is single-threaded; blocking `execute()` freezes Express |
| `threading.Lock` on `MetricsCollector` | No lock needed | Node.js is single-threaded |
| FastAPI `Depends()` for auth middleware | Express middleware functions `(req, res, next) => {}` | Framework difference |
| `httpx.stream()` for file downloads | Native `fetch` + `ReadableStream` | Node 24 has built-in streaming fetch |

---

## Phase 1: Foundation — Types, Validation, Exceptions

- [x] Create `typescript/` directory structure with `src/` layout
- [x] Create `src/version.ts` — SDK version constant (`"0.13.0"`)
- [x] Create `src/definition.ts` — Zod schemas for `NodeDefinition`, `RetryConfig`, `NodeStyles`, `ColorPreset` (22 values matching Python's `ColorPreset` literal)
- [x] Create `src/definition.ts` — `getNodeId(def)` computed function → `"name-v1.0.0"`
- [x] Create `src/definition.ts` — `getFileInputFields()`, `getFileOutputFields()`, `validateFileInput()` helpers
- [x] Create `src/definition.ts` — Schema validation: reject `format: "binary"` (DA-894), enforce `type: "string"` for file fields, warn on manual `id` (DA-1014)
- [x] Create `src/exceptions.ts` — Full error hierarchy: `NodeExecutionError` (base with `message`, `errorCode`, `details`, `toDict()`), `NodeTimeoutError` (with `timeoutSeconds`), `NodeValidationError` (with `errors[]`), `NodeOutputValidationError` (with `errors[]`), `NodeIOError` (with `path`), `NodeConfigurationError`, `WorkflowExecutionError` (with `nodeId`), `WorkflowValidationError` (with `errors[]`)
- [x] Create `src/exceptions.ts` — `RegistrationError` (with `statusCode`, `body` — separate from hierarchy, mirrors Python placement in `registry.py`)
- [x] Create `src/exceptions.ts` — `ERROR_CODE_TO_HTTP_STATUS` mapping matching Python exactly: `EXECUTION_ERROR→500`, `TIMEOUT→408`, `VALIDATION_ERROR→422`, `OUTPUT_VALIDATION_ERROR→422`, `IO_ERROR→500`, `CONFIGURATION_ERROR→500`, `WORKFLOW_EXECUTION_ERROR→500`, `WORKFLOW_VALIDATION_ERROR→422`
- [x] Create `src/exceptions.ts` — `getHttpStatusForError()` function
- [x] Create `src/request.ts` — Zod schema for `NodeExecutionRequest` with fields: `runId`, `nodeId`, `inputs` (default `{}`), `callbackUrl` (optional), `outputUploadUrl` (`Record<string, string> | null`, optional)
- [x] Create `src/response.ts` — Zod schemas for `NodeExecutionResponse` (with `success()` and `failure()` static factory methods), `HealthResponse`
- [x] Write unit tests for schema validation (valid/invalid cases, file field constraints, slug pattern, semver pattern)
- [x] Write unit tests for error hierarchy, `toDict()` serialization, and HTTP status mapping

**Acceptance Criteria:**
- `NodeDefinitionSchema.parse()` validates name (slug regex), version (semver regex), file field constraints (rejects `format: "binary"`, enforces `type: "string"` for file fields)
- Manual `id` in schema triggers console.warn and is stripped
- Each exception has correct `errorCode` and `toDict()` serialization with all subclass-specific fields
- `getHttpStatusForError()` maps every error code to correct HTTP status
- `NodeExecutionResponse.success()` creates `status: "pass"`; `.failure()` creates `status: "fail"`
- Unit tests pass for all schema validation cases

---

## Phase 2: Logging, Context, BaseNode + Execution Pipeline + Middleware

- [x] Create `src/logging.ts` — `StructuredJsonFormatter` (emits one JSON object per line: `timestamp`, `level`, `logger`, `message`, plus `run_id`/`node_id` when present)
- [x] Create `src/logging.ts` — `HumanReadableFormatter` (plain text for local dev)
- [x] Create `src/logging.ts` — `configureLogging(opts?)` reads `CANVASTEKK_LOG_LEVEL` (default `INFO`) and `CANVASTEKK_LOG_FORMAT` (`"json"` default, `"text"` for dev); configures SDK and node loggers
- [x] Create `src/logging.ts` — `getNodeLogger(nodeId, runId?)` returns logger named `node.<nodeId>`
- [x] Create `src/context.ts` — `ExecutionContext` with `outputDir`, `downloadsDir` (lazy-created on first access), `outputPath(filename)`, `reportProgress(progress, message?)`, `recordTokenUsage({promptTokens, completionTokens, totalTokens})`, `metadata` (mutable dict), `tokenUsage` (getter returns copy)
- [x] Create `src/context.ts` — `CANVASTEKK_OUTPUT_DIR` env var fallback for output directory resolution (mirrors `context.py:49-53`)
- [x] Create `src/context.ts` — `runId` and `nodeId` derived from request or output dir path
- [x] Create `src/middleware.ts` — `NodeMiddleware` interface: `onBeforeExecute(inputs, context) → inputs`, `onAfterExecute(inputs, outputs, context, durationMs)`, `onError(inputs, error, context, durationMs)`
- [x] Create `src/middleware.ts` — `LoggingMiddleware`: logs execution start, completion with duration, and errors with correlation IDs
- [x] Create `src/middleware.ts` — `TimingMiddleware`: records `{runId, nodeId, durationMs, status}` in `timings` array
- [x] Create `src/middleware.ts` — `SDKVersionMiddleware` (Express middleware, sets `X-SDK-Version` header)
- [x] Create `src/observability.ts` — `ExecutionMetric` interface with `toDict()` method
- [x] Create `src/observability.ts` — `MetricsCollector` with `record(metric)`, `getSummary(lastN?)`, `clear()`; `maxRecords` constructor param (default 10000) with eviction; no lock needed (single-threaded)
- [x] Create `src/base-node.ts` — `BaseNode` abstract class:
  - Constructor validates `definition` via `NodeDefinitionSchema.parse()`, replacing Python's `__init_subclass__`
  - `addMiddleware(middleware)` / `setMetricsCollector(collector)` fluent methods returning `this`
  - `abstract execute(inputs, context) → Record<string, unknown>` — authors can return Promise or plain value
  - `run(request) → NodeExecutionResponse` — full pipeline with timing
  - `healthCheck() → Record<string, boolean>` — overridable, default `{}`
  - `hook(payload) → Record<string, unknown> | null` — overridable webhook handler, default `null`
  - `onStartup() → Promise<void>` — overridable lifecycle hook (model loading, connections)
  - `onShutdown() → Promise<void>` — overridable lifecycle hook (cleanup, flush)
  - `createApp(opts?)` — convenience method delegating to `createNodeApp()`
- [x] Create `src/base-node.ts` — Full `run()` pipeline: validate inputs (Ajv Draft 7) → create context → download file inputs (native fetch streaming) → middleware before → execute → validate outputs (Ajv Draft 7) → middleware after → metrics → response
- [x] Implement JSON Schema Draft 7 validation via Ajv configured as `new Ajv({ strict: false })` — error output format must match Python: `[{path: [...], message: string, validator: string}]`
- [x] Implement file download using native `fetch` with streaming; track downloaded files for atomic cleanup on error (mirrors Python's `downloaded: list[Path]` + `except: unlink` pattern)
- [x] Implement `_extractFilename(url, contentDisposition?)` and `_sanitizeFilename()` for download naming
- [x] Token usage fallback: `context.tokenUsage.totalTokens ?? definition.tokenCost`
- [x] Write unit tests for `ExecutionContext` (output dir, downloads dir lazy creation, CANVASTEKK_OUTPUT_DIR)
- [x] Write unit tests for `configureLogging()`, `getNodeLogger()`, structured JSON formatter
- [x] Write unit tests for middleware hooks (before/after/error)
- [x] Write unit tests for `MetricsCollector` (record, getSummary, clear, maxRecords eviction)
- [x] Write integration tests for `BaseNode.run()` full pipeline (success, validation error, IO error, timeout)

**Acceptance Criteria:**
- `BaseNode` constructor validates `definition` — throws on invalid schema
- `run()` pipeline: validate → download → execute → validate output → response
- `configureLogging()` reads env vars, configures JSON/text formatters
- `getNodeLogger()` returns logger named `node.<nodeId>`
- Middleware `onBeforeExecute` can modify inputs; `onAfterExecute` and `onError` fire correctly
- `MetricsCollector.getSummary()` returns correct statistics; `clear()` works; eviction works at capacity
- `addMiddleware()` / `setMetricsCollector()` return `this` for chaining
- `createApp()` convenience method produces same result as `createNodeApp(node)`
- Ajv validation errors match Python's error format: `[{path, message, validator}]`
- File download cleanup: partially downloaded files are deleted on error
- Lifecycle hooks (`onStartup`/`onShutdown`) exist and are overridable

---

## Phase 3: Express HTTP Server + Auth + Uploads

- [ ] Create `src/app.ts` — `createNodeApp(node, opts)` Express factory:
  - `opts.dependencies` → Express middleware applied to all node routes
  - `opts.extraRoutes` → additional Express routers mounted on app
  - Startup: calls `configureLogging()` then `node.onStartup()`
  - Shutdown: calls `node.onShutdown()` on server close
  - `X-SDK-Version` header on all responses via Express middleware
- [ ] Implement `POST /execute` — parse JSON body, create `NodeExecutionRequest`, enforce timeout via `AbortSignal.timeout()`, run `node.run()` in worker thread (see I4), upload file outputs if `outputUploadUrl` provided
- [ ] Implement `GET /health` — calls `node.healthCheck()`, returns `HealthResponse` with status logic (healthy/unhealthy/degraded based on checks)
- [ ] Implement `GET /manifest` — returns `NodeDefinition` dict + `sdkVersion` + `mode` (dev/uat/production from `CANVASTEKK_NODE_ENV`)
- [ ] Implement `GET /definition` — 301 redirect to `/manifest` (deprecated)
- [ ] Implement `POST /hook` — calls `node.hook(body)`, returns 501 if null
- [ ] Implement `GET /metrics` — returns `node._metricsCollector.getSummary()`
- [ ] Implement `GET /live` — returns `{status: "alive"}`
- [ ] Implement `GET /ready` — calls `node.healthCheck()`, returns 503 if any check fails
- [ ] Implement error handler middleware: maps `NodeExecutionError` subclasses to HTTP status codes via `getHttpStatusForError()`
- [ ] Create `src/auth.ts` — `NodeAuth` static factory class:
  - `apiKey(keyEnvVar?)` — validates `X-API-Key` header with `crypto.timingSafeEqual`
  - `jwt(secretEnvVar?, algorithm?, audience?)` — validates `Authorization: Bearer` with `jsonwebtoken` (optional peer dep)
  - `keycloak(serverUrl?, realm?, audience?)` — RS256 JWKS validation (optional peer dep)
  - All backends: dev mode bypass via `CANVASTEKK_DEV_MODE` env var
- [ ] Create `src/uploads.ts` — `OutputUploader` interface (protocol for custom upload strategies)
- [ ] Create `src/uploads.ts` — `S3PresignedUploader` implementing `OutputUploader`: `uploadFile(filePath, presignedUrl)` and `uploadOutputs(response, uploadUrls, fileOutputFields)` using native `fetch` PUT
- [ ] Create `src/uploads.ts` — Individual upload failures logged but NOT raised (mirrors Python's graceful degradation in `uploads.py:93-98`)
- [ ] Create `src/uploads.ts` — `getDefaultUploader()` singleton accessor
- [ ] Create `src/router.ts` — `createMultiNodeApp(nodes, opts)` mounting multiple nodes under URL prefixes; includes root `GET /health` endpoint returning `{status: "healthy", nodes: [...]}` (mirrors `router.py:81-83`)
- [ ] Write integration tests for all 8 endpoints using `supertest`
- [ ] Write tests for auth middleware (API key, JWT, dev mode bypass, missing env var)
- [ ] Write tests for error handler mapping (each error type → correct HTTP status)
- [ ] Write tests for lifecycle hooks (onStartup fires before listen, onShutdown fires on close)

**Acceptance Criteria:**
- All 8 endpoints respond correctly with same JSON shapes as Python SDK
- Timeout enforcement via `AbortSignal.timeout()` produces `NodeTimeoutError` → 408
- `POST /execute` handles: valid request, invalid JSON, validation errors, execution errors, file output upload
- `GET /manifest` includes `sdkVersion` and `mode` (dev/uat/production)
- `GET /ready` returns 503 when health checks fail
- Auth middleware: API key uses `crypto.timingSafeEqual`, dev mode bypasses all auth
- Lifecycle hooks: `onStartup()` fires at app start, `onShutdown()` fires at app close
- `X-SDK-Version` header present on all responses
- `createMultiNodeApp` root `/health` endpoint returns node list
- Individual S3 upload failures are logged but don't fail the execution

---

## Phase 4: Data Contracts + Registry

- [ ] Create `src/contracts/base.ts` — `CONTRACT_VERSION = "1.0.0"` constant
- [ ] Create `src/contracts/base.ts` — `BaseContract` base class/interface with `contractVersion`, `sourceNode`, `sourceFile`, `saveJson(path)`, `loadJson(path)` (static, returns typed instance)
- [ ] Create `src/contracts/point3d.ts` — `Point3D` with `toList()`, `fromList(coords)` static; `BoundingBox3D` with `center` and `size` getters
- [ ] Create `src/contracts/instance.ts` — `Instance` with `instanceId`, `classId`, `className`, `confidence`, `pointIndices`, `centroid`, `boundingBox`, `metadata`; `numPoints` getter
- [ ] Create `src/contracts/instance.ts` — `InstanceSet` extends `BaseContract` with `instances`, `classNames`, `pointCount`, `semanticLabels`, `instanceLabels`; methods: `getInstancesByClass(name)`, `getInstancesByClassId(id)`
- [ ] Create `src/contracts/measurement.ts` — `Measurement` with `name`, `value`, `unit` (default `"mm"`), `method`, `confidence`, `points`, `metadata`
- [ ] Create `src/contracts/measurement.ts` — `MeasurementSet` extends `BaseContract` with `measurements`; methods: `getMeasurement(name)`, `getValue(name, default?)`
- [ ] Create `src/contracts/plane.ts` — `Plane` with `point`, `normal` (both `Point3D`), `label` (optional)
- [ ] Create `src/contracts/plane.ts` — `PlaneSet` extends `BaseContract` with `planes`; method: `getPlaneByLabel(label)`
- [ ] Create `src/contracts/index.ts` — barrel export of all contracts
- [ ] Export `STANDARD_CLASSES` and `STANDARD_CLASS_NAMES` constants (BCA inspection class IDs)
- [ ] Create `src/registry.ts` — `InvokeType` type (`"http" | "lambda" | "sagemaker" | "in-process"`)
- [ ] Create `src/registry.ts` — `RegisterNodeResult` with `node`, `action`, `revisionId`, `previousVersion`, `changes`; dict-like access: `[key]`, `get(key, default?)`, `has(key)` (mirrors Python's `__getitem__`/`__contains__`)
- [ ] Create `src/registry.ts` — `buildRegistryPayload(definition, opts)` with field mapping: `title→label`, `defaultRetry→retry`, omit `id`, includes `invokeConfig` if provided (DA-1016 exact match)
- [ ] Create `src/registry.ts` — `_extractNodeData(payload)` helper for registry response parsing (handles `node`, `data`, and flat response formats)
- [ ] Create `src/registry.ts` — `registerNode(node, registryUrl, opts)` with `apiKey`/`serviceToken` auth (X-API-Key or X-Service-Token header), `invokeConfig` support, `AbortSignal.timeout()`
- [ ] Create `src/registry.ts` — `exportDefinition(definition, outputPath, opts)` writes registry-compatible JSON file
- [ ] Write unit tests for all contract Zod schemas (valid/invalid fixtures)
- [ ] Write unit tests for `BaseContract.saveJson()`/`loadJson()` round-trip
- [ ] Write unit tests for contract helper methods (`getInstancesByClass`, `getInstancesByClassId`, `getMeasurement`, `getValue`, `getPlaneByLabel`, `Point3D.toList`/`fromList`, `BoundingBox3D.center`/`size`, `Instance.numPoints`)
- [ ] Write unit tests for `buildRegistryPayload()` field mapping (title→label, omit id, retry shape)
- [ ] Write unit tests for `RegisterNodeResult` dict-like access
- [ ] Write integration tests for `registerNode()` with correct auth headers

**Acceptance Criteria:**
- All contract schemas validate with Zod (including edge cases)
- `BaseContract.saveJson()`/`loadJson()` round-trip preserves all fields
- `Point3D.toList()` returns `[x, y, z]`; `fromList()` creates `Point3D`
- `BoundingBox3D.center` and `size` computed correctly
- `Instance.numPoints` returns `pointIndices.length`
- `InstanceSet.getInstancesByClass("vent")` filters correctly
- `MeasurementSet.getValue("height", 0)` returns value or default
- `buildRegistryPayload()` maps `title→label`, `defaultRetry→retry`, omits `id`
- `RegisterNodeResult` supports `result["name"]`, `result.get("name")`, `"name" in result`
- `registerNode()` sends correct auth headers (`X-API-Key` or `X-Service-Token`)
- `exportDefinition()` produces engine-compatible JSON
- `STANDARD_CLASSES` / `STANDARD_CLASS_NAMES` exported

---

## Phase 5: Workflow Builder + Runner

- [ ] Create `src/workflow/models.ts` — `EdgeType` enum (`default`, `success`, `failure`, `conditional`), `ResolutionStrategy` enum (`auto`, `flat`, `dot_path`)
- [ ] Create `src/workflow/models.ts` — `WorkflowEdge` interface with `id` (auto-UUID), `fromNode`, `toNode`, `fromOutput`, `toInput`, `edgeType`, `resolutionStrategy`, `condition`
- [ ] Create `src/workflow/models.ts` — `WorkflowNode` interface with `id`, `slug`, `version`, `name`, `x`, `y`, `inputs`
- [ ] Create `src/workflow/models.ts` — `WorkflowSpec` interface with `name`, `nodes`, `edges`, `metadata`
- [ ] Create `src/workflow/builder.ts` — `WorkflowBuilder` fluent API:
  - `addStart(nodeId, {outputs, configSchema})` — converts `outputs: string[]` to `configSchema: {type: "object", properties: {...}}` matching Python's builder behavior; only one START allowed
  - `addEnd(nodeId)` — multiple END nodes allowed
  - `addNode(nodeId, {slug, name, inputs, version})` — rejects reserved slugs (`__start__`, `__end__`)
  - `connect(fromNode, toNode, {fromOutput, toInput, edgeType, resolutionStrategy, condition})` — validates node IDs exist
  - `build({validate})` — builds spec and optionally validates graph
- [ ] Create `src/workflow/executor.ts` — `NodeExecutor` abstract class: `execute(slug, inputs, context) → Promise<Record<string, unknown>>`, `has(slug) → boolean`
- [ ] Create `src/workflow/executor.ts` — `InProcessExecutor`: `register(slug, node)` fluent; calls `node.execute()` directly
- [ ] Create `src/workflow/executor.ts` — `HttpExecutor`: `registerUrl(slug, url)` fluent; POSTs to `/execute` with `{runId, nodeId, inputs}` payload; handles pass/fail response
- [ ] Create `src/workflow/level.ts` — `computeLevels(spec)` BFS topological sort (Kahn's algorithm), exported as standalone function
- [ ] Create `src/workflow/resolver.ts` — `resolveInputs(nodeId, spec, nodeOutputs)` resolves inputs from static node params + incoming edge outputs; supports flat, dot-path, and AUTO resolution strategies; exported as standalone function
- [ ] Create `src/workflow/validation.ts` — `ValidationResult` with `isValid`, `errors[]`, `orphans[]`, `deadEnds[]`
- [ ] Create `src/workflow/validation.ts` — `validate(spec)` checks: node ID uniqueness, edge reference validity, START/END constraints (exactly 1 start, ≥1 end, degree rules), cycle detection (Kahn's), forward BFS connectivity (orphans), reverse BFS connectivity (dead-ends)
- [ ] Create `src/workflow/control-flow.ts` — `CONTROL_FLOW_HANDLERS` map: `__start__` (identity passthrough), `__end__` (identity passthrough)
- [ ] Create `src/workflow/runner.ts` — `ErrorPolicy` enum (`fail_fast`, `continue`)
- [ ] Create `src/workflow/runner.ts` — `NodeResult` interface with `nodeId`, `slug`, `status`, `outputs`, `durationMs`, `error`, `skippedReason`
- [ ] Create `src/workflow/runner.ts` — `WorkflowRunResult` interface with `status`, `finalOutputs`, `nodeResults`, `durationMs`, `outputDir`
- [ ] Create `src/workflow/runner.ts` — `WorkflowRunner` with constructor params: `executor`, `errorPolicy`, `outputDir`, `cleanup`
  - `run(spec, inputs?)` — async execution
  - Shared `outputDir` created if not provided; auto-cleaned if `cleanup=true` (even on exceptions)
  - Initialize result variables before try block (DA-1102 C1)
  - Control flow nodes executed sequentially before user nodes within each level
  - User nodes executed in parallel via `Promise.allSettled()` within each level
  - Upstream failure detection marks downstream nodes as `skipped`
  - Executor registration check before dispatching tasks
  - Document: parallel nodes writing same filename = undefined behavior
  - Document: `outputDir` only works with `InProcessExecutor`; `HttpExecutor` doesn't share local filesystem
- [ ] Write unit tests for `WorkflowBuilder` (valid specs, validation errors, duplicate IDs, reserved slugs, START uniqueness, configSchema generation from outputs)
- [ ] Write unit tests for `computeLevels()` topological ordering
- [ ] Write unit tests for `resolveInputs()` (flat, dot-path, AUTO strategies, missing key errors)
- [ ] Write unit tests for graph validation (cycles, missing nodes, connectivity, orphans, dead-ends)
- [ ] Write integration tests for `WorkflowRunner` (sequential, parallel, error policies, outputDir, cleanup, upstream failure skip)

**Acceptance Criteria:**
- `WorkflowBuilder.addStart()` converts `outputs: string[]` to `configSchema` correctly
- `WorkflowBuilder` produces valid `WorkflowSpec` with all model fields (`x`, `y`, `metadata`, edge `id`)
- `computeLevels()` returns correct BFS topological levels, exported standalone
- `resolveInputs()` resolves flat and dot-path inputs, exported standalone
- `ValidationResult` includes `orphans` and `deadEnds` arrays
- `InProcessExecutor` runs registered `BaseNode` instances directly
- `HttpExecutor` POSTs to registered URLs, handles success/failure responses
- `WorkflowRunner` executes levels in order, parallel within levels
- Shared `outputDir` enables file-passing between nodes
- `fail_fast` stops on first failure; `continue` runs all levels
- Auto-created temp dirs are cleaned up (even on exceptions)
- User-supplied `outputDir` is never cleaned up

---

## Phase 6: Testing Utilities, CLI, Packaging, CI/CD

- [ ] Create `src/testing/index.ts` — `LocalFileServer` using Node `http.createServer`:
  - Constructor: `directory`, `host` (default `127.0.0.1`), `port` (default `0`)
  - Properties: `baseUrl` (throws if not started), `urlFor(filename)`
  - Methods: `start()` (idempotent), `stop()`
  - `Symbol.dispose` and `Symbol.asyncDispose` for `using`/`await using`
  - Path traversal protection (reject `../` patterns)
- [ ] Create `src/testing/index.ts` — `serveFiles(directory, host?, port?)` convenience wrapper
- [ ] Create `src/cli.ts` — CLI entry point:
  - `canvastekk-sdk validate <file:export> [--json]` — load definition, inspect file fields, report warnings for missing `x-accept`/`x-maxSizeBytes`
  - `canvastekk-sdk init [--agents-md] [--force]` — scaffold AI agent skills
  - `canvastekk-sdk --version` — print SDK version
- [ ] Create `src/index.ts` — Barrel export matching Python's `__all__` (see Export Checklist below)
- [ ] Create `package.json` — see Package Configuration section below
- [ ] Create `tsconfig.json` — `strict: true`, `module: "nodenext"`, `target: "ES2025"`, `declaration: true`
- [ ] Create `tsup.config.ts` — `entry: ["src/index.ts", "src/cli.ts"]`, ESM + CJS dual output + `.d.ts`, `target: "node24"`
- [ ] Create `vitest.config.ts` — Vitest configuration
- [ ] Verify `npm run build` produces working ESM + CJS + `.d.ts` in `dist/`
- [ ] Verify `npm run test` passes full test suite
- [ ] Create `.github/workflows/ci-typescript.yml` — Node 24, `npm ci`, lint, typecheck, test (triggered on `typescript/**` paths)
- [ ] Update `.github/workflows/release.yml` — Add steps after Python build:
  - Setup Node.js 24 (conditional on `typescript/package.json` existing)
  - `npm ci && npm run build && npm publish` (to GitHub Packages `@nus-cee`)
  - `npm pack && gh release upload` (attach tarball to GitHub Release)
  - Stage `typescript/package-lock.json` in git commit
- [ ] Create `examples/echo-node-typescript/` — Canonical TypeScript reference implementation with `handler.ts`, `package.json`, `Dockerfile` (Node 24 slim), `tsconfig.json`
- [ ] Final feature parity audit: every Python export has TypeScript equivalent (use Export Checklist)

**Acceptance Criteria:**
- `npm run build` produces working ESM + CJS + `.d.ts` in `dist/`
- `npm run test` passes full test suite
- `LocalFileServer` serves files, rejects path traversal, supports `Symbol.dispose`
- `serveFiles()` convenience wrapper works
- CLI `validate` reports file field warnings; `--json` outputs structured report
- CLI `init` scaffolds skills with `--agents-md` and `--force` flags
- `ci-typescript.yml` runs on `typescript/**` path changes
- `release.yml` builds, publishes, and uploads TypeScript SDK
- Echo node example builds and runs correctly

---

## Package Configuration

```json
{
  "name": "canvastekk-workflow-sdk",
  "version": "0.13.0",
  "type": "module",
  "main": "./dist/index.cjs",
  "module": "./dist/index.js",
  "types": "./dist/index.d.ts",
  "exports": {
    ".": {
      "import": "./dist/index.js",
      "require": "./dist/index.cjs",
      "types": "./dist/index.d.ts"
    }
  },
  "bin": { "canvastekk-sdk": "./dist/cli.js" },
  "engines": { "node": ">=24.0.0" },
  "files": ["dist"],
  "scripts": {
    "build": "tsup",
    "test": "vitest run",
    "test:watch": "vitest",
    "lint": "eslint src/ tests/",
    "typecheck": "tsc --noEmit",
    "prepublishOnly": "npm run build"
  },
  "dependencies": {
    "express": "^4.21",
    "zod": "^3.25",
    "ajv": "^8"
  },
  "optionalDependencies": {
    "jsonwebtoken": "^9"
  },
  "devDependencies": {
    "typescript": "^5.8",
    "tsup": "^8",
    "vitest": "^3",
    "@types/express": "^5",
    "@types/node": "^24",
    "@types/jsonwebtoken": "^9",
    "supertest": "^7",
    "@types/supertest": "^6",
    "eslint": "^9",
    "typescript-eslint": "^8"
  },
  "publishConfig": { "registry": "https://npm.pkg.github.com/@nus-cee" },
  "license": "Apache-2.0"
}
```

---

## Export Checklist (Feature Parity)

Every export from `python/canvastekk_workflow_sdk/__init__.py` must have a TypeScript equivalent:

| Python Export | TypeScript Export | Phase |
|---|---|---|
| `BaseNode` | `BaseNode` | 2 |
| `NodeDefinition` | `NodeDefinition` (Zod inferred type) | 1 |
| `ExecutionContext` | `ExecutionContext` | 2 |
| `RetryConfig` | `RetryConfig` (Zod inferred type) | 1 |
| `NodeStyles` | `NodeStyles` (Zod inferred type) | 1 |
| `ColorPreset` | `ColorPreset` (Zod union type) | 1 |
| `NodeExecutionRequest` | `NodeExecutionRequest` | 1 |
| `NodeExecutionResponse` | `NodeExecutionResponse` | 1 |
| `HealthResponse` | `HealthResponse` | 1 |
| `NodeExecutionError` | `NodeExecutionError` | 1 |
| `NodeTimeoutError` | `NodeTimeoutError` | 1 |
| `NodeValidationError` | `NodeValidationError` | 1 |
| `NodeOutputValidationError` | `NodeOutputValidationError` | 1 |
| `NodeIOError` | `NodeIOError` | 1 |
| `NodeConfigurationError` | `NodeConfigurationError` | 1 |
| `WorkflowExecutionError` | `WorkflowExecutionError` | 1 |
| `WorkflowValidationError` | `WorkflowValidationError` | 1 |
| `RegistrationError` | `RegistrationError` | 1 |
| `NodeMiddleware` | `NodeMiddleware` (interface) | 2 |
| `LoggingMiddleware` | `LoggingMiddleware` | 2 |
| `TimingMiddleware` | `TimingMiddleware` | 2 |
| `SDKVersionMiddleware` | `SDKVersionMiddleware` | 2 |
| `MetricsCollector` | `MetricsCollector` | 2 |
| `ExecutionMetric` | `ExecutionMetric` | 2 |
| `StructuredJsonFormatter` | `StructuredJsonFormatter` | 2 |
| `configure_logging` | `configureLogging` | 2 |
| `get_node_logger` | `getNodeLogger` | 2 |
| `OutputUploader` | `OutputUploader` (interface) | 3 |
| `S3PresignedUploader` | `S3PresignedUploader` | 3 |
| `get_default_uploader` | `getDefaultUploader` | 3 |
| `NodeAuth` | `NodeAuth` | 3 |
| `create_node_app` | `createNodeApp` | 3 |
| `create_multi_node_app` | `createMultiNodeApp` | 3 |
| `register_node` | `registerNode` | 4 |
| `build_registry_payload` | `buildRegistryPayload` | 4 |
| `export_definition` | `exportDefinition` | 4 |
| `RegisterNodeResult` | `RegisterNodeResult` | 4 |
| `BaseContract` | `BaseContract` | 4 |
| `Point3D` | `Point3D` | 4 |
| `BoundingBox3D` | `BoundingBox3D` | 4 |
| `Instance` | `Instance` | 4 |
| `InstanceSet` | `InstanceSet` | 4 |
| `Measurement` | `Measurement` | 4 |
| `MeasurementSet` | `MeasurementSet` | 4 |
| `Plane` | `Plane` | 4 |
| `PlaneSet` | `PlaneSet` | 4 |
| `STANDARD_CLASSES` | `STANDARD_CLASSES` | 4 |
| `STANDARD_CLASS_NAMES` | `STANDARD_CLASS_NAMES` | 4 |
| `EdgeType` | `EdgeType` | 5 |
| `ResolutionStrategy` | `ResolutionStrategy` | 5 |
| `WorkflowBuilder` | `WorkflowBuilder` | 5 |
| `WorkflowRunner` | `WorkflowRunner` | 5 |
| `WorkflowSpec` | `WorkflowSpec` | 5 |
| `WorkflowNode` | `WorkflowNode` | 5 |
| `WorkflowEdge` | `WorkflowEdge` | 5 |
| `NodeExecutor` | `NodeExecutor` | 5 |
| `InProcessExecutor` | `InProcessExecutor` | 5 |
| `HttpExecutor` | `HttpExecutor` | 5 |
| `NodeResult` | `NodeResult` | 5 |
| `WorkflowRunResult` | `WorkflowRunResult` | 5 |
| `ValidationResult` | `ValidationResult` | 5 |
| `validate` (workflow) | `validate` | 5 |
| `LocalFileServer` | `LocalFileServer` | 6 |
| `serve_files` | `serveFiles` | 6 |
| `__version__` | `VERSION` | 1 |

---

## Key Constraints

- **Node `id` is auto-derived** from `name-v{version}` — never manual. Warn if user provides `id`.
- **File fields must use `format: "file"` + `type: "string"`** — reject `format: "binary"` from day one (DA-894).
- **`registerNode()` payload** must match engine `RegisterNodeRequest` exactly: `title→label`, `defaultRetry→retry`, omit `id` (DA-1016).
- **Dev mode auth bypass** (`CANVASTEKK_DEV_MODE`) included in all auth backends.
- **Initialize result variables before try blocks** — avoid undefined references (DA-1102 C1).
- **Feature parity guarantee** — all Python exports in checklist above must have TypeScript equivalents.
- **API shapes** must be byte-identical to Python SDK output.
- **Ajv configured for Draft 7** with `strict: false` — error format matches Python's `[{path, message, validator}]`.
- **Express 4** (stable) — not Express 5 (still RC).
- **Worker threads** for CPU-heavy `execute()` to avoid blocking event loop.
- **Token usage fallback**: `context.tokenUsage.totalTokens ?? definition.tokenCost`.
- **Individual S3 upload failures logged but not raised** — graceful degradation.
- **`MetricsCollector` no locks** — Node.js is single-threaded; document as deliberate simplification.
