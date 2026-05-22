# External Author Guide

> **SDK Version:** This guide targets `canvastekk-workflow-sdk` >= 0.9.0. Features documented here may differ in earlier versions.

End-to-end guide for building, deploying, and registering a CanvasTEKK workflow node.

## Overview

The workflow has four stages:

```
1. Build      → Create a node using the Python SDK
2. Containerize → Package it as a Docker image
3. Deploy     → Push the image and run it on your infrastructure
4. Register   → Tell the engine your node exists via the registry API
```

After registration, the engine can discover your node and include it in workflows.

---

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.12+ | Required by the SDK |
| Docker | 20+ | For building container images |
| `httpx` | 0.28+ | SDK dependency for file downloads and registration |
| GitHub account | — | For CI/CD (GitHub Actions) |
| Engine registry URL | — | Provided by the platform team |

---

## Step 1: Install the SDK

```bash
pip install canvastekk-workflow-sdk \
  --index-url https://pypi.pkg.github.com/nus-cee/
```

For local development:

```bash
cd python/
python3.12 -m venv .venv
source .venv/bin/activate
pip install poetry
poetry install
```

---

## Step 2: Create Your Node

Create a file called `handler.py`. Subclass `BaseNode`, define a `NodeDefinition`, implement `execute()`, and call `.create_app()`:

```python
# handler.py
from canvastekk_workflow_sdk import BaseNode, NodeDefinition, ExecutionContext

# Module-level definition — needed for CLI validation
definition = NodeDefinition(
    name="my-node",
    version="1.0.0",
    title="My Node",
    description="Does something useful",
    input_schema={
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    },
    output_schema={
        "type": "object",
        "properties": {"result": {"type": "string"}},
    },
)


class MyNode(BaseNode):
    definition = definition  # Class attribute (same object)

    def execute(self, inputs: dict, context: ExecutionContext) -> dict:
        context.report_progress(0.5, "Processing")
        return {"result": inputs["text"].upper()}


app = MyNode().create_app()
```

### Key Requirements

1. **Subclass `BaseNode`** — inherit from `canvastekk_workflow_sdk.BaseNode`
2. **Define `definition`** as both a module-level variable and a class attribute
3. **Implement `execute(inputs, context)`** — return a dict matching your `output_schema`
4. **Call `.create_app()`** — produces a ready-to-run FastAPI app

### Node ID Format

The `id` field is automatically derived from `name` + `version` as `{name}-v{version}` (e.g., `my-node-v1.0.0`). Node authors must NOT provide `id` manually.

**Requirements:**
- `name` must be a valid slug: lowercase alphanumeric characters and hyphens only
- `version` must follow semantic versioning (e.g., `1.0.0`, `2.3.1`) — this is an **author-facing label** for your own tracking

> **Note on engine versioning:** The engine maintains its own independent versioning system (monotonically increasing integer). Your `NodeDefinition.version` is your own semantic version label — it does **not** control the engine's version assignment. The engine assigns a new version automatically each time `register_node()` is called with changed content.

### SDK Types and Engine Terminology

The SDK's `NodeDefinition` maps to the engine's **registry-level node type** (called `WorkflowNode` in the engine). This is distinct from `WorkflowDefinitionNode`, which the engine uses to represent a node instance within a specific workflow definition.

| SDK Type | Engine Type | Purpose |
|----------|-------------|---------|
| `NodeDefinition` | `WorkflowNode` | Registry-level node type (schemas, metadata, styles) |
| — | `WorkflowDefinitionNode` | Node instance within a workflow definition (inputs, position, edges) |

Node authors only interact with `NodeDefinition`. The engine handles `WorkflowDefinitionNode` internally.

### File Inputs

Use `format: "file"` with `x-accept` and `x-maxSizeBytes`:

```python
input_schema={
    "type": "object",
    "properties": {
        "point_cloud": {
            "type": "string",
            "format": "file",
            "x-accept": [".ply", ".las"],
            "x-maxSizeBytes": 52428800,
        },
    },
}
```

