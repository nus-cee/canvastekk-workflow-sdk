# PLAN: TS SDK — per-invocation WASM worker pattern docs (DA-3010)

**Branch**: feat/DA-3010
**Issue**: https://betekk.atlassian.net/browse/DA-3010
**Base**: main

## Acceptance Criteria

- [x] Pattern documented: why (V8 returns JS heap; WASM linear memory never shrinks; malloc_trim cannot touch it), worker_threads-per-invocation sketch with terminate-in-every-exit-path, pitfalls (startup cost, cross-thread WASM instances, transferable buffers), when-not-to-use
- [x] Docs-only — no helper API (deferred until a node adopts the pattern; the doc carries a complete sketch)

## Implementation Phases

### Phase 1: Doc (exit gate)

- [x] **1.1** `docs/WASM-WORKER-PATTERN.md` (repo-root docs/ where EXTERNAL-AUTHOR-GUIDE.md lives).
    — **Why:** the CISA node lambda (web-ifc + fragments + three) accumulates WASM heap per model; warm-sandbox reuse turns that into permanent inflation.
    — **Done when:** doc committed; CI green.
    — **Consumers affected:** TS node authors.

## Technical Notes

Deliberately docs-only per ticket scope ("document/implement" — implement deferred until first adopter; the sketch is complete enough to lift).

## Dependencies

None.

## Risks & Mitigation

| Risk | Mitigation |
|------|------------|
| Doc drift vs SDK evolution | Sketch uses stable node:worker_threads API; no SDK-code coupling |

## Trace

GATE 1447277 tier=full lint=t(typescript CI lint+typecheck run repo-wide) typecheck=t(build=n.a.) build=n.a. unit=n.a.(docs-only) e2e=n.a. (docs-only; CI typescript lint/typecheck runs repo-wide on PR)
