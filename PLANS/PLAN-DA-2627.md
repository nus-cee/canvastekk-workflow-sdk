# PLAN: SDK manifest vocabulary alignment (slug/name/description/version)

**Branch**: feat/DA-2627
**Issue**: https://betekk.atlassian.net/browse/DA-2627
**Base**: main (7ca0e08 — v0.26.4; this repo has no dev branch, main is the integration branch)

> Review status: architecture-reviewed + requirements-relay resolved. WARN findings (safety-mechanism text, two missed adoption-time consumers) and NOTE findings (compat determinism pins, `id` field fate, `workflow/` do-not-touch guard) folded in; Mode R answers adopted with amendments (one-way engine-ticket blocker, DA-2604 same-commit fail-closed AC, FE blast radius verified closed).

## Acceptance Criteria

- [ ] Manifest carries all four standard fields with standard spellings: `slug` (identity), `name` (display), `description`, `version` — in BOTH the python and typescript packages, on the wire (`/manifest` output) and at construction (`NodeDefinition`/manifest schema)
- [ ] Both language packages released with aligned versions (automated `release.yml` on merge — a `feat`-bearing commit yields ≥ 0.27.0 per `cliff.toml` `features_always_bump_minor`; both packages bump in lockstep via `scripts/bump_versions.py`; no manual version edits)
- [ ] A manifest-served node registers with display name + description visible in the registry row once adoption lands (construction compat maps legacy `name=`+`title=` to `slug=`+display `name=` so existing nodes keep constructing; registration mapping itself is the register-CLI / adoption scope — see Technical Notes for the COMPLETE adoption pairing)
- [ ] Docs stay in sync per repo AGENTS.md: `docs/EXTERNAL-AUTHOR-GUIDE.md`, `python/README.md`, `typescript/README.md`, root `README.md`, the two embedded skills, and `examples/echo_node/`
- [ ] Gates green: python `ruff check canvastekk_workflow_sdk/ tests/` + `pytest -v`; typescript `tsc --noEmit` + `vitest run` + `tsup`

## Vocabulary contract (the word-collision rule)

The manifest today spells identity `name` ("Slug for routing") and display `title`. The standard moves BOTH words: identity → `slug`, display → `name`. Because `name` changes meaning, wire-level dual vocabulary is IMPOSSIBLE (`name` cannot mean identity and display in one payload). Compatibility therefore lives at CONSTRUCTION only, with a deterministic rule:

- **New vocabulary (preferred)**: `slug=<id>, name=<display>` → served verbatim.
- **Legacy call**: the legacy map fires ONLY when `slug` is absent AND BOTH `name` and `title` are present → `slug=name`, display `name=title`, emit DeprecationWarning (`python`) / `console.warn` (ts) naming the new spellings. **Never implement a `slug ?? name` fallback** — it would silently map a lowercase display name into identity.
- `slug` present + `title` present: `title` ignored with warning (display comes from `name`).
- `slug` present + `name` absent: error — display name is required in the new vocabulary.
- `name` only (no `slug`, no `title`): error in both vocabularies — the message disambiguates: "identity goes in `slug=`; legacy `name=`+`title=` construction still works".
- Wire output (`to_dict`, zod transform result, `/manifest` response): the four standard fields with NO `title` and no alias identity keys. The wire legitimately keeps the contract fields (schemas, `token_cost`, retry, category/metadata, `sdk_version`, `mode`) and the computed `id` field STAYS, becoming slug-derived (`{slug}-v{version}`) — it has live consumers (`/health` at `app.py:423`, `diff.py:26`).

## Dependency & Consumer Map

