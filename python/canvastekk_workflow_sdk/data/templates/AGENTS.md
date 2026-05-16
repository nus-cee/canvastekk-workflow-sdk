## CanvasTEKK Node Development

This project uses the CanvasTEKK Workflow SDK. When a user asks to create, scaffold, or build a workflow node, follow these routing rules:

### Skill Routing

| User Request Pattern | Skill to Load | When |
|----------------------|---------------|------|
| "Create a workflow node" / "Build a CanvasTEKK node" / "Scaffold a node" | `canvastekk-node-builder` | Always load first for any node creation task |
| "How do I use InstanceSet/MeasurementSet/PlaneSet?" | `canvastekk-node-patterns` | Load for domain-specific patterns and examples |
| "Create a point cloud segmentation node" | `canvastekk-node-builder` + `canvastekk-node-patterns` | Load both — builder for workflow, patterns for domain example |
| "Add auth/middleware/webhooks to my node" | `canvastekk-node-patterns` | Load for advanced integration patterns |
| "Review my node" / "Validate my handler" | `canvastekk-node-builder` | Load for the validation checklist |

### Node Creation Conventions

When creating CanvasTEKK workflow nodes, always follow these rules:

1. **Use `canvastekk-workflow-sdk` from GitHub Packages**: `pip install canvastekk-workflow-sdk --index-url https://pypi.pkg.github.com/nus-cee/`
2. **File fields use `format: "file"` with `type: "string"`**: Never use `format: "binary"` or `type: "object"` on file fields — the SDK's model_validator rejects them
3. **Include `x-accept` and `x-maxSizeBytes`** on every file input field
4. **Download with `httpx.stream()`**: Use streaming with `iter_bytes(chunk_size=65536)`, `timeout=30.0`, and `follow_redirects=True`
5. **Call `validate_file_input()` after download**: Always validate downloaded files against schema constraints
6. **Write outputs to `context.output_path(filename)`**: Never hardcode paths; return them as `str(output_path)`
7. **`definition` must be both module-level AND class attribute**: Module-level enables CLI validation; class attribute satisfies `BaseNode.__init_subclass__`
8. **Node IDs follow `{name}-v{version}` format**: e.g., `segment-v1.0.0`
9. **Report progress with `context.report_progress()`**: At key stages (download, process, save)
10. **Always generate Dockerfile + pyproject.toml + tests**: A complete node project includes all four files
