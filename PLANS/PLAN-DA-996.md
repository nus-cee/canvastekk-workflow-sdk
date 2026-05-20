# PLAN-DA-996: SDK Auto-Download Middleware for Presigned URL File Inputs

**Jira Ticket**: [DA-996](https://betekk.atlassian.net/browse/DA-996)
**Branch**: `DA-996`
**Repo**: `canvastekk-workflow-sdk`
**Priority**: P2
**Size**: M
**Status**: Planning

---

## Problem

Every node that receives file inputs must implement its own download logic for presigned GET URLs. This caused a bug in `floor-flatness-assessment` (DA-994) where `validate_file_input` was called on the raw URL string instead of a downloaded file. Nodes repeatedly reimplement the same download/validate boilerplate.

## Proposal

Add built-in file download middleware to the SDK that auto-downloads presigned URL inputs before calling `execute()`, replaces URL values with local file paths, preserves original URLs in `context.metadata`, and optionally validates downloaded files.

---

## Files to Change

| File | Change |
|------|--------|
| `python/canvastekk_workflow_sdk/middleware.py` | Add `FileDownloadMiddleware` class |
| `python/canvastekk_workflow_sdk/context.py` | Add `metadata` dict + `downloads_dir` property |
| `python/canvastekk_workflow_sdk/base.py` | Register `FileDownloadMiddleware` by default when node has file inputs; update `execute()` docstring |
| `python/canvastekk_workflow_sdk/definition.py` | Add `x-auto-validate` support in `validate_file_input` schema check |
| `python/tests/test_file_download_middleware.py` | New test file |
| `python/canvastekk_workflow_sdk/__init__.py` | Export `FileDownloadMiddleware` |

---

## Acceptance Criteria

- [ ] `FileDownloadMiddleware.on_before_execute()` auto-downloads presigned URL inputs to `context.downloads_dir`
- [ ] File input values in `inputs` dict are replaced with local file paths
- [ ] Original presigned URLs preserved in `context.metadata["{field_name}_original_url"]`
- [ ] When `x-auto-validate: true` is set on a field schema, `validate_file_input()` is called automatically after download
- [ ] Local file paths pass through unchanged (backward compatible)
- [ ] Download uses `httpx.stream()` with `timeout=30.0`, `follow_redirects=True`, `chunk_size=65536`
- [ ] Download errors raise `NodeIOError` with descriptive message
- [ ] `ExecutionContext` gains `metadata` dict and `downloads_dir` property
- [ ] `BaseNode.run()` registers `FileDownloadMiddleware` when `definition.has_file_inputs` is true
- [ ] All existing tests pass
- [ ] New unit tests cover: URL download, local path passthrough, auto-validate, error cases
- [ ] Ruff lint passes
- [ ] `docs/EXTERNAL-AUTHOR-GUIDE.md` updated to mention auto-download behavior

---

## Implementation Phases

### Phase 1: Add `metadata` and `downloads_dir` to `ExecutionContext`

- [ ] Add `_metadata: dict[str, Any]` to `ExecutionContext.__init__()`
- [ ] Add `metadata` property (returns the dict)
- [ ] Add `downloads_dir` property that returns `self._output_dir / "downloads"` and creates it lazily

### Phase 2: Implement `FileDownloadMiddleware`

- [ ] Create `FileDownloadMiddleware` class implementing `NodeMiddleware` protocol
- [ ] `on_before_execute()`: iterate `definition.file_input_fields`, detect URL strings (`http://` or `https://`), download to `context.downloads_dir / filename`
- [ ] Extract filename from `Content-Disposition` header or URL path
- [ ] Replace `inputs[field_name]` with `str(local_path)`
- [ ] Store original URL in `context.metadata[f"{field_name}_original_url"]`
- [ ] If field schema has `x-auto-validate: true`, call `self._definition.validate_file_input(field_name, local_path)`
- [ ] Raise `NodeIOError` on download failure (network, timeout, HTTP error)
- [ ] Skip fields where value is already a local path (not starting with `http`)

### Phase 3: Wire into `BaseNode.run()`

- [ ] In `BaseNode.__init__()`, check `self.definition.has_file_inputs` and register `FileDownloadMiddleware` if true
- [ ] Update `execute()` docstring to note file inputs may be local paths when auto-download is active
- [ ] Export `FileDownloadMiddleware` from `__init__.py`

### Phase 4: Tests

- [ ] Test: URL input is downloaded and replaced with local path
- [ ] Test: original URL stored in `context.metadata`
- [ ] Test: local path input passes through unchanged
- [ ] Test: `x-auto-validate: true` triggers `validate_file_input()`
- [ ] Test: download failure raises `NodeIOError`
- [ ] Test: multiple file inputs all processed
- [ ] Test: non-file inputs untouched

### Phase 5: Documentation & Lint

- [ ] Update `execute()` docstring in `base.py`
- [ ] Update `docs/EXTERNAL-AUTHOR-GUIDE.md` to mention auto-download
- [ ] Run `poetry run ruff check canvastekk_workflow_sdk/ tests/`
- [ ] Run `poetry run pytest -v`

---

## Dependencies

- **DA-994**: floor-flatness-assessment bug (motivation for this ticket)
- **DA-995**: engine S3 key extensions (related but not blocking)

## Risks & Mitigation

| Risk | Mitigation |
|------|-----------|
| Breaking existing nodes that download manually | Local paths pass through unchanged — fully backward compatible |
| Large file downloads timeout | Configurable timeout (default 30s), streaming chunks |
| Filename collisions in `downloads_dir` | Prefix with field name to avoid overwrites |
| Memory pressure from many concurrent downloads | Each download streams to disk, not memory |
