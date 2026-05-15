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
BEFORE (format: "binary"):
  Engine → downloads file from S3 → multipart POST → SDK saves to /tmp → node.execute()
  
AFTER (format: "file"):
  Engine → resolves CDS/S3 refs → presigned GET URL in JSON → SDK passes through → node.execute()
  Node downloads from presigned URL itself. SDK does NOT auto-download.
```

### Dependencies

| Dependency | Ticket | Status | Impact on SDK |
| --- | --- | --- | --- |
| Engine file input pipeline redesign | DA-889 | PR #111 open | Engine handles both `format: "file"` and `format: "binary"` |
| Node: floor-flatness-app update | DA-895 | Backlog | Blocked by this ticket |

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
- [ ] Document that `format: "file"` means "this field may contain a presigned GET URL, an S3 URI, or a CDS reference object"

---

## Phase 6: Version Bump & Validation

### 6.1 Bump version
- [ ] Update `__version__` in `python/canvastekk_workflow_sdk/__init__.py` from `"0.5.0"` → `"0.6.0"`
- [ ] Update version in `python/pyproject.toml`

### 6.2 Run validation
- [ ] All existing tests pass: `cd python && python -m pytest`
- [ ] Ruff lint passes: `ruff check python/`
- [ ] Verify backward compatibility: nodes with `"binary"` format still detected correctly

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
