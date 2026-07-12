# PLAN: DA-1476 — Publish Python SDK to GitHub Packages PyPI Registry

**Ticket**: [DA-1476](https://betekk.atlassian.net/browse/DA-1476)
**Created**: 2026-07-12
**Status**: In Progress
**Branch**: `DA-1476`
**Labels**: backend, ci-cd, python, github-packages, publishing
**Priority**: Medium

---

## Overview

The TypeScript SDK is published to GitHub Packages npm registry (`npm.pkg.github.com`) on every release, but the Python SDK is only uploaded as a **GitHub Release asset** — it is **not** pushed to the GitHub Packages PyPI registry (`pypi.pkg.github.com/nus-cee/`). This means consumers cannot `pip install canvastekk-workflow-sdk` despite the AGENTS.md and README stating they can. The post-publish verify step (release.yml:144-173) attempts this install but has `continue-on-error: true`, so it silently fails.

Additionally, GitHub Packages PyPI requires authentication even for installing public packages — meaning the documented consumer install commands are broken even after publishing is added. This plan addresses both the publishing pipeline AND the consumer-facing documentation.

## Dependency & Consumer Map

| Consumer / Dependency | Impact |
|---|---|
| **release.yml pipeline** | New publish step + pre-publish smoke test changes release flow; verify step becomes blocking |
| **Python SDK consumers** | Package becomes available via `pip install` (requires PAT with `read:packages` scope) |
| **AGENTS.md / README / EXTERNAL-AUTHOR-GUIDE** | Docs must reflect auth requirement for `pip install` — all current install commands omit credentials |
| **Node template AGENTS.md** (`python/.../templates/AGENTS.md`) | Generated node projects reference the install command — must include auth |
| **TypeScript SDK publish step** | Also has `continue-on-error: true` (release.yml:197) — parity gap acknowledged but out of scope for this ticket (see Phase 6) |

---

## Problem Analysis

### Current Pipeline Behavior

| SDK | Build | Registry Publish | Verify |
|---|---|---|---|
| TypeScript | `npm run build` | `npm publish` → `npm.pkg.github.com` (release.yml:195-201) | **Silent failure** — `continue-on-error: true` (release.yml:197) |
| Python | `poetry build` (wheel) | **None** — only `gh release upload` as asset (release.yml:142) | **Silent failure** — `continue-on-error: true` (release.yml:146) |

> **Note (M3 finding):** The TypeScript publish step also has `continue-on-error: true` at release.yml:197. Both SDKs silently swallow publish failures. This PLAN scopes to Python (Phase 1-5) and flags the TypeScript parity gap as a follow-up (Phase 6).

### Root Cause

Two distinct gaps:

1. **Publishing gap:** The `[[tool.poetry.source]]` block in `python/pyproject.toml:15-18` configures GitHub Packages as a **dependency source** (pull), but the release pipeline never calls `poetry publish` (push). Crucially, `[[tool.poetry.source]]` is NOT a publish repository — Poetry has separate concepts for dependency sources vs publish targets. The pipeline builds the wheel and uploads it as a downloadable release asset, but that is NOT the same as publishing to the PyPI registry.

2. **Consumer auth gap:** GitHub Packages PyPI requires authentication for `pip install` even for public packages (unlike npm). All documented install commands across the repo omit credentials, so even after publishing, consumers get HTTP 401.

> **Prior failure evidence:** CHANGELOG.md v0.4.6 (2026-05-14) contains `release: Configure poetry publish repository URL for GitHub Packages`, indicating a prior attempt that was subsequently removed — confirming this configuration is non-trivial.

### Documentation vs Reality Gap

- **AGENTS.md** states: "The released wheel is published to GitHub Packages at `https://pypi.pkg.github.com/nus-cee/`" — this is currently **inaccurate**
- **README/AGENTS.md** instructs consumers: `pip install canvastekk-workflow-sdk --index-url https://pypi.pkg.github.com/nus-cee/` — this **does not work** (no publish + no auth)
- All files with broken `pip install` commands:

| File | Lines | Issue |
|---|---|---|
| `README.md` | 128 | No auth credentials |
| `AGENTS.md` | 52 | No auth credentials |
| `docs/EXTERNAL-AUTHOR-GUIDE.md` | 38, 228, 421 | No auth credentials (including CI workflow examples) |
| `python/README.md` | 13, 68 | No auth credentials |
| `python/.../templates/AGENTS.md` | 19 | No auth credentials |

---

## Phase 1: Add `poetry publish` Step to Release Pipeline

**CRITICAL** — This is the core fix: push the built wheel to the GitHub Packages PyPI registry.

- [x] **1.1** Pin Poetry version in the "Install Poetry" step
  - **Why:** Poetry's repository/source configuration behavior has changed across versions (the `priority` field was introduced in 1.5; source vs repository separation was formalized in 1.8+). `release.yml:53` runs `pip install poetry` with no constraint — an unpinned install could get Poetry 2.x with breaking changes. The publish configuration commands in this plan are tested against Poetry 1.8.x
  - **Done when:** `release.yml:53` reads `pip install poetry==1.8.5` (or equivalent pinned version)
  - **Consumers affected:** Release pipeline reproducibility
  - **File:** `.github/workflows/release.yml:53`

- [x] **1.2** Add "Publish Python SDK to GitHub Packages" step with explicit repository configuration
  - **Why:** The wheel is built (release.yml:121) and uploaded as a release asset (release.yml:142), but never pushed to the registry. However, `poetry publish --repository github` will fail with "Repository github is not defined" because `[[tool.poetry.source]]` in `pyproject.toml` is a **dependency source**, not a **publish repository**. Poetry requires a separate `poetry config repositories.<name> <url>` command to register a publish target. The env vars (`POETRY_HTTP_BASIC_GITHUB_USERNAME` / `POETRY_HTTP_BASIC_GITHUB_PASSWORD`) are correct but only work once the repository is registered
  - **Done when:** The release pipeline (1) registers the publish repository via `poetry config repositories.github`, (2) calls `poetry publish --repository github` with `GITHUB_TOKEN` auth, and (3) the package appears in the GitHub Packages PyPI registry after a release
  - **Consumers affected:** All Python SDK consumers who `pip install` from GitHub Packages
  - **File:** `.github/workflows/release.yml` — insert after line 142 (after `gh release upload`)
  - **Proposed code:**
    ```yaml
          - name: Publish Python SDK to GitHub Packages
            if: steps.git-cliff.outputs.version != '' && hashFiles('python/pyproject.toml') != ''
            working-directory: python
            env:
              POETRY_HTTP_BASIC_GITHUB_USERNAME: "nus-cee"
              POETRY_HTTP_BASIC_GITHUB_PASSWORD: ${{ secrets.GITHUB_TOKEN }}
            run: |
              # Register GitHub Packages as a publish repository.
              # NOTE: [[tool.poetry.source]] in pyproject.toml is a dependency *source*,
              # NOT a publish target. Poetry requires this explicit config for publishing.
              poetry config repositories.github "https://pypi.pkg.github.com/nus-cee/"

              # Publish wheel already built in dist/ from the previous step.
              poetry publish --repository github
    ```

---

## Phase 2: Add Pre-Publish Local Smoke Test

**CRITICAL** — GitHub Packages PyPI does not support version deletion. If publish succeeds but the post-publish verify fails, the broken version is permanently orphaned. This phase adds a local smoke test BEFORE the irreversible publish step.

- [x] **2.1** Add pre-publish import smoke test from local wheel
  - **Why:** The existing wheel symbol verification (release.yml:123-136) checks that expected symbols exist in the wheel's `definition.py`, but it does not test that the wheel actually installs and imports in a clean environment. A local `pip install dist/*.whl` + import check catches packaging errors (missing dependencies, broken imports, namespace issues) before the irreversible `poetry publish` step
  - **Done when:** A new step creates a clean virtualenv, installs the wheel from `dist/*.whl`, and runs the same import check as the post-publish verify — all BEFORE `poetry publish`. If this fails, the pipeline stops before publishing
  - **Consumers affected:** Release pipeline — prevents broken versions from being published
  - **File:** `.github/workflows/release.yml` — insert between line 142 (release upload) and the new publish step from Phase 1.2
  - **Proposed code:**
    ```yaml
          - name: Pre-publish smoke test (local wheel install)
            if: steps.git-cliff.outputs.version != '' && hashFiles('python/pyproject.toml') != ''
            working-directory: python
            run: |
              python3 -m venv /tmp/pre-publish-venv
              WHEEL_FILE=$(ls dist/*.whl)
              /tmp/pre-publish-venv/bin/pip install "${WHEEL_FILE}"

              /tmp/pre-publish-venv/bin/python -c "
              from canvastekk_workflow_sdk import (
                  WorkflowNodeManifest, WorkflowNodeStyles, WorkflowNodeRole,
                  RetryConfig, BaseNode, ExecutionContext,
              )
              from canvastekk_workflow_sdk.workflow.models import (
                  WorkflowDefinitionNode, WorkflowEdgeDefinition, WorkflowDefinitionSpec,
              )
              print('Pre-publish smoke test passed: wheel installs and imports correctly')
              "
    ```

---

## Phase 3: Fix Post-Publish Verify Step

**HIGH** — The existing verify step silently fails. Once publishing works, the verify should actually run, authenticate, and catch regressions — with retry logic for propagation latency.

- [x] **3.1** Remove `continue-on-error: true` from the Python post-publish verify step
  - **Why:** The verify step (release.yml:144-173) attempts `pip install canvastekk-workflow-sdk` but has `continue-on-error: true` (release.yml:146), so it silently fails. Once Phase 1 publishes the package, the verify should actually enforce success
  - **Done when:** `continue-on-error: true` is removed from the "Verify published wheel" step. If the install or import check fails, the release pipeline fails
  - **Consumers affected:** Release pipeline — catches publishing/import regressions
  - **File:** `.github/workflows/release.yml:146`

- [x] **3.2** Add authentication and retry logic to verify step `pip install`
  - **Why:** GitHub Packages PyPI requires authentication even for public packages. The current verify step (release.yml:156-158) passes `--index-url` but no credentials — GitHub returns 401. Additionally, GitHub Packages may have propagation latency between `poetry publish` and `pip install` availability. The fix uses credentials embedded in the index URL (the standard GitHub Actions pattern for pip + GitHub Packages) with a retry loop for propagation delay
  - **Done when:** The verify step's `pip install` uses `https://nus-cee:${GITHUB_TOKEN}@pypi.pkg.github.com/nus-cee/` as the index URL, includes `GITHUB_TOKEN` in the step's `env:` block, and retries up to 3 times with 10s sleep between attempts
  - **Consumers affected:** Release pipeline verify step
  - **File:** `.github/workflows/release.yml:144-173`
  - **Proposed code changes:**
    ```yaml
          - name: Verify published wheel (post-publish smoke test)
            if: steps.git-cliff.outputs.version != '' && hashFiles('python/pyproject.toml') != ''
            # NOTE: continue-on-error removed — verify is now blocking
            env:
              NEW_VERSION: ${{ steps.git-cliff.outputs.version }}
              GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
            run: |
              VERSION_NUM="${NEW_VERSION#v}"

              # Create clean virtualenv
              python3 -m venv /tmp/verify-venv

              # Install from GitHub Packages with auth + retry for propagation latency
              # GitHub Packages PyPI requires credentials even for public packages
              INDEX_URL="https://nus-cee:${GITHUB_TOKEN}@pypi.pkg.github.com/nus-cee/"
              for i in 1 2 3; do
                /tmp/verify-venv/bin/pip install \
                  "canvastekk-workflow-sdk==${VERSION_NUM}" \
                  --index-url "${INDEX_URL}" && break
                echo "Attempt $i failed, retrying in 10s..."
                sleep 10
              done

              # Verify all canonical names import correctly from published wheel
              /tmp/verify-venv/bin/python -c "
              from canvastekk_workflow_sdk import (
                  WorkflowNodeManifest, WorkflowNodeStyles, WorkflowNodeRole,
                  RetryConfig, BaseNode, ExecutionContext,
              )
              from canvastekk_workflow_sdk.workflow.models import (
                  WorkflowDefinitionNode, WorkflowEdgeDefinition, WorkflowDefinitionSpec,
              )
              print('Post-publish verification passed: all canonical names resolve correctly')
              "
    ```

---

## Phase 4: Documentation Alignment — Consumer Auth Requirements

**HIGH** — Publishing alone does not achieve the PLAN's stated goal. GitHub Packages PyPI requires authentication for `pip install` even for public packages. ALL consumer-facing documentation must be updated to include auth instructions, or the gap remains open.

- [x] **4.1** Add consumer authentication setup section to `README.md`
  - **Why:** Consumers following current docs get HTTP 401. GitHub Packages PyPI requires a PAT with `read:packages` scope even for public packages. This is fundamentally different from npm GitHub Packages (where public packages install without a token after registry config). The README must prominently document this requirement
  - **Done when:** `README.md` includes a section explaining: (1) Create a GitHub PAT with `read:packages` scope, (2) Configure pip with the PAT via `.netrc` or URL-embedded credentials, (3) This is required even though the package is public
  - **Consumers affected:** All Python SDK consumers
  - **File:** `README.md`

- [x] **4.2** Update ALL `pip install` commands across docs to include authentication
  - **Why:** Every documented `pip install` command omits credentials. After publishing, consumers will get 401 errors. The correct pattern embeds credentials in the index URL or uses a `.netrc` file
  - **Done when:** All `pip install` commands in the following files are updated to include auth:

    | File | Lines | Current (broken) | Fixed |
    |---|---|---|---|
    | `README.md` | 128 | `--index-url https://pypi.pkg.github.com/nus-cee/` | Include auth instructions + correct command |
    | `AGENTS.md` | 52 | Same | Same fix |
    | `docs/EXTERNAL-AUTHOR-GUIDE.md` | 38, 228, 421 | Same (including CI workflow examples) | Include `${{ secrets.GITHUB_TOKEN }}` in CI examples |
    | `python/README.md` | 13, 68 | Same | Same fix |
    | `python/.../templates/AGENTS.md` | 19 | Same | Same fix (generated node projects inherit this) |

  - **Standard install command (documented form):**
    ```bash
    # Option A: URL-embedded credentials (quick start)
    pip install canvastekk-workflow-sdk \
      --index-url https://USERNAME:TOKEN@pypi.pkg.github.com/nus-cee/

    # Option B: .netrc file (recommended for repeated use)
    # Add to ~/.netrc:
    # machine pypi.pkg.github.com
    #   login USERNAME
    #   password TOKEN
    pip install canvastekk-workflow-sdk \
      --index-url https://pypi.pkg.github.com/nus-cee/
    ```
  - **CI workflow pattern (for EXTERNAL-AUTHOR-GUIDE.md):**
    ```yaml
    - run: pip install canvastekk-workflow-sdk --index-url https://nus-cee:${{ secrets.GITHUB_TOKEN }}@pypi.pkg.github.com/nus-cee/
    ```

  - **Consumers affected:** All SDK consumers reading installation docs

- [x] **4.3** Verify AGENTS.md publishing claims are accurate after pipeline change
  - **Why:** AGENTS.md states "The released wheel is published to GitHub Packages at `https://pypi.pkg.github.com/nus-cee/`". After Phase 1, this becomes true. Verify no other doc references need updating
  - **Done when:** AGENTS.md accurately describes the Python package as available via authenticated `pip install` from GitHub Packages
  - **Consumers affected:** All SDK consumers reading installation docs

---

## Phase 5: Local Dry-Run Validation

**MEDIUM** — Validate the publish command works before the first real release.

- [x] **5.1** Test `poetry publish --dry-run` with explicit repository configuration
  - **Why:** GitHub Packages PyPI has quirks (first publish claims the name, version immutability). A dry-run confirms the Poetry configuration and auth env vars are correct before the first real release encounters a failure. This must include the `poetry config repositories.github` command — not just the `pyproject.toml` source
  - **Done when:** The following sequence succeeds locally (with a test PAT):
    ```bash
    cd python
    poetry config repositories.github "https://pypi.pkg.github.com/nus-cee/"
    POETRY_HTTP_BASIC_GITHUB_USERNAME="nus-cee" \
    POETRY_HTTP_BASIC_GITHUB_PASSWORD="<test-pat>" \
    poetry publish --dry-run --repository github
    ```
  - **Consumers affected:** None — dry-run only
  - **Note:** No `poetry.toml` exists in the repo — no override risk from local Poetry config. The only repository configuration comes from the explicit `poetry config` command and the `[[tool.poetry.source]]` in `pyproject.toml` (which is a dependency source, not a publish target)

---

## Phase 6: Deferred — TypeScript Publish Parity (Follow-up Ticket)

**LOW** — The TypeScript publish step (release.yml:197) also has `continue-on-error: true`, meaning TS publish failures are also silently swallowed. This is out of scope for DA-1476 (Python-only) but should be tracked.

- [x] **6.1** Create follow-up ticket for TypeScript publish `continue-on-error` removal
  - **Why:** Parity — both SDKs should have blocking publish verification. However, removing `continue-on-error` from the TS step requires verifying that TS publish currently works reliably (it has been live longer than the Python publish will be)
  - **Done when:** Follow-up JIRA ticket created referencing DA-1476, scoped to evaluating and removing `continue-on-error: true` from release.yml:197
  - **Consumers affected:** Release pipeline TS publishing

---

## Files Changed

| File | Change | Phase |
|---|---|---|
| `.github/workflows/release.yml:53` | Pin Poetry version (`pip install poetry==1.8.5`) | 1.1 |
| `.github/workflows/release.yml` (~line 142) | Add pre-publish local smoke test step | 2.1 |
| `.github/workflows/release.yml` (~line 142) | Add `poetry config repositories.github` + `poetry publish` step | 1.2 |
| `.github/workflows/release.yml:146` | Remove `continue-on-error: true` from verify step | 3.1 |
| `.github/workflows/release.yml:144-173` | Add auth + retry logic to verify `pip install` | 3.2 |
| `README.md` | Add consumer auth setup section + fix install command | 4.1, 4.2 |
| `AGENTS.md` | Fix install command with auth | 4.2 |
| `docs/EXTERNAL-AUTHOR-GUIDE.md` | Fix install commands with auth + CI token pattern | 4.2 |
| `python/README.md` | Fix install commands with auth | 4.2 |
| `python/.../templates/AGENTS.md` | Fix install command with auth | 4.2 |

---

## Acceptance Criteria

### Publishing
- [x] Poetry version is pinned in the release pipeline
- [x] Release pipeline registers publish repository via `poetry config repositories.github`
- [x] Release pipeline calls `poetry publish --repository github` after building the wheel
- [ ] Python wheel appears in GitHub Packages PyPI registry (`pypi.pkg.github.com/nus-cee/`) after a release

### Pre-publish Safety
- [x] Pre-publish local smoke test installs wheel from `dist/*.whl` and verifies imports
- [x] Pre-publish smoke test runs BEFORE `poetry publish` (blocks on failure)

### Post-publish Verify
- [x] `continue-on-error: true` removed from Python verify step
- [x] Verify step authenticates to GitHub Packages using embedded credentials
- [x] Verify step retries on propagation delay (up to 3 attempts)
- [x] Verify step fails the pipeline on import errors

### Consumer Documentation
- [x] README.md documents PAT requirement with `read:packages` scope
- [x] All `pip install` commands across 5+ doc files include authentication
- [x] CI workflow examples in EXTERNAL-AUTHOR-GUIDE.md use `${{ secrets.GITHUB_TOKEN }}`
- [x] `pip install canvastekk-workflow-sdk` works for consumers following documented instructions (both GitHub Packages and Release asset methods documented)

### Validation
- [x] `poetry publish --dry-run` succeeds locally (with explicit `poetry config repositories.github`)

---

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| **First publish "claims" the package name** — GitHub Packages PyPI doesn't support version deletion/re-publish | Phase 2 pre-publish smoke test catches broken wheels before the irreversible publish step. Phase 5 dry-run validates config. Ensure version is correct before merge |
| **`poetry publish` fails with "Repository not defined"** — `[[tool.poetry.source]]` is a dependency source, not a publish target | Phase 1.2 explicitly registers the publish repository via `poetry config repositories.github "https://pypi.pkg.github.com/nus-cee/"` before calling `poetry publish`. Prior failure at v0.4.6 confirms this is non-trivial |
| **`GITHUB_TOKEN` auth fails for `poetry publish`** — GitHub Packages requires username = org name | Use `POETRY_HTTP_BASIC_GITHUB_USERNAME: "nus-cee"` and `POETRY_HTTP_BASIC_GITHUB_PASSWORD: ${{ secrets.GITHUB_TOKEN }}`. These env vars are correct once repository is registered via `poetry config` |
| **Verify step `pip install` fails with 401** — GitHub Packages PyPI requires auth for public packages | Phase 3.2 embeds credentials in index URL: `https://nus-cee:${GITHUB_TOKEN}@pypi.pkg.github.com/nus-cee/`. `GITHUB_TOKEN` added to verify step `env:` block |
| **Publish succeeds but verify fails** — broken version is permanently in registry | Phase 2 pre-publish local smoke test catches packaging errors before the irreversible step. If post-publish verify still fails, a new version must be bumped and re-published (the broken version remains orphaned — documented as a GitHub Packages limitation) |
| **Verify step starts failing CI** — removing `continue-on-error: true` makes verify blocking | This is intentional — the verify SHOULD be blocking. Phase 3.2 retry logic handles propagation latency. If it fails after retries, it indicates a real publishing or import regression |
| **GitHub Packages PyPI propagation delay** — `pip install` may not find the package immediately after publish | Phase 3.2 adds retry loop (3 attempts, 10s sleep). If still failing, propagation issue is a GitHub infra problem |
| **Poetry version drift changes behavior** — unpinned `pip install poetry` could install 2.x with breaking changes | Phase 1.1 pins to `poetry==1.8.5`. All config commands in this plan are validated against Poetry 1.8.x |
| **Consumers still get 401 after docs update** — PAT not configured locally | Phase 4.1 prominently documents the PAT requirement. Phase 4.2 provides both URL-embedded (quick start) and `.netrc` (recommended) patterns |

---

## Architecture Review Findings

| ID | Severity | Finding | Resolution |
|---|---|---|---|
| C1 | Critical | `[[tool.poetry.source]]` is NOT a publish repository — `poetry publish --repository github` would fail | Phase 1.2 adds `poetry config repositories.github` before publish |
| C2 | Critical | GitHub Packages PyPI requires auth for `pip install` — all consumer docs broken | Phase 4 (expanded) documents PAT requirement + fixes all install commands |
| M1 | Major | Missing Dependency & Consumer Map | Added after Overview |
| M2 | Major | Phase 2.2 (now 3.2) listed 3 auth options without committing to one | Phase 3.2 now specifies embedded credentials in index URL |
| M3 | Major | TypeScript publish also has `continue-on-error: true` — Problem Analysis table was inaccurate | Table corrected; Phase 6 creates follow-up ticket for TS parity |
| M4 | Major | No rollback strategy for publish-succeeds/verify-fails | Phase 2 adds pre-publish local smoke test before irreversible publish |
| M5 | Major | Poetry version unpinned | Phase 1.1 pins to `poetry==1.8.5` |
| m1 | Minor | Notes linked to Maven docs instead of PyPI docs | Removed incorrect link; GitHub has no dedicated PyPI registry doc page |
| m2 | Minor | Phase 4.2 checked for `poetry.toml` that doesn't exist | Phase 5.1 notes no `poetry.toml` exists — no override risk |
| m3 | Minor | `poetry publish` may rebuild wheel | Phase 1.2 adds comment: "Publish wheel already built in dist/" |
| R1 | Recommendation | Consider `twine` instead of `poetry publish` for GitHub Packages | Evaluated — keeping `poetry publish` for tooling consistency (pipeline already uses Poetry). `twine` is the fallback if publish issues persist after dry-run validation |
| R2 | Recommendation | Add retry logic for verify step | Implemented in Phase 3.2 (3 attempts, 10s sleep) |
| R3 | Recommendation | Document consumer auth requirement prominently | Implemented in Phase 4.1 (dedicated README section for PAT setup) |

---

## Notes

- This repo uses **automated semantic versioning via git-cliff** — do NOT manually bump versions
- **Commit type**: `feat(ci):` — this adds a new publishing capability (minor bump per `cliff.toml`)
- **Poetry source vs repository:** `[[tool.poetry.source]]` in `pyproject.toml` configures dependency resolution (pull). `poetry config repositories.<name> <url>` configures publishing (push). These are separate concepts — the PLAN's Phase 1.2 adds the publish configuration explicitly
- TypeScript SDK publishing (release.yml:195-201) serves as a partial reference pattern, but npm and PyPI GitHub Packages have different auth models (npm public packages install without token; PyPI requires auth always)
- The wheel symbol verification step (release.yml:123-136) that checks for expected symbols should remain as-is — it validates the wheel before the pre-publish smoke test
- No `poetry.toml` exists in the repo — no local override risk for repository configuration
- GitHub Packages PyPI has no dedicated documentation page (unlike npm/Maven). Configuration requires community knowledge and the patterns documented in this PLAN
