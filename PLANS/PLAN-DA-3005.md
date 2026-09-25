# PLAN: Document UploadSession file-output upload lane in node skills — canvastekk-workflow-sdk

**Branch**: feat/DA-3005
**Issue**: https://betekk.atlassian.net/browse/DA-3005
**Base**: main

## Acceptance Criteria

- [x] Both bundled skills document the `UploadTarget = str | UploadSession` union (`uploads.py:63`): engine-minted `UploadSession` (multipart standard, DA-2885/2886) vs legacy presigned-PUT string (deprecated, `LegacyPresignedUploadWarning`, removed in v1.0)
- [x] Skills teach pass-through discipline: never assume the target is a string; never construct `UploadSession` manually
- [x] Repo mirrors updated in lockstep (byte-identical to bundled); frontmatter untouched (exactly `name` + `description`)
- [x] Gates genuinely green: full pytest (deps provisioned via `poetry install`), ruff, `poetry build`

## Dependency & Consumer Map

| Node (file/module) | Depends on | Consumers | Change risk |
|---------------------|-----------|-----------|-------------|
| `python/canvastekk_workflow_sdk/data/skills/**/SKILL.md` (canonical, edited first) | uploads.py/multipart.py facts | wheel consumers via `sdk init` | low |
| `.agents/skills/**/SKILL.md` (mirrors) | canonical copies (copy after edit) | in-repo OpenCode/pi sessions | low |

## Implementation Phases

### Phase 1: Document the union in canonical copies
- [x] **1.1** Builder SKILL.md "How File Outputs Work": correct the presigned-PUT-only claim; add upload-target note (str | UploadSession, deprecation warning, pass-through discipline, lazy multipart machinery in multipart.py)
    — **Why:** skills currently teach only the string lane, which is deprecated and warns per call site since DA-2885/2886
    — **Done when:** section names both target kinds, the deprecation, and the pass-through rule
    — **Consumers affected:** wheel consumers + in-repo agents
    — **Done:** "How File Outputs Work" corrected + Upload targets note added (union, deprecation warning, pass-through rules, multipart machinery); files: data/skills/canvastekk-node-builder/SKILL.md; fixes: none
- [x] **1.2** Patterns SKILL.md: add a compact "Upload targets" section (same facts, example showing pass-through of `upload_urls`/targets without string assumptions)
    — **Why:** patterns are the copy-paste examples agents reuse
    — **Done when:** section present with grounded example
    — **Consumers affected:** same
    — **Done:** "Upload targets: str | UploadSession" section appended with pass-through example; files: data/skills/canvastekk-node-patterns/SKILL.md; fixes: none

### Phase 2: Mirror + verify
- [x] **2.1** Copy canonical → `.agents/skills/` mirrors; verify byte-identical; frontmatter untouched
    — **Why:** mirrors must not re-drift (DA-3003 lesson)
    — **Done when:** `diff -q` IDENTICAL both pairs
    — **Consumers affected:** in-repo agent sessions
    — **Done:** mirrors copied + diff-verified IDENTICAL; frontmatter untouched; files: .agents/skills/*/SKILL.md; fixes: none
- [x] **2.2** Gates: ruff, full pytest, `poetry build`
    — **Why:** exit gate full; docs-only but gates are cheap now that deps provision
    — **Done when:** all green
    — **Consumers affected:** release workflow
    — **Done:** ruff pass; full suite 721 passed (deps provisioned); wheel 0.29.2 built; files: none; fixes: none

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

## Gate trace

GATE reviewfix tier=full lint=t typecheck=- build=t unit=t e2e=- (docs-only content change; ruff pass; full suite 721 passed with deps provisioned; wheel built)

- [x] **1.3** (review fix) Warning-frequency wording (registry-dedup), line-218 mapping comment, silencing import, PLAN title
    — **Why:** "each use emits" contradicts uploads.py:84-87 dedup; :218 was stale presigned-only; snippet lacked import path
    — **Done when:** all copies consistent, dedup wording accurate, PLAN title correct
    — **Consumers affected:** docs readers
    — **Done:** applied to canonical + mirror (byte-parity preserved); PLAN ticked; files: 2 SKILL.md pairs + PLAN; fixes: review WARN 1 + NOTEs
