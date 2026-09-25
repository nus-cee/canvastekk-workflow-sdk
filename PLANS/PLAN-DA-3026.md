# PLAN: CI skill-mirror drift guard + canonical example cleanup — canvastekk-workflow-sdk

**Branch**: feat/DA-3026
**Issue**: https://betekk.atlassian.net/browse/DA-3026
**Base**: main

## Acceptance Criteria

- [x] `skill-mirror-guard` job in `.github/workflows/ci-python.yml` fails when mirrors differ from canonical (negatively tested before push)
- [x] Zero manual `id=` kwargs in any SKILL.md (6 instances removed across builder + patterns, canonical + mirrors)
- [x] `context.metadata` post-download example restored in patterns skill, matching `base.py:396-400`
- [x] httpx mistakes-row reworded (chunked local reads for downloaded files; httpx.stream only for manual URL downloads)
- [x] Mirrors byte-identical to canonical after all edits; ruff + full pytest + `poetry build` green

## Dependency & Consumer Map

| Node (file/module) | Depends on | Consumers | Change risk |
|---------------------|-----------|-----------|-------------|
| `.github/workflows/ci-python.yml` (+1 job) | mirrors/canonical layout (DA-2982) | CI on every PR/push — guard blocks drift merges | med (workflow edit) |
| `data/skills/**/SKILL.md` (canonical edits) | base.py/definition.py facts | wheel consumers via `sdk init` | low |
| `.agents/skills/**/SKILL.md` (mirrors) | canonical (copy after edits) | in-repo OpenCode/pi sessions | low |

## Implementation Phases

### Phase 1: Canonical cleanup + mirror sync
- [x] **1.1** Remove the 6 manual `id=` kwargs from manifest examples (builder :126; patterns :54/:188/:309 and bundled twins)
    — **Why:** `id` is a `@computed_field` derived from `slug`+`version` (`definition.py:294`); the kwarg is silently ignored and teaches a false contract
    — **Done when:** `git grep 'id="'` over both skills returns only non-manifest matches (0 in manifest examples)
    — **Consumers affected:** agents copying the examples
    — **Done:** 6 kwarg lines removed across 4 copies; remaining id=" matches are reads (run_id/node_id/lookup) — grep-verified; files: 4 SKILL.md; fixes: none
- [x] **1.2** Restore the `context.metadata` post-download example in the patterns skill's manual-download teaching, grounded on `base.py:396-400`
    — **Why:** real SDK behavior the canonical dropped; agents writing audit/report nodes need it
    — **Done when:** example present with the exact three keys (`original_url`, `local_path`, `size_bytes`)
    — **Consumers affected:** agents writing file-download nodes
    — **Done:** "File-input download facts" section added (exact 3 keys from base.py:396-400) in both patterns copies; files: patterns SKILL.md ×2; fixes: none
- [x] **1.3** Reword builder :777 mistakes row: chunked local reads for downloaded files; `httpx.stream()` scoped to manual URL downloads
    — **Why:** current row points at the wrong tool for auto-downloaded local paths
    — **Done when:** row reads as scoped above
    — **Consumers affected:** node authors
    — **Done:** row reworded — chunked local reads for downloaded files, httpx.stream scoped to manual URL downloads; files: builder SKILL.md ×2; fixes: none
- [x] **1.4** Copy canonical → mirrors; verify byte-identical
    — **Why:** mirrors must not re-drift (DA-3003 lesson)
    — **Done when:** `diff -q` IDENTICAL for both pairs
    — **Consumers affected:** in-repo agent sessions
    — **Done:** diff -q IDENTICAL both pairs; files: mirrors; fixes: none

### Phase 2: CI drift guard + gates
- [x] **2.1** Add `skill-mirror-guard` job (ubuntu-latest: checkout → `diff -r .agents/skills python/canvastekk_workflow_sdk/data/skills`) to `ci-python.yml`
    — **Why:** hand-resync without a guard makes recurrence mechanically certain (the DA-3003 failure mode)
    — **Done when:** job present; negative test proven (temporarily corrupt a mirror locally, `diff -r` exits non-zero, restore) BEFORE push
    — **Consumers affected:** all future PRs
    — **Done:** job added (checkout@v6, diff -r, ubuntu-latest); negative test proven locally — drift exit 1, clean exit 0; files: ci-python.yml; fixes: one botched git-checkout restore during the negative test, corrected by re-copying canonical
- [x] **2.2** Gates: ruff, full pytest (poetry install), `poetry build`
    — **Why:** exit gate full; workflow YAML not covered by pytest but job syntax is validated by the negative test + CI itself
    — **Done when:** all green
    — **Consumers affected:** release workflow
    — **Done:** ruff pass; poetry install + FULL suite 721 passed; wheel 0.29.4 built; files: none; fixes: none

## Technical Notes
- Guard is `diff -r`, exit-code based — no new tooling, no python needed in the job.
- Manifest examples correctly use `slug=`/`name=`; only the `id=` kwarg lines are removed (the computed `id` keeps appearing in output/lookup teaching where it is a read).

## Dependencies
DA-3003 (resync) — merged; this ticket builds on the synced state.

## Risks & Mitigation
| Risk | Mitigation |
|------|------------|
| Guard job YAML syntax error blocks all CI | Workflow parsed by CI on this PR (job list visible in checks); negative test done locally pre-push |
| Removing `id=` lines changes example output expectations | `id` is computed — examples print identical values; grep-verified remaining matches are reads, not kwargs |

## Gate trace

GATE reviewfix tier=full lint=t typecheck=- build=t unit=t e2e=- (ruff pass; poetry install + full suite 721 passed; wheel 0.29.4; guard negative-tested locally: drift=1 clean=0)
