# claudephant

Mine your Claude Code conversation history for patterns, mistakes, and insights.

## Quick Start: Find What Claude Gets Wrong

```bash
git clone git@github.com:ianhi/claudephant.git
cd claudephant
uv tool install -e .
claude
```

Then in Claude Code:

```
/mine-api-mistakes mine mistakes Claude makes with pandas
```

Claude handles everything — scans your history, extracts errors, analyzes
patterns with parallel subagents, and compiles a shareable catalog of API
mistakes with correct alternatives. Works with any library.

## Quick Start: Discover Workflow Patterns

In Claude Code:

```
/conversation-miner mine my history
```

Claude scans your sessions, finds repeating workflows, and helps you turn
them into reusable skill files.

## Install

For use as a standalone CLI (no slash commands):

```bash
uv tool install git+https://github.com/ianhi/claudephant
```

For slash commands + development:

```bash
git clone git@github.com:ianhi/claudephant.git
cd claudephant
uv tool install -e .
```

## CLI Usage

```bash
claudephant list                                  # see all sessions
claudephant list -p myproject --since 2026-03-01  # filter by project/date
claudephant session abc123 --tools                # inspect a session
claudephant mistakes -k pandas                    # error turns mentioning pandas
claudephant prompts | sort | uniq -c | sort -rn   # find repeated prompts
```

### Commands

| Command | Purpose |
|---------|---------|
| `list` | List all sessions (ID, date, turns, branch, project, first prompt) |
| `session ID` | Inspect a session with composable filters |
| `mistakes` | Extract error and correction turns as JSON |
| `prompts` | All user prompts across sessions, one per line |
| `summary` | Cross-session analysis (common prompts, tool usage, hot files) |

### Session Filters

All filters compose — combine them freely:

```bash
claudephant session abc123 --edits --file auth.py     # edits to one file
claudephant session abc123 --bash --tail 5             # last 5 shell commands
claudephant session abc123 --grep "test" --tools       # test-related turns
claudephant session abc123 --json | jq .               # structured output
```

| Flag | Shows |
|------|-------|
| `--tools` | Tool call names and key inputs |
| `--edits` | Only file modifications (Edit/Write) |
| `--bash` | Only shell commands and output |
| `--full` | Everything including tool results |
| `--json` | Machine-readable JSON |
| `--grep PATTERN` | Turns matching a pattern |
| `--file PATH` | Turns that touched a file |
| `--tool NAME` | Turns using a specific tool |
| `--turn N` / `--turns N-M` | Specific turn(s) |
| `--head N` / `--tail N` | First/last N turns |

### Mistakes Command

```bash
claudephant mistakes -k pandas -k DataFrame    # pandas errors across all projects
claudephant mistakes -p mylib --since 2026-03  # recent project errors
claudephant mistakes > /tmp/mistakes.json      # save for analysis
```

Each turn is tagged with what triggered it:
- `user_correction` — you told Claude it was wrong (highest signal)
- `error` — tool result had a traceback
- `self_correction` — Claude acknowledged a mistake

## Slash Commands

Available when you open Claude Code in this repo:

| Command | What it does |
|---------|-------------|
| `/mine-api-mistakes` | Find API mistakes Claude makes with any library |
| `/conversation-miner` | Discover workflow patterns and build skills |

## Pre-built Skill Files

The [scientific-python-skills](https://github.com/ianhi/scientific-python-skills)
repo has skill files for icechunk, zarr, xarray, pandas, numpy, and matplotlib —
built using this pipeline. Install without running the mining:

```bash
mkdir -p .claude/skills
curl -o .claude/skills/zarr.md \
  https://raw.githubusercontent.com/ianhi/scientific-python-skills/main/skills/zarr.md
```

## For AI Agents

Run `claudephant --agent-help` for a comprehensive reference (~1k tokens)
covering all commands, filters, output format, and filtering rules.

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) (for slash commands)
- Conversation history in `~/.claude/projects/`
