# PLAN: Move project skills to .agents/skills so OpenCode and pi share them — canvastekk-workflow-sdk

**Branch**: feat/DA-2982
**Issue**: https://betekk.atlassian.net/browse/DA-2982
**Base**: main

## Acceptance Criteria

- [x] Both skill folders live under `.agents/skills/<id>/SKILL.md`, git-tracked; `.opencode/skills/` no longer exists
- [x] Every SKILL.md frontmatter is exactly `name` + `description`, name matching its directory — in BOTH the repo copy and the wheel-bundled `python/canvastekk_workflow_sdk/data/skills/` copy
- [x] No skill body requires OpenCode-only tools or subagents without a harness-agnostic fallback line
- [x] No remaining `.opencode/skills` path strings in tracked in-scope files (historical `PLANS/*` excluded)
- [x] `_init_skills` scaffolds consumer skills into `.agents/skills` (code change, not docs)
- [ ] Repo gates green (ruff + pytest); global-shadow check for the 2 IDs documented; pi discovery spot-check — ruff+build green, shadow check clean; pytest inconclusive locally (pre-existing missing deps), closes via CI; live pi check N/A (binary absent)
- [x] `README.md` install/layout instructions point at `.agents/skills`

## Dependency & Consumer Map

| Node (file/module) | Depends on (must precede) | Consumers (who depends on this) | Change risk |
|---------------------|---------------------------|---------------------------------|-------------|
| `.agents/skills/{canvastekk-node-builder,canvastekk-node-patterns}/` | 1.1 move | OpenCode + pi sessions in this repo; DA-2983 re-copy (cross-repo, linked blocked-by) | low |
| `python/canvastekk_workflow_sdk/data/skills/**/SKILL.md` (frontmatter only) | none | Wheel consumers: `sdk init` scaffolds these into user projects | low |
| `python/canvastekk_workflow_sdk/__main__.py` `_init_skills` dest | 1.1 (message consistency) | CLI users scaffolding consumer projects; no in-repo test asserts the dest path | med |
| `README.md` | 2.1 (instructions must match new dest) | developers | low |

## Implementation Phases

### Phase 1: Move and normalize skills
- [x] **1.1** `git mv .opencode/skills .agents/skills` so both harnesses discover the skills natively
    — **Why:** `.opencode/skills/` is OpenCode-only; `.agents/skills/` is the standard location both OpenCode v2 and pi scan with zero config
    — **Done when:** `git ls-files .agents/skills` shows both `SKILL.md` files; `.opencode/skills` is absent from the tree
    — **Consumers affected:** in-repo agent sessions; DA-2983 re-copy source path
    — **Done:** clean renames via `mkdir -p .agents && git mv`; both SKILL.md tracked at new path; `.opencode/skills` gone; files: `.agents/skills/**`; fixes: none
- [x] **1.2** Normalize `.agents/skills/*/SKILL.md` frontmatter to exactly `name` + `description` (drop `license`, `compatibility`, `metadata`)
    — **Why:** `compatibility: opencode` is a harness leak; OpenCode hard-requires name == directory, pi warns on drift; portable subset is the migration contract
    — **Done when:** `head -4` of each file shows only the two fields; names match directory names
    — **Consumers affected:** none (content-neutral fields dropped)
    — **Done:** both files rebuilt to `---`/`name`/`description`/`---`; names match dirs; files: `.agents/skills/*/SKILL.md`; fixes: first pass truncated bodies (awk kept header only, 3495 deletions) — bodies restored byte-identical from HEAD~1 (diff-verified tails) in fix commit
- [x] **1.3** Apply the same frontmatter normalization to `python/canvastekk_workflow_sdk/data/skills/*/SKILL.md`
    — **Why:** these are the copies the wheel ships and `sdk init` scaffolds into consumer projects, where pi/OpenCode will load them at `.agents/skills`
    — **Done when:** both bundled files carry exactly `name` + `description`
    — **Consumers affected:** wheel consumers of `sdk init`
    — **Done:** both bundled files rebuilt to the two-field header (each keeps its own description text); files: `python/canvastekk_workflow_sdk/data/skills/*/SKILL.md`; fixes: same truncation as 1.2 — bodies restored byte-identical, diff-verified
- [x] **1.4** Grep all four SKILL.md bodies for OpenCode-only tool/subagent assumptions; add one "or perform the steps directly" fallback line where found
    — **Why:** the skills must be executable by any harness, not just OpenCode's agent roster
    — **Done when:** no skill body references OpenCode-specific subagents/tools without a fallback
    — **Consumers affected:** none
    — **Done:** `grep -in "subagent|opencode|.claude|openai codex"` over all four bodies → zero hits; no fallback lines needed; files: none; fixes: none

