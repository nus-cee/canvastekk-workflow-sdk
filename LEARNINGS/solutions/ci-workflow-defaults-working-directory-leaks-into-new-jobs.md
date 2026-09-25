# Workflow-Level defaults.run.working-directory Leaks Into Every New Job

**Category**: solution
**Confidence**: 0.85
**Scope**: project
**Date**: 2026-09-25
**Source**: DA-3026 review (skill-mirror-guard job would have failed every run)

## Solution

A workflow-level `defaults.run.working-directory` (ci-python.yml sets
`python`) applies to every job's `run` steps — root-relative commands in a
new job execute inside that dir where the target paths don't exist
(diff exit 2 → repo-wide merge blockade). The in-file precedent:
`schema-stability` overrides back to `${{ github.workspace }}`. Rule: any
new job in such a workflow must override the default or use
workspace-relative paths; and local negative tests of a CI job must run
from the job's cwd, not the repo root.
