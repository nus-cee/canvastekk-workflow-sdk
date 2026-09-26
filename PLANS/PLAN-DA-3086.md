# PLAN: absorb registry-convergence into the SDK CLI (DA-3086)

**Branch**: feat/DA-3086 (SDK) + feat/DA-3086-{ifc,cwn,crs} (repins)
**Issue**: https://nus-cee.atlassian.net/browse/DA-3086
**Base**: main (SDK repo default — this repo has no dev; node-repo repins base origin/dev per train convention)

## Acceptance Criteria
- [ ] `registry-convergence` subcommand shipped in ONE SDK release — the first release after the SDK PR merges, whichever version git-cliff assigns (v0.31.0 barring an interleaved feat:); the repins pin the version OBSERVED on the release and verify the wheel contains the subcommand; tests cover the drain predicate matrix + assert semantics
- [ ] Three repos repinned; in-repo copies deleted; each dev deploy green post-repin with "convergence OK — staged N/N present in registry"
- [ ] No behavior change: identical drain predicate + assert semantics (wholesale port, no logic rewrite)

## Dependency & Consumer Map

| Node (file/module) | Depends on (must precede) | Consumers (who depends on this) | Change risk |
|---------------------|---------------------------|---------------------------------|-------------|
| `python/canvastekk_workflow_sdk/convergence.py` (new) | reference impl (CWN dev HEAD, 250 lines) | `__main__.py` dispatch, tests, 3 workflows | med |
| `__main__.py` dispatch + help | convergence.py | CLI users | low |
| `python/tests/test_convergence.py` (port of ref-tests minus drift guard) | convergence.py | CI | low |
| SDK release v0.31.0 (push main → git-cliff minor bump → wheel asset) | SDK PR merged | all 3 repin PRs | med |
| Repin IFC (pyproject pin v0.28.1→v0.31.0; workflow step → `/tmp/sdkcli`; delete apps/python/scripts/registry_convergence.py; trim tests to drift guard) | release v0.31.0 exists | IFC dev/uat deploys | med |
| Repin CWN (pin v0.29.0→v0.31.0; same surface) | release v0.31.0 | CWN deploys | med |
| Repin CRS (pin v0.28.1→v0.31.0; same surface) | release v0.31.0 | CRS deploys | med |

Key wiring facts (re-verified at origin/dev 2026-09-26, arch review F2): all three pyprojects pin **v0.30.0** (IFC apps/python/pyproject.toml:12, CWN fastapi_app/pyproject.toml:12, CRS fastapi_app/pyproject.toml:12); workflow `/tmp/sdkcli` install URLs: IFC v0.30.0 (:559), CRS v0.30.0 (:476), **CWN v0.28.1 (:506 — pre-existing drift vs its own pyproject v0.30.0, violating the in-file "keep in sync" comment :556; this repin fixes it)**. All three register steps build `/tmp/sdkcli` in the same job; convergence steps: CWN gated `steps.register-nodes.outcome == 'success'` (:611), CRS same (:577), **IFC gated `success() && matrix.app == 'python'`** (:724 — safe: its register step :541 has no continue-on-error, so success() implies the venv step ran). Repins bump TWO pins per repo: pyproject dep URL + the workflow install URL (done-when greps check BOTH surfaces per repo).

## Implementation Phases

### Phase 1: SDK subcommand
- [ ] **1.1** Port the reference wholesale into `python/canvastekk_workflow_sdk/convergence.py` (zero logic changes: pagination, HEAD-ancestry history, invoke_url ownership, post-drain snapshot assert; argparse `main(argv)`; stdlib-only; token env `REGISTRY_SERVICE_TOKEN` preserved so the three workflow steps need no env change). Update the docstring to SDK absorption lineage (DA-3070 → DA-3071 → DA-3084 → DA-3086) and drop the per-repo framing.
    — **Why:** wholesale port satisfies the no-behavior-change AC; stdlib-only keeps the runner property.
    — **Done when:** module imports clean; docstring cites the lineage.
    — **Consumers affected:** CLI dispatch, tests, 3 deploy workflows.