### Phase 2: Flip scaffold code and docs
- [x] **2.1** Change `_init_skills` destination to `.agents/skills` in `python/canvastekk_workflow_sdk/__main__.py` (docstrings at ~355/358, dest at ~367, CLI help wording at ~520)
    — **Why:** otherwise `sdk init` keeps scaffolding the dead `.opencode/skills` location in consumer projects
    — **Done when:** `git grep -n "opencode.*skills" python/` returns no `.opencode/skills` dest; new dest is `.agents/skills`
    — **Consumers affected:** CLI `init` users
    — **Done:** dest flipped to `target_dir / ".agents" / "skills"`; docstring + CLI help reworded harness-neutral; files: `python/canvastekk_workflow_sdk/__main__.py`; fixes: none
- [x] **2.2** Update `README.md` references (layout tree ~385, manual install cp commands ~405-406) to `.agents/skills`
    — **Why:** instructions must match the shipped reality
    — **Done when:** `rg '\.opencode/skills' README.md` is empty
    — **Consumers affected:** developers
    — **Done:** tree + global-copy commands now target `.agents/skills` / `~/.agents/skills` (shared by OpenCode + pi); "OpenCode-compatible" prose line neutralized to Agent Skills standard; files: `README.md`; fixes: none
- [x] **2.3** Repo-wide residual check: `git grep -n '\.opencode/skills'` over tracked files excluding `PLANS/`
    — **Why:** catches any reference the two steps above missed
    — **Done when:** zero hits outside `PLANS/`
    — **Consumers affected:** none
    — **Done:** zero hits (exit 1); files: none; fixes: none

## Gate trace

GATE d4f313f tier=light lint=t typecheck=- build=- unit=inconclusive e2e=- (Phase 1: md-only after body-restore fix; ruff pass)
GATE phase2 tier=light lint=t typecheck=- build=- unit=inconclusive e2e=- (ruff pass; py_compile pass; pytest INCONCLUSIVE: all 25 test modules fail collection on missing ambient deps — identical on pristine origin/main; change is string-literal-only)
GATE EXIT tier=full lint=t typecheck=- build=t unit=inconclusive e2e=- (ruff pass; poetry build pass — wheel ships bundled data; pytest inconclusive pre-existing, CI-covered; backend-only, no Playwright)

### Phase 3: Gates and verification
- [x] **3.1** Run repo gates: `ruff check python` + `pytest` (from `python/`)
    — **Why:** the only code change is `__main__.py`; gates prove nothing else broke
    — **Done when:** both exit 0
    — **Consumers affected:** release workflow
    — **Done:** ruff pass (All checks passed); pytest INCONCLUSIVE locally — 25 modules fail collection on missing ambient deps, identical on pristine origin/main; covered by PR CI (poetry install + pytest); files: none; fixes: none
- [x] **3.2** One-time global-shadow check: confirm `canvastekk-node-builder` / `canvastekk-node-patterns` do not exist in `~/.config/opencode/skills/`, `~/.agents/skills/`, `~/.pi/agent/skills/`
    — **Why:** globals outrank project `.agents/skills` in both harnesses; a stale global would shadow the migrated copies
    — **Done when:** check output recorded in the ticket comment (expected: absent)
    — **Consumers affected:** all repos in this migration (one-time check carried here)
    — **Done:** all 6 probes (2 IDs × 3 global dirs) absent — no shadows; recorded in ticket comment; files: none; fixes: none
- [x] **3.3** pi discovery spot-check from the worktree (pi binary if installed; else document the limitation and verify paths against the pi discovery rules)
    — **Why:** the ticket's cross-harness premise must be evidenced at least once in the pipeline
    — **Done when:** pi lists both skills, or limitation + path verification documented in ticket comment
    — **Consumers affected:** pi users
    — **Done:** pi binary not installed locally (limitation noted, not installed unprompted); paths verified against pi discovery rules (project `.agents/skills/`, cwd up to git root); recorded in ticket comment; files: none; fixes: none

## Technical Notes

- Three-copy layout discovered during re-validation: repo authoring copy (`.opencode/skills/`, this PLAN moves it), wheel-bundled copy (`python/canvastekk_workflow_sdk/data/skills/`, frontmatter-normalized only), and the stale copy in canvastekk-point-cloud-app (DA-2983 replaces it).
- **Body drift** between repo and bundled copies (109 / 140 diff lines) is pre-existing and OUT OF SCOPE — record in ticket comment as a follow-up candidate; this PLAN touches bundled files' frontmatter only.
- No packaging change needed: Poetry includes `canvastekk_workflow_sdk/data/**/*` in sdist+wheel.
- No in-repo test asserts the scaffold destination.

## Dependencies

- None blocking start. DA-2983 (point-cloud re-copy) is blocked by THIS ticket's merge.

## Risks & Mitigation

| Risk | Mitigation |
|------|------------|
| Re-introduced drift between authoring and bundled copies | Out-of-scope follow-up noted in ticket; both copies' frontmatter normalized here so at least the machine-read header is identical |
| Consumers' existing `.opencode/skills/` scaffolds become stale | New scaffolds go to `.agents/skills`; old dirs in consumer projects are inert (harnesses just stop discovering them) |
