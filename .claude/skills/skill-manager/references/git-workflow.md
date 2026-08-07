# Git Workflow Guide for Skill Manager

## Overview

This document describes the Git workflow used by the skill-manager skill. It follows industry best practices including Conventional Commits and Semantic Versioning.

## Conventional Commits

### Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- **feat**: New feature or skill
- **fix**: Bug fix
- **docs**: Documentation only changes
- **style**: Code style changes (formatting, semicolons, etc.)
- **refactor**: Code refactoring (no feature change)
- **perf**: Performance improvements
- **test**: Adding or updating tests
- **chore**: Maintenance tasks (dependencies, build, etc.)
- **release**: Version release

### Examples

```bash
# New skill
feat(nextjs15-init): Add dashboard domain support

Added support for dashboard domain with analytics components.

# Bug fix
fix(web-to-markdown): Fix Playwright fallback issue

Fixed issue where Playwright was not being invoked for dynamic content.

# Documentation
docs(README): Update installation instructions

Added marketplace installation method to README.

# Release
release: Version 1.2.0

- Added 2 new skills
- Fixed 3 bugs
- Updated documentation
```

## Semantic Versioning

### Version Format

`MAJOR.MINOR.PATCH` (e.g., 1.2.3)

### Increment Rules

**MAJOR** version (X.0.0):
- Breaking changes
- Incompatible API changes
- Major restructuring

**MINOR** version (0.X.0):
- New features (backward-compatible)
- New skills added
- Significant enhancements

**PATCH** version (0.0.X):
- Bug fixes
- Minor updates
- Documentation improvements

### Examples

```
1.0.0 → 1.0.1   (patch: bug fix)
1.0.1 → 1.1.0   (minor: new skill added)
1.1.0 → 2.0.0   (major: breaking change)
```

## Git Workflow Steps

### 1. Make Changes

Edit files, add new skills, update configurations.

### 2. Stage Changes

```bash
git add .
```

### 3. Commit with Conventional Message

```bash
git commit -m "feat(skill-manager): Add marketplace validation

- Validate marketplace.json format
- Check all skills for completeness
- Report errors and warnings

🤖 Generated with Claude Code

Co-Authored-By: Claude <noreply@anthropic.com>"
```

### 4. Tag Version

```bash
git tag -a v1.2.0 -m "Release v1.2.0"
```

### 5. Push to Remote

```bash
git push origin master
git push origin v1.2.0
```

## Changelog Maintenance

### Format

Follow [Keep a Changelog](https://keepachangelog.com/) format:

```markdown
## [1.2.0] - 2025-01-10

### Added
- New skill: skill-manager
- Marketplace validation tool

### Changed
- Updated README with new installation method

### Fixed
- Fixed plugin.json version mismatch
```

### Categories

- **Added**: New features
- **Changed**: Changes in existing functionality
- **Deprecated**: Soon-to-be removed features
- **Removed**: Removed features
- **Fixed**: Bug fixes
- **Security**: Security fixes

## Best Practices

### Commit Messages

✅ **Good**:
```
feat(nextjs15-init): Add TypeScript strict mode support
fix(web-to-markdown): Handle UTF-8 encoding correctly
docs: Update skill-creator with new examples
```

❌ **Bad**:
```
update files
fix bug
changes
```

### Atomic Commits

- One logical change per commit
- Don't mix features and bug fixes
- Keep commits focused and small

### Branching Strategy

**master**: Main development branch
- All features committed here
- Tagged for releases

**feature/***: Feature branches (optional)
- Use for major features
- Merge to master when complete

### Release Process

1. Update version in marketplace.json
2. Update all plugin.json versions (if needed)
3. Update CHANGELOG.md
4. Commit with "release: Version X.X.X"
5. Create Git tag
6. Push to remote

## Integration with /sc:git

The skill-manager works harmoniously with the `/sc:git` command:

### Scenario 1: Use skill-manager for full automation

```bash
/skill-manager publish --type minor
```

This handles:
- Version bumping
- Changelog generation
- Git commit
- Git tag
- Git push

### Scenario 2: Manual Git with skill-manager versioning

```bash
# Update versions
/skill-manager update-marketplace

# Manual commit
git add .
git commit -m "Custom commit message"
git tag v1.2.0
git push origin master --tags

# Or use /sc:git
/sc:git commit -m "Custom message"
```

## Troubleshooting

### Uncommitted Changes

```bash
# Check status
git status

# Add specific files
git add file1 file2

# Or add all
git add .
```

### Wrong Commit Message

```bash
# Amend last commit
git commit --amend -m "New message"
```

### Forgot to Tag

```bash
# Create tag for existing commit
git tag -a v1.2.0 <commit-hash> -m "Release v1.2.0"
git push origin v1.2.0
```

### Push Rejected

```bash
# Pull first
git pull origin master --rebase

# Then push
git push origin master
```

## References

- [Conventional Commits](https://www.conventionalcommits.org/)
- [Semantic Versioning](https://semver.org/)
- [Keep a Changelog](https://keepachangelog.com/)
- [Git Best Practices](https://git-scm.com/book/en/v2)
