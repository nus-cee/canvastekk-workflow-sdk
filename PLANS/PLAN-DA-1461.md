# PLAN: DA-1461 — TypeScript SDK Parity Fixes: Version Sync, Wire-Format Naming, Keycloak Security, Resolver Alignment

**Ticket**: [DA-1461](https://betekk.atlassian.net/browse/DA-1461)
**Created**: 2026-07-12
**Status**: In Progress
**Branch**: `DA-1461`
**Labels**: backend, bugfix, parity, sdk, typescript
**Priority**: High

---

## Overview

Full feature parity audit between Python SDK (0.16.0) and TypeScript SDK (0.16.0). This ticket documents fixes already applied to `main` (pre-tag), review findings from architecture + TypeScript + Python reviews, and remaining parity gaps deferred to future work.

## Dependency & Consumer Map

| Consumer / Dependency | Impact |
|---|---|
| **Python SDK (canvastekk_workflow_sdk)** | Source of truth for wire-format behavior; TS must match |
| **Workflow Engine** | Rejects camelCase edge fields — TS nodes using old format would fail |
| **Keycloak Auth** | TS nodes deployed with insecure fallback could validate tokens against wrong key |
| **Consumer TS nodes** | Contract data must be snake_case to interoperate with Python nodes. **Exported TS interfaces changed field names — breaking change for direct field access** |
| **Registry / manifests** | `sdk_version` reported from `version.ts` must match actual package version |

---

## Phase 1: Version Sync Fix — `version.ts` (Completed)

**CRITICAL** — Runtime version mismatch caused every manifest, header, and registry payload to report wrong version.

- [x] **1.1** Update `typescript/src/version.ts:4` from `0.13.0` → `0.16.0`
  - **Why:** `package.json` reports 0.16.0 but `version.ts` was stale at 0.13.0; every `X-SDK-Version` header, manifest `sdk_version`, and registry payload reported the wrong version
  - **Done when:** `version.ts` reads `0.16.0` at runtime
  - **Consumers affected:** All TS nodes deployed via this SDK (manifests, headers, registry)

---

## Phase 2: Keycloak Security Fix — JWKS Key Fallback Removal (Completed)

**CRITICAL** — Security vulnerability: TS could validate tokens against the wrong signing key.

- [x] **2.1** Remove insecure JWKS key fallback in `typescript/src/auth.ts` (lines 216-217)
  - **Why:** When `kid` header didn't match any JWKS key, TS fell back to the first available key. Python correctly rejects with 401 "Token signing key not found in JWKS" (auth.py:237-238). This allowed TS to validate tokens against the wrong signing key
  - **Done when:** TS rejects tokens with unmatched `kid` header with 401, matching Python behavior
  - **Consumers affected:** All TS nodes behind Keycloak authentication

---

## Phase 3: Workflow Edge Field snake_case Migration (Completed)

**HIGH** — Workflow definitions built with TS SDK would be rejected by the engine.

All `WorkflowEdgeDefinition` fields changed from camelCase → snake_case across 6 files:

| Old (camelCase) | New (snake_case) |
|---|---|
| `fromNode` | `from_node` |
| `toNode` | `to_node` |
| `fromOutput` | `from_output` |
| `toInput` | `to_input` |
| `edgeType` | `edge_type` |

- [x] **3.1** Update `typescript/src/workflow/models.ts` — `WorkflowEdgeDefinition` interface fields
  - **Why:** Engine wire format expects snake_case; camelCase definitions rejected at runtime
  - **Done when:** All 5 edge fields are snake_case in the interface definition
  - **Consumers affected:** All TS nodes building workflow definitions via SDK

- [x] **3.2** Update `typescript/src/workflow/builder.ts` — edge construction output
  - **Why:** Builder must emit snake_case keys matching the updated model
  - **Done when:** Builder output uses snake_case field names
  - **Consumers affected:** Workflow builder consumers

- [x] **3.3** Update `typescript/src/workflow/runner.ts` — edge references
  - **Why:** Runner reads edge data; must reference snake_case keys
  - **Done when:** All edge field accesses use snake_case
  - **Consumers affected:** Workflow runner consumers

- [x] **3.4** Update `typescript/src/workflow/resolver.ts` — edge references
  - **Why:** Resolver traverses edge data; must use snake_case keys
  - **Done when:** All edge field accesses use snake_case
  - **Consumers affected:** Workflow resolver consumers

- [x] **3.5** Update `typescript/src/workflow/level.ts` — edge references
  - **Why:** Level executor reads edge connections; must use snake_case keys
  - **Done when:** All edge field accesses use snake_case
  - **Consumers affected:** Level-based workflow execution

- [x] **3.6** Update `typescript/src/workflow/validation.ts` — edge references (3 functions)
  - **Why:** Validation checks edge data; must reference snake_case keys
  - **Done when:** All edge field accesses across validation functions use snake_case
  - **Consumers affected:** Workflow validation consumers

---

## Phase 4: Contract Field snake_case Migration (Completed)

**HIGH** — Contract data produced by TS nodes would be incompatible with Python nodes.

- [x] **4.1** Update `typescript/src/contracts/instance.ts` — Instance interface fields → snake_case
  - **Why:** Python SDK uses snake_case throughout contracts; TS nodes producing camelCase data would fail interop
  - **Done when:** All Instance fields are snake_case
  - **Consumers affected:** All TS nodes producing/consuming Instance data

- [x] **4.2** Update `typescript/src/contracts/point3d.ts` — BoundingBox3D fields → snake_case
  - **Why:** BoundingBox3D must match Python contract format
  - **Done when:** All BoundingBox3D fields are snake_case
  - **Consumers affected:** All TS nodes producing/consuming point cloud bounding box data

---

## Phase 5: Resolver Alignment — KeyError Behavior (Completed, but has parity bug — see Phase 7)

**MEDIUM** — TS resolver silently walked dot-paths when flat keys should be checked first.

- [x] **5.1** Update `typescript/src/workflow/resolver.ts:27-38` — check flat keys before dot-path walk
  - **Why:** Python `resolveOutput()` checks direct key first and raises `KeyError` if flat key not found. TS always went to dot-path walk if key contained ".", masking missing-key errors
  - **Done when:** `resolveOutput()` throws `Error` on missing flat keys, matching Python `KeyError` behavior
  - **Consumers affected:** Workflow nodes using resolver for output lookups
  - **Note:** Review found this implementation has a parity bug — Phase 7.1 fixes it

---

## Phase 6: Test Updates (Completed, but has test bugs — see Phase 7)

All test files updated to use snake_case field names.

- [x] **6.1** Update `typescript/tests/contracts.test.ts` — Instance/Point3D assertions → snake_case
  - **Why:** Tests must match updated contract field names
  - **Done when:** All contract test assertions pass with snake_case fields
  - **Consumers affected:** CI pipeline

- [x] **6.2** Update `typescript/tests/workflow-builder.test.ts` — edge assertions → snake_case
  - **Why:** Builder output field names changed
  - **Done when:** All builder tests pass with snake_case edge fields
  - **Consumers affected:** CI pipeline

- [x] **6.3** Update `typescript/tests/workflow-level.test.ts` — edge assertions → snake_case
  - **Why:** Level executor references changed
  - **Done when:** All level tests pass with snake_case edge fields
  - **Consumers affected:** CI pipeline

- [x] **6.4** Update `typescript/tests/workflow-resolver.test.ts` — edge + KeyError assertions
  - **Why:** Resolver key references changed; new KeyError behavior needs test coverage
  - **Done when:** All resolver tests pass including KeyError throw cases
  - **Consumers affected:** CI pipeline

- [x] **6.5** Update `typescript/tests/workflow-runner.test.ts` — edge assertions → snake_case
  - **Why:** Runner edge references changed
  - **Done when:** All runner tests pass with snake_case edge fields
  - **Consumers affected:** CI pipeline

- [x] **6.6** Update `typescript/tests/workflow-validation.test.ts` — edge assertions → snake_case (3 functions)
  - **Why:** Validation edge references changed
  - **Done when:** All validation tests pass with snake_case edge fields
  - **Consumers affected:** CI pipeline

---

## Phase 7: Critical Fixes from Reviews (Blocking — must complete before merge)

**Sources:** Architecture review C2, TypeScript review C1/M1, Python reviewer confirmation

These issues were found during architecture, TypeScript, and Python code reviews. They are blocking — the resolver bug is a parity gap and the test bugs mean tests are silently testing wrong behavior.

- [ ] **7.1** Fix resolver parity bug — TS `resolveOutput()` must check flat keys first for ALL keys
  - **Why:** Current TS implementation branches on dot presence (`if (!fromOutput.includes("."))`), skipping the flat-key check for dotted keys. Python checks flat key first for ALL keys. For `sourceOutputs = { "a.b": 42 }` and `fromOutput = "a.b"`: Python returns `42`, TS throws error. This is a wire-format parity gap
  - **Done when:** `resolveOutput()` checks `if (fromOutput in sourceOutputs)` first, then falls back to dot-path walk, then throws — matching Python's `_resolve_output` exactly
  - **Consumers affected:** All workflow nodes using resolver for output lookups
  - **Fix:**
    ```typescript
    function resolveOutput(sourceOutputs: Record<string, unknown>, fromOutput: string): unknown {
      if (!fromOutput) return sourceOutputs;
      if (fromOutput in sourceOutputs) return sourceOutputs[fromOutput];
      if (fromOutput.includes(".")) return walkDotPath(sourceOutputs, fromOutput);
      throw new Error(`Cannot resolve from_output '${fromOutput}'`);
    }
    ```

- [ ] **7.2** Fix `connect()` test calls — revert snake_case option keys to camelCase
  - **Why:** `connect()` method signature accepts camelCase option keys (`fromOutput`, `toInput`, `edgeType`). Multiple tests were changed to pass snake_case keys (`from_output`, `to_input`) which don't exist on the type — they're silently ignored, defaulting to empty strings. Tests appear to pass but are testing wrong behavior. `tsconfig.json` excludes tests from type checking, and Vitest uses esbuild (strips types), so these type errors are invisible
  - **Done when:** All `connect()` calls in tests use camelCase option keys matching the builder API
  - **Consumers affected:** CI pipeline — tests will actually verify edge wiring correctly
  - **Files affected:** `typescript/tests/workflow-builder.test.ts:11-12,168`, `typescript/tests/workflow-runner.test.ts:176-177,201-202,223-224,312-313`

- [ ] **7.3** Fix stale resolver test name — "returns undefined" → "throws"
  - **Why:** Test name at `workflow-resolver.test.ts:36` says "returns undefined when from_output does not exist" but the body now expects `toThrow(...)`. Misleading test names reduce debuggability
  - **Done when:** Test name accurately reflects throw behavior
  - **Consumers affected:** Developer experience

- [ ] **7.4** Add resolver unit tests for edge cases (flat-key-with-dots, missing keys, dot-path failures)
  - **Why:** CodeGraph blast radius shows `resolveOutput` and `walkDotPath` have no dedicated test coverage beyond the workflow-level integration tests. The parity bug in 7.1 went undetected because of this gap
  - **Done when:** Unit tests cover: flat key match (found/not found), dot-path traversal (nested/missing segment/non-dict intermediate/empty segment), flat-key-first-then-dot-path ordering for dotted keys, multi-edge input merging, node-not-found
  - **Consumers affected:** CI pipeline, future resolver changes

---

## Phase 8: TypeScript Type Safety & Error Handling Improvements (Non-breaking)

**Sources:** TypeScript review M5/m2/m3/m4/m5, Architecture review R1

- [ ] **8.1** Add custom `ResolverError` class with error codes
  - **Why:** Resolver currently throws bare `Error` for 5 distinct failure modes (node not found, key not found, invalid path, traversal error, segment not found). Callers catch as `String(exc)` losing structured info. Python uses `KeyError` which is catchable by type. A typed error enables `if (e instanceof ResolverError)` handling
  - **Done when:** `ResolverError` class exported with discriminating `code` field (`NODE_NOT_FOUND | KEY_NOT_FOUND | INVALID_PATH | TRAVERSAL_ERROR`)
  - **Consumers affected:** Workflow runner error handling, SDK consumers catching resolver errors
  - **File:** `typescript/src/workflow/resolver.ts`

- [ ] **8.2** Add `readonly` modifier to wire-format interface fields
  - **Why:** Wire-format types (`WorkflowEdgeDefinition`, `Instance`, `InstanceSetData`, `BoundingBox3D`) represent immutable serialized data. Adding `readonly` enforces immutability at compile time, preventing accidental mutation
  - **Done when:** All wire-format interface fields have `readonly` modifier
  - **Consumers affected:** None (additive type safety — valid code doesn't mutate these)
  - **Files:** `typescript/src/workflow/models.ts`, `typescript/src/contracts/instance.ts`, `typescript/src/contracts/point3d.ts`

- [ ] **8.3** Replace `as` type assertions with proper type guard in `walkDotPath`
  - **Why:** `walkDotPath` uses `current as Record<string, unknown>` assertions (lines 50, 53) instead of proper narrowing. A type guard function (`isRecord`) is cleaner and safer
  - **Done when:** `isRecord` type guard function replaces `as` assertions
  - **Consumers affected:** None (internal implementation)
  - **File:** `typescript/src/workflow/resolver.ts`

- [ ] **8.4** Remove redundant type cast in `apiKey` middleware
  - **Why:** `const req = _req as Request` is redundant — `_req` is already typed as `Request`
  - **Done when:** Redundant cast removed
  - **Consumers affected:** None
  - **File:** `typescript/src/auth.ts:50`

- [ ] **8.5** Add warning log in runner cleanup error swallowing
  - **Why:** `catch {}` block at `runner.ts:217-219` silently swallows cleanup errors. At minimum should log a warning for debuggability
  - **Done when:** Empty `catch {}` replaced with `catch (e) { console.warn(...) }`
  - **Consumers affected:** Operator observability
  - **File:** `typescript/src/workflow/runner.ts`

---

## Phase 9: Version Drift Prevention (Non-breaking)

**Source:** TypeScript review M3

- [ ] **9.1** Add `version.ts` to release pipeline's version bump script OR derive from `package.json`
  - **Why:** `version.ts` was the root cause of the original bug (0.13.0 vs 0.16.0). The fix bumps the number but doesn't prevent recurrence. The release pipeline bumps `pyproject.toml`, `__init__.py`, `package.json`, `Directory.Build.props` but not `version.ts`. Without this fix, version drift will happen again on the next release
  - **Done when:** Either (a) the release bump script includes `typescript/src/version.ts`, or (b) `version.ts` derives its value from `package.json` at build/runtime
  - **Consumers affected:** Release pipeline, all future SDK releases
  - **Option A (pipeline fix):** Add `version.ts` to `.github/workflows/release.yml` bump script
  - **Option B (derive):**
    ```typescript
    // version.ts — derived from package.json to prevent drift
    import packageJson from "../package.json" with { type: "json" };
    export const VERSION = packageJson.version;
    ```

---

## Phase 10: Python Auth Robustness — JWKS Hardening (Non-breaking)

**Sources:** Python review P1/P7, Architecture review R2

- [ ] **10.1** Implement JWKS refresh-on-miss during key rotation (Python)
  - **Why:** When a token's `kid` is not found in the cached JWKS, the code immediately returns 401. During Keycloak key rotation, there's a window where the old `kid` is in tokens but the JWKS cache (TTL=300s) still holds pre-rotation keys. Valid tokens are rejected for up to 5 minutes. Force-refreshing once before rejecting eliminates this outage window
  - **Done when:** On key-not-found, JWKS cache is invalidated and re-fetched once before final rejection. Existing tokens with matching kids follow the same path (cache hit). The 401 for genuinely unknown kids is unchanged
  - **Consumers affected:** All nodes behind Keycloak auth — eliminates rotation-induced auth outages
  - **File:** `python/canvastekk_workflow_sdk/auth.py:228-238`
  - **Non-breaking because:** Only the key-not-found path changes; it adds one retry before the same 401. No API surface change

- [ ] **10.2** Add explicit `kid` None check with clearer error message (Python)
  - **Why:** `kid = unverified_header.get("kid")` returns `None` if missing. The loop silently fails to match, giving a generic "Token signing key not found in JWKS" error. An explicit check gives a clear "Token header missing required 'kid' field" message
  - **Done when:** Missing `kid` header produces a specific 401 error message before JWKS lookup
  - **Consumers affected:** Operator debuggability
  - **File:** `python/canvastekk_workflow_sdk/auth.py:228`

- [ ] **10.3** Add debug logging on `kid` mismatch (Python + TS)
  - **Why:** When a token is rejected because `kid` doesn't match any JWKS key, there's no logging. During key rotation or misconfiguration, operators need visibility into why tokens are rejected
  - **Done when:** Warning log includes the unmatched `kid` and available JWKS key IDs
  - **Consumers affected:** Operator troubleshooting
  - **Files:** `python/canvastekk_workflow_sdk/auth.py`, `typescript/src/auth.ts:218-221`

- [ ] **10.4** Document JWKS x5c-only key parsing limitation (TS)
  - **Why:** TS JWKS parsing only handles `x5c` certificate keys (`if (key.kid && key.x5c?.[0])`). Python's `PyJWKSet` handles all JWK formats (x5c, n/e, etc.). If Keycloak issues RSA keys with only `n`/`e` (no `x5c`), TS silently drops them. This is a latent parity gap exposed by the security review
  - **Done when:** JSDoc on the keycloak middleware documents the x5c-only limitation, OR migrate to `jose` library for full JWK support (deferred to separate ticket if large effort)
  - **Consumers affected:** Keycloak deployments using non-x5c key formats
  - **File:** `typescript/src/auth.ts:174-180`

---

## Phase 11: Python Contract Field Validation (Non-breaking)

**Sources:** Python review P2/P3/P4

- [ ] **11.1** Add `ge=0` constraints on contract ID and index fields (Python)
  - **Why:** `instance_id`, `class_id`, `point_indices`, and `point_count` accept any integer including negatives. Negative IDs/indices are semantically invalid and cause subtle downstream bugs (e.g., negative list indexing)
  - **Done when:** Fields have `ge=0` Pydantic constraint; `point_indices` has `@field_validator` rejecting negative values. Serialized JSON for valid data is byte-identical
  - **Consumers affected:** None (only rejects invalid data at parse time)
  - **File:** `python/canvastekk_workflow_sdk/contracts.py:158-167`
  - **Code:**
    ```python
    class Instance(BaseModel):
        instance_id: int = Field(ge=0, description="Unique ID within this instance set")
        class_id: int = Field(ge=0, description="Numeric class identifier")
        point_indices: list[int] = Field(default_factory=list)

        @field_validator("point_indices")
        @classmethod
        def _validate_indices_non_negative(cls, v):
            if any(idx < 0 for idx in v):
                raise ValueError("point_indices must be non-negative integers")
            return v

    class InstanceSet(BaseContract):
        point_count: int = Field(default=0, ge=0, ...)
    ```

- [ ] **11.2** Add `BoundingBox3D` `min <= max` cross-field validator (Python)
  - **Why:** Accepts inverted boxes where `min_point.x > max_point.x`, producing negative sizes and nonsensical centers. The existing `test_zero_size` test uses `min == max` which should pass
  - **Done when:** `@model_validator(mode="after")` checks each axis (`x`, `y`, `z`) and raises `ValueError` if `min > max`
  - **Consumers affected:** None (only rejects invalid data)
  - **File:** `python/canvastekk_workflow_sdk/contracts.py:108-130`
  - **Code:**
    ```python
    @model_validator(mode="after")
    def _validate_min_le_max(self) -> "BoundingBox3D":
        for axis in ("x", "y", "z"):
            if getattr(self.min_point, axis) > getattr(self.max_point, axis):
                raise ValueError(
                    f"BoundingBox3D min_point.{axis} > max_point.{axis}"
                )
        return self
    ```

- [ ] **11.3** Add `min_length=1` on edge and node string ID fields (Python)
  - **Why:** `from_node`, `to_node` (edge), and `id` (node) accept empty strings. An edge with `from_node=""` passes Pydantic but fails downstream with cryptic errors. The existing `_check_node_ids` validation catches these post-construction — this catches them earlier with a clearer Pydantic error
  - **Done when:** `min_length=1` constraint on `WorkflowEdgeDefinition.from_node`, `.to_node` and `WorkflowDefinitionNode.id`
  - **Consumers affected:** None (empty-string IDs were never valid)
  - **File:** `python/canvastekk_workflow_sdk/workflow/models.py:30-42,45-60`

---

## Phase 12: Python Resolver Error Enrichment (Non-breaking)

**Source:** Python review P5

- [ ] **12.1** Enrich `KeyError` messages with source node context and available keys (Python)
  - **Why:** Current error says `Cannot resolve from_output 'X'` without indicating which source node's outputs were searched. In multi-edge workflows, this makes debugging difficult. Including available keys helps immediately identify typos
  - **Done when:** `_resolve_output` accepts optional `from_node` parameter (default `""`); error messages include node context and `sorted(source_outputs.keys())`. Function signature backward-compatible (optional param with default). Tests matching on "not found"/"non-dict"/"empty segment" substrings still pass
  - **Consumers affected:** Developer debugging experience
  - **File:** `python/canvastekk_workflow_sdk/workflow/resolver.py:28-30,39-50`

---

## Phase 13: Python Testing & Builder Improvements (Non-breaking)

**Sources:** Python review P6/P8

- [ ] **13.1** Switch `LocalFileServer` to `ThreadingHTTPServer` (Python)
  - **Why:** `HTTPServer` is single-threaded. Concurrent file downloads (e.g., a node with multiple file inputs) are serialized, causing timeouts in test scenarios. `ThreadingHTTPServer` is a drop-in subclass that spawns a thread per request
  - **Done when:** `ThreadingHTTPServer` replaces `HTTPServer`. Server lifecycle (start/stop/shutdown) works identically. All existing tests pass
  - **Consumers affected:** Test suite throughput, node authors using LocalFileServer in integration tests
  - **File:** `python/canvastekk_workflow_sdk/testing.py:103`

- [ ] **13.2** Add self-loop detection in builder `connect()` (Python)
  - **Why:** `connect("node1", "node1")` creates a self-loop, caught later during `build()` → `validate()` → `_check_cycles()` with a generic "cycle involving node(s)" message. Catching it earlier in `connect()` gives a clearer "Self-loop detected: cannot connect 'node1' to itself" message
  - **Done when:** `connect()` raises `ValueError` immediately if `from_node == to_node`. No valid workflow uses self-loops
  - **Consumers affected:** Developer UX for workflow construction errors
  - **File:** `python/canvastekk_workflow_sdk/workflow/builder.py:134-159`

---

## Phase 14: TS Parity Propagation from Python Improvements

**Sources:** Python review P1-P5/P7-P8, Architecture review parity mandate

Propagate the Python improvements from Phases 10-13 to the TypeScript SDK to maintain parity. Each item mirrors its Python counterpart.

- [ ] **14.1** TS: Implement JWKS refresh-on-miss during key rotation (mirrors Phase 10.1)
  - **Why:** Parity — Python will have refresh-on-miss; TS must match to avoid asymmetric auth behavior
  - **Done when:** TS `keycloak` auth force-refreshes JWKS once on `kid`-not-found before 401
  - **File:** `typescript/src/auth.ts`

- [ ] **14.2** TS: Add explicit `kid` undefined check (mirrors Phase 10.2)
  - **Why:** Parity — Python will have explicit missing-kid check
  - **Done when:** TS rejects tokens missing `kid` header with specific 401 message
  - **File:** `typescript/src/auth.ts`

- [ ] **14.3** TS: Add contract field validation constraints (mirrors Phase 11.1/11.2)
  - **Why:** Parity — Python will enforce `ge=0` and `min <= max` at construction time. TS should validate the same constraints (via runtime validation or schema)
  - **Done when:** TS contract creation validates non-negative IDs, non-negative indices, and `min <= max` bounding boxes
  - **Files:** `typescript/src/contracts/instance.ts`, `typescript/src/contracts/point3d.ts`

- [ ] **14.4** TS: Add `min_length=1` validation on edge/node string fields (mirrors Phase 11.3)
  - **Why:** Parity — Python will enforce non-empty string IDs
  - **Done when:** TS builder/validation rejects empty-string node/edge IDs
  - **Files:** `typescript/src/workflow/models.ts`, `typescript/src/workflow/validation.ts`

- [ ] **14.5** TS: Enrich resolver error messages with node context (mirrors Phase 12.1)
  - **Why:** Parity — Python resolver errors will include source node context and available keys
  - **Done when:** TS `ResolverError` messages (from Phase 8.1) include node ID and available output keys
  - **File:** `typescript/src/workflow/resolver.ts`

- [ ] **14.6** TS: Add self-loop detection in builder `connect()` (mirrors Phase 13.2)
  - **Why:** Parity — Python builder will reject self-loops early
  - **Done when:** TS `connect()` throws if `fromNode === toNode`
  - **File:** `typescript/src/workflow/builder.ts`

---

## Phase 15: Documentation & Migration Guide

**Sources:** Architecture review M3/R4, TypeScript review M4

- [ ] **15.1** Update `typescript/README.md` — document snake_case wire-format convention
  - **Why:** README shows camelCase API params for `connect()` but doesn't explain that wire-format types use snake_case. This dual-layer convention needs explicit documentation
  - **Done when:** README includes a section explaining: wire-format types use snake_case by design, builder translates camelCase API → snake_case wire format, this matches Python SDK and engine's `SaveWorkflowRequest.spec` schema
  - **Consumers affected:** All TS SDK consumers

- [ ] **15.2** Add migration table for renamed fields
  - **Why:** The field renames are a breaking change for consumers accessing exported interface fields directly. A migration table enables consumers to update their code
  - **Done when:** Migration table in `typescript/README.md` (or a `MIGRATION.md`) documents all old → new field name mappings for `WorkflowEdgeDefinition`, `Instance`, `InstanceSetData`, `BoundingBox3D`
  - **Consumers affected:** All TS SDK consumers upgrading from pre-0.16.0

- [ ] **15.3** Check `docs/EXTERNAL-AUTHOR-GUIDE.md` for TypeScript references
  - **Why:** The external author guide is the primary external-facing doc. If it references TS field names, they need updating
  - **Done when:** Guide reviewed and updated if it references old camelCase TS field names
  - **Consumers affected:** External node authors

---

## Phase 16: Cross-Language Verification (Pending)

**Sources:** Architecture review R3, verification requirements

- [ ] **16.1** Run TypeScript typecheck: `npx tsc --noEmit` in `typescript/`
  - **Why:** Must confirm no type errors after all fixes (resolver restructure, readonly, type guards, error class)
  - **Done when:** Typecheck exits 0 with no errors
  - **Consumers affected:** CI pipeline, SDK consumers

- [ ] **16.2** Run TypeScript tests: `npx vitest run` in `typescript/`
  - **Why:** All tests must pass after resolver fix, test corrections, and new resolver unit tests
  - **Done when:** All tests pass (previous 204 + new resolver tests)
  - **Consumers affected:** CI pipeline, SDK consumers

- [ ] **16.3** Run TypeScript build: `npx tsup` in `typescript/`
  - **Why:** Ensure production build succeeds with all changes
  - **Done when:** Build completes without errors
  - **Consumers affected:** Published SDK package consumers

- [ ] **16.4** Run Python lint: `poetry run ruff check canvastekk_workflow_sdk/ tests/`
  - **Why:** Must confirm no lint errors after Python robustness improvements
  - **Done when:** Ruff exits 0 with no errors
  - **Consumers affected:** CI pipeline

- [ ] **16.5** Run Python tests: `poetry run pytest -v`
  - **Why:** All Python tests must pass after contract validators, auth changes, resolver enrichment, builder improvements
  - **Done when:** All tests pass
  - **Consumers affected:** CI pipeline

- [ ] **16.6** Add cross-language round-trip serialization test
  - **Why:** Verification strategy tests each SDK in isolation. A round-trip test serializes a `WorkflowDefinitionSpec` from both builders and compares JSON structure, catching future snake_case/camelCase drift early
  - **Done when:** Test compares TS `JSON.stringify(spec)` against Python `model_dump(mode="json")` for a representative workflow definition
  - **Consumers affected:** CI pipeline, future parity maintenance

---

## Phase 17: Deferred — Remaining Parity Gaps (Not in scope for this ticket)

These are LOW-priority items identified during the parity audit but intentionally deferred.

- [ ] **17.1** Testing utilities — LocalFileServer equivalent for TS
  - **Why:** Python has `canvastekk_workflow_sdk.testing.LocalFileServer`; TS has none. Low impact — TS can test with real HTTP servers or mocks
  - **Done when:** TS SDK ships a `LocalFileServer` or equivalent test utility
  - **Consumers affected:** TS node authors writing integration tests

- [ ] **17.2** CLI tool — `__main__.py` equivalent
  - **Why:** Python SDK has a CLI entry point for validation; TS has none. Low impact — `npx` can serve similar purpose
  - **Done when:** TS SDK ships a CLI entry point
  - **Consumers affected:** TS node authors wanting quick validation

- [ ] **17.3** File download streaming
  - **Why:** Python streams file downloads via `httpx.stream()`; TS reads entire response into memory. Low impact for typical file sizes
  - **Done when:** TS file downloads use streaming
  - **Consumers affected:** TS nodes handling large file inputs

- [ ] **17.4** OpenAPI metadata generation
  - **Why:** Python generates OpenAPI spec from node definitions; TS Express has no built-in equivalent. Low impact — external tools can generate specs
  - **Done when:** TS SDK can auto-generate OpenAPI from node definitions
  - **Consumers affected:** API documentation workflows

- [ ] **17.5** Sync workflow runner
  - **Why:** TS workflow runner is async-only; Python supports sync. Low impact — async is idiomatic for Node.js
  - **Done when:** TS SDK offers sync runner option (if ever needed)
  - **Consumers affected:** Edge cases requiring sync execution

- [ ] **17.6** TS: Migrate JWKS parsing to `jose` library for full JWK format support
  - **Why:** TS only handles `x5c`-bearing keys (Phase 10.4 documents this). Full JWK support (n/e keys) requires a proper library. Deferred as separate ticket due to dependency addition scope
  - **Done when:** TS uses `jose` or equivalent for JWKS parsing supporting all JWK formats
  - **Consumers affected:** Keycloak deployments using non-x5c key formats

---

## Files Changed

### Original parity fixes (17 files — completed)

| File | Change | Phase |
|---|---|---|
| `typescript/src/version.ts` | 0.13.0 → 0.16.0 | 1 |
| `typescript/src/auth.ts` | Removed insecure JWKS key fallback | 2 |
| `typescript/src/workflow/models.ts` | Edge fields → snake_case | 3 |
| `typescript/src/workflow/builder.ts` | Edge output → snake_case | 3 |
| `typescript/src/workflow/runner.ts` | Edge refs → snake_case | 3 |
| `typescript/src/workflow/resolver.ts` | Edge refs → snake_case + KeyError behavior | 3, 5 |
| `typescript/src/workflow/level.ts` | Edge refs → snake_case | 3 |
| `typescript/src/workflow/validation.ts` | Edge refs → snake_case (3 functions) | 3 |
| `typescript/src/contracts/instance.ts` | Instance fields → snake_case | 4 |
| `typescript/src/contracts/point3d.ts` | BoundingBox3D fields → snake_case | 4 |
| `typescript/tests/contracts.test.ts` | Updated to snake_case | 6 |
| `typescript/tests/workflow-builder.test.ts` | Updated to snake_case | 6 |
| `typescript/tests/workflow-level.test.ts` | Updated to snake_case | 6 |
| `typescript/tests/workflow-resolver.test.ts` | Updated to snake_case | 6 |
| `typescript/tests/workflow-runner.test.ts` | Updated to snake_case | 6 |
| `typescript/tests/workflow-validation.test.ts` | Updated to snake_case | 6 |
| `typescript/package-lock.json` | Lockfile update | — |

### New files from review findings (Phases 7-15)

| File | Change | Phase |
|---|---|---|
| `typescript/src/workflow/resolver.ts` | Fix flat-key-first parity bug + `ResolverError` class + `isRecord` guard | 7.1, 8.1, 8.3 |
| `typescript/tests/workflow-builder.test.ts` | Fix `connect()` calls to camelCase option keys | 7.2 |
| `typescript/tests/workflow-runner.test.ts` | Fix `connect()` calls to camelCase option keys | 7.2 |
| `typescript/tests/workflow-resolver.test.ts` | Fix test name + add edge-case unit tests | 7.3, 7.4 |
| `typescript/src/workflow/models.ts` | Add `readonly` to wire-format fields | 8.2 |
| `typescript/src/contracts/instance.ts` | Add `readonly` + validation constraints | 8.2, 14.3 |
| `typescript/src/contracts/point3d.ts` | Add `readonly` + validation constraints | 8.2, 14.3 |
| `typescript/src/auth.ts` | Remove redundant cast + kid check + refresh-on-miss + logging | 8.4, 14.1, 14.2, 10.3 |
| `typescript/src/workflow/runner.ts` | Add warning log in cleanup | 8.5 |
| `typescript/src/workflow/builder.ts` | Add self-loop detection | 14.6 |
| `typescript/src/workflow/validation.ts` | Add min_length validation | 14.4 |
| `.github/workflows/release.yml` | Add `version.ts` to bump script | 9.1 |
| `python/canvastekk_workflow_sdk/auth.py` | JWKS refresh-on-miss + kid check + logging | 10.1, 10.2, 10.3 |
| `python/canvastekk_workflow_sdk/contracts.py` | `ge=0` + `min <= max` validators | 11.1, 11.2 |
| `python/canvastekk_workflow_sdk/workflow/models.py` | `min_length=1` on string fields | 11.3 |
| `python/canvastekk_workflow_sdk/workflow/resolver.py` | Enriched error messages | 12.1 |
| `python/canvastekk_workflow_sdk/testing.py` | `ThreadingHTTPServer` | 13.1 |
| `python/canvastekk_workflow_sdk/workflow/builder.py` | Self-loop detection | 13.2 |
| `typescript/README.md` | Wire-format convention docs + migration table | 15.1, 15.2 |
| `docs/EXTERNAL-AUTHOR-GUIDE.md` | Review for TS field name references | 15.3 |

---

## Acceptance Criteria

### Original parity criteria
- [x] `version.ts` reports `0.16.0` at runtime
- [x] Keycloak auth rejects tokens when `kid` not matched (no fallback)
- [x] Workflow edge fields use snake_case matching engine wire format
- [x] Contract fields use snake_case matching Python SDK
- [x] Resolver throws on missing flat keys (matches Python `KeyError`)

### Review-driven criteria
- [ ] Resolver checks flat keys first for ALL keys including dotted keys (parity bug fix)
- [ ] All `connect()` test calls use correct camelCase option keys
- [ ] Resolver has dedicated unit tests covering flat-key, dot-path, and ordering edge cases
- [ ] `ResolverError` custom class with discriminating error codes
- [ ] Wire-format interfaces have `readonly` fields
- [ ] `version.ts` is in the release bump pipeline or derived from `package.json`
- [ ] Python JWKS refreshes on key-not-found before rejecting (rotation resilience)
- [ ] Python contracts enforce `ge=0` on IDs/indices and `min <= max` on bounding boxes
- [ ] Python edge/node fields enforce `min_length=1`
- [ ] Python resolver errors include source node context and available keys
- [ ] Python `LocalFileServer` uses `ThreadingHTTPServer`
- [ ] Python builder rejects self-loops early
- [ ] TS propagated all applicable Python improvements (Phases 14.1-14.6)
- [ ] Migration table documenting renamed fields published
- [ ] Cross-language round-trip serialization test passes

### Verification criteria
- [ ] All TypeScript tests pass (`npx vitest run`)
- [ ] TypeScript typecheck passes (`npx tsc --noEmit`)
- [ ] TypeScript build succeeds (`npx tsup`)
- [ ] Python lint passes (`poetry run ruff check`)
- [ ] Python tests pass (`poetry run pytest -v`)

### Deferred (Phase 17)
- [ ] Testing utilities (LocalFileServer equivalent) — TS
- [ ] CLI tool — TS
- [ ] File download streaming — TS
- [ ] OpenAPI metadata generation — TS
- [ ] Sync workflow runner — TS
- [ ] Full JWK format support via `jose` library — TS

---

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| **Existing TS nodes using camelCase field names break** | Exported TS interfaces (`WorkflowEdgeDefinition`, `Instance`, `InstanceSetData`, `BoundingBox3D`) changed field names — this IS a **breaking change** for direct field access. Builder API (`connect()` with camelCase params) is unchanged. Migration table provided in Phase 15.2. Use `feat(ts)!:` commit type for breaking change semver signal |
| Keycloak rejection breaks legitimate tokens | Matches Python behavior; only tokens with unmatched `kid` headers are rejected — these were already being validated against wrong keys (a security bug). Phase 10.1 adds refresh-on-miss to handle key rotation gracefully |
| Snake_case fields feel unidiomatic in TS | Required for engine wire-format compatibility; Python SDK uses snake_case throughout. Builder API remains camelCase (dual-layer architecture). Documented in README (Phase 15.1) |
| Resolver restructure (Phase 7.1) changes behavior for dotted flat keys | Extremely rare edge case (literal keys containing dots). Python has always checked flat first. New unit tests (Phase 7.4) verify both behaviors |
| Python validators (`ge=0`, `min <= max`) reject previously-accepted invalid data | Only rejects semantically invalid data (negative IDs, inverted boxes). All valid data passes unchanged. Wire-format output is byte-identical for valid inputs |
| JWKS refresh-on-miss adds latency to auth failures | Only triggers on key-not-found path (rare). One additional network round-trip before 401. Acceptable tradeoff for eliminating rotation-induced outages |

---

## Review Findings Index

| ID | Source Review | Severity | Phase |
|---|---|---|---|
| Arch-C1 | Architecture | Critical — versioning strategy | Notes (commit type) |
| Arch-C2 | Architecture | Critical — resolver parity bug | 7.1 |
| Arch-M1 | Architecture | Major — misleading API impact claim | Risks section rewritten |
| Arch-M2 | Architecture | Major — no resolver tests | 7.4 |
| Arch-M3 | Architecture | Major — no migration guide | 15.2 |
| Arch-M4 | Architecture | Major — PLAN atomicity | All new phases have Why/Done when/Consumers |
| Arch-R1 | Architecture | Recommendation — typed resolver error | 8.1 |
| Arch-R2 | Architecture | Recommendation — JWKS logging | 10.3 |
| Arch-R3 | Architecture | Recommendation — cross-lang test | 16.6 |
| Arch-R4 | Architecture | Recommendation — README docs | 15.1 |
| TS-C1 | TypeScript | Critical — `connect()` test keys wrong | 7.2 |
| TS-M1 | TypeScript | Major — resolver divergence | 7.1 |
| TS-M2 | TypeScript | Major — JWKS x5c-only limitation | 10.4 |
| TS-M3 | TypeScript | Major — version.ts drift prevention | 9.1 |
| TS-M4 | TypeScript | Major — breaking change mischaracterized | Risks section + commit type |
| TS-M5 | TypeScript | Major — generic Error in resolver | 8.1 |
| TS-m1 | TypeScript | Minor — stale test name | 7.3 |
| TS-m2 | TypeScript | Minor — `as` type assertion | 8.3 |
| TS-m3 | TypeScript | Minor — missing `readonly` | 8.2 |
| TS-m4 | TypeScript | Minor — redundant type cast | 8.4 |
| TS-m5 | TypeScript | Minor — error swallowing | 8.5 |
| TS-m6 | TypeScript | Minor — `await` on sync `build()` | Noted (cosmetic, non-blocking) |
| Py-P1 | Python | High — JWKS refresh-on-miss | 10.1 |
| Py-P2 | Python | High — `ge=0` contract constraints | 11.1 |
| Py-P3 | Python | Medium — BoundingBox min<=max | 11.2 |
| Py-P4 | Python | Medium — min_length on string fields | 11.3 |
| Py-P5 | Python | Medium — resolver error context | 12.1 |
| Py-P6 | Python | Medium — ThreadingHTTPServer | 13.1 |
| Py-P7 | Python | Low — explicit kid None check | 10.2 |
| Py-P8 | Python | Low — self-loop detection | 13.2 |

---

## Notes

- This repo uses **automated semantic versioning via git-cliff** — do NOT manually bump versions
- **Commit type should be `feat(ts)!:`** (breaking change) — these are breaking type renames on exported interfaces. Per `cliff.toml` with `breaking_always_bump_major = false`, this triggers a minor bump (0.16.0 → 0.17.0). A `fix:` commit (patch bump) would misrepresent the semver impact
- TypeScript SDK conventions: typecheck `npx tsc --noEmit`, tests `npx vitest run`, build `npx tsup`
- Python SDK conventions: lint `poetry run ruff check`, tests `poetry run pytest -v`
- All Python robustness improvements (Phases 10-13) are additive — they add validation gates or improve error messages without changing wire format, API surface, or test behavior
- TS parity propagation (Phase 14) mirrors Python improvements to maintain source-of-truth alignment
