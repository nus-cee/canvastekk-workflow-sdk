# PLAN "Done" Ticks Must Cite a Diff-Observable Change

**Category**: convention
**Confidence**: 0.6
**Scope**: project
**Date**: 2026-09-25
**Source**: DA-3026 review (step 1.3 ticked "row reworded" with zero hunks)

## Convention

Before ticking a PLAN step, verify the claim against
`git diff origin/main -- <file>` — a tick with no corresponding hunk
misrepresents verification state. DA-3026's builder mistakes-row reword was
silently skipped (an earlier script aborted before reaching it) yet ticked;
the review caught builder:776 byte-identical to origin/main.
