"""CLI tools for canvastekk-workflow-sdk.

Usage:
    python -m canvastekk_workflow_sdk validate <module_path> [--json]
    python -m canvastekk_workflow_sdk init [--agents-md] [--force]
"""

from __future__ import annotations

import importlib
import json
import shutil
import sys
from importlib.resources import as_file
from importlib.resources import files as pkg_files
from pathlib import Path


def _load_definition(module_path: str):
    """Load a WorkflowNodeManifest from a module:attribute path."""
    if ":" not in module_path:
        raise ValueError(f"Invalid path '{module_path}'. Use 'module:attribute' format (e.g., 'handler:definition').")

    module_name, attr_name = module_path.rsplit(":", 1)
    module = importlib.import_module(module_name)
    definition = getattr(module, attr_name)

    from canvastekk_workflow_sdk.definition import WorkflowNodeManifest

    if not isinstance(definition, WorkflowNodeManifest):
        raise TypeError(f"Expected WorkflowNodeManifest, got {type(definition).__name__}")

    return definition


def _validate_definition(definition) -> dict:
    """Inspect a validated WorkflowNodeManifest and return a diagnostic report.

    The Pydantic ``model_validator`` has already checked format/type
    constraints.  This function inspects file fields for recommended
    ``x-*`` extensions and builds a human-readable report.

    Args:
        definition: A fully-validated :class:`WorkflowNodeManifest` instance.

    Returns:
        A dict with keys ``valid``, ``errors``, ``warnings``,
        ``file_input_fields``, and ``file_output_fields``.
    """
    report = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "file_input_fields": [],
        "file_output_fields": [],
        "name": definition.name,
        "version": definition.version,
        "id": definition.id,
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


_CONTENT_MARKER = "CanvasTEKK Node Development"


def _read_data_file(relative_path: str) -> str:
    """Read a bundled data file from the installed package.

    Uses ``importlib.resources.as_file()`` to handle both directory-installed
    and zipped wheels correctly.

    Args:
        relative_path: Path relative to ``canvastekk_workflow_sdk/data/``.
    """
    try:
        ref = pkg_files("canvastekk_workflow_sdk.data").joinpath(relative_path)
    except ModuleNotFoundError:
        print("Error: SDK data package not found — reinstall canvastekk-workflow-sdk", file=sys.stderr)
        sys.exit(1)
    with as_file(ref) as real_path:
        return real_path.read_text(encoding="utf-8")


def _get_bundled_skills_dir():
    """Return a Traversable for the bundled skills directory."""
    try:
        return pkg_files("canvastekk_workflow_sdk.data").joinpath("skills")
    except ModuleNotFoundError:
        print("Error: SDK data package not found — reinstall canvastekk-workflow-sdk", file=sys.stderr)
        sys.exit(1)


def _init_skills(target_dir: Path, *, include_agents_md: bool = False, force: bool = False) -> None:
    """Copy bundled skill files into *target_dir*/.opencode/skills/.

    Args:
        target_dir: Project root where .opencode/ will be created.
        include_agents_md: Also write AGENTS.md in *target_dir*.
        force: Overwrite existing files without prompting.
    """
    with as_file(_get_bundled_skills_dir()) as skills_src:
        if not skills_src.is_dir():
            print("Error: bundled skills not found in package", file=sys.stderr)
            sys.exit(1)

        skills_dest = target_dir / ".opencode" / "skills"
        created: list[str] = []
        skipped: list[str] = []

        for skill_dir in sorted(skills_src.iterdir()):
            if not skill_dir.is_dir():
                continue
            src_file = skill_dir / "SKILL.md"
            if not src_file.exists():
                continue

            skill_name = skill_dir.name
            if ".." in skill_name or "/" in skill_name or "\\" in skill_name:
                continue

            dest_file = skills_dest / skill_name / "SKILL.md"
            resolved = dest_file.resolve()
            if not str(resolved).startswith(str(skills_dest.resolve())):
                continue

            if dest_file.exists() and not force:
                skipped.append(str(dest_file.relative_to(target_dir)))
                continue

            dest_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dest_file)
            created.append(str(dest_file.relative_to(target_dir)))

        if not created and not skipped:
            print("Warning: No bundled skills found to install.", file=sys.stderr)

        if created:
            print(f"Created {len(created)} skill(s):")
            for path in created:
                print(f"  {path}")

        if skipped:
            print(f"Skipped {len(skipped)} existing file(s) (use --force to overwrite):")
            for path in skipped:
                print(f"  {path}")

    if include_agents_md:
        _write_agents_md(target_dir, force=force)

    print()
    print("Skills are loaded on-demand by coding agents.")
    print("Your agent will discover them automatically when you ask it to create a node.")


