"""Tests for canvastekk-workflow-sdk CLI.

Uses subprocess.run to invoke the CLI since it calls sys.exit().

IMPORTANT: Do NOT import canvastekk_workflow_sdk modules directly in the test
module scope — the model_validator will reject format:"binary". Only use
subprocess.run.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

PYTHON_BIN = Path(sys.executable)


def test_validate_valid_definition():
    """Test validating a valid NodeDefinition."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a temporary Python file with a valid NodeDefinition
        test_file = Path(tmpdir) / "test_node.py"
        test_file.write_text("""
from canvastekk_workflow_sdk import NodeDefinition

definition = NodeDefinition(
    id="test-node-v1.0.0",
    name="test-node",
    version="1.0.0",
    title="Test Node",
    description="A test node",
    input_schema={"type": "object", "properties": {"input": {"type": "string"}}},
    output_schema={"type": "object", "properties": {"output": {"type": "string"}}},
)
""")

        # Run the CLI validate command
        result = subprocess.run(
            [str(PYTHON_BIN), "-m", "canvastekk_workflow_sdk", "validate", "test_node:definition"],
            cwd=tmpdir,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Expected exit 0, got {result.returncode}. stdout: {result.stdout}, stderr: {result.stderr}"
        assert "PASS: Manifest is valid" in result.stdout


def test_validate_with_json_flag():
    """Test validating with --json flag returns valid JSON with valid: true."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a temporary Python file with a valid NodeDefinition
        test_file = Path(tmpdir) / "test_node.py"
        test_file.write_text("""
from canvastekk_workflow_sdk import NodeDefinition

definition = NodeDefinition(
    id="test-node-v1.0.0",
    name="test-node",
    version="1.0.0",
    title="Test Node",
    description="A test node",
    input_schema={"type": "object", "properties": {"input": {"type": "string"}}},
    output_schema={"type": "object", "properties": {"output": {"type": "string"}}},
)
""")

        # Run the CLI validate command with --json flag
        result = subprocess.run(
            [str(PYTHON_BIN), "-m", "canvastekk_workflow_sdk", "validate", "test_node:definition", "--json"],
            cwd=tmpdir,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Expected exit 0, got {result.returncode}. stdout: {result.stdout}, stderr: {result.stderr}"

        # Parse the JSON output
        output = json.loads(result.stdout)
        assert output["valid"] is True, f"Expected valid: true, got {output}"


def test_validate_invalid_path_format():
    """Test validating with invalid path format (missing colon) fails with exit 1."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a temporary Python file with a valid NodeDefinition
        test_file = Path(tmpdir) / "test_node.py"
        test_file.write_text("""
from canvastekk_workflow_sdk import NodeDefinition

definition = NodeDefinition(
    id="test-node-v1.0.0",
    name="test-node",
    version="1.0.0",
    title="Test Node",
    description="A test node",
    input_schema={"type": "object", "properties": {"input": {"type": "string"}}},
    output_schema={"type": "object", "properties": {"output": {"type": "string"}}},
)
""")

        # Run the CLI validate command with invalid path (missing colon)
        result = subprocess.run(
            [str(PYTHON_BIN), "-m", "canvastekk_workflow_sdk", "validate", "test_node-definition"],
            cwd=tmpdir,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 1, f"Expected exit 1, got {result.returncode}. stdout: {result.stdout}, stderr: {result.stderr}"
        assert "Invalid path" in result.stderr or "Invalid path" in result.stdout


def test_validate_unknown_command():
    """Test unknown command fails with exit 1."""
    result = subprocess.run(
        [str(PYTHON_BIN), "-m", "canvastekk_workflow_sdk", "foo"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1, f"Expected exit 1, got {result.returncode}. stdout: {result.stdout}, stderr: {result.stderr}"
    assert "Unknown command" in result.stderr


def test_validate_missing_module_path():
    """Test validate command without module path fails with exit 1."""
    result = subprocess.run(
        [str(PYTHON_BIN), "-m", "canvastekk_workflow_sdk", "validate"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1, f"Expected exit 1, got {result.returncode}. stdout: {result.stdout}, stderr: {result.stderr}"
    assert "module path required" in result.stderr


def test_version_flag():
    """Test --version flag shows SDK version."""
    result = subprocess.run(
        [str(PYTHON_BIN), "-m", "canvastekk_workflow_sdk", "--version"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, f"Expected exit 0, got {result.returncode}. stdout: {result.stdout}, stderr: {result.stderr}"
    assert "canvastekk-workflow-sdk" in result.stdout
    # Version should be present
    assert "0.6.0" in result.stdout


def test_help_flag():
    """Test --help flag shows usage and exits with 0."""
    result = subprocess.run(
        [str(PYTHON_BIN), "-m", "canvastekk_workflow_sdk", "--help"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, f"Expected exit 0, got {result.returncode}. stdout: {result.stdout}, stderr: {result.stderr}"
    assert "Usage:" in result.stdout
    assert "validate" in result.stdout
    assert "--json" in result.stdout
    assert "--version" in result.stdout
    assert "--help" in result.stdout
