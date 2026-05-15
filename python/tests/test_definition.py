"""Tests for NodeDefinition and RetryConfig models."""

import json
import tempfile
from pathlib import Path

import pytest

from canvastekk_workflow_sdk import NodeDefinition, RetryConfig
from canvastekk_workflow_sdk.definition import export_definition


class TestRetryConfig:
    """Tests for RetryConfig model."""

    def test_default_values(self) -> None:
        """Test default retry configuration."""
        config = RetryConfig()
        assert config.max_attempts == 1
        assert config.initial_delay_ms == 1000
        assert config.backoff_multiplier == 2.0
        assert config.max_delay_ms == 30000

    def test_custom_values(self) -> None:
        """Test custom retry configuration."""
        config = RetryConfig(
            max_attempts=3,
            initial_delay_ms=500,
            backoff_multiplier=1.5,
            max_delay_ms=10000,
        )
        assert config.max_attempts == 3
        assert config.initial_delay_ms == 500
        assert config.backoff_multiplier == 1.5
        assert config.max_delay_ms == 10000

    def test_validation_max_attempts_minimum(self) -> None:
        """Test that max_attempts must be at least 1."""
        with pytest.raises(ValueError):
            RetryConfig(max_attempts=0)

    def test_validation_backoff_multiplier_minimum(self) -> None:
        """Test that backoff_multiplier must be at least 1.0."""
        with pytest.raises(ValueError):
            RetryConfig(backoff_multiplier=0.5)


class TestNodeDefinition:
    """Tests for NodeDefinition model."""

    def test_minimal_definition(self) -> None:
        """Test creating a minimal node definition."""
        definition = NodeDefinition(
            id="echo-v1.0.0",
            name="echo",
            version="1.0.0",
            title="Echo",
            description="Returns input unchanged",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
        )
        assert definition.id == "echo-v1.0.0"
        assert definition.name == "echo"
        assert definition.version == "1.0.0"
        assert definition.title == "Echo"
        assert definition.token_cost == 0.0
        assert definition.category == "utility"
        assert definition.timeout_seconds == 30
        assert definition.is_control_flow is False

    def test_full_definition(self) -> None:
        """Test creating a full node definition with all fields."""
        definition = NodeDefinition(
            id="segmentation-v2.0.0",
            name="segmentation",
            version="2.0.0",
            title="Point Cloud Segmentation",
            description="Segments point cloud into semantic classes",
            input_schema={
                "type": "object",
                "properties": {
                    "pointcloud_path": {"type": "string"},
                },
                "required": ["pointcloud_path"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "instances_path": {"type": "string"},
                },
            },
            token_cost=5.0,
            default_retry=RetryConfig(max_attempts=3),
            category="inference",
            timeout_seconds=300,
        )
        assert definition.token_cost == 5.0
        assert definition.default_retry.max_attempts == 3
        assert definition.category == "inference"
        assert definition.timeout_seconds == 300

    def test_to_dict(self) -> None:
        """Test converting definition to dictionary."""
        definition = NodeDefinition(
            id="echo-v1.0.0",
            name="echo",
            version="1.0.0",
            title="Echo",
            description="Returns input unchanged",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
        )
        data = definition.to_dict()
        assert isinstance(data, dict)
        assert data["id"] == "echo-v1.0.0"
        assert data["name"] == "echo"
        assert "default_retry" in data

    def test_control_flow_node(self) -> None:
        """Test creating a control flow node definition."""
        definition = NodeDefinition(
            id="if-v1.0.0",
            name="if",
            version="1.0.0",
            title="IF Condition",
            description="Conditional branching",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            category="control-flow",
            is_control_flow=True,
            token_cost=0.0,
        )
        assert definition.is_control_flow is True
        assert definition.category == "control-flow"
        assert definition.token_cost == 0.0

    def test_file_input_fields_with_binary(self) -> None:
        """Test file_input_fields returns fields with format: binary."""
        definition = NodeDefinition(
            id="upload-v1.0.0",
            name="upload",
            version="1.0.0",
            title="Upload Node",
            description="Accepts file uploads",
            input_schema={
                "type": "object",
                "properties": {
                    "point_cloud": {"type": "string", "format": "binary", "description": "Point cloud file"},
                    "threshold": {"type": "number", "default": 0.5},
                    "mask": {"type": "string", "format": "binary"},
                },
            },
            output_schema={"type": "object"},
        )
        assert sorted(definition.file_input_fields) == ["mask", "point_cloud"]

    def test_file_input_fields_no_binary(self) -> None:
        """Test file_input_fields returns empty list when no binary fields."""
        definition = NodeDefinition(
            id="echo-v1.0.0",
            name="echo",
            version="1.0.0",
            title="Echo",
            description="No file inputs",
            input_schema={
                "type": "object",
                "properties": {
                    "message": {"type": "string"},
                    "count": {"type": "integer"},
                },
            },
            output_schema={"type": "object"},
        )
        assert definition.file_input_fields == []

    def test_file_input_fields_empty_schema(self) -> None:
        """Test file_input_fields with schema that has no properties."""
        definition = NodeDefinition(
            id="empty-v1.0.0",
            name="empty",
            version="1.0.0",
            title="Empty",
            description="No properties",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
        )
        assert definition.file_input_fields == []

    def test_has_file_inputs_true(self) -> None:
        """Test has_file_inputs returns True when binary fields exist."""
        definition = NodeDefinition(
            id="upload-v1.0.0",
            name="upload",
            version="1.0.0",
            title="Upload Node",
            description="Accepts file uploads",
            input_schema={
                "type": "object",
                "properties": {
                    "file": {"type": "string", "format": "binary"},
                },
            },
            output_schema={"type": "object"},
        )
        assert definition.has_file_inputs is True

    def test_has_file_inputs_false(self) -> None:
        """Test has_file_inputs returns False when no binary fields."""
        definition = NodeDefinition(
            id="echo-v1.0.0",
            name="echo",
            version="1.0.0",
            title="Echo",
            description="No file inputs",
            input_schema={
                "type": "object",
                "properties": {"message": {"type": "string"}},
            },
            output_schema={"type": "object"},
        )
        assert definition.has_file_inputs is False

    def test_file_output_fields_with_binary(self) -> None:
        """Test file_output_fields returns fields with format: binary in output_schema."""
        definition = NodeDefinition(
            id="segmentation-v1.0.0",
            name="segmentation",
            version="1.0.0",
            title="Segmentation",
            description="Produces binary output files",
            input_schema={"type": "object"},
            output_schema={
                "type": "object",
                "properties": {
                    "result_path": {"type": "string", "format": "binary"},
                    "summary": {"type": "string"},
                    "mask_path": {"type": "string", "format": "binary"},
                },
            },
        )
        assert sorted(definition.file_output_fields) == ["mask_path", "result_path"]

    def test_file_output_fields_no_binary(self) -> None:
        """Test file_output_fields returns empty list when no binary output fields."""
        definition = NodeDefinition(
            id="echo-v1.0.0",
            name="echo",
            version="1.0.0",
            title="Echo",
            description="No binary outputs",
            input_schema={"type": "object"},
            output_schema={
                "type": "object",
                "properties": {
                    "message": {"type": "string"},
                    "count": {"type": "integer"},
                },
            },
        )
        assert definition.file_output_fields == []

    def test_file_output_fields_empty_schema(self) -> None:
        """Test file_output_fields with output_schema that has no properties."""
        definition = NodeDefinition(
            id="empty-v1.0.0",
            name="empty",
            version="1.0.0",
            title="Empty",
            description="No properties in output",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
        )
        assert definition.file_output_fields == []


