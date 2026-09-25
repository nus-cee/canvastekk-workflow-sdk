# Verify reindent-heavy diffs with `git diff -w`

**Source:** DA-3009 code review (canvastekk-workflow-sdk) · **Date:** 2026-09-25 · **Confidence:** high

When a change is dominated by a mechanical reindent (e.g. wrapping ~70 lines in
`try:/finally:`), review the semantic delta with `git diff -w <base>...<branch>` —
it collapses whitespace-only movement to the real changes. On DA-3009 the raw
diff showed 169 changed lines in `app.py`; `-w` reduced it to four: two imports,
the `_release_freed_heap` helper, one `try:`, one `finally:`. Proves zero
behavior drift in one command instead of line-by-line diff reading.
