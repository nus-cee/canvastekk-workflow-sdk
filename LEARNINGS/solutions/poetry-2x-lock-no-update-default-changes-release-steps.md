# Poetry 2.x `lock` Defaults to no-update — Release Steps Change Semantics Silently

**Category**: solution
**Confidence**: 0.85
**Scope**: project
**Date**: 2026-09-26

## Solution

Poetry 2.x `poetry lock` preserves locked versions (old default was full
re-resolve); full regen needs `--regenerate`. A mechanical
`poetry` → `python -m poetry` conversion in a release workflow therefore
silently stops refreshing transitive dependencies at release — security fixes
can sit unfrozen with nobody deciding that. Audit any "update lock" step when
bumping poetry majors and make the regenerate-vs-pin decision explicit.
DA-3036 chose `--regenerate` (behavior parity); pinning-at-release would be a
separate policy ticket. Evidence: release.yml:58; poetry 2.0 announcement
#9327.
