# CanvasTEKK Workflow SDK

Multi-language SDK for building CanvasTEKK Workflow Engine nodes. Each language implementation is self-contained in its own directory.

## Available SDKs

| Language | Status | Package | Directory |
|----------|--------|---------|-----------|
| Python | Available | `canvastekk-workflow-sdk` | [`python/`](./python/) |
| TypeScript | Available | `@nus-cee/canvastekk-workflow-sdk` | [`typescript/`](./typescript/) |

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

### Auto-Download Pipeline

The SDK automatically downloads presigned URL file inputs before calling `execute()`:

- URL inputs (`https://`/`http://`) are downloaded to `context.downloads_dir`
- Downloaded files are auto-validated against `x-accept` and `x-maxSizeBytes`
- `execute()` receives local file paths, not URLs
- Download metadata available via `context.metadata[field_name]`

```python
def execute(self, inputs, context):
    cloud_path = Path(inputs["point_cloud"])  # already a local file
    data = cloud_path.read_bytes()
```

### Test Utilities (`LocalFileServer`)

Test the full presigned URL download pipeline without S3 or mocking:

```python
from canvastekk_workflow_sdk import LocalFileServer, NodeExecutionRequest

with LocalFileServer(tmp_path) as server:
    url = server.url_for("scan.las")
    response = MyNode().run(NodeExecutionRequest(
        run_id="test", node_id="n1",
        inputs={"input_file": url},
    ))
    assert response.status == "pass"
```

The SDK's auto-download only triggers on `http://`/`https://` values — a plain local path bypasses the pipeline. `LocalFileServer` serves real HTTP so the full download → validate → execute path runs end-to-end.

### CLI Manifest Validation

Offline validation without starting the server:

```bash
python -m canvastekk_workflow_sdk validate my_node.handler:definition --json
```

### Template Variable Substitution

The workflow engine automatically resolves `{{variable}}` placeholders in string node inputs after edge resolution. Node authors receive fully resolved strings — no code changes needed.

```json
{"folder_path": "{{report_id}}/runs/{{run_id}}/output/zip/"}
```

