# PLAN-DA-1162: Improve Docstring/JSDoc Coverage Across Python and TypeScript SDKs

> **JIRA Ticket:** [DA-1162](https://betekk.atlassian.net/browse/DA-1162)
> **Branch:** `DA-1162`
> **Status:** Planning
> **Created:** 2026-05-29

## Overview

A comprehensive docstring review found the Python SDK at ~95% coverage and the TypeScript SDK at ~75%. This plan closes all gaps to bring both SDKs to full docstring/JSDoc coverage with cross-language parity. Work is phased by priority: TypeScript public API first, then internal helpers, then workflow internals, then Python gaps, then verification.

**Target:** 100% docstring/JSDoc coverage across both SDKs.

---

## Phase 1: TypeScript High Priority — Public API Docstrings (Items 1–4)

### 1.1 Class-level JSDoc on public classes

- [ ] `typescript/src/base-node.ts` — Add class-level JSDoc to `BaseNode` matching Python's 24-line docstring (describe the abstract base class, lifecycle, `execute()` contract, `definition` attribute, `@abstract` tag)
- [ ] `typescript/src/context.ts` — Add class-level JSDoc to `ExecutionContext` matching Python's 11-line docstring (describe execution context, properties: `runId`, `nodeId`, `downloadsDir`, `outputPath()`, `reportProgress()`)

### 1.2 Public helper functions in `definition.ts`

- [ ] `typescript/src/definition.ts` — Add JSDoc to `getFileInputFields(def)` with `@param`, `@returns`, `@throws`
- [ ] `typescript/src/definition.ts` — Add JSDoc to `getFileOutputFields(def)` with `@param`, `@returns`
- [ ] `typescript/src/definition.ts` — Add JSDoc to `validateFileInput(field)` with `@param`, `@returns`, `@throws`

### 1.3 Wire-format types and response factories

- [ ] `typescript/src/request.ts` — Expand `NodeExecutionRequest` JSDoc: describe each field (`runId`, `nodeId`, `inputs`, `callbackUrl`, `outputUploadUrl`), add property-level docs
- [ ] `typescript/src/response.ts` — Expand `NodeExecutionResponse` JSDoc: describe each field, add property-level docs
- [ ] `typescript/src/response.ts` — Add JSDoc to `createSuccessResponse(outputs)` with `@param`, `@returns`
- [ ] `typescript/src/response.ts` — Add JSDoc to `createFailureResponse(error)` with `@param`, `@returns`

### 1.4 Route handlers in `app.ts`

- [ ] `typescript/src/app.ts` — Add JSDoc to `POST /execute` handler (describe request/response format, error handling)
- [ ] `typescript/src/app.ts` — Add JSDoc to `GET /health` handler (describe `HealthResponse` shape)
- [ ] `typescript/src/app.ts` — Add JSDoc to `GET /manifest` handler (describe `NodeDefinition` response)
- [ ] `typescript/src/app.ts` — Add JSDoc to `POST /hook` handler (describe lifecycle hook handling)
- [ ] `typescript/src/app.ts` — Add JSDoc to `GET /metrics` handler (describe Prometheus-style metrics)
- [ ] `typescript/src/app.ts` — Add JSDoc to `GET /live` handler (describe liveness probe)
- [ ] `typescript/src/app.ts` — Add JSDoc to `GET /ready` handler (describe readiness probe)
- [ ] `typescript/src/app.ts` — Add JSDoc to `GET /` root handler (describe redirect/overview response)

**Acceptance Criteria:**
- All public classes have class-level JSDoc matching Python depth
- All public functions have JSDoc with `@param`, `@returns`, `@throws` where applicable
- All route handlers documented with HTTP method, path, and response format

---

## Phase 2: TypeScript Medium Priority — Internal Helpers (Items 5–7)

### 2.1 Private helpers in `base-node.ts`

- [ ] `typescript/src/base-node.ts` — Add JSDoc to `sanitizeFilename(filename)` with `@param`, `@returns`
- [ ] `typescript/src/base-node.ts` — Add JSDoc to `extractFilename(url)` with `@param`, `@returns`
- [ ] `typescript/src/base-node.ts` — Add JSDoc to `compileSchema(definition)` with `@param`, `@returns`
- [ ] `typescript/src/base-node.ts` — Add JSDoc to `formatAjvErrors(errors)` with `@param`, `@returns`

### 2.2 Private helpers in `logging.ts`

- [ ] `typescript/src/logging.ts` — Add JSDoc to `getEnvLogLevel()` with `@returns`
- [ ] `typescript/src/logging.ts` — Add JSDoc to `getEnvLogFormat()` with `@returns`
- [ ] `typescript/src/logging.ts` — Add JSDoc to `writeLog(level, logger, message, meta)` with `@param`, `@returns`
- [ ] `typescript/src/logging.ts` — Add JSDoc to `getOrCreateConfig(name)` with `@param`, `@returns`

### 2.3 Private helpers in `auth.ts`

- [ ] `typescript/src/auth.ts` — Add JSDoc to `isDevMode()` with `@returns`
- [ ] `typescript/src/auth.ts` — Add JSDoc to `unauthorized(res, message)` with `@param`

### 2.4 Workflow builder private method

- [ ] `typescript/src/workflow/builder.ts` — Add JSDoc to `checkDuplicate(nodeId)` with `@param`, `@throws`

### 2.5 Workflow model types

- [ ] `typescript/src/workflow/models.ts` — Add JSDoc descriptions to all enum values in `NodeStatus`, `EdgeType` (or equivalent enums)
- [ ] `typescript/src/workflow/models.ts` — Add JSDoc descriptions to all interface properties in `WorkflowNode`, `WorkflowEdge`, `WorkflowSpec` (or equivalent interfaces)

**Acceptance Criteria:**
- All private helpers have purpose-level JSDoc with `@param` and `@returns`
- Workflow enums and interfaces have property-level descriptions

---

## Phase 3: TypeScript Low Priority — Workflow Internals (Item 8)

### 3.1 Workflow internal modules

- [ ] `typescript/src/workflow/level.ts` — Add JSDoc with `@param`/`@returns` to all exported functions
- [ ] `typescript/src/workflow/resolver.ts` — Add JSDoc with `@param`/`@returns` to all exported functions
- [ ] `typescript/src/workflow/control-flow.ts` — Add JSDoc with `@param`/`@returns` to all exported functions
- [ ] `typescript/src/workflow/validation.ts` — Add JSDoc with `@param`/`@returns`/`@throws` to all exported functions
- [ ] `typescript/src/workflow/executor.ts` — Add JSDoc with `@param`/`@returns`/`@throws` to all exported functions

**Acceptance Criteria:**
- Every exported function in workflow internals has JSDoc with `@param`, `@returns`, and `@throws` (where applicable)

---

## Phase 4: Python Low Priority — Remaining Gaps (Items 9–11)

### 4.1 `router.py`

- [ ] `python/canvastekk_workflow_sdk/router.py` — Add PEP 257 docstring to `root_health()` function (describe purpose, response shape, HTTP 200)

### 4.2 `testing.py`

- [ ] `python/canvastekk_workflow_sdk/testing.py` — Expand helper method docstrings with parameter descriptions, return types, and usage examples (review all methods in `LocalFileServer` and any test utilities)

### 4.3 `workflow/validation.py`

- [ ] `python/canvastekk_workflow_sdk/workflow/validation.py` — Add docstrings to all private functions (`_validate_*` / `_check_*`) describing the validation rules they enforce, `@param`-style descriptions, and what conditions trigger `WorkflowValidationError`

**Acceptance Criteria:**
- `root_health()` has a PEP 257 compliant docstring
- `testing.py` helper methods have detailed docstrings
- `workflow/validation.py` private functions document their validation rules

---

## Phase 5: Verification

- [ ] Run `npx tsc --noEmit` from `typescript/` — must pass with zero errors
- [ ] Run `poetry run ruff check canvastekk_workflow_sdk/ tests/` from `python/` — must pass with zero errors
- [ ] Run `poetry run pytest -v` from `python/` — all tests pass
- [ ] Run `npx vitest run` from `typescript/` — all tests pass
- [ ] Cross-parity audit: no symbol documented in one language but missing in the other
- [ ] Post completion comment to [DA-1162](https://betekk.atlassian.net/browse/DA-1162)

**Acceptance Criteria:**
- `tsc --noEmit` passes
- `ruff check` passes
- All existing tests pass
- Cross-parity: every public symbol documented in both Python and TypeScript

---

## File Change Summary

| File | Phase | Changes |
|------|-------|---------|
| `typescript/src/base-node.ts` | 1, 2 | Class JSDoc + 4 private helper JSDocs |
| `typescript/src/context.ts` | 1 | Class JSDoc |
| `typescript/src/definition.ts` | 1 | 3 function JSDocs |
| `typescript/src/request.ts` | 1 | Expanded type JSDoc |
| `typescript/src/response.ts` | 1 | Expanded type JSDoc + 2 factory JSDocs |
| `typescript/src/app.ts` | 1 | 8 route handler JSDocs |
| `typescript/src/logging.ts` | 2 | 4 private helper JSDocs |
| `typescript/src/auth.ts` | 2 | 2 private helper JSDocs |
| `typescript/src/workflow/builder.ts` | 2 | 1 private method JSDoc |
| `typescript/src/workflow/models.ts` | 2 | Enum/interface property descriptions |
| `typescript/src/workflow/level.ts` | 3 | Function JSDocs |
| `typescript/src/workflow/resolver.ts` | 3 | Function JSDocs |
| `typescript/src/workflow/control-flow.ts` | 3 | Function JSDocs |
| `typescript/src/workflow/validation.ts` | 3 | Function JSDocs |
| `typescript/src/workflow/executor.ts` | 3 | Function JSDocs |
| `python/canvastekk_workflow_sdk/router.py` | 4 | `root_health()` docstring |
| `python/canvastekk_workflow_sdk/testing.py` | 4 | Expanded helper docstrings |
| `python/canvastekk_workflow_sdk/workflow/validation.py` | 4 | Private function docstrings |

**Total:** 18 files, ~50+ docstring/JSDoc additions
