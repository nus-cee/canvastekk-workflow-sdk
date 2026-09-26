---
category: decisions
tickets: [DA-3086]
---

# Decision: registry convergence is owned by the SDK CLI

DA-3086 absorbed the three per-repo registry_convergence.py copies
(DA-3070 IFC -> DA-3071 CWN -> DA-3084 CRS) into
`python -m canvastekk_workflow_sdk registry-convergence` (first release:
v0.31.0). Deploy steps run the CLI from the register step's /tmp/sdkcli
venv (gate: register success), with `--invoke-base` = the exact base the
register step posts (IFC: bare $FUNCTION_URL; CWN/CRS: dual-strip
INVOKE_BASE chain). Repos keep only their node-slugs.txt drift-guard test;
semantics tests live in python/tests/test_convergence.py. Supersedes the
per-repo-duplication convention — new node repos MUST NOT vendor a
convergence copy.
