@README.md

## CanvasTEKK Node Development

This repo contains the CanvasTEKK Workflow SDK. When a user asks to create, scaffold, or build a workflow node, follow these routing rules:

### Critical Documentation Structure

The repo has a layered documentation architecture. These files must be kept in sync when the SDK changes:

| File | Purpose | Audience |
|------|---------|----------|
| `docs/EXTERNAL-AUTHOR-GUIDE.md` | **Primary external-facing guide** — build, deploy, and register nodes end-to-end. This is the single source of truth for third-party node authors. Any change to the node creation workflow, registration API, or CI/CD patterns must be reflected here. | External authors |
| `python/README.md` | Full Python SDK API reference (including workflow builder) | SDK users |
| `typescript/README.md` | Full TypeScript SDK API reference (including workflow builder) | SDK users |
| `README.md` | Repo overview, features, architecture | Everyone |
| `examples/echo_node/` | Canonical Python reference implementation | All developers |

When updating SDK APIs (especially `register_node()`, `BaseNode`, `NodeDefinition`, `WorkflowBuilder`, `WorkflowRunner`, or auth), always check if `docs/EXTERNAL-AUTHOR-GUIDE.md` needs corresponding updates.

### Workflow Builder & Local Runner

The SDK includes a `workflow` package for building, validating, and test-running workflow DAGs locally. Key classes:

| Class | Purpose |
|-------|---------|
| `WorkflowBuilder` | Fluent API for building workflow definitions with `add_start()`, `add_end()`, `add_node()`, `connect()`, `build()`. Constructor no longer takes a `name` parameter. |
| `WorkflowRunner` | Local executor — accepts a `NodeExecutor` strategy (in-process or HTTP). Supports `output_dir` for shared file passing between nodes and `cleanup` for temp dir management |
| `InProcessExecutor` | **Python:** runs `BaseNode.execute()` directly via `asyncio.to_thread()`. **TypeScript:** runs via `await node.execute()` directly |
| `HttpExecutor` | **Python:** calls node `/execute` endpoints via httpx. **TypeScript:** calls via `fetch` |
| `WorkflowSpec` | Engine-compatible model — Python: `model_dump(mode="json")`, TypeScript: `JSON.stringify()`. POSTable to `/api/workflows/definitions` |
| `LocalFileServer` | Test utility — serves local files over HTTP to simulate presigned URL downloads without S3 or mocking |

This is **intentionally local-only** — no Temporal, no S3, no distributed orchestration. For the full guide, see `python/README.md` or `typescript/README.md` → "Workflow Builder & Local Runner" section.

### Skill Routing

| User Request Pattern | Skill to Load | When |
|----------------------|---------------|------|
| "Create a workflow node" / "Build a CanvasTEKK node" / "Scaffold a node" | `canvastekk-node-builder` | Always load first for any node creation task |
| "How do I use InstanceSet/MeasurementSet/PlaneSet?" | `canvastekk-node-patterns` | Load for domain-specific patterns and examples |
| "Create a point cloud segmentation node" | `canvastekk-node-builder` + `canvastekk-node-patterns` | Load both — builder for workflow, patterns for domain example |
| "Add auth/middleware/webhooks to my node" | `canvastekk-node-patterns` | Load for advanced integration patterns |
| "Review my node" / "Validate my handler" | `canvastekk-node-builder` | Load for the validation checklist |
| "Build a workflow" / "Test run a workflow" / "WorkflowBuilder" / "WorkflowRunner" | No skill needed — use SDK docs directly | The `workflow` package is self-documenting |
| "Test file download" / "Test presigned URL" / "LocalFileServer" | No skill needed — use SDK docs directly | `LocalFileServer` is in `canvastekk_workflow_sdk.testing` |

### Node Creation Conventions

When creating CanvasTEKK workflow nodes, always follow these rules:

1. **Use `canvastekk-workflow-sdk` from GitHub Packages or GitHub Releases**: `pip install canvastekk-workflow-sdk --index-url https://USERNAME:TOKEN@pypi.pkg.github.com/nus-cee/` (requires PAT with `read:packages` scope), OR download the wheel directly from [GitHub Releases](https://github.com/nus-cee/canvastekk-workflow-sdk/releases) — see [README](./README.md#python) for both methods
2. **File fields use `format: "file"` with `type: "string"`**: Never use `format: "binary"` or `type: "object"` on file fields — the SDK's model_validator rejects them
3. **Include `x-accept` and `x-maxSizeBytes`** on every file input field — the SDK auto-validates downloaded files against these constraints
4. **File inputs are auto-downloaded by the SDK**: The SDK downloads presigned URL file inputs to `context.downloads_dir` before calling `execute()`. Node authors receive local file paths, not URLs. Manual download with `httpx.stream()` is only needed for non-file URLs or opt-out scenarios.
5. **Write outputs to `context.output_path(filename)`**: Never hardcode paths; return them as `str(output_path)`
6. **`definition` must be both module-level AND class attribute**: Module-level enables CLI validation; class attribute satisfies `BaseNode.__init_subclass__`
7. **Node `id` is auto-derived** from `name` + `version` (e.g., `"segment-v1.0.0"`). Node authors must NOT provide `id` manually. `name` must be a valid slug (lowercase alphanumeric, hyphens) and `version` must be semver (X.Y.Z).
8. **Report progress with `context.report_progress()`**: At key stages (download, process, save)
9. **Always generate Dockerfile + pyproject.toml + tests**: A complete node project includes all four files

### SDK Development

When working on the Python SDK (`python/` directory):

- Run `poetry run ruff check canvastekk_workflow_sdk/ tests/` before committing
- Run `poetry run pytest -v` to verify all tests pass
- The echo node at `examples/echo_node/` is the canonical reference implementation
- SDK version is in `python/canvastekk_workflow_sdk/__init__.py` and `python/pyproject.toml`

When working on the TypeScript SDK (`typescript/` directory):

- Run `npx tsc --noEmit` for type checking
- Run `npx vitest run` to verify all tests pass
- Run `npx tsup` to build (ESM + CJS + `.d.ts`)
- SDK version is in `typescript/src/version.ts` and `typescript/package.json`
- Wire-format types use `snake_case` (for Python engine compatibility); internal types use `camelCase`

### Versioning & Releases

**Versions are NEVER bumped manually.** The entire release flow is automated by `.github/workflows/release.yml` using [git-cliff](https://git-cliff.org) with conventional commits.

**Release trigger**: Push to `main` → git-cliff determines if a new version is needed based on conventional commit messages since the last tag.

**Version bump rules** (from `cliff.toml`):

| Commit Type | Version Bump | Example |
|-------------|-------------|---------|
| `feat:` | Minor (0.15.0 → 0.16.0) | `feat: add new node pattern` |
| `fix:` | Patch (0.15.0 → 0.15.1) | `fix(ci): fix release pipeline` |
| `docs:`, `chore:`, `ci:`, `refactor:`, `test:`, `style:` | No release (skipped) | — |
| `feat!:` / `BREAKING CHANGE` | Major or minor (`breaking_always_bump_major = false`) | `feat!: rename API` |

**Automated pipeline flow** (on qualifying push to `main`):

1. git-cliff determines next version from commit history
2. Python script auto-bumps ALL version files: `pyproject.toml`, `__init__.py`, `typescript/package.json`, `dotnet/Directory.Build.props`
3. Auto-commits (`chore(release): prepare vX.Y.Z`), auto-tags (`vX.Y.Z`), auto-pushes
4. Creates GitHub Release with auto-generated changelog notes
5. Builds Python wheel (`poetry build`) and uploads to GitHub Release

**Important**:

- Do NOT manually edit version strings in `pyproject.toml`, `__init__.py`, `package.json`, or `Directory.Build.props` — the pipeline overwrites them
- To trigger a patch release, use `fix:` commit type
- To trigger a minor release, use `feat:` commit type
- `docs:` / `chore:` / `ci:` commits alone do NOT trigger a release
- The released wheel is published to GitHub Packages at `https://pypi.pkg.github.com/nus-cee/` (requires PAT with `read:packages` scope) and also attached as a downloadable asset on the [GitHub Release](https://github.com/nus-cee/canvastekk-workflow-sdk/releases) page (no auth)

## Cross-repo Deployment Coordination (DA-1546)

This repo is the **origin** of the dispatch chain — after publishing a release, dispatches `sdk-released` to `canvastekk-workflow-nodes` to trigger a Lambda rebuild.

### Dispatch chain

```
THIS REPO ──sdk-released──► Nodes deploy-lambda.yml ──nodes-deployed──► CWE reseed.yml
```

### Event table (this repo's participation only)

| Event | Direction | Counterparty | Payload |
|---|---|---|---|
| `sdk-released` | **Send** | canvastekk-workflow-nodes | `{sdk_version, environment: "prod", breaking, breaking_changes[], released_at}` |

### Breaking-change detection (Phase 5.2)

`release.yml` scans commits since the last tag for:

- `BREAKING CHANGE:` footer (Conventional Commits spec)
- `!:` in type scope (e.g., `feat(api)!: ...`)

Populates `breaking` boolean + `breaking_changes` array in the dispatch payload. Both the token-generation and dispatch steps use `continue-on-error: true` — a dispatch failure never fails the release.

### Credentials

GitHub App credentials (`GH_APP_ID` variable + `GH_APP_PRIVATE_KEY` secret) are required for the dispatch step. If missing, the dispatch fails silently (`continue-on-error: true`). See `canvastekk-devops/canvastekk-shared-infra` for provisioning.

### Canonical source

Full dispatch pattern template + MAJOR-bump policy: [canvastekk-workflow-engine/AGENTS.md](https://github.com/nus-cee/canvastekk-workflow-engine/blob/dev/AGENTS.md#cross-repo-deployment-coordination-da-1546)
