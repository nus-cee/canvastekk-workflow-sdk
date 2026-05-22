# PLAN-DA-1041: Align SDK registration with engine semver versioning

**Ticket:** [DA-1041](https://betekk.atlassian.net/browse/DA-1041)
**Depends on:** [DA-1040](https://betekk.atlassian.net/browse/DA-1040) (engine semver migration)
**Branch:** `DA-1041`
**Created:** 2026-05-23

## Context

The engine (DA-1040) is migrating its node registry from integer versions (1, 2, 3) to semantic versioning strings ("1.0.0", "1.1.0") with immutability enforcement. This ticket aligns the SDK's documentation and docstrings.

**Key fact:** The SDK's `NodeDefinition.version` has **always** been `str` (semver) with validation. The SDK never sent integers. The engine had its own independent integer versioning that ignored the SDK's version string. After DA-1040, the engine will use the SDK's semver string directly. This is a **documentation-only ticket** — no code logic changes are needed.

## Impact Analysis

### Files requiring changes (10 "independent versioning" references across 6 files)

| File | Location | Current Text | Action |
|------|----------|-------------|--------|
| `python/canvastekk_workflow_sdk/definition.py` | L102-109 (class docstring) | "engine maintains its own independent versioning system" | Rewrite |
| `python/canvastekk_workflow_sdk/definition.py` | L113-116 (field description) | "independent of the engine's own versioning system" | Rewrite |
| `python/canvastekk_workflow_sdk/definition.py` | L309-310 (export_definition docstring) | "engine assigns its own version" | Rewrite |
| `python/canvastekk_workflow_sdk/registry.py` | L79-81 (build_registry_payload docstring) | "engine assigns its own independent version" | Rewrite |
| `python/canvastekk_workflow_sdk/registry.py` | L168-172 (register_node docstring) | "engine assigns its own independent version" | Rewrite |
| `docs/EXTERNAL-AUTHOR-GUIDE.md` | L105 | "engine maintains its own independent versioning system" | Rewrite |
| `python/README.md` | L757 | "engine maintains its own independent versioning system" | Rewrite |
| `python/README.md` | L1014 | "engine assigns its own independent version" | Rewrite |
| `README.md` | L138 | "engine has a separate, independent versioning system" | Rewrite |
| `examples/echo_node/handler.py` | L19 | "engine assigns its own version independently" | Rewrite |

### Files requiring NO changes

| File | Reason |
|------|--------|
| `python/canvastekk_workflow_sdk/definition.py` (logic) | `_validate_version()` + `_SEMVER_PATTERN` already enforce semver |
| `python/canvastekk_workflow_sdk/registry.py` (logic) | `build_registry_payload()` already sends `version` as `str` |
| `python/canvastekk_workflow_sdk/definition.py` (`id`) | Computed `f"{name}-v{version}"` already works with semver |
| Test files | No test logic changes needed (validation already covered) |

## Key Decisions

1. **No code logic changes** — semver validation and payload format are already correct
2. **Add immutability documentation** — document that same version + changed data = rejected by engine (new behavior from DA-1040)
3. **Deprecation window is irrelevant for SDK** — `_validate_version()` rejects integers at definition time, so they can never reach the engine via the SDK
4. **Clarify in DA-1040 comments** — the engine team incorrectly states "SDK must change int->str" when the SDK already uses `str`

## Implementation Phases

### Phase 1: Verify existing SDK behavior (no code change)
- [ ] Confirm `_validate_version()` in `definition.py` enforces semver pattern
- [ ] Confirm `build_registry_payload()` sends `version` as `str`
- [ ] Confirm `id` computed field works with semver strings
- [ ] Verify with `poetry run pytest` that existing tests pass

### Phase 2: Update code docstrings (5 locations)
- [ ] `definition.py` L102-109: Rewrite NodeDefinition class docstring Versioning section
- [ ] `definition.py` L113-116: Rewrite `version` field description
- [ ] `definition.py` L309-310: Update `export_definition()` field mapping note
- [ ] `registry.py` L79-81: Rewrite `build_registry_payload()` versioning note
- [ ] `registry.py` L168-172: Rewrite `register_node()` Versioning section

### Phase 3: Update user-facing documentation (4 locations)
- [ ] `docs/EXTERNAL-AUTHOR-GUIDE.md` L105: Replace independent versioning note with shared semver + immutability
- [ ] `python/README.md` L757: Update versioning section
- [ ] `python/README.md` L1014: Update versioning section
- [ ] `README.md` L138: Update architecture section

### Phase 4: Update example (1 location)
- [ ] `examples/echo_node/handler.py` L19: Update inline comment

### Phase 5: Validation
- [ ] `poetry run ruff check canvastekk_workflow_sdk/ tests/` — pass
- [ ] `poetry run pytest -v` — pass
- [ ] Grep for remaining "independent version" or "assigns its own version" — zero results
- [ ] Review all changes for consistency

## Acceptance Criteria

- [ ] `NodeDefinition.version` semver validation confirmed working (already implemented, no code change)
- [ ] `build_registry_payload()` confirmed compatible with engine's updated semver schema (no code change)
- [ ] `id` derivation verified compatible with engine's post-DA-1040 ID format
- [ ] `docs/EXTERNAL-AUTHOR-GUIDE.md` updated: version is shared between SDK and engine
- [ ] `python/README.md` updated: all versioning sections reflect shared semver
- [ ] `README.md` updated: architecture section reflects shared semver
- [ ] Immutability behavior documented (same version + changed data = rejected)
- [ ] `definition.py` class + field docstrings updated (3 locations)
- [ ] `registry.py` function docstrings updated (2 locations)
- [ ] `examples/echo_node/handler.py` comment updated
- [ ] All DA-1028 "independent versioning" language removed from docs and code
- [ ] `poetry run ruff check` and `poetry run pytest` pass

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Engine DA-1040 not yet merged | Medium | Low | Doc changes are forward-compatible; can merge before or after engine |
| ID format mismatch with engine after DA-1040 | Low | High | Verify engine's ID derivation still matches `f"{name}-v{version}"` before merging |
| "No code changes" underestimation | Medium | Low | 10 locations need careful rewording — use grep to track completeness |
| Inconsistent wording across docs | Medium | Low | Use consistent terminology: "shared semver version" everywhere |
