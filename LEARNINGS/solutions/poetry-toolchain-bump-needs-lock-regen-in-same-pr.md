# Poetry Toolchain Bump Needs Lock Regen in the Same PR

**Category**: solution
**Confidence**: 0.8
**Scope**: project
**Date**: 2026-09-26

## Solution

Bumping the poetry tool version in CI without regenerating the committed lock
leaves a mixed-format window: 2.x install steps reading a 1.x-generated lock
(`lock-version = "2.0"`), with the documented failure mode
`pyproject.toml changed significantly since poetry.lock was last generated`
(poetry #10918 cross-minor content-hash churn; redash #7315). Regenerate the
lock in the same PR so the one-time format bump is a reviewed diff instead of
a bot release commit. DA-3036: `poetry lock` (2.4.1, no-update) = format/hash
refresh only — verify `git diff` shows zero `-version/+version` lines before
committing.
