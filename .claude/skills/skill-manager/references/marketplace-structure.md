# Marketplace Structure Reference

## Directory Structure

```
marketplace-root/
├── .claude-plugin/
│   └── marketplace.json          # Marketplace configuration
│
├── skill-name-1/
│   ├── .claude-plugin/
│   │   └── plugin.json          # Skill metadata
│   ├── SKILL.md                 # Skill documentation
│   ├── scripts/                 # Automation scripts (optional)
│   ├── references/              # Reference docs (optional)
│   └── assets/                  # Resources (optional)
│
├── skill-name-2/
│   └── ...
│
├── README.md                     # Marketplace documentation
├── CHANGELOG.md                  # Version history
└── .gitignore                    # Git exclusions
```

## marketplace.json

### Required Fields

```json
{
  "name": "my-skills",              // Marketplace identifier (required)
  "displayName": "My Skills",       // Human-readable name (optional)
  "version": "1.0.0",               // Semver version (optional)
  "owner": {                        // Owner information (required)
    "name": "John Doe",
    "url": "https://github.com/johndoe"
  },
  "homepage": "https://...",        // Marketplace URL (optional)
  "description": "...",             // Brief description (optional)
  "plugins": []                     // Skill entries (required)
}
```

### Plugin Entry Format

```json
{
  "name": "nextjs15-init",          // Skill name (required)
  "source": "./nextjs15-init",      // Path to skill folder (required)
  "description": "...",             // Brief description (required)
  "version": "1.0.0",               // Skill version (required)
  "category": "Project Init",       // Category (optional)
  "keywords": ["nextjs", "react"]   // Search keywords (optional)
}
```

### Complete Example

```json
{
  "name": "awesome-skills",
  "displayName": "Awesome Skills Marketplace",
  "version": "1.2.0",
  "owner": {
    "name": "Awesome Team",
    "url": "https://github.com/awesome-team"
  },
  "homepage": "https://github.com/awesome-team/skills",
  "description": "Collection of productivity skills for Claude Code",
  "plugins": [
    {
      "name": "nextjs15-init",
      "source": "./nextjs15-init",
      "description": "Initialize Next.js 15 projects with modern stack",
      "version": "1.2.0",
      "category": "Project Initialization",
      "keywords": ["nextjs", "react", "typescript"]
    },
    {
      "name": "web-to-markdown",
      "source": "./web-to-markdown",
      "description": "Convert web pages to markdown",
      "version": "1.0.5",
      "category": "Documentation",
      "keywords": ["markdown", "web-scraping"]
    }
  ]
}
```

## plugin.json

### Required Fields

```json
{
  "name": "skill-name",             // Must match folder name (required)
  "displayName": "Skill Name",      // Human-readable (optional)
  "description": "...",             // Brief description (required)
  "version": "1.0.0",               // Semver version (required)
  "author": {                       // Author info (optional)
    "name": "Author Name",
    "url": "https://..."
  },
  "homepage": "https://...",        // Skill URL (optional)
  "keywords": [],                   // Search keywords (optional)
  "category": "..."                 // Category (optional)
}
```

### Complete Example

```json
{
  "name": "nextjs15-init",
  "displayName": "Next.js 15 Project Initializer",
  "description": "Create Next.js 15 projects with App Router, ShadCN, and modern stack",
  "version": "1.2.0",
  "author": {
    "name": "Awesome Team",
    "url": "https://github.com/awesome-team"
  },
  "homepage": "https://github.com/awesome-team/skills/tree/master/nextjs15-init",
  "keywords": ["nextjs", "react", "typescript", "shadcn", "app-router"],
  "category": "Project Initialization"
}
```

## Categories

Recommended categories for organization:

- **Project Initialization**: Project scaffolding tools
- **AI Integration**: AI-powered development tools
- **Documentation**: Documentation generation and management
- **Prompt Tools**: Prompt engineering and enhancement
- **Development Tools**: General development utilities
- **UI/UX Development**: Frontend and design tools
- **Testing & QA**: Testing and quality assurance
- **DevOps**: Deployment and infrastructure tools
- **Database**: Database management tools
- **Other**: Miscellaneous tools

## Keywords Best Practices

### Good Keywords ✅

- Specific technologies: `nextjs`, `react`, `typescript`
- Use cases: `scaffolding`, `automation`, `documentation`
- Features: `ai-optimization`, `dual-mode`, `validation`

### Bad Keywords ❌

- Too generic: `tool`, `helper`, `utility`
- Redundant: Repeating skill name
- Too vague: `good`, `best`, `awesome`

### Examples

```json
// Good
{
  "name": "web-to-markdown",
  "keywords": ["markdown", "web-scraping", "ai-optimization", "playwright"]
}

// Bad
{
  "name": "web-to-markdown",
  "keywords": ["tool", "web", "good", "helper"]
}
```

## Version Synchronization

### Strategy 1: Synchronized Versioning

All skills share the marketplace version:

```json
// marketplace.json
{
  "version": "1.2.0",
  "plugins": [
    { "name": "skill-1", "version": "1.2.0" },
    { "name": "skill-2", "version": "1.2.0" }
  ]
}
```

**Pros**: Simple, clear release versions
**Cons**: Unnecessary version bumps for unchanged skills

### Strategy 2: Independent Versioning

Each skill has its own version:

```json
// marketplace.json
{
  "version": "1.2.0",
  "plugins": [
    { "name": "skill-1", "version": "2.0.0" },
    { "name": "skill-2", "version": "1.5.3" }
  ]
}
```

**Pros**: Accurate skill versioning
**Cons**: More complex to manage

### Recommended: Hybrid Approach

- Marketplace version: Overall collection version
- Skill versions: Individual skill versions
- Update both on release:
  - Marketplace version for major releases
  - Skill versions for changes to that skill

## File Size Recommendations

- **marketplace.json**: < 100 KB
- **plugin.json**: < 5 KB
- **SKILL.md**: < 50 KB (move large content to references/)
- **Total marketplace**: < 10 MB

## Validation Checklist

### Marketplace Level
- [ ] `.claude-plugin/marketplace.json` exists
- [ ] Valid JSON format
- [ ] Required fields present (name, owner, plugins)
- [ ] Version follows semver
- [ ] All plugin entries valid

### Skill Level
- [ ] Skill folder exists
- [ ] `SKILL.md` exists with frontmatter
- [ ] `.claude-plugin/plugin.json` exists
- [ ] Version matches marketplace (or documented difference)
- [ ] No broken links in documentation

### Git Level
- [ ] `.git` directory exists
- [ ] Remote origin configured
- [ ] `.gitignore` present
- [ ] No uncommitted changes

## Troubleshooting

### Invalid JSON

```bash
# Validate JSON syntax
python -m json.tool .claude-plugin/marketplace.json
```

### Version Mismatch

```bash
# Check all versions
grep -r '"version"' .claude-plugin/ */

# Update all to 1.2.0
# Use skill-manager: /skill-manager publish
```

### Missing Files

```bash
# Check for required files
for skill in */; do
  echo "Checking $skill"
  test -f "$skill/SKILL.md" || echo "  Missing SKILL.md"
  test -f "$skill/.claude-plugin/plugin.json" || echo "  Missing plugin.json"
done
```
