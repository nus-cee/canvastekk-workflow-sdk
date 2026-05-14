# CanvasTEKK Workflow SDK

Multi-language SDK for building CanvasTEKK Workflow Engine nodes. Each language implementation is self-contained in its own directory.

## Available SDKs

| Language | Status | Package | Directory |
|----------|--------|---------|-----------|
| Python | Available | `canvastekk-workflow-sdk` | [`python/`](./python/) |
| TypeScript | Planned | — | `typescript/` |

## Quick Start

### Python

**Install from GitHub Packages:**

```bash
pip install canvastekk-workflow-sdk \
  --index-url https://pypi.pkg.github.com/nus-cee/
```

**Develop locally:**

```bash
cd python/
python3.12 -m venv .venv
source .venv/bin/activate
pip install poetry
poetry install
```

All commands (`poetry run pytest`, `poetry run ruff check`, etc.) run from `python/`.

See [`python/README.md`](./python/) for full documentation.

## Architecture

Each language SDK follows the same pattern:

```
<language>/
├── src/                  # SDK source code
├── tests/                # Test suite
├── <package-config>      # package.json, pyproject.toml, etc.
├── README.md             # Language-specific documentation
└── .github/workflows/    # CI/CD (in repo root)
```

### Adding a New Language

1. Create a new directory at the repo root (e.g., `typescript/`)
2. Initialize with language-appropriate package manager
3. Mirror the same API surface as existing SDKs:
   - `BaseNode` class with `execute()` method
   - `NodeDefinition` with schema validation
   - HTTP endpoints: `/execute`, `/health`, `/manifest`, `/hook`, `/metrics`
   - Error handling with structured error codes
4. Add CI workflow at `.github/workflows/ci-<lang>.yml`
5. Add publish workflow at `.github/workflows/publish-<lang>.yml`
6. Update this README with the new language entry

## Repository

[github.com/nus-cee/canvastekk-workflow-sdk](https://github.com/nus-cee/canvastekk-workflow-sdk)
