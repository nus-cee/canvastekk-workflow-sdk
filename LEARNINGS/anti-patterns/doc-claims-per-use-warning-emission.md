# Doc Claims About Warning Emission Must Match Dedup Semantics

**Category**: anti-pattern
**Confidence**: 0.8
**Scope**: project
**Date**: 2026-09-25
**Source**: DA-3005 review (builder SKILL.md "each use emits" vs registry dedup)

## Anti-pattern

Teaching docs said "each use emits `LegacyPresignedUploadWarning`", but the
warnings registry deduplicates: under default filters it is emitted once per
call site per process (uploads.py:84-87). Consumers writing assertions or
log-volume expectations from the doc hit the exact trap already recorded in
`simplefilter-always-defeats-dedup-tests`.

## Rule

Any doc describing warning emission frequency must match dedup semantics —
say "once per call site (deduped)".
