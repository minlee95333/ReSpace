---
name: analytics
description: Tool/Agent 사용 통계를 CLI 차트로 시각화. "통계", "사용량", "analytics", "metrics", "리포트" 키워드에 반응.
---

# Analytics Skill

Tool usage statistics with CLI visualization. Displays bar charts, sparklines, and distribution graphs.

## Usage

```bash
/analytics [command]
```

### Commands

| Command | Alias | Description |
|---------|-------|-------------|
| `summary` | `s` | Quick overview (default) |
| `tools` | `t` | Tool usage bar chart |
| `errors` | `e` | Error distribution |
| `activity` | `a` | Hourly activity sparkline |
| `agents` | `ag` | Agent usage stats |
| `categories` | `c` | Category distribution |
| `full` | `f` | Complete report |

## Output Examples

### Summary (Default)

```
📊 Analytics Summary (2026-01-21)
══════════════════════════════════════════════════

Total Calls: 156  Success Rate: 97%

Tool Usage
──────────────────────────────────────────────────
Read       │████████████████████████│ 48
Write      │██████████████│ 28
Edit       │████████████│ 24
Bash       │████████│ 16

Success Rate
──────────────────────────────────────────────────
Overall    █████████████████████████  97% (151/156)

Hourly Activity
──────────────────────────────────────────────────
Activity: ▁▂▃▅▇█▇▅▃▂▁▁▂▅▇█▆▄▂▁
          00    06    12    18    23
```

### Tool Usage

```
Tool Usage
──────────────────────────────────────────────────
Read       │████████████████████████│ 48
Write      │██████████████│ 28
Edit       │████████████│ 24
Bash       │████████│ 16
Grep       │██████│ 12
Glob       │████│ 8
Task       │███│ 6
```

### Category Distribution

```
Category Distribution
──────────────────────────────────────────────────
file         ████████████████████  68% (106)
shell        ████████░░░░░░░░░░░░  18% (28)
agent        ████░░░░░░░░░░░░░░░░   8% (12)
planning     ██░░░░░░░░░░░░░░░░░░   4% (6)
interaction  █░░░░░░░░░░░░░░░░░░░   2% (4)
```

### Error Distribution

```
Error Distribution
──────────────────────────────────────────────────
Bash         │████████│ 4
Write        │████│ 2
Read         │██│ 1

(Or if no errors: "No errors recorded!")
```

### Agent Usage

```
Agent Usage
──────────────────────────────────────────────────
Explore            │████████████████████│ 15
code-reviewer      │████████████│ 9
commit-helper      │████████│ 6
analytics-reporter │████│ 3
```

## Implementation

Execute the visualizer script:

```bash
.claude/scripts/analytics-visualizer.sh [command]
```

## Workflow

```
/analytics → Parse metrics.jsonl → Aggregate data → Render ASCII charts
```

## Data Source

- **Primary**: `.claude/analytics/metrics.jsonl`
- **Format**: JSONL with fields: `ts`, `type`, `name`, `category`, `success`, `file`, `context`

## Settings

Configured in `.claude/settings.json`:

```json
{
  "analytics": {
    "enabled": true,
    "track_tool_usage": true,
    "track_agent_calls": true,
    "track_skill_invocations": true,
    "metrics_file": ".claude/analytics/metrics.jsonl",
    "retention_days": 30
  }
}
```

## Related

- **Agent**: `analytics-reporter` - Detailed analysis and insights
- **Hook**: `post-tool-use-tracker.sh` - Data collection
