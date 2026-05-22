# PLAN-DA-1041: Align SDK registration with engine semver versioning

**Ticket:** [DA-1041](https://betekk.atlassian.net/browse/DA-1041)
**Depends on:** [DA-1040](https://betekk.atlassian.net/browse/DA-1040) (engine semver migration)
**Branch:** `DA-1041`
**Created:** 2026-05-23

## Context

The engine (DA-1040) is migrating its node registry from integer versions (1, 2, 3) to semantic versioning strings ("1.0.0", "1.1.0") with immutability enforcement. This ticket aligns the SDK's documentation and docstrings.

**Key fact:** The SDK's `NodeDefinition.version` has **always** been `str` (semver) with validation. The SDK never sent integers. The engine had its own independent integer versioning that ignored the SDK's version string. After DA-1040, the engine will use the SDK's semver string directly. This is a **documentation-only ticket** — no code logic changes are needed.

## Impact Analysis

### Files requiring changes (11 "independent versioning" references across 6 files + 409 error table)

| File | Location | Current Text | Action |
|------|----------|-------------|--------|
| `python/canvastekk_workflow_sdk/definition.py` | L102-109 (class docstring) | "engine maintains its own independent versioning system" | Rewrite |
| `python/canvastekk_workflow_sdk/definition.py` | L113-116 (field description) | "independent of the engine's own versioning system" | Rewrite |
| `python/canvastekk_workflow_sdk/definition.py` | L309-310 (export_definition docstring) | "engine assigns its own version" | Rewrite |
| `python/canvastekk_workflow_sdk/registry.py` | L79-81 (build_registry_payload docstring) | "engine assigns its own independent version" | Rewrite |
| `python/canvastekk_workflow_sdk/registry.py` | L168-172 (register_node docstring) | "engine assigns its own independent version" | Rewrite |
| `docs/EXTERNAL-AUTHOR-GUIDE.md` | L103 | "for your own tracking" — implies engine ignores version | Rewrite to reflect authoritative shared semver |
| `docs/EXTERNAL-AUTHOR-GUIDE.md` | L105 | "engine maintains its own independent versioning system" | Rewrite |
| `docs/EXTERNAL-AUTHOR-GUIDE.md` | L427 (error table) | 409 = "Node already exists with a different owner" only | Add immutability rejection case (same version + changed data) |
| `docs/EXTERNAL-AUTHOR-GUIDE.md` | L449-450 (409 example) | Only handles ownership conflict | Add immutability conflict example |
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
5. **Update 409 Conflict semantics** — EXTERNAL-AUTHOR-GUIDE error table and example code must reflect new immutability rejection case

## Implementation Phases

### Phase 1: Verify existing SDK behavior (no code change)
- [x] Confirm `_validate_version()` in `definition.py` enforces semver pattern
- [x] Confirm `build_registry_payload()` sends `version` as `str`
- [x] Confirm `id` computed field works with semver strings
- [x] Verify with `poetry run pytest` that existing tests pass

### Phase 2: Update code docstrings (5 locations)
- [x] `definition.py` L102-109: Rewrite NodeDefinition class docstring Versioning section
- [x] `definition.py` L113-116: Rewrite `version` field description
- [x] `definition.py` L309-310: Update `export_definition()` field mapping note
- [x] `registry.py` L79-81: Rewrite `build_registry_payload()` versioning note
- [x] `registry.py` L168-172: Rewrite `register_node()` Versioning section
- [x] `registry.py` `RegisterNodeResult` docstring: List possible `action` values and note semantics depend on engine version

### Phase 3: Update user-facing documentation (6 locations)
- [x] `docs/EXTERNAL-AUTHOR-GUIDE.md` L103: Rewrite "for your own tracking" to reflect authoritative shared semver
- [x] `docs/EXTERNAL-AUTHOR-GUIDE.md` L105: Replace independent versioning note with shared semver + immutability
- [x] `docs/EXTERNAL-AUTHOR-GUIDE.md` L427: Update 409 error table to include immutability rejection (same version + changed data)
- [x] `docs/EXTERNAL-AUTHOR-GUIDE.md` L449-450: Update 409 handling example to include immutability conflict
- [x] `python/README.md` L757: Update versioning section
- [x] `python/README.md` L1014: Update versioning section
- [x] `README.md` L138: Update architecture section

### Phase 4: Update example (1 location)
- [x] `examples/echo_node/handler.py` L19: Update inline comment

### Phase 5: Validation
- [x] `poetry run ruff check canvastekk_workflow_sdk/ tests/` — pass (no code logic changes)
- [x] `poetry run pytest -v` — pass (no code logic changes)
- [x] Expanded grep for remaining outdated language — zero results in .py files; only PLAN-DA-1041.md references remain (expected)
- [x] Review all changes for consistency
- [x] Bump SDK version as patch (`0.10.1` → `0.10.2`) in `__init__.py` and `pyproject.toml`

## Acceptance Criteria

- [x] `NodeDefinition.version` semver validation confirmed working (already implemented, no code change)
- [x] `build_registry_payload()` confirmed compatible with engine's updated semver schema (no code change)
- [x] `id` derivation verified compatible with engine's post-DA-1040 ID format
- [x] `docs/EXTERNAL-AUTHOR-GUIDE.md` updated: version is shared between SDK and engine
- [x] `docs/EXTERNAL-AUTHOR-GUIDE.md` L103 rewritten: "for your own tracking" replaced with shared semver semantics
- [x] `docs/EXTERNAL-AUTHOR-GUIDE.md` 409 error table updated with immutability rejection case
- [x] `python/README.md` updated: all versioning sections reflect shared semver
- [x] `README.md` updated: architecture section reflects shared semver
- [x] Immutability behavior documented (same version + changed data = rejected)
- [x] `definition.py` class + field docstrings updated (3 locations)
- [x] `registry.py` function docstrings updated (2 locations) + `RegisterNodeResult` docstring updated with `action` values
- [x] `examples/echo_node/handler.py` comment updated
- [x] All DA-1028 "independent versioning" language removed from docs and code
- [x] `poetry run ruff check` and `poetry run pytest` pass

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Engine DA-1040 not yet merged | Medium | Low | Doc changes are forward-compatible; can merge before or after engine |
| ID format mismatch with engine after DA-1040 | Low | High | Verify engine's ID derivation still matches `f"{name}-v{version}"` before merging |
| Engine ID migration breaks existing workflow definitions (e.g. `echo-v1` → `echo-v1.0.0`) | Low | High | Engine-side migration concern (DA-1040 handles backfill); SDK does not control workflow definitions |
| "No code changes" underestimation | Medium | Low | 11+ locations need careful rewording — use expanded grep to track completeness |
| Inconsistent wording across docs | Medium | Low | Use consistent terminology: "shared semver version" everywhere |
| 409 Conflict docs outdated | High | Medium | Update EXTERNAL-AUTHOR-GUIDE error table (L427) and example (L449-450) with immutability rejection |
| Incomplete grep misses related phrases ("for your own tracking", "label only") | High | Low | Use expanded grep pattern in Phase 5 covering all semantic variants |
