#!/usr/bin/env python3
"""
Marketplace Validation Script
Validates marketplace.json and all skill configurations.
"""

import json
import os
import sys
import yaml
from pathlib import Path
from typing import List, Dict, Tuple
from version_manager import VersionManager


class MarketplaceValidator:
    """Validates Claude Code marketplace configuration."""

    def __init__(self, root_dir: str = "."):
        self.root_dir = Path(root_dir)
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.vm = VersionManager()

    def validate_all(self) -> bool:
        """Run all validations. Returns True if all passed."""
        print("🔍 Validating marketplace...")
        print()

        # Validate marketplace.json
        if not self.validate_marketplace_json():
            return False

        # Validate each skill
        if not self.validate_all_skills():
            return False

        # Validate Git repository
        self.validate_git_repo()

        # Print results
        self.print_results()

        return len(self.errors) == 0

    def validate_marketplace_json(self) -> bool:
        """Validate marketplace.json file."""
        marketplace_path = self.root_dir / ".claude-plugin" / "marketplace.json"

        # Check file exists
        if not marketplace_path.exists():
            self.errors.append("marketplace.json not found at .claude-plugin/marketplace.json")
            return False

        # Check valid JSON
        try:
            with open(marketplace_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            self.errors.append(f"Invalid JSON in marketplace.json: {e}")
            return False

        # Check required fields
        required_fields = ['name', 'owner', 'plugins']
        for field in required_fields:
            if field not in data:
                self.errors.append(f"Missing required field in marketplace.json: {field}")

        # Check owner structure
        if 'owner' in data:
            if 'name' not in data['owner']:
                self.errors.append("Missing 'name' in marketplace owner")

        # Check version format
        if 'version' in data:
            if not self.vm.is_valid_semver(data['version']):
                self.errors.append(f"Invalid version format: {data['version']} (use X.X.X)")

        # Check plugins array
        if 'plugins' in data:
            if not isinstance(data['plugins'], list):
                self.errors.append("'plugins' must be an array")
            else:
                for idx, plugin in enumerate(data['plugins']):
                    self.validate_plugin_entry(plugin, idx)

        return len(self.errors) == 0

    def validate_plugin_entry(self, plugin: Dict, idx: int) -> None:
        """Validate a plugin entry in marketplace.json."""
        required = ['name', 'source', 'description', 'version']

        for field in required:
            if field not in plugin:
                self.errors.append(f"Plugin #{idx}: Missing required field '{field}'")

        # Check version format
        if 'version' in plugin:
            if not self.vm.is_valid_semver(plugin['version']):
                self.errors.append(f"Plugin #{idx} ({plugin.get('name', '?')}): Invalid version format")

        # Check keywords
        if 'keywords' in plugin:
            if not isinstance(plugin['keywords'], list):
                self.warnings.append(f"Plugin #{idx} ({plugin.get('name', '?')}): keywords should be an array")
            elif len(plugin['keywords']) == 0:
                self.warnings.append(f"Plugin #{idx} ({plugin.get('name', '?')}): No keywords provided")

    def validate_all_skills(self) -> bool:
        """Validate all skills referenced in marketplace.json."""
        marketplace_path = self.root_dir / ".claude-plugin" / "marketplace.json"

        with open(marketplace_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        plugins = data.get('plugins', [])
        total = len(plugins)
        passed = 0

        for plugin in plugins:
            skill_name = plugin.get('name', '')
            if self.validate_skill(skill_name, plugin):
                passed += 1

        print(f"Skills: {passed}/{total} passed")
        print()

        return passed == total

    def validate_skill(self, skill_name: str, marketplace_entry: Dict) -> bool:
        """Validate a single skill."""
        skill_dir = self.root_dir / skill_name
        has_errors = False

        # Check skill folder exists
        if not skill_dir.exists():
            self.errors.append(f"Skill '{skill_name}': Folder not found")
            return False

        # Check SKILL.md exists
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            self.errors.append(f"Skill '{skill_name}': SKILL.md not found")
            has_errors = True
        else:
            # Validate SKILL.md frontmatter
            if not self.validate_skill_frontmatter(skill_md, skill_name):
                has_errors = True

        # Check plugin.json exists
        plugin_json = skill_dir / ".claude-plugin" / "plugin.json"
        if not plugin_json.exists():
            self.errors.append(f"Skill '{skill_name}': plugin.json not found")
            has_errors = True
        else:
            # Validate plugin.json
            if not self.validate_plugin_json(plugin_json, skill_name, marketplace_entry):
                has_errors = True

        return not has_errors

    def validate_skill_frontmatter(self, skill_md_path: Path, skill_name: str) -> bool:
        """Validate SKILL.md YAML frontmatter."""
        try:
            with open(skill_md_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Extract frontmatter
            if not content.startswith('---'):
                self.errors.append(f"Skill '{skill_name}': SKILL.md missing YAML frontmatter")
                return False

            parts = content.split('---', 2)
            if len(parts) < 3:
                self.errors.append(f"Skill '{skill_name}': Invalid YAML frontmatter format")
                return False

            frontmatter = yaml.safe_load(parts[1])

            # Check required fields
            if 'name' not in frontmatter:
                self.errors.append(f"Skill '{skill_name}': Missing 'name' in frontmatter")
            elif frontmatter['name'] != skill_name:
                self.warnings.append(f"Skill '{skill_name}': Frontmatter name '{frontmatter['name']}' doesn't match folder name")

            if 'description' not in frontmatter:
                self.errors.append(f"Skill '{skill_name}': Missing 'description' in frontmatter")

            return True

        except Exception as e:
            self.errors.append(f"Skill '{skill_name}': Error reading SKILL.md: {e}")
            return False

    def validate_plugin_json(self, plugin_json_path: Path, skill_name: str, marketplace_entry: Dict) -> bool:
        """Validate plugin.json file."""
        try:
            with open(plugin_json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            self.errors.append(f"Skill '{skill_name}': Invalid JSON in plugin.json: {e}")
            return False

        # Check required fields
        required = ['name', 'description', 'version']
        for field in required:
            if field not in data:
                self.errors.append(f"Skill '{skill_name}': Missing '{field}' in plugin.json")

        # Check version matches marketplace
        if 'version' in data and 'version' in marketplace_entry:
            if data['version'] != marketplace_entry['version']:
                self.warnings.append(
                    f"Skill '{skill_name}': Version mismatch "
                    f"(plugin.json: {data['version']}, marketplace: {marketplace_entry['version']})"
                )

        return True

    def validate_git_repo(self) -> None:
        """Validate Git repository configuration."""
        git_dir = self.root_dir / ".git"

        if not git_dir.exists():
            self.warnings.append("Git not initialized")
            return

        # Check for remote
        try:
            import subprocess
            result = subprocess.run(
                ['git', 'remote', '-v'],
                cwd=self.root_dir,
                capture_output=True,
                text=True
            )
            if not result.stdout.strip():
                self.warnings.append("No Git remote configured")
        except Exception:
            pass

        # Check for uncommitted changes
        try:
            result = subprocess.run(
                ['git', 'status', '--porcelain'],
                cwd=self.root_dir,
                capture_output=True,
                text=True
            )
            if result.stdout.strip():
                changes = len(result.stdout.strip().split('\n'))
                self.warnings.append(f"{changes} uncommitted change(s)")
        except Exception:
            pass

    def print_results(self) -> None:
        """Print validation results."""
        print()
        if len(self.errors) == 0 and len(self.warnings) == 0:
            print("✅ Marketplace Validation: PASSED")
            print()
            print("Marketplace: ✅ Valid")
            print("Git: ✅ Configured")
        elif len(self.errors) == 0:
            print("⚠️  Marketplace Validation: PASSED (with warnings)")
            print()
            print("Warnings:")
            for warning in self.warnings:
                print(f"  ⚠️  {warning}")
        else:
            print("❌ Marketplace Validation: FAILED")
            print()
            print("Errors:")
            for error in self.errors:
                print(f"  ❌ {error}")

            if self.warnings:
                print()
                print("Warnings:")
                for warning in self.warnings:
                    print(f"  ⚠️  {warning}")


if __name__ == "__main__":
    validator = MarketplaceValidator()
    success = validator.validate_all()
    sys.exit(0 if success else 1)
