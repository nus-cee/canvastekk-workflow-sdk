# PLAN — DA-881: Add automatic semantic versioning for Python SDK

**Branch:** `DA-881`
**Jira:** [DA-881](https://betekk.atlassian.net/browse/DA-881)
**Repo:** https://github.com/nus-cee/canvastekk-workflow-sdk

---

## Phase 1: Setup & Configuration

- [x] Create `cliff.toml` at repo root (adapted from ibis-workflow-nodes)
- [x] Configure `tag_pattern = "python-v[0-9].*"` to avoid conflicts with future language SDKs
- [x] Configure conventional commit parsers (feat, fix, perf, refactor, doc, style, test, chore, ci, build)

## Phase 2: Release Workflow

- [x] Create `.github/workflows/release-python.yml` matching ibis-workflow-nodes pattern
- [x] Trigger on push to `main` when `python/**` paths are affected
- [x] Use `orhun/git-cliff-action@v4` for changelog generation + version bump detection
- [x] Bump version in `python/pyproject.toml` via Python script (PEP 440 validation)
- [x] Commit version bump + changelog, tag as `python-v*`, push
- [x] Create GitHub Release with changelog notes
- [x] The existing `publish-python.yml` triggers on the new `python-v*` tag

## Phase 3: Documentation

- [ ] Document release process in `python/README.md`
- [ ] Document conventional commit requirements

## Phase 4: Testing & Validation

- [ ] Verify workflow triggers correctly on merge to main affecting python/
- [ ] Verify `python-v*` tag is created
- [ ] Verify `publish-python.yml` is triggered by the tag

---

## Flow

```
Commit with conventional prefix (feat:/fix:/etc) merged to main
  → release-python.yml triggers (paths: python/**)
    → git-cliff analyzes commits since last python-v* tag
    → Determines next version (major/minor/patch)
    → Bumps version in python/pyproject.toml
    → Generates python/CHANGELOG.md
    → Commits, tags python-v*, pushes
      → publish-python.yml triggers on python-v* tag
        → Builds and publishes to GitHub Packages
```
