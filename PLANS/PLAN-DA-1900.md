# PLAN-DA-1900 — Python SDK uploads: explicit fixed-length PUT contract pin

**Ticket:** DA-1900 (Bug → re-scoped hardening) · **Branch:** feat/DA-1900-fixed-length-put · **Base:** origin/main `dfe4c04`
**Repos touched:** canvastekk-workflow-sdk, then canvastekk-workflow-nodes (wheel pin bump).
**Release fires on merge** (CR-1: git-cliff bumps patch for ANY conventional commit — no
`no_increment_regex` in cliff.toml); user decision 2026-08-22: accept v0.22.3 + nodes bump
(wire-neutral, zero behavior risk; keeps pins current).

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
- Current SDK version is 0.22.2; ANY conventional commit on main auto-releases a patch
  (v0.22.3) — git-cliff bumps by default; `cliff.toml` has no `no_increment_regex` opt-out
  (code-review CR-1, verified upstream). The `test:` prefix does NOT suppress the release.
  Release accepted as harmless (wire-neutral); nodes bump to v0.22.3 follows per user decision.

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

- [ ] **3.2** Commit with subject `test(uploads): pin fixed-length identity PUT contract — DA-1900`
      (actual shipped subject — CR-3 tick-with-actual; prefix does NOT suppress release per CR-1);
      body ≤72 chars, notes premise correction. Tick plan + Done lines. Push.
      PR → **main** (no dev branch), merge, CI green. Post-merge: confirm v0.22.3 release +
      tag fired (release.yml git-cliff auto-bump) and `sdk-released` dispatch sent to nodes.
    — **Why:** ship; release accepted per user decision (wire-neutral).
    — **Done when:** PR merged; v0.22.3 tag + GitHub Release exist; dispatch run observed.
    — **Consumers affected:** nodes repo (dispatch triggers a rebuild; pin bump lands in Phase 4).

- [ ] **3.3** JIRA close-out on DA-1900: premise correction evidence (probe results), what
      shipped (contract pin + tests + docstring fixes), release fired (v0.22.3, accepted),
      nodes bump PR link.
    — **Why:** the ticket was filed as a bug — the record must carry the falsification.
    — **Done when:** comment posted with both PR links.
    — **Consumers affected:** ticket reviewers.

### Phase 4 — Nodes consumption (restored per user decision 2026-08-22)

- [ ] **4.1** Nodes repo `fastapi_app/pyproject.toml`: wheel pin `v0.22.0` → `v0.22.3`;
      `poetry lock` (bare URL, no sha256); gates (ruff/format/mypy + full pytest) green;
      PR → dev, merge. Deploy Lambda run green (auth assertions, 50 nodes, reseed).
    — **Why:** keep the pin current; the DA-1546 dispatch rebuild alone doesn't move the pin.
    — **Done when:** merge commit on dev + deploy run URL recorded.
    — **Consumers affected:** nodes Lambda runtime (wire-neutral).

## Acceptance Criteria

- [ ] AC-1: explicit `Content-Length` sent (contract no longer relies on httpx internals);
      wire format unchanged (identity, correct length — verified pre/post)
- [ ] AC-2: wire-format regression test + zero-byte test green; existing suite untouched
- [ ] AC-3: v0.22.3 release fired (accepted — git-cliff bumps any conventional commit);
      nodes pin bumped to v0.22.3 on dev
- [ ] AC-4: JIRA comment records premise correction + evidence

## Rollback

SDK: revert the merge commit (a revert lands as another patch release since git-cliff bumps any
conventional commit — harmless; wheels are immutable so v0.22.3 stays valid). Nodes: revert the
pin bump commit on dev (re-pin to v0.22.0 wheel + lock in one atomic commit). Fully safe either
way: the change is wire-neutral.
