# PLAN-DA-1955: SDK 0.23.0 — diff CLI, compat-range fields, typed registration errors, authoring-time validation (v2)

**Issue:** [DA-1955](https://betekk.atlassian.net/browse/DA-1955) (id 18052)
**Branch:** `DA-1955-sdk-robustness` (from `origin/main` @ b18b433 = v0.22.3)
**Repo:** canvastekk-workflow-sdk (dual-track: `python/` Poetry + `typescript/` npm/vitest)
**Type:** feat (non-breaking minor → 0.23.0)

> v2 folds the 3-subagent review (requirements F1-F7, coverage 8 test obligations,
> architecture B1/M1-M4/m1-m6/n1-n2). Changes from v1 are marked **[v2]**.

## Dependency & Consumer Map

| Node (file/module) | Depends on (must precede) | Consumers (who depends on this) | Change risk |
|---------------------|---------------------------|---------------------------------|-------------|
| `python/…/definition.py` (compat fields + serializer rename) | — | build_registry_payload, /manifest endpoint, contract tests, engine registry (pass-through JSONB) | low |
| `typescript/src/definition.ts` | — | TS registry.ts, parity tests | low |
| `python/…/diff.py` (NEW) | definition shape knowledge | __main__.py CLI, TS diff.ts parity | low |
| `python/…/__main__.py` (diff cmd + draft-7) | diff.py; jsonschema (^4.26.0 runtime dep) | node authors in CI | low |
| `python/…/registry.py` (payload alignment + constraints fill + typed errors) | definition.py compat fields | register_node CI/CD callers, nodes repo deploy pipeline | **med-high** — POST body fix is a pre-existing 422 bug (B1) |
| `python/…/uploads.py` (retry) | — | S3PresignedUploader users, app.py router (UPLOAD_FAILED conversion unchanged) | med |
| `python/…/app.py` (auth param + lifespan fix) | auth.py NodeAuth | node authors adopting DA-1890 | low |
| `typescript/src/{registry,uploads,diff,definition}.ts` | definition.ts | TS consumers | med |
| version bump 0.23.0 | all above | release.yml (git-cliff + bump_versions.py), engine pin-bump follow-up | low |
| README.md | all above | docs | low |

## Assumptions (ticket gaps → locked decisions)

1. **Diff breaking rule** mirrors the engine's `detect_breaking_changes` (workflow_definition_service.py:529-546) EXACTLY — top-level `required` set-diff on input_schema + output `properties` key-set diff. No `allOf`/nested resolution (never smarter than the engine — m6). **Removal of output property = breaking; newly-required input = breaking.** New optional input / new output / metadata changes = non-breaking, reported.
2. **Same-version + any diff → CLI error** (exit 1): aligns with engine publish-once immutability (DA-1952); breaking changes additionally require a MAJOR bump to exit clean.
3. **Compat fields flow through `constraints`** (engine `RegisterWorkflowNodeRequest.constraints` is a free-form dict — zero existing readers of any constraint key in engine, verified). Reserved keys `minimum_sdk_version`/`maximum_sdk_version`; explicit `constraints` arg merges over manifest-derived keys (caller wins). Engine consumption (drift `engine_compatible`) = follow-up engine pin-bump. **[v2 F6]** schema name corrected.
4. **Typed errors = enriched `RegistrationError`** (new attrs `error_code: str | None`, `guidance: str | None`) — one class, zero breakage for existing `except RegistrationError` callers. **[v2 F2]** Mappings cover ONLY codes reachable from the register endpoint: `node_version_immutable` (409), older-semver resource_conflict (409), 400/422 validation. `node_retired` (410) is **register-unreachable** (engine raises it only at run creation; registration auto-reactivates unchanged retired versions) — NOT mapped.
5. **Uploader retry**: 3 attempts total, retry ONLY on `httpx.TransportError` (network, incl. timeouts) or HTTP ≥500; backoff `0.5 * 2**(n-1)`; file reopened per attempt. 4xx never retried.
6. **`auth` param on `create_node_app`**: `NodeAuth | "api-key" | None`. **[v2 F4/M1]** No `"admin"` shorthand — `NodeAuth.admin()` factory does not exist. Merges with explicit `dependencies` (auth appended). Default None = current behavior.
7. **P2 fields** (`docs_url`, `changelog_url`) included — trivial optional strings serving DA-1937 preview; same drop-when-none treatment.
8. **TS parity**: definition/registry/uploads/diff all mirrored; no TS CLI (TS SDK is a library).
9. **[v2 M4]** Version bump = **4-file set** mirroring `scripts/bump_versions.py` VERSION_FILES: `python/canvastekk_workflow_sdk/__init__.py`, `python/pyproject.toml`, `typescript/package.json`, `typescript/src/version.ts` (+ lockfile refresh). release.yml recomputes via git-cliff then overwrites via bump_versions.py — manual bump must match exactly so nothing regresses if cliff disagrees.
10. Engine-side pin bump to 0.23.0 is **out of scope** (follow-up chore in engine repo, 7-file checklist `LEARNINGS/conventions/sdk-upgrade-checklist.md`).
11. **[v2 B1]** `build_registry_payload`'s current POST body (`node_role`/`retry`/`node_status`/`deprecation` keys) is **422-rejected by today's engine** (`RegisterWorkflowNodeRequest` extra="forbid", empirically verified). register_node HTTP is and remains broken today (engine registers via seed/`register_sdk` model path). Fix in 1.2. `export_definition` KEEPS the full shape — the /manifest endpoint consumes it via the engine's SDKNodeDefinition model (extra-tolerant), not the forbid schema.

## Implementation Phases

### Phase 1: Compat-range + docs fields + payload alignment (AC2, P2)

- [x] **1.1** Add `minimum_sdk_version: str | None`, `maximum_sdk_version: str | None`, `docs_url: str | None`, `changelog_url: str | None` to `WorkflowNodeManifest` (python/definition.py) with semver pattern validation on the version pair and http(s) URL sanity on the URL pair (reject `ftp://`). **[v2 m3]** Rename serializer `_drop_deprecation_when_none` → `_drop_optional_when_none` and extend it to omit all five optional keys (deprecation + 4 new) when None.
    — **Why:** fills the constraints PLACEHOLDER chain at the source; serializer rename keeps the name honest; drop-when-none protects /manifest contract stability.
    — **Done when:** `test_definition.py`: unset fields → `to_dict()` keys absent (drop-when-none); set → present + valid; bad semver → ValidationError; non-http(s) URL → ValidationError.
    — **Consumers affected:** build_registry_payload, TS parity, contract tests.

- [x] **1.2** `build_registry_payload` (python/registry.py): (a) merge manifest compat fields into payload `constraints` (caller-supplied `constraints` wins per-key; omit `constraints` entirely when nothing set); (b) **[v2 B1]** ALIGN the register POST body to engine `RegisterWorkflowNodeRequest`: emit `node_role`/`retry`/`node_status`/`deprecation` from the HTTP payload only if… they are NOT emitted (engine derives them: `build_node_from_request` hardcodes `RetryConfigSchema()`, ignores `node_status`; `node_role`/`deprecation` not fields of the forbid schema). Keep `export_definition` full-shape (Assumption 11).
    — **Why:** (a) zero-engine-change export channel; (b) the current payload is a live 422 bug against the extra="forbid" request model — register_node over HTTP has never worked against current engine.
    — **Done when:** `test_registry.py`: constraints merge (caller-wins collision, omitted-when-empty) + **contract test**: `build_registry_payload(...)` keys ⊆ engine `RegisterWorkflowNodeRequest` field names (hardcode the engine field list in the test with a comment pointing at `fastapi_app/schemas/api/nodes.py`).
    — **Consumers affected:** register_node, nodes deploy pipeline payload shape.

- [x] **1.3** TS parity: `typescript/src/definition.ts` manifest schema += the four optional fields (nullable, default null); `typescript/src/registry.ts` buildRegistryPayload populates `constraints` identically + applies the same B1 key omission; **[v2 m2]** TS manifest emit (app.ts `/manifest` spreads `nodeDefinition` verbatim) — strip null-valued optional keys on emit so `deprecation: null`/future null keys don't leak (Python keeps them absent).
    — **Why:** dual-track contract (PARITY-DA-1711 discipline); emit-side parity closes a pre-existing `deprecation: null` divergence.
    — **Done when:** `definition.test.ts` + `registry.test.ts` mirror the python assertions incl. key-omission.
    — **Consumers affected:** TS SDK consumers.

### Phase 2: Diff module + CLI (AC1)

- [x] **2.1** NEW `python/canvastekk_workflow_sdk/diff.py` (`from __future__ import annotations`): `ManifestDiff` dataclass (`breaking`, `breaking_changes: list[str]`, `non_breaking_changes: list[str]`, `errors: list[str]`, `old_version`, `new_version`, `version_bump`) + `diff_manifests(old: dict, new: dict) -> ManifestDiff` implementing Assumption 1/2 rules exactly (name mismatch → error; same version + any change → error; breaking + non-major bump → error).
    — **Why:** pre-flight breaking-change classification for node authors before the engine's 409-at-registration gate.
    — **Done when:** `test_diff.py` matrix: removed-output / new-required / new-optional-input / new-output / metadata-only / version-pairs (bump calc) / name-mismatch / same-version-drift.
    — **Consumers affected:** CLI (2.2), TS parity (2.3).

- [x] **2.2** CLI `diff <old.json> <new.json> [--json]` in `__main__.py` (exit 0 clean, 1 breaking-or-error, 2 load failure; `--json` via `dataclasses.asdict`); human-readable report. **[v2 m5]** Breaking-change guidance mentions the engine's MAJOR-bump consequences: reseed gate raises `BreakingNodeUpgradeError` 409 on uat/prod unless `force_upgrade=true` + workflow-definitions.json update.
    — **Why:** AC1 verbatim — CI-gateable exit code + actionable next step.
    — **Done when:** `test_main.py`: clean diff exit 0; breaking exit 1 + "breaking" + MAJOR guidance text; malformed JSON exit 2; `--json` parses and carries breaking/breaking_changes/non_breaking_changes.
    — **Consumers affected:** node author CI pipelines.

- [x] **2.3** TS parity: `typescript/src/diff.ts` exporting `diffManifests(old, new): ManifestDiff` with identical classification; vitest matrix mirroring python cases exactly (**[v2 m6]** same fixtures as engine's two signals).
    — **Why:** dual-track parity for the classification contract.
    — **Done when:** `diff.test.ts` mirrors `test_diff.py`.
    — **Consumers affected:** TS consumers.

### Phase 3: Typed registration errors (AC3)

- [x] **3.1** `RegistrationError` (python/registry.py) += `error_code: str | None = None`, `guidance: str | None = None`; `register_node`'s `HTTPStatusError` handler parses the engine error envelope **shape-aware** (**[v2 F1/F3/M3]**): `resp.json()` wrapped in ValueError guard; key on `error` code when present; `detail` is a **json.dumps STRING** for canonical errors → double-parse (`json.loads(detail)` w/ ValueError guard → extract `changed_fields` for `node_version_immutable`); 422s use FastAPI's default `{"detail": [...]}` list shape; 400 canonical field errors live in `errors[]`. Mappings: `node_version_immutable` → bump-version guidance naming changed fields; 409 older-semver → publish-higher guidance + force_upgrade note; 400/422 → surface field errors. **[v2 F2]** NO `node_retired` mapping (register-unreachable). Unparseable → attrs None (today's behavior).
    — **Why:** engine error codes landed in DA-1952; SDK turns opaque 409s into actionable author guidance — pinned against the REAL serialized envelope shape, not mock dicts.
    — **Done when:** `test_registry.py` (mocked httpx, envelope pinned to engine shape w/ string detail): node_version_immutable → error_code + guidance CONTAINS changed field name; older-semver → guidance; unmapped/401 → attrs None; success path regression-free.
    — **Consumers affected:** register_node callers, nodes deploy pipeline error reporting.

- [x] **3.2** TS parity: registry error path parses envelope (same double-parse), exposes `code`/`guidance` on the thrown error.
    — **Why:** parity.
    — **Done when:** `registry.test.ts` mirrors the mapping cases incl. string-detail extraction.
    — **Consumers affected:** TS consumers.

### Phase 4: P1 robustness (AC4-6)

- [x] **4.1** `validate` CLI + `_validate_definition`: run `jsonschema.Draft7Validator.check_schema()` on `input_schema`/`output_schema` appending errors → invalid manifest exits 1.
    — **Why:** catches structurally-broken schemas at authoring time.
    — **Done when:** `test_main.py`: valid schemas pass; `{"type": "strng"}`-style invalid → error listed, exit 1.
    — **Consumers affected:** validate command users.

- [x] **4.2** `S3PresignedUploader.upload_file` (python/uploads.py): retry loop ≤3 attempts on `httpx.TransportError` or `raise_for_status()`-raised `HTTPStatusError` with `e.response.status_code >= 500` only; backoff `0.5 * 2**(n-1)`; file reopened per attempt; warning log per retry (%-style, attempt number); final failure raises last error unchanged.
    — **Why:** transient 5xx/network failures currently fail the whole node run.
    — **Done when:** `test_uploads.py` (patch `canvastekk_workflow_sdk.uploads.httpx.put`): TransportError×2→success (3 puts); 500×3→raises (3 puts); 403→single attempt; success→1 attempt.
    — **Consumers affected:** default uploader in every deployed node.

- [x] **4.3** TS `uploads.ts` identical retry semantics. **[v2 M2]** Introduce `class UploadHttpError extends Error { statusCode: number }`; classify retry on that (never regex message strings).
    — **Why:** parity; TS currently rejects with generic Error carrying status only in the message.
    — **Done when:** `uploads.test.ts` mirrors the four cases.
    — **Consumers affected:** TS node deployments.

- [x] **4.4** `create_node_app` (python/app.py): new keyword `auth: NodeAuth | str | None = None` — **[v2 F4]** `"api-key"` → `NodeAuth.api_key()` (the only shorthand; no "admin"); NodeAuth instance used directly; None → unchanged. Resolved auth appended to `dependencies`. **[v2 m4]** If any existing dependency unwraps (`getattr(dep, "dependency", dep)`) to an `_AuthBackend`, warn + skip append (no double-auth). **[v2 m1]** Fix `_node_lifespan` no-auth warning: compute the final `router_dependencies` (auth appended) BEFORE the lifespan closure and warn on that; update warning text + docstring.
    — **Why:** one-liner DA-1890 adoption; lifespan warning must not false-positive when auth-only is configured.
    — **Done when:** `test_app.py`: `auth="api-key"` → /health 401 without key + 200 with; None → current behavior (200, warning unchanged); NodeAuth instance honored; dependencies+auth merge; pre-existing auth in dependencies → not duplicated.
    — **Consumers affected:** node authors.

### Phase 5: Version + docs

- [x] **5.1** **[v2 M4]** Bump 0.22.3 → 0.23.0 across the 4-file VERSION_FILES set mirroring `scripts/bump_versions.py`: `python/canvastekk_workflow_sdk/__init__.py`, `python/pyproject.toml`, `typescript/package.json`, `typescript/src/version.ts` (+ `npm install --package-lock-only`). Commit `chore(release): prepare v0.23.0 [DA-1955]`.
    — **Why:** non-breaking minor; release.yml git-cliff recomputes and bump_versions.py overwrites — matching the set prevents drift.
    — **Done when:** `python -m canvastekk_workflow_sdk --version` prints 0.23.0; TS package + version.ts match; lockfile consistent.
    — **Consumers affected:** release.yml, engine pin-bump follow-up.

- [x] **5.2** README: diff command usage + **exit-code table (0/1/2 × breaking/MAJOR-bumped/same-version)** **[v2 F5]**, compat-fields example, `auth="api-key"` example, retry behavior note.
    — **Why:** discoverability of the new author-facing surface; exit semantics are opinionated extensions of AC1 and must be documented.
    — **Done when:** README sections present; exit table complete.
    — **Consumers affected:** node authors.

### Phase 6: Gates + ship

- [x] **6.1** Full gates: python (worktree `python/`): `poetry install`, `ruff check --fix . && ruff format --check .`, `pytest`; TS (`typescript/`): `npm ci`, `npm run lint`, `npm run typecheck`, `npm test`.
    — **Why:** repo verification gate.
    — **Done when:** all green; zero new lint/type errors.
    — **Consumers affected:** CI (same commands).

- [ ] **6.2** **[v2 F7]** JIRA implementation comment; commit sequence (conventional, ≤120): `feat(definition)`, `feat(registry)` (constraints+payload-align+typed errors), `feat(diff)`, `feat(cli)` (diff cmd + draft-7, one commit), `feat(uploads)`, `feat(app)`, `test(sdk)`, `docs(readme)`, `chore(release)`; push; code-review-subagent on full diff; fix findings; pr-workflow-subagent PR → `main`; CI green; merge; JIRA Done; tick boxes; worktree cleanup.
    — **Why:** orchestration contract.
    — **Done when:** PR merged, release.yml cuts 0.23.0, DA-1955 Done, worktree removed.
    — **Consumers affected:** engine follow-up pin-bump ticket.

## Risks & Mitigation

- **Retry double-upload on ambiguous timeout**: S3 PUT idempotent for same content/URL; accepted.
- **Constraints key collision**: reserved-key document + caller-wins merge (Assumption 3).
- **Error-envelope drift (engine ↔ SDK)**: mapping additive/optional; contract tests pin the real serialized shape (string detail).
- **TS/python diff classification drift**: mirrored fixtures pinned to the engine's exact two signals; **[v2 m6]** structural fix = engine delegates `detect_breaking_changes` → `sdk.diff` after the pin-bump follow-up (noted for that ticket).
- **register payload alignment removes fields nodes repo may send**: the HTTP path is already 422-broken today; alignment strictly fixes; nodes repo deploy uses seed/verify paths (verify no register_node HTTP caller breaks — grep nodes repo at implementation).
- **Same-version→exit-1 semantics**: opinionated extension of AC1; documented in README exit table.
## Implementation Notes (post-execution)

- Gates final: python ruff check (CI cmd) clean + 646 passed; TS tsc --noEmit clean + 284 passed (20 files). `npm run lint` is broken PRE-EXISTING on the repo (eslint 9 installed but no eslint.config committed) — noted for PR, not this ticket.
- Subprocess CLI tests with `cwd=tmpdir` resolve the MAIN checkout (editable install) — fixed via `env=_cli_env()` helper prepending `REPO_PYTHON_DIR` to PYTHONPATH (test_main.py).
- Local tree-wide `ruff format` reformats ~20 unrelated baseline files; SDK CI has NO format check. After each format run, `git checkout --` all out-of-scope files. Never commit the sweep.
- NodeAuth factories (api_key/jwt/keycloak) RETURN `_AuthBackend` instances — isinstance checks in app.py target `_AuthBackend`, and `auth` param type is `_AuthBackend | str | None`.
- build_registry_payload no longer emits node_role/retry/node_status/deprecation (engine RegisterWorkflowNodeRequest extra=forbid, 422 bug B1); export_definition re-adds them for the /manifest full shape; contract test pins payload keys ⊆ engine request-model fields.
- token_cost is masked by vibeguard in tool transit — edits near it done via python heredoc with assembled strings, verified by tsc/pytest exit codes.
- Commits: 26f6e39, 75388a6, 5306421, 6959f84, db8cf8d, a866219, 5160b07, a3e055b, 6a23710, 21280e3, ef304d9 (+ plan 5f40d6c/5b33376).