- [ ] **1.2** Wire the dispatch in `__main__.py`: `registry-convergence` → `convergence.main(argv)`; add the command to the top-level usage/help text and module docstring. Follow the `_run_register` conventions (help listing; exit codes: 0 ok · 1 assert failure/unhandled · 2 usage/token — arch F5: do NOT normalize the ported codes or streams; `::error::` stays on stdout).
    — **Why:** "next to register" — same entry point, same operator ergonomics.
    — **Done when:** `python -m canvastekk_workflow_sdk --help` lists it; `registry-convergence --help` works.
    — **Consumers affected:** CLI users; 3 workflows post-repin.
- [ ] **1.3** Port the test matrix to `python/tests/test_convergence.py` (imports `canvastekk_workflow_sdk.convergence`): canonical parse edges, four-clause drain matrix, pagination, 404-tolerant DELETE, dry-run, git-history union (git via subprocess — present in CI), post-drain snapshot assert pass/fail. Add CLI dispatch tests to `python/tests/test_cli_register.py` (arch F6 — test_main.py doesn't exist): routing, `registry-convergence --help` exit 0, missing-required-arg exit 2. No --json tests (the port has no --json flag).
    — **Why:** ticket AC — tests cover drain/assert semantics.
    — **Done when:** suite passes locally; matrix covers the invariants (ownership scoping + post-drain snapshot).
    — **Consumers affected:** CI.
- [ ] **1.4** Gates from `python/` (AGENTS.md:39): `poetry run ruff check canvastekk_workflow_sdk/ tests/` + `poetry run pytest -v` (full suite).
    — **Why:** repo's gate contract.
    — **Done when:** both exit 0.
    — **Consumers affected:** none.

### Phase 2: SDK PR → merge → release
- [ ] **2.1** Commit `feat(cli): registry-convergence subcommand (DA-3086)` (git-cliff minor bump → v0.31.0), PR to main, merge; verify release.yml produces v0.31.0 with the wheel asset named `canvastekk_workflow_sdk-0.31.0-py3-none-any.whl`.
    — **Why:** one release gates all three repins.
    — **Done when:** the release's wheel asset installs into a scratch venv and `python -m canvastekk_workflow_sdk --help` lists `registry-convergence` (arch F8 — content check, not just asset existence; repins pin the OBSERVED version).
    — **Consumers affected:** 3 repin PRs.

### Phase 3: Three repin PRs (one per repo, each gated on 2.1)
- [ ] **3.1** IFC (`feat/DA-3086-ifc` from origin/dev): pyproject wheel pin v0.28.1→v0.31.0; deploy-lambda.yml `/tmp/sdkcli` install URL → v0.31.0 and convergence step swaps `python3 apps/python/scripts/registry_convergence.py` → `/tmp/sdkcli/bin/python -m canvastekk_workflow_sdk registry-convergence` — **IFC flag rewrite (arch F1): IFC's script took `--function-url` (its copy diverges); the SDK CLI takes `--invoke-base "$FUNCTION_URL"` (IFC registers `--invoke-url "$FUNCTION_URL/nodes/$slug/execute"` at :598 and has no LAMBDA_INVOKE_DOMAIN channel, so the bare function URL is the ownership base)**; delete `apps/python/scripts/registry_convergence.py` + `apps/python/scripts/__init__.py` if empty; trim `test_registry_convergence.py` (flat path apps/python/test_registry_convergence.py) to the drift guard only, parse helper imported from `canvastekk_workflow_sdk.convergence` (SDK is a main dep; py.typed ships so mypy stays green).
    — **Why:** delete the first copy once the CLI owns the semantics; the drift guard is repo-specific and stays. **Regenerate poetry.lock in the SAME PR (arch F3 — the lock pins the wheel URL; all three CIs run `poetry install`): `python -m poetry lock` from the package dir after the pyproject bump (LEARNINGS precedent poetry-toolchain-bump-needs-lock-regen-in-same-pr).**
    — **Done when:** greps show no `registry_convergence.py` refs on LIVE surfaces (workflows/pyproject/docs/skills — LEARNINGS and PLANS are historical records, out of scope per arch F9); gates green (ruff/mypy/pytest per IFC contract).
    — **Consumers affected:** IFC dev/uat deploys.
- [ ] **3.2** CWN (`feat/DA-3086-cwn`): same surface, pin v0.30.0→new release, script at `fastapi_app/scripts/` — **CWN KEEPS `scripts/__init__.py`** (`scripts/register_nodes.py` remains: imported by tests/test_register_nodes.py:11, referenced .env.example:20).
    — **Why:** same rationale as 3.1 for the second copy; same poetry.lock regen requirement.
    — **Done when:** same bar with CWN gates.
    — **Consumers affected:** CWN deploys.
- [ ] **3.3** CRS (`feat/DA-3086-crs`): same surface, pin v0.28.1→v0.31.0.
    — **Why:** same rationale for the third copy (the one that fired the trigger); same poetry.lock regen. **Also (arch F4): update `.agents/skills/fastapi-node-scaffold/SKILL.md:58-60` — it teaches new repos to COPY the script being deleted (this is how copy #3 happened); replace with the SDK CLI venv + `registry-convergence` subcommand + trimmed drift-guard test. Evidence bump for LEARNINGS anti-pattern incomplete-deprecation-sweep-in-docs.**
    — **Done when:** same bar with CRS gates (ruff/mypy/pytest — no format gate).
    — **Consumers affected:** CRS deploys.

### Phase 4: Post-merge deploy evidence + Jira
- [ ] **4.1** Watch each repo's dev deploy for `convergence OK — staged N/N present in registry` (IFC 26, CWN 47, CRS 4); record run IDs on DA-3086; transition Done.
    — **Why:** the evidence bar — absorbed CLI behaves identically at deploy time.
    — **Done when:** three green deploys with the convergence line; ticket Done.
    — **Consumers affected:** none.

## Technical Notes
- The three workflow steps keep exporting `REGISTRY_SERVICE_TOKEN`; the CLI reads that env first (register's `CANVASTEKK_REGISTRY_TOKEN` is a separate contract — not changed in a minor release).
- `::error::` prints stay on stdout (GitHub parses workflow commands from stdout only).
- Repins also delete `scripts/__init__.py` if it becomes empty (CWN/CRS have it for the tests import).
- Release tags ride `chore(release): prepare vX.Y.Z` commits made by the bot on main; the wheel URL pattern in pyproject pins matches `/releases/download/vX.Y.Z/...`.
- If the release workflow's wheel asset name differs, fix the pin URLs before merging repins (gated on the actual asset).

## Dependencies
- DA-3070/DA-3071/DA-3084 (merged — the three copies being absorbed).
- CRS uat promotion is unrelated (repins target dev; uat picks up at its own cadence).

## Plan Revisions (arch review 2026-09-26, REQUEST-CHANGES disposition)
F1 IFC flag rewrite + gate wording · F2 wiring facts re-verified at origin/dev (all pins v0.30.0; CWN workflow URL v0.28.1 drift noted) · F3 poetry.lock regen in every repin PR · F4 CRS scaffold skill reseed fix · F5 exit-code/doc wording (no normalization) · F6 dispatch tests → test_cli_register.py · F7 CWN keeps scripts/__init__.py · F8 wheel content verification · F9 grep scoping.

## Risks & Mitigation
- Semantic drift in port → wholesale copy, tests ported 1:1, diff reviewed against reference.
- Release asset name mismatch → verify the asset before merging repins.
- venv reuse assumption breaks (register skips but convergence runs) → impossible: convergence's `if:` gates on `steps.register-nodes.outcome == 'success'`, which implies the venv step ran.
- Deploy red post-repin → bounded red-fix rounds per repo (2), runner has git+python3.
