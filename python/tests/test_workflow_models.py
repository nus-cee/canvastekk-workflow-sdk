"""Tests for workflow models."""


from canvastekk_workflow_sdk.workflow.models import (
    EdgeType,
    ResolutionStrategy,
    WorkflowEdge,
    WorkflowNode,
    WorkflowSpec,
)


class TestWorkflowSpec:
    def test_serialization_to_json(self) -> None:
        spec = WorkflowSpec(
            name="test-workflow",
            nodes=[
                WorkflowNode(id="node1", slug="echo-v1.0.0"),
            ],
            edges=[
                WorkflowEdge(from_node="node1", to_node="node2"),
            ],
        )
        data = spec.model_dump(mode="json")
        assert isinstance(data, dict)
        assert data["name"] == "test-workflow"
        assert len(data["nodes"]) == 1
        assert len(data["edges"]) == 1

    def test_round_trip_serialization(self) -> None:
        original = WorkflowSpec(
            name="round-trip",
            metadata={"version": "1.0.0"},
            nodes=[
                WorkflowNode(id="n1", slug="start-v1.0.0", inputs={"value": 42}),
                WorkflowNode(id="n2", slug="echo-v1.0.0", version="1.0.0"),
            ],
            edges=[
                WorkflowEdge(from_node="n1", to_node="n2", from_output="value", to_input="input"),
            ],
        )

        data = original.model_dump(mode="json")
        restored = WorkflowSpec(**data)
        second_data = restored.model_dump(mode="json")

        assert data == second_data
        assert original.metadata == restored.metadata
        assert len(original.nodes) == len(restored.nodes)
        assert len(original.edges) == len(restored.edges)

    def test_metadata_defaults_to_empty_dict(self) -> None:
        spec = WorkflowSpec(nodes=[], edges=[])
        assert spec.metadata == {}


class TestEdgeType:
    def test_enum_values(self) -> None:
        assert EdgeType.DEFAULT == "default"
        assert EdgeType.SUCCESS == "success"
        assert EdgeType.FAILURE == "failure"
        assert EdgeType.CONDITIONAL == "conditional"

    def test_edge_type_count(self) -> None:
        assert len(EdgeType) == 4


class TestResolutionStrategy:
    def test_enum_values(self) -> None:
        assert ResolutionStrategy.AUTO == "auto"
        assert ResolutionStrategy.FLAT == "flat"
        assert ResolutionStrategy.DOT_PATH == "dot_path"

    def test_strategy_count(self) -> None:
        assert len(ResolutionStrategy) == 3


class TestWorkflowEdge:
    def test_default_values(self) -> None:
        edge = WorkflowEdge(from_node="n1", to_node="n2")
        assert edge.id is not None
        assert isinstance(edge.id, str)
        assert edge.edge_type == EdgeType.DEFAULT
        assert edge.resolution_strategy == ResolutionStrategy.AUTO
        assert edge.from_output == ""
        assert edge.to_input == ""
        assert edge.condition is None

    def test_auto_generated_id_unique(self) -> None:
        edge1 = WorkflowEdge(from_node="n1", to_node="n2")
        edge2 = WorkflowEdge(from_node="n2", to_node="n3")
        assert edge1.id != edge2.id

    def test_all_fields_settable(self) -> None:
        edge = WorkflowEdge(
            id="custom-id",
            from_node="n1",
            to_node="n2",
            from_output="result",
            to_input="input",
            edge_type=EdgeType.SUCCESS,
            resolution_strategy=ResolutionStrategy.DOT_PATH,
            condition="true",
        )
        assert edge.id == "custom-id"
        assert edge.from_node == "n1"
        assert edge.to_node == "n2"
        assert edge.from_output == "result"
        assert edge.to_input == "input"
        assert edge.edge_type == EdgeType.SUCCESS
        assert edge.resolution_strategy == ResolutionStrategy.DOT_PATH
        assert edge.condition == "true"

    def test_condition_defaults_to_none(self) -> None:
        edge = WorkflowEdge(from_node="n1", to_node="n2")
        assert edge.condition is None


class TestWorkflowNode:
    def test_minimal_node(self) -> None:
        node = WorkflowNode(id="n1", slug="echo-v1.0.0")
        assert node.id == "n1"
        assert node.slug == "echo-v1.0.0"
        assert node.version is None
        assert node.name is None
        assert node.x is None
        assert node.y is None
        assert node.inputs == {}

    def test_all_fields_settable(self) -> None:
        node = WorkflowNode(
            id="n1",
            slug="segmentation-v1.0.0",
            version="1.0.0",
            name="My Segmentation",
            x=100.5,
            y=200.0,
            inputs={"threshold": 0.5},
        )
        assert node.id == "n1"
        assert node.slug == "segmentation-v1.0.0"
        assert node.version == "1.0.0"
        assert node.name == "My Segmentation"
        assert node.x == 100.5
        assert node.y == 200.0
        assert node.inputs == {"threshold": 0.5}

    def test_no_outputs_field(self) -> None:
        node = WorkflowNode(id="n1", slug="echo-v1.0.0")
        assert not hasattr(node, "outputs")

    def test_inputs_default_to_empty_dict(self) -> None:
        node = WorkflowNode(id="n1", slug="echo-v1.0.0")
        assert node.inputs == {}

    def test_positional_coordinates_optional(self) -> None:
        node = WorkflowNode(id="n1", slug="echo-v1.0.0", x=50.0)
        assert node.x == 50.0
        assert node.y is None

        node2 = WorkflowNode(id="n2", slug="echo-v1.0.0", y=100.0)
        assert node2.x is None
        assert node2.y == 100.0


class TestWorkflowSpecComplete:
    def test_complete_workflow_spec(self) -> None:
        spec = WorkflowSpec(
            name="point-cloud-pipeline",
            metadata={"author": "test", "version": "1.0.0"},
            nodes=[
                WorkflowNode(id="start", slug="__start__"),
                WorkflowNode(
                    id="segment",
                    slug="segmentation-v1.0.0",
                    version="1.0.0",
                    name="Segmentation",
                    inputs={"method": "dbscan"},
                ),
                WorkflowNode(id="end", slug="__end__"),
            ],
            edges=[
                WorkflowEdge(
                    from_node="start",
                    to_node="segment",
                    from_output="point_cloud",
                    to_input="input_file",
                ),
                WorkflowEdge(
                    from_node="segment",
                    to_node="end",
                    from_output="instances",
                    to_input="result",
                ),
            ],
        )
        assert spec.name == "point-cloud-pipeline"
        assert len(spec.nodes) == 3
        assert len(spec.edges) == 2
        assert spec.metadata == {"author": "test", "version": "1.0.0"}
