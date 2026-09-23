# PLAN: SDK multipart output uploader — transparent swap, deprecate single-PUT

**Branch**: feat/DA-2886
**Issue**: https://betekk.atlassian.net/browse/DA-2886
**Base**: main (repo default — the SDK has no dev lane; releases cut from main)

## Acceptance Criteria

- [x] `upload_file(file_path, target: str | UploadSession)`: plain string = legacy fallback; session descriptor = multipart client (direct swap — Protocol widened, never broken)
- [x] Multipart client: lazy initiate via session token → bounded parallel part PUTs (orchestrator pre-read + pure worker — DA-2882 pattern) → complete; per-part retry/backoff; resume-from-server-truth (DA-2881 pattern); abort-on-failure contract
- [x] Per-part digest — per DA-2891 verdict: per-part Content-MD5 (RFC 1864), port the DA-2884 machinery as-is (verdict comment id 18196)
- [x] >5GB node outputs upload successfully; DA-1711 failure semantics preserved (fail/UPLOAD_FAILED at router layer, outside ErrorOutputNode)
- [x] Graceful degradation BOTH directions: old SDK + new engine (strings), new SDK + old engine (strings)
- [x] Deprecation: custom `DeprecationWarning` subclass + stacklevel blaming the DIRECT caller of `upload_file` (the router seam in production — node frames are never in the post-execution upload stack; amended per review), deduped per call site; once-per-process `logger.warning`; message names the engine upgrade and removal target (SDK v1.0); standard warnings filtering only (no env flag); ships WITH the multipart client
- [x] Tests: session handshake, both degradation directions, warning fires once + filterable, multipart happy/failure/resume paths

## Dependency & Consumer Map

| Node (file/module) | Depends on (must precede) | Consumers (who depends on this) | Change risk |
|--------------------|---------------------------|---------------------------------|-------------|
| `uploads.py` — `UploadSession` model + widened `upload_file` + deprecation shim | multipart machinery | engine execute wire (via request.py), external node authors (Protocol, widened additively), app.py router | med |
| `multipart.py` (new) — ported machinery: etag parse, chunk read, part PUT (Content-MD5 + retry), status reconcile, orchestration | UploadSession shape | `S3PresignedUploader.upload_file` | med |
| `request.py` — `output_upload_url: dict[str, str \| UploadSession] \| None` | UploadSession | engine (wire), app.py | low (union widened; strings unchanged) |
| `app.py` — annotation pass-through (`_upload_to_presigned`, `_upload_outputs_to_s3`) | uploads.py | DA-1711 fail/UPLOAD_FAILED semantics (unchanged — exceptions still propagate to the router layer) | low |
| `tests/test_multipart_uploads.py` + `test_uploads.py`/`test_request.py` extensions | all above | — | low |
| `docs/EXTERNAL-AUTHOR-GUIDE.md` + `python/README.md` | final shape | external authors | low (repo-mandatory doc sync) |

Cross-repo consumer = the ENGINE (DA-2887, next in this pipeline, implements the same descriptor schema). No engine code consumes sessions TODAY (engine still emits strings) → contract risk is sequencing, not breakage; DA-2887 consumes this schema verbatim. External node authors: Protocol widening is additive (str still valid). Zero plan-review delegates selected on that basis; Step 9 code review backstops the contract.

## Wire Contract (documented here; DA-2887 implements the engine side)

`output_upload_url[field]` is EITHER a plain presigned-URL string (legacy) OR:

```json
{
  "kind": "multipart-upload-session",
  "session_token": "<opaque, TTL-bound>",
  "initiate_url": "<POST {size, content_type} -> {upload_id, part_size, part_urls: [str, ...]}>",
  "complete_url": "<POST {upload_id, parts: [{part_number, etag}]} -> 200>",
  "abort_url": "<POST {upload_id} -> best-effort, never 5xx-fatal>",
  "status_url": "<GET -> {upload_id, uploaded_parts: [{part_number, etag}]}>",
  "expires_at": "<ISO-8601, informational>"
}
```

snake_case to match the execute-request wire (`output_upload_url` itself is snake_case). Casing is part of the contract; DA-2887 mirrors it.

## Implementation Phases

### Phase 1: Wire contract + model

- [x] **1.1** `UploadSession` pydantic model in `uploads.py` (`kind` literal discriminator, all URL fields + `expires_at`); `request.py` widens `output_upload_url` to `dict[str, str | UploadSession] | None`
    — **Why:** The degradation AC lives at the request seam — a new engine must be able to send either shape to a new SDK, and an old engine's strings must validate unchanged.
    — **Done when:** mixed `{"a": "https://...", "b": {session}}` validates; garbage dict (no `kind`) rejects with 422-shaped validation error.
    — **Consumers affected:** engine wire (additive), `app.py` (type only).

### Phase 2: Multipart machinery (ported from nodes `_shared/cds_multipart.py`)

- [x] **2.1** New `multipart.py`: `_parse_etag`, `_read_part_chunk` (orchestrator-thread seek+read, shrink guard), `_put_one_part` (pure worker: pre-read bytes in → ETag out; per-part Content-MD5 RFC-1864 raw-MD5 base64; explicit Content-Length; retry with backoff; S3 error body surfaced), `_reconcile_resume` (GET status_url; uploadId match; server-truth part list), `upload_via_session` orchestrator (lazy initiate → ONE fh + ONE bare httpx client + bounded ThreadPoolExecutor batches (pre-read sequential on orchestrator, PUTs parallel) → complete with parts sorted by part_number; abort-on-failure contract: abort after retries+resume exhausted / resume impossible / local I/O; NEVER on complete failure; abort never raises)
    — **Why:** 925-test-pinned patterns (DA-2881/2882/2884) — port, don't reinvent; the adaptation is control-plane genericity (engine session URLs instead of CDS client calls).
    — **Done when:** Module imports clean; every function carries a Google-style docstring; no `canvastekk_workflow_sdk.exceptions` leakage changes (raises NodeIOError/NodeExecutionError as the nodes machinery does — DA-1711 router semantics preserved).
    — **Consumers affected:** `S3PresignedUploader.upload_file` (2.2).

