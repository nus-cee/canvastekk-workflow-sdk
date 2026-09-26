# PLAN: Standardize poetry — >=2.2 floor + module-mode invocation — canvastekk-workflow-sdk

**Branch**: feat/DA-3036
**Issue**: https://betekk.atlassian.net/browse/DA-3036
**Base**: main (351d4a4, v0.30.1)

## Acceptance Criteria

- [x] Zero bare `poetry` invocations in `.github/workflows/ci-python.yml` and `release.yml` (all become `python -m poetry ...`)
- [x] Zero unpinned / <2.2 installs: ci-python.yml :38,:105 and release.yml :53 all read `pip install "poetry>=2.2"`
- [x] Both workflow YAMLs parse; local gates green (ruff + full pytest + poetry build)
- [ ] PR CI green — ci-python.yml is validated by the PR run; release.yml triggers on push to main only, so its first real run is the next release (post-merge); noted as accepted residual

## Dependency & Consumer Map

| Node (file) | Depends on | Consumers | Change risk |
|---|---|---|---|
| `.github/workflows/ci-python.yml` | setup-python 3.12 (hosted) | every PR/push CI run | low (mechanical) |
| `.github/workflows/release.yml` | git-cliff version step | release pipeline: lock regen + wheel publish | med (touches lock regen tool version) |

## Implementation Phases

### Phase 1: ci-python.yml — floor + module invocation
- [x] **1.1** `pip install poetry` → `pip install "poetry>=2.2"` (:38, :105)
    — **Why:** unpinned install drifts from the org floor (workflow-nodes/engine already `poetry>=2.2`); `>=2.2` resolves to the largest available minor (2.5.1 today)
    — **Done when:** both lines carry the quoted floor; zero unpinned installs remain
    — **Done:** 2 floors set; grep 0 unpinned; files: ci-python.yml; fixes: none
    — **Consumers affected:** all CI runs
- [x] **1.2** 7 bare invocations (:41, :44, :47, :110, :115, :120, :125) → `python -m poetry ...`
    — **Why:** PATH-immune module mode — org standard per DA-3028 precedent
    — **Done when:** grep finds zero `run: poetry ` lines
    — **Done:** 7 module invocations; command-position grep NONE; files: ci-python.yml; fixes: first regex missed nothing here, applied clean
    — **Consumers affected:** all CI runs

### Phase 2: release.yml — floor + module invocation
- [x] **2.1** `pip install poetry==1.8.5` → `pip install "poetry>=2.2"` (:53)
    — **Why:** 1.x-era pin regenerates poetry.lock with the 1.x resolver/lock format against a 2.x toolchain — lock-format churn
    — **Done when:** pin line reads `"poetry>=2.2"`; no `1.8.5` remains
    — **Done:** pin → "poetry>=2.2"; 1.8.5 grep 0; files: release.yml; fixes: first attempt asserted wrong count (run:-prefixed lock line not matched by ^\s*poetry regex) and aborted before write — re-applied with exact-form asserts
    — **Consumers affected:** release pipeline lock regeneration
- [x] **2.2** bare `poetry lock` (:58) and `poetry build` (:121, multiline block) → `python -m poetry ...`
    — **Why:** same standard; working-directory (`python/`) semantics unchanged
    — **Done when:** grep finds zero bare `poetry` command lines
    — **Done:** lock + build converted; command-position grep NONE; files: release.yml; fixes: none
    — **Consumers affected:** release pipeline

### Phase 3: Gates
- [x] **3.1** `yaml.safe_load` both files; grep assertions (0 bare, 0 unpinned, 0 `1.8.5`); ruff + full pytest + `poetry build` from `python/` — re-run after lock regen: 732 passed
    — **Why:** workflow-only diff; PR CI self-validates, local gates prove nothing else broke
    — **Done when:** all green
    — **Consumers affected:** release workflow
    — **Done:** YAML valid x2; GATES-PASS (poetry install + full pytest suite + wheel 0.30.1 built) via background run after 2 env restarts; files: none; fixes: none

## Technical Notes
- **Lock-regen policy (review WARN1):** release step uses `python -m poetry lock --regenerate` — behavior-identical to the 1.8.5 step (full re-resolve at release). Poetry 2.x bare `lock` defaults to no-update, which would have silently frozen transitive deps. Pinning-at-release remains a possible future policy change (follow-up ticket material), NOT smuggled into this standardization.
- **Reviewed lock-format regen (review WARN2):** python/poetry.lock regenerated with poetry 2.4.1 (format 2.0 → 2.1) IN this PR — diff is format/hash-only, zero version changes (verified); removes the 2.x-CI-reads-1.x-lock window from every schema-stability run.
- `python -m poetry` requires install and invocation to share the interpreter — guaranteed by `actions/setup-python@v6` pinning 3.12 in every job that uses poetry.
- Release lock regen with poetry 2.x may rewrite `poetry.lock` format on the next release run — expected and one-time (consumers are all 2.x).

## Risks & Mitigation
| Risk | Mitigation |
|------|------------|
| poetry 2.x lock format churn on next release | All consumers (engine check, CI) already 2.x; one-time regen is the fix, not a regression |
| Module invocation + different interpreter than pip install | setup-python pins one interpreter per job; `pip`/`python` resolve identically |

## Gate trace

GATE reviewfix tier=full lint=- typecheck=- build=t unit=t e2e=- workflow=CI-self-validating (post-lock-regen: poetry install + FULL suite 732 passed + wheel 0.30.1; lock 2.4.1 format-only regen, zero version drift; YAML x2; release.yml gated at next release — push-only trigger)
