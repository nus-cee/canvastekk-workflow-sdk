# Vocabulary-Wide Renames Leak Into Doc Examples For Symbols That Were Never Renamed

**Category**: anti-pattern
**Confidence**: 0.85
**Scope**: project
**Date**: 2026-09-25
**Source**: DA-3003 review (Measurement(slug=…) broken example)

## Anti-pattern

DA-2627 (678db93) renamed WorkflowNodeManifest `name`/`title` → `slug`/`name`
and the same commit rewrote `Measurement(name=…)` → `Measurement(slug=…)` in
the bundled skill — but `contracts.py:289` still defines `Measurement.name`
(no slug anywhere in contracts). Copying the example raises pydantic
ValidationError. The broken example then propagated repo-wide via DA-3003's
faithful mirror resync.

## Rule

When reviewing a rename refactor that touches docs/skills, verify each
renamed symbol against its source definition — renames must be
symbol-scoped, not vocabulary-scoped.
