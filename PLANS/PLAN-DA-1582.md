# PLAN-DA-1582 — Add deprecation metadata field to WorkflowNodeManifest (SDK)

**Issue:** [DA-1582](https://betekk.atlassian.net/browse/DA-1582) — Add deprecation metadata field to WorkflowNodeManifest (SDK)
**Branch:** `DA-1582`
**Epic:** [DA-1577](https://betekk.atlassian.net/browse/DA-1577)
**Review:** `PLANS/REVIEW-DA-1582.md` (architecture + standards review whose findings are incorporated below)
**Origin:** Raised during the DA-1578 architecture review — the legacy `floor-flatness-assessment` node (frozen at v1.4.1) needs a deprecation marker now that its successor `floor-flatness-per-check-assessment` exists, and the SDK has no field for it.

---

## Revisions to the ticket (verified against code + standards)

The ticket was authored against an older SDK state and pre-dates a standards benchmark. Four corrections:

1. **Version bump target is wrong.** Ticket AC says "SDK minor version bump (e.g. v0.20.0)", but the SDK is **already at v0.20.0** (`python/pyproject.toml`, `python/canvastekk_workflow_sdk/__init__.py::__version__`, `typescript/src/version.ts`, `typescript/package.json` all show `0.20.0`). Target is **v0.21.0**.
2. **Version bump is NOT manual.** Per repo `AGENTS.md` → Versioning & Releases: *"Versions are NEVER bumped manually."* A `feat:` commit on `main` triggers `.github/workflows/release.yml` → git-cliff → auto minor bump → wheel + GitHub Release + cross-repo `sdk-released` dispatch. There is **no manual version-edit step**; the implementation commit IS the bump trigger. (`release.yml:69-73` confirms the bump loop includes `typescript/src/version.ts`, so no version-file is left behind.)
3. **TypeScript parity added (user-approved scope expansion).** The ticket's scope table lists Python files only, but this repo ships a parallel TypeScript SDK whose `WorkflowNodeManifestSchema` (`typescript/src/definition.ts:85-104`) has the identical field set and also lacks a deprecation field. For wire-format parity (both SDKs must emit the same `RegisterNodeRequest` payload the engine consumes), the field is added to **both** SDKs. The engine/frontend consumers remain out of scope (separate cross-repo tickets).
4. **`DeprecationInfo` widened to standards-aligned shape (from REVIEW-DA-1582 Part B).** Benchmarking against RFC 8594 (Sunset), RFC 9745 (Deprecation), and Kubernetes showed the ticket's 3-field shape omits two fields the standards consistently carry: the *deprecation-start* date (RFC 9745's core field, distinct from the removal date) and a *migration/docs URL* (RFC 9745 §3 `Link rel="deprecation"`, RFC 8594 §6 `Link rel="sunset"`). The shape is widened to 5 fields; both additions are optional + None-omitted, so the change remains strictly additive.

### Proposed shape (revised)

```python
class DeprecationInfo(BaseModel):
    deprecated_at:   date | None = None   # RFC 9745 — when deprecation took effect (announcement start)
    sunset_date:     date | None = None   # RFC 8594 — planned removal date; None = no firm date yet
    replacement_slug: str | None = None   # domain pointer — engine resolves slug → node
    migration_url:   str | None = None    # RFC 9745 §3 / RFC 8594 §6 — human/machine migration docs
    notice:          str                  # free-text summary always rendered by the workflow builder
```

---

## Dependency & Consumer Map

| Node (file/module) | Depends on (must precede) | Consumers (who depends on this) | Change risk |
|---|---|---|---|
| `python/.../definition.py` `DeprecationInfo` + `deprecation` field + `model_serializer` | — | `WorkflowNodeManifest.to_dict()`/`model_dump()` via serializer, `build_registry_payload()`, `__init__.py` exports, `app.py:267` `/manifest` endpoint, all node authors (additive) | low — optional field, default None |
| `python/.../definition.py` `model_serializer` None-exclusion | `DeprecationInfo` exists | `/manifest` endpoint (`app.py:267`), any caller that JSON-serializes a manifest | low — drops one key when None across all paths |
| `python/.../registry.py` `build_registry_payload()` | `deprecation` field exists | `register_node()`, `export_definition()`, CI/CD registration payloads | low — key added only when set |
| `python/.../__init__.py` exports | `DeprecationInfo` exists | external node authors importing the SDK | low — additive export |
| `python/scripts/check_schema_stability.py` `MODEL_IMPORTS` + `MODELS_TO_CHECK` | `DeprecationInfo` exported | the CI schema-stability gate (PR check from DA-1546) | low — registers the new model for contract enforcement |
| `typescript/src/definition.ts` `DeprecationInfoSchema` + field | — | `WorkflowNodeManifestSchema`, `buildRegistryPayload()`, `index.ts` exports | low — optional, nullable default null |
| `typescript/src/registry.ts` `buildRegistryPayload()` | TS `deprecation` field exists | `registerNode()`, `exportDefinition()` | low — key added only when set |
| `typescript/src/index.ts` exports | TS schema exists | external TS node authors | low — additive |
| `python/pyproject.toml` / `__init__.py` / `typescript/package.json` / `typescript/src/version.ts` | all code+tests merged to `main` as `feat:` | release pipeline (`release.yml`) | none — **pipeline auto-bumps all four files; never hand-edited** |

---

## Implementation Phases

### Phase 1 — Python: `DeprecationInfo` model + manifest field + serializer

- [x] **1.1** Add `DeprecationInfo(BaseModel)` to `python/canvastekk_workflow_sdk/definition.py` with five fields: `deprecated_at: date | None = None`, `sunset_date: date | None = None`, `replacement_slug: str | None = None`, `migration_url: str | None = None`, `notice: str`. Add `from datetime import date` to imports. Document RFC alignment in each field's `description` (`deprecated_at` → RFC 9745, `sunset_date` → RFC 8594, `migration_url` → RFC 9745 §3 / RFC 8594 §6).
    — **Why:** First-class deprecation metadata shape; must exist before it can be referenced by the manifest field, serializer, and registry payload. The 5-field shape (vs the ticket's 3) comes from the standards benchmark in REVIEW-DA-1582 Part B — RFC 9745's core field is the *deprecation* date and RFC 9745 §3 / RFC 8594 §6 both reach for a migration URL.
    — **Done when:** `DeprecationInfo` is importable; constructs with `notice` required and the four other fields defaulting None.
    — **Consumers affected:** none yet (model only).

- [x] **1.2** Add `deprecation: DeprecationInfo | None = Field(default=None, ...)` to `WorkflowNodeManifest` in `definition.py`, placed after `styles` and before the `@computed_field id`.
    — **Why:** Attaches the advisory deprecation signal to the manifest as additive, opt-in metadata — the core ask of the ticket. Default None means existing node definitions are unaffected.
    — **Done when:** A `WorkflowNodeManifest` constructs without passing `deprecation`; `manifest.deprecation` is `None` by default.
    — **Consumers affected:** serializer (1.3), `build_registry_payload()` (2.1); all existing nodes (no change required — they stay `deprecation=None`).

- [x] **1.3** Add a `@model_serializer(mode="wrap")` to `WorkflowNodeManifest` that pops `deprecation` from the output dict when it is None. Leave `to_dict()` as `return self.model_dump(mode="json")` (unchanged) — the serializer transparently covers `to_dict()`, `model_dump()`, and every other instance-serialization path. Do **not** override `to_dict()` itself.
    — **Why:** The concrete consumer is `app.py:267` (`/manifest` endpoint serves `node.definition.to_dict()`), which is NOT routed through `build_registry_payload`. A bare `to_dict()` override would still let `deprecation: null` leak through any `model_dump()` caller (e.g. `registry.py:108/122`, `contracts.py:69`). The wrap serializer drops None for **all** instance paths in one place. It does **not** affect `model_json_schema()` (static schema generation), so the schema-stability gate still sees `deprecation` as a property — correctly classified ADDITIVE.
    — **Done when:** `WorkflowNodeManifest(...).to_dict()` AND `.model_dump(mode="json")` on a deprecation-less manifest both omit the `deprecation` key; a manifest with `deprecation=DeprecationInfo(notice="...")` includes the nested object on both paths.
    — **Consumers affected:** `export_definition()` (routes through `build_registry_payload` — unaffected); `/manifest` endpoint (`app.py:267` — now byte-clean); any external caller serializing a manifest (key appears only when deprecated).

- [x] **1.4** Export `DeprecationInfo` from `python/canvastekk_workflow_sdk/__init__.py`.
    — **Why:** External node authors need to import the model to mark a node deprecated (`from canvastekk_workflow_sdk import DeprecationInfo`).
    — **Done when:** `DeprecationInfo` appears in `__all__` and is importable from the package root.
    — **Consumers affected:** none (additive export).

### Phase 2 — Python: registry propagation

- [x] **2.1** In `python/canvastekk_workflow_sdk/registry.py::build_registry_payload()`, add `deprecation` to the payload **only when `definition.deprecation is not None`** (serialize via `definition.deprecation.model_dump(mode="json")` — the 1.3 serializer already drops nested-None fields, but the top-level key is hand-added here). Do not emit the key when None.
    — **Why:** Propagates the deprecation signal to the engine's `RegisterNodeRequest` payload so downstream (engine store, registry API, eventually frontend) can surface migration guidance. Omitting-when-None keeps payloads byte-identical for non-deprecated nodes and means legacy nodes never send the key (so an engine that doesn't yet accept `deprecation` is never fed it except for nodes that are actually deprecated).
    — **Done when:** `build_registry_payload(manifest_no_deprecation)` dict has no `deprecation` key; `build_registry_payload(manifest_deprecated)` includes the full nested object.
    — **Consumers affected:** `register_node()` (passes through automatically), `export_definition()` (passes through automatically), engine `RegisterNodeRequest` (out-of-scope consumer — separate CWE ticket).

### Phase 3 — Python: contract gate + tests + quality gate

- [x] **3.1** Register `DeprecationInfo` in `python/scripts/check_schema_stability.py`: add it to `MODEL_IMPORTS` (import from `canvastekk_workflow_sdk`) and to `MODELS_TO_CHECK`.
    — **Why:** `check_schema_stability.py:51-60` is the canonical list of public models whose schema stability CI enforces (PR gate from DA-1546). A new public wire-contract model should be stability-tracked too; otherwise future breaking changes to `DeprecationInfo` (renaming a field, changing optionality) won't be caught by CI.
    — **Done when:** `poetry run python scripts/check_schema_stability.py dump` includes a `DeprecationInfo` entry.
    — **Consumers affected:** the CI stability gate (additive registration).

- [x] **3.2** Run a schema-stability diff (`dump` on `main` vs `DA-1582`, then `diff`) and assert the change is classified **ADDITIVE** (new optional field on `WorkflowNodeManifest` + new model added), not BREAKING.
    — **Why:** `check_schema_stability.py:280-284` classifies an added optional field as ADDITIVE and an added required field as BREAKING. The PLAN's "no breaking change" AC is *enforced by this gate* — asserting ADDITIVE here proves the design before the CI PR check runs. Uses `model_json_schema()` (`:134`), which the 1.3 serializer does not touch, so the classification is unaffected by None-exclusion.
    — **Done when:** diff output reports `ADDITIVE` changes only; `breaking=false` in `GITHUB_OUTPUT`.
    — **Consumers affected:** none (verification).

- [x] **3.3** Add tests to `python/tests/test_definition.py`: (a) a manifest built without `deprecation` omits the key from **both** `to_dict()` and `model_dump(mode="json")`; (b) a manifest built with a fully-populated `DeprecationInfo(deprecated_at=..., sunset_date=..., replacement_slug=..., migration_url=..., notice=...)` round-trips through `to_dict()` with all five fields present; (c) `DeprecationInfo` requires `notice` and tolerates the four optional fields being omitted.
    — **Why:** Locks in the ticket AC ("default-None serializes identically to today; set round-trips") AND the 1.3 serializer guarantee across both serialization entry points — the `/manifest` endpoint uses `to_dict()`, so both paths must be clean.
    — **Done when:** `poetry run pytest python/tests/test_definition.py -k deprecation` passes; dict-equality assertions confirm the key is absent when None on both paths.
    — **Consumers affected:** none (test-only).

- [x] **3.4** Add tests to `python/tests/test_registry.py`: (a) `build_registry_payload()` on a deprecation-less manifest produces no `deprecation` key; (b) on a deprecated manifest the payload includes the nested `deprecation` object with all five fields.
    — **Why:** Guards the registry wire contract — the engine consumes this payload, so the key's presence/absence must be deterministic and the shape complete.
    — **Done when:** `poetry run pytest python/tests/test_registry.py -k deprecation` passes.
    — **Consumers affected:** none (test-only).

- [x] **3.5** Run `poetry run ruff check canvastekk_workflow_sdk/ tests/ scripts/` and `poetry run pytest -v`. Fix any findings before proceeding.
    — **Why:** Repo quality gate (AGENTS.md → SDK Development). Must be green before TS work so a Python-only failure isn't misattributed to later changes.
    — **Done when:** Both commands exit 0.
    — **Consumers affected:** none (gate).

### Phase 4 — TypeScript: schema + manifest field

- [x] **4.1** Add `DeprecationInfoSchema = z.object({ deprecated_at: z.string().nullable().default(null), sunset_date: z.string().nullable().default(null), replacement_slug: z.string().nullable().default(null), migration_url: z.string().nullable().default(null), notice: z.string() })` to `typescript/src/definition.ts`. Export the schema and `export type DeprecationInfo = z.infer<typeof DeprecationInfoSchema>`. Use `z.string()` for both date fields (ISO 8601) to match the engine's wire format — do NOT use `z.date()` (it serializes to `Date` objects, breaking JSON).
    — **Why:** TS parity with Python's 5-field `DeprecationInfo`. `string` for dates keeps JSON-round-trip parity with Python's `date` (which `model_dump(mode="json")` emits as ISO string).
    — **Done when:** `DeprecationInfoSchema` parses `{ notice: "..." }` and infers nullable for the four optional fields.
    — **Consumers affected:** none yet (schema only).

- [x] **4.2** Add `deprecation: DeprecationInfoSchema.nullable().default(null)` to the `WorkflowNodeManifestSchema` object (after `styles`, before the `.transform(...)`). Do not add None-stripping to the `.transform()` — on the TS side no path serializes a raw manifest to JSON (the wire goes through `buildRegistryPayload`, which omits-when-null in 5.1), so in-memory `null` is harmless.
    — **Why:** Attaches the field to the TS manifest, mirroring the Python change for wire-format parity. The Python `model_serializer` (1.3) is needed there because `app.py:267` serializes via `to_dict()`; TS has no equivalent raw-manifest endpoint, so a transform tweak would be dead code.
    — **Done when:** `WorkflowNodeManifestSchema.parse({...minimal manifest...})` yields `.deprecation === null`; parsing with a deprecation object yields the nested shape.
    — **Consumers affected:** `buildRegistryPayload()` (wired in 5.1); existing TS nodes (no change — field defaults null).

### Phase 5 — TypeScript: registry propagation

- [x] **5.1** In `typescript/src/registry.ts::buildRegistryPayload()`, add `deprecation` to the payload **only when `definition.deprecation` is not null** (emit `payload.deprecation = definition.deprecation`). Omit the key when null.
    — **Why:** Wire-format parity with the Python registry payload (Phase 2.1) — the engine receives the same shape regardless of which SDK produced it. This is the sole TS serialization point, so omitting here is sufficient (no transform change needed, per 4.2).
    — **Done when:** `buildRegistryPayload(manifestNoDeprecation)` produces no `deprecation` key; `buildRegistryPayload(manifestDeprecated)` includes the nested object.
    — **Consumers affected:** `registerNode()`, `exportDefinition()` (both pass through automatically).

### Phase 6 — TypeScript: tests + gates

- [x] **6.1** Add a TS test mirroring Python 3.3: a fully-populated `deprecation` round-trips through `WorkflowNodeManifestSchema.parse()` with all five fields; `notice` is required; the four optional fields default to null.
    — **Why:** Parity test coverage; locks the TS schema contract.
    — **Done when:** The new vitest case passes.
    — **Consumers affected:** none (test-only).

- [x] **6.2** Add a TS test mirroring Python 3.4: `buildRegistryPayload()` omits `deprecation` when null, includes the nested object when set.
    — **Why:** Guards the TS registry wire contract — the engine consumes this payload, so key presence/absence must be deterministic and match the Python payload exactly.
    — **Done when:** The new vitest case passes.
    — **Consumers affected:** none (test-only).

- [x] **6.3** Export `DeprecationInfoSchema` and the `DeprecationInfo` type from `typescript/src/index.ts` (alongside the existing `WorkflowNodeManifestSchema` / `WorkflowNodeManifest` exports).
    — **Why:** External TS node authors need the symbols to mark a node deprecated.
    — **Done when:** `import { DeprecationInfoSchema, type DeprecationInfo } from "canvastekk-workflow-sdk"` resolves.
    — **Consumers affected:** none (additive).

- [x] **6.4** Run `npx tsc --noEmit`, `npx vitest run`, `npx tsup`. Fix any findings.
    — **Why:** Repo quality gate (AGENTS.md → TypeScript SDK). All three must be green.
    — **Done when:** All three commands exit 0.
    — **Consumers affected:** none (gate).

### Phase 7 — Docs + release

- [x] **7.1** Update API-reference tables in `python/README.md` and `typescript/README.md` to document the new `deprecation` field on the manifest (5-field shape, defaults, None-omission behavior, RFC alignment). Only edit if those READMEs enumerate manifest fields (verify first; skip silently if they don't).
    — **Why:** Per repo `AGENTS.md` → Critical Documentation Structure, the language READMEs are the SDK API reference and must reflect new manifest fields.
    — **Done when:** Both READMEs (if they list manifest fields) include `deprecation` with the correct shape.
    — **Consumers affected:** SDK readers.

- [x] **7.2** Check `docs/EXTERNAL-AUTHOR-GUIDE.md` for any manifest-field enumeration or deprecation-guidance section; add a short "Marking a node deprecated" subsection (with a 5-field example and the RFC references) if the guide documents node authoring. Skip if not applicable.
    — **Why:** AGENTS.md mandates the external guide stay in sync with node-authoring workflow changes. Deprecation is a new authoring capability.
    — **Done when:** Guide either updated with a deprecation example, or confirmed not to enumerate fields (documented in the commit body).
    — **Consumers affected:** external node authors.

- [x] **7.3** Commit all code+test+docs+gate changes as a single `feat:` commit (Conventional Commits). Squash Python + TS + docs + the stability-check registration into one logical change: `feat: add deprecation metadata field to WorkflowNodeManifest`. Push `DA-1582` and open a PR to `main`.
    — **Why:** (a) Atomic feature commit; (b) the `feat:` type is what triggers `release.yml` → git-cliff minor bump → **v0.21.0** → wheel publish → `sdk-released` dispatch to `canvastekk-workflow-nodes` (with `breaking: false`, since additive). This replaces the ticket's manual "version bump" AC. The PR check will also run `check_schema_stability.py` (registered in 3.1, asserted ADDITIVE in 3.2).
    — **Done when:** PR opened; on merge to `main` the release pipeline produces v0.21.0 with a wheel asset and fires the cross-repo dispatch.
    — **Consumers affected:** `canvastekk-workflow-nodes` (auto-rebuild via dispatch), downstream node authors (opt-in field).

---

## Technical Notes

- **Additive only.** `deprecation` is optional (Python `None` / TS `null`). Existing node definitions — `FloorFlatnessNode`, the echo node, all others — are unaffected and need no changes.
- **`deprecation` is NOT `node_status`.** `node_status` (`active | inactive | dead`) remains the operational routing lever (retirement). `deprecation` is an advisory/migration signal orthogonal to it (RFC 9745 §5: "deprecation does not change any behavior of the resource"). A deprecated node stays `active` until retired.
- **Version-immutability interaction.** Because the field is additive metadata (not a schema/behavior change), a node can later set `deprecation` with a **patch** bump. This resolves the DA-1578 problem where deprecating a frozen node currently forces an awkward version bump.
- **None-exclusion is deliberate and covers all Python paths.** The `model_serializer` (1.3) drops `deprecation` when None from *every* instance-serialization path (`to_dict`, `model_dump`), so non-deprecated nodes serialize byte-identically to today. This protects the `/manifest` endpoint (`app.py:267`) and contract tests. The TS side needs no equivalent because the only TS wire path is `buildRegistryPayload`, which omits-when-null (5.1); no TS endpoint serializes a raw manifest.
- **Schema-stability gate interaction.** `check_schema_stability.py` uses `model_json_schema()` (static schema), which the `model_serializer` does **not** affect. The gate sees `deprecation` as a new optional property → classified ADDITIVE (`:280-284`) → no `major` label required.
- **RFC alignment.** `deprecated_at` → RFC 9745 (Deprecation header: the date deprecation took effect); `sunset_date` → RFC 8594 (Sunset header: the removal date); `migration_url` → RFC 9745 §3 `Link rel="deprecation"` / RFC 8594 §6 `Link rel="sunset"`. RFC 9745 §4 notes Sunset MUST NOT precede Deprecation — the SDK does not enforce this invariant (both are optional dates); leave that policy to the engine.
- **Wire format.** Python `date` → `model_dump(mode="json")` emits ISO 8601 string; TS uses `z.string()` to match. Engine stores as string.
- **Version bump is automated.** Do NOT edit `pyproject.toml` / `__init__.py` / `package.json` / `version.ts` by hand — `release.yml:69-73` overwrites all four. The `feat:` commit IS the bump trigger.

## Dependencies

- **Originating:** DA-1578 (sibling-node retirement pattern), DA-1577 (parent epic).
- **Out of scope (separate cross-repo tickets):** Engine (CWE) `RegisterNodeRequest` schema persist + store `deprecation`; engine registry API exposure; engine workflow-def staleness UI (the consumer that will read `deprecated_at` / `sunset_date`); frontend deprecation badge; `deploy-lambda.yml` allowlist addition in consuming apps.
- **Automated downstream:** on merge to `main`, `release.yml` dispatches `sdk-released` (breaking=false) to `canvastekk-workflow-nodes` → triggers Lambda rebuild.

## Risks & Mitigation

| Risk | Likelihood | Mitigation |
|---|---|---|
| `model_dump`/`to_dict` emit `deprecation: null`, breaking byte-equality on `/manifest` or in contract tests | high if untreated | 1.3 `model_serializer` drops None across **all** Python instance paths; 3.3 asserts absence on both `to_dict()` and `model_dump()` |
| `DeprecationInfo` not in the stability-tracked model set → future breaking changes uncaught | medium | 3.1 registers it in `MODEL_IMPORTS` + `MODELS_TO_CHECK` |
| TS `z.date()` for date fields breaks JSON round-trip | medium | 4.1 mandates `z.string()` (ISO 8601) for both dates |
| Engine rejects unknown `deprecation` key in `RegisterNodeRequest` | low | 2.1/5.1 emit the key **only when set**, so non-deprecated nodes never send it; if the engine 400s for a deprecated node, the engine consumer ticket is the blocker (gated by 3.4/6.2 contract tests) |

## Success Metrics (Acceptance Criteria — from ticket, revised + standards-aligned)

- [x] `DeprecationInfo` model added (Python + TS) with five fields: `deprecated_at`, `sunset_date`, `replacement_slug`, `migration_url`, `notice` (RFC-aligned).
- [x] `WorkflowNodeManifest` gains optional `deprecation` (Python `None` / TS `null` default) — additive, no behavior change for existing nodes.
- [x] `model_serializer` (Py) + `buildRegistryPayload` omit-when-null (Py + TS) → default-unset manifest serializes byte-identically to today across `to_dict()` **and** `model_dump()`.
- [x] `build_registry_payload()` (Py + TS) includes `deprecation` when set, omits when unset.
- [x] `check_schema_stability.py` classifies the change **ADDITIVE** (not BREAKING) and `DeprecationInfo` is registered in the tracked-model set.
- [x] Unit tests on both sides: 5-field round-trip + default-unset omission + `notice` required.
- [x] No breaking change to existing node definitions.
- [ ] Release: `feat:` commit → pipeline auto-bumps to **v0.21.0** → wheel on GitHub Release → `sdk-released` dispatch (breaking=false). *(Revised from the ticket's manual "v0.20.0" AC.)*

---
*Tracking progress with ticket-plan-workflow-skill*
