# Scaffold Dest Flip Between Agent-Discovered Skill Dirs Needs a Legacy-Cleanup Note

**Category**: pattern
**Confidence**: 0.8
**Scope**: project
**Date**: 2026-09-25
**Source**: DA-2982 review (scaffold dest `.opencode/skills` → `.agents/skills`)

## Pattern

When flipping a scaffolder's destination between directories that coding
agents actively scan (`.opencode/skills` → `.agents/skills`), the old
location does not become inert for users who already scaffolded there —
OpenCode v2 and pi both require skill-name uniqueness across discovery
locations, so an upgrade leaves consumers with each skill discovered twice
and the stale copy never prunes itself.

Every dest flip needs an explicit migration note (README: remove the legacy
dir before re-init) or an in-scaffolder warning when the legacy dest exists.
Reference: `python/canvastekk_workflow_sdk/__main__.py` `_init_skills`,
README "Global setup" (DA-2982).

## When to apply

Any change to where generated agent-readable artifacts (skills, agents,
commands) are written into consumer projects.