The SDK **automatically downloads** presigned URL file inputs and validates them before calling `execute()`. Your `execute()` method receives local file paths, not URLs:

```python
from pathlib import Path

def execute(self, inputs: dict, context: ExecutionContext) -> dict:
    # inputs["point_cloud"] is already a local file path (auto-downloaded)
    cloud_path = Path(inputs["point_cloud"])
    data = cloud_path.read_bytes()

    # Access download metadata if needed
    meta = context.metadata.get("point_cloud", {})
    # meta contains: original_url, local_path, size_bytes

    output = context.output_path("result.json")
    output.write_text('{"count": 42}')

    return {"result_path": str(output)}
```

> **Note:** Manual download with `httpx.stream()` is only needed for non-file URLs or opt-out scenarios. Standard file inputs are handled automatically.

### Validate Locally

Before deploying, validate your node definition offline:

```bash
python -m canvastekk_workflow_sdk validate handler:definition
```

Exit code `0` = valid, `1` = errors.

---

## Step 3: Containerize

Create a `Dockerfile`:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml handler.py ./
RUN pip install . --index-url https://pypi.pkg.github.com/nus-cee/

EXPOSE 8001

CMD ["uvicorn", "handler:app", "--host", "0.0.0.0", "--port", "8001"]
```

Create a `pyproject.toml`:

```toml
[project]
name = "my-node"
version = "1.0.0"
description = "My CanvasTEKK workflow node"
requires-python = ">=3.12"
dependencies = [
    "canvastekk-workflow-sdk>=0.9.0,<1.0.0",
]
```

> **Tip:** Pin to a specific minor version for production nodes. This prevents unexpected breakage when the SDK releases a new minor or major version.

Build and test locally:

```bash
docker build -t my-node .
docker run -p 8001:8001 my-node

# Verify
curl http://localhost:8001/health
curl http://localhost:8001/manifest
```

---

## Step 4: Deploy

Push your image to a container registry accessible by the platform:

```bash
docker tag my-node your-registry.example.com/my-node:1.0.0
docker push your-registry.example.com/my-node:1.0.0
```

The platform team will deploy it to the cluster. Once running, your node exposes:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/execute` | POST | Run the node |
| `/health` | GET | Health check |
| `/manifest` | GET | Node self-description |
| `/hook` | POST | Webhook/callback handler (optional, override `hook()`) |
| `/metrics` | GET | Execution metrics summary |
| `/live` | GET | Liveness probe (Kubernetes) |
| `/ready` | GET | Readiness probe (Kubernetes) |

---

## Step 5: Register with the Engine

After deployment, register your node so the engine can discover it. The engine stores your node as a `WorkflowNode` (registry-level node type) — distinct from a `WorkflowDefinitionNode`, which represents a node instance within a workflow definition.

### Authentication Methods

| Method | Header | Use Case |
|--------|--------|----------|
| **Service Token** | `X-Service-Token` | CI/CD pipelines (recommended) |
| **API Key** | `X-API-Key` | Manual registration, testing |

### Using `register_node()` (Python)

```python
from canvastekk_workflow_sdk import BaseNode, NodeDefinition
from canvastekk_workflow_sdk.registry import register_node

node = MyNode()

# CI/CD with service token (recommended)
register_node(
    node,
    registry_url="https://engine.example.com/api/workflows/nodes/",
    invoke_url="https://my-node.example.com",
    service_token="svs_your-token-here",
    tags=["category:utility", "team:platform"],
)

# Manual with API key
register_node(
    node,
    registry_url="https://engine.example.com/api/workflows/nodes/",
    invoke_url="https://my-node.example.com",
    api_key="your-api-key",
)

# Lambda invocation
register_node(
    node,
    registry_url="https://engine.example.com/api/workflows/nodes/",
    invoke_type="lambda",
    invoke_url="arn:aws:lambda:ap-southeast-1:123456789:function:my-node",
    invoke_config={"region": "ap-southeast-1"},
    service_token="svs_your-token-here",
)
```

