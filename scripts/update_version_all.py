#!/usr/bin/env python
# /// script
# dependencies = [
#   "tomli",
#   "click",
#   "inquirer",
#   "regex",
# ]
# [tool.uv]
# exclude-newer = "2025-03-20T00:00:00Z"
# ///
"""
Enhanced interactive version update script for dbgpt-mono project.

Features:
- Collects all files that need version updates
- Shows a preview of all changes before applying
- Allows user to confirm or reject changes
- Supports dry-run mode to only show changes without applying them
- Can selectively apply changes to specific packages
- Supports standard version formats (X.Y.Z) and pre-release versions (X.Y.Z-beta, X.Y.ZrcN)
- Only updates version numbers without changing file formatting
- Supports _version.py files commonly found in Python packages

Usage:
  uv run version_update.py NEW_VERSION [options]

Options:
  -y, --yes          Apply changes without confirmation
  -d, --dry-run      Only show changes without applying them
  -f, --filter PKG   Only update packages containing this string
  -h, --help         Show help message

Examples:
  uv run version_update.py 0.8.0              # Standard version
  uv run version_update.py 0.7.0rc0           # Release candidate
  uv run version_update.py 0.7.0-beta.1       # Beta version
  uv run version_update.py 0.8.0 --yes        # Apply all changes without prompting
  uv run version_update.py 0.8.0 --dry-run    # Only show what would change
  uv run version_update.py 0.8.0 --filter dbgpt-core  # Only update dbgpt-core package
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import tomli


@dataclass
class VersionChange:
    """Represents a single version change in a file."""

    file_path: Path
    file_type: str
    old_version: str
    new_version: str
    package_name: str

    def __str__(self):
        rel_path = self.file_path.as_posix()
        return f"{self.package_name:<20} {self.file_type:<12} {rel_path:<50} {self.old_version} -> {self.new_version}"


class VersionUpdater:
    """Class to handle version updates across the project."""

    def __init__(self, new_version: str, root_dir: Path, args: argparse.Namespace):
        self.new_version = new_version
        self.root_dir = root_dir
        self.args = args
        self.changes: List[VersionChange] = []
        # Support: X.Y.Z, X.Y.ZrcN, X.Y.Z-alpha.N, X.Y.Z-beta.N, X.Y.Z-rc.N
        self.version_pattern = re.compile(
            r"^\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?$|^\d+\.\d+\.\d+[a-zA-Z][a-zA-Z0-9.]*$"
        )

    def validate_version(self) -> bool:
        """Validate the version format."""
        if not self.version_pattern.match(self.new_version):
            print("Error: Invalid version format. Examples of valid formats:")
            print("  - Standard: 0.7.0, 1.0.0")
            print("  - Pre-release: 0.7.0rc0, 0.7.0-beta.1, 1.0.0-alpha.2")
            return False
        return True

    def find_main_config(self) -> Optional[Path]:
        """Find the main project configuration file."""
        root_config = self.root_dir / "pyproject.toml"

        if not root_config.exists():
            # Try to find it in subdirectories
            possible_files = list(self.root_dir.glob("**/pyproject.toml"))
            if possible_files:
                root_config = possible_files[0]
                print(f"Found root configuration at: {root_config}")
            else:
                print("Error: Could not find the project configuration file")
                return None

        return root_config

    def collect_toml_changes(self, file_path: Path, package_name: str) -> bool:
        """Collect version changes needed in a TOML file."""
        try:
            # Read the entire file content to preserve formatting
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Parse the TOML content to extract version information
            with open(file_path, "rb") as f:
                data = tomli.load(f)

            # Check for project.version or tool.poetry.version
            if "project" in data and "version" in data["project"]:
                old_version = data["project"]["version"]
                self.changes.append(
                    VersionChange(
                        file_path=file_path,
                        file_type="pyproject.toml",
                        old_version=old_version,
                        new_version=self.new_version,
                        package_name=package_name,
                    )
                )
                return True

            # Check for tool.poetry.version
            elif (
                "tool" in data
                and "poetry" in data["tool"]
                and "version" in data["tool"]["poetry"]
            ):
                old_version = data["tool"]["poetry"]["version"]
                self.changes.append(
                    VersionChange(
                        file_path=file_path,
                        file_type="pyproject.toml",
                        old_version=old_version,
                        new_version=self.new_version,
                        package_name=package_name,
                    )
                )
                return True

            return False

        except Exception as e:
            print(f"Error analyzing {file_path}: {str(e)}")
            return False

    def collect_setup_py_changes(self, file_path: Path, package_name: str) -> bool:
        """Collect version changes needed in a setup.py file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Find version pattern - more flexible to detect different formats
            version_pattern = r'version\s*=\s*["\']([^"\']+)["\']'
            match = re.search(version_pattern, content)

            if match:
                old_version = match.group(1)
                self.changes.append(
                    VersionChange(
                        file_path=file_path,
                        file_type="setup.py",
                        old_version=old_version,
                        new_version=self.new_version,
                        package_name=package_name,
                    )
                )
                return True

            return False

        except Exception as e:
            print(f"Error analyzing {file_path}: {str(e)}")
            return False

    def collect_version_py_changes(self, file_path: Path, package_name: str) -> bool:
        """Collect version changes needed in a _version.py file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Collect version pattern - more flexible to detect different formats
            # e.g. version = "0.7.0"
            version_pattern = r'version\s*=\s*["\']([^"\']+)["\']'
            match = re.search(version_pattern, content)

            if match:
                old_version = match.group(1)
                self.changes.append(
                    VersionChange(
                        file_path=file_path,
                        file_type="_version.py",
                        old_version=old_version,
                        new_version=self.new_version,
                        package_name=package_name,
                    )
                )
                return True

            return False

        except Exception as e:
            print(f"Error analyzing {file_path}: {str(e)}")
            return False

    def collect_json_changes(self, file_path: Path, package_name: str) -> bool:
        """Collect version changes needed in a JSON file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                data = json.loads(content)

            if "version" in data:
                old_version = data["version"]
                self.changes.append(
                    VersionChange(
                        file_path=file_path,
                        file_type="package.json",
                        old_version=old_version,
                        new_version=self.new_version,
                        package_name=package_name,
                    )
                )
                return True

            return False

        except Exception as e:
            print(f"Error analyzing {file_path}: {str(e)}")
            return False

    def find_workspace_members(self, workspace_members: List[str]) -> List[Path]:
        """Find all workspace member directories."""
        members = []

        for pattern in workspace_members:
            # Handle glob patterns
            if "*" in pattern:
                found = list(self.root_dir.glob(pattern))
                members.extend(found)
            else:
                path = self.root_dir / pattern
                if path.exists():
                    members.append(path)

        return members

    def collect_all_changes(self) -> bool:
        """Collect all version changes needed across the project."""
        # Find main project configuration
        root_config = self.find_main_config()
        if not root_config:
            return False

        # Start with the main config file
        self.collect_toml_changes(root_config, "root-project")

        # Find and parse workspace members from configuration
        workspace_members = []
        try:
            with open(root_config, "rb") as f:
                data = tomli.load(f)

            if (
                "tool" in data
                and "uv" in data["tool"]
                and "workspace" in data["tool"]["uv"]
            ):
                workspace_members = data["tool"]["uv"]["workspace"].get("members", [])
        except Exception as e:
            print(f"Warning: Could not parse workspace members: {str(e)}")

        # Find all package directories
        package_dirs = self.find_workspace_members(workspace_members)
        print(f"Found {len(package_dirs)} workspace packages to check")

        # Check each package directory for version files
        for pkg_dir in package_dirs:
            package_name = pkg_dir.name

            # Skip if filter is applied and doesn't match
            if self.args.filter and self.args.filter not in package_name:
                continue

            # Check for pyproject.toml
            pkg_toml = pkg_dir / "pyproject.toml"
            if pkg_toml.exists():
                self.collect_toml_changes(pkg_toml, package_name)

            # Check for setup.py
            setup_py = pkg_dir / "setup.py"
            if setup_py.exists():
                self.collect_setup_py_changes(setup_py, package_name)

            # Check for package.json
            package_json = pkg_dir / "package.json"
            if package_json.exists():
                self.collect_json_changes(package_json, package_name)

            # Check for _version.py files
            version_py_files = list(pkg_dir.glob("**/_version.py"))
            for version_py in version_py_files:
                self.collect_version_py_changes(version_py, package_name)

        return len(self.changes) > 0

    def apply_changes(self) -> int:
        """Apply all collected changes."""
        applied_count = 0

        for change in self.changes:
            try:
                if change.file_type == "pyproject.toml":
                    self._update_toml_file(change.file_path)
                elif change.file_type == "setup.py":
                    self._update_setup_py_file(change.file_path)
                elif change.file_type == "package.json":
                    self._update_json_file(change.file_path)
                elif change.file_type == "_version.py":
                    self._update_version_py_file(change.file_path)

                applied_count += 1
                print(f"✅ Updated {change.file_path}")

            except Exception as e:
                print(f"❌ Failed to update {change.file_path}: {str(e)}")

        return applied_count

    def _update_toml_file(self, file_path: Path) -> None:
        """Update version in a TOML file using regex to preserve formatting."""
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        updated = False

        # Update project.version
        project_version_pattern = (
            r'(\[project\][^\[]*?version\s*=\s*["\'](.*?)["\']\s*)'
        )
        if re.search(project_version_pattern, content, re.DOTALL):
            project_pattern = r'(\[project\][^\[]*?version\s*=\s*["\'](.*?)["\']\s*)'
            content = re.sub(
                project_pattern,
                lambda m: m.group(0).replace(m.group(2), self.new_version),
                content,
                flags=re.DOTALL,
            )
            updated = True

        poetry_version_pattern = (
            r'(\[tool\.poetry\][^\[]*?version\s*=\s*["\'](.*?)["\']\s*)'
        )
        if re.search(poetry_version_pattern, content, re.DOTALL):
            poetry_pattern = (
                r'(\[tool\.poetry\][^\[]*?version\s*=\s*["\'](.*?)["\']\s*)'
            )
            content = re.sub(
                poetry_pattern,
                lambda m: m.group(0).replace(m.group(2), self.new_version),
                content,
                flags=re.DOTALL,
            )
            updated = True

        if not updated:
            version_line_pattern = r'(^version\s*=\s*["\'](.*?)["\']\s*$)'
            content = re.sub(
                version_line_pattern,
                lambda m: m.group(0).replace(m.group(2), self.new_version),
                content,
                flags=re.MULTILINE,
            )

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

    def _update_setup_py_file(self, file_path: Path) -> None:
        """Update version in a setup.py file."""
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Find and replace version
        version_pattern = r'(version\s*=\s*["\'])([^"\']+)(["\'])'
        updated_content = re.sub(
            version_pattern, rf"\g<1>{self.new_version}\g<3>", content
        )

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(updated_content)

    def _update_version_py_file(self, file_path: Path) -> None:
        """Update version in a _version.py file."""
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        version_pattern = r'(version\s*=\s*["\'])([^"\']+)(["\'])'
        updated_content = re.sub(
            version_pattern, rf"\g<1>{self.new_version}\g<3>", content
        )

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(updated_content)

    def _update_json_file(self, file_path: Path) -> None:
        """Update version in a JSON file while preserving formatting."""
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        version_pattern = r'("version"\s*:\s*")([^"]+)(")'
        updated_content = re.sub(
            version_pattern, rf"\g<1>{self.new_version}\g<3>", content
        )

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(updated_content)

    def show_changes(self) -> None:
        """Display the collected changes."""
        if not self.changes:
            print("No changes to apply.")
            return

        print("\n" + "=" * 100)
        print(f"Version changes to apply: {self.new_version}")
        print("=" * 100)
        print(f"{'Package':<20} {'File Type':<12} {'Path':<50} {'Version Change'}")
        print("-" * 100)

        for change in self.changes:
            print(str(change))

        print("=" * 100)
        print(f"Total: {len(self.changes)} file(s) to update")
        print("=" * 100)

    def prompt_for_confirmation(self) -> bool:
        """Prompt the user for confirmation."""
        if self.args.yes:
            return True

        response = input("\nApply these changes? [y/N]: ").strip().lower()
        return response in ["y", "yes"]

    def run(self) -> bool:
        """Run the updater."""
        if not self.validate_version():
            return False

        # Collect all changes
        if not self.collect_all_changes():
            print("No files found that need version updates.")
            return False

        # Show the changes
        self.show_changes()

        # If dry run, exit now
        if self.args.dry_run:
            print("\nDry run complete. No changes were applied.")
            return True

        # Prompt for confirmation
        if not self.prompt_for_confirmation():
            print("\nOperation cancelled. No changes were applied.")
            return False

        # Apply the changes
        applied_count = self.apply_changes()
        print(
            f"\n🎉 Version update complete! Updated {applied_count} files to version {self.new_version}"
        )
        return True


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Update version numbers across the dbgpt-mono project",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("\n\n")[2],  # Extract usage examples
    )

    parser.add_argument(
        "version", help="New version number (supports standard and pre-release formats)"
    )
    parser.add_argument(
        "-y", "--yes", action="store_true", help="Apply changes without confirmation"
    )
    parser.add_argument(
        "-d",
        "--dry-run",
        action="store_true",
        help="Only show changes without applying them",
    )
    parser.add_argument(
        "-f", "--filter", help="Only update packages containing this string"
    )

    return parser.parse_args()


def main():
    """Main entry point for the script."""
    args = parse_args()

    # Initialize the updater
    updater = VersionUpdater(new_version=args.version, root_dir=Path("../"), args=args)

    # Run the updater
    success = updater.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