### Phase 3: Widened entry point + deprecation

- [x] **3.1** `S3PresignedUploader.upload_file(file_path, target: str | UploadSession)`: session → `upload_via_session`; string → legacy single-PUT body (unchanged) + `_warn_legacy_presigned_upload()`. `OutputUploader` Protocol annotation widened identically. `app.py` helper annotations follow.
    — **Why:** The direct-swap AC — node-developer code stays byte-identical; the router (not the developer) performs uploads.
    — **Done when:** Existing string-path behavior identical (test_uploads.py green, untouched); session path exercised by new tests.
    — **Consumers affected:** external authors (additive), app.py router.
- [x] **3.2** Deprecation shim: `class LegacyPresignedUploadWarning(DeprecationWarning)`; `warnings.warn(..., stacklevel)` into the node package (per-call-site dedup via the default warnings registry — standard filtering is the ONLY silencing mechanism, no env flag); once-per-process `logger.warning` (module flag + lock) for operators; message names the engine upgrade (multipart sessions, DA-2887) and removal target (SDK v1.0)
    — **Why:** AC — ships WITH the client, never before; operators get one log line, developers get filterable, deduped warnings.
    — **Done when:** Second call at same site emits nothing; different site emits again; `filterwarnings("ignore", category=LegacyPresignedUploadWarning)` silences; operator log fires exactly once per process.
    — **Consumers affected:** none at runtime (optics + migration).

### Phase 4: Tests (`tests/test_multipart_uploads.py` + extensions)

- [x] **4.1** Handshake/typing: request model accepts mixed str|session dict; rejects malformed session dict (Phase 1 done-when, as tests)
- [x] **4.2** Degradation both directions: string target → legacy PUT path hit (mock httpx.put) + warning; session target → initiate/complete flow hit
- [x] **4.3** Warning semantics: once-per-call-site, second-site fires, filterable, operator log once per process
- [x] **4.4** Multipart happy path: N parts, bounded parallel batches (order-preserved etags), Content-MD5 header per part PUT, explicit Content-Length, complete body carries parts sorted by part_number
- [x] **4.5** Failure path: part PUT fails after retries → abort_url POSTed, original error re-raised (router fail/UPLOAD_FAILED contract preserved)
- [x] **4.6** Resume path: part fails post-retry → status_url consulted → confirmed parts adopted as server truth → only remaining re-PUT → complete; status mismatch → abort + original error
    — **Why:** Each AC names these paths explicitly; mocked httpx seams at the control-plane and part-PUT boundaries.
    — **Done when:** All green; suite total grows; `ruff check` + full pytest green (exit gate).

### Phase 5: Docs sync (repo-mandatory)

- [x] **5.1** `docs/EXTERNAL-AUTHOR-GUIDE.md` + `python/README.md`: document the widened upload contract (what changed for engine operators — nothing for node authors), the deprecation warning + filter recipe, and the session descriptor schema (mirror of the Wire Contract block above)
    — **Why:** Repo rule — any change to `BaseNode`/router/upload behavior must mirror the author guide + README in the same change.
    — **Done when:** Both files updated; no drift with uploads.py docstrings.

## Technical Notes

- Bare `httpx.Client` for part PUTs (no Authorization — presigned S3 sig v4); control-plane calls (initiate/complete/abort/status) also plain httpx — engine session endpoints are token-authed by URL.
- Per-part timeout mirrors `_UPLOAD_TIMEOUT_SECONDS`; part PUTs get the generous timeout, control-plane calls a short one.
- Size-independence (>5GB AC) is structural: part count = ceil(size/part_size) with the engine choosing part_size at initiate; tests exercise N-part flows at tiny sizes.
- Deprecation targets the STRING path — which is also the only path old engines can serve; it stays fully functional until v1.0.
- TS SDK untouched (ticket scope: python package only).

## Dependencies

- DA-2891 verdict (Content-MD5 per part) — resolved, port as-is.
- DA-2887 (engine sessions) — NEXT ticket in this pipeline; consumes this schema. No code dependency today.

## Risks & Mitigation

- **Schema drift between SDK and engine implementations** — mitigated by the Wire Contract block (the documented source both tickets code against) + DA-2887 building immediately after against this module.
- **Warnings spam in node packages** — default-filter dedup is per (message, category, module, lineno); the operator log is once-per-process with a lock.
- **Port fidelity** — the nodes machinery is 925-test-pinned; porting verbatim (renames only: CDS client → session URLs) and re-pinning each behavior in SDK tests.

## Gate Trace

- GATE 2d8655f tier=full ruff="check clean (post-format on touched files)" pytest="717 passed (706 + 11 new)" note="machinery ported from nodes cds_multipart; contract documented in PLAN Wire Contract + README + author guide"

- GATE d5f4609 tier=full ruff="check clean" pytest="719 passed (706 + 13 new)" note="review fixes: M1 status-payload validation inside resume try, M2 part-count equality guard, M3 kind Literal, M4 dedup-under-default + status-mismatch tests; minors: dead MultipartUploadError deleted, dead _upload_to_presigned deleted, status rows projected, import os hoisted; AC-6 amended (direct-caller blame)"
