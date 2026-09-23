# simplefilter("always") Defeats Warnings-Dedup Tests

**Category**: solution
**Confidence**: 0.9
**Scope**: project
**Date**: 2026-09-23
**Source**: DA-2886 review (deprecation dedup AC)

## Problem

`warnings.simplefilter("always")` bypasses `__warningregistry__`, so a
test using it CANNOT verify per-call-site dedup — every call shows the
warning regardless of registry state.

## Fix

Dedup tests must run under `simplefilter("default")`, route repeated
calls through ONE helper so both blames land on the same source line
(the registry key includes lineno — two calls on two adjacent lines are
two sites), and assert exactly one warning; a second helper (different
line) must fire again.

## Evidence

- python/tests/test_multipart_uploads.py `test_warning_deduped_per_call_site`
