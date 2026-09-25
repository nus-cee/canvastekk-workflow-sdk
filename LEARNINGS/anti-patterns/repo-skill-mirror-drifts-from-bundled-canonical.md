# Repo Skill Mirror Drifts From the Bundled Canonical Copy

**Category**: anti-pattern
**Confidence**: 0.7
**Scope**: project
**Date**: 2026-09-25
**Source**: DA-2982 review (repo `.agents/skills` vs `python/canvastekk_workflow_sdk/data/skills`)

## Anti-pattern

Hand-maintaining the same skill content in two places — the repo-level skill
dir (authoring/discovery copy) and the package `data/skills/` copy the wheel
ships — lets them drift silently. Found during DA-2982: the repo mirror
teaches the **deprecated** legacy manifest vocabulary (`name=<slug>` +
`title=`, deprecated at `canvastekk_workflow_sdk/definition.py:33-35,328-341`)
while the shipped canonical copy teaches the current `slug=`/`name=`
vocabulary (114/146 pre-existing diff lines). Agents working in the SDK repo
itself load the stale-teaching mirror.

## Fix direction

Single-source the content: one canonical copy, with the other derived
(build step or symlink-equivalent), or delete the mirror and rely on the
bundled copy. Follow-up candidate from DA-2982 review.

## Resolution (2026-09-25, DA-3026)

Resolved with a CI `diff -r` guard job (`skill-mirror-guard` in
`.github/workflows/ci-python.yml`) instead of single-sourcing — zero build
complexity; recursion auto-covers future skill dirs. Residual gap at merge
time: `.agents/skills/**` added to trigger paths so mirror-only PRs run the
guard. Canonical content errors found during the resync were fixed in the
same ticket (Measurement example, validate_file_input row).