def _write_agents_md(target_dir: Path, *, force: bool = False) -> None:
    """Write or update AGENTS.md with CanvasTEKK skill routing rules."""
    agents_md_path = target_dir / "AGENTS.md"
    template = _read_data_file("templates/AGENTS.md")

    if force and agents_md_path.exists():
        agents_md_path.write_text(template)
        print(f"Overwrote {agents_md_path.relative_to(target_dir)}")
        return

    if not agents_md_path.exists():
        agents_md_path.write_text(template)
        print(f"Created {agents_md_path.relative_to(target_dir)}")
        return

    existing = agents_md_path.read_text()
    if _CONTENT_MARKER in existing:
        print("AGENTS.md already contains CanvasTEKK routing rules")
        return

    separator = "\n\n" if not existing.endswith("\n") else "\n"
    agents_md_path.write_text(existing + separator + template)
    print(f"Updated {agents_md_path.relative_to(target_dir)}")


def _load_manifest_file(path: str) -> dict:
    """Load a manifest dictionary from a JSON file.

    Args:
        path: Path to the JSON manifest file.

    Returns:
        The parsed manifest dictionary.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the content is not a JSON object.
        json.JSONDecodeError: If the content is not valid JSON.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(path)
    data = json.loads(file_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"'{path}' does not contain a JSON object")
    return data


def _run_diff(args: list[str]) -> int:
    """Run the ``diff`` command: classify changes between two manifest files.

    Args:
        args: Positional file paths plus optional ``--json`` flag.

    Returns:
        Process exit code: 0 clean, 1 breaking change or diff error,
        2 load failure.
    """
    use_json = "--json" in args
    positional = [a for a in args if not a.startswith("--")]
    if len(positional) != 2:
        print("Error: diff requires two manifest files (old.json new.json)", file=sys.stderr)
        return 2

    old_path, new_path = positional
    try:
        old = _load_manifest_file(old_path)
        new = _load_manifest_file(new_path)
    except (OSError, ValueError, json.JSONDecodeError) as e:
        print(f"Error loading manifests: {e}", file=sys.stderr)
        return 2

    from canvastekk_workflow_sdk.diff import diff_manifests

    result = diff_manifests(old, new)

    if use_json:
        from dataclasses import asdict

        print(json.dumps(asdict(result), indent=2))
    else:
        print(f"{old_path} -> {new_path}")
        print(f"  version: {result.old_version} -> {result.new_version} (bump: {result.version_bump or 'none'})")
        for change in result.breaking_changes:
            print(f"  BREAKING: {change}")
        for change in result.non_breaking_changes:
            print(f"  ok: {change}")
        for error in result.errors:
            print(f"  ERROR: {error}")
        if result.breaking:
            print()
            print("Breaking changes require a MAJOR version bump before registering.")
            print("On uat/prod the engine reseed additionally gates MAJOR+schema-diff upgrades")
            print("behind force_upgrade (update workflow-definitions.json, then POST")
            print("/api/internal/reseed?force_upgrade=true).")

    return 1 if (result.breaking or result.errors) else 0


def main() -> None:
    """CLI entry point for ``python -m canvastekk_workflow_sdk``.

    Supports:
      ``validate <module:attribute> [--json]`` — validate a node manifest.
      ``init [--agents-md] [--force]`` — scaffold opencode skills into your project.
      ``--version`` — print SDK version.
      ``--help`` — print usage information.
    """
    args = sys.argv[1:]

    if not args or args[0] == "--help":
        print("Usage: python -m canvastekk_workflow_sdk <command> [options]")
        print()
        print("Commands:")
        print("  validate <module:attribute> [--json]  Validate a node manifest definition")
        print("  diff <old.json> <new.json> [--json]   Classify breaking changes between manifests")
        print("  init [--agents-md] [--force]          Scaffold AI agent skills into your project")
        print()
        print("Options:")
        print("  --json         Output validation results as JSON")
        print("  --agents-md    Also create AGENTS.md with skill routing rules")
        print("  --force        Overwrite existing files")
        print("  --version      Show SDK version")
        print("  --help         Show this help message")
        sys.exit(0)

    if args[0] == "--version":
        from canvastekk_workflow_sdk import __version__

        print(f"canvastekk-workflow-sdk {__version__}")
        sys.exit(0)

    if args[0] == "diff":
        sys.exit(_run_diff(args[1:]))

    if args[0] == "init":
        include_agents_md = "--agents-md" in args
        force = "--force" in args
        _init_skills(Path.cwd(), include_agents_md=include_agents_md, force=force)
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
