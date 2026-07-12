#!/usr/bin/env python3
"""Bump version across all language config files.

Usage: python3 scripts/bump_versions.py <version>

Handled file types:
  .py    — __version__ = "X.Y.Z"
  .toml  — version = "X.Y.Z" (under [tool.poetry])
  .json  — {"version": "X.Y.Z"}
  .props — <Version>X.Y.Z</Version> (XML)
  .ts    — export const VERSION = "X.Y.Z"
"""

from __future__ import annotations

import json
import os
import re
import sys
import xml.etree.ElementTree as ET


VERSION_FILES = {
    "python": "python/pyproject.toml",
    "python_init": "python/canvastekk_workflow_sdk/__init__.py",
    "typescript": "typescript/package.json",
    "typescript_version": "typescript/src/version.ts",
    "dotnet": "dotnet/Directory.Build.props",
}


def bump_file(path: str, version: str) -> bool:
    """Bump version in a single file. Returns True if bumped."""
    if not os.path.exists(path):
        print(f"SKIP: {path} does not exist")
        return False

    with open(path, "r") as f:
        content = f.read()

    if path.endswith(".py"):
        new_content, count = re.subn(
            r'__version__\s*=\s*"[^"]*"',
            f'__version__ = "{version}"',
            content,
            count=1,
        )
        if count == 0:
            print(f"WARNING: Could not find __version__ pattern in {path}")
            return False
        with open(path, "w") as f:
            f.write(new_content)

    elif path.endswith(".toml"):
        new_content, count = re.subn(
            r'(\[tool\.poetry\][^\[]*?)version\s*=\s*"[^"]*"',
            rf'\1version = "{version}"',
            content,
            flags=re.DOTALL,
        )
        if count == 0:
            new_content, count = re.subn(
                r'version\s*=\s*"[^"]*"',
                f'version = "{version}"',
                content,
                count=1,
            )
        if count == 0:
            print(f"WARNING: Could not find version pattern in {path}")
            return False
        with open(path, "w") as f:
            f.write(new_content)

    elif path.endswith(".json"):
        data = json.loads(content)
        data["version"] = version
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
            f.write("\n")

    elif path.endswith(".props"):
        tree = ET.parse(path)
        root = tree.getroot()
        for elem in root.iter("Version"):
            elem.text = version
        tree.write(path, xml_declaration=True, encoding="utf-8")

    elif path.endswith(".ts"):
        new_content, count = re.subn(
            r'export\s+const\s+VERSION\s*=\s*"[^"]*"',
            f'export const VERSION = "{version}"',
            content,
            count=1,
        )
        if count == 0:
            print(f"WARNING: Could not find VERSION pattern in {path}")
            return False
        with open(path, "w") as f:
            f.write(new_content)

    else:
        print(f"SKIP: unknown file type {path}")
        return False

    print(f"BUMPED: {path} -> {version}")
    return True


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python3 scripts/bump_versions.py <version>")
        sys.exit(1)

    version = sys.argv[1].lstrip("v")

    if not re.match(r"^\d+\.\d+\.\d+", version):
        print(f"ERROR: '{version}' is not a valid semver version (expected X.Y.Z)")
        sys.exit(1)

    bumped = []
    for lang, path in VERSION_FILES.items():
        if bump_file(path, version):
            bumped.append(lang)

    if not bumped:
        print("WARNING: No version files were bumped!")
    else:
        print(f"\nBumped {len(bumped)} files: {', '.join(bumped)}")


if __name__ == "__main__":
    main()
