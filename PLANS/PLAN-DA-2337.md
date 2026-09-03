# PLAN: DA-2337 — workflow-sdk: make silent file-output upload skip fatal

**Ticket:** [DA-2337](https://betekk.atlassian.net/browse/DA-2337)
**Branch:** DA-2337 (base: `main` @ v0.26.0)
**Repo:** canvastekk-workflow-sdk

## Overview

Failed run of `floor-flatness-app-v3` on canvastekk-dev: `url-load-1`
reported `pass`, but its `buffer` output (declared `format: file`) was
never uploaded to the workflow-runs bucket. Cause: the SDK uploader
silently skips outputs whose value is not a `str` / not an existing local
file (`python/.../uploads.py:150-160`, `typescript/src/uploads.ts:186-197`)
— the node still reports SUCCESS, and the engine unconditionally rewrites
the field to `s3://…runs/{run_id}/{node}/{field}` on pass
(engine `temporal/activities.py` ~655-680). Downstream nodes presign a GET
against the nonexistent object → `HTTP 404 downloading file for field
'pcd_path'` at `downsample-1`, cascading into `'pcd_path' is a required
property` at `ff-1`.

Real PUT failures were made fatal by DA-1711 4.1 (already in
`app.py:365-381` py / `app.ts:126-142` ts) — but the not-a-local-file skip
still warns and continues. The engine stamps `s3://` for the object the
moment a URL was presigned, so skipping the upload is guaranteed
corruption: fail the node instead.

Why now (not a regression): the nodes gateway ran SDK v0.21.0 until Sep 3,
which was ALSO silent on real PUT failures; v0.25.0 (deployed Sep 3) made
those fatal, leaving only the isfile-skip path. The failing run most likely
hit a swallowed transient PUT failure during the Sep 3 deploy churn, or the
remaining isfile-skip path.

## Acceptance Criteria

- [ ] A `format: file` output whose value is not a `str`, or not an
      existing local file, FAILS the node (`fail` / `UPLOAD_FAILED`) —
      never warn+continue+success — in both Python and TypeScript SDKs.
- [ ] Skipping when NO upload URL was presigned for the field
      (`field not in upload_urls`) remains valid local-run behavior —
      unchanged.
- [ ] Python unit tests cover: non-str value, non-existent path, happy
      path (existing temp file uploads), no-URL skip.
- [ ] TypeScript tests mirror the Python cases.
- [ ] `poetry run ruff check canvastekk_workflow_sdk/ tests/` and
      `poetry run pytest -v` green in `python/`; `npm test` green in
      `typescript/`.
- [ ] Merge to `main` releases (git-cliff `fix:` → v0.26.1) and the
      `sdk-released` dispatch fires.
- [ ] Consumers updated: canvastekk-workflow-nodes pins bumped to the
      released wheel + gateway redeployed (separate PR in nodes repo,
      referencing DA-2337).

## Scope

**Both SDK languages** (bug exists in both; consumers of each exist).
Out of scope: engine head-object verification before the `s3://` rewrite
(follow-up ticket in canvastekk-workflow-engine — see Dependencies);
node-handler changes (url-loader current code is correct).

- `python/canvastekk_workflow_sdk/uploads.py` — skip → raise
- `python/tests/test_uploads.py` (new or existing)
- `typescript/src/uploads.ts` — skip → throw
- `typescript/tests/` upload tests
- `PLANS/PLAN-DA-2337.md` (this file)

## Technical Notes

- Python raise: `NodeIOError(f"Output field '{field}' value is not a local
  file: {value}", path=value if isinstance(value, str) else None)` —
  `app.py`'s broad `except` converts any exception to
  `fail`/`UPLOAD_FAILED`, so no `app.py` change needed.
- TS throw: `throw new Error(...)` — same message shape; `app.ts` catch
  already converts.
- Only raise when `field_name in upload_urls` (engine stamped a URL →
  engine WILL rewrite → not uploading is corruption). No URL → skip stays
  (local/UI run, value legitimately remains a local path).
- Engine stamps on `status==pass` regardless of object existence
  (`activities.py` "Replaced output … with S3 URI", `s3_uri += f"?ext="`).
- No version bump by hand — git-cliff; commit MUST be `fix:` type →
  patch v0.26.1.
- Rollout order: SDK merge → release → nodes pin bump PR → gateway
  redeploy.

## Dependency & Consumer Map

| Node (file/module) | Depends on | Consumers | Change risk |
|---|---|---|---|
| `python uploads.py::upload_outputs` skip→raise | — | `app.py:365-381` failure conversion (unchanged); every Python node runtime | med (previously-"successful" buggy nodes now fail loudly — intended) |
| `typescript uploads.ts::uploadOutputs` skip→throw | — | `app.ts:126-142` failure conversion (unchanged); every TS node runtime | med (same) |
| nodes repo `fastapi_app*/pyproject.toml` wheel pin | SDK release v0.26.1 | gateway deploy (cross-repo dispatch chain) | low (pin bump) |
| engine `activities.py` head-verify | — (follow-up ticket) | producer-node attribution | out of scope |

## Implementation Phases

### Phase 1: Python fix

- [ ] **1.1** In `upload_outputs` (`python/canvastekk_workflow_sdk/uploads.py`), replace both silent skips with a raise when `field_name in upload_urls`: non-str value → `NodeIOError("Output field '{field}' value is not a string: {type}")`; non-existent file → `NodeIOError("Output field '{field}' value is not a local file: {value}", path=value)`
    — **Why:** the engine presigned a URL and stamps `s3://` on pass unconditionally — skipping the upload guarantees a downstream 404 cascade attributed to the wrong node; failing at the producer is the only correct signal.
    — **Done when:** a response whose file-output value is `None`/dict or points at a missing path raises `NodeIOError`; the `field not in upload_urls` skip is untouched.
    — **Consumers affected:** `app.py` failure conversion (already broad-catches); all Python node runtimes.

### Phase 2: Python tests

- [ ] **2.1** Add pytest coverage in `python/tests/test_uploads.py`: (a) non-str output value → raises, (b) str path that does not exist → raises with `path` in details, (c) real temp file → upload_file called with the presigned URL, (d) field without URL → skipped silently, (e) `response.outputs` empty → no-op
    — **Why:** pins the fail-loud contract and the preserved local-run skip against regression; (c)/(d) guard against over-tightening.
    — **Done when:** `poetry run pytest -v` green, new tests fail against the old code.
    — **Consumers affected:** none (CI gate).

### Phase 3: TypeScript parity

- [ ] **3.1** Mirror in `typescript/src/uploads.ts::uploadOutputs`: non-string value → `throw new Error(...)`; `statSync` failure → `throw new Error(...)` (drop the `console.warn` + `continue`); keep the `!(fieldName in uploadUrls)` skip
    — **Why:** identical corruption path exists in TS (uploads.ts:186-197); DA-2242 deferred TS parity but this bug class must not ship divergent.
    — **Done when:** TS upload tests mirror Phase 2 cases; `npm test` green in `typescript/`.
    — **Consumers affected:** `app.ts` failure conversion (unchanged); TS node runtimes.

### Phase 4: gates + release

- [ ] **4.1** Run `poetry run ruff check canvastekk_workflow_sdk/ tests/ && poetry run pytest -v` (python/) and `npm test` (typescript/)
    — **Why:** repo-mandated pre-merge gates.
    — **Done when:** both exit 0.
    — **Consumers affected:** CI / release automation.
- [ ] **4.2** Commit as `fix(sdk): fail node when declared file output is not a local file [DA-2337]` and merge to `main`
    — **Why:** git-cliff maps `fix:` → patch bump v0.26.1; merge auto-publishes the wheel and dispatches `sdk-released` to canvastekk-workflow-nodes.
    — **Done when:** release workflow publishes v0.26.1; dispatch observed.
    — **Consumers affected:** nodes repo pin bump (Phase 5).

### Phase 5: consumer bump (executed in canvastekk-workflow-nodes repo)

- [ ] **5.1** PR in canvastekk-workflow-nodes bumping the wheel pin to v0.26.1 in `fastapi_app/pyproject.toml`, `fastapi_app_ml/pyproject.toml`, `fastapi_app_open3d/pyproject.toml`; commit `fix(nodes): bump SDK to v0.26.1 — fatal missing-file output upload [DA-2337]`; merge + gateway redeploy
    — **Why:** the gateway bundles the SDK wheel — the fix is inert until consumers pick it up (user-confirmed requirement: SDK consumers must be updated).
    — **Done when:** gateway runs v0.26.1; a node returning a non-path file output fails at the producer with `UPLOAD_FAILED`.
    — **Consumers affected:** all deployed nodes.

### Phase 6 (post-deploy verification)

- [ ] **6.1** Pull gateway logs + `aws s3api head-object runs/{run_id}/url-load-1/buffer*` for the failed dev run; rerun `floor-flatness-app-v3` on dev and confirm end-to-end success (or a correctly-attributed producer failure)
    — **Why:** closes the loop on the original incident and confirms which silent path fired historically.
    — **Done when:** rerun succeeds or fails at `url-load-1` with `UPLOAD_FAILED`; findings commented on DA-2337.
    — **Consumers affected:** none (verification).

## Dependencies

- Follow-up (separate ticket, canvastekk-workflow-engine): verify object
  exists via head before rewriting output to `s3://` so ANY producer miss
  (including pre-v0.26.1 nodes) fails at the producer node.
- Cross-repo dispatch chain (`sdk-released` → nodes `deploy-lambda.yml`)
  handles redeploy notification automatically once nodes pin is bumped.

## Risks & Mitigation

- **Risk:** nodes that legitimately returned non-file values in file
  fields previously "succeeded" and now fail. **Mitigation:** that
  success was always corrupt downstream (404 cascade) — failing loudly is
  the fix, not a regression; dev-first rollout catches offenders.
- **Risk:** TS `throw` inside the loop aborts remaining field uploads.
  **Mitigation:** Python behaves the same (raise exits `upload_outputs`);
  the whole response is failed anyway (`UPLOAD_FAILED`) — partial uploads
  for earlier fields are harmless orphans under `runs/{run_id}/` lifecycle
  cleanup.

## Success Metrics

- v0.26.1 wheel published; nodes gateway on v0.26.1.
- `floor-flatness-app-v3` rerun on dev no longer produces downstream-404
  signatures.
