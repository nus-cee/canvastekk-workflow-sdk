# PLAN: SDK manifest vocabulary alignment (slug/name/description/version)

**Branch**: feat/DA-2627
**Issue**: https://betekk.atlassian.net/browse/DA-2627
**Base**: main (7ca0e08 — v0.26.4; this repo has no dev branch, main is the integration branch)

## Acceptance Criteria

- [ ] Manifest carries all four standard fields with standard spellings: `slug` (identity), `name` (display), `description`, `version` — in BOTH the python and typescript packages, on the wire (`/manifest` output) and at construction (`NodeDefinition`/manifest schema)
- [ ] Both language packages released with aligned versions (automated `release.yml` on merge — `feat!:` commit yields ≥ 0.27.0; both packages bump in lockstep via `scripts/bump_versions.py`; no manual version edits)
- [ ] A manifest-served node registers with display name + description visible in the registry row once adoption lands (construction compat maps legacy `name=`+`title=` to `slug=`+display `name=` so existing nodes keep constructing; registration mapping itself is DA-2603 CLI / DA-2604/2605 adoption scope)
- [ ] Docs stay in sync per repo AGENTS.md: `docs/EXTERNAL-AUTHOR-GUIDE.md`, `python/README.md`, `typescript/README.md`, root `README.md`, the two embedded skills, and `examples/echo_node/`
- [ ] Gates green: python `ruff check canvastekk_workflow_sdk/ tests/` + `pytest -v`; typescript `tsc --noEmit` + `vitest run` + `tsup`

## Vocabulary contract (the word-collision rule)

The manifest today spells identity `name` ("Slug for routing") and display `title`. The standard moves BOTH words: identity → `slug`, display → `name`. Because `name` changes meaning, wire-level dual vocabulary is IMPOSSIBLE (`name` cannot mean identity and display in one payload). Compatibility therefore lives at CONSTRUCTION only, with a deterministic rule:

- **New vocabulary (preferred)**: `slug=<id>, name=<display>` → served verbatim.
- **Legacy call** (no `slug`, `name` + `title` given): map `slug=name`, display `name=title`, emit DeprecationWarning (`python`) / `console.warn` (ts) naming the new spellings.
- `slug` present + `title` present: `title` ignored with warning (display comes from `name`).
- `slug` present + `name` absent: error — display name is required in the new vocabulary.
- Wire output (`to_dict`, zod transform result, `/manifest` response): standard fields only — no `title`, no alias identity keys.

## Dependency & Consumer Map

| Node (file/module) | Depends on (must precede) | Consumers (who depends on this) | Change risk |
|--------------------|---------------------------|---------------------------------|-------------|
| `python/.../definition.py` `WorkflowNodeManifest` (name→slug, title→name, before-validator legacy map) | — | every SDK surface: `/manifest` endpoint, registry, base node, diff, `__main__`, workflow models, ALL downstream node repos, engine registration, external node authors | high — breaking wire+constructor change; mitigated by construction compat + version gating |
| `python/.../app.py` `/manifest` endpoint (docstring says "Identity (id, name, ...)" — identity list + any `.name` reads) | definition flip | engine `fetch_node_manifest` + `compare_node_to_manifest` (verify endpoint), future register CLI | medium — engine verify reads `manifest["name"]` as identity; safe ONLY because node repos cannot auto-adopt a ≥0.27.0 release (caret pins `^0.26` exclude it; breaking dispatch is major-gated per MAJOR-bump policy) — adoption is manual via DA-2604/2605, which must pair with the engine verify dual-mode change |
| `python/.../{base,registry,diff,__main__,logging,context}.py` + `workflow/` (identity reads `.name` → `.slug`; display reads `.title` → `.name`) | definition flip | internal only | medium — mechanical but wide; `workflow/` builder/runner node pins must be checked for `node_name` spellings |
| `typescript/src/definition.ts` zod schema + `getNodeId` | — | ts package mirrors python: base-node, registry, app, workflow/builder | high — same breaking semantics, same compat rule |
| `typescript/src/{base-node,registry,app,logging,workflow/builder,...}.ts` identity reads | definition flip | internal only | medium — grep counts include unrelated domain `name` fields (e.g. `contracts/measurement.ts`); rename ONLY identity-of-node reads |
| `docs/EXTERNAL-AUTHOR-GUIDE.md`, READMEs, `data/skills/*.md`, `examples/echo_node/` | code flip | node authors (the guide is the source of truth) | low — mandatory sync per AGENTS.md |
| Release (`feat!:` commit → cliff `--bump` → `bump_versions.py` → dispatch) | all above merged | canvastekk-workflow-nodes + ff-app Lambdas (auto-rebuild on sdk-released), engine verify | controlled — verify version math: shipped version MUST be ≥0.27.0 so caret pins exclude auto-adoption; BREAKING CHANGE footer propagates the flag downstream |
| Engine `compare_node_to_manifest` (reads `manifest["name"]` as identity) | NOT changed in this PR | engine verify endpoint | out of scope — recorded on DA-2627 + as prerequisite note: engine verify needs dual-vocabulary mode before DA-2604/2605 adoption (separate small engine change) |

