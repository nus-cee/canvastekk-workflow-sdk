# PLAN: Pin sdk init scaffold destination with pytest — canvastekk-workflow-sdk

**Branch**: feat/DA-3004
**Issue**: https://betekk.atlassian.net/browse/DA-3004
**Base**: main

## Acceptance Criteria

- [ ] `python/tests/test_cli_init.py` asserts both bundled skills scaffold into `.agents/skills/<id>/SKILL.md` and the legacy `.opencode/skills` is NOT created
- [ ] Follows the repo's subprocess convention (no package import at module scope — model_validator constraint)
- [ ] Gates genuinely green: full pytest suite (deps provisioned via `poetry install` — closes the DA-2982 INCONCLUSIVE limitation), ruff, `poetry build`

## Dependency & Consumer Map

| Node (file/module) | Depends on | Consumers | Change risk |
|---------------------|-----------|-----------|-------------|
| `python/tests/test_cli_init.py` (new) | `_init_skills` dest contract (DA-2982, `__main__.py` ~367) | CI (`ci-python.yml` pytest) — fails on any dest regression | low |

## Implementation Phases

### Phase 1: Add dest-pinning tests
- [ ] **1.1** Write `tests/test_cli_init.py`: subprocess `python -m canvastekk_workflow_sdk init` in `tmp_path` per `test_main.py` conventions; assert `.agents/skills/{canvastekk-node-builder,canvastekk-node-patterns}/SKILL.md` exist and `.opencode/skills` absent
    — **Why:** DA-2982 changed the dest with zero test coverage (validated: no test referenced `_init_skills`/skills paths); a regression would ship silently
    — **Done when:** `poetry run pytest tests/test_cli_init.py -q` → 2 passed
    — **Consumers affected:** CI suite

### Phase 2: Full gates
- [ ] **2.1** Full pytest suite + ruff + `poetry build` after `poetry install`
    — **Why:** exit gate is full; deps provisioned locally so pytest runs for real (not INCONCLUSIVE)
    — **Done when:** full suite green, ruff clean, wheel builds
    — **Consumers affected:** release workflow

## Technical Notes
- `init` is non-interactive (no `input()`/`confirm()` in `__main__.py`) — subprocess-safe without stdin.
- Package import requires fastapi transitively; that is why the tests use the subprocess convention AND why local execution needed `poetry install` (done in this run — ambient python still lacks deps).

## Dependencies
None.

## Risks & Mitigation
| Risk | Mitigation |
|------|------------|
| Test only pins dest, not content | In scope per ticket (~10-line dest pin); content parity is DA-3003's resync + proposed CI drift guard |
