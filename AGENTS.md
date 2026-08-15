@README.md

## Repo Management

This repo ships the CanvasTEKK Workflow SDK (Python + TypeScript). This file defines **how to work in and manage the repo** — API reference lives in the READMEs and guides linked below, not here.

### Documentation Sync (mandatory)

Docs are layered — they must stay consistent when the SDK changes:

| File | Role |
|------|------|
| `docs/EXTERNAL-AUTHOR-GUIDE.md` | Single source of truth for external node authors |
| `python/README.md` / `typescript/README.md` | Full SDK API reference per language (incl. workflow builder & local runner) |
| `README.md` | Repo overview, features, architecture |
| `examples/echo_node/` | Canonical reference implementation |

**Behavior:** any change to `register_node()`, `BaseNode`, `NodeDefinition`, `WorkflowBuilder`, `WorkflowRunner`, auth, or the node creation workflow must be mirrored in `docs/EXTERNAL-AUTHOR-GUIDE.md` and the affected README(s) in the same change. Never finish a task with docs out of sync, and never duplicate that reference content here — link to it.

### Skill Routing

| User Request Pattern | Skill to Load |
|----------------------|---------------|
| "Create a workflow node" / "Build a CanvasTEKK node" / "Scaffold a node" | `canvastekk-node-builder` — always load first |
| "How do I use InstanceSet/MeasurementSet/PlaneSet?" | `canvastekk-node-patterns` |
| "Create a point cloud segmentation node" | Both skills — builder for workflow, patterns for domain example |
| "Add auth/middleware/webhooks to my node" | `canvastekk-node-patterns` |
| "Review my node" / "Validate my handler" | `canvastekk-node-builder` — validation checklist |
| "Build a workflow" / "Test run a workflow" / "WorkflowBuilder" / "WorkflowRunner" / `LocalFileServer` | No skill — the `workflow` package is documented in the READMEs |

### Node Creation

Follow `docs/EXTERNAL-AUTHOR-GUIDE.md` and the `canvastekk-node-builder` skill checklist rather than reimplementing conventions from memory — the skill enforces the file-field rules (`format: "file"`, `x-accept`, `x-maxSizeBytes`), `context.output_path()`, auto-derived node `id`, progress reporting, and the full project scaffold (handler + Dockerfile + pyproject.toml + tests). Copy from `examples/echo_node/` as the reference implementation.

### Verification Gates

Run before declaring any change done:

- Python (`python/`): `poetry run ruff check canvastekk_workflow_sdk/ tests/`, then `poetry run pytest -v`
- TypeScript (`typescript/`): `npx tsc --noEmit`, then `npx vitest run`; `npx tsup` to build
- Wire-format types are `snake_case` (Python engine compatibility); internal TypeScript types are `camelCase`

### Releases

Fully automated by `.github/workflows/release.yml` (git-cliff + conventional commits). **Behavior:**

- **Never bump version strings manually** — the pipeline overwrites `pyproject.toml`, `__init__.py`, `typescript/package.json`, and `dotnet/Directory.Build.props`
- Control releases via commit type: `feat:` → minor, `fix:` → patch, `feat!:` / `BREAKING CHANGE:` footer → major-or-minor, `docs:` / `chore:` / `ci:` / `refactor:` / `test:` / `style:` → no release
- Wheels publish to GitHub Packages (`nus-cee`) and as GitHub Release assets (no auth) automatically

### Cross-repo Dispatch (DA-1546)

Every release dispatches `sdk-released` to `canvastekk-workflow-nodes` to trigger a Lambda rebuild (this repo is the origin of the dispatch chain). **Behavior:**

- Flag breaking changes in commit messages (`!:` or `BREAKING CHANGE:` footer) — they propagate to the downstream payload
- Dispatch failure is non-fatal by design (`continue-on-error`); missing GitHub App creds (`GH_APP_ID` / `GH_APP_PRIVATE_KEY`) fail silently — don't "fix" this into a hard failure
- Canonical dispatch pattern + MAJOR-bump policy: [canvastekk-workflow-engine/AGENTS.md](https://github.com/nus-cee/canvastekk-workflow-engine/blob/dev/AGENTS.md#cross-repo-deployment-coordination-da-1546)

## OpenCode Rule Blocks

<!-- opencode:codegraph -->
The `codegraph_*` tools are the interface (`status` → `search`/`callers`/`callees`/`impact`/`node`/`files`). Never call `read_mcp_resource`/`list_mcp_resources` — runtime-denied (upstream tool-list bug). Main session: lightweight lookups only — never `codegraph_explore`/`codegraph_context` (flood context; spawn an explore agent).

<!-- opencode:lsp -->
On reviews with >10-file or shared-module changes where `opencode.json` has no `lsp` key and a built-in server matches: append a one-line LSP-enable recommendation (TS/JS/Next.js → `typescript`+`eslint`; Python → `pyright`). Recommend only — never auto-edit `opencode.json`.
