# PLAN: Resync repo .agents/skills mirrors from bundled canonical copies — canvastekk-workflow-sdk

**Branch**: feat/DA-3003
**Issue**: https://betekk.atlassian.net/browse/DA-3003
**Base**: main

## Acceptance Criteria

- [x] `.agents/skills/{canvastekk-node-builder,canvastekk-node-patterns}/SKILL.md` byte-identical to `python/canvastekk_workflow_sdk/data/skills/` canonical copies
- [x] No deprecated legacy-construction teaching (`name=<slug>` / `title=`) remains in repo mirrors — current `slug=`/`name=` vocabulary only
- [x] Frontmatter stays exactly `name` + `description` in all 4 copies; `poetry build` + ruff + pytest gates green (pytest may be INCONCLUSIVE locally on missing ambient deps — CI-covered, as in DA-2982)

## Dependency & Consumer Map

| Node (file/module) | Depends on | Consumers | Change risk |
|---------------------|-----------|-----------|-------------|
| `.agents/skills/*/SKILL.md` (2 files) | bundled canonical (copy source) | OpenCode + pi sessions in this repo; agents reading SDK authoring docs | low |
| `python/canvastekk_workflow_sdk/data/skills/**` | none (unchanged — canonical source) | wheel consumers via `sdk init` | none |

## Implementation Phases

### Phase 1: Resync mirrors
- [x] **1.1** Copy `python/canvastekk_workflow_sdk/data/skills/{2 skills}/SKILL.md` over `.agents/skills/{2 skills}/SKILL.md`
    — **Why:** bundled copies are canonical (shipped to consumers, teach current `slug=`/`name=` vocabulary); the mirrors drifted (62/77 changed lines) and teach the deprecated `title=` legacy construction deprecated at `definition.py:34`
    — **Done when:** `diff -q` reports IDENTICAL for both pairs; mirrors contain zero `title=` legacy examples
    — **Consumers affected:** in-repo agent sessions
    — **Done:** canonical copied over both mirrors; diff-verified IDENTICAL; 0 title= legacy examples remain; files: .agents/skills/*/SKILL.md; fixes: none
- [x] **1.2** Verify frontmatter of the resynced mirrors is exactly `name` + `description` (bundled copies were normalized in DA-2982 — expected to pass through)
    — **Why:** the DA-2982 portable-frontmatter contract must survive the resync
    — **Done when:** head -4 of both mirrors = two-field header
    — **Consumers affected:** none
    — **Done:** two-field header pass-through confirmed on both mirrors; files: none; fixes: none

### Phase 2: Verification
- [x] **2.1** Gates: ruff, pytest (INCONCLUSIVE-tolerant per DA-2982 precedent), `poetry build`
    — **Why:** only markdown changed; build validates the wheel still packages correctly
    — **Done when:** ruff pass, build pass, pytest green or INCONCLUSIVE-with-CI-coverage recorded
    — **Consumers affected:** release workflow
    — **Done:** ruff pass; poetry build pass (wheel 0.29.1); pytest not run locally — INCONCLUSIVE-tolerant (no ambient deps), CI-covered; files: none; fixes: none

## Technical Notes
- Drift validated 2026-09-25 against `17287d8` (v0.29.1): node-builder 800 vs 785 lines (62 changed), node-patterns 953 vs 941 (77 changed); mirrors carried `title=` legacy examples (builder L128/410, patterns L57/192/312) and lacked the auto-download description sentence.
- Future-proofing option (proposed in PR, not implemented here): a build-time or release-checklist step to derive mirrors from canonical — avoids recurrence; a full mechanism is deliberately out of scope for this ticket.

## Dependencies
None.

## Risks & Mitigation
| Risk | Mitigation |
|------|------------|
| Recurrence of drift | Single canonical direction documented (bundled → mirror); recurrence-mechanism proposal in PR body |

## Gate trace

GATE reviewfix tier=full lint=t typecheck=- build=t unit=inconclusive e2e=- (md-only resync; ruff+build pass; pytest CI-covered per DA-2982 precedent)
