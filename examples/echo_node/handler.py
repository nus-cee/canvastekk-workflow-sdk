"""
Echo Node — minimal example of file I/O with the CanvasTEKK Workflow SDK.

Demonstrates:
  - File input/output with format: "file" and x-* extensions
  - Downloading from presigned URLs with httpx
  - Runtime validation with validate_file_input()
  - Writing output files via context.output_path()
  - CLI manifest validation: python -m canvastekk_workflow_sdk validate handler:definition
"""

from pathlib import Path

import httpx
from canvastekk_workflow_sdk import BaseNode, ExecutionContext, NodeDefinition

definition = NodeDefinition(
    name="echo",
    version="1.0.0",  # semantic version — engine enforces immutability; bump for schema changes
    title="Echo",
    description="Receives a file, validates it, and writes it to output",
    input_schema={
        "type": "object",
        "properties": {
            "input_file": {
                "type": "string",
                "format": "file",
                "description": "Input file to echo",
                "x-accept": [".txt", ".csv", ".json"],
                "x-maxSizeBytes": 10485760,
            },
        },
        "required": ["input_file"],
    },
    output_schema={
        "type": "object",
        "properties": {
            "output_file": {
                "type": "string",
                "format": "file",
                "description": "Echoed output file",
            },
        },
    },
    category="utility",
    timeout_seconds=60,
)


class EchoNode(BaseNode):
    definition = definition

    def execute(self, inputs: dict, context: ExecutionContext) -> dict:
        url = inputs["input_file"]
        context.report_progress(0.1, "Downloading input file")

        suffix = Path(url.split("?")[0]).suffix or ".txt"
        local_path = context.output_dir / f"input_download{suffix}"
        self._download(url, local_path)

        context.report_progress(0.5, "Validating input file")
        definition.validate_file_input("input_file", local_path)

        context.report_progress(0.7, "Writing output")
        output_path = context.output_path("echo_output.txt")
        output_path.write_bytes(local_path.read_bytes())

        context.report_progress(1.0, "Done")
        return {"output_file": str(output_path)}

    @staticmethod
    def _download(url: str, dest: Path) -> None:
        with httpx.stream("GET", url, timeout=30.0, follow_redirects=True) as resp:
            resp.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in resp.iter_bytes(chunk_size=65536):
                    f.write(chunk)


app = EchoNode().create_app()