#### Registration Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `node` | `BaseNode` | Yes | The node instance to register |
| `registry_url` | `str` | Yes | Engine registry endpoint (e.g., `/api/workflows/nodes/`) |
| `invoke_url` | `str \| None` | No | URL where the node is reachable |
| `invoke_type` | `"http" \| "lambda" \| "sagemaker" \| "in-process"` | No | Invocation type (default: `"http"`) |
| `api_key` | `str \| None` | Yes* | API key for auth (`X-API-Key` header) |
| `service_token` | `str \| None` | Yes* | Service token for CI/CD (`X-Service-Token` header, takes precedence) |
| `tags` | `list[str] \| None` | No | Searchable tags for the registry |
| `invoke_config` | `dict \| None` | No | Extra invocation parameters (e.g., Lambda region) |
| `timeout` | `int` | No | Request timeout in seconds (default: 30) |

*Either `api_key` or `service_token` must be provided.

### Using `curl` (manual)

```bash
# Get your node manifest
MANIFEST=$(curl -s http://localhost:8001/manifest)

# Register with service token
curl -X POST https://engine.example.com/api/workflows/nodes/ \
  -H "Content-Type: application/json" \
  -H "X-Service-Token: svs_your-token-here" \
  -d "$(echo "$MANIFEST" | jq '. + {invoke_url: "https://my-node.example.com", invoke_type: "http"}')"
```

---

## Required Secrets

Secrets are **never stored in code**. Use your CI/CD provider's secrets store.

| Secret | When Required | Description |
|--------|--------------|-------------|
| `REGISTRY_SERVICE_TOKEN` | CI/CD registration | Service token for automated registration (`X-Service-Token` header). Provided by the platform team. |
| `REGISTRY_API_KEY` | Manual registration | API key for the registry (`X-API-Key` header). Provided by the platform team. |
| `CANVASTEKK_API_KEY` | Node auth (API Key mode) | Shared secret for authenticating requests to your node. Set via `NodeAuth.api_key()`. |
| `CANVASTEKK_KEYCLOAK_SERVER_URL` | Node auth (Keycloak mode) | Keycloak base URL. Only needed if using Keycloak auth. |
| `CANVASTEKK_KEYCLOAK_REALM` | Node auth (Keycloak mode) | Keycloak realm name. |
| `CANVASTEKK_JWT_SECRET` | Node auth (JWT mode) | HS256 signing secret. Only needed if using JWT auth. |

### Auth Mode Summary

| Auth Mode | Secrets Required | Typical Use Case |
|-----------|-----------------|------------------|
| None | None | Local development (`CANVASTEKK_DEV_MODE=true`) |
| API Key | `CANVASTEKK_API_KEY` | Simple shared-secret protection |
| Keycloak | `CANVASTEKK_KEYCLOAK_SERVER_URL` + `CANVASTEKK_KEYCLOAK_REALM` | Production SSO integration |
| JWT | `CANVASTEKK_JWT_SECRET` | Custom token-based auth |

---

## CI/CD Pipeline Example (GitHub Actions)

This workflow builds, pushes, and registers your node automatically:

```yaml
name: Build and Register Node

on:
  push:
    branches: [main]
    tags: ["v*"]

env:
  REGISTRY: your-registry.example.com
  IMAGE_NAME: my-node
  ENGINE_URL: https://engine.example.com/api/workflows/nodes/

jobs:
  build-and-register:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Build Docker image
        run: docker build -t ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }} .

      - name: Push to registry
        run: |
          echo "${{ secrets.REGISTRY_PASSWORD }}" | docker login ${{ env.REGISTRY }} -u "${{ secrets.REGISTRY_USERNAME }}" --password-stdin
          docker push ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}

      - name: Install SDK
        run: pip install canvastekk-workflow-sdk --index-url https://pypi.pkg.github.com/nus-cee/

      - name: Register node with engine
        env:
          REGISTRY_SERVICE_TOKEN: ${{ secrets.REGISTRY_SERVICE_TOKEN }}
        run: |
          python -c "
          import os
          from handler import MyNode
          from canvastekk_workflow_sdk.registry import register_node

          register_node(
              MyNode(),
              registry_url='${{ env.ENGINE_URL }}',
              invoke_url='https://my-node.example.com',
              service_token=os.environ['REGISTRY_SERVICE_TOKEN'],
              tags=['ci-cd', 'auto-registered'],
          )
          print('Registration successful')
          "

      - name: Validate registration
        run: |
          HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
            -H "X-Service-Token: ${{ secrets.REGISTRY_SERVICE_TOKEN }}" \
            "${{ env.ENGINE_URL }}/my-node-v1.0.0")
          if [ "$HTTP_STATUS" != "200" ]; then
            echo "Registration verification failed (HTTP $HTTP_STATUS)"
            exit 1
          fi
          echo "Registration verified"
```

### Required GitHub Secrets

Configure these in **Settings > Secrets and variables > Actions**:

| Secret | Description |
|--------|-------------|
| `REGISTRY_SERVICE_TOKEN` | Service token for engine registration |
| `REGISTRY_USERNAME` | Container registry username |
| `REGISTRY_PASSWORD` | Container registry password |

---

## Error Handling Reference

When calling the registry API, you may encounter these errors:

| HTTP Status | Error Meaning | Cause | Fix |
|-------------|--------------|-------|-----|
| **401** | Unauthorized | Missing or invalid API key / service token | Check your `api_key` or `service_token` value. Ensure the header is correct (`X-API-Key` or `X-Service-Token`). |
| **403** | Forbidden | Wrong owner — the node is registered under a different owner | Contact the platform team to transfer ownership, or use a different node ID. |
| **404** | Not Found | Node not found in registry (GET/PUT/DELETE) or registry endpoint doesn't exist | Verify the `registry_url` and node ID. |
| **409** | Conflict | Node already exists with a different owner | Use a unique node ID or contact the platform team. |
| **422** | Validation Error | Invalid manifest payload | Validate locally first: `python -m canvastekk_workflow_sdk validate handler:definition` |
| **500** | Internal Server Error | Engine-side failure | Retry after a few seconds. Contact the platform team if persistent. |

### Handling Errors in Python

```python
from canvastekk_workflow_sdk.registry import register_node, RegistrationError

try:
    result = register_node(
        node,
        registry_url="https://engine.example.com/api/workflows/nodes/",
        invoke_url="https://my-node.example.com",
        service_token="svs_your-token-here",
    )
    print(f"Registered: {result['name']} v{result['version']}")
except RegistrationError as e:
    if e.status_code == 401:
        print("Authentication failed: check your service token")
    elif e.status_code == 403:
        print("Forbidden: this node belongs to another owner")
    elif e.status_code == 409:
        print("Conflict: node already registered with different owner")
    else:
        print(f"Registration failed ({e.status_code}): {e}")
```

---

## Quick Reference: Complete Minimal Node

```
my-node/
├── handler.py
├── pyproject.toml
├── Dockerfile
└── tests/
    └── test_handler.py
```

