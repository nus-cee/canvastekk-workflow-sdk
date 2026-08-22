# PLAN-DA-1900 — Python SDK uploads: explicit fixed-length PUT contract pin

**Ticket:** DA-1900 (Bug → re-scoped hardening) · **Branch:** feat/DA-1900-fixed-length-put · **Base:** origin/main `dfe4c04`
**Repos touched:** canvastekk-workflow-sdk only. **No nodes bump, no release required** (wire-neutral).

## Context

**Premise correction (3-review consensus, empirically verified 2026-08-22):** the original
filing assumed Python `uploads.py` chunked S3 presigned PUTs like the pre-DA-1811 TS SDK.
False: httpx 0.28.x auto-sets `Content-Length` for open-file bodies via `peek_filelike_length`
(`os.fstat`, `_utils.py:95-117`) with identity encoding — verified by raw-socket capture on the
pinned stack (httpx 0.28.1/httpcore 1.0.9): current code and the "fix" produce byte-identical
wire format. DA-1811's bug class was undici-specific (`fetch` forces chunked + strips user
`Content-Length`); no httpx analogue. Dev uploads always worked because there was no bug.

**What this change actually is:** make the wire contract explicit instead of depending on httpx
internals, and pin it with a real-server regression test. Aligns with the nodes-repo S3 PUT
rule ("explicit Content-Length on presigned PUTs") and the TS DA-1811 contract.

**Verified facts folded in from reviews:**
- Error path is `app.py:304` `except Exception` → `fail`/`UPLOAD_FAILED` — there is NO
  `OutputUploadError` class (uploads.py:64 docstring cites it — pre-existing doc drift, fixed here).
- `timeout=600.0` (uploads.py:18) is httpx scalar = per-operation, not the TS fix's 600s
  wall-clock deadline — docstring corrected, behavior unchanged.
- Content-Length is NOT a sigv4 signed header (`X-Amz-SignedHeaders=host`) — no 403 risk.
- Size-mutation race (file grows/shrinks between getsize and send) fails fast client-side
  (`h11 LocalProtocolError`) → UPLOAD_FAILED; same race exists today via auto-fstat. No hang.
- Existing 13 tests assert headers by key lookup (not dict equality) — adding a header key
  breaks nothing.
- Current SDK version is 0.22.2; a `fix:` commit on main auto-releases v0.22.3 (git-cliff).
  This change ships as `test:`/`refactor:` (no behavior change) so NO release fires and the
  nodes repo needs no bump. If a release fires anyway it is harmless (wire-neutral).

## Dependency & Consumer Map

| Change | Consumers | Risk |
|---|---|---|
| `uploads.py` explicit Content-Length + docstring | `app.py:91-120, 294-317` upload path (sole caller); nodes repo consumes via wheel pin (untouched) | wire-neutral; signature unchanged |
| new wire-format + zero-byte tests | CI (ci-python.yml, `python/**`) | none |
| engine | none — engine presigns, never uploads (pins 0.21.0, unaffected) | n/a |

## Phases

### Phase 1 — Fix + docstrings

- [x] **1.1** `python/canvastekk_workflow_sdk/uploads.py`: in `upload_file`, compute
      `size = os.path.getsize(file_path)` and send
      `headers={"Content-Type": "application/octet-stream", "Content-Length": str(size)}`,
      keeping `content=f` streaming (NO `read_bytes()` — multi-GB no-buffering contract).
      Docstring updates: (a) replace the nonexistent `OutputUploadError` citation with the real
      error path (`app.py` router → `UPLOAD_FAILED`); (b) state the timeout is per-operation;
      (c) state the explicit Content-Length pins the identity wire contract (httpx currently
      auto-sets it for seekable files; this guards against transport drift).
    — **Why:** contract explicitness + doc accuracy; zero behavior change.
    — **Done when:** diff is the header + getsize + docstring only; ruff clean.
    — **Consumers affected:** none (wire-identical).
    — **Done:** Content-Length via os.path.getsize + streaming content=f kept; 3 docstring fixes (UPLOAD_FAILED path, per-op timeout, contract-pin rationale).

