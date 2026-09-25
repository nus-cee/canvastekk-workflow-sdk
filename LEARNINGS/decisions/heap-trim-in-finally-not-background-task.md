# Post-execution heap trim runs in the endpoint finally, not a BackgroundTask

**Source:** DA-3009 (canvastekk-workflow-sdk) · **Date:** 2026-09-25 · **Confidence:** medium

`gc.collect() + malloc_trim(0)` after each `/execute` runs synchronously in the
endpoint `finally` rather than as a FastAPI BackgroundTask. Reason: a warm Lambda
sandbox freezes right after the response is dispatched — a BackgroundTask would
not be guaranteed to run before the freeze, so the freed heap would be retained
into the next invocation (the exact poisoning DA-3009 fixes). Cost: trim latency
(typically single-digit ms) lands on response time. Opt-out:
`CANVASTEKK_SDK_MEMORY_TRIM=0`; permanent no-op on non-glibc.
