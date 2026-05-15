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

## Utilities

### CLI Manifest Validation

Node authors can validate their node definition offline without starting the server:

```bash
# Validate a node definition
python -m canvastekk_workflow_sdk validate my_node.handler:definition

# Structured JSON output for CI
python -m canvastekk_workflow_sdk validate my_node.handler:definition --json

# Exit codes: 0 = valid, 1 = validation errors
```

The validator checks:
- `format: "file"` enforcement (rejects `format: "binary"`)
- File fields use `type: "string"` (not `"object"` or `"array"`)
- Warns on file fields missing `x-accept` or `x-maxSizeBytes` extensions

## Examples

| Example | Directory | Description |
|---------|-----------|-------------|
| Echo Node | [`examples/echo_node/`](./examples/echo_node/) | Minimal node with file input/output, presigned URL download, and `validate_file_input()` usage |

## Architecture Decisions

Key decisions recorded as the SDK evolves. See [`PLANS/PLAN-DA-894.md`](./PLANS/PLAN-DA-894.md) for full context on the file pipeline migration.

### v0.6.0 — File Pipeline Migration (DA-894)

| Decision | Rationale |
|----------|-----------|
| `format: "binary"` replaced with `format: "file"` | Aligns with engine (DA-889) presigned URL pipeline. `binary` implied multipart upload; `file` correctly describes "this field receives a URL string" |
| Hard break — no backward compat | Not in production yet. Dual detection adds complexity for zero benefit |
| `httpx` promoted to runtime dependency | Replaces `urllib.request` in `uploads.py` and `registry.py`. Async-capable, timeout/redirect support, already a de facto standard in FastAPI projects |
| `python-multipart` removed | JSON-only `/execute` endpoint. File data never hits the SDK — engine sends presigned URLs, node downloads directly |
| `NodeDefinition.model_validator` rejects `format: "binary"` | Definition-time validation. Node authors discover errors on app startup, not at runtime |
| `validate_file_input()` helper on `NodeDefinition` | Validates downloaded files against `x-accept` (extensions) and `x-maxSizeBytes` (size). Node authors call after download |
| `x-*` JSON Schema extensions | Custom keys (`x-accept`, `x-maxSizeBytes`, `x-description`) ignored by `Draft7Validator`, consumed by frontend and node. Follows JSON Schema extension convention |
| CLI `python -m canvastekk_workflow_sdk validate` | Offline manifest validation for node authors during development. Fast feedback without server startup |
| Echo node example (`examples/echo_node/`) | Reference implementation showing file I/O, validation, CLI usage, Docker build |
| SDK version = manifest format contract | `pip install canvastekk-workflow-sdk==0.6.0` enforces `format: "file"`. Engine reads `/manifest` to determine presigned URL treatment |

## Repository

[github.com/nus-cee/canvastekk-workflow-sdk](https://github.com/nus-cee/canvastekk-workflow-sdk)

## Versioning

All languages share a single version counter (PEP 440). Releases are automated via git-cliff on conventional commits merged to `main`. Only language directories with changes get their version bumped and published. See [`python/README.md`](./python/) for details.