### Phase 2 — Tests

- [x] **2.1** New wire-contract regression test in `python/tests/test_uploads.py`: real
      `http.server.ThreadingHTTPServer` on 127.0.0.1 ephemeral port (pattern from
      `canvastekk_workflow_sdk/testing.py:37-145` LocalFileServer; `protocol_version = "HTTP/1.1"`,
      explicit response Content-Length, daemon thread, 5s join), handler captures request
      headers + body; `monkeypatch.setenv("CANVASTEKK_DEV_MODE", "true")` for pattern
      consistency. Assert: (a) captured `Content-Length == str(size)`; (b) NO
      `Transfer-Encoding` header; (c) body byte-for-byte equal to original; (d) returns cleanly
      on 200. Passes on BOTH pre- and post-fix code (regression pin — do NOT require pre-fix
      failure; httpx already satisfies the contract).
    — **Why:** mocks can't see wire format; this pins it against future httpx drift.
    — **Done when:** test passes pre- AND post-fix (verified both); no flakiness over 5 runs.
    — **Consumers affected:** none.
    — **Done:** TestUploadWireFormat real-server test — Content-Length==size, no Transfer-Encoding, body byte-equal; 5-run stable; passes pre/post-fix (regression pin).

- [x] **2.2** Zero-byte edge test (mocked `httpx.put`): empty file → assert
      `headers["Content-Length"] == "0"` + Content-Type preserved. Existing 13 tests green
      unmodified.
    — **Why:** cheap edge pin for the new explicit header.
    — **Done when:** suite green; count = baseline + 2.
    — **Consumers affected:** none.
    — **Done:** zero-byte test asserts Content-Length '0'; existing 13 tests untouched, 15/15 green.

### Phase 3 — Gates + ship

- [x] **3.1** Gates from `python/`: `poetry run ruff check canvastekk_workflow_sdk/ tests/`;
      `poetry run pytest -v`. Full suite green.
    — **Why:** merge readiness (AGENTS.md:39 verbatim).
    — **Done when:** both green.
    — **Consumers affected:** none.
    — **Done:** ruff check clean; ruff format applied (1 file); full SDK suite 594 passed.

- [ ] **3.2** Commit with NON-release-triggering subject (`test(uploads): pin fixed-length
      wire contract for S3 presigned PUTs` — no `fix:`/`feat:` prefix so git-cliff does not
      bump); body ≤72 chars, notes premise correction. Tick plan + Done lines. Push.
      PR → **main** (no dev branch), merge, CI green. Post-merge: confirm NO new release/tag
      fired (if one did, accept it — wire-neutral, no consumer action).
    — **Why:** wire-neutral hardening must not force a consumer bump cycle.
    — **Done when:** PR merged; no release created (or accepted harmlessly).
    — **Consumers affected:** nodes repo (none — no dispatch if no release).

- [ ] **3.3** JIRA close-out on DA-1900: premise correction evidence (probe results), what
      shipped (contract pin + tests + docstring fixes), why no release/nodes-bump.
    — **Why:** the ticket was filed as a bug — the record must carry the falsification.
    — **Done when:** comment posted with PR link.
    — **Consumers affected:** ticket reviewers.

## Acceptance Criteria

- [ ] AC-1: explicit `Content-Length` sent (contract no longer relies on httpx internals);
      wire format unchanged (identity, correct length — verified pre/post)
- [ ] AC-2: wire-format regression test + zero-byte test green; existing suite untouched
- [ ] AC-3: no release triggered; no consumer bumps needed
- [ ] AC-4: JIRA comment records premise correction + evidence

## Rollback

Revert the merge commit (use a `test:`/`refactor:`-prefixed revert subject — git-cliff filters
default `Revert "..."` subjects, and no release is involved anyway). Fully safe: wire-neutral
change; nodes repo never consumes it (pin stays 0.22.0 until the next real SDK release).
