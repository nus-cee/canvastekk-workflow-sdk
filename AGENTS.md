@README.md

## CanvasTEKK Node Development

This repo contains the CanvasTEKK Workflow SDK. When a user asks to create, scaffold, or build a workflow node, follow these routing rules:

### Critical Documentation Structure

The repo has a layered documentation architecture. These files must be kept in sync when the SDK changes:

| File | Purpose | Audience |
|------|---------|----------|
| `docs/EXTERNAL-AUTHOR-GUIDE.md` | **Primary external-facing guide** — build, deploy, and register nodes end-to-end. This is the single source of truth for third-party node authors. Any change to the node creation workflow, registration API, or CI/CD patterns must be reflected here. | External authors |
| `python/README.md` | Full Python SDK API reference (including workflow builder) | SDK users |
| `README.md` | Repo overview, features, architecture | Everyone |
| `examples/echo_node/` | Canonical reference implementation | All developers |

When updating SDK APIs (especially `register_node()`, `BaseNode`, `NodeDefinition`, `WorkflowBuilder`, `WorkflowRunner`, or auth), always check if `docs/EXTERNAL-AUTHOR-GUIDE.md` needs corresponding updates.

### Workflow Builder & Local Runner

The SDK includes a `workflow` package for building, validating, and test-running workflow DAGs locally. Key classes:

| Class | Purpose |
|-------|---------|
| `WorkflowBuilder` | Fluent API for building workflow definitions with `add_start()`, `add_end()`, `add_node()`, `connect()`, `build()` |
| `WorkflowRunner` | Local executor — accepts a `NodeExecutor` strategy (in-process or HTTP) |
| `InProcessExecutor` | Runs `BaseNode.execute()` directly via `asyncio.to_thread()` |
| `HttpExecutor` | Calls node `/execute` endpoints via httpx |
| `WorkflowSpec` | Engine-compatible Pydantic model — `model_dump(mode="json")` is POSTable to `/api/workflows/definitions` |

This is **intentionally local-only** — no Temporal, no S3, no distributed orchestration. For the full guide, see `python/README.md` → "Workflow Builder & Local Runner" section.

### Skill Routing

| User Request Pattern | Skill to Load | When |
|----------------------|---------------|------|
| "Create a workflow node" / "Build a CanvasTEKK node" / "Scaffold a node" | `canvastekk-node-builder` | Always load first for any node creation task |
| "How do I use InstanceSet/MeasurementSet/PlaneSet?" | `canvastekk-node-patterns` | Load for domain-specific patterns and examples |
| "Create a point cloud segmentation node" | `canvastekk-node-builder` + `canvastekk-node-patterns` | Load both — builder for workflow, patterns for domain example |
| "Add auth/middleware/webhooks to my node" | `canvastekk-node-patterns` | Load for advanced integration patterns |
| "Review my node" / "Validate my handler" | `canvastekk-node-builder` | Load for the validation checklist |
| "Build a workflow" / "Test run a workflow" / "WorkflowBuilder" / "WorkflowRunner" | No skill needed — use SDK docs directly | The `workflow` package is self-documenting |

### Node Creation Conventions

When creating CanvasTEKK workflow nodes, always follow these rules:

1. **Use `canvastekk-workflow-sdk` from GitHub Packages**: `pip install canvastekk-workflow-sdk --index-url https://pypi.pkg.github.com/nus-cee/`
2. **File fields use `format: "file"` with `type: "string"`**: Never use `format: "binary"` or `type: "object"` on file fields — the SDK's model_validator rejects them
3. **Include `x-accept` and `x-maxSizeBytes`** on every file input field — the SDK auto-validates downloaded files against these constraints
4. **File inputs are auto-downloaded by the SDK**: The SDK downloads presigned URL file inputs to `context.downloads_dir` before calling `execute()`. Node authors receive local file paths, not URLs. Manual download with `httpx.stream()` is only needed for non-file URLs or opt-out scenarios.
5. **Write outputs to `context.output_path(filename)`**: Never hardcode paths; return them as `str(output_path)`
6. **`definition` must be both module-level AND class attribute**: Module-level enables CLI validation; class attribute satisfies `BaseNode.__init_subclass__`
7. **Node `id` is auto-derived** from `name` + `version` (e.g., `"segment-v1.0.0"`). Node authors must NOT provide `id` manually. `name` must be a valid slug (lowercase alphanumeric, hyphens) and `version` must be semver (X.Y.Z).
8. **Report progress with `context.report_progress()`**: At key stages (download, process, save)
9. **Always generate Dockerfile + pyproject.toml + tests**: A complete node project includes all four files

### SDK Development

When working on the SDK itself (the `python/` directory):

- Run `poetry run ruff check canvastekk_workflow_sdk/ tests/` before committing
- Run `poetry run pytest -v` to verify all tests pass
- The echo node at `examples/echo_node/` is the canonical reference implementation
- SDK version is in `python/canvastekk_workflow_sdk/__init__.py` and `python/pyproject.toml`
