"""CLI tools for canvastekk-workflow-sdk.

Usage:
    python -m canvastekk_workflow_sdk validate <module_path> [--json]
"""

from __future__ import annotations

import importlib
import json
import sys


def _load_definition(module_path: str):
    """Load a NodeDefinition from a module:attribute path."""
    if ":" not in module_path:
        raise ValueError(f"Invalid path '{module_path}'. Use 'module:attribute' format (e.g., 'handler:definition').")

    module_name, attr_name = module_path.rsplit(":", 1)
    module = importlib.import_module(module_name)
    definition = getattr(module, attr_name)

    from canvastekk_workflow_sdk.definition import NodeDefinition

    if not isinstance(definition, NodeDefinition):
        raise TypeError(f"Expected NodeDefinition, got {type(definition).__name__}")

    return definition


def _validate_definition(definition) -> dict:
    """Validate a NodeDefinition and return a report."""
    report = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "file_input_fields": [],
        "file_output_fields": [],
    }

    # The model_validator already ran at definition time.
    # If we got here, basic format validation passed.

    for name in definition.file_input_fields:
        schema = definition.input_schema.get("properties", {}).get(name, {})
        field_report = {"name": name, "format": schema.get("format"), "type": schema.get("type")}

        extensions = {}
        if "x-accept" in schema:
            extensions["x-accept"] = schema["x-accept"]
        else:
            report["warnings"].append(f"File input field '{name}' has no x-accept extension (recommended)")

        if "x-maxSizeBytes" in schema:
            extensions["x-maxSizeBytes"] = schema["x-maxSizeBytes"]
        else:
            report["warnings"].append(f"File input field '{name}' has no x-maxSizeBytes extension (recommended)")

        field_report["extensions"] = extensions
        report["file_input_fields"].append(field_report)

    for name in definition.file_output_fields:
        schema = definition.output_schema.get("properties", {}).get(name, {})
        field_report = {"name": name, "format": schema.get("format"), "type": schema.get("type")}
        report["file_output_fields"].append(field_report)

    return report


def main() -> None:
    args = sys.argv[1:]

    if not args or args[0] == "--help":
        print("Usage: python -m canvastekk_workflow_sdk validate <module:attribute> [--json]")
        print()
        print("Commands:")
        print("  validate    Validate a node manifest definition")
        print()
        print("Options:")
        print("  --json      Output validation results as JSON")
        print("  --version   Show SDK version")
        print("  --help      Show this help message")
        sys.exit(0)

    if args[0] == "--version":
        from canvastekk_workflow_sdk import __version__

        print(f"canvastekk-workflow-sdk {__version__}")
        sys.exit(0)

    if args[0] != "validate":
        print(f"Unknown command: {args[0]}", file=sys.stderr)
        sys.exit(1)

    if len(args) < 2 or args[1].startswith("--"):
        print("Error: module path required (e.g., handler:definition)", file=sys.stderr)
        sys.exit(1)

    module_path = args[1]
    use_json = "--json" in args

    try:
        definition = _load_definition(module_path)
    except Exception as e:
        if use_json:
            print(json.dumps({"valid": False, "errors": [str(e)], "warnings": []}, indent=2))
        else:
            print(f"Error loading definition: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        report = _validate_definition(definition)
    except Exception as e:
        report = {"valid": False, "errors": [str(e)], "warnings": []}

    if use_json:
        print(json.dumps(report, indent=2))
    else:
        if report["valid"]:
            print("PASS: Manifest is valid")
        else:
            print("FAIL: Manifest has errors")

        for error in report.get("errors", []):
            print(f"  ERROR: {error}")

        for warning in report.get("warnings", []):
            print(f"  WARN: {warning}")

        if report["file_input_fields"]:
            print(f"  File inputs: {[f['name'] for f in report['file_input_fields']]}")
        if report["file_output_fields"]:
            print(f"  File outputs: {[f['name'] for f in report['file_output_fields']]}")

    sys.exit(0 if report["valid"] else 1)


if __name__ == "__main__":
    main()