| Node (file/module) | Depends on (must precede) | Consumers (who depends on this) | Change risk |
|--------------------|---------------------------|---------------------------------|-------------|
| `python/.../definition.py` `WorkflowNodeManifest` (name→slug, title→name, before-validator legacy map) | — | every SDK surface: `/manifest` endpoint, registry, base node, diff, `__main__`, workflow models, ALL downstream node repos, engine registration, external node authors | high — breaking wire+constructor change; mitigated by construction compat + version gating |
| `python/.../app.py` `/manifest` endpoint (docstring identity list + reads) | definition flip | engine `fetch_node_manifest` + `compare_node_to_manifest` (verify endpoint), future register CLI | medium — engine verify reads `manifest["name"]` as identity; safe ONLY because every consumer pins the SDK by **exact wheel URL** (nodes 0.26.1, engine 0.25.0, ff-app 0.25.0, wall-app 0.14.1). The `sdk-released` dispatch is UNGATED (rebuilds on every release, `sdk_breaking` gates nothing) but rebuilds install the exact pinned version — nothing auto-adopts 0.27.0. Adoption is manual via DA-2604/2605 and must pair with the engine prerequisites below |
| `python/.../{base,registry,diff,__main__,logging,context}.py` identity reads (`.name`→`.slug`; display `.title`→`.name`) | definition flip | internal only | medium — mechanical; `base.py:501,595` pass `node_name=` LOG kwarg names whose VALUES flip (log kwarg names are log-format vocabulary, not wire — leave the kwarg name, flip the value); DO NOT touch `workflow/` (see next row) |
| `python/.../workflow/models.py` + `typescript/src/workflow/models.ts` | DO NOT TOUCH | engine `SaveWorkflowRequest` wire contract | already standard — `WorkflowDefinitionNode` carries `slug` + display `name` (python `models.py:56-68`, ts `models.ts:50-63`); renaming anything here breaks the engine's canonical wire |
| `typescript/src/definition.ts` zod schema + `getNodeId` | — | ts package mirrors python: base-node, registry, app, workflow/builder | high — same breaking semantics, same compat rule |
| `typescript/src/{base-node,registry,app,logging,workflow/builder,...}.ts` identity reads | definition flip | internal only | medium — grep counts include unrelated domain `name` fields (e.g. `contracts/measurement.ts`); rename ONLY identity-of-node reads |
| `docs/EXTERNAL-AUTHOR-GUIDE.md`, READMEs, `data/skills/*.md`, `examples/echo_node/` | code flip | node authors (the guide is the source of truth) | low — mandatory sync per AGENTS.md |
| Release (`feat!:` commit → cliff `--bump` → `bump_versions.py` → dispatch) | all above merged | canvastekk-workflow-nodes + ff-app Lambdas (auto-rebuild on sdk-released), engine verify | controlled — `cliff.toml` `features_always_bump_minor=true` + `breaking_always_bump_major=false` ⇒ any `feat`-bearing commit yields ≥0.27.0, NEVER a patch. Deploy safety invariant: the exact wheel-URL pins stay exact — verify pin style unchanged in all four repos at merge time (a converted-to-range pin would auto-adopt and flip live manifests before the engine pairing lands) |
| nodes `.github/workflows/deploy-lambda.yml:520-535` register-step manifest rewrite (`m['name']` identity `:523`, `m.get('title')` display `:524`, `ALLOWED` whitelist without `slug` `:532`) | NOT changed in this PR | node registration at adoption (DA-2604) | breaks at adoption, not at release — safe while exact wheel pins hold. Every registration 422s while failures degrade to `::warning::` (`:566-574`) and the reseed dispatch still fires (`:612-627`) ⇒ silent registry drift. Pairs with a DA-2604 same-commit AC: parser reads `slug` identity / `name` display / `ALLOWED` += `slug`, AND parse failure hard-fails BEFORE the reseed dispatch fires (warn-and-continue is the silent-drift mode — a severity fix, not just vocabulary) |
| engine manifest ingestion via its own installed SDK model (discover `api/v2/workflows/nodes/router.py:561-583`, seed/refresh `node_registry.py:902-917` hard-fails `sdk_def.name != slug`, `from_sdk` `schemas/converters.py:125,139`, verify `workflow_node_service.py:209`; engine SDK pin 0.25.0) | NOT changed in this PR | registry seed/refresh/discover/verify for every node | breaks at adoption, not at release — safe while exact wheel pins hold. Pairs with a NEW engine ticket (one-way blocker to DA-2604/2605 — NOT a mutual link): flip all four read sites to `slug` identity AND bump the SDK pin to an exact 0.27.x in ONE atomic change; the pin bump must never merge ahead of the read flips (0.27's compat map flips `.name` to display ⇒ seed hard-fails every legacy node) |

## Implementation Phases

### Phase 1: Python package vocabulary flip

- [x] **1.1** `WorkflowNodeManifest`: rename identity field `name` → `slug` (keep the slug pattern validation + field_validator, updated messages) and display `title` → `name` (required display); add a `model_validator(mode="before")` implementing the Vocabulary contract rule above (strict legacy trigger: `slug` absent AND `name` AND `title` present → map + DeprecationWarning; NO `slug ?? name` fallback; `name`-only errors with the disambiguating message); `to_dict` drops `title` and alias identity keys; the computed `id` stays and becomes slug-derived (`{slug}-v{version}`)
    — **Why:** ticket item 2 — identity spelled `slug` everywhere; the word collision means compat must be resolved at construction deterministically, not on the wire; `id` has live consumers (`/health`, `diff.py`) and must survive
    — **Done:** fields flipped (`definition.py`), before-validator `_map_legacy_vocabulary` implements all four determinism rules, `id` slug-derived, export docstring mapping updated; one fix: the deprecation message lives at module level (a pydantic class attr with leading underscore becomes `ModelPrivateAttr` — unhashable in `warnings.warn`); files: `python/canvastekk_workflow_sdk/definition.py`; fixes: ModelPrivateAttr relocation
    — **Consumers affected:** all python SDK surfaces, downstream node repos, engine registration ingestion, external authors

- [x] **1.2** Sweep python internal reads: `base.py`, `app.py` (endpoint docstring identity list + reads), `registry.py`, `diff.py`, `__main__.py`, `logging.py`, `context.py`, `__init__.py` exports/docs. Identity reads flip `.name` → `.slug`; display reads flip `.title` → `.name`. `base.py:501,595` `node_name=` LOG kwargs keep their kwarg NAME (log-format vocabulary) but carry the slug VALUE. **Do not touch `workflow/models.py`** — already canonical (`slug` + display `name` against the engine's `SaveWorkflowRequest`)
    — **Why:** item 2 — "identity field spelled slug everywhere in both packages"; half-flipped internals would silently keep serving the old vocabulary from some paths
    — **Done:** base.py 4 identity reads (incl. both `node_name=` kwarg values), registry.py `build_registry_payload` (`name`=slug value, `label`=display — engine register shape unchanged), `__main__.py` manifest summary key `slug`, app.py FastAPI `title=` kwarg value + `/manifest` docstring identity list, diff.py `_HANDLED_KEYS` + slug-mismatch reads/message, `__init__.py` docstring example; `rg "\.title\b"` returns no display stragglers; `workflow/` untouched (`git diff --stat` proves it); files: `base.py, app.py, registry.py, diff.py, __main__.py, __init__.py`; fixes: none
    — **Consumers affected:** internal SDK paths only

- [x] **1.3** Python tests: update manifest/definition/registry/diff/app/workflow tests to the new vocabulary + add explicit compat tests pinning the determinism rules: legacy map fires ONLY on slug-absent + name + title (with warning); `slug ?? name`-style silent fallback forbidden (slug-absent + name-only → error); mixed slug+title warns + ignores title; slug-without-display errors; wire has no `title`/alias keys but keeps `id` (slug-derived) and contract fields. Run gate `ruff check canvastekk_workflow_sdk/ tests/` + `pytest -v` green from `python/`
    — **Why:** the compat rule and the wire shape are the two safety properties of this change — both need pinned tests so a future refactor cannot silently drop them (review NOTE: the strict trigger and the name-only error are the two cases a sloppy implementation would get wrong)
    — **Done:** all constructor call sites migrated (98 across 7 files), wire-shape assertions flipped with one deliberate exception kept: `export_definition`/registry-payload tests keep `data["name"]` (engine register shape carries name=slug value + label=display — not manifest wire); new `TestVocabularyCompatibility` class pins all five determinism rules incl. no-alias-key wire check; gate green: 686 passed, ruff clean; files: 8 test files; fixes: export-payload assertion over-flip reverted, `data1/data2`-named manifest assertions, missing ValidationError import
    — **Consumers affected:** CI

### Phase 2: TypeScript package vocabulary flip

- [ ] **2.1** `definition.ts`: zod schema renames identity `name` → `slug` (keep SLUG_PATTERN refine, updated messages) and display `title` → `name` (required); implement the same Vocabulary contract rule as a pre-transform (STRICT legacy trigger: no `slug` + `name` + `title` → map + `console.warn`; no `slug ?? name` fallback; `name`-only fails with the disambiguating message; mixed slug+title warns + ignores); `getNodeId` picks `"slug" | "version"`; inbound `id` stripping stays
    — **Why:** the ts package must serve the identical manifest contract — divergence between packages breaks the "aligned packages" AC and the register CLI's cross-language assumptions
    — **Done when:** parsing a legacy manifest object yields the standard shape with a warning; parsing a name-only object fails with the disambiguating message; parsing a slugless-new-vocabulary object fails; parsed output type has `slug`/`name`/`description`/`version` and no `title`
    — **Consumers affected:** ts SDK consumers, future register CLI (ts flavor)

- [ ] **2.2** Sweep ts internal identity reads: `base-node.ts`, `registry.ts`, `app.ts`, `logging.ts`, `workflow/builder.ts`, `middleware.ts` — rename ONLY node-identity reads (domain `name` fields in `contracts/` are NOT node identity; leave them); **do not touch `workflow/models.ts`** (already canonical engine wire); update ts tests incl. manifest shape + the compat cases from 2.1; run gate `tsc --noEmit` + `vitest run` + `tsup` green from `typescript/`
    — **Why:** same completeness rule as 1.2; the grep counts include false positives (`contracts/measurement.ts`) — judgment, not blind rename
    — **Done when:** gates green; no node-identity `.name` reads remain in `src/` outside domain contracts; `workflow/models.ts` untouched (`git diff --stat` proves it)
    — **Consumers affected:** internal ts SDK paths, CI

### Phase 3: Docs, skills, example + release safety

- [ ] **3.1** Sync docs per AGENTS.md: `docs/EXTERNAL-AUTHOR-GUIDE.md`, `python/README.md`, `typescript/README.md`, root `README.md` (manifest field tables/examples), `python/.../data/skills/canvastekk-node-builder/SKILL.md` + `canvastekk-node-patterns/SKILL.md` (they teach `name=`/`title=` construction), and `examples/echo_node/` to the new spellings (keep a short migration note: legacy kwargs still accepted with a warning)
    — **Why:** repo rule — "never finish a task with docs out of sync"; the guide + skills are the source of truth for external node authors, who are the population this change breaks
    — **Done when:** `rg "title=" docs/ *.md python/README.md typescript/README.md examples/` shows no stale construction examples; manifest tables list the four standard fields
    — **Consumers affected:** external node authors, internal skill consumers

- [ ] **3.2** Release safety verification + final gates: confirm the merge commit carries `feat!:` + a `BREAKING CHANGE:` footer (per `cliff.toml` `features_always_bump_minor=true` any feat-bearing commit yields ≥0.27.0 — never patch; the `!` + footer additionally flag breaking through the dispatch payload); verify the REAL deploy-safety invariant at merge time — all four consumer repos still pin the SDK by exact wheel URL (nodes ×3 app variants, engine, ff-app, wall-app) and `deploy-lambda.yml` has no version-range/upgrade step; run both packages' full gates one final time from a clean tree
    — **Why:** the safety mechanism is EXACT-PIN non-adoption (the dispatch itself is ungated) — if any pin became a range or an upgrade step appeared, a ≥0.27.0 release would flip live manifests before the engine pairing lands; this step catches that at merge time
    — **Done when:** version math + pin style verified across all four repos with evidence in the PR body; both packages' gates green
    — **Consumers affected:** canvastekk-workflow-nodes + ff-app deploy pipelines, engine verify endpoint

## Technical Notes

- **Complete adoption pairing (recorded on the JIRA tickets, out of this repo's scope)** — the breaking release is safe to ship NOW because nothing auto-adopts it, but adoption (DA-2604/2605) pairs with: (a) a DA-2604 same-commit AC fixing the nodes-side `deploy-lambda.yml:520-535` rewrite script (`slug` identity read, `name` display read, `slug` added to `ALLOWED`) with parse failures hard-failing before the reseed dispatch — until then every registration 422s SILENTLY (failures are `::warning::`, reseed still dispatches ⇒ registry drifts); (b) a NEW engine ticket (one-way blocker to DA-2604/2605, paired by deployment window not reverse links) atomically flipping the engine's own-SDK manifest ingestion to `slug` identity (discover `router.py:561-583`, seed/refresh `node_registry.py:902-917`, `from_sdk` `converters.py:125,139`, `compare_node_to_manifest` `workflow_node_service.py:209`) and bumping the engine's SDK pin to an exact 0.27.x in the same change — pin-first hard-fails legacy seed. DA-2605 carries a scope-check AC: confirm ff-app and wall-app have no parallel register parser/whitelist.
- **Map invariant (the reason this map exists)**: the ungated `sdk-released` dispatch is safe only because all four consumers pin exact wheel URLs; floating any pin converts adoption-gated risk into release-time breakage.
- **Frontend blast radius: verified CLOSED** — the FE has no direct SDK-manifest consumer; `IWorkflowNodeManifest` (`src/types/workflow.ts:207-228`) is the engine registry API's own shape, already slug-keyed (`slug`/`label`), fetched via `cwe-api` `registry-controller/endpoints.ts:185`. No FE row needed; recorded so the completeness claim is auditable.
- The register CLI (DA-2603, unshipped) becomes the vocabulary adapter: manifest standard fields → engine registration request (`name`=slug value, `label`=display, `description`), matching the engine's post-DA-2626 boundary (client-sent slug 422s on registry POST) — `workflow_node_service.py:125-127` confirms the mapping.
- Wire-format types stay `snake_case` (repo rule); the zod schema field renames keep snake_case wire keys — only the field NAMES change, not the casing convention.
- Never bump version strings manually — release.yml owns pyproject/`__init__.py`/package.json bumps; the `dotnet` entry in `bump_versions.py` is vestigial (no `dotnet/` dir; bump_file safely SKIPs).
- SDK's `workflow/` package (builder/runner models) is ALREADY canonical — do not rename anything there; it speaks the engine's `SaveWorkflowRequest` wire.

## Dependencies

- None blocking (ticket: "No blockers — can start immediately"). DA-2603 (code_digest/register CLI) is unstarted; this ships independently rather than riding it — the ticket's "can ride" was an option, not a requirement, and shipping first means the CLI gets written against the final vocabulary (review-confirmed: no contract conflict). Blocks: DA-2604, DA-2605.

## Risks & Mitigations

- **Auto-adopt flips live manifests before the engine pairing lands** — real mechanism: exact wheel-URL pins in all four consumer repos exclude 0.27.0 (the dispatch is UNGATED, `sdk_breaking` gates nothing, so the pins are the ONLY protection); verified at merge time in 3.2; breaking release flagged via `feat!:` + footer.
- **External node authors break on upgrade** — construction compat keeps legacy kwargs working (warning, not error); migration note in the guide; BREAKING CHANGE footer + version bump signals it.
- **Ambiguous mixed construction (slug + title, name-only, neither)** — deterministic rules in the Vocabulary contract section, every case pinned by tests in 1.3/2.1; the strict legacy trigger forbids the `slug ?? name` silent mis-map.
- **Divergent python/ts compat semantics** — identical rules implemented in both packages; cross-checked in review.
- **Implementer renames engine-owned wire models by accident** — explicit DO-NOT-TOUCH rows in the consumer map + done-when `git diff --stat` guards in 1.2/2.2.