class TestExportDefinition:
    """Tests for export_definition function (Phase 3)."""

    def test_export_definition_creates_registry_compatible_json(self) -> None:
        """Test that export_definition creates registry-compatible JSON."""
        definition = NodeDefinition(
            id="test-v1.0.0",
            name="test",
            version="1.0.0",
            title="Test Node",
            description="A test node",
            input_schema={
                "type": "object",
                "properties": {"input": {"type": "string"}},
            },
            output_schema={
                "type": "object",
                "properties": {"output": {"type": "string"}},
            },
            category="utility",
            timeout_seconds=60,
            token_cost=5.0,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.json"
            result_path = export_definition(definition, output_path)

            assert result_path == output_path
            assert output_path.exists()

            data = json.loads(output_path.read_text())
            assert data["name"] == "test"
            assert data["version"] == "1.0.0"
            assert data["label"] == "Test Node"
            assert data["description"] == "A test node"
            assert data["category"] == "utility"
            assert data["input_schema"] == definition.input_schema
            assert data["output_schema"] == definition.output_schema
            assert data["invoke_type"] == "http"
            assert data["invoke_url"] is None
            assert data["token_cost"] == 5.0
            assert data["timeout_seconds"] == 60

    def test_export_definition_maps_title_to_label(self) -> None:
        """Test that title field is mapped to label."""
        definition = NodeDefinition(
            id="test-v1.0.0",
            name="test",
            version="1.0.0",
            title="My Test Node",
            description="Test",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.json"
            export_definition(definition, output_path)

            data = json.loads(output_path.read_text())
            assert "label" in data
            assert data["label"] == "My Test Node"
            assert "title" not in data

    def test_export_definition_maps_default_retry_to_retry(self) -> None:
        """Test that default_retry field is mapped to retry."""
        retry_config = RetryConfig(
            max_attempts=3,
            initial_delay_ms=500,
            backoff_multiplier=1.5,
            max_delay_ms=10000,
        )
        definition = NodeDefinition(
            id="test-v1.0.0",
            name="test",
            version="1.0.0",
            title="Test",
            description="Test",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            default_retry=retry_config,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.json"
            export_definition(definition, output_path)

            data = json.loads(output_path.read_text())
            assert "retry" in data
            assert data["retry"]["max_attempts"] == 3
            assert data["retry"]["initial_delay_ms"] == 500
            assert data["retry"]["backoff_multiplier"] == 1.5
            assert data["retry"]["max_delay_ms"] == 10000

    def test_export_definition_includes_all_required_fields(self) -> None:
        """Test that export_definition includes all required fields."""
        definition = NodeDefinition(
            id="test-v1.0.0",
            name="test",
            version="1.0.0",
            title="Test",
            description="Test",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.json"
            export_definition(definition, output_path)

            data = json.loads(output_path.read_text())
            required_fields = [
                "name",
                "version",
                "label",
                "description",
                "category",
                "input_schema",
                "output_schema",
                "invoke_type",
                "invoke_url",
                "token_cost",
                "timeout_seconds",
                "retry",
                "tags",
                "styles",
            ]
            for field in required_fields:
                assert field in data, f"Missing required field: {field}"

    def test_export_definition_with_custom_invoke_type(self) -> None:
        """Test that custom invoke_type is included."""
        definition = NodeDefinition(
            id="test-v1.0.0",
            name="test",
            version="1.0.0",
            title="Test",
            description="Test",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.json"
            export_definition(definition, output_path, invoke_type="lambda")

            data = json.loads(output_path.read_text())
            assert data["invoke_type"] == "lambda"

    def test_export_definition_with_invoke_url(self) -> None:
        """Test that invoke_url is included when provided."""
        definition = NodeDefinition(
            id="test-v1.0.0",
            name="test",
            version="1.0.0",
            title="Test",
            description="Test",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.json"
            export_definition(definition, output_path, invoke_url="https://node.example.com")

            data = json.loads(output_path.read_text())
            assert data["invoke_url"] == "https://node.example.com"

    def test_export_definition_with_custom_tags(self) -> None:
        """Test that custom tags are included."""
        definition = NodeDefinition(
            id="test-v1.0.0",
            name="test",
            version="1.0.0",
            title="Test",
            description="Test",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
        )

        tags = ["machine-learning", "segmentation", "point-cloud"]
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.json"
            export_definition(definition, output_path, tags=tags)

            data = json.loads(output_path.read_text())
            assert data["tags"] == tags

    def test_export_definition_with_custom_styles(self) -> None:
        """Test that custom styles override definition.styles."""
        definition = NodeDefinition(
            id="test-v1.0.0",
            name="test",
            version="1.0.0",
            title="Test",
            description="Test",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
        )

        custom_styles = {"icon": "Brain", "color": "emerald"}
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.json"
            export_definition(definition, output_path, styles=custom_styles)

            data = json.loads(output_path.read_text())
            assert data["styles"] == custom_styles

    def test_export_definition_uses_definition_styles_when_not_overridden(self) -> None:
        """Test that definition.styles is used when not overridden."""
        from canvastekk_workflow_sdk.definition import NodeStyles

        styles = NodeStyles(icon="Box", color="blue")
        definition = NodeDefinition(
            id="test-v1.0.0",
            name="test",
            version="1.0.0",
            title="Test",
            description="Test",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            styles=styles,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.json"
            export_definition(definition, output_path)

            data = json.loads(output_path.read_text())
            assert data["styles"] == {"icon": "Box", "color": "blue"}

    def test_export_definition_with_constraints(self) -> None:
        """Test that constraints are included when provided."""
        definition = NodeDefinition(
            id="test-v1.0.0",
            name="test",
            version="1.0.0",
            title="Test",
            description="Test",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
        )

        constraints = {"gpu_required": True, "memory_gb": 8}
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.json"
            export_definition(definition, output_path, constraints=constraints)

            data = json.loads(output_path.read_text())
            assert data["constraints"] == constraints

    def test_export_definition_with_node_status(self) -> None:
        """Test that node_status is included."""
        definition = NodeDefinition(
            id="test-v1.0.0",
            name="test",
            version="1.0.0",
            title="Test",
            description="Test",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.json"
            export_definition(definition, output_path, node_status="inactive")

            data = json.loads(output_path.read_text())
            assert data["node_status"] == "inactive"

    def test_export_definition_creates_parent_directories(self) -> None:
        """Test that export_definition creates parent directories."""
        definition = NodeDefinition(
            id="test-v1.0.0",
            name="test",
            version="1.0.0",
            title="Test",
            description="Test",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "nested" / "dir" / "test.json"
            export_definition(definition, output_path)

            assert output_path.exists()
            data = json.loads(output_path.read_text())
            assert data["name"] == "test"

    def test_export_definition_writes_formatted_json(self) -> None:
        """Test that export_definition writes formatted JSON with newlines."""
        definition = NodeDefinition(
            id="test-v1.0.0",
            name="test",
            version="1.0.0",
            title="Test",
            description="Test",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.json"
            export_definition(definition, output_path)

            content = output_path.read_text()
            assert content.endswith("\n")
            assert "\n" in content