After engine resolution: `"13/runs/abc-123/output/zip/"`. See [EXTERNAL-AUTHOR-GUIDE](./docs/EXTERNAL-AUTHOR-GUIDE.md#template-variable-substitution) for the full guide.

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

### TypeScript

**Install from GitHub Packages:**

```bash
npm install @nus-cee/canvastekk-workflow-sdk \
  --registry https://npm.pkg.github.com/nus-cee
```

**Develop locally:**

```bash
cd typescript/
npm install
```

All commands (`npx vitest run`, `npx tsc --noEmit`, `npx tsup`, etc.) run from `typescript/`.

See [`typescript/README.md`](./typescript/) for full documentation.

## Workflow Builder & Local Runner

Build, validate, and test-run workflow DAGs locally without the engine:

```python
from canvastekk_workflow_sdk import WorkflowBuilder, WorkflowRunner
from canvastekk_workflow_sdk.workflow.executor import InProcessExecutor

# Build a workflow
spec = (
    WorkflowBuilder("my-pipeline")
    .add_start("start", outputs=["point_cloud"])
    .add_node("segment", slug="segmentation-v1.0.0", inputs={"method": "dbscan"})
    .add_end("end")
    .connect("start", "segment", from_output="point_cloud", to_input="input_file")
    .connect("segment", "end", from_output="instances", to_input="result")
    .build()  # validates the DAG
)

# Test run locally with BaseNode instances
executor = InProcessExecutor()
executor.register("segmentation-v1.0.0", MySegmentNode())

runner = WorkflowRunner(executor)
result = runner.run(spec, inputs={"point_cloud": "/data/scan.las"})
print(result.status)          # "completed" or "failed"
print(result.final_outputs)   # {"result": ...}
print(result.output_dir)      # Path or None (auto-cleaned temp dir)

# Export for engine
spec.model_dump(mode="json")  # POSTable to /api/workflows/definitions
```

See [`python/README.md`](./python/) for the full workflow builder guide.

## Architecture

The SDK provides registry-level node definition tools and a local workflow builder. In the engine's terminology:

| SDK Type | Engine Type | Purpose |
|----------|-------------|---------|
| `WorkflowNodeManifest` | `WorkflowNodeManifest` | Registry-level node type (schemas, metadata, styles, invocation config) |
| `workflow.WorkflowDefinitionNode` | `WorkflowDefinitionNode` | Node instance within a workflow definition (inputs, position, edges) |
| `workflow.WorkflowDefinitionSpec` | `WorkflowDefinitionSpec` | Complete workflow definition (nodes + edges as a DAG) |

Node authors define `WorkflowNodeManifest`. The engine handles `WorkflowDefinitionNode` internally when building workflow definitions.

The SDK's `workflow` module lets end users build, validate, and test-run complete workflow DAGs locally without the engine. `WorkflowDefinitionSpec.model_dump(mode="json")` produces JSON directly POSTable to the engine's `/api/workflows/definitions` endpoint.

**Versioning:** `WorkflowNodeManifest.version` is the node's semantic version string (e.g., `"1.0.0"`). The engine uses this version directly and enforces immutability — re-registering with the same version and changed data is rejected. Bump the version for any schema or metadata changes.

Project structure:

| Directory | Purpose |
|-----------|---------|
| `python/` | Python SDK source, tests, and package config |
| `typescript/` | TypeScript SDK source, tests, and package config |
| `docs/` | External-facing documentation |
| `examples/` | Reference node implementations and deployment templates |
| `PLANS/` | Implementation plan files per ticket |
| `.github/workflows/` | CI/CD and release workflows |

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
   - `WorkflowNodeManifest` with schema validation
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

### AI Agent Setup

The SDK bundles OpenCode-compatible skills that teach coding agents (opencode, Claude Code, Cursor, etc.) how to create CanvasTEKK workflow nodes correctly — without reading docs.

**One-command setup** in your node project:

```bash
# Copy skills + create AGENTS.md with routing rules
python -m canvastekk_workflow_sdk init --agents-md

# Copy skills only (skip AGENTS.md)
python -m canvastekk_workflow_sdk init

# Overwrite existing files
python -m canvastekk_workflow_sdk init --agents-md --force
```

This creates:

```
my-node-project/
├── .opencode/skills/
│   ├── canvastekk-node-builder/SKILL.md    # Primary creation skill
│   └── canvastekk-node-patterns/SKILL.md   # Domain pattern library
└── AGENTS.md                               # Skill routing + conventions
```

**Two bundled skills:**

| Skill | Purpose |
|-------|---------|
| `canvastekk-node-builder` | Full SDK API reference, 7-step creation workflow, templates, validation checklist |
| `canvastekk-node-patterns` | 10 complete code examples — segmentation, measurement, plane detection, inference, auth, middleware, webhooks, testing |

**How it works:** After setup, your coding agent automatically discovers the skills. When you say *"create a workflow node that segments point clouds"*, the agent loads the relevant skill and follows the correct SDK patterns — proper schemas, file I/O, Dockerfile, tests — all generated correctly.

**Global setup** (works across all projects):

```bash
# Run init in any directory, then copy skills to global config
python -m canvastekk_workflow_sdk init
cp -r .opencode/skills/canvastekk-node-builder ~/.config/opencode/skills/
cp -r .opencode/skills/canvastekk-node-patterns ~/.config/opencode/skills/
rm -rf .opencode
```

## Examples

| Example | Directory | Description |
|---------|-----------|-------------|
| Echo Node | [`examples/echo_node/`](./examples/echo_node/) | Minimal node with file input/output and auto-download pipeline |
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

## External Author Guide

Building and deploying a node for the first time? See the **[EXTERNAL AUTHOR GUIDE](./docs/EXTERNAL-AUTHOR-GUIDE.md)** for a step-by-step walkthrough covering:

- Creating a node with the SDK
- Containerizing with Docker
- Deploying and registering with the engine
- CI/CD pipeline examples (GitHub Actions)
- Error handling reference (401, 403, 409, etc.)

## Architecture Decisions

Key decisions recorded as the SDK evolves. See [`PLANS/PLAN-DA-894.md`](./PLANS/PLAN-DA-894.md) for full context on the file pipeline migration.

### v0.6.0 — File Pipeline Migration (DA-894)

| Decision | Rationale |
|----------|-----------|
| `format: "binary"` replaced with `format: "file"` | Aligns with engine (DA-889) presigned URL pipeline. `binary` implied multipart upload; `file` correctly describes "this field receives a URL string" |
| Hard break — no backward compat | Not in production yet. Dual detection adds complexity for zero benefit |
| `httpx` promoted to runtime dependency | Replaces `urllib.request` in `uploads.py` and `registry.py`. Async-capable, timeout/redirect support, already a de facto standard in FastAPI projects |
| `python-multipart` removed | JSON-only `/execute` endpoint. File data never hits the SDK — engine sends presigned URLs, node downloads directly |
| `WorkflowNodeManifest.model_validator` rejects `format: "binary"` | Definition-time validation. Node authors discover errors on app startup, not at runtime |
| `validate_file_input()` helper on `WorkflowNodeManifest` | Validates downloaded files against `x-accept` (extensions) and `x-maxSizeBytes` (size). Node authors call after download |
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

### v0.7.0 — Auto-Download Pipeline (DA-996)

| Decision | Rationale |
|----------|-----------|
| Auto-download as built-in pipeline step (not middleware) | Core infrastructure — guarantees ordering, prevents user removal. `NodeMiddleware` protocol lacks `definition` access |
| `request.inputs` copied before mutation | Avoids side effects on the original request object |
| `context.metadata[field_name]` stores download info | Node authors can access `original_url`, `local_path`, `size_bytes` |
| `context.downloads_dir` as lazy temp directory | Only created when file inputs are present; cleaned up with tempdir |
| Field-prefixed filenames (`{field}_{name}`) | Prevents filename collisions when multiple file inputs are present |
| Partial download cleanup on failure | Downloaded files removed if download or validation fails |

### v0.13.0 — WorkflowRunner output_dir (DA-1102)

| Decision | Rationale |
|----------|-----------|
| Shared `output_dir` per run (not per-node) | Enables file passing between nodes in multi-step pipelines — node A writes, node B reads from the same directory |
| `output_dir: Path | None = None` parameter | Default creates a temp dir transparently; existing tests unaffected. User-supplied dirs are never cleaned up |
| `cleanup: bool = True` parameter | Auto-created temp dirs are removed after the run. `cleanup=False` preserves intermediate outputs for debugging |
| `WorkflowRunResult.output_dir` field | Exposes the output directory path on the result (set to `None` if auto-cleaned) |
| `finally`-style cleanup | Temp dirs cleaned up even when nodes raise exceptions, preventing leaks |
| `LocalFileServer` test utility | Serves local files over HTTP so the full presigned URL download pipeline can be tested without S3 or mocking |
| `HttpExecutor` limitation documented | Shared `output_dir` only effective with `InProcessExecutor` — remote nodes don't share the local filesystem |

## Repository

[github.com/nus-cee/canvastekk-workflow-sdk](https://github.com/nus-cee/canvastekk-workflow-sdk)

## Versioning

All languages share a single version counter (PEP 440). Releases are automated via git-cliff on conventional commits merged to `main`. Only language directories with changes get their version bumped and published. See [`python/README.md`](./python/) for details.
