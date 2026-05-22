# Echo Node — Workflow Examples

Examples showing how the echo node can be used in workflow definitions, including `{{variable}}` template substitution.

> **Note:** These examples are **workflow definition configurations**, not node code. Templates are resolved by the workflow engine **before** the node's `execute()` runs. The node receives fully resolved strings.

---

## Basic Usage (No Templates)

```json
{
  "nodes": [
    {
      "id": "echo-1",
      "node_type": "echo",
      "inputs": {
        "input_file": "https://s3.amazonaws.com/bucket/input.txt?X-Amz-Signature=..."
      }
    }
  ]
}
```

## Path Construction with `{{variable}}` Templates

The workflow engine supports `{{variable}}` template substitution in string inputs. After resolving edges, the engine scans string values for `{{key}}` patterns and substitutes them from the same node's resolved inputs.

### Example: Dynamic File Path

A preceding node outputs `report_id` and `run_id`. The echo node constructs a path using templates:

```json
{
  "nodes": [
    {
      "id": "start",
      "node_type": "__start__",
      "outputs": {
        "run_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
      }
    },
    {
      "id": "process",
      "node_type": "some-processor",
      "outputs": {
        "report_id": 13
      }
    },
    {
      "id": "echo-1",
      "node_type": "echo",
      "inputs": {
        "input_file": "https://storage.example.com/{{report_id}}/runs/{{run_id}}/input/scan.txt"
      }
    }
  ],
  "edges": [
    {"source": "start", "target": "echo-1"},
    {"source": "process", "target": "echo-1"}
  ]
}
```

After template resolution, `echo-1` receives:

```json
{
  "input_file": "https://storage.example.com/13/runs/a1b2c3d4-e5f6-7890-abcd-ef1234567890/input/scan.txt",
  "run_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "report_id": 13
}
```

### Syntax Quick Reference

| Pattern | Behavior |
|---------|----------|
| `{{variable}}` | Replaced with `str(inputs["variable"])` |
| `{variable}` | Literal — single braces are NOT substituted |
| `{{unknown}}` | Left as-is if key not found in inputs |
| Non-string values | Pass through unchanged |

### Key Rules

- **Single-pass** — no recursive substitution (prevents injection)
- **String-only** — non-string inputs (numbers, arrays, objects) are not affected
- **Transparent** — nodes receive fully resolved values, unaware of templating
- **Engine version** — requires DA-1037 or later; older engines pass `{{...}}` as literal text

For the full documentation, see [EXTERNAL-AUTHOR-GUIDE: Template Variable Substitution](../../docs/EXTERNAL-AUTHOR-GUIDE.md#template-variable-substitution).
