# PLAN-DA-1582 — Add deprecation metadata field to WorkflowNodeManifest (SDK)

**Issue:** [DA-1582](https://betekk.atlassian.net/browse/DA-1582) — Add deprecation metadata field to WorkflowNodeManifest (SDK)
**Branch:** `DA-1582`
**Epic:** [DA-1577](https://betekk.atlassian.net/browse/DA-1577)
**Origin:** Raised during the DA-1578 architecture review — the legacy `floor-flatness-assessment` node (frozen at v1.4.1) needs a deprecation marker now that its successor `floor-flatness-per-check-assessment` exists, and the SDK has no field for it.

---

## Revisions to the ticket (verified against code on this branch)

The ticket was authored against an older SDK state. Three corrections, confirmed by reading the current source:

1. **Version bump target is wrong.** Ticket AC says "SDK minor version bump (e.g. v0.20.0)", but the SDK is **already at v0.20.0** (`python/pyproject.toml`, `python/canvastekk_workflow_sdk/__init__.py::__version__`, `typescript/src/version.ts`, `typescript/package.json` all show `0.20.0`). Target is **v0.21.0**.
2. **Version bump is NOT manual.** Per repo `AGENTS.md` → Versioning & Releases: *"Versions are NEVER bumped manually."* A `feat:` commit on `main` triggers `.github/workflows/release.yml` → git-cliff → auto minor bump → wheel + GitHub Release + cross-repo `sdk-released` dispatch. So there is **no manual version-edit step**; the implementation commit IS the bump trigger.
3. **TypeScript parity added (user-approved scope expansion).** The ticket's scope table lists Python files only, but this repo ships a parallel TypeScript SDK whose `WorkflowNodeManifestSchema` (`typescript/src/definition.ts:85-104`) has the identical field set and also lacks a deprecation field. For wire-format parity (both SDKs must emit the same `RegisterNodeRequest` payload the engine consumes), the field is added to **both** SDKs. The engine/frontend consumers remain out of scope (separate cross-repo tickets, per the ticket's "Out of scope" section).

---

## Dependency & Consumer Map

| Node (file/module) | Depends on (must precede) | Consumers (who depends on this) | Change risk |
|---|---|---|---|
| `python/.../definition.py` `DeprecationInfo` + `deprecation` field | — | `WorkflowNodeManifest.to_dict()`, `build_registry_payload()`, `__init__.py` exports, all node authors (additive) | low — optional field, default None |
| `python/.../definition.py` `to_dict()` None-exclusion | `DeprecationInfo` exists | `export_definition()`, any caller that JSON-serializes a manifest | low — surgical pop of one key |
| `python/.../registry.py` `build_registry_payload()` | `deprecation` field exists | `register_node()`, `export_definition()`, CI/CD registration payloads | low — key added only when set |
| `python/.../__init__.py` exports | `DeprecationInfo` exists | external node authors importing the SDK | low — additive export |
| `typescript/src/definition.ts` `DeprecationInfoSchema` + field | — | `WorkflowNodeManifestSchema`, `buildRegistryPayload()`, `index.ts` exports | low — optional, nullable default null |
| `typescript/src/registry.ts` `buildRegistryPayload()` | TS `deprecation` field exists | `registerNode()`, `exportDefinition()` | low — key added only when set |
| `typescript/src/index.ts` exports | TS schema exists | external TS node authors | low — additive |
| `python/pyproject.toml` / `__init__.py` / `typescript/package.json` / `typescript/src/version.ts` | all code+tests merged to `main` as `feat:` | release pipeline (`release.yml`) | none — **pipeline auto-bumps; never hand-edited** |

---

## Implementation Phases

### Phase 1 — Python: `DeprecationInfo` model + manifest field

- [ ] **1.1** Add `DeprecationInfo(BaseModel)` to `python/canvastekk_workflow_sdk/definition.py` (fields: `sunset_date: date | None = None`, `replacement_slug: str | None = None`, `notice: str`). Add `from datetime import date` to imports.
    — **Why:** First-class deprecation metadata shape proposed by the ticket; must exist before it can be referenced by the manifest field and registry payload.
    — **Done when:** `DeprecationInfo` is importable and constructs with `notice` required, the two other fields defaulting None.
    — **Consumers affected:** none yet (model only).

- [ ] **1.2** Add `deprecation: DeprecationInfo | None = Field(default=None, ...)` to `WorkflowNodeManifest` in `definition.py`, placed after `styles` and before the `@computed_field id`.
    — **Why:** Attaches the advisory deprecation signal to the manifest as additive, opt-in metadata — the core ask of the ticket. Default None means existing node definitions are unaffected.
    — **Done when:** A `WorkflowNodeManifest` constructs without passing `deprecation`; `manifest.deprecation` is `None` by default.
    — **Consumers affected:** `to_dict()`, `build_registry_payload()` (wired in 1.3 / 2.1); all existing nodes (no change required — they stay `deprecation=None`).

- [ ] **1.3** Override `WorkflowNodeManifest.to_dict()` so `deprecation` is **dropped from output when None**, and kept (serialized) when set. Implement as: `data = self.model_dump(mode="json"); if data.get("deprecation") is None: data.pop("deprecation", None); return data`.
    — **Why:** Ticket AC requires "manifest with `deprecation=None` serializes **identically to today**". Pydantic's default `model_dump` would emit `deprecation: null`, changing every existing manifest's JSON and breaking byte-equality expectations of downstream consumers/contract tests. This matches the registry's "omitted when not set" rule too.
    — **Done when:** `WorkflowNodeManifest(...).to_dict()` on a deprecation-less manifest is byte-identical to pre-change output; a manifest with `deprecation=DeprecationInfo(notice="...")` includes the nested object.
    — **Consumers affected:** `export_definition()` (transparent — it routes through `build_registry_payload`); any external caller serializing a manifest (additive: key appears only when deprecated).

- [ ] **1.4** Export `DeprecationInfo` from `python/canvastekk_workflow_sdk/__init__.py`.
    — **Why:** External node authors need to import the model to mark a node deprecated (`from canvastekk_workflow_sdk import DeprecationInfo`).
    — **Done when:** `DeprecationInfo` appears in `__all__` and is importable from the package root.
    — **Consumers affected:** none (additive export).

### Phase 2 — Python: registry propagation

- [ ] **2.1** In `python/canvastekk_workflow_sdk/registry.py::build_registry_payload()`, add `deprecation` to the payload **only when `definition.deprecation is not None`** (serialize via `definition.deprecation.model_dump(mode="json")`). Do not emit the key when None.
    — **Why:** Propagates the deprecation signal to the engine's `RegisterNodeRequest` payload so downstream (engine store, registry API, eventually frontend) can surface migration guidance. Omitting-when-None keeps payloads byte-identical for non-deprecated nodes (consistent with 1.3 and the ticket AC).
    — **Done when:** `build_registry_payload(manifest_no_deprecation)` dict has no `deprecation` key; `build_registry_payload(manifest_deprecated)` includes the full nested object.
    — **Consumers affected:** `register_node()` (passes through automatically), `export_definition()` (passes through automatically), engine `RegisterNodeRequest` (out-of-scope consumer — separate CWE ticket).

### Phase 3 — Python: tests + gates

- [ ] **3.1** Add tests to `python/tests/test_definition.py`: (a) a manifest built without `deprecation` has `to_dict()` byte-identical to the pre-change shape (no `deprecation` key); (b) a manifest built with `deprecation=DeprecationInfo(notice="...", sunset_date=date(...), replacement_slug="...")` round-trips through `to_dict()` with all three fields present; (c) `DeprecationInfo` requires `notice` (validation error when omitted).
    — **Why:** Locks in the ticket AC ("default-None serializes identically to today; set round-trips") and prevents regressions in the None-exclusion behavior.
    — **Done when:** `poetry run pytest python/tests/test_definition.py -k deprecation` passes; a snapshot/dict-equality assertion confirms absence of the key when None.
    — **Consumers affected:** none (test-only).

- [ ] **3.2** Add tests to `python/tests/test_registry.py`: (a) `build_registry_payload()` on a deprecation-less manifest produces no `deprecation` key; (b) on a deprecated manifest the payload includes the nested `deprecation` object with `notice`/`sunset_date`/`replacement_slug`.
    — **Why:** Guards the registry contract — the engine consumes this payload, so the key's presence/absence must be deterministic.
    — **Done when:** `poetry run pytest python/tests/test_registry.py -k deprecation` passes.
    — **Consumers affected:** none (test-only).

- [ ] **3.3** Run `poetry run ruff check canvastekk_workflow_sdk/ tests/` and `poetry run pytest -v`. Fix any findings before proceeding.
    — **Why:** Repo quality gate (AGENTS.md → SDK Development). Must be green before TS work so a Python-only failure isn't misattributed to later changes.
    — **Done when:** Both commands exit 0.
    — **Consumers affected:** none (gate).

### Phase 4 — TypeScript: schema + manifest field

- [ ] **4.1** Add `DeprecationInfoSchema = z.object({ sunset_date: z.string().nullable().default(null), replacement_slug: z.string().nullable().default(null), notice: z.string() })` to `typescript/src/definition.ts`. Export the schema and `export type DeprecationInfo = z.infer<typeof DeprecationInfoSchema>`. Use `z.string()` for `sunset_date` (ISO 8601) to match the engine's wire format — do NOT use `z.date()` (it serializes to `Date` objects, breaking JSON).
    — **Why:** TS parity with Python's `DeprecationInfo`. `string` for the date keeps JSON-round-trip parity with Python's `date` (which `model_dump(mode="json")` emits as ISO string).
    — **Done when:** `DeprecationInfoSchema` parses `{ notice: "..." }` and infers nullable for the two optional fields.
    — **Consumers affected:** none yet (schema only).

- [ ] **4.2** Add `deprecation: DeprecationInfoSchema.nullable().default(null)` to the `WorkflowNodeManifestSchema` object (after `styles`, before the `.transform(...)`).
    — **Why:** Attaches the field to the TS manifest, mirroring the Python change for wire-format parity.
    — **Done when:** `WorkflowNodeManifestSchema.parse({...minimal manifest...})` yields `.deprecation === null`; parsing with a deprecation object yields the nested shape.
    — **Consumers affected:** `buildRegistryPayload()` (wired in 5.1); existing TS nodes (no change — field defaults null).

### Phase 5 — TypeScript: registry propagation

- [ ] **5.1** In `typescript/src/registry.ts::buildRegistryPayload()`, add `deprecation` to the payload **only when `definition.deprecation` is not null** (emit `payload.deprecation = definition.deprecation`). Omit the key when null.
    — **Why:** Wire-format parity with the Python registry payload (Phase 2.1) — the engine receives the same shape regardless of which SDK produced it.
    — **Done when:** `buildRegistryPayload(manifestNoDeprecation)` produces no `deprecation` key; `buildRegistryPayload(manifestDeprecated)` includes the nested object.
    — **Consumers affected:** `registerNode()`, `exportDefinition()` (both pass through automatically).

### Phase 6 — TypeScript: tests + gates

- [ ] **6.1** Add a TS test mirroring Python 3.1: default-null manifest strips `deprecation` from serialized output; a deprecated manifest round-trips with all three fields; `notice` is required.
    — **Why:** Parity test coverage; locks the null-exclusion contract on the TS side.
    — **Done when:** The new vitest case passes.
    — **Consumers affected:** none (test-only).

- [ ] **6.2** Add a TS test mirroring Python 3.2: `buildRegistryPayload()` omits `deprecation` when null, includes the nested object when set.
    — **Why:** Guards the TS registry wire contract — the engine consumes this payload, so key presence/absence must be deterministic and match the Python payload exactly.
    — **Done when:** The new vitest case passes.
    — **Consumers affected:** none (test-only).

- [ ] **6.3** Export `DeprecationInfoSchema` and the `DeprecationInfo` type from `typescript/src/index.ts` (alongside the existing `WorkflowNodeManifestSchema` / `WorkflowNodeManifest` exports).
    — **Why:** External TS node authors need the symbols to mark a node deprecated.
    — **Done when:** `import { DeprecationInfoSchema, type DeprecationInfo } from "canvastekk-workflow-sdk"` resolves.
    — **Consumers affected:** none (additive).

- [ ] **6.4** Run `npx tsc --noEmit`, `npx vitest run`, `npx tsup`. Fix any findings.
    — **Why:** Repo quality gate (AGENTS.md → TypeScript SDK). All three must be green.
    — **Done when:** All three commands exit 0.
    — **Consumers affected:** none (gate).

### Phase 7 — Docs + release

- [ ] **7.1** Update API-reference tables in `python/README.md` and `typescript/README.md` to document the new `deprecation` field on the manifest (shape, defaults, behavior). Only edit if those READMEs enumerate manifest fields (verify first; skip silently if they don't).
    — **Why:** Per repo `AGENTS.md` → Critical Documentation Structure, the language READMEs are the SDK API reference and must reflect new manifest fields.
    — **Done when:** Both READMEs (if they list manifest fields) include `deprecation` with the correct shape.
    — **Consumers affected:** SDK readers.

- [ ] **7.2** Check `docs/EXTERNAL-AUTHOR-GUIDE.md` for any manifest-field enumeration or deprecation-guidance section; add a short "Marking a node deprecated" subsection if the guide documents node authoring. Skip if not applicable.
    — **Why:** AGENTS.md mandates the external guide stay in sync with node-authoring workflow changes. Deprecation is a new authoring capability.
    — **Done when:** Guide either updated with a deprecation example, or confirmed not to enumerate fields (documented in the commit body).
    — **Consumers affected:** external node authors.

- [ ] **7.3** Commit all code+test+docs changes as a single `feat:` commit (Conventional Commits). Squash Python + TS + docs into one logical change: `feat: add deprecation metadata field to WorkflowNodeManifest`. Push `DA-1582` and open a PR to `main`.
    — **Why:** (a) Atomic feature commit; (b) the `feat:` type is what triggers `release.yml` → git-cliff minor bump → **v0.21.0** → wheel publish → `sdk-released` dispatch to `canvastekk-workflow-nodes` (with `breaking: false`, since additive). This replaces the ticket's manual "version bump" AC.
    — **Done when:** PR opened; on merge to `main` the release pipeline produces v0.21.0 with a wheel asset and fires the cross-repo dispatch.
    — **Consumers affected:** `canvastekk-workflow-nodes` (auto-rebuild via dispatch), downstream node authors (opt-in field).

---

## Technical Notes

- **Additive only.** `deprecation` is optional (Python `None` / TS `null`). Existing node definitions — `FloorFlatnessNode` and all others — are unaffected and need no changes.
- **`deprecation` is NOT `node_status`.** `node_status` (`active | inactive | dead`) remains the operational routing lever (retirement). `deprecation` is an advisory/migration signal orthogonal to it. A deprecated node stays `active` until retired.
- **Version-immutability interaction.** Because the field is additive metadata (not a schema/behavior change), a node can later set `deprecation` with a **patch** bump. This resolves the DA-1578 problem where deprecating a frozen node currently forces an awkward version bump.
- **None-exclusion is deliberate.** Both `to_dict()` (Py) and `buildRegistryPayload()` (Py + TS) omit the key when the field is unset, so non-deprecated nodes serialize byte-identically to today. This protects contract tests and downstream byte-equality assumptions.
- **`sunset_date` wire format.** Python `date` → `model_dump(mode="json")` emits ISO 8601 string; TS uses `z.string()` to match. Engine stores as string.
- **Version bump is automated.** Do NOT edit `pyproject.toml` / `__init__.py` / `package.json` / `version.ts` by hand — `release.yml` overwrites them. The `feat:` commit IS the bump trigger.  **Pre-flight check:** AGENTS.md lists the auto-bumped files as `pyproject.toml`, `__init__.py`, `typescript/package.json`, `dotnet/Directory.Build.props` — it does **not** explicitly list `typescript/src/version.ts`. Confirm in `release.yml` that `version.ts` is bumped (it currently reads `0.20.0`, so *something* keeps it in sync); if not, raise a separate ticket rather than hand-editing here.

## Dependencies

- **Originating:** DA-1578 (sibling-node retirement pattern), DA-1577 (parent epic).
- **Out of scope (separate cross-repo tickets):** Engine (CWE) `RegisterNodeRequest` schema persist + store `deprecation`; engine registry API exposure; engine workflow-def staleness UI; frontend deprecation badge; `deploy-lambda.yml` allowlist addition in consuming apps.
- **Automated downstream:** on merge to `main`, `release.yml` dispatches `sdk-released` (breaking=false) to `canvastekk-workflow-nodes` → triggers Lambda rebuild.

## Risks & Mitigation

| Risk | Likelihood | Mitigation |
|---|---|---|
| `model_dump` emits `deprecation: null`, breaking byte-equality / contract tests | high if untreated | 1.3 + 2.1 explicitly pop/omit the key when None; 3.1/3.2 assert absence |
| TS `z.date()` for `sunset_date` breaks JSON round-trip | medium | 4.1 mandates `z.string()` (ISO 8601) |
| `version.ts` not auto-bumped by pipeline → TS reports stale version after release | low (currently in sync) | 7.3 pre-flight verification; separate ticket if drift found |
| Engine rejects unknown `deprecation` key in `RegisterNodeRequest` | low (additive payloads usually tolerated) | Out-of-scope engine ticket will formally accept the field; if registration 400s, omit key from payload until engine ships — gated by 3.2/6.2 contract tests |

## Success Metrics (Acceptance Criteria — from ticket, revised)

- [ ] `DeprecationInfo` model added (Python + TS): `sunset_date`, `replacement_slug`, `notice`.
- [ ] `WorkflowNodeManifest` gains optional `deprecation` (Python `None` / TS `null` default) — additive, no behavior change for existing nodes.
- [ ] `build_registry_payload()` (Py + TS) includes `deprecation` when set, omits when unset.
- [ ] Default-unset manifest serializes byte-identically to today (Py `to_dict()` + both `buildRegistryPayload()`).
- [ ] Unit tests on both sides: round-trip + default-unset + `notice` required.
- [ ] No breaking change to existing node definitions.
- [ ] Release: `feat:` commit → pipeline auto-bumps to **v0.21.0** → wheel on GitHub Release → `sdk-released` dispatch (breaking=false). *(Revised from the ticket's manual "v0.20.0" AC.)*

---
*Tracking progress with ticket-plan-workflow-skill*
