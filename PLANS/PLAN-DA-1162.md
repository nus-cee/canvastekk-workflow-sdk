# PLAN-DA-1162: Improve Docstring/JSDoc Coverage Across Python and TypeScript SDKs

> **JIRA Ticket:** [DA-1162](https://betekk.atlassian.net/browse/DA-1162)
> **Branch:** `DA-1162`
> **Status:** Planning
> **Created:** 2026-05-29
> **Updated:** 2026-05-29

## Overview

A comprehensive docstring review found the Python SDK at ~95% coverage and the TypeScript SDK at ~75%. This plan closes all verified gaps to bring both SDKs to full docstring/JSDoc coverage with cross-language parity. Phases 1-4 are **independent and parallelizable**.

**Docstring conventions:**
- **Python**: PEP 257 + Google-style (`Args:`, `Returns:`, `Raises:`)
- **TypeScript**: JSDoc with `@param`, `@returns`, `@throws`

**Target:** 100% docstring/JSDoc coverage across both SDKs.

---

## Verified Complete (No Changes Needed)

These modules already have full coverage — verified by code review:

| File | Status |
|------|--------|
| `typescript/src/exceptions.ts` | 100% — all classes documented |
| `typescript/src/middleware.ts` | 100% — all interfaces/classes documented |
| `typescript/src/observability.ts` | 100% — all types/functions documented |
| `typescript/src/uploads.ts` | 100% — all interfaces/classes documented |
| `typescript/src/version.ts` | 100% — constant documented |
| `typescript/src/index.ts` | N/A — barrel exports |
| `typescript/src/workflow/executor.ts` (partial) | `NodeExecutor`, `InProcessExecutor`/`HttpExecutor` classes + `register`/`registerUrl` methods documented |
| `typescript/src/workflow/level.ts` | 100% — `computeLevels` fully documented |
| `python/canvastekk_workflow_sdk/definition.py` | 100% |
| `python/canvastekk_workflow_sdk/base.py` | 100% |
| `python/canvastekk_workflow_sdk/context.py` | 100% |
| `python/canvastekk_workflow_sdk/request.py` | 100% |
| `python/canvastekk_workflow_sdk/response.py` | 100% |
| `python/canvastekk_workflow_sdk/logging.py` | 100% |
| `python/canvastekk_workflow_sdk/middleware.py` | 100% |
| `python/canvastekk_workflow_sdk/observability.py` | 100% |
| `python/canvastekk_workflow_sdk/exceptions.py` | 100% |
| `python/canvastekk_workflow_sdk/auth.py` | 100% |
| `python/canvastekk_workflow_sdk/uploads.py` | 100% |
| `python/canvastekk_workflow_sdk/registry.py` | 100% |
| `python/canvastekk_workflow_sdk/app.py` | 100% |
| `python/canvastekk_workflow_sdk/contracts.py` | 100% |
| `python/canvastekk_workflow_sdk/workflow/models.py` | 100% |
| `python/canvastekk_workflow_sdk/workflow/builder.py` | 100% |
| `python/canvastekk_workflow_sdk/workflow/runner.py` | 100% |
| `python/canvastekk_workflow_sdk/workflow/executor.py` | 100% |
| `python/canvastekk_workflow_sdk/workflow/resolver.py` | 100% |
| `python/canvastekk_workflow_sdk/workflow/level.py` | 100% |
| `python/canvastekk_workflow_sdk/workflow/_control_flow.py` | 100% |

---

## Phase 1: TypeScript High Priority — Public API Docstrings

**Parallelizable with Phases 2-4.**

### 1.1 Class-level JSDoc on public classes

- [ ] `typescript/src/base-node.ts` — `BaseNode`: Add class-level JSDoc matching Python's 24-line docstring (abstract base class, lifecycle, `execute()` contract, `definition` attribute, usage example)
- [ ] `typescript/src/context.ts` — `ExecutionContext`: Add class-level JSDoc matching Python's 11-line docstring (execution context, properties: `runId`, `nodeId`, `downloadsDir`, `outputPath()`, `reportProgress()`)

### 1.2 Public helper functions in `definition.ts`

- [ ] `typescript/src/definition.ts` — `getFileInputFields(def)`: JSDoc with `@param`, `@returns`, `@throws`
- [ ] `typescript/src/definition.ts` — `getFileOutputFields(def)`: JSDoc with `@param`, `@returns`
- [ ] `typescript/src/definition.ts` — `validateFileInput(field, fileSize?)`: JSDoc with `@param`, `@returns`, `@throws`

### 1.3 Wire-format types and response factories

- [ ] `typescript/src/request.ts` — `NodeExecutionRequest`: Expand JSDoc with field descriptions (`run_id`, `node_id`, `inputs`, `callback_url`, `output_upload_url`)
- [ ] `typescript/src/response.ts` — `NodeExecutionResponse`: Expand JSDoc with field descriptions (`execution_id`, `status`, `outputs`, `duration_ms`, `token_usage`)
- [ ] `typescript/src/response.ts` — `createSuccessResponse(outputs)`: Add JSDoc with `@param`, `@returns`
- [ ] `typescript/src/response.ts` — `createFailureResponse(error)`: Add JSDoc with `@param`, `@returns`

### 1.4 Route handlers in `app.ts`

- [ ] `typescript/src/app.ts` — `POST /execute` handler: JSDoc with request/response format, error handling
- [ ] `typescript/src/app.ts` — `GET /health` handler: JSDoc with `HealthResponse` shape
- [ ] `typescript/src/app.ts` — `GET /manifest` handler: JSDoc with `NodeDefinition` response
- [ ] `typescript/src/app.ts` — `POST /hook` handler: JSDoc with lifecycle hook handling
- [ ] `typescript/src/app.ts` — `GET /metrics` handler: JSDoc with metrics output format
- [ ] `typescript/src/app.ts` — `GET /live` handler: JSDoc with liveness probe behavior
- [ ] `typescript/src/app.ts` — `GET /ready` handler: JSDoc with readiness probe behavior
- [ ] `typescript/src/app.ts` — `GET /` root handler: JSDoc with overview response

**Acceptance Criteria:**
- All public classes have class-level JSDoc matching Python depth
- All public functions have JSDoc with `@param`, `@returns`, `@throws` where applicable
- All route handlers documented with HTTP method, path, and response format

---

## Phase 2: TypeScript Medium Priority — Internal Helpers

**Parallelizable with Phases 1, 3-4.**

### 2.1 Private helpers in `base-node.ts`

- [ ] `sanitizeFilename(filename)`: JSDoc — security purpose, path traversal prevention, `@param`, `@returns`
- [ ] `extractFilename(url)`: JSDoc — Content-Disposition header parsing, fallback to URL path, `@param`, `@returns`
- [ ] `compileSchema(definition)`: JSDoc — Ajv compilation with caching, `@param`, `@returns`
- [ ] `formatAjvErrors(errors)`: JSDoc — error transformation for readable output, `@param`, `@returns`

### 2.2 Private helpers in `logging.ts`

- [ ] `getEnvLogLevel()`: JSDoc — env var parsing, default fallback, `@returns`
- [ ] `getEnvLogFormat()`: JSDoc — env var parsing, default fallback, `@returns`
- [ ] `writeLog(level, logger, message, meta)`: JSDoc — level filtering, JSON/text output, `@param`, `@returns`
- [ ] `getOrCreateConfig(name)`: JSDoc — logger hierarchy, lazy init, `@param`, `@returns`

### 2.3 Private helpers in `auth.ts`

- [ ] `isDevMode()`: JSDoc — dev mode bypass logic, security warning, `@returns`
- [ ] `unauthorized(res, message)`: JSDoc — HTTP 401 response generation, `@param`

### 2.4 Workflow builder private method

- [ ] `typescript/src/workflow/builder.ts` — `checkDuplicate(nodeId)`: JSDoc with `@param`, `@throws`

### 2.5 Workflow model types — expand weak JSDoc

- [ ] `typescript/src/workflow/models.ts` — `EdgeType`: Expand from one-liner to describe edge types and their meanings
- [ ] `typescript/src/workflow/models.ts` — `WorkflowEdge`: Expand with property descriptions
- [ ] `typescript/src/workflow/models.ts` — `WorkflowNode`: Expand with property descriptions
- [ ] `typescript/src/workflow/models.ts` — `WorkflowSpec`: Expand with property descriptions

**Acceptance Criteria:**
- All private helpers have purpose-level JSDoc with `@param` and `@returns`
- Workflow interfaces have property-level descriptions

---

## Phase 3: TypeScript Low Priority — Workflow Internals (Verified Gaps Only)

**Parallelizable with Phases 1-2, 4.**

### 3.1 `resolver.ts` — 2 undocumented functions

- [ ] `resolveOutput(...)`: JSDoc with `@param`, `@returns`
- [ ] `walkDotPath(...)`: JSDoc with `@param`, `@returns`

### 3.2 `control-flow.ts` — 2 weak docstrings

- [ ] `ControlFlowHandler`: Expand from trivial one-liner to describe handler signature and purpose
- [ ] `CONTROL_FLOW_HANDLERS`: Expand to describe built-in handlers and how to extend

### 3.3 `validation.ts` — 8 undocumented symbols

- [ ] `ValidationResult`: Expand from trivial one-liner to describe fields
- [ ] `checkNodeIds(...)`: JSDoc with `@param`, `@returns`, `@throws`
- [ ] `checkEdgeReferences(...)`: JSDoc with `@param`, `@returns`, `@throws`
- [ ] `checkStartEnd(...)`: JSDoc with `@param`, `@returns`, `@throws`
- [ ] `checkCycles(...)`: JSDoc with `@param`, `@returns`, `@throws`
- [ ] `checkConnectivity(...)`: JSDoc with `@param`, `@returns`, `@throws`
- [ ] `bfs(...)`: JSDoc with algorithm description, `@param`, `@returns`
- [ ] `bfsMulti(...)`: JSDoc with algorithm description, `@param`, `@returns`

### 3.4 `executor.ts` — 5 undocumented methods

- [ ] `NodeExecutor.has(...)`: JSDoc with `@param`, `@returns`
- [ ] `InProcessExecutor.execute(...)`: JSDoc with `@param`, `@returns`, `@throws`
- [ ] `InProcessExecutor.has(...)`: JSDoc with `@param`, `@returns`
- [ ] `HttpExecutor.execute(...)`: JSDoc with `@param`, `@returns`, `@throws`
- [ ] `HttpExecutor.has(...)`: JSDoc with `@param`, `@returns`

**Note:** `level.ts` is already 100% documented — removed from scope.

**Acceptance Criteria:**
- Every symbol listed above has JSDoc with `@param`, `@returns`, `@throws` where applicable

---

## Phase 4: Python Low Priority — Remaining Gaps (Verified)

**Parallelizable with Phases 1-3.**

### 4.1 `router.py` — 1 missing docstring

- [ ] `python/canvastekk_workflow_sdk/router.py` — `root_health()`: Add PEP 257 docstring (purpose, response shape, HTTP 200)

### 4.2 `testing.py` — 3 undocumented methods

- [ ] `python/canvastekk_workflow_sdk/testing.py` — `LocalFileServer.__init__`: Add docstring (constructor params)
- [ ] `python/canvastekk_workflow_sdk/testing.py` — `LocalFileServer.__enter__`: Add docstring (context manager)
- [ ] `python/canvastekk_workflow_sdk/testing.py` — `LocalFileServer.__exit__`: Add docstring (context manager)

### 4.3 `workflow/validation.py` — 7 undocumented private functions

- [ ] `_check_node_ids(...)`: Docstring with validation rule, `Args`, `Raises`
- [ ] `_check_edge_references(...)`: Docstring with validation rule, `Args`, `Raises`
- [ ] `_check_start_end(...)`: Docstring with validation rule, `Args`, `Raises`
- [ ] `_check_cycles(...)`: Docstring with validation rule, `Args`, `Raises`
- [ ] `_check_connectivity(...)`: Docstring with validation rule, `Args`, `Raises`
- [ ] `_bfs(...)`: Docstring with algorithm description, `Args`, `Returns`
- [ ] `_bfs_multi(...)`: Docstring with algorithm description, `Args`, `Returns`

**Acceptance Criteria:**
- `root_health()` has PEP 257 compliant docstring
- `testing.py` dunder methods have docstrings
- `workflow/validation.py` private functions document their validation rules

---

## Phase 5: Verification

- [ ] Run `npx tsc --noEmit` from `typescript/` — must pass (type safety check)
- [ ] Run `poetry run ruff check canvastekk_workflow_sdk/ tests/` from `python/` — must pass (includes docstring linting)
- [ ] Run `poetry run pytest -v` from `python/` — all tests pass
- [ ] Run `npx vitest run` from `typescript/` — all tests pass
- [ ] Coverage audit — run coverage check scripts:
  ```bash
  # TypeScript: find functions without JSDoc
  grep -rn 'export function\|export class\|export interface\|export type\|export enum\|export const' typescript/src/ | grep -v '/**' | head -20

  # Python: find functions without docstrings (rough check)
  grep -rn 'def ' python/canvastekk_workflow_sdk/ | grep -v '"""' | grep -v '__' | head -20
  ```
- [ ] Cross-parity audit: verify every public symbol documented in Python has equivalent TypeScript JSDoc
- [ ] Post completion comment to [DA-1162](https://betekk.atlassian.net/browse/DA-1162)

**Acceptance Criteria:**
- `tsc --noEmit` passes
- `ruff check` passes
- All existing tests pass
- Coverage audit returns zero undocumented public symbols
- Cross-parity: every public symbol documented in both Python and TypeScript

---

## File Change Summary

| File | Phase | Additions |
|------|-------|-----------|
| `typescript/src/base-node.ts` | 1, 2 | 1 class JSDoc + 4 private helper JSDocs |
| `typescript/src/context.ts` | 1 | 1 class JSDoc |
| `typescript/src/definition.ts` | 1 | 3 function JSDocs |
| `typescript/src/request.ts` | 1 | 1 expanded type JSDoc |
| `typescript/src/response.ts` | 1 | 1 expanded type JSDoc + 2 factory JSDocs |
| `typescript/src/app.ts` | 1 | 8 route handler JSDocs |
| `typescript/src/logging.ts` | 2 | 4 private helper JSDocs |
| `typescript/src/auth.ts` | 2 | 2 private helper JSDocs |
| `typescript/src/workflow/builder.ts` | 2 | 1 private method JSDoc |
| `typescript/src/workflow/models.ts` | 2 | 4 expanded type/enum JSDocs |
| `typescript/src/workflow/resolver.ts` | 3 | 2 function JSDocs |
| `typescript/src/workflow/control-flow.ts` | 3 | 2 expanded JSDocs |
| `typescript/src/workflow/validation.ts` | 3 | 8 JSDocs (1 type + 7 functions) |
| `typescript/src/workflow/executor.ts` | 3 | 5 method JSDocs |
| `python/canvastekk_workflow_sdk/router.py` | 4 | 1 docstring |
| `python/canvastekk_workflow_sdk/testing.py` | 4 | 3 method docstrings |
| `python/canvastekk_workflow_sdk/workflow/validation.py` | 4 | 7 private function docstrings |

**Total:** 17 files, ~40 docstring/JSDoc additions (verified gaps only)
