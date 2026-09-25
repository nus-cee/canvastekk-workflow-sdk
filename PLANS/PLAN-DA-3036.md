# PLAN: Standardize poetry — >=2.2 floor + module-mode invocation — canvastekk-workflow-sdk

**Branch**: feat/DA-3036
**Issue**: https://betekk.atlassian.net/browse/DA-3036
**Base**: main (351d4a4, v0.30.1)

## Acceptance Criteria

- [ ] Zero bare `poetry` invocations in `.github/workflows/ci-python.yml` and `release.yml` (all become `python -m poetry ...`)
- [ ] Zero unpinned / <2.2 installs: ci-python.yml :38,:105 and release.yml :53 all read `pip install "poetry>=2.2"`
- [ ] Both workflow YAMLs parse; local gates green (ruff + full pytest + poetry build); PR CI green

## Dependency & Consumer Map

| Node (file) | Depends on | Consumers | Change risk |
|---|---|---|---|
| `.github/workflows/ci-python.yml` | setup-python 3.12 (hosted) | every PR/push CI run | low (mechanical) |
| `.github/workflows/release.yml` | git-cliff version step | release pipeline: lock regen + wheel publish | med (touches lock regen tool version) |

## Implementation Phases

### Phase 1: ci-python.yml — floor + module invocation
- [ ] **1.1** `pip install poetry` → `pip install "poetry>=2.2"` (:38, :105)
    — **Why:** unpinned install drifts from the org floor (workflow-nodes/engine already `poetry>=2.2`); `>=2.2` resolves to the largest available minor (2.5.1 today)
    — **Done when:** both lines carry the quoted floor; zero unpinned installs remain
    — **Consumers affected:** all CI runs
- [ ] **1.2** 7 bare invocations (:41, :44, :47, :110, :115, :120, :125) → `python -m poetry ...`
    — **Why:** PATH-immune module mode — org standard per DA-3028 precedent
    — **Done when:** grep finds zero `run: poetry ` lines
    — **Consumers affected:** all CI runs

### Phase 2: release.yml — floor + module invocation
- [ ] **2.1** `pip install poetry==1.8.5` → `pip install "poetry>=2.2"` (:53)
    — **Why:** 1.x-era pin regenerates poetry.lock with the 1.x resolver/lock format against a 2.x toolchain — lock-format churn
    — **Done when:** pin line reads `"poetry>=2.2"`; no `1.8.5` remains
    — **Consumers affected:** release pipeline lock regeneration
- [ ] **2.2** bare `poetry lock` (:58) and `poetry build` (:121, multiline block) → `python -m poetry ...`
    — **Why:** same standard; working-directory (`python/`) semantics unchanged
    — **Done when:** grep finds zero bare `poetry` command lines
    — **Consumers affected:** release pipeline

### Phase 3: Gates
- [ ] **3.1** `yaml.safe_load` both files; grep assertions (0 bare, 0 unpinned, 0 `1.8.5`); ruff + full pytest + `poetry build` from `python/`
    — **Why:** workflow-only diff; PR CI self-validates, local gates prove nothing else broke
    — **Done when:** all green
    — **Consumers affected:** release workflow

## Technical Notes
- `python -m poetry` requires install and invocation to share the interpreter — guaranteed by `actions/setup-python@v6` pinning 3.12 in every job that uses poetry.
- Release lock regen with poetry 2.x may rewrite `poetry.lock` format on the next release run — expected and one-time (consumers are all 2.x).

## Risks & Mitigation
| Risk | Mitigation |
|------|------------|
| poetry 2.x lock format churn on next release | All consumers (engine check, CI) already 2.x; one-time regen is the fix, not a regression |
| Module invocation + different interpreter than pip install | setup-python pins one interpreter per job; `pip`/`python` resolve identically |
