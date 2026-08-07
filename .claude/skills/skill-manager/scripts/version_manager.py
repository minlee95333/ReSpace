#!/usr/bin/env python3
"""
Version Manager Utility
Handles semantic versioning operations for Claude Code marketplace.
"""

import re
from typing import Tuple


class VersionManager:
    """Manages semantic versioning (semver) for marketplace and skills."""

    @staticmethod
    def is_valid_semver(version: str) -> bool:
        """Check if version follows semver format (X.X.X)."""
        pattern = r'^\d+\.\d+\.\d+$'
        return bool(re.match(pattern, version))

    @staticmethod
    def parse_version(version: str) -> Tuple[int, int, int]:
        """Parse version string into (major, minor, patch) tuple."""
        if not VersionManager.is_valid_semver(version):
            raise ValueError(f"Invalid semver format: {version}")

        parts = version.split('.')
        return int(parts[0]), int(parts[1]), int(parts[2])

    @staticmethod
    def increment_version(current: str, bump_type: str) -> str:
        """
        Increment version based on bump type.

        Args:
            current: Current version (e.g., "1.0.0")
            bump_type: Type of bump ("major", "minor", "patch")

        Returns:
            New version string

        Example:
            >>> VersionManager.increment_version("1.2.3", "patch")
            '1.2.4'
            >>> VersionManager.increment_version("1.2.3", "minor")
            '1.3.0'
            >>> VersionManager.increment_version("1.2.3", "major")
            '2.0.0'
        """
        major, minor, patch = VersionManager.parse_version(current)

        if bump_type == 'major':
            return f"{major + 1}.0.0"
        elif bump_type == 'minor':
            return f"{major}.{minor + 1}.0"
        elif bump_type == 'patch':
            return f"{major}.{minor}.{patch + 1}"
        else:
            raise ValueError(f"Invalid bump type: {bump_type}. Use 'major', 'minor', or 'patch'")

    @staticmethod
    def compare_versions(v1: str, v2: str) -> int:
        """
        Compare two versions.

        Returns:
            -1 if v1 < v2
             0 if v1 == v2
             1 if v1 > v2
        """
        major1, minor1, patch1 = VersionManager.parse_version(v1)
        major2, minor2, patch2 = VersionManager.parse_version(v2)

        if major1 != major2:
            return 1 if major1 > major2 else -1
        if minor1 != minor2:
            return 1 if minor1 > minor2 else -1
        if patch1 != patch2:
            return 1 if patch1 > patch2 else -1

        return 0


# Example usage
if __name__ == "__main__":
    vm = VersionManager()

    # Test version validation
    print("Valid semver:")
    print(f"  1.0.0: {vm.is_valid_semver('1.0.0')}")
    print(f"  1.2.3: {vm.is_valid_semver('1.2.3')}")
    print(f"  1.0: {vm.is_valid_semver('1.0')}")  # False
    print(f"  v1.0.0: {vm.is_valid_semver('v1.0.0')}")  # False

    # Test version increment
    print("\nVersion increment:")
    print(f"  1.2.3 + patch → {vm.increment_version('1.2.3', 'patch')}")
    print(f"  1.2.3 + minor → {vm.increment_version('1.2.3', 'minor')}")
    print(f"  1.2.3 + major → {vm.increment_version('1.2.3', 'major')}")

    # Test version comparison
    print("\nVersion comparison:")
    print(f"  1.0.0 vs 1.0.1: {vm.compare_versions('1.0.0', '1.0.1')}")  # -1
    print(f"  2.0.0 vs 1.9.9: {vm.compare_versions('2.0.0', '1.9.9')}")  # 1
    print(f"  1.5.0 vs 1.5.0: {vm.compare_versions('1.5.0', '1.5.0')}")  # 0
