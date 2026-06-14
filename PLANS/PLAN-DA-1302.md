# PLAN: DA-1302 — Release Pipeline Guardrails + v0.15.1 Patch

**Ticket**: [DA-1302](https://betekk.atlassian.net/browse/DA-1302)
**Created**: 2026-06-14
**Status**: In Progress

---

## Overview

Hardened the release pipeline to prevent stale wheel artifacts and shipping a v0.15.1 patch release with the pipeline guardrails in place.

## Phase 0: Root Cause Investigation (Completed)

### Finding: v0.15.0 Wheel is NOT Stale

**The original diagnosis was incorrect.** The published v0.15.0 GitHub Release wheel is correct and contains all renamed classes and aliases.

| Check | Result |
|---|---|
| GitHub Actions run for v0.15.0 | Run `27214328102` — triggered by `f5bb04e` (rename commit) |
| Wheel built from tagged commit | Yes — `9d715e5` (release commit, includes `f5bb04e` renames) |
| Published wheel SHA256 | `82797668299985a8c7d04ea7d5e91360431e6beeb3eecd82d64627520766ea9e` |
| Local build SHA256 (from `main`) | `82797668299985a8c7d04ea7d5e91360431e6beeb3eecd82d64627520766ea9e` |
| **Match?** | **YES — wheels are identical** |
| `WorkflowNodeManifest` in published wheel | Present |
| `WorkflowNodeStyles` in published wheel | Present |
| `WorkflowNodeRole` in published wheel | Present |
| All backward-compat aliases | Present |

### Consumer Issue Likely Caused By

Since the wheel is correct, the consumer `ImportError` was most likely caused by:
- Stale Poetry/pip cache serving an older resolved version
- Lock file pinning an older resolution
- Virtualenv not refreshed after SDK upgrade

Regardless, the pipeline guardrails below are still valuable preventive measures.

- [x] Check GitHub Actions run history for the v0.15.0 release
- [x] Identify which workflow run produced the wheel and at what commit SHA
- [x] Download and verify published wheel contents
- [x] Compare published wheel SHA256 against local build
- [x] Document findings

## Phase 1: Verify Source Correctness (Completed)

- [x] `definition.py` defines `WorkflowNodeManifest` (line 96), `WorkflowNodeStyles` (line 47), `WorkflowNodeRole` (line 89)
- [x] Backward-compat aliases present (lines 353-356):
  ```python
  NodeDefinition = WorkflowNodeManifest
  WorkflowNodeDefinition = WorkflowNodeManifest
  NodeStyles = WorkflowNodeStyles
  NodeRole = WorkflowNodeRole
  ```
- [x] `__init__.py` imports and exports both old and new names
- [x] `__all__` includes both old and new names
- [x] `__version__ = "0.15.0"`

### Full Alias Surface (7 aliases across 2 modules)

| Alias | Canonical Name | Module |
|---|---|---|
| `NodeDefinition` | `WorkflowNodeManifest` | `definition.py` |
| `WorkflowNodeDefinition` | `WorkflowNodeManifest` | `definition.py` |
| `NodeStyles` | `WorkflowNodeStyles` | `definition.py` |
| `NodeRole` | `WorkflowNodeRole` | `definition.py` |
| `WorkflowNode` | `WorkflowDefinitionNode` | `workflow/models.py` |
| `WorkflowEdge` | `WorkflowEdgeDefinition` | `workflow/models.py` |
| `WorkflowSpec` | `WorkflowDefinitionSpec` | `workflow/models.py` |

## Phase 2.5: Fix Release Pipeline Defects (Completed)

Hardened `release.yml` to prevent stale wheel artifacts from shipping in the future.

- [x] Add `rm -rf dist/` before `poetry build` — prevents stale artifacts from previous builds
- [x] Add `--clobber` flag to `gh release upload` — ensures correct upload replaces any stale asset
- [x] Add commit SHA assertion before build — verifies `git rev-parse HEAD` matches the tagged commit
- [x] Add pre-upload wheel content verification — checks `definition.py` in wheel for expected symbols before upload
- [x] Add wheel SHA256 hash as `.sha256` release asset for provenance attestation
- [x] Add post-publish verification step — installs from GitHub Packages, tests all 7 aliases
- [ ] Pin `actions/checkout` to a SHA digest for supply-chain hardening _(deferred — requires manual SHA lookup)_

## Phase 2: Publish v0.15.1 (Automated via Pipeline)

> The release is fully automated by `.github/workflows/release.yml` using git-cliff with conventional commits. Version bump, tagging, wheel build, and GitHub release creation are ALL handled by the pipeline — no manual version editing. See AGENTS.md → "Versioning & Releases".

**Commit and push** (triggers the pipeline):
- [x] Phase 2.5 fixes committed to `release.yml`
- [x] Phase 5 echo_node canonical name fix committed
- [ ] Commit with `fix:` type so git-cliff bumps to patch (0.15.0 → 0.15.1):
  ```
  fix(ci): add release pipeline guardrails and canonical name fix [DA-1302]
  ```
- [ ] Push to `main` — pipeline auto-detects `fix:` commit and determines v0.15.1

**Pipeline auto-executes on push to main** (no manual intervention):
1. git-cliff determines v0.15.1 from `fix:` commit type
2. Auto-bumps ALL version files (`pyproject.toml`, `__init__.py`, `package.json`, `Directory.Build.props`)
3. Auto-commits, auto-tags `v0.15.1`, auto-pushes
4. Creates GitHub Release v0.15.1 with changelog notes
5. Builds wheel with pre-upload content verification
6. Generates SHA256 hash, uploads wheel + `.sha256` (with `--clobber`)
7. Post-publish smoke test: installs from GitHub Packages and verifies all 7 aliases

**Post-release (manual consumer-side)**:
- [ ] Verify pipeline succeeded
- [ ] Update `canvastekk-workflow-nodes` `pyproject.toml` to `v0.15.1`

## Phase 3: Verify Published Wheel

### 3.1 Wheel Integrity

- [ ] Download published wheel and compare SHA256 against locally built wheel — must match
- [ ] Verify wheel METADATA: `Name`, `Version`, `Requires-Python` match `pyproject.toml`

### 3.2 Fresh Install & Import Verification

- [ ] Fresh `pip install` from GitHub release URL in a clean virtualenv
- [ ] `from canvastekk_workflow_sdk import WorkflowNodeManifest` works
- [ ] `from canvastekk_workflow_sdk.definition import WorkflowNodeStyles, RetryConfig` works
- [ ] All 7 backward-compat aliases resolve (definition + workflow models)

### 3.3 Consumer Verification

- [ ] Consumer repo (`canvastekk-workflow-nodes`) passes test collection
- [ ] mypy errors in `canvastekk-workflow-nodes` resolved

### Consumer Enumeration

- [ ] `canvastekk-workflow-nodes` — 59 mypy errors, broken test collection
- [ ] `canvastekk-workflow-engine` — check for new-name imports
- [ ] `canvastekk-floor-flatness-app` — check for new-name imports

## Phase 5: Update Reference Example (Completed)

- [x] Update `examples/echo_node/handler.py` to import canonical name `WorkflowNodeManifest` instead of old alias `NodeDefinition`

---

## Rollback Plan

v0.15.0 remains available. If v0.15.1 introduces a regression, consumers can downgrade to v0.15.0 and use old alias names.

## Dependencies

- **Origin**: [DA-1230](https://betekk.atlassian.net/browse/DA-1230) — SDK model renames (commit `f5bb04e`)
- **Affected**: [DA-1299](https://betekk.atlassian.net/browse/DA-1299) — workflow-nodes env var documentation
- **Affected**: `canvastekk-workflow-nodes` — 59 mypy errors, broken test collection

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Release pipeline defect recurs | Phase 2.5 guardrails: `rm -rf dist/`, `--clobber`, pre-upload verification, commit SHA assertion, post-publish smoke test |
| Consumer stale cache serves old wheel | v0.15.1 version bump forces cache invalidation |
| Rollback needed | v0.15.0 preserved as fallback |

## Success Metrics

- Root cause documented: v0.15.0 wheel verified correct (Phase 0)
- Release pipeline hardened with 6 guardrails (Phase 2.5)
- v0.15.1 published with pipeline auto-verification
- Zero `ImportError` across consumer repos after upgrade
- All 7 backward-compat aliases resolve from published wheel
- Wheel SHA256 hash published as provenance attestation