## Implementation Phases

### Phase 1: Python package vocabulary flip

- [ ] **1.1** `WorkflowNodeManifest`: rename identity field `name` → `slug` (keep the slug pattern validation + field_validator, updated messages) and display `title` → `name` (required display); add a `model_validator(mode="before")` implementing the Vocabulary contract rule above (legacy `name`+`title` → `slug`+display `name` with `DeprecationWarning`); update `to_dict`/serialization so the wire carries exactly the standard fields (no `title` key, no alias identity keys)
    — **Why:** ticket item 2 — identity spelled `slug` everywhere; the word collision means compat must be resolved at construction deterministically, not on the wire
    — **Done when:** `NodeDefinition(slug="x", name="Display", version="1.0.0", ...)` round-trips through `to_dict()` serving `slug`/`name`/`description`/`version`; `NodeDefinition(name="x", title="Display", ...)` constructs via the legacy map with a DeprecationWarning and serves the same standard wire; `title` never appears in output
    — **Consumers affected:** all python SDK surfaces, downstream node repos, engine registration ingestion, external authors

- [ ] **1.2** Sweep python internal reads: `base.py`, `app.py` (endpoint docstring identity list + reads), `registry.py`, `diff.py`, `__main__.py`, `logging.py`, `context.py`, `__init__.py` exports/docs, and `workflow/` models (builder/runner node pins — any `node_name` spelling flips to `slug`; verify against the engine's canonical wire vocabulary from DA-2626)
    — **Why:** item 2 — "identity field spelled slug everywhere in both packages"; half-flipped internals would silently keep serving the old vocabulary from some paths
    — **Done when:** `rg "node_name|\.title\b" python/canvastekk_workflow_sdk --glob '!data/**'` returns no identity/display stragglers; every identity read uses `.slug`
    — **Consumers affected:** internal SDK paths only

- [ ] **1.3** Python tests: update manifest/definition/registry/diff/app/workflow tests to the new vocabulary + add explicit compat tests (legacy constructor maps + warns; mixed slug+title warns; slug-without-display errors; wire has no `title`/alias keys); run gate `ruff check canvastekk_workflow_sdk/ tests/` + `pytest -v` green from `python/`
    — **Why:** the compat rule and the wire shape are the two safety properties of this change — both need pinned tests so a future refactor cannot silently drop them
    — **Done when:** gates green; compat + wire-shape tests exist and pass
    — **Consumers affected:** CI

### Phase 2: TypeScript package vocabulary flip

- [ ] **2.1** `definition.ts`: zod schema renames identity `name` → `slug` (keep SLUG_PATTERN refine, updated messages) and display `title` → `name` (required); implement the same Vocabulary contract rule as a pre-transform (legacy `name`+`title` → `slug`+display `name` with `console.warn`; mixed warns; slug-without-display fails with a clear message); `getNodeId` picks `"slug" | "version"`
    — **Why:** the ts package must serve the identical manifest contract — divergence between packages breaks the "aligned packages" AC and the register CLI's cross-language assumptions
    — **Done when:** parsing a legacy manifest object yields the standard shape with a warning; parsing a slugless-new-vocabulary object fails; parsed output type has `slug`/`name`/`description`/`version`
    — **Consumers affected:** ts SDK consumers, future register CLI (ts flavor)

- [ ] **2.2** Sweep ts internal identity reads: `base-node.ts`, `registry.ts`, `app.ts`, `logging.ts`, `workflow/builder.ts`, `middleware.ts` — rename ONLY node-identity reads (domain `name` fields in `contracts/` are NOT node identity; leave them); update ts tests incl. manifest shape + compat warning cases; run gate `tsc --noEmit` + `vitest run` + `tsup` green from `typescript/`
    — **Why:** same completeness rule as 1.2; the grep counts include false positives (`contracts/measurement.ts`) — judgment, not blind rename
    — **Done when:** gates green; no node-identity `.name` reads remain in `src/` outside domain contracts
    — **Consumers affected:** internal ts SDK paths, CI

### Phase 3: Docs, skills, example + release safety

- [ ] **3.1** Sync docs per AGENTS.md: `docs/EXTERNAL-AUTHOR-GUIDE.md`, `python/README.md`, `typescript/README.md`, root `README.md` (manifest field tables/examples), `python/.../data/skills/canvastekk-node-builder/SKILL.md` + `canvastekk-node-patterns/SKILL.md` (they teach `name=`/`title=` construction), and `examples/echo_node/` to the new spellings (keep a short migration note: legacy kwargs still accepted with a warning)
    — **Why:** repo rule — "never finish a task with docs out of sync"; the guide + skills are the source of truth for external node authors, who are the population this change breaks
    — **Done when:** `rg "title=" docs/ *.md python/README.md typescript/README.md examples/` shows no stale construction examples; manifest tables list the four standard fields
    — **Consumers affected:** external node authors, internal skill consumers

- [ ] **3.2** Release safety verification + final gates: confirm `cliff.toml` bump rules make this a ≥ 0.27.0 release (never a patch — a 0.26.x patch WOULD auto-adopt into node-repo caret pins and flip live manifests before the engine verify is dual-mode); prepare the merge commit message as `feat!:` with a `BREAKING CHANGE:` footer (propagates the breaking flag through the sdk-released dispatch per MAJOR-bump policy); run both packages' full gates one final time from a clean tree
    — **Why:** the version math IS the safety mechanism protecting the engine verify endpoint and deployed Lambdas — a patch-numbered release would silently break them via the dispatch chain
    — **Done when:** cliff bump verified (dry-run or rule inspection) to yield ≥0.27.0 for the planned commit message; both packages' gates green
    — **Consumers affected:** canvastekk-workflow-nodes + ff-app deploy pipelines, engine verify endpoint

## Technical Notes

- Engine-side gap (recorded on the ticket, out of this repo's scope): `compare_node_to_manifest` compares `manifest["name"]` against stored identity — after adoption it must read `slug` (identity) + `name` (display vs `label`) with a legacy fallback. That small engine change must land before DA-2604/2605 bump their SDK pins.
- The register CLI (DA-2603, unshipped) becomes the vocabulary adapter: manifest standard fields → engine registration request (`name`=slug value, `label`=display, `description`), matching the engine's post-DA-2626 boundary (client-sent slug 422s on registry POST).
- Wire-format types stay `snake_case` (repo rule); the zod schema field renames keep snake_case wire keys — only the field NAMES change, not the casing convention.
- Never bump version strings manually — release.yml owns pyproject/`__init__.py`/package.json bumps.

## Dependencies

- None blocking (ticket: "No blockers — can start immediately"). DA-2603 (code_digest/register CLI) is unstarted; this ships independently rather than riding it — the ticket's "can ride" was an option, not a requirement, and waiting would block DA-2604/2605's vocabulary amendment indefinitely. Blocks: DA-2604, DA-2605.

## Risks & Mitigations

- **Auto-adopt flips live manifests before engine verify is dual-mode** — version math: ≥0.27.0 excluded by node repos' caret pins; breaking dispatch major-gated; verified in 3.2 before merge.
- **External node authors break on upgrade** — construction compat keeps legacy kwargs working (warning, not error); migration note in the guide; BREAKING CHANGE footer + version bump signals it.
- **Ambiguous mixed construction (slug + title, or neither)** — deterministic rules in the Vocabulary contract section; pinned tests in 1.3/2.1.
- **Divergent python/ts compat semantics** — identical rules implemented in both packages; cross-checked in review.
