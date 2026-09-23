# Post-Execution SDK Warnings Blame the Router Seam, Not Node Packages

**Category**: decision
**Confidence**: 0.9
**Scope**: project
**Date**: 2026-09-23
**Source**: DA-2886 review (stacklevel AC could not be met as written)

## Decision

Output uploads run in the ROUTER after `execute()` returns — node
package frames are never in that stack. `stacklevel=3` from the
upload-path deprecation warning blames the direct caller of
`upload_file`: the router seam (`upload_outputs`) in production, or the
exact call site for direct callers. No stacklevel reaches a frame that
is not there; ACs for SDK deprecation warnings in post-execution paths
should name "direct caller" semantics, not "into the node package".

Per-call-site dedup still collapses production warnings to one
registry entry, so behavior is one-warning-per-process in practice.

## Evidence

- python/canvastekk_workflow_sdk/uploads.py `_warn_legacy_presigned_upload`
- app.py:378-395 (router upload chain, no node frames)
