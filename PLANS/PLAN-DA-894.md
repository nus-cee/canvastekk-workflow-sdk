# PLAN — DA-894: SDK: migrate format:"binary" → format:"file" for file input/output fields

**Branch:** `DA-894`
**Jira:** [DA-894](https://betekk.atlassian.net/browse/DA-894)
**Repo:** https://github.com/nus-cee/canvastekk-workflow-sdk
**Priority:** High
**Target Version:** `0.6.0` (minor bump from `0.5.0`)
**Effort:** ~1.5 days

---

## Context

DA-889 redesigned the file input pipeline to use symmetric presigned URLs. The new convention is `format: "file"` to signal "this field carries a file reference (presigned GET URL or CDS ref)" without triggering multipart handling in the engine.

All changes are **backward-compatible**. The `file_input_fields` and `file_output_fields` properties detect both `"binary"` (legacy) and `"file"` formats during the transition period. Multipart handling is removed since the engine now sends JSON-only payloads with presigned URLs.

### Architecture Shift

```
BEFORE (format: "binary" — target-workflow-reference.md Step 3):
  Engine → downloads file from S3 → multipart POST → SDK saves UploadFile to /tmp → node.execute()
  
AFTER (format: "file" — DA-889 presigned URL pipeline):
  Engine → resolves CDS/S3 refs → generates presigned GET URL → JSON POST → SDK passes through → node.execute()
  Node downloads from presigned URL itself. SDK does NOT auto-download.
```

### Release Coordination

This is a **coordinated cross-repo release** (per DA-889 design decisions). Engine, SDK, and nodes all ship together — no phased migration. The engine (DA-889) already handles both `format: "file"` and `format: "binary"` in its validation and activities. The SDK's dual detection ensures nodes that haven't migrated their schemas yet still work correctly.

### End-to-End File Flow

**All file inputs go through CDS.** Browser uploads go to CDS (not the engine's temp bucket). The engine resolves CDS references to presigned GET URLs before sending to nodes.

```
FE uploads file to CDS
  → POST /api/projects/{projectId}/reports/{reportId}/files
  → CDS stores file, returns { file_id }
  → FE sends { source: "cds", file_id: "789" } in POST /api/runs
                         │
                         ▼
              Engine (DA-889):
              1. run_service: relax validation for format:"file" fields
              2. Temporal activity: call CDS API → download → upload to temp bucket
              3. Generate presigned GET URL for temp bucket object
              4. JSON POST to node /execute with presigned URL in inputs[field]
                         │
                         ▼
              SDK (DA-894 — THIS TICKET):
              5. JSON-only /execute (no multipart)
              6. Pass presigned URL through to node.execute()
                         │
                         ▼
              Node (DA-895):
              7. Node downloads from presigned URL
              8. Processes and writes outputs
              9. SDK uploads outputs via presigned PUT URL to temp bucket
```

### Dependencies

| Dependency | Ticket | Status | Impact on SDK |
| --- | --- | --- | --- |
| Engine file input pipeline redesign | DA-889 | PR #111 open | Engine handles both `format: "file"` and `format: "binary"` |
| Node: floor-flatness-app update | DA-895 | Backlog | Blocked by this ticket |
| Publisher node (project-file-publisher) | DA-893 | Backlog | Uses SDK, needs format migration |

---

## Phase 1: Backward-Compatible Format Detection — definition.py

### 1.1 Update `file_input_fields` property
- [ ] Update filter to detect BOTH `"file"` and `"binary"` in `definition.py:145`
- [ ] Update docstring: mention both formats, note `"binary"` as legacy

### 1.2 Update `file_output_fields` property
- [ ] Update filter to detect BOTH `"file"` and `"binary"` in `definition.py:160`
- [ ] Update docstring: mention both formats, note `"binary"` as legacy

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

## Phase 3: Update Docstrings and Contracts

### 3.1 Update base.py docstrings
- [ ] `base.py` execute() docstring: change "File inputs may be local paths (downloaded by SDK) or URLs" to "File inputs are presigned GET URLs provided by the engine"
- [ ] `request.py` inputs field description is already correct ("may include signed URLs for file access")

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
- [ ] Test: `file_input_fields` detects both `"file"` and `"binary"` format fields
- [ ] Test: `file_output_fields` detects both `"file"` and `"binary"` format fields
- [ ] Test: execute with presigned URL input for `format: "file"` field passes validation
- [ ] Test: JSON-only /execute endpoint works with presigned URL passthrough

---

## Phase 5: Documentation Updates — README.md

### 5.1 Rewrite File Handling Guide
- [ ] Replace `format: "binary"` → `format: "file"` in all examples
- [ ] Remove "Receiving Files via Multipart/Form-Data" section and curl multipart examples
- [ ] Add presigned URL flow documentation: engine sends presigned GET URL in JSON, node downloads itself
- [ ] Update "S3 Output Upload" section: remove multipart-specific `output_upload_url` JSON string instructions
- [ ] Update curl examples to use JSON POST only
- [ ] Document that `format: "file"` means "this field receives a presigned GET URL from the engine" — all file inputs are CDS-sourced, the engine resolves references before the node sees them

---

## Phase 6: Version Bump & Validation

### 6.1 Bump version
- [ ] Update `__version__` in `python/canvastekk_workflow_sdk/__init__.py` from `"0.5.0"` → `"0.6.0"`
- [ ] Update version in `python/pyproject.toml`

### 6.2 Run validation
- [ ] All existing tests pass: `cd python && python -m pytest`
- [ ] Ruff lint passes: `ruff check python/`
- [ ] Verify backward compatibility: nodes with `"binary"` format still detected correctly
- [ ] Verify `export_definition()` passes through `format: "file"` in schemas unchanged (no transformation needed — it serializes input_schema/output_schema as-is)
- [ ] Verify `/manifest` endpoint returns schemas with `format: "file"` — engine reads these to determine file fields for presigned URL generation

---

## Acceptance Criteria

- [ ] SDK node schemas use `format: "file"` as primary convention
- [ ] `file_input_fields` / `file_output_fields` detect both `"file"` and `"binary"` (backward compat)
- [ ] Multipart handling removed from app.py — JSON-only `/execute`
- [ ] `python-multipart` dependency removed
- [ ] Existing nodes with `format: "binary"` still work (dual detection)
- [ ] Presigned URL inputs pass JSON Schema validation (Draft7Validator)
- [ ] SDK version bumped to `0.6.0`
- [ ] All tests pass (multipart tests removed, new presigned URL tests added)
- [ ] Ruff lint clean
- [ ] README reflects JSON-only, presigned URL file handling
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
| `python/canvastekk_workflow_sdk/definition.py` | Dual format detection (`"file"` + `"binary"`), updated docstrings |
| `python/canvastekk_workflow_sdk/app.py` | Remove multipart handling, remove `_coerce_form_value`, remove dead imports |
| `python/canvastekk_workflow_sdk/base.py` | Update execute() docstring for presigned URL flow |
| `python/canvastekk_workflow_sdk/__init__.py` | Bump `__version__` to `"0.6.0"` |
| `python/pyproject.toml` | Bump version, remove `python-multipart` dependency |
| `python/tests/test_definition.py` | Update format values, add dual-detection tests |
| `python/tests/test_app.py` | Remove multipart tests, update format values, add presigned URL tests |
| `python/README.md` | Rewrite File Handling Guide for presigned URL flow |
