# Negative Assertions in Subprocess CLI Tests Need an Exit-0 Guard First

**Category**: convention
**Confidence**: 0.6
**Scope**: project
**Date**: 2026-09-25
**Source**: DA-3004 review (test_cli_init.py)

## Convention

A negative filesystem assertion in a subprocess CLI test must be preceded by
an exit-0 assertion — otherwise the test passes vacuously when the CLI
crashes (the asserted-absent path trivially doesn't exist). Applied in
`python/tests/test_cli_init.py:49` (returncode guard) before `:57` (legacy
`.opencode/skills` absence check). Request this pattern in review whenever a
test asserts absence. Related family: `test_main.py` subprocess style (no
module-scope package import — model_validator constraint).
