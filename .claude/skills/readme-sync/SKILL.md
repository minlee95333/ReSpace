---
name: readme-sync
description: Automatically synchronize README.md with actual project components. Scans .claude directory and updates Agents, Skills, Hooks, Commands sections.
---

# README Sync Skill

Automatically keeps README.md synchronized with actual project components. Scans the `.claude` directory structure and updates documentation to match reality.

## Usage

```bash
/readme-sync [--section <name>] [--validate] [--dry-run]
```

### Options

| Option | Description |
|--------|-------------|
| `--section <name>` | Sync specific section: agents, skills, hooks, commands, stats |
| `--validate` | Check for mismatches without making changes |
| `--dry-run` | Show what would change without actually changing |
| (default) | Sync all sections |

## What Gets Synced

### 1. Agents Section
Scans `.claude/agents/*.md` and updates:
- Agent count
- Agent table with names, purposes, keywords
- Auto-detects from frontmatter: `name`, `description`

### 2. Skills Section
Scans `.claude/skills/*/SKILL.md` and `.claude/skills/*.md`:
- Skill count
- Skill table with usage, description
- Auto-detects from frontmatter

### 3. Hooks Section
Scans `.claude/hooks/*.sh` and `.claude/hooks/*.md`:
- Hook count
- Hook table with events, purposes
- Auto-detects from frontmatter or comments

### 4. Commands Section
Scans `.claude/commands/*.md` and `.claude/commands/*/`:
- Command count
- Command table with descriptions
- Includes subcommand files

### 5. Stats Section
Updates summary statistics:
```markdown
| Category | Count |
|----------|-------|
| Agents | 16 |
| Skills | 14 |
| Hooks | 4 |
| Commands | 2 |
| Templates | 5 |
| **Total** | **41** |
```

## Workflow

### Step 1: Scan Components
```bash
# Scan all .claude directories
find .claude/agents -name "*.md" -type f
find .claude/skills -name "SKILL.md" -o -name "*.md" -type f
find .claude/hooks -name "*.sh" -o -name "*.md" -type f
find .claude/commands -name "*.md" -type f
```

### Step 2: Extract Metadata
For each file, extract:
```yaml
# From frontmatter
name: component-name
description: Brief description
tools: [Tool1, Tool2]  # for agents
keywords: [key1, key2]
```

### Step 3: Generate Section Content
```markdown
## Sub-Agents (16)

### Development & Analysis

| Agent | Purpose | Keywords |
|-------|---------|----------|
| `project-analyzer` | Analyze project structure | "analyze", "structure" |
| `code-reviewer` | Review code quality | "review", "PR" |
...
```

### Step 4: Update README
- Find existing section by header
- Replace content between headers
- Preserve custom content outside synced sections

## Section Markers

Use these markers to define sync boundaries:

```markdown
<!-- README-SYNC:agents:start -->
## Sub-Agents (16)
...content auto-generated...
<!-- README-SYNC:agents:end -->

<!-- README-SYNC:skills:start -->
## Skills (14)
...content auto-generated...
<!-- README-SYNC:skills:end -->
```

Without markers, the skill will find sections by `## Sub-Agents` or `## Agents` headers.

## Output Examples

### Sync Report
```
📝 README-SYNC: Synchronizing README.md...

[1/4] Scanning agents...
      Found: 16 agents
      New: file-explorer (+1)
      Removed: none

[2/4] Scanning skills...
      Found: 14 skills
      New: agile-sync, readme-sync (+2)
      Removed: none

[3/4] Scanning hooks...
      Found: 4 hooks
      New: auto-doc-sync (+1)
      Removed: none

[4/4] Updating stats...
      Total: 36 → 40 (+4)

📝 README-SYNC: Complete!
   Sections updated: 4
   Components added: 4
   Components removed: 0
```

### Validation Report
```
📝 README-SYNC: Validation Report

## Agents
✅ 16 agents in README matches 16 files
⚠️ `old-agent` in README but file not found

## Skills
❌ README shows 12 skills, found 14 files
   Missing in README:
   - agile-sync
   - readme-sync

## Hooks
✅ All hooks accounted for

## Stats
❌ Stats section outdated
   README: 33 total
   Actual: 40 total

Issues: 3
Recommendations:
- Run `/readme-sync` to fix mismatches
- Remove reference to `old-agent`
```

## Configuration

### Auto-Sync Settings
```json
{
  "readme-sync": {
    "auto_on_change": true,
    "sections": ["agents", "skills", "hooks", "commands", "stats"],
    "preserve_custom": true,
    "use_markers": true,
    "table_format": "markdown"
  }
}
```

### Section Templates
```yaml
# .claude/readme-sync-config.yml
sections:
  agents:
    header: "## Sub-Agents ({count})"
    columns:
      - name: "Agent"
        source: "name"
        format: "`{value}`"
      - name: "Purpose"
        source: "description"
        truncate: 50
      - name: "Keywords"
        source: "keywords"
        format: "\"{value}\""

  skills:
    header: "## Skills ({count})"
    group_by: "category"
    columns:
      - name: "Skill"
        source: "name"
      - name: "Usage"
        source: "usage"
      - name: "Description"
        source: "description"
```

## Integration

### With auto-doc-sync Hook
```bash
# Hook triggers readme-sync when .claude files change
# In hooks/auto-doc-sync.sh:
if [[ "$TOOL_INPUT" == *".claude/"* ]]; then
    # Trigger README sync suggestion
fi
```

### With /agile-sync
```bash
# agile-sync includes readme-sync as step 3
/agile-sync  # Includes README stats update
```

### Manual Trigger
```bash
# Full sync
/readme-sync

# Specific section
/readme-sync --section skills

# Validate only
/readme-sync --validate
```

## Best Practices

### DO
- ✅ Use section markers for precise updates
- ✅ Run after adding new agents/skills
- ✅ Include in PR checklist
- ✅ Keep frontmatter accurate in source files

### DON'T
- ❌ Manually edit synced sections (will be overwritten)
- ❌ Remove section markers
- ❌ Skip validation before releases

## Troubleshooting

### "Section not found in README"
```bash
# Add section markers or headers:
## Sub-Agents
<!-- or -->
<!-- README-SYNC:agents:start -->
<!-- README-SYNC:agents:end -->
```

### "Component not detected"
```bash
# Ensure frontmatter is valid:
---
name: my-component
description: Brief description
---
```

### "Stats mismatch"
```bash
# Force full recalculation:
/readme-sync --section stats
```

## Related Skills

| Skill | Purpose |
|-------|---------|
| `/agile-sync` | Full agile artifact sync |
| `/init` | Project initialization |
| `/doc` | Documentation generation |
