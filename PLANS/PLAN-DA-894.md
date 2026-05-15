# PLAN — DA-894: SDK: migrate format:"binary" → format:"file" for file input/output fields

**Branch:** `DA-894`
**Jira:** [DA-894](https://betekk.atlassian.net/browse/DA-894)
**Repo:** https://github.com/nus-cee/canvastekk-workflow-sdk
**Priority:** High
**Target Version:** `0.6.0` (minor bump from `0.5.0`)
**Effort:** ~0.5 day

---

## Context

DA-889 redesigned the file input pipeline to use symmetric presigned URLs. The new convention is `format: "file"` to signal "this field carries a file reference (presigned GET URL or CDS ref)" without triggering multipart handling in the engine.

All changes are **backward-compatible**. The `file_input_fields` and `file_output_fields` properties will detect both `"binary"` and `"file"` formats during the transition period.

### Dependencies

| Dependency | Ticket | Status | Impact on SDK |
| --- | --- | --- | --- |
| Engine file input pipeline redesign | DA-889 | To Do | Engine already handles both `format: "file"` and `format: "binary"` |
| Node: floor-flatness-app update | DA-895 | Backlog | Blocked by this ticket |

---

## Phase 1: Core Migration — definition.py

### 1.1 Update `file_input_fields` property
- [ ] Change docstring from `"format": "binary"` to `"format": "file"` in `definition.py:141`
- [ ] Update filter to match `"file"` instead of `"binary"` in `definition.py:145`

### 1.2 Update `file_output_fields` property
- [ ] Change docstring from `"format": "binary"` to `"format": "file"` in `definition.py:156`
- [ ] Update filter to match `"file"` instead of `"binary"` in `definition.py:160`

---

## Phase 2: Test Updates

### 2.1 Update test_definition.py
- [ ] Update docstring in test at line 138
- [ ] Update `"format": "binary"` → `"format": "file"` at lines 148, 150, 200, 235, 237

### 2.2 Update test_app.py
- [ ] Update `"format": "binary"` → `"format": "file"` at lines 55, 362, 389, 410, 416

---

## Phase 3: Documentation Updates

### 3.1 Update README.md
- [ ] Update references at lines 297, 309, 322, 374, 387, 393 to use `format: "file"`
- [ ] Update conceptual description to explain `"file"` means presigned URL / CDS ref

---

## Phase 4: Version Bump & Validation

### 4.1 Bump version
- [ ] Update `__version__` in `python/canvastekk_workflow_sdk/__init__.py` from `"0.5.0"` → `"0.6.0"`
- [ ] Update version in `python/pyproject.toml` if present

### 4.2 Run validation
- [ ] All existing tests pass: `cd python && python -m pytest`
- [ ] Ruff lint passes: `ruff check python/`
- [ ] Verify backward compatibility: tests with `"file"` format work identically to old `"binary"` tests

---

## Acceptance Criteria

- [ ] SDK node schemas use `format: "file"` instead of `format: "binary"`
- [ ] Existing nodes continue to work with engine's backward-compatible detection
- [ ] SDK version bumped to `0.6.0`
- [ ] All tests pass
- [ ] Ruff lint clean

---

## Modified Files

| File | Changes |
| --- | --- |
| `python/canvastekk_workflow_sdk/definition.py` | Update `file_input_fields` and `file_output_fields` to use `"file"` format |
| `python/canvastekk_workflow_sdk/__init__.py` | Bump `__version__` to `"0.6.0"` |
| `python/tests/test_definition.py` | Update format values in test schemas |
| `python/tests/test_app.py` | Update format values in test schemas |
| `python/README.md` | Update documentation to reflect `format: "file"` convention |
