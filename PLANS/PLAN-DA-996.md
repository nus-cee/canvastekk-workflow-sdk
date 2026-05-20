# PLAN-DA-996: SDK Auto-Download Pipeline for Presigned URL File Inputs

**Jira Ticket**: [DA-996](https://betekk.atlassian.net/browse/DA-996)
**Branch**: `DA-996`
**Repo**: `canvastekk-workflow-sdk`
**Priority**: P2
**Size**: M
**Status**: In Progress

---

## Problem

Every node that receives file inputs must implement its own download logic for presigned GET URLs. This caused a bug in `floor-flatness-assessment` (DA-994) where `validate_file_input` was called on the raw URL string instead of a downloaded file. Nodes repeatedly reimplement the same download/validate boilerplate.

## Proposal

Add a built-in file download pipeline step in `BaseNode.run()` that auto-downloads presigned URL inputs before calling `execute()`, replaces URL values with local file paths, preserves original URLs in `context.metadata`, and validates downloaded files automatically.

**Architecture decision**: This is a built-in pipeline step in `run()`, NOT a `NodeMiddleware`. The `NodeMiddleware` protocol doesn't pass `NodeDefinition`, and auto-download is core SDK infrastructure, not a user-extensible hook.

---

## Files to Change

| File | Change |
|------|--------|
| `python/canvastekk_workflow_sdk/context.py` | Add `metadata` dict + `downloads_dir` property |
| `python/canvastekk_workflow_sdk/base.py` | Add `_prepare_file_inputs()` method; wire into `run()` as pipeline step; update docstrings |
| `python/tests/test_file_download.py` | New test file |
| `python/canvastekk_workflow_sdk/__init__.py` | Bump version |

---

## Acceptance Criteria

- [ ] `_prepare_file_inputs()` auto-downloads presigned URL inputs to `context.downloads_dir`
- [ ] File input values in `inputs` dict are replaced with local file paths
- [ ] Original presigned URLs preserved in `context.metadata[field_name]` dict (with `original_url`, `local_path`, `size_bytes`)
- [ ] Downloaded files auto-validated with `validate_file_input()` (always, not opt-in)
- [ ] Local file paths pass through unchanged (backward compatible)
- [ ] Download uses `httpx.stream()` with `timeout=30.0`, `follow_redirects=True`, `chunk_size=65536`
- [ ] Download errors raise `NodeIOError` with descriptive message
- [ ] `ExecutionContext` gains `metadata` dict and `downloads_dir` property
- [ ] `request.inputs` is NOT mutated — `run()` copies inputs before modification
- [ ] Optional file fields (`None` / missing) handled gracefully
- [ ] Filenames sanitized against path traversal (`Path(name).name`)
- [ ] Only `https://` and `http://` URLs trigger download; non-string values skipped
- [ ] Partial download failures cleaned up
- [ ] Field name prefixed filenames prevent collisions (`{field_name}_{filename}`)
- [ ] All existing tests pass
- [ ] Ruff lint passes

---

## Implementation Phases

### Phase 1: Add `metadata` and `downloads_dir` to `ExecutionContext`

- [ ] Add `_metadata: dict[str, Any]` to `ExecutionContext.__init__()`
- [ ] Add `metadata` property (returns the dict)
- [ ] Add `downloads_dir` property that returns `self._output_dir / "downloads"` and creates it lazily

### Phase 2: Implement `_prepare_file_inputs()` in `BaseNode`

- [ ] Add `_prepare_file_inputs(inputs, context)` method to `BaseNode`
- [ ] Iterate `self.definition.file_input_fields`, skip `None` / missing / non-string values
- [ ] Detect URL strings (`http://` or `https://`), skip local paths
- [ ] Download to `context.downloads_dir / f"{field_name}_{sanitized_filename}"`
- [ ] Extract filename from `Content-Disposition` header, fallback to URL path
- [ ] Sanitize filename: `Path(filename).name` to strip directory components
- [ ] Replace `inputs[field_name]` with `str(local_path)`
- [ ] Store metadata in `context.metadata[field_name]` with `original_url`, `local_path`, `size_bytes`
- [ ] Call `self.definition.validate_file_input(field_name, local_path)` after download
- [ ] Raise `NodeIOError` on download failure with cleanup of partial downloads
- [ ] Report progress with `context.report_progress()`

### Phase 3: Wire into `BaseNode.run()`

- [ ] Copy inputs: `inputs = dict(request.inputs)` before any modification
- [ ] Add pipeline step after context creation, before middleware:
  ```
  if self.definition.has_file_inputs:
      inputs = self._prepare_file_inputs(inputs, context)
  ```
- [ ] Update `execute()` docstring to note file inputs may be local paths

### Phase 4: Tests

- [ ] URL input downloaded and replaced with local path
- [ ] Original URL stored in `context.metadata`
- [ ] Local path input passes through unchanged
- [ ] Optional file field with `None` skipped
- [ ] Optional file field missing from inputs — no crash
- [ ] Empty string file input skipped
- [ ] Non-file string input (URL-like) not downloaded
- [ ] Download HTTP error raises `NodeIOError`
- [ ] Download timeout raises `NodeIOError`
- [ ] Content-Disposition path traversal sanitized
- [ ] Two file inputs with same server filename — no collision
- [ ] URL with query params — filename extracted from path
- [ ] URL with no file extension — fallback filename
- [ ] `request.inputs` not mutated by pipeline
- [ ] Node with zero file inputs — `run()` unaffected
- [ ] Non-string value in file field skipped
- [ ] Multiple file inputs all processed
- [ ] Non-file inputs untouched

### Phase 5: Lint & Existing Tests

- [ ] Run `poetry run ruff check canvastekk_workflow_sdk/ tests/`
- [ ] Run `poetry run pytest -v`

### Phase 6: Documentation Sync (deferred to separate commit)

- [ ] Update `AGENTS.md` rules 4-5
- [ ] Update `python/README.md` File Handling Guide
- [ ] Update `docs/EXTERNAL-AUTHOR-GUIDE.md` File Inputs section
- [ ] Update `.opencode/skills/canvastekk-node-builder/SKILL.md`
- [ ] Update `.opencode/skills/canvastekk-node-patterns/SKILL.md`
- [ ] Update `README.md` File Input Validation + Architecture Decisions
- [ ] Update `examples/echo_node/` to demonstrate new pattern

---

## Dependencies

- **DA-994**: floor-flatness-assessment bug (motivation for this ticket)
- **DA-995**: engine S3 key extensions (related but not blocking)

## Risks & Mitigation

| Risk | Mitigation |
|------|-----------|
| Breaking existing nodes that download manually | Local paths pass through unchanged — fully backward compatible |
| Large file downloads timeout | Configurable timeout (default 30s), streaming chunks |
| Filename collisions in `downloads_dir` | Prefix with field name: `{field_name}_{filename}` |
| Memory pressure from many concurrent downloads | Each download streams to disk, not memory |
| SSRF via crafted URLs | URL scheme check; SDK runs in trusted orchestrator context |
| Path traversal in filenames | `Path(filename).name` strips directory components |
| `request.inputs` mutation affects error recording | Copy inputs dict before modification |
| Optional file fields with None values | Explicit None/missing/non-string skip logic |
