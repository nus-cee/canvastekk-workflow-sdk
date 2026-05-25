# PLAN: SDK Workflow Builder & Local Runner

**JIRA Ticket**: [DA-1087](https://betekk.atlassian.net/browse/DA-1087)
**Branch**: `DA-1087`
**Issue Type**: Story
**Priority**: High

---

## Overview

Add a new `workflow` module to the CanvasTEKK Workflow SDK that lets end users build, validate, and test-run complete workflow DAGs locally — without requiring the CanvasTEKK Workflow Engine's REST API, Temporal, S3, or distributed orchestration.

---

## Acceptance Criteria

- [ ] Users can build workflow definitions using a fluent API (`WorkflowBuilder`) with `add_start()`, `add_end()`, `add_node()`, `connect()`, `build()`
- [ ] Workflow DAGs are validated locally — graph connectivity, input/schema checks, orphan/dead-end detection, START/END constraints
- [ ] Users can test-run workflows locally in two modes: in-process (BaseNode instances directly) or HTTP (calling running node services)
- [ ] WorkflowSpec serializes to engine-compatible JSON (POSTable to `/api/workflows/definitions`)
- [ ] No new external dependencies required — uses asyncio (stdlib), httpx (existing), existing BaseNode/ExecutionContext
- [ ] Full test coverage for models, builder, validation, and runner

---

## Phase 1: Models — WorkflowSpec, WorkflowNode, WorkflowEdge, EdgeType

**File**: `python/canvastekk_workflow_sdk/workflow/models.py`

- [ ] Create `workflow/` package directory with `__init__.py`
- [ ] Define `EdgeType` enum (DATA, CONTROL) matching engine schema
- [ ] Define `WorkflowEdge` Pydantic model with `id`, `source`, `target`, `source_output`, `target_input`, `edge_type` fields
- [ ] Define `WorkflowNode` Pydantic model with `id`, `slug`, `inputs` (static params), `outputs` fields
- [ ] Define `WorkflowSpec` Pydantic model with `name`, `nodes`, `edges` fields
- [ ] Add `to_engine_json()` method on `WorkflowSpec` for engine-compatible serialization
- [ ] Add `from_engine_json()` classmethod for deserialization from engine format
- [ ] Verify models serialize to JSON compatible with engine's `SaveWorkflowRequest.spec` schema

## Phase 2: Builder — WorkflowBuilder Fluent API

**File**: `python/canvastekk_workflow_sdk/workflow/builder.py`

- [ ] Implement `WorkflowBuilder.__init__(name)` — initialize empty node/edge lists
- [ ] Implement `add_start(id, outputs)` — add a `__start__` type node with named outputs
- [ ] Implement `add_end(id, inputs)` — add an `__end__` type node with named inputs
- [ ] Implement `add_node(id, slug, inputs)` — add a user node with slug reference and static input params
- [ ] Implement `connect(source, target, from_output, to_input, edge_type)` — add an edge between nodes
- [ ] Implement `build()` — validate (delegates to validation module) and return `WorkflowSpec`
- [ ] Add duplicate node ID detection in builder methods
- [ ] Add method chaining support (all methods return `self` except `build()`)

## Phase 3: Validation — Graph Validation (BFS)

**File**: `python/canvastekk_workflow_sdk/workflow/validation.py`

- [ ] Implement `validate(spec: WorkflowSpec)` entry point returning list of validation errors
- [ ] Implement node ID uniqueness check
- [ ] Implement edge reference validation (source/target must reference existing node IDs)
- [ ] Implement START/END constraints:
  - [ ] Exactly 1 `__start__` node
  - [ ] At least 1 `__end__` node
  - [ ] START has no incoming edges
  - [ ] END has no outgoing edges
- [ ] Implement forward BFS from START — detect orphan nodes (unreachable from START)
- [ ] Implement reverse BFS from END — detect dead-end nodes (cannot reach any END)
- [ ] Raise `WorkflowValidationError` with descriptive messages for each failure mode
- [ ] Return cleanly (no exception) for valid graphs

## Phase 4: Control Flow — Built-in START/END Handlers

**File**: `python/canvastekk_workflow_sdk/workflow/_control_flow.py`

- [ ] Implement `_start_handler(inputs, context)` — identity function that passes through initial workflow inputs to output map
- [ ] Implement `_end_handler(inputs, context)` — identity function that collects final outputs from incoming edges
- [ ] Ensure handlers are compatible with BaseNode.execute() signature pattern
- [ ] Handle multiple output mapping (START produces named outputs, END collects named inputs)

## Phase 5: Runner — WorkflowRunner with In-Process and HTTP Modes

**File**: `python/canvastekk_workflow_sdk/workflow/runner.py`

- [ ] Define `WorkflowRunResult` dataclass with `status`, `final_outputs`, `node_results`, `duration_ms`
- [ ] Define `NodeResult` dataclass with `node_id`, `status`, `outputs`, `duration_ms`, `error`
- [ ] Implement `WorkflowRunner.__init__()` — initialize node registry (in-process) and URL registry (HTTP)
- [ ] Implement `register(slug, node_instance)` — register a BaseNode instance for in-process execution
- [ ] Implement `register_url(slug, url)` — register a URL for HTTP mode execution
- [ ] Implement `_compute_levels(spec)` — BFS topological sort returning list of execution levels
- [ ] Implement `_resolve_inputs(node_id, spec, results)` — resolve node inputs from edge outputs + static params
- [ ] Implement `_execute_in_process(node, inputs, context)` — call `node.execute()` directly
- [ ] Implement `_execute_http(url, slug, inputs)` — POST inputs to running node service via httpx
- [ ] Implement `run(spec, inputs)` — main execution loop:
  - [ ] Compute execution levels
  - [ ] For each level: separate control-flow nodes from user nodes
  - [ ] Run user nodes concurrently within each level using `asyncio.gather`
  - [ ] Collect and propagate outputs between levels
  - [ ] Collect final outputs from END nodes
  - [ ] Return `WorkflowRunResult`
- [ ] Handle errors gracefully — capture per-node errors, continue/stop based on severity
- [ ] Raise `WorkflowExecutionError` for unrecoverable failures

## Phase 6: Update SDK Exports, Exceptions, and Context

**Files**:
- `python/canvastekk_workflow_sdk/__init__.py`
- `python/canvastekk_workflow_sdk/exceptions.py`
- `python/canvastekk_workflow_sdk/context.py`

- [ ] Add `WorkflowValidationError` to `exceptions.py`
- [ ] Add `WorkflowExecutionError` to `exceptions.py`
- [ ] Add `ExecutionContext.from_params()` classmethod to `context.py` for runner-created lightweight contexts
- [ ] Export `WorkflowSpec`, `WorkflowBuilder`, `WorkflowRunner`, `WorkflowRunResult` from `__init__.py`
- [ ] Export `WorkflowValidationError`, `WorkflowExecutionError` from `__init__.py`
- [ ] Export `WorkflowNode`, `WorkflowEdge`, `EdgeType` from `__init__.py`
- [ ] Update `workflow/__init__.py` with public API exports

## Phase 7: Tests

**Files**:
- `tests/test_workflow_models.py`
- `tests/test_workflow_builder.py`
- `tests/test_workflow_validation.py`
- `tests/test_workflow_runner.py`

- [ ] `test_workflow_models.py`:
  - [ ] Test WorkflowSpec serialization to engine-compatible JSON
  - [ ] Test WorkflowSpec deserialization from engine JSON
  - [ ] Test round-trip (serialize → deserialize → serialize) produces identical output
  - [ ] Test EdgeType enum values match engine
  - [ ] Test default values and field validation
- [ ] `test_workflow_builder.py`:
  - [ ] Test basic workflow creation with add_start, add_node, add_end, connect
  - [ ] Test build() triggers validation
  - [ ] Test duplicate node ID detection
  - [ ] Test missing START/END node errors
  - [ ] Test method chaining
  - [ ] Test auto-START/END node creation if desired
- [ ] `test_workflow_validation.py`:
  - [ ] Test valid graph passes validation
  - [ ] Test orphan node detection (forward BFS)
  - [ ] Test dead-end node detection (reverse BFS)
  - [ ] Test multiple START nodes rejected
  - [ ] Test no START node rejected
  - [ ] Test no END node rejected
  - [ ] Test START with incoming edges rejected
  - [ ] Test END with outgoing edges rejected
  - [ ] Test invalid edge references rejected
  - [ ] Test duplicate node IDs rejected
- [ ] `test_workflow_runner.py`:
  - [ ] Test in-process execution with mock BaseNode instances
  - [ ] Test level computation for linear and diamond DAGs
  - [ ] Test input resolution from edges and static params
  - [ ] Test final output collection from END nodes
  - [ ] Test WorkflowRunResult structure
  - [ ] Test error handling — node raises exception
  - [ ] Test concurrent execution within a level
  - [ ] Test HTTP mode (mocked httpx calls)

---

## Dependencies

No new dependencies. Uses:
- `asyncio` (stdlib) for concurrent node execution
- `httpx` (existing SDK dependency) for HTTP mode
- `pydantic` (existing) for models
- Existing `BaseNode`, `ExecutionContext` from SDK

## Risks & Mitigation

| Risk | Mitigation |
|------|------------|
| Engine schema drift | Validate JSON output against engine's actual schema in tests |
| Async complexity in runner | Keep asyncio usage simple (gather per level), avoid complex synchronization |
| Control flow edge cases | Comprehensive test coverage for START/END handlers |

## Success Metrics

- All acceptance criteria met
- All tests pass (`poetry run pytest -v`)
- Ruff linting clean (`poetry run ruff check`)
- PLAN phases 1-7 complete
