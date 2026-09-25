# Deprecation Documentation Must Sweep Every Mention of the Deprecated Term

**Category**: anti-pattern
**Confidence**: 0.7
**Scope**: project
**Date**: 2026-09-25
**Source**: DA-3005 review (builder SKILL.md:218 stale presigned-only comment)

## Anti-pattern

A diff documenting the replacement lane fixed the target section but left a
stale presigned-only mention of the same mapping elsewhere in the same file
(builder SKILL.md:218 vs `request.py:70`'s `dict[str, UploadTarget] | None`).

## Rule

When documenting a deprecation, grep the deprecated term file-wide and sweep
every teaching mention, not just the section being rewritten.
