# Deployment Examples

Reference templates for deploying CanvasTEKK Workflow SDK nodes. These are **not** part of the SDK — they are examples that deployers (DevOps / platform teams) can adapt.

> **Note:** The SDK does not install or manage these manifests. They are provided as starting points only. For SDK documentation, see the [root README](../../README.md).

## Contents

| File | Description |
|------|-------------|
| `kubernetes-node.yaml` | Kubernetes Deployment with health probes, env vars, and volume mounts |

## Usage

Copy the relevant template and adapt values for your environment:

```bash
cp kubernetes-node.yaml my-node-deployment.yaml
# Edit image, env vars, secrets, volumes as needed
kubectl apply -f my-node-deployment.yaml
```

## Environment Variables

These are deployment-level env vars that the **deployer** sets — node authors do not interact with them directly.

### Core

| Variable | Description |
|----------|-------------|
| `CANVASTEKK_OUTPUT_DIR` | Base directory for node output files. SDK creates `{CANVASTEKK_OUTPUT_DIR}/{run_id}/{node_id}/`. Override in production to use a persistent volume. Defaults to `/tmp`. |
| `CANVASTEKK_NODE_ENV` | Node environment mode (`dev`/`uat`/`production`). |
| `CANVASTEKK_LOG_LEVEL` | SDK log level (`DEBUG`/`INFO`/`WARNING`/`ERROR`/`CRITICAL`). |
| `CANVASTEKK_LOG_FORMAT` | Log format (`json` for production, `text` for local dev). |

### Authentication

| Variable | Description |
|----------|-------------|
| `CANVASTEKK_API_KEY` | Shared secret for API key auth (if configured). |
| `CANVASTEKK_JWT_SECRET` | Signing secret for HS256 JWT token validation. |
| `CANVASTEKK_KEYCLOAK_SERVER_URL` | Keycloak base URL (e.g., `https://keycloak.example.com`). |
| `CANVASTEKK_KEYCLOAK_REALM` | Keycloak realm name. |
| `CANVASTEKK_KEYCLOAK_AUDIENCE` | Expected `aud` claim in JWT tokens. Optional. |
