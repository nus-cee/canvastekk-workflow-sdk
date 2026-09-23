# Inlining a Fetch During a Port Drops the Callee's Validation

**Category**: anti-pattern
**Confidence**: 0.9
**Scope**: project
**Date**: 2026-09-23
**Source**: DA-2886 review (multipart port from nodes)

## Symptom

Nodes' `CdsClient.get_upload_status` validated the resume payload
(uploadId required; every row an object with int partNumber + non-empty
etag) so `cds_multipart` could trust it unchecked. The SDK port inlined
the HTTP fetch but left `status.get` / row iteration OUTSIDE its try —
a malformed status body escaped as `AttributeError`/`TypeError`,
aborting (fine) but re-raising the PARSE error instead of the original
part failure, breaking the DA-2881 "re-raise the original error"
contract silently.

## Fix

When porting a call, port the callee's validation obligations with it
— or route the parse through the same failure path
(`raise failure from exc`). Test the malformed-status case explicitly.

## Evidence

- python/canvastekk_workflow_sdk/multipart.py `_reconcile_resume`
  (fixed in the same PR as this entry)
- Original: canvastekk-workflow-nodes `_shared/cds_client.py`
  `get_upload_status`