**handler.py** — see [Step 2](#step-2-create-your-node)

**pyproject.toml**:

```toml
[project]
name = "my-node"
version = "1.0.0"
requires-python = ">=3.12"
dependencies = ["canvastekk-workflow-sdk>=0.9.0,<1.0.0"]
```

**Dockerfile** — see [Step 3](#step-3-containerize)

**tests/test_handler.py**:

```python
from fastapi.testclient import TestClient
from handler import app

client = TestClient(app)


def test_execute():
    resp = client.post("/execute", json={
        "run_id": "test", "node_id": "test", "inputs": {"text": "hello"},
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "pass"
    assert resp.json()["outputs"]["result"] == "HELLO"


def test_manifest():
    resp = client.get("/manifest")
    assert resp.status_code == 200
    assert resp.json()["name"] == "my-node"
```

---

## Template Variable Substitution

The workflow engine automatically resolves `{{variable}}` placeholders in **string** node inputs after edge resolution.

### How It Works

When the engine executes a workflow, it resolves each node's inputs via edges (connecting upstream outputs to downstream inputs). After this resolution, the engine scans all **string** values for `{{key}}` patterns and substitutes them using the same node's resolved input dict.

**Your node receives fully resolved strings.** You do not need to handle `{{}}` syntax in your `execute()` method — the engine handles substitution before your node runs.

```
Engine: resolve edges → resolve {{templates}} → POST /execute to your node
```

### Syntax

| Pattern | Behavior |
|---------|----------|
| `{{variable}}` | Replaced with `str(inputs["variable"])` |
| `{variable}` | **Literal** — single braces are not substituted |
| `{{unknown_key}}` | Left as-is if the key is not in the node's inputs (logged at DEBUG) |

**Key rules:**
- Only `{{double_braces}}` trigger substitution — single braces `{like_this}` are literal
- Substitution is **single-pass** (no recursive resolution — `{{foo}}` in a resolved value is not re-processed)
- Non-string inputs (integers, booleans, arrays, objects) pass through unchanged
- Unresolved placeholders are left as-is and logged at DEBUG level

### Availability

> Template substitution requires an engine version that includes [DA-1037](https://betekk.atlassian.net/browse/DA-1037). On older engines, `{{...}}` placeholders pass through as literal text.

### Examples

**Path construction:**

Workflow definition configures the node with template inputs:

```json
{
  "folder_path": "{{report_id}}/runs/{{run_id}}/output/zip/",
  "report_id": 13,
  "run_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

Your node receives the resolved string:

```json
{
  "folder_path": "13/runs/a1b2c3d4-e5f6-7890-abcd-ef1234567890/output/zip/",
  "report_id": 13,
  "run_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

**URL construction:**

```json
{
  "download_url": "https://api.example.com/reports/{{report_id}}/export?format=pdf",
  "report_id": 42
}
```

After substitution: `"https://api.example.com/reports/42/export?format=pdf"`

### Common Variables

| Variable | Source | Description |
|----------|--------|-------------|
| `run_id` | `__start__` node (via edges) | Workflow run identifier — always available when connected via edges |
| `report_id` | Upstream node output | Report identifier from a preceding node |
| `node_id` | Engine-injected | Node instance ID within the workflow |

Variables must be present in the same node's resolved inputs (from edges, defaults, or overrides). The `run_id` is available when the `__start__` node connects to your node via an edge.

### Design Considerations

#### Input Schema Constraints

Your `input_schema` constraints (`pattern`, `format`, `minLength`, `maxLength`) validate against the **resolved** value, not the template syntax. Design your constraints to match the expected resolved output:

```python
input_schema={
    "type": "object",
    "properties": {
        "folder_path": {
            "type": "string",
            # This pattern must match the RESOLVED value, e.g. "13/runs/abc/output/"
            # NOT the template "{{report_id}}/runs/{{run_id}}/output/"
            "pattern": "^[a-zA-Z0-9/_-]+$",
        },
    },
}
```

#### Security

Template substitution is single-pass, which prevents recursive injection — if a resolved value contains `{{another_key}}`, it is **not** re-substituted. However, node authors should still validate resolved string values before using them in file paths, URLs, or shell commands, as the resolved content depends on upstream node outputs.

#### Avoiding Conflicts

If your node naturally produces or consumes strings containing `{{` and `}}` (e.g., LaTeX templates, Mustache/Handlebars syntax), be aware that the engine will attempt substitution on any string input containing `{{...}}`. To avoid unintended substitution:

- Use single braces `{...}` instead of `{{...}}` where possible
- Structure your workflow so conflicting string fields receive their values from non-edge sources (defaults, overrides)

---

## Further Reading

- [SDK Python README](../python/README.md) — full API reference
- [Echo Node Example](../examples/echo_node/) — minimal reference implementation
- [Root README](../README.md) — SDK overview and architecture
