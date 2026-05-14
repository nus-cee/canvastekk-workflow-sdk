# PLAN — DA-876: Restructure canvastekk-workflow-sdk as polyglot monorepo

**Branch:** `DA-876`
**Jira:** [DA-876](https://betekk.atlassian.net/browse/DA-876)
**Repo:** https://github.com/nus-cee/canvastekk-workflow-sdk

---

## Phase 1: Repo Restructuring — DA-880

- [x] Move `canvastekk_workflow_sdk/`, `tests/`, `pyproject.toml`, `poetry.lock`, `README.md` into `python/`
- [x] Create root `README.md` as monorepo overview with links to per-language SDKs
- [x] Update `pyproject.toml` with repository URL and GitHub Packages source config
- [x] Verify `poetry run pytest` passes from `python/` (166/166 passed)
- [x] Verify `poetry run ruff check canvastekk_workflow_sdk/ tests/` passes from `python/`

## Phase 2: GitHub Packages Publishing — DA-877

- [x] Create `.github/workflows/publish-python.yml`
- [x] Configure trigger on `python-v*` tags
- [x] Build with Poetry, publish to `https://pypi.pkg.github.com/nus-cee/`
- [x] Use `GITHUB_TOKEN` for authentication

## Phase 3: CI/CD Pipeline — DA-878

- [x] Create `.github/workflows/ci-python.yml`
- [x] Trigger on PRs/pushes to `main` affecting `python/`
- [x] Run ruff linting + pytest, Python 3.12

## Phase 4: Future Language Support Preparation — DA-879

- [x] Document folder structure convention in root README
- [x] Document self-contained structure per language
- [x] Add TypeScript placeholder mention

---

## Target Structure

```
canvastekk-workflow-sdk/
├── python/
│   ├── canvastekk_workflow_sdk/
│   ├── tests/
│   ├── pyproject.toml
│   ├── poetry.lock
│   └── README.md
├── typescript/                    # Future
├── .github/
│   └── workflows/
│       ├── publish-python.yml
│       └── ci-python.yml
├── README.md
└── PLANS/
    └── PLAN-DA-876.md
```
