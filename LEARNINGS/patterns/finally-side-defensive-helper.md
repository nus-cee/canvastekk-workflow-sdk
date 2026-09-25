# Finally-side helpers must be exception-proof by construction

**Source:** DA-3009 code review (canvastekk-workflow-sdk) · **Date:** 2026-09-25 · **Confidence:** high

A helper called from a `finally:` runs on both the success and exception path —
if it raises, it masks the original response/exception (the classic finally bug).
Construct such helpers so nothing can escape: env/platform checks first, every
raise-able step inside its own try/except, log-and-return at debug level.
Reference: `_release_freed_heap` (workflow-sdk `app.py`, DA-3009). Its unlocked
module-global memoization race is deliberately tolerated — worst case is one
skipped trim or one redundant dlopen, self-healing on the next call; documented
in the docstring instead of paying a lock per request.
