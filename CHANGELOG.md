# Changelog

All notable changes to this project will be documented in this file.

## [0.14.1] - 2026-05-29

### Documentation

- **DA-1162**: Add docstrings/JSDoc coverage + fix exception handling (#37)


## [0.14.0] - 2026-05-28

### Features

- **typescript**: Add TypeScript SDK with full feature parity (DA-1148) (#36)


### Miscellaneous Tasks

- **release**: Prepare v0.14.0


## [0.13.0] - 2026-05-26

### Features

- **sdk**: Add WorkflowRunner output_dir support and LocalFileServer test utility (DA-1102) (#34)


### Miscellaneous Tasks

- **release**: Prepare v0.13.0


## [0.12.0] - 2026-05-25

### Features

- Add workflow builder and local runner (DA-1087) (#33)


### Miscellaneous Tasks

- **release**: Prepare v0.12.0


## [0.11.0] - 2026-05-22

### Features

- **sdk**: Align SDK docs with engine semver versioning [DA-1041] (#32)


### Miscellaneous Tasks

- **release**: Prepare v0.11.0


## [0.10.1] - 2026-05-22

### Documentation

- **sdk**: Document {{variable}} template substitution behavior for node authors [DA-1038] (#31)


### Miscellaneous Tasks

- **release**: Prepare v0.10.1


## [0.10.0] - 2026-05-22

### Features

- **docs**: Align SDK naming with engine WorkflowNode/WorkflowDefinitionNode model [DA-1028]


### Miscellaneous Tasks

- **release**: Prepare v0.10.0


## [0.9.1] - 2026-05-21

### Bug Fixes

- **registry**: Align register_node() payload with engine RegisterNodeRequest schema [DA-1016] (#29)


### Miscellaneous Tasks

- **release**: Prepare v0.9.1


## [0.9.0] - 2026-05-21

### Features

- Enforce node definition versioning and auto-derive id field (DA-1014) (#28) (**BREAKING**)


### Miscellaneous Tasks

- **release**: Prepare v0.9.0


## [0.8.0] - 2026-05-20

### Features

- **sdk**: Auto-download presigned URL file inputs before execute() [DA-996] (#26)


### Miscellaneous Tasks

- **release**: Prepare v0.8.0


## [0.7.2] - 2026-05-17

### Documentation

- Add EXTERNAL-AUTHOR-GUIDE.md for node registration [DA-943]


### Miscellaneous Tasks

- **release**: Prepare v0.7.2


## [0.7.1] - 2026-05-17

### Style

- Apply ruff formatter to existing codebase


### Miscellaneous Tasks

- **release**: Prepare v0.7.1


## [0.7.0] - 2026-05-17

### Features

- **registry**: Add service_token auth support to register_node() [DA-931]


### Miscellaneous Tasks

- **release**: Prepare v0.7.0


## [0.6.0] - 2026-05-16

### Features

- **DA-910**: Add opencode skill scaffolding CLI for AI agent node creation
- **DA-910**: Add opencode skill scaffolding CLI for AI agent node creation (#DA-910)


### Miscellaneous Tasks

- **release**: Prepare v0.6.0


## [0.5.2] - 2026-05-16

### Documentation

- **DA-898**: Separate deployment concerns from SDK documentation (#21)


### Miscellaneous Tasks

- **release**: Prepare v0.5.2


## [0.5.1] - 2026-05-16

### Bug Fixes

- Resolve ruff N812 and I001 lint errors in test files


### Miscellaneous Tasks

- **release**: Prepare v0.5.1


## [0.5.0] - 2026-05-16

### Features

- **sdk**: V0.5.0 — public-endpoint hardening with auth, timeout enforcement, and DX improvements (#14)
- Migrate format:binary to format:file, remove multipart, add CLI validate (**BREAKING**)
- Add industry-standard SDK enhancements, structured logging, env vars docs
- Migrate format:binary to format:file, add SDK enhancements (DA-894) (**BREAKING**)


### Bug Fixes

- Address code review findings — P0/P1/P2 fixes
- Use sys.executable instead of hardcoded .venv path in test_main.py (CI fix)
- Revert manual version bump to 0.4.9, let release workflow handle bump


### Documentation

- **plan**: Add PLAN-DA-894 for format:binary → format:file migration
- **plan**: Revise PLAN-DA-894 with architecture review findings
- **plan**: Add end-to-end file flow, release coordination, and reference docs
- **plan**: Simplify file flow to CDS-only — remove MODE A browser upload
- **plan**: Add file field validation helper and x-* extensions
- **plan**: Hard break — remove dual detection, promote httpx
- **plan**: Add manifest format enforcement via Pydantic validator
- **plan**: Add full workflow diagram and manifest enforcement diagram
- **plan**: Clarify HTTP client choice in publisher, add CLI validate utility
- **plan+readme+example**: Add utilities section, architecture decisions, echo node example
- Add logging section to Python README, expand root README features, update plan checkboxes


### Style

- Remove unused SDKVersionMiddleware import in test_middleware
- Fix ruff N812 and I001 in test files — use __version__ directly


### Miscellaneous Tasks

- Add workflow_dispatch and __init__.py bump to release workflow
- Regenerate poetry.lock (remove python-multipart, promote httpx to main)
- Configure git-cliff to not bump major on breaking for 0.x
- **release**: Prepare v0.5.0


## [0.4.9] - 2026-05-14

### Bug Fixes

- **release**: Upload Python SDK as release assets instead of GitHub Packages


### Miscellaneous Tasks

- **release**: Prepare v0.4.9


## [0.4.8] - 2026-05-14

### Bug Fixes

- **release**: Use twine for GitHub Packages publish


### Miscellaneous Tasks

- **release**: Prepare v0.4.8


## [0.4.7] - 2026-05-14

### Bug Fixes

- **release**: Use GH_PAT for GitHub Packages publish


### Miscellaneous Tasks

- **release**: Prepare v0.4.7


## [0.4.6] - 2026-05-14

### Bug Fixes

- **release**: Configure poetry publish repository URL for GitHub Packages


### Miscellaneous Tasks

- **release**: Prepare v0.4.6


## [0.4.5] - 2026-05-14

### Bug Fixes

- **release**: Unconditional version bump, detect only for publish gate
- **release**: Restore pull-requests read permission for git-cliff GitHub API
- **release**: Remove --no-update flag incompatible with Poetry 2.x


### Miscellaneous Tasks

- **release**: Prepare v0.4.5


## [0.4.4] - 2026-05-14

### Bug Fixes

- **release**: Export version variable for Python bump and sync poetry.lock


### Miscellaneous Tasks

- **release**: Prepare v0.4.4


## [0.4.3] - 2026-05-14

### Refactoring

- Combine release and publish into single workflow (#5)


### Miscellaneous Tasks

- **release**: Prepare v0.4.3


## [0.4.2] - 2026-05-14

### Bug Fixes

- Prevent release workflow from re-triggering on changelog commits (#4)


### Miscellaneous Tasks

- **release**: Prepare v0.4.2


## [0.4.1] - 2026-05-14

### Features

- Add git-cliff semantic versioning and automated release workflow (#2)


### Bug Fixes

- Unified monorepo versioning with per-language selective publish (#3)


### Refactoring

- Restructure as polyglot monorepo with GitHub Packages CI/CD (#1)


<!-- generated by git-cliff -->
