# PLAN-DA-1038: Document {{variable}} Template Substitution Behavior for Node Authors

**JIRA Ticket**: [DA-1038](https://betekk.atlassian.net/browse/DA-1038)
**Related Engine Ticket**: [DA-1037](https://betekk.atlassian.net/browse/DA-1037) — `feat(engine): implement {{variable}} template substitution in _resolve_inputs`
**Branch**: `DA-1038`
**Created**: 2026-05-22
**Status**: Implementation Complete

---

## Overview

The CanvasTEKK workflow engine now supports `{{variable}}` template substitution in node string inputs (DA-1037). After edge resolution resolves inputs for each node, the engine scans string values for `{{variable}}` placeholders and substitutes them from the same node's resolved input dict.

Node authors need to know about this behavior so they can:
1. Design their node input schemas to take advantage of `{{}}` templates
2. Understand that any string input can contain `{{variable}}` placeholders
3. Avoid using `{{` and `}}` in their node if it conflicts with the syntax

---

## Impact Analysis

### Files Affected

| File | Change | Severity |
|------|--------|----------|
| `docs/EXTERNAL-AUTHOR-GUIDE.md` | Add `{{variable}}` template substitution section | High |
| `python/README.md` | Add template substitution section to API reference | High |
| `README.md` | Update features/architecture section to mention template support | Low |
| `examples/echo_node/WORKFLOW_EXAMPLES.md` | Add workflow JSON example showing `{{}}` template usage (not in handler.py — templates are resolved before `execute()`) | Medium |

### NOT Affected

- `python/canvastekk_workflow_sdk/definition.py` — No model changes; template resolution is engine-side
- `python/canvastekk_workflow_sdk/context.py` — No changes; nodes receive fully resolved strings
- `python/canvastekk_workflow_sdk/contracts.py` — No changes
- `python/canvastekk_workflow_sdk/*.py` — No code changes; documentation-only ticket
- `python/tests/` — No test changes needed in SDK (engine tests cover DA-1037)

---

## Key Decisions

### Decision 1: Documentation-only, no SDK code changes

The `{{variable}}` template substitution is implemented entirely in the workflow engine (DA-1037). The SDK's `BaseNode.execute()` receives fully resolved strings — node authors never interact with the templating system directly. This ticket is purely about documenting the feature for node authors.

### Decision 2: Document in EXTERNAL-AUTHOR-GUIDE as primary reference

The `docs/EXTERNAL-AUTHOR-GUIDE.md` is the single source of truth for third-party node authors. The template substitution documentation should be a dedicated section with:
- How it works (transparent to nodes)
- Syntax reference (`{{key}}`, single braces literal, single-pass)
- Practical examples (path construction, URLs)
- Availability of `run_id` from `__start__` node
- Edge cases and caveats

### Decision 3: Version bump NOT required

This is documentation-only with no code changes. No version bump needed unless the team prefers a docs-only patch release.

---

## Implementation Phases

### Phase 1: Document Template Substitution in EXTERNAL-AUTHOR-GUIDE

- [x] Add "Template Variable Substitution" section to `docs/EXTERNAL-AUTHOR-GUIDE.md`
  - [x] Explain the `{{variable}}` syntax and how it works
  - [x] Document that substitution is transparent to nodes
  - [x] Document single-brace literals (`{` `}` are not substituted)
  - [x] Document single-pass (no recursive substitution) — no injection risk since `{{}}` in resolved values is not re-processed
  - [x] Document unresolved placeholders left as-is
  - [x] Provide practical examples (path construction, URLs, messages)
  - [x] Note that `run_id` is available from `__start__` node via edges
  - [x] Add caveat about avoiding `{{` in node output patterns
  - [x] Note that `input_schema` constraints (`pattern`, `format`, `minLength`, etc.) validate against **resolved** values, not template syntax — design constraints to match the expected resolved output
  - [x] Add engine version compatibility note: template substitution is available in engine versions that include DA-1037; on older engines, `{{...}}` passes through as literal text
  - [x] Add security note: single-pass substitution prevents recursive injection, but node authors should still validate resolved values before using them in file paths, URLs, or shell commands

### Phase 2: Update python/README.md

- [x] Add template substitution section to the Python SDK README
- [x] Include syntax reference and examples
- [x] Link to EXTERNAL-AUTHOR-GUIDE for full documentation

### Phase 3: Update Root README.md

- [x] Add mention of template variable support in features/architecture section

### Phase 4: Update Echo Node Example

- [x] Add `examples/echo_node/WORKFLOW_EXAMPLES.md` with workflow JSON showing how `{{}}` templates are configured when using the echo node in a workflow definition
- [x] Do NOT modify `handler.py` — templates are resolved by the engine before `execute()` runs, so there's nothing to demonstrate in node code

### Phase 5: Final Validation

- [x] `poetry run ruff check canvastekk_workflow_sdk/ tests/` passes (no code changes — documentation-only)
- [x] `poetry run pytest -v` passes (no code changes — documentation-only)
- [x] Verify documentation is clear and accurate for node authors

---

## Acceptance Criteria

### P0 — Blocking

- [x] SDK documentation (EXTERNAL-AUTHOR-GUIDE or README) updated with `{{variable}}` template section
- [x] Example showing how to use templates in node input definitions
- [x] Note about `run_id` being available from `__start__` node
- [x] Note about avoiding `{{` in node output patterns if it could conflict

### P1 — Required

- [x] Documentation covers syntax: `{{key}}` substitution, single braces literal, single-pass
- [x] Documentation covers what is NOT affected (non-strings, strings without `{{}}`, unresolved)
- [x] `poetry run ruff check` and `poetry run pytest` pass

### P2 — Recommended

- [x] Echo node `WORKFLOW_EXAMPLES.md` includes template usage example
- [x] Root README mentions template support

---

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| DA-1037 not yet merged | Low — documentation can be written from ticket spec | Verify against engine implementation before merge |
| Node authors confused about engine vs SDK responsibility | Low | Clear documentation that substitution is transparent, engine-side only |
| Syntax conflict with other templating systems | Low | Document the `{{...}}` syntax clearly and note it's specific to the engine |
| Node `pattern` constraints reject resolved template values | Medium — e.g. `^[a-zA-Z/_-]+$` passes template syntax but resolved value with digits may violate a stricter pattern | Document that `input_schema` constraints apply to resolved values, not template syntax |
| Engine version mismatch — templates on old engine | Low — `{{...}}` passes through as literal text on engines without DA-1037 | Add version compatibility note in documentation |

---

## Template Substitution Quick Reference

### Syntax
- `{{variable}}` → replaced with `str(inputs["variable"])`
- Single braces `{` `}` → literal (no substitution)
- Single-pass (no recursive substitution)
- Unresolved placeholders → left as-is, logged at DEBUG
- Non-string values → pass through unchanged

### Example

Node static inputs (defined in workflow):
```json
{
  "folder_path": "{{report_id}}/runs/{{run_id}}/output/zip/",
  "report_id": 13,
  "run_id": "a1b2c3d4-..."
}
```

After engine template resolution, node receives:
```json
{
  "folder_path": "13/runs/a1b2c3d4-.../output/zip/",
  "report_id": 13,
  "run_id": "a1b2c3d4-..."
}
```

---

*Tracking progress with ticket-plan-workflow-skill*
