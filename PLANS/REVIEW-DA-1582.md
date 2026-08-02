# REVIEW-DA-1582 — Architecture + Standards review of PLAN-DA-1582

**Reviewed:** `PLANS/PLAN-DA-1582.md`
**Reviewers:** architecture lens + standards/research lens (run in primary session — the two requested subagents failed on a model-config error: `architecture-review-subagent` is wired to `zai-coding-plan/glm-5.1`, which is not a valid model id).
**Verdict (architecture):** **Approve-with-changes** — the design is sound; three concrete corrections sharpen correctness and framing.
**Verdict (standards):** The proposed `DeprecationInfo` shape is **richer than most peers** (OpenAPI/JSON Schema/Protobuf are boolean-only) and aligns with RFC 8594/9745 on the removal date, but is **missing two fields the standards consistently include** (deprecation-start date, migration URL). Recommend additive widening.

---

## Part A — Architecture review (against the actual code)

### Strengths (verified)

- **Additive, opt-in field** is the correct minimal-footprint approach; `default=None` means existing nodes are untouched.
- **`deprecation` vs `node_status` separation is sound** — advisory/migration signal orthogonal to operational routing/retirement. The PLAN states this correctly.
- **Wire-format parity (Py + TS)** is the right call given both SDKs emit the engine's `RegisterNodeRequest`.
- **Version bump correctly identified as pipeline-automated** (the ticket's manual-bump AC is genuinely wrong).

### Findings

**[MAJOR A1] The PLAN doesn't mention `python/scripts/check_schema_stability.py` — the CI gate that actually enforces the "non-breaking" claim.**
Evidence: `check_schema_stability.py:51-60` lists `WorkflowNodeManifest` in `MODELS_TO_CHECK`; `:280-284` classifies an *added optional field* as `ADDITIVE` and an *added required field* as `BREAKING`; `:134` serializes via `model.model_json_schema()` (the static schema, NOT `to_dict()`/`model_dump()`). The PR-check workflow (`commit ddbf7a1`, "manifest schema stability check") requires a `major` label for BREAKING changes.
Impact: The PLAN's "no breaking change" AC is *enforced by this gate*, but the PLAN never references it. Adding `deprecation: DeprecationInfo | None = None` → new optional property → classified **ADDITIVE** → no `major` label required → CI green. This *validates* the design but should be stated, and the PLAN should add a step asserting the stability check classifies the change as ADDITIVE (run `python scripts/check_schema_stability.py dump` before/after).
Recommendation: Add a Phase 3 step that runs the stability diff and asserts `ADDITIVE` (not `BREAKING`).

**[MAJOR A2] The `to_dict()` None-exclusion (PLAN 1.3) only patches one of several serialization paths — and the real consumer is `app.py:267`, not "contract tests".**
Evidence: `app.py:267` serves `node.definition.to_dict()` on the `/manifest` endpoint — this is the concrete consumer that must stay byte-identical. But `registry.py:108` (`definition.styles.model_dump(...)`), `registry.py:122` (`default_retry.model_dump(...)`), and `contracts.py:69` (`self.model_dump(mode="json")`) all call `model_dump()` directly. If any future path serializes the whole manifest via `model_dump()`, `deprecation: null` leaks.
Impact: The PLAN's proposed `to_dict()` override leaves `model_dump()` emitting `deprecation: null`, so byte-identity is path-dependent. Today no registry path serializes a full manifest via `model_dump()` (the payload is hand-built in `build_registry_payload`), so it's currently safe — but it's fragile.
Recommendation: Replace the `to_dict()` override (PLAN 1.3) with a Pydantic `@model_serializer(mode="wrap")` that pops `deprecation` when None. This covers **every** instance-serialization path (`to_dict`, `model_dump`, anything downstream) in one place, and does *not* affect `model_json_schema()` (so A1's stability check is unaffected). Cleaner and more robust than overriding one method.

**[MAJOR A3] `DeprecationInfo` should be added to the stability-tracked model set.**
Evidence: `check_schema_stability.py:36-49` (`MODEL_IMPORTS`) and `:51-60` (`MODELS_TO_CHECK`) are the canonical lists. A new public model that is part of the wire contract should be stability-tracked too; otherwise future breaking changes to `DeprecationInfo` (e.g. making `notice` optional, renaming a field) won't be caught by CI.
Recommendation: Add `DeprecationInfo` to both `MODEL_IMPORTS` and `MODELS_TO_CHECK` in the same PR. Add as a Phase 3 step.

**[MINOR A4] `examples/echo_node/handler.py` is the canonical reference node but isn't mentioned.**
Evidence: `examples/echo_node/handler.py:17` constructs a `WorkflowNodeManifest`. AGENTS.md calls it "the canonical reference implementation". The PLAN doesn't require touching it (its manifest stays `deprecation=None`), but a deprecation *example* somewhere would help authors.
Recommendation: Optional — either leave echo node untouched (it stays additive-None) or add a one-line commented example in the EXTERNAL-AUTHOR-GUIDE (PLAN 7.2 already covers this).

**[MINOR A5 — RESOLVED] The `version.ts` auto-bump risk is a non-issue.**
Evidence: `.github/workflows/release.yml:69-73` explicitly lists `typescript/src/version.ts` in the bump loop. The PLAN's Risk row 3 ("version.ts not auto-bumped") and Technical Notes "Pre-flight check" should be **removed/downgraded** — the pipeline already handles it.

**[NIT A6] PLAN 7.3 bundles code+tests+docs+PR.** Slightly non-atomic, but acceptable since it's a single `feat:` commit and the step passed the atomicity self-check. No change required.

### LSP recommendation
`opencode.json` is absent in this repo (so no `lsp` key). The change touches a shared imported module (`definition.py`) consumed across the Python SDK and crosses into TS. Enabling LSP would give ambient cross-file type diagnostics during edits. Recommend (do not auto-apply) adding to a new `opencode.json`:
```json
{ "lsp": { "typescript": {}, "eslint": {}, "pyright": {} } }
```
CLI gates (`ruff`, `pytest`, `tsc`, `vitest`, `tsup`) remain the source of truth.

---

## Part B — Standards / research benchmarking

Primary sources fetched: **RFC 8594** (Sunset), **RFC 9745** (Deprecation). Supporting: Kubernetes deprecation policy, OpenAPI 3.1, JSON Schema, GraphQL spec (established facts cited below).

### B.1 Survey

| Standard / vendor | Primitives | Removal date? | Replacement pointer? | Notice type | bool vs object | Source |
|---|---|---|---|---|---|---|
| **RFC 9745** `Deprecation` header | deprecation **date** (when deprecated/will be) | no (that's Sunset) | via `Link rel="deprecation"` → **URL** | link target (human/machine) | date (object) | https://datatracker.ietf.org/doc/html/rfc9745 |
| **RFC 8594** `Sunset` header | removal/sunset **date** | **yes** (the date) | via `Link rel="sunset"` → **URL** (policy/migration) | link target | date (object) | https://datatracker.ietf.org/doc/html/rfc8594 |
| **RFC 9745 §4 constraint** | Sunset date MUST NOT precede Deprecation date | — | — | — | — | RFC 9745 §4 |
| **OpenAPI 3.1** | `deprecated: boolean` | no | no | no | **boolean** | OAS 3.1 spec, `deprecated` keyword |
| **JSON Schema** (2019-09+) | `deprecated: boolean` | no | no | no | **boolean** | JSON Schema validation, `deprecated` |
| **GraphQL** | `@deprecated(reason: String)` | no | no | free-text `reason` | object (directive) | GraphQL spec, `@deprecated` |
| **gRPC / Protobuf** | `option deprecated = true` | no | no | no | **boolean** | Protobuf language guide |
| **Kubernetes** | deprecated-version + removed-version + replacement-API-group + migration-docs link | yes (removed-version) | **yes** (replacement group/version) | docs URL | **object** | https://kubernetes.io/docs/reference/using-api/deprecation-policy/ |
| **Stripe / GitHub / Twilio** | sunset date + replacement version + migration docs URL | yes | yes (version/endpoint) | docs URL | object | vendor API-deprecation docs |

### B.2 Conformance assessment of `DeprecationInfo(sunset_date, replacement_slug, notice)`

**Alignment (strengths):**
- `sunset_date`  **RFC 8594 Sunset** (removal date) — correct, terminologically exact mapping.
- Object (not boolean) — **richer than OpenAPI/JSON Schema/Protobuf**, on par with the RFCs and Kubernetes (the two closest analogs: a registry of individually-versioned, individually-deprecate-able components).
- `notice` free-text  GraphQL `reason` + RFC Link-relation target text.
- Advisory-only, no behavior change  **RFC 9745 §5** ("deprecation does not change any behavior of the resource") and the PLAN's `deprecation ≠ node_status` principle. Strong conceptual alignment.

**Gaps (where the proposal diverges from the consistent norm):**

- **GAP B1 (Major) — Missing the *deprecation* date (announcement start).** RFC 9745's *core* field is the deprecation date (when it was/will be deprecated), which is **distinct** from the Sunset/removal date. RFC 9745 §4 even orders them: Sunset MUST NOT precede Deprecation. Kubernetes likewise tracks the deprecated-in version *and* the removed-in version as a pair. The proposal captures only the removal end (`sunset_date`); consumers cannot tell *when* deprecation began or how long a node has been deprecated — information a workflow-def-staleness UI (the engine ticket's stated goal) will want.
  *Recommendation:* add `deprecated_at: date | None = None` (when the node was marked deprecated). Aligns with RFC 9745's deprecation date and gives the frontend the announcement-start.

- **GAP B2 (Major) — No migration/docs URL.** RFC 9745 §3 (`Link rel="deprecation"`) and RFC 8594 §6 (`Link rel="sunset"`) both reach for a **URL** for migration/policy info; Stripe/GitHub/Kubernetes all link out to migration docs. The proposal has only free-text `notice` + a `replacement_slug`, forcing any URL into the prose. Machine tooling (frontend badge, IDE plugin) can't follow a link buried in prose.
  *Recommendation:* add `migration_url: str | None = None`. Aligns with RFC 9745 §3 / RFC 8594 §6; lets tooling deep-link to migration docs directly.

- **GAP B3 (Minor) — `replacement_slug` is domain-typed.** Standards favor a URI or a typed reference. *Within this system* a slug is the correct pointer (the engine resolves slug→node), so this is defensible — but it should be *paired* with `migration_url` (the human-doc angle the slug can't cover). Keep the slug; don't rely on it alone.

- **GAP B4 (Minor) — `notice` required vs optional.** RFCs treat the human text as optional (the Link carries the heavy lifting). The proposal makes `notice` mandatory — reasonable given the workflow-builder UI wants to always render *something*, but it means `DeprecationInfo(sunset_date=...)` alone is invalid. Acceptable design choice; document the rationale in the docstring.

- **GAP B5 (Nit) — RFC alignment is undocumented.** Field docstrings should note `sunset_date` maps to RFC 8594 Sunset and (if added) `deprecated_at` maps to RFC 9745 Deprecation. Aids future maintainers and signals intent to the engine/frontend implementers.

### B.3 Recommended revised shape (all additive, all None-omitted)

```python
class DeprecationInfo(BaseModel):
    deprecated_at: date | None = None      # RFC 9745 — when deprecation took effect
    sunset_date: date | None = None        # RFC 8594 — planned removal date
    replacement_slug: str | None = None    # domain pointer (engine resolves slug→node)
    migration_url: str | None = None       # RFC 9745 §3 / RFC 8594 §6 — human/machine migration docs
    notice: str                             # free-text summary (always rendered by the workflow builder)
```

This is a strict superset of the ticket's shape — every existing consumer that only reads `sunset_date`/`replacement_slug`/`notice` is unaffected. The two new fields are optional and None-omitted, so the byte-identity guarantee (PLAN 1.3 / A2) still holds.

---

## Required changes to PLAN-DA-1582 before execution

1. **[A2]** Replace the `to_dict()` override (1.3) with a Pydantic `@model_serializer(mode="wrap")` so *every* instance-serialization path drops `deprecation` when None (not just `to_dict()`).
2. **[A1]** Add a Phase 3 step: run `python scripts/check_schema_stability.py` diff and assert the change is classified **ADDITIVE** (not BREAKING) — this is the CI gate that actually enforces the "non-breaking" AC.
3. **[A3]** Add `DeprecationInfo` to `MODEL_IMPORTS` + `MODELS_TO_CHECK` in `check_schema_stability.py` (new Phase 3 step).
4. **[A5]** Remove the `version.ts` risk row (Risk table #3) and the "Pre-flight check" caveat — `release.yml:72` already bumps it.
5. **[B1/B2 — decision]** Decide whether to widen `DeprecationInfo` to include `deprecated_at` + `migration_url` now (recommended, still additive, standards-aligned) or defer to a follow-up. If deferred, the engine/frontend consumers will likely need them anyway when they build the staleness UI.

Optional: [A4] echo-node example, [A6] 7.3 granularity (no action).
