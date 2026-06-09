"""Tests for WorkflowNodeManifest and RetryConfig models."""

import json
import tempfile
from pathlib import Path

import pytest

from canvastekk_workflow_sdk import NodeRole, NodeStyles, RetryConfig, WorkflowNodeManifest
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


class TestNodeRole:
    """Tests for NodeRole enum."""

    def test_enum_values(self) -> None:
        assert NodeRole.START.value == "start"
        assert NodeRole.END.value == "end"
        assert NodeRole.ERROR_GATE.value == "error_gate"
        assert NodeRole.OPERATION.value == "operation"

    def test_default_role_is_operation(self) -> None:
        definition = WorkflowNodeManifest(
            name="echo",
            version="1.0.0",
            title="Echo",
            description="Test",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
        )
        assert definition.role == NodeRole.OPERATION

    def test_explicit_role(self) -> None:
        definition = WorkflowNodeManifest(
            name="start",
            version="1.0.0",
            title="Start",
            description="Test",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            role=NodeRole.START,
        )
        assert definition.role == NodeRole.START


class TestWorkflowNodeManifest:
    """Tests for WorkflowNodeManifest model."""

    def test_minimal_definition(self) -> None:
        """Test creating a minimal node definition."""
        definition = WorkflowNodeManifest(
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
        assert definition.role == NodeRole.OPERATION

    def test_full_definition(self) -> None:
        """Test creating a full node definition with all fields."""
        definition = WorkflowNodeManifest(
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
        definition = WorkflowNodeManifest(
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
        """Test creating a node with explicit role."""
        definition = WorkflowNodeManifest(
            name="if",
            version="1.0.0",
            title="IF Condition",
            description="Conditional branching",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            category="control-flow",
            role=NodeRole.START,
            token_cost=0.0,
        )
        assert definition.role == NodeRole.START
        assert definition.category == "control-flow"
        assert definition.token_cost == 0.0

    def test_file_input_fields_with_file(self) -> None:
        """Test file_input_fields returns fields with format: file."""
        definition = WorkflowNodeManifest(
            name="upload",
            version="1.0.0",
            title="Upload Node",
            description="Accepts file uploads",
            input_schema={
                "type": "object",
                "properties": {
                    "point_cloud": {"type": "string", "format": "file", "description": "Point cloud file"},
                    "threshold": {"type": "number", "default": 0.5},
                    "mask": {"type": "string", "format": "file"},
                },
            },
            output_schema={"type": "object"},
        )
        assert sorted(definition.file_input_fields) == ["mask", "point_cloud"]

    def test_file_input_fields_no_file(self) -> None:
        """Test file_input_fields returns empty list when no file fields."""
        definition = WorkflowNodeManifest(
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
        definition = WorkflowNodeManifest(
            name="empty",
            version="1.0.0",
            title="Empty",
            description="No properties",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
        )
        assert definition.file_input_fields == []

    def test_has_file_inputs_true(self) -> None:
        """Test has_file_inputs returns True when file fields exist."""
        definition = WorkflowNodeManifest(
            name="upload",
            version="1.0.0",
            title="Upload Node",
            description="Accepts file uploads",
            input_schema={
                "type": "object",
                "properties": {
                    "file": {"type": "string", "format": "file"},
                },
            },
            output_schema={"type": "object"},
        )
        assert definition.has_file_inputs is True

    def test_has_file_inputs_false(self) -> None:
        """Test has_file_inputs returns False when no file fields."""
        definition = WorkflowNodeManifest(
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

    def test_file_output_fields_with_file(self) -> None:
        """Test file_output_fields returns fields with format: file in output_schema."""
        definition = WorkflowNodeManifest(
            name="segmentation",
            version="1.0.0",
            title="Segmentation",
            description="Produces file output",
            input_schema={"type": "object"},
            output_schema={
                "type": "object",
                "properties": {
                    "result_path": {"type": "string", "format": "file"},
                    "summary": {"type": "string"},
                    "mask_path": {"type": "string", "format": "file"},
                },
            },
        )
        assert sorted(definition.file_output_fields) == ["mask_path", "result_path"]

    def test_file_output_fields_no_file(self) -> None:
        """Test file_output_fields returns empty list when no file output fields."""
        definition = WorkflowNodeManifest(
            name="echo",
            version="1.0.0",
            title="Echo",
            description="No file outputs",
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
        definition = WorkflowNodeManifest(
            name="empty",
            version="1.0.0",
            title="Empty",
            description="No properties in output",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
        )
        assert definition.file_output_fields == []

    def test_file_input_fields_does_not_detect_binary(self) -> None:
        """Test that file_input_fields does NOT detect format: binary (breaking change)."""
        with pytest.raises(ValueError, match="format 'binary'"):
            WorkflowNodeManifest(
                name="old",
                version="1.0.0",
                title="Old",
                description="Uses old binary format",
                input_schema={
                    "type": "object",
                    "properties": {
                        "file": {"type": "string", "format": "binary"},
                    },
                },
                output_schema={"type": "object"},
            )

    def test_model_validator_rejects_binary_format(self) -> None:
        """Test that WorkflowNodeManifest rejects format: binary at definition time."""
        with pytest.raises(ValueError, match="no longer supported"):
            WorkflowNodeManifest(
                name="bad",
                version="1.0.0",
                title="Bad",
                description="Uses binary",
                input_schema={
                    "type": "object",
                    "properties": {
                        "x": {"type": "string", "format": "binary"},
                    },
                },
                output_schema={"type": "object"},
            )

    def test_model_validator_rejects_file_with_wrong_type(self) -> None:
        """Test that WorkflowNodeManifest rejects format: file with non-string type."""
        with pytest.raises(ValueError, match="must have type 'string'"):
            WorkflowNodeManifest(
                name="bad",
                version="1.0.0",
                title="Bad",
                description="Wrong type",
                input_schema={
                    "type": "object",
                    "properties": {
                        "x": {"type": "object", "format": "file"},
                    },
                },
                output_schema={"type": "object"},
            )

    def test_to_dict_contains_file_format(self) -> None:
        """Test that to_dict() preserves format: file in schemas."""
        definition = WorkflowNodeManifest(
            name="echo",
            version="1.0.0",
            title="Echo",
            description="Test",
            input_schema={
                "type": "object",
                "properties": {
                    "file": {"type": "string", "format": "file"},
                },
            },
            output_schema={
                "type": "object",
                "properties": {
                    "result": {"type": "string", "format": "file"},
                },
            },
        )
        data = definition.to_dict()
        assert data["input_schema"]["properties"]["file"]["format"] == "file"
        assert data["output_schema"]["properties"]["result"]["format"] == "file"


class TestExportDefinition:
    """Tests for export_definition function (Phase 3)."""

    def test_export_definition_creates_registry_compatible_json(self) -> None:
        """Test that export_definition creates registry-compatible JSON."""
        definition = WorkflowNodeManifest(
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
            assert "invoke_url" not in data
            assert data["token_cost"] == 5.0
            assert data["timeout_seconds"] == 60

    def test_export_definition_maps_title_to_label(self) -> None:
        """Test that title field is mapped to label."""
        definition = WorkflowNodeManifest(
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
        definition = WorkflowNodeManifest(
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
        definition = WorkflowNodeManifest(
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
        definition = WorkflowNodeManifest(
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
        definition = WorkflowNodeManifest(
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
        definition = WorkflowNodeManifest(
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
        definition = WorkflowNodeManifest(
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
        styles = NodeStyles(icon="Box", color="blue")
        definition = WorkflowNodeManifest(
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
        definition = WorkflowNodeManifest(
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
        definition = WorkflowNodeManifest(
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
        definition = WorkflowNodeManifest(
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
        definition = WorkflowNodeManifest(
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


class TestValidateFileInput:
    """Tests for WorkflowNodeManifest.validate_file_input()."""

    def _make_definition(self, **schema_overrides):
        props = {
            "file": {
                "type": "string",
                "format": "file",
                "x-accept": [".txt", ".csv"],
                "x-maxSizeBytes": 1000,
            },
        }
        props.update(schema_overrides)
        return WorkflowNodeManifest(
            name="test",
            version="1.0.0",
            title="Test",
            description="Test",
            input_schema={"type": "object", "properties": props},
            output_schema={"type": "object"},
        )

    def test_valid_file_passes(self, tmp_path) -> None:
        definition = self._make_definition()
        f = tmp_path / "data.txt"
        f.write_text("hello")
        definition.validate_file_input("file", f)

    def test_rejects_wrong_extension(self, tmp_path) -> None:
        definition = self._make_definition()
        f = tmp_path / "data.json"
        f.write_text("{}")
        with pytest.raises(Exception, match="not allowed"):
            definition.validate_file_input("file", f)

    def test_rejects_oversized_file(self, tmp_path) -> None:
        definition = self._make_definition()
        f = tmp_path / "data.txt"
        f.write_bytes(b"x" * 2000)
        with pytest.raises(Exception, match="exceeds maximum"):
            definition.validate_file_input("file", f)

    def test_passes_when_no_extensions_defined(self, tmp_path) -> None:
        props = {
            "file": {
                "type": "string",
                "format": "file",
            },
        }
        definition = WorkflowNodeManifest(
            name="test",
            version="1.0.0",
            title="Test",
            description="Test",
            input_schema={"type": "object", "properties": props},
            output_schema={"type": "object"},
        )
        f = tmp_path / "data.xyz"
        f.write_text("anything")
        definition.validate_file_input("file", f)


class TestSlugValidation:
    def test_valid_slugs(self) -> None:
        for slug in ["echo", "file-loader", "point-cloud-segment", "a1"]:
            WorkflowNodeManifest(
                name=slug,
                version="1.0.0",
                title="Test",
                description="Test",
                input_schema={"type": "object"},
                output_schema={"type": "object"},
            )

    def test_single_char_slug(self) -> None:
        WorkflowNodeManifest(
            name="a",
            version="1.0.0",
            title="Test",
            description="Test",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
        )

    def test_rejects_uppercase(self) -> None:
        with pytest.raises(ValueError, match="lowercase slug"):
            WorkflowNodeManifest(
                name="Echo",
                version="1.0.0",
                title="Test",
                description="Test",
                input_schema={"type": "object"},
                output_schema={"type": "object"},
            )

    def test_rejects_spaces(self) -> None:
        with pytest.raises(ValueError, match="lowercase slug"):
            WorkflowNodeManifest(
                name="has space",
                version="1.0.0",
                title="Test",
                description="Test",
                input_schema={"type": "object"},
                output_schema={"type": "object"},
            )

    def test_rejects_underscores(self) -> None:
        with pytest.raises(ValueError, match="lowercase slug"):
            WorkflowNodeManifest(
                name="under_score",
                version="1.0.0",
                title="Test",
                description="Test",
                input_schema={"type": "object"},
                output_schema={"type": "object"},
            )

    def test_rejects_leading_hyphen(self) -> None:
        with pytest.raises(ValueError, match="lowercase slug"):
            WorkflowNodeManifest(
                name="-leading",
                version="1.0.0",
                title="Test",
                description="Test",
                input_schema={"type": "object"},
                output_schema={"type": "object"},
            )

    def test_rejects_trailing_hyphen(self) -> None:
        with pytest.raises(ValueError, match="lowercase slug"):
            WorkflowNodeManifest(
                name="trailing-",
                version="1.0.0",
                title="Test",
                description="Test",
                input_schema={"type": "object"},
                output_schema={"type": "object"},
            )

    def test_rejects_numeric_start(self) -> None:
        with pytest.raises(ValueError, match="lowercase slug"):
            WorkflowNodeManifest(
                name="1numeric",
                version="1.0.0",
                title="Test",
                description="Test",
                input_schema={"type": "object"},
                output_schema={"type": "object"},
            )


class TestSemverValidation:
    def test_valid_versions(self) -> None:
        for v in ["1.0.0", "0.1.0", "10.20.30"]:
            WorkflowNodeManifest(
                name="test",
                version=v,
                title="Test",
                description="Test",
                input_schema={"type": "object"},
                output_schema={"type": "object"},
            )

    def test_rejects_two_part(self) -> None:
        with pytest.raises(ValueError, match="semantic version"):
            WorkflowNodeManifest(
                name="test",
                version="1.0",
                title="Test",
                description="Test",
                input_schema={"type": "object"},
                output_schema={"type": "object"},
            )

    def test_rejects_v_prefix(self) -> None:
        with pytest.raises(ValueError, match="semantic version"):
            WorkflowNodeManifest(
                name="test",
                version="v1.0.0",
                title="Test",
                description="Test",
                input_schema={"type": "object"},
                output_schema={"type": "object"},
            )

    def test_rejects_prerelease(self) -> None:
        with pytest.raises(ValueError, match="semantic version"):
            WorkflowNodeManifest(
                name="test",
                version="1.0.0-alpha",
                title="Test",
                description="Test",
                input_schema={"type": "object"},
                output_schema={"type": "object"},
            )

    def test_rejects_non_numeric(self) -> None:
        with pytest.raises(ValueError, match="semantic version"):
            WorkflowNodeManifest(
                name="test",
                version="abc",
                title="Test",
                description="Test",
                input_schema={"type": "object"},
                output_schema={"type": "object"},
            )

    def test_rejects_leading_zeros(self) -> None:
        with pytest.raises(ValueError, match="semantic version"):
            WorkflowNodeManifest(
                name="test",
                version="01.0.0",
                title="Test",
                description="Test",
                input_schema={"type": "object"},
                output_schema={"type": "object"},
            )


class TestIdAutoDerivation:
    def test_id_auto_derived(self) -> None:
        definition = WorkflowNodeManifest(
            name="echo",
            version="1.0.0",
            title="Echo",
            description="Test",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
        )
        assert definition.id == "echo-v1.0.0"

    def test_id_in_to_dict(self) -> None:
        definition = WorkflowNodeManifest(
            name="echo",
            version="1.2.0",
            title="Echo",
            description="Test",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
        )
        assert definition.to_dict()["id"] == "echo-v1.2.0"

    def test_manual_id_matching_warns(self) -> None:
        import warnings

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            definition = WorkflowNodeManifest(
                id="echo-v1.0.0",
                name="echo",
                version="1.0.0",
                title="Echo",
                description="Test",
                input_schema={"type": "object"},
                output_schema={"type": "object"},
            )
            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecation_warnings) >= 1
        assert definition.id == "echo-v1.0.0"

    def test_manual_id_mismatching_warns(self) -> None:
        import warnings

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            definition = WorkflowNodeManifest(
                id="wrong-v1.0.0",
                name="echo",
                version="1.0.0",
                title="Echo",
                description="Test",
                input_schema={"type": "object"},
                output_schema={"type": "object"},
            )
            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecation_warnings) >= 1
        assert definition.id == "echo-v1.0.0"


class TestExportDefinitionNoId:
    def test_export_does_not_include_id(self) -> None:
        definition = WorkflowNodeManifest(
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
            assert "id" not in data
            assert data["name"] == "test"
            assert data["version"] == "1.0.0"


class TestBackwardCompatAliases:
    def test_node_styles_alias(self) -> None:
        from canvastekk_workflow_sdk.definition import NodeStyles, WorkflowNodeStyles

        assert NodeStyles is WorkflowNodeStyles

    def test_node_role_alias(self) -> None:
        from canvastekk_workflow_sdk.definition import NodeRole, WorkflowNodeRole

        assert NodeRole is WorkflowNodeRole

    def test_node_definition_alias(self) -> None:
        from canvastekk_workflow_sdk.definition import NodeDefinition, WorkflowNodeManifest

        assert NodeDefinition is WorkflowNodeManifest

    def test_workflow_node_definition_alias(self) -> None:
        from canvastekk_workflow_sdk.definition import WorkflowNodeDefinition, WorkflowNodeManifest

        assert WorkflowNodeDefinition is WorkflowNodeManifest

    def test_workflow_node_styles_importable_from_top_level(self) -> None:
        from canvastekk_workflow_sdk import WorkflowNodeStyles

        styles = WorkflowNodeStyles(icon="Brain", color="emerald")
        assert styles.icon == "Brain"

    def test_workflow_node_role_importable_from_top_level(self) -> None:
        from canvastekk_workflow_sdk import WorkflowNodeRole

        assert WorkflowNodeRole.OPERATION.value == "operation"

    def test_workflow_node_styles_primary_name(self) -> None:
        from canvastekk_workflow_sdk.definition import WorkflowNodeStyles

        styles = WorkflowNodeStyles(icon="Test", color="blue")
        assert styles.icon == "Test"
        assert styles.color == "blue"

    def test_workflow_node_role_primary_name(self) -> None:
        from canvastekk_workflow_sdk.definition import WorkflowNodeRole

        assert WorkflowNodeRole.START.value == "start"
        assert WorkflowNodeRole.END.value == "end"
        assert WorkflowNodeRole.ERROR_GATE.value == "error_gate"
        assert WorkflowNodeRole.OPERATION.value == "operation"
