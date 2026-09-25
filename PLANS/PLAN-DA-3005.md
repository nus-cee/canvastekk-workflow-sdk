# PLAN: Document UploadSession file-input lane in node skills — canvastekk-workflow-sdk

**Branch**: feat/DA-3005
**Issue**: https://betekk.atlassian.net/browse/DA-3005
**Base**: main

## Acceptance Criteria

- [ ] Both bundled skills document the `UploadTarget = str | UploadSession` union (`uploads.py:63`): engine-minted `UploadSession` (multipart standard, DA-2885/2886) vs legacy presigned-PUT string (deprecated, `LegacyPresignedUploadWarning`, removed in v1.0)
- [ ] Skills teach pass-through discipline: never assume the target is a string; never construct `UploadSession` manually
- [ ] Repo mirrors updated in lockstep (byte-identical to bundled); frontmatter untouched (exactly `name` + `description`)
- [ ] Gates genuinely green: full pytest (deps provisioned via `poetry install`), ruff, `poetry build`

## Dependency & Consumer Map

| Node (file/module) | Depends on | Consumers | Change risk |
|---------------------|-----------|-----------|-------------|
| `python/canvastekk_workflow_sdk/data/skills/**/SKILL.md` (canonical, edited first) | uploads.py/multipart.py facts | wheel consumers via `sdk init` | low |
| `.agents/skills/**/SKILL.md` (mirrors) | canonical copies (copy after edit) | in-repo OpenCode/pi sessions | low |

## Implementation Phases

### Phase 1: Document the union in canonical copies
- [ ] **1.1** Builder SKILL.md "How File Outputs Work": correct the presigned-PUT-only claim; add upload-target note (str | UploadSession, deprecation warning, pass-through discipline, lazy multipart machinery in multipart.py)
    — **Why:** skills currently teach only the string lane, which is deprecated and warns per call site since DA-2885/2886
    — **Done when:** section names both target kinds, the deprecation, and the pass-through rule
    — **Consumers affected:** wheel consumers + in-repo agents
- [ ] **1.2** Patterns SKILL.md: add a compact "Upload targets" section (same facts, example showing pass-through of `upload_urls`/targets without string assumptions)
    — **Why:** patterns are the copy-paste examples agents reuse
    — **Done when:** section present with grounded example
    — **Consumers affected:** same

### Phase 2: Mirror + verify
- [ ] **2.1** Copy canonical → `.agents/skills/` mirrors; verify byte-identical; frontmatter untouched
    — **Why:** mirrors must not re-drift (DA-3003 lesson)
    — **Done when:** `diff -q` IDENTICAL both pairs
    — **Consumers affected:** in-repo agent sessions
- [ ] **2.2** Gates: ruff, full pytest, `poetry build`
    — **Why:** exit gate full; docs-only but gates are cheap now that deps provision
    — **Done when:** all green
    — **Consumers affected:** release workflow

## Technical Notes
- Grounded API facts (uploads.py:32-80): `UploadSession` is engine-provided (session_token, initiate/complete/abort/status URLs, TTL-bound); SDK redeems lazily — initiate POST `{size, content_type}` → part PUTs in bounded parallel batches → complete; resume via status. Legacy single-PUT string emits `LegacyPresignedUploadWarning` per call site; removed in v1.0.
- `context.output_path(...)` + returning the path string remains the node-author contract; targets are engine-provided, not constructed by nodes.

## Dependencies
DA-3003 (resync) — merged (b3a5254) so edits land on already-synced copies.

## Risks & Mitigation
| Risk | Mitigation |
|------|------------|
| Drift reintroduced by editing only one copy | Canonical first, then mirror copy + diff-verify (2.1) |
| Teaching inaccuracy | All claims grounded in uploads.py/multipart.py source read this run |
