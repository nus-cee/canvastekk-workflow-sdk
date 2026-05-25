# PLAN: SDK Workflow Builder & Local Runner

**JIRA Ticket**: [DA-1087](https://betekk.atlassian.net/browse/DA-1087)
**Branch**: `DA-1087`
**Issue Type**: Story
**Priority**: High

---

## Overview

Add a new `workflow` module to the CanvasTEKK Workflow SDK that lets end users build, validate, and test-run complete workflow DAGs locally — without requiring the CanvasTEKK Workflow Engine's REST API, Temporal, S3, or distributed orchestration.

### Intentional Feature Differences from Engine

| Feature | Engine | SDK Runner |
|---------|--------|------------|
| Orchestration | Temporal (distributed) | In-process (BFS levels, asyncio) |
| Node execution | HTTP calls to deployed services | Direct .execute() or HTTP calls |
| File handling | S3 presigned URLs | Local file paths (passthrough) |
| Credentials | Encrypted credential store | Not needed locally |
| Durability | Workflow state persisted | Ephemeral, in-memory |
| Callbacks | Async HTTP callbacks | Synchronous execution |

---

## Acceptance Criteria

- [ ] Users can build workflow definitions using a fluent API (`WorkflowBuilder`) with `add_start()`, `add_end()`, `add_node()`, `connect()`, `build()`
- [ ] Workflow DAGs are validated locally — graph connectivity, cycle detection, orphan/dead-end detection, START/END constraints
- [ ] Users can test-run workflows locally via `NodeExecutor` strategy: in-process (`BaseNode` instances) or HTTP (calling running node services)
- [ ] WorkflowSpec serializes to engine-compatible JSON (POSTable to `/api/workflows/definitions`)
- [ ] No new external dependencies required — uses asyncio (stdlib), httpx (existing), existing BaseNode/ExecutionContext
- [ ] Full test coverage for models, builder, validation, and runner
- [ ] Backward compatibility — existing BaseNode/ExecutionContext/NodeExecutionRequest unchanged

---

## Phase 1: Models — WorkflowSpec, WorkflowNode, WorkflowEdge, EdgeType, ResolutionStrategy

**File**: `python/canvastekk_workflow_sdk/workflow/models.py`

Engine-compatible Pydantic models matching the engine's `SaveWorkflowRequest.spec` schema.
Field names use engine conventions (`from_node`, `to_node`) directly — no aliasing needed
since these are data models, not a user-facing builder API.

- [ ] Create `workflow/` package directory with `__init__.py`
- [ ] Define `EdgeType` enum matching engine routing semantics:
  ```python
  class EdgeType(str, Enum):
      DEFAULT = "default"        # Always fires on successful execution
      SUCCESS = "success"        # Fires only on success result
      FAILURE = "failure"        # Fires only on failure result
      CONDITIONAL = "conditional"  # Fires on CEL expression evaluation
  ```
- [ ] Define `ResolutionStrategy` enum for output resolution:
  ```python
  class ResolutionStrategy(str, Enum):
      AUTO = "auto"          # Flat key first, dot-path fallback
      FLAT = "flat"          # Literal key name only
      DOT_PATH = "dot_path"  # Nested dict traversal via dot segments
  ```
- [ ] Define `WorkflowEdge` Pydantic model with engine-compatible field names:
  - `id: str` (auto-generated uuid4)
  - `from_node: str` (source node instance ID)
  - `to_node: str` (target node instance ID)
  - `from_output: str` (output field from source — supports dot-notation)
  - `to_input: str` (input field name on target)
  - `edge_type: EdgeType = DEFAULT`
  - `resolution_strategy: ResolutionStrategy = AUTO`
  - `condition: str | None = None` (CEL expression for conditional edges)
- [ ] Define `WorkflowNode` Pydantic model matching engine spec (NO `outputs` field):
  - `id: str` (unique node instance ID within workflow)
  - `slug: str` (node type slug from registry, e.g. `"__start__"`, `"segmentation-v1.0.0"`)
  - `version: str | None = None` (pinned node version)
  - `name: str | None = None` (display label)
  - `x: float | None = None` (canvas position)
  - `y: float | None = None` (canvas position)
  - `inputs: dict[str, Any] = {}` (static input values)
- [ ] Define `WorkflowSpec` Pydantic model:
  - `name: str | None = None` (workflow display name)
  - `nodes: list[WorkflowNode]`
  - `edges: list[WorkflowEdge]`
  - `metadata: dict[str, Any] = {}` (includes optional `version` key)
- [ ] Verify `WorkflowSpec.model_dump(mode="json")` produces JSON compatible with engine's `SaveWorkflowRequest.spec`
- [ ] Verify round-trip: serialize → deserialize → serialize produces identical output

## Phase 2: Builder — WorkflowBuilder Fluent API

**File**: `python/canvastekk_workflow_sdk/workflow/builder.py`

Fluent builder with built-in START/END node creation. Builder methods return `self` for chaining.

- [ ] Implement `WorkflowBuilder.__init__(name)` — initialize empty node/edge lists, store workflow name
- [ ] Implement `add_start(node_id="start", *, outputs=None, config_schema=None)`:
  - Creates node with `slug="__start__"`
  - If `outputs` provided (list of field names), sets `config_schema` with string properties for each field
  - Only one START node allowed (raise on duplicate)
- [ ] Implement `add_end(node_id="end")`:
  - Creates node with `slug="__end__"`
  - Multiple END nodes allowed
- [ ] Implement `add_node(node_id, *, slug, name=None, inputs=None, version=None)`:
  - Creates node with given slug (registry reference)
  - `slug` must not be `"__start__"` or `"__end__"` (reserved)
  - Duplicate `node_id` raises error
- [ ] Implement `connect(from_node, to_node, *, from_output, to_input, edge_type=EdgeType.DEFAULT, condition=None)`:
  - Creates edge with engine-compatible field names
  - Validates `from_node` and `to_node` reference existing node IDs (raises on unknown)
- [ ] Implement `build(*, validate=True)`:
  - Constructs `WorkflowSpec` from accumulated nodes/edges
  - If `validate=True`, delegates to `validation.validate(spec)` — raises `WorkflowValidationError` on failure
  - Returns `WorkflowSpec`
- [ ] Add duplicate node ID detection in all `add_*` methods
- [ ] Add method chaining support (all methods return `self` except `build()`)

## Phase 3: Validation — Graph Validation (BFS + Cycle Detection)

**File**: `python/canvastekk_workflow_sdk/workflow/validation.py`

Port engine's validation logic with cycle detection added.

- [ ] Implement `validate(spec: WorkflowSpec) -> ValidationResult` entry point
- [ ] Implement `ValidationResult` dataclass:
  - `is_valid: bool`
  - `errors: list[str]`
  - `orphans: list[str]` (node IDs unreachable from START)
  - `dead_ends: list[str]` (node IDs that cannot reach any END)
- [ ] Implement node ID uniqueness check
- [ ] Implement edge reference validation (`from_node`/`to_node` must reference existing node IDs)
- [ ] Implement START/END constraints:
  - [ ] Exactly 1 `__start__` node
  - [ ] At least 1 `__end__` node
  - [ ] START has no incoming edges (in_degree == 0)
  - [ ] END has no outgoing edges (out_degree == 0)
- [ ] Implement **cycle detection** using Kahn's algorithm:
  - Build adjacency list + in-degree map
  - Process nodes with 0 in-degree
  - If processed count < total node count, remaining nodes form a cycle
- [ ] Implement forward BFS from START — detect orphan nodes (unreachable from START)
- [ ] Implement reverse BFS from END — detect dead-end nodes (cannot reach any END)
- [ ] Raise `WorkflowValidationError` with descriptive messages for each failure mode
- [ ] Return cleanly (no exception) for valid graphs

## Phase 4: Control Flow — Built-in START/END Handlers

**File**: `python/canvastekk_workflow_sdk/workflow/_control_flow.py`

Simple callable handlers for the runner. NOT BaseNode subclasses — they're plain functions
following a `ControlFlowHandler` protocol. No schema validation, no middleware.

- [ ] Define `ControlFlowHandler` protocol:
  ```python
  class ControlFlowHandler(Protocol):
      def __call__(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]: ...
  ```
- [ ] Implement `start_handler(inputs, context)` — identity passthrough (returns `dict(inputs)`)
- [ ] Implement `end_handler(inputs, context)` — identity passthrough (collects wired inputs)
- [ ] Register handlers in a module-level dict: `CONTROL_FLOW_HANDLERS: dict[str, ControlFlowHandler]`
  - Keys: `"__start__"`, `"__end__"`

## Phase 5a: Executor — NodeExecutor Strategy (InProcess + HTTP)

**File**: `python/canvastekk_workflow_sdk/workflow/executor.py`

Strategy pattern for node execution. Decouples HOW a node runs from the orchestration loop.

- [ ] Define `NodeExecutor` ABC:
  ```python
  class NodeExecutor(ABC):
      @abstractmethod
      async def execute(self, slug: str, inputs: dict, context: ExecutionContext) -> dict: ...
      @abstractmethod
      def has(self, slug: str) -> bool: ...
  ```
- [ ] Implement `InProcessExecutor(NodeExecutor)`:
  - Internal registry: `dict[str, BaseNode]`
  - `register(slug, node: BaseNode)` — register a node instance
  - `execute(slug, inputs, context)` — wrap `node.execute()` in `asyncio.to_thread()` to avoid blocking event loop
  - `has(slug)` — check if slug is registered
- [ ] Implement `HttpExecutor(NodeExecutor)`:
  - Internal registry: `dict[str, str]` (slug → base URL)
  - `register_url(slug, url)` — register a node URL
  - `execute(slug, inputs, context)` — POST `NodeExecutionRequest`-compatible payload to `{url}/execute` via `httpx.AsyncClient`
  - Payload format: `{"run_id": ctx.run_id, "node_id": ctx.node_id, "inputs": inputs}`
  - Parse response `outputs` field from `NodeExecutionResponse`
  - `has(slug)` — check if slug is registered

## Phase 5b: Resolver — Input Resolution with Dot-Notation

**File**: `python/canvastekk_workflow_sdk/workflow/resolver.py`

Resolves a node's inputs from static params + incoming edge outputs. Supports dot-notation
traversal for nested output extraction (matching engine's `ResolutionStrategy`).

- [ ] Implement `resolve_inputs(node_id, spec, node_outputs) -> dict`:
  - Start with node's static `inputs` as base
  - For each incoming edge targeting `node_id`:
    - Extract value from source node's outputs using `from_output` + `resolution_strategy`
    - Apply to `to_input` key on the resolved inputs dict
  - Return merged inputs dict
- [ ] Implement `_resolve_output(source_outputs, from_output, strategy) -> Any`:
  - `FLAT`: literal key lookup
  - `DOT_PATH`: walk nested dict via dot segments (e.g. `"data.url"` → `outputs["data"]["url"]`)
  - `AUTO`: flat first, dot-path fallback if key not found and `from_output` contains "."

## Phase 5c: Level — BFS Level Computation

**File**: `python/canvastekk_workflow_sdk/workflow/level.py`

Pure function for computing execution levels from a DAG. Each level contains nodes
that can execute in parallel (all their dependencies are in earlier levels).

- [ ] Implement `compute_levels(spec: WorkflowSpec) -> list[list[str]]`:
  - Build adjacency list and in-degree map from edges
  - BFS topological sort (Kahn's algorithm)
  - Group nodes by level (nodes with 0 in-degree at each iteration)
  - Control-flow nodes (`__start__`, `__end__`) included in appropriate levels
  - Returns list of levels, each level is a list of node IDs
- [ ] Handle edge case: single node, linear chain, diamond DAG, wide fan-out

## Phase 5d: Runner — WorkflowRunner Orchestrator

**File**: `python/canvastekk_workflow_sdk/workflow/runner.py`

Orchestrator that ties together executor, resolver, and level computation. Accepts a
`NodeExecutor` via constructor (Strategy pattern) — no dual-registry confusion.

- [ ] Define `NodeResult` Pydantic model:
  - `node_id: str`
  - `slug: str`
  - `status: Literal["completed", "failed", "skipped"]`
  - `outputs: dict[str, Any] | None`
  - `duration_ms: int`
  - `error: str | None = None`
  - `skipped_reason: str | None = None`
- [ ] Define `WorkflowRunResult` Pydantic model:
  - `status: Literal["completed", "failed"]`
  - `final_outputs: dict[str, Any]`
  - `node_results: list[NodeResult]`
  - `duration_ms: int`
- [ ] Implement `WorkflowRunner.__init__(executor: NodeExecutor)`:
  - Accept a `NodeExecutor` instance (user creates `InProcessExecutor()` or `HttpExecutor()`)
- [ ] Implement `run(spec, inputs=None) -> WorkflowRunResult`:
  - Compute execution levels via `level.compute_levels(spec)`
  - Create `ExecutionContext` for each node via new factory (see Phase 6)
  - For each level:
    - Separate control-flow nodes from user nodes
    - Control-flow: call `CONTROL_FLOW_HANDLERS[slug](inputs, context)` synchronously
    - User nodes: call `executor.execute(slug, inputs, context)` concurrently via `asyncio.gather`
    - Resolve inputs via `resolver.resolve_inputs()` before execution
  - Collect final outputs from END nodes
  - Handle errors per-node — failed upstream nodes cause downstream nodes to be `skipped`
  - Return `WorkflowRunResult`
- [ ] Define `ErrorPolicy` enum:
  - `FAIL_FAST` — stop entire workflow on first node error
  - `CONTINUE` — skip failed node's downstream nodes, continue remaining
  - Default: `FAIL_FAST`
- [ ] Wire `run()` as async, provide `run_sync()` convenience wrapper

## Phase 6: Update SDK Exports, Exceptions, and Context

**Files**:
- `python/canvastekk_workflow_sdk/__init__.py`
- `python/canvastekk_workflow_sdk/exceptions.py`
- `python/canvastekk_workflow_sdk/context.py`
- `python/canvastekk_workflow_sdk/workflow/__init__.py`

- [ ] Add `WorkflowValidationError` to `exceptions.py`:
  ```python
  class WorkflowValidationError(NodeExecutionError):
      """Raised when workflow spec validation fails."""
      def __init__(self, message, *, errors=None): ...
  ```
- [ ] Add `WorkflowExecutionError` to `exceptions.py`:
  ```python
  class WorkflowExecutionError(NodeExecutionError):
      """Raised when local workflow execution fails."""
      def __init__(self, message, *, node_id=None): ...
  ```
- [ ] Refactor `ExecutionContext.__init__()` to accept EITHER `NodeExecutionRequest` (existing path) OR keyword args `run_id`/`node_id` (new runner path):
  ```python
  def __init__(self, request=None, *, run_id=None, node_id=None, output_dir=None):
      # Backward compatible: request still works as positional arg
      # New path: run_id + node_id from keyword args (for runner-created contexts)
  ```
- [ ] Update `workflow/__init__.py` with clean public API boundary:
  - `WorkflowSpec`, `WorkflowNode`, `WorkflowEdge`, `EdgeType`, `ResolutionStrategy`
  - `WorkflowBuilder`
  - `WorkflowRunner`, `WorkflowRunResult`, `NodeResult`
  - `InProcessExecutor`, `HttpExecutor`
  - `validate`
- [ ] Export workflow classes from top-level `__init__.py`
- [ ] Export `WorkflowValidationError`, `WorkflowExecutionError` from top-level `__init__.py`

## Phase 7: Tests

**Files**:
- `python/tests/test_workflow_models.py`
- `python/tests/test_workflow_builder.py`
- `python/tests/test_workflow_validation.py`
- `python/tests/test_workflow_resolver.py`
- `python/tests/test_workflow_runner.py`

- [ ] `test_workflow_models.py`:
  - [ ] Test WorkflowSpec serialization to engine-compatible JSON
  - [ ] Test WorkflowSpec round-trip (serialize → deserialize → serialize) produces identical output
  - [ ] Test EdgeType enum values match engine (`DEFAULT/SUCCESS/FAILURE/CONDITIONAL`)
  - [ ] Test ResolutionStrategy enum values (`AUTO/FLAT/DOT_PATH`)
  - [ ] Test default values and field validation
  - [ ] Test WorkflowNode has NO `outputs` field (engine doesn't have it)
  - [ ] Test WorkflowSpec `metadata` field defaults to empty dict
- [ ] `test_workflow_builder.py`:
  - [ ] Test basic workflow creation with add_start, add_node, add_end, connect
  - [ ] Test `add_start()` creates node with `slug="__start__"`
  - [ ] Test `add_end()` creates node with `slug="__end__"`
  - [ ] Test `add_start()` with `outputs` sets `config_schema`
  - [ ] Test `add_start()` rejects second START node
  - [ ] Test `add_node()` rejects `__start__` or `__end__` as slug
  - [ ] Test build() triggers validation by default
  - [ ] Test build(validate=False) skips validation
  - [ ] Test duplicate node ID detection
  - [ ] Test missing START/END node errors
  - [ ] Test method chaining (all add/connect methods return self)
  - [ ] Test connect() validates node IDs exist
- [ ] `test_workflow_validation.py`:
  - [ ] Test valid graph passes validation
  - [ ] Test orphan node detection (forward BFS)
  - [ ] Test dead-end node detection (reverse BFS)
  - [ ] Test cycle detection (Kahn's algorithm)
  - [ ] Test multiple START nodes rejected
  - [ ] Test no START node rejected
  - [ ] Test no END node rejected
  - [ ] Test START with incoming edges rejected
  - [ ] Test END with outgoing edges rejected
  - [ ] Test invalid edge references rejected
  - [ ] Test duplicate node IDs rejected
  - [ ] Test ValidationResult structure (is_valid, errors, orphans, dead_ends)
- [ ] `test_workflow_resolver.py`:
  - [ ] Test flat key resolution
  - [ ] Test dot-notation resolution (`"data.url"` → nested traversal)
  - [ ] Test AUTO strategy (flat first, dot fallback)
  - [ ] Test FLAT strategy (literal key only)
  - [ ] Test DOT_PATH strategy (always nested traversal)
  - [ ] Test static inputs merged with edge inputs
  - [ ] Test multiple incoming edges to same node
  - [ ] Test missing source output raises error
- [ ] `test_workflow_runner.py`:
  - [ ] Test InProcessExecutor with mock BaseNode instances
  - [ ] Test HttpExecutor with mocked httpx calls (verify NodeExecutionRequest payload format)
  - [ ] Test level computation for linear, diamond, and wide DAGs
  - [ ] Test input resolution from edges and static params
  - [ ] Test final output collection from END nodes
  - [ ] Test WorkflowRunResult structure
  - [ ] Test error handling — node raises exception, downstream nodes skipped
  - [ ] Test ErrorPolicy.FAIL_FAST stops on first error
  - [ ] Test ErrorPolicy.CONTINUE skips failed node downstream only
  - [ ] Test concurrent execution within a level (asyncio.to_thread for sync execute)
  - [ ] Test backward compatibility — existing BaseNode.run() still works with NodeExecutionRequest

---

## Architecture

```
workflow/
  __init__.py        — Public API boundary
  models.py          — Engine-compatible Pydantic models (WorkflowSpec, WorkflowNode, WorkflowEdge, EdgeType, ResolutionStrategy)
  builder.py         — Fluent WorkflowBuilder API
  validation.py      — Graph validation (BFS connectivity + Kahn's cycle detection)
  _control_flow.py   — Built-in START/END handlers (plain functions, not BaseNode)
  executor.py        — NodeExecutor ABC + InProcessExecutor + HttpExecutor (Strategy pattern)
  resolver.py        — Input resolution with dot-notation support
  level.py           — BFS topological sort (pure function)
  runner.py          — WorkflowRunner orchestrator (accepts NodeExecutor, delegates execution)
```

Dependency direction (all inward toward models):
```
builder ──→ models       ✅ Presentation → Domain
validation ──→ models    ✅ Application → Domain
runner ──→ models        ✅ Application → Domain
runner ──→ executor      ✅ Orchestration → Strategy
runner ──→ resolver      ✅ Orchestration → Utility
runner ──→ level         ✅ Orchestration → Algorithm
runner ──→ _control_flow ✅ Orchestration → Built-in
executor ──→ base.py     ✅ Strategy → Domain (BaseNode)
executor ──→ context.py  ✅ Strategy → Domain (ExecutionContext)
```

## Dependencies

No new dependencies. Uses:
- `asyncio` (stdlib) for concurrent node execution
- `httpx` (existing SDK dependency) for HTTP mode
- `pydantic` (existing) for models
- Existing `BaseNode`, `ExecutionContext` from SDK

## Risks & Mitigation

| Risk | Mitigation |
|------|------------|
| Engine schema drift | Test SDK output against engine's Pydantic models for structural compatibility |
| Async/sync mismatch | Wrap sync `BaseNode.execute()` in `asyncio.to_thread()` — don't block event loop |
| Cycle in DAG | Kahn's algorithm detects cycles before execution |
| Context coupling | Refactor ExecutionContext to accept primitives (backward compatible) |
| Dual runner confusion | Strategy pattern: one executor per runner, no register/register_url on same object |

## Success Metrics

- All acceptance criteria met
- All tests pass (`poetry run pytest -v`)
- Ruff linting clean (`poetry run ruff check canvastekk_workflow_sdk/ tests/`)
- PLAN phases 1-7 complete
- Existing tests still pass (backward compatibility)
