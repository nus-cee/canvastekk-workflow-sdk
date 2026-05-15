# PLAN — DA-894: SDK: migrate format:"binary" → format:"file" for file input/output fields

**Branch:** `DA-894`
**Jira:** [DA-894](https://betekk.atlassian.net/browse/DA-894)
**Repo:** https://github.com/nus-cee/canvastekk-workflow-sdk
**Priority:** High
**Target Version:** `0.6.0` (minor bump from `0.5.0`, breaking change)
**Effort:** ~1.5 days
**Breaking Change:** `format: "binary"` is fully removed. All nodes must migrate to `format: "file"`.

---

## Context

DA-889 redesigned the file input pipeline to use symmetric presigned URLs. The new convention is `format: "file"` to signal "this field carries a file reference (presigned GET URL)" without triggering multipart handling in the engine.

This is a **breaking change**. Since the SDK is not yet deployed in production, we are taking a clean break — no backward compatibility with `format: "binary"`. All nodes must update their schemas when adopting this SDK version.

### Release Coordination

This is a **coordinated cross-repo release** (per DA-889 design decisions). Engine, SDK, and nodes all ship together. Since nothing is in production yet, there is no need for a phased migration or dual detection. The engine (DA-889) will also stop accepting `format: "binary"` in the same release.

### End-to-End File Flow

**All file inputs go through CDS.** Browser uploads go to CDS (not the engine's temp bucket). The engine resolves CDS references to presigned GET URLs before sending to nodes.

### Full Workflow Diagram

```
╔══════════════════════════════════════════════════════════════════════════════════╗
║                         FLOOR FLATNESS WORKFLOW — DA-889/DA-894                ║
╚══════════════════════════════════════════════════════════════════════════════════╝

 ┌──────────┐       ┌──────────┐       ┌──────────────────────────────┐
 │ Frontend │       │   CDS    │       │      Keycloak                │
 │ (Next.js)│       │ (Defect  │       │   (Auth + Service Acct)      │
 │          │       │  Service)│       │                              │
 └────┬─────┘       └────┬─────┘       └──────────────┬───────────────┘
      │                  │                            │
      │  1. Upload LAS   │                            │
      │  POST /api/proj/{id}/reports/{rid}/files      │
      │ ───────────────► │                            │
      │                  │ stores in permanent S3     │
      │  { file_id: 789} │                            │
      │ ◄─────────────── │                            │
      │                  │                            │
      │  2. Start workflow                            │
      │  POST /api/runs                               │
      │  {                                            │
      │    workflow_id: "floor-flatness-app",         │
      │    project_id: 123,                           │
      │    inputs: {                                  │
      │      "ff-1": { pcd_path:                     │
      │        { source:"cds", file_id:"789" }        │
      │      },                                       │
      │      "pub-1": { project_id: 123 }             │
      │    }                                          │
      │  }                                            │
      │ ──────────────────────────────────────────────┼──────────►
      │                                               │   Engine
      │  { run_id, status: "running" }                │   (FastAPI +
      │ ◄──────────────────────────────────────────── │    Temporal)
      │                                               │
      │                                               │
      │         ══════════ INSIDE ENGINE ══════════   │
      │                                               │
      │         3. run_service.create_run()            │
      │            ├─ Load workflow def from DB        │
      │            ├─ Deep-merge: schema defaults      │
      │            │  ← workflow defaults              │
      │            │  ← user overrides                 │
      │            ├─ Validate merged inputs           │
      │            │  (skip format:"file" fields)      │
      │            ├─ Create workflow_runs DB row       │
      │            └─ Trigger Temporal DAGWorkflow     │
      │                                               │
      │         4. Temporal Activity (ff-1)            │
      │            ├─ Detect: pcd_path =               │
      │            │  { source:"cds", file_id:"789" }  │
      │            ├─ Mint service-account JWT ────────┼──────────►│
      │            ├─ GET CDS /api/proj/123/reports/   │ ◄──────────┘
      │            │  456/files/789                     │
      │            ├─ Download from CDS presigned URL  │
      │            ├─ Upload to temp S3 bucket:        │
      │            │  runs/{run_id}/ff-1/pcd_path      │
      │            └─ Generate presigned GET URL ──┐   │
      │                                           │   │
      │                                           │   │
      │         ════════ TO NODE (ff-1) ════════  │   │
      │                                           │   │
      │         5. JSON POST to node /execute     │   │
      │            {                               │   │
      │              "run_id": "run-abc",          │   │
      │              "node_id": "ff-1",            │   │
      │              "inputs": {                   │   │
      │                "pcd_path":                 │   │
      │         ┌───   "https://s3.../presigned-GET-URL", ◄─┘
      │         │      "distance_threshold": 10.0   │
      │         │    },                             │
      │         │    "output_upload_url": {         │
      │         │      "report_bundle_zip":        │
      │         │        "https://s3.../presigned-PUT-URL"
      │         │    }                             │
      │         │  }                               │
      │         │                                  │
      │         ▼                                  │
      │  ┌──────────────────────────────────────┐  │
      │  │  SDK (DA-894 — canvastekk-workflow-sdk) │
      │  │                                      │  │
      │  │  NodeDefinition model_validator:     │  │
      │  │  ├─ ✅ format:"file" → allowed       │  │
      │  │  ├─ ❌ format:"binary" → ValueError  │  │
      │  │  └─ ❌ type != "string" → ValueError │  │
      │  │                                      │  │
      │  │  /execute endpoint:                  │  │
      │  │  ├─ JSON body only (no multipart)    │  │
      │  │  ├─ Parse NodeExecutionRequest       │  │
      │  │  ├─ Validate inputs (Draft7Validator)│  │
      │  │  ├─ asyncio.to_thread(node.run)      │  │
      │  │  └─ Upload outputs via presigned PUT │  │
      │  └──────────────┬───────────────────────┘  │
      │                 │                            │
      │                 ▼                            │
      │  ┌──────────────────────────────────────┐  │
      │  │  Node (DA-895 — floor-flatness-app)  │  │
      │  │                                      │  │
      │  │  execute(inputs, context):           │  │
      │  │  ├─ url = inputs["pcd_path"]         │  │
      │  │  ├─ httpx.get(url) → download LAS   │  │
      │  │  ├─ validate_file_input("pcd_path",  │  │
      │  │  │     local_path)  # x-accept,     │  │
      │  │  │                   x-maxSizeBytes  │  │
      │  │  ├─ Process point cloud             │  │
      │  │  ├─ Write report ZIP to             │  │
      │  │  │  context.output_path("report.zip")│  │
      │  │  └─ return {                        │  │
      │  │       "report_bundle_zip": "/tmp/..."│  │
      │  │     }                               │  │
      │  └──────────────┬───────────────────────┘  │
      │                 │                            │
      │                 ▼                            │
      │         SDK auto-uploads:                     │
      │         PUT presigned-PUT-URL ← /tmp/report.zip
      │                                               │
      │         ════════ EDGE PROPAGATION ════════    │
      │                                               │
      │         6. Engine replaces output:             │
      │            /tmp/... → s3://temp-bucket/        │
      │            runs/{run_id}/ff-1/report_bundle_zip│
      │                                               │
      │         7. Temporal Activity (pub-1)           │
      │            ├─ Read edge: ff-1.report_bundle_zip│
      │            │  → pub-1.report_zip               │
      │            ├─ Generate presigned GET URL        │
      │            ├─ Inject project_id from            │
      │            │  _request_context                  │
      │            └─ JSON POST to publisher /execute   │
      │                                               │
      │         ════════ TO NODE (pub-1) ══════════   │
      │                                               │
      │  ┌──────────────────────────────────────┐  │
      │  │  Publisher (DA-893 — project-file-   │  │
      │  │            publisher)                │  │
      │  │                                      │  │
      │  │  execute(inputs, context):           │  │
      │  │  ├─ url = inputs["report_zip"]       │  │
      │  │  ├─ httpx.get(url) → download ZIP   │  │
      │  │  ├─ Mint own service-account JWT     │  │
      │  │  ├─ POST ZIP to CDS                  │  │
      │  │  │  /api/projects/123/files          │  │
      │  │  └─ return {                        │  │
      │  │       "published_file_id": 42,       │  │
      │  │       "published_files_path": "..."  │  │
      │  │     }                               │  │
      │  └──────────────────────────────────────┘  │
      │                                               │
      │         ════════ COMPLETION ═══════════════   │
      │                                               │
      │         8. update_run_status activity          │
      │            ├─ DB: status="completed"           │
      │            ├─ DB: result={ published_file_id } │
      │            └─ cleanup_run_files()              │
      │               DELETE runs/{run_id}/** from     │
      │               temp bucket only                 │
      │               (CDS permanent files survive)    │
      │                                               │
      │         9. Frontend polls                      │
      │            GET /api/runs/{run_id}               │
      │            → { status: "completed",             │
      │                result: { published_file_id: 42 }}
      │ ◄──────────────────────────────────────────── │
      │                                               │


 ╔══════════════════════════════════════════════════════════════════════════════╗
 ║  MANIFEST FORMAT ENFORCEMENT (SDK 0.6.0)                                    ║
 ╠══════════════════════════════════════════════════════════════════════════════╣
 ║                                                                              ║
 ║  pip install canvastekk-workflow-sdk==0.6.0                                   ║
 ║         │                                                                    ║
 ║         ▼                                                                    ║
 ║  ┌─────────────────────────────────────────┐                                 ║
 ║  │  NodeDefinition (Pydantic model)         │                                ║
 ║  │                                          │                                ║
 ║  │  @model_validator(mode="after")          │                                ║
 ║  │  def _validate_file_field_formats():     │                                ║
 ║  │    for each field in input/output_schema:│                                ║
 ║  │      ├─ format:"file" + type:"string"   │──── ✅ PASS                    ║
 ║  │      ├─ format:"binary"                  │──── ❌ ValueError:             ║
 ║  │      │                                    │      "use format:\"file\""     ║
 ║  │      └─ format:"file" + type:"object"   │──── ❌ ValueError:             ║
 ║  │                                           │      "must be type:\"string\"" ║
 ║  └─────────────────────────────────────────┘                                 ║
 ║         │                                                                    ║
 ║         ▼  (passes validation)                                                ║
 ║  ┌─────────────────────────────────────────┐                                 ║
 ║  │  GET /manifest → JSON response           │                                ║
 ║  │  {                                       │                                ║
 ║  │    "name": "floor-flatness-assessment",  │                                ║
 ║  │    "version": "1.0.0",                   │                                ║
 ║  │    "input_schema": {                     │                                ║
 ║  │      "properties": {                     │                                ║
 ║  │        "pcd_path": {                     │                                ║
 ║  │          "type": "string",               │                                ║
 ║  │          "format": "file",  ◄────────────┼── SDK guarantees this          ║
 ║  │          "x-accept": [".las",".laz"],    │                                ║
 ║  │          "x-maxSizeBytes": 500000000     │                                ║
 ║  │        }                                 │                                ║
 ║  │      }                                   │                                ║
 ║  │    },                                    │                                ║
 ║  │    "output_schema": {                    │                                ║
 ║  │      "properties": {                     │                                ║
 ║  │        "report_bundle_zip": {            │                                ║
 ║  │          "type": "string",               │                                ║
 ║  │          "format": "file"  ◄─────────────┼── and this                     ║
 ║  │        }                                 │                                ║
 ║  │      }                                   │                                ║
 ║  │    }                                     │                                ║
 ║  │  }                                       │                                ║
 ║  └─────────────────────────────────────────┘                                 ║
 ║         │                                                                    ║
 ║         ▼                                                                    ║
 ║  ┌─────────────────────────────────────────┐                                 ║
 ║  │  Engine reads /manifest                  │                                ║
 ║  │  ├─ Stores in node_registry DB           │                                ║
 ║  │  ├─ Detects format:"file" fields         │                                ║
 ║  │  ├─ Skips validation for file inputs     │                                ║
 ║  │  │  (accepts CDS refs + S3 URIs)        │                                ║
 ║  │  └─ Generates presigned GET/PUT URLs     │                                ║
 ║  └─────────────────────────────────────────┘                                 ║
 ║                                                                              ║
 ╚══════════════════════════════════════════════════════════════════════════════╝
```

### Dependencies

| Dependency | Ticket | Status | Impact on SDK |
| --- | --- | --- | --- |
| Engine file input pipeline redesign | DA-889 | PR #111 open | Engine stops accepting `format: "binary"` in same release |
| Node: floor-flatness-app update | DA-895 | Backlog | Blocked by this ticket — must migrate to `format: "file"` |
| Publisher node (project-file-publisher) | DA-893 | Backlog | Must migrate to `format: "file"` |

---

## Phase 1: Format Migration — definition.py

### 1.1 Update `file_input_fields` property
- [ ] Change filter from `== "binary"` to `== "file"` in `definition.py:145`
- [ ] Update docstring: `format: "file"` only

### 1.2 Update `file_output_fields` property
- [ ] Change filter from `== "binary"` to `== "file"` in `definition.py:160`
- [ ] Update docstring: `format: "file"` only

---

## Phase 2: Remove Multipart Handling — app.py

### 2.1 Remove multipart code path
- [ ] Remove multipart/form-data branch from execute() (lines 202-247)
- [ ] Simplify execute() to JSON-only: `body = await request.json(); exec_request = NodeExecutionRequest(**body)`
- [ ] Remove `_coerce_form_value()` helper (lines 38-56)
- [ ] Remove unused imports: `tempfile`, `starlette.datastructures.UploadFile`
- [ ] Update execute() docstring: remove multipart references, document JSON-only + presigned URL flow
- [ ] Update OpenAPI `description` on /execute: "Execute the node with given inputs via JSON body"

### 2.2 Remove python-multipart dependency
- [ ] Remove `python-multipart` from `pyproject.toml` dependencies
- [ ] Remove from README.md Runtime Dependencies table (if listed)

---

## Phase 3: Add File Field Validation Helper + Update Docstrings

### 3.1 Add `validate_file_input()` helper to definition.py
- [ ] Add method to `NodeDefinition` that validates a downloaded file against `x-*` extensions on its schema
- [ ] Support `x-accept` (allowed extensions), `x-maxSizeBytes` (max file size)
- [ ] Node authors call this in `execute()` after downloading

### 3.2 Promote `httpx` to runtime dependency
- [ ] Move `httpx` from `[tool.poetry.group.dev.dependencies]` to `[tool.poetry.dependencies]` in `pyproject.toml`
- [ ] `httpx` is already used by FastAPI's `TestClient` and is a de facto standard HTTP client for FastAPI projects
- [ ] Replace `urllib.request` usage in `uploads.py` and `registry.py` with `httpx` for consistency
- [ ] Document `httpx` as the recommended download client in README examples

### 3.3 Update docstrings
- [ ] `base.py` execute() docstring: change "File inputs may be local paths (downloaded by SDK) or URLs" to "File inputs are presigned GET URLs provided by the engine"
- [ ] `request.py` inputs field description is already correct ("may include signed URLs for file access")

### 3.4 Add manifest validation — `NodeDefinition.model_validator`
- [ ] Add Pydantic `@model_validator(mode="after")` to `NodeDefinition` that checks `input_schema` and `output_schema` for file field format correctness
- [ ] Reject `format: "binary"` at node definition time — raise `ValueError` if any property uses it, with message pointing to `format: "file"` migration
- [ ] Validate that file fields have `type: "string"` (not `"object"` or `"array"`)
- [ ] This means `NodeDefinition(input_schema={"properties": {"x": {"format": "binary"}}})` will **fail at import time**, not at runtime — node authors discover the error immediately when starting their app
- [ ] The SDK version itself is the contract: `pip install canvastekk-workflow-sdk==0.6.0` guarantees `format: "file"` enforcement

### 3.5 File field schema conventions (document in README)
- [ ] Document the `x-*` extension convention for file fields in JSON Schema
- [ ] `x-accept`: list of allowed file extensions (e.g. `[".las", ".laz", ".ply"]`) — used by frontend for file picker + node for runtime validation
- [ ] `x-maxSizeBytes`: maximum file size in bytes — validated by node at runtime after download
- [ ] `x-description`: longer description for frontend tooltip (optional, separate from `description`)
- [ ] These are custom extensions on top of JSON Schema Draft-07; the `Draft7Validator` ignores unknown keys

---

## Phase 4: Test Updates

### 4.1 Remove multipart tests
- [ ] Remove `TestMultipartExecuteEndpoint` class (~3 tests)
- [ ] Remove `TestCoerceFormValue` class (~7 tests)
- [ ] Remove `test_multipart_output_upload_url_parsed_from_json`
- [ ] Remove `test_multipart_with_async_wrapper_and_s3_upload`
- [ ] Remove `FileInOutNode` test fixture (only used for multipart tests)

### 4.2 Update format values in remaining tests
- [ ] Update `"format": "binary"` → `"format": "file"` in test_definition.py
- [ ] Update `"format": "binary"` → `"format": "file"` in test_app.py remaining tests

### 4.3 Add new tests
- [ ] Test: `file_input_fields` detects `"file"` format fields only
- [ ] Test: `file_output_fields` detects `"file"` format fields only
- [ ] Test: `file_input_fields` does NOT detect `"binary"` format fields (confirms breaking change)
- [ ] Test: `NodeDefinition` raises `ValueError` when `format: "binary"` is used in schema
- [ ] Test: `NodeDefinition` raises `ValueError` when file field has wrong type (not `"string"`)
- [ ] Test: `to_dict()` manifest output contains `format: "file"` for file fields
- [ ] Test: `/manifest` endpoint returns correct format
- [ ] Test: execute with presigned URL input for `format: "file"` field passes validation
- [ ] Test: JSON-only /execute endpoint works with presigned URL passthrough
- [ ] Test: `validate_file_input()` rejects file exceeding `x-maxSizeBytes`
- [ ] Test: `validate_file_input()` rejects file with wrong extension per `x-accept`
- [ ] Test: `validate_file_input()` passes valid file

---

## Phase 5: Documentation Updates — README.md

### 5.1 Rewrite File Handling Guide
- [ ] Replace `format: "binary"` → `format: "file"` in all examples
- [ ] Remove "Receiving Files via Multipart/Form-Data" section and curl multipart examples
- [ ] Add presigned URL flow documentation: engine sends presigned GET URL in JSON, node downloads itself
- [ ] Update "S3 Output Upload" section: remove multipart-specific `output_upload_url` JSON string instructions
- [ ] Update curl examples to use JSON POST only
- [ ] Document that `format: "file"` means "this field receives a presigned GET URL from the engine" — all file inputs are CDS-sourced, the engine resolves references before the node sees them
- [ ] Add section on `x-*` file field extensions with examples
- [ ] Add full node definition example showing file fields with conditions

### 5.2 Add download example
- [ ] Show how to download from presigned URL using `httpx` (promoted to runtime dep — async, timeout, redirect support)
- [ ] Show `validate_file_input()` usage after download

---

## Phase 6: Version Bump & Validation

### 6.1 Bump version
- [ ] Update `__version__` in `python/canvastekk_workflow_sdk/__init__.py` from `"0.5.0"` → `"0.6.0"`
- [ ] Update version in `python/pyproject.toml`

### 6.2 Run validation
- [ ] All existing tests pass: `cd python && python -m pytest`
- [ ] Ruff lint passes: `ruff check python/`
- [ ] Verify `format: "file"` fields are detected correctly (no `"binary"` fallback)
- [ ] Verify `export_definition()` passes through `format: "file"` in schemas unchanged (no transformation needed — it serializes input_schema/output_schema as-is)
- [ ] Verify `/manifest` endpoint returns schemas with `format: "file"` — engine reads these to determine file fields for presigned URL generation

---

## Acceptance Criteria

- [ ] SDK uses `format: "file"` only — `format: "binary"` is fully removed
- [ ] `file_input_fields` / `file_output_fields` detect `"file"` format only (breaking change)
- [ ] `NodeDefinition` rejects `format: "binary"` at definition time via Pydantic validator — node authors see the error on app startup
- [ ] SDK version (`0.6.0`) is the manifest format contract — `pip install canvastekk-workflow-sdk==0.6.0` enforces `format: "file"`
- [ ] `validate_file_input()` helper validates file constraints from `x-*` extensions
- [ ] Multipart handling removed from app.py — JSON-only `/execute`
- [ ] `python-multipart` dependency removed
- [ ] `httpx` promoted to runtime dependency, replaces `urllib.request` in uploads/registry
- [ ] Presigned URL inputs pass JSON Schema validation (Draft7Validator)
- [ ] SDK version bumped to `0.6.0`
- [ ] All tests pass (multipart tests removed, new presigned URL + file validation tests added)
- [ ] Ruff lint clean
- [ ] README reflects JSON-only, presigned URL file handling
- [ ] README documents `x-*` file field extensions and download patterns
- [ ] `export_definition()` and `/manifest` correctly expose `format: "file"` schemas for engine consumption

---

## Reference Documents

| Document | Relevance |
| --- | --- |
| `target-workflow-reference.md` | Target end-to-end workflow design — Steps 2-4 define the file pipeline contract |
| `README-CWE.md` | Engine implementation reference — describes presigned URL file transfer pattern |
| DA-889 Jira description | Cross-repo scope and design decisions for the file pipeline redesign |
| DA-889 Engine PR #111 | Engine implementation of CDS resolution + presigned URL delivery |

---

## Modified Files

| File | Changes |
| --- | --- |
| `python/canvastekk_workflow_sdk/definition.py` | Hard switch to `format: "file"`, add `validate_file_input()` helper, updated docstrings |
| `python/canvastekk_workflow_sdk/app.py` | Remove multipart handling, remove `_coerce_form_value`, remove dead imports |
| `python/canvastekk_workflow_sdk/base.py` | Update execute() docstring for presigned URL flow |
| `python/canvastekk_workflow_sdk/uploads.py` | Replace `urllib.request` with `httpx` |
| `python/canvastekk_workflow_sdk/registry.py` | Replace `urllib.request` with `httpx` |
| `python/canvastekk_workflow_sdk/__init__.py` | Bump `__version__` to `"0.6.0"` |
| `python/pyproject.toml` | Bump version, remove `python-multipart`, promote `httpx` to runtime dep |
| `python/tests/test_definition.py` | Update format values, add file validation tests |
| `python/tests/test_app.py` | Remove multipart tests, update format values, add presigned URL tests |
| `python/README.md` | Rewrite File Handling Guide, add `x-*` extensions docs, `httpx` download examples |
