# CanvasTEKK Workflow SDK

Multi-language SDK for building CanvasTEKK Workflow Engine nodes. Each language implementation is self-contained in its own directory.

## Available SDKs

| Language | Status | Package | Directory |
|----------|--------|---------|-----------|
| Python | Available | `canvastekk-workflow-sdk` | [`python/`](./python/) |
| TypeScript | Planned | — | `typescript/` |

## Features

### SDK Version in Manifest

The `/manifest` endpoint auto-injects `sdk_version` (read from the installed package version). The engine uses this to verify SDK compatibility:

```json
{
  "id": "segment-v1.0.0",
  "name": "segment",
  "version": "1.0.0",
  "sdk_version": "0.6.0",
  "mode": "dev",
  "input_schema": { ... }
}
```

`sdk_version` and `mode` are never set by node authors — they are injected at the endpoint level.

### X-SDK-Version Response Header

All SDK HTTP responses include `X-SDK-Version: <version>` (e.g. `0.6.0`). This enables engine-side version-aware routing and debugging without parsing response bodies. Follows the same convention as Stripe, AWS SDKs, and Twilio.

### Kubernetes Health Probes

Standard liveness and readiness endpoints for container orchestration:

| Endpoint | Purpose | Behavior |
|----------|---------|----------|
| `GET /live` | Liveness — "don't restart me" | Returns 200 if the process is alive. Kubernetes restarts the pod if this fails. |
| `GET /ready` | Readiness — "send me traffic" | Returns 200 when ready to accept traffic. Calls `node.health_check()` if defined. Kubernetes removes the pod from service if this fails. |

See [`examples/deployment/`](./examples/deployment/) for Kubernetes manifest examples.

### Environment Mode

`CANVASTEKK_NODE_ENV` controls the `mode` field in `/manifest`:

| Env Value | Manifest `mode` | Use Case |
|-----------|----------------|----------|
| `dev`, `development`, `test` | `"dev"` | Local development (default) |
| `uat`, `staging` | `"uat"` | User acceptance testing |
| `production` | `"production"` | Production deployment |

The engine reads `mode` to adjust routing, test behavior, and logging verbosity.

### Structured Logging

Production-ready structured logging configured automatically at app startup:

- **JSON format** (default): one JSON object per line — compatible with CloudWatch Logs Insights, Datadog, ELK
- **Text format**: human-readable for local development
- **Correlation IDs**: `run_id` and `node_id` automatically included in structured logs
- **Zero config**: works out of the box with `CANVASTEKK_LOG_FORMAT` and `CANVASTEKK_LOG_LEVEL` env vars

See [`python/README.md`](./python/) for the full logging guide.

### File Input Validation

The `validate_file_input()` method validates downloaded files against schema constraints:

- `x-accept`: allowed file extensions (e.g. `[".las", ".ply"]`)
- `x-maxSizeBytes`: maximum file size in bytes
- Case-insensitive extension matching

```python
definition.validate_file_input(field_name="point_cloud", data=response.content)
```

### CLI Manifest Validation

Offline validation without starting the server:

```bash
python -m canvastekk_workflow_sdk validate my_node.handler:definition --json
```

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
| Deployment | [`examples/deployment/`](./examples/deployment/) | Kubernetes manifest templates for deployers (not part of the SDK) |

## Environment Variables

The SDK reads the following environment variables. None are required by default — nodes work out of the box with no configuration.

### Core

| Variable | Default | Description |
|----------|---------|-------------|
| `CANVASTEKK_NODE_ENV` | `dev` | Node environment mode. `dev`/`development`/`test` → `"mode": "dev"`. `uat`/`staging` → `"mode": "uat"`. `production` → `"mode": "production"`. The engine reads this from `/manifest` to adjust routing and test behaviour. |
| `CANVASTEKK_LOG_LEVEL` | `INFO` | SDK-wide log level: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. |
| `CANVASTEKK_LOG_FORMAT` | `json` | `json` (one JSON object per line — CloudWatch/Datadog/ELK) or `text` (human-readable for local dev). |

### Authentication

Auth environment variables are only read when the corresponding `NodeAuth` backend is configured. If no auth is configured, none of these are needed.

| Variable | Auth Layer | Description |
|----------|-----------|-------------|
| `CANVASTEKK_API_KEY` | API Key (`NodeAuth.api_key()`) | Shared secret validated against the `X-API-Key` request header. |
| `CANVASTEKK_JWT_SECRET` | JWT / HMAC (`NodeAuth.jwt()`) | Signing secret for HS256 JWT token validation. Requires `PyJWT` package. |
| `CANVASTEKK_KEYCLOAK_SERVER_URL` | Keycloak (`NodeAuth.keycloak()`) | Keycloak base URL (e.g., `https://keycloak.example.com`). Requires `PyJWT` + `cryptography`. |
| `CANVASTEKK_KEYCLOAK_REALM` | Keycloak | Keycloak realm name. |
| `CANVASTEKK_KEYCLOAK_AUDIENCE` | Keycloak | Expected `aud` claim in JWT tokens. Optional — skip if tokens don't include `aud`. |

### Dev Mode

| Variable | Description |
|----------|-------------|
| `CANVASTEKK_DEV_MODE` | Set to `true`, `1`, or `yes` to **bypass all authentication**. Useful for local development. **Never enable in production.** |

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
| `sdk_version` auto-injected in `/manifest` | Engine can verify SDK compatibility. Node authors never set it — injected at endpoint level |
| `X-SDK-Version` response header | Industry standard (Stripe, AWS, Twilio). Enables debugging and version-aware routing without parsing body |
| `GET /live` and `GET /ready` | Kubernetes-standard health probes. `/live` = process alive, `/ready` = ready for traffic |
| `CANVASTEKK_NODE_ENV` → `mode` field | Maps env (`dev`/`uat`/`production`) to manifest `mode`. Engine adjusts behavior per environment |
| Structured JSON logging (default) | One JSON object per line with `timestamp`, `level`, `run_id`, `node_id`. CloudWatch/Datadog/ELK compatible |
| `CANVASTEKK_LOG_FORMAT` / `CANVASTEKK_LOG_LEVEL` env vars | Zero-config logging. `json` for production, `text` for local dev. `INFO` default level |

## Repository

[github.com/nus-cee/canvastekk-workflow-sdk](https://github.com/nus-cee/canvastekk-workflow-sdk)

## Versioning

All languages share a single version counter (PEP 440). Releases are automated via git-cliff on conventional commits merged to `main`. Only language directories with changes get their version bumped and published. See [`python/README.md`](./python/) for details.
