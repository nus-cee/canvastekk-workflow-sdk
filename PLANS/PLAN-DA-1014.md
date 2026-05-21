# PLAN-DA-1014: Enforce Node Definition Versioning in SDK

**Jira Ticket**: [DA-1014](https://betekk.atlassian.net/browse/DA-1014)
**GitHub Issue**: [#27](https://github.com/nus-cee/canvastekk-workflow-sdk/issues/27)
**Depends On**: [DA-1007](https://betekk.atlassian.net/browse/DA-1007) (engine versioning — merged)
**Branch**: `DA-1014`
**Repo**: `canvastekk-workflow-sdk`
**Priority**: Medium
**Breaking Change**: Yes (minor version bump 0.7.2 → 0.8.0)

---

## Problem

The engine now supports node definition versioning (DA-1007) with `(name, version)` as the composite key and a revision chain. The SDK is backward compatible but does not enforce versioning conventions:

1. **`id`** is manually provided with no validation it matches `{name}-v{version}`. The engine ignores it entirely.
2. **`name`** is described as "slug for routing" but not validated as slug format.
3. **`version`** is described as "semantic version" but accepts any string.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| `id` field | Auto-derived `computed_field` | Engine ignores it; eliminates drift bugs; single source of truth |
| Manual `id` deprecation path | Validate + DeprecationWarning | Graceful migration for existing nodes |
| `name` validation | Regex `^[a-z][a-z0-9-]*[a-z0-9]$` | Must be URL-safe slug matching engine expectations |
| `version` validation | Regex `^\d+\.\d+\.\d+$` | Strict semver (major.minor.patch only) |
| `id` in export payload | Remove | Engine uses `(name, version)`, not `id` |
| Version bump | 0.7.2 → 0.8.0 | Breaking change to NodeDefinition constructor |
| `title` → `label` rename | No change | SDK `title` maps to engine `label` in `export_definition()`; renaming breaks every node for no engine benefit |

---

## Files to Change

| File | Change |
|------|--------|
| `python/canvastekk_workflow_sdk/definition.py` | Auto-derive `id`, add slug/semver validators, deprecation path |
| `python/canvastekk_workflow_sdk/registry.py` | Enhanced error handling for versioning responses |
| `python/canvastekk_workflow_sdk/__main__.py` | CLI validation for slug/semver |
| `python/canvastekk_workflow_sdk/__init__.py` | Bump version to 0.8.0, update docstring example |
| `python/canvastekk_workflow_sdk/base.py` | Update docstring example (remove manual `id`) |
| `python/canvastekk_workflow_sdk/app.py` | Update manifest endpoint (auto-derived `id` transparent) |
| `python/pyproject.toml` | Bump version to 0.8.0 |
| `examples/echo_node/handler.py` | Remove manual `id` from definition |
| `python/tests/test_definition.py` | Update all tests, add slug/semver/id-derivation tests |
| `python/tests/test_registry.py` | Add versioning response tests |
| `python/tests/test_app.py` | Update any `id` assertions |
| `python/tests/test_base.py` | Update any `id` assertions |
| `python/tests/test_main.py` | Add CLI slug/semver validation tests |
| `docs/EXTERNAL-AUTHOR-GUIDE.md` | Document enforced versioning |
| `python/README.md` | Update examples |
| `.opencode/skills/canvastekk-node-builder/SKILL.md` | Update templates and checklist |
| `AGENTS.md` | Update conventions |

---

## Implementation Phases

### Phase 1: Core Model Changes (`definition.py`)

The foundation — auto-derive `id`, validate `name` and `version`.

- [ ] Add `import re` and `import warnings`
- [ ] Add `_SLUG_PATTERN = re.compile(r"^[a-z][a-z0-9-]*[a-z0-9]$")`
- [ ] Add `_SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")`
- [ ] Add `name` field validator: reject if `_SLUG_PATTERN` doesn't match
- [ ] Add `version` field validator: reject if `_SEMVER_PATTERN` doesn't match
- [ ] Remove `id` from `Field()` declarations — make it a `@computed_field @property` returning `f"{self.name}-v{self.version}"`
- [ ] Add `model_validator` to handle deprecated manual `id`:
  - If `id` is passed in constructor kwargs and differs from derived → emit `DeprecationWarning` and validate it matches
  - If `id` matches derived → silently accept
- [ ] Update field descriptions to reflect enforcement
- [ ] Ensure `to_dict()` includes `id` in output (computed_field auto-included via `model_dump`)

**Validation:**
```python
# These should now fail:
NodeDefinition(id="bad", name="UPPER", version="abc", ...)
NodeDefinition(id="bad", name="has spaces", version="1.0", ...)
NodeDefinition(name="echo", version="1.0.0", ...)  # id auto-derived as "echo-v1.0.0"
```

### Phase 2: Update `register_node()` and `export_definition()`

Align registration with engine's new versioning contract.

- [ ] In `registry.py`: parse engine response `action` field (`created`/`updated`/`unchanged`) and log it
- [ ] In `registry.py`: return `action` and `previous_version` in result dict
- [ ] In `registry.py`: handle 409 Conflict (version collision) with clear error
- [ ] In `export_definition()`: do NOT include `id` in the registry payload dict
- [ ] In `export_definition()`: keep `name` and `version` (engine expects them)

### Phase 3: CLI Validation (`__main__.py`)

Surface slug/semver issues at validate time.

- [ ] In `_validate_definition()`: check `name` matches slug pattern → error if not
- [ ] In `_validate_definition()`: check `version` matches semver pattern → error if not
- [ ] In `_validate_definition()`: check if `id` was manually provided → warning (deprecated)
- [ ] Add `id`, `name`, `version` to the report output

### Phase 4: Update Examples and Docstrings

- [ ] `examples/echo_node/handler.py`: remove `id="echo-v1.0.0"` from definition
- [ ] `base.py` docstring example: remove `id=`
- [ ] `__init__.py` module docstring: remove `id=` from example
- [ ] `app.py` manifest endpoint: verify `node.definition.id` still works (computed_field)

### Phase 5: Version Bump

- [ ] `python/canvastekk_workflow_sdk/__init__.py`: `__version__ = "0.8.0"`
- [ ] `python/pyproject.toml`: `version = "0.8.0"`

### Phase 6: Tests

Update existing tests and add new ones.

- [ ] Update ALL existing `NodeDefinition(...)` calls: remove `id=` parameter
- [ ] Add `TestSlugValidation`:
  - [ ] Valid slugs pass: `echo`, `file-loader`, `point-cloud-segment`, `a1`
  - [ ] Invalid slugs rejected: `UPPER`, `has space`, `under_score`, `-leading`, `trailing-`, `1numeric-start`
- [ ] Add `TestSemverValidation`:
  - [ ] Valid versions pass: `1.0.0`, `0.1.0`, `10.20.30`
  - [ ] Invalid versions rejected: `1.0`, `v1.0.0`, `1.0.0-alpha`, `abc`
- [ ] Add `TestIdAutoDerivation`:
  - [ ] `id` auto-derived as `f"{name}-v{version}"`
  - [ ] `id` included in `to_dict()` output
  - [ ] Manual `id` that matches derived → accepted with no warning
  - [ ] Manual `id` that mismatches → DeprecationWarning + accepted (for now)
- [ ] Add `TestRegistryVersioningResponse`:
  - [ ] Mock engine response with `action: "created"` → returned in result
  - [ ] Mock engine response with `action: "updated"` → returned in result
  - [ ] Mock 409 response → clear RegistrationError
- [ ] Add `TestExportDefinitionNoId`:
  - [ ] `export_definition()` output does NOT contain `id` key
  - [ ] `export_definition()` output DOES contain `name` and `version`
- [ ] Add CLI validation tests for slug/semver

### Phase 7: Documentation

- [ ] Update `docs/EXTERNAL-AUTHOR-GUIDE.md`:
  - [ ] Document `name` must be a valid slug (lowercase, hyphens)
  - [ ] Document `version` must be semver (X.Y.Z)
  - [ ] Document `id` is auto-derived, manual setting is deprecated
  - [ ] Document engine creates revision chain entries on registration
- [ ] Update `python/README.md`: remove `id=` from all examples
- [ ] Update `.opencode/skills/canvastekk-node-builder/SKILL.md`: update templates and validation checklist
- [ ] Update `AGENTS.md` Node Creation Conventions: reflect enforced versioning

---

## Acceptance Criteria

- [ ] `id` is auto-derived from `name` + `version` — node authors no longer need to provide it
- [ ] Manual `id` emits DeprecationWarning but still works if matching
- [ ] `name` validates as slug (lowercase, alphanumeric + hyphens, no leading/trailing hyphens)
- [ ] `version` validates as semver (X.Y.Z)
- [ ] `register_node()` logs and returns engine's `action`/`previous_version` from response
- [ ] `export_definition()` does NOT include `id` in payload
- [ ] CLI `validate` reports slug/semver issues
- [ ] All existing tests pass (with updated definitions)
- [ ] New tests cover validators, auto-derivation, deprecation warnings
- [ ] SDK version bumped to 0.8.0
- [ ] Documentation updated (guide, README, skill, AGENTS.md)
- [ ] Echo node example updated

---

## Impact on Node Authors

**Before (0.7.x):**
```python
definition = NodeDefinition(
    id="echo-v1.0.0",      # manual, error-prone
    name="echo",
    version="1.0.0",
    ...
)
```

**After (0.8.0):**
```python
definition = NodeDefinition(
    name="echo",            # validated as slug
    version="1.0.0",        # validated as semver
    ...                     # id auto-derived as "echo-v1.0.0"
)
```

**Migration:** Node authors remove `id=` from their definitions. If they leave it in, they get a DeprecationWarning. If it mismatches, they get a DeprecationWarning + the derived value is used.

---

## Dependencies

- **DA-1007** (merged): Engine node versioning with revision chain

## Security Notes

- No new secrets or credentials involved
- Validation is client-side only; engine validates server-side independently
