# Mining API Mistakes from Claude Code History

Find what Claude gets wrong when working with your libraries. This uses
`claudephant mistakes` to extract error turns from your conversation history,
then parallel AI analysis to identify recurring mistake patterns.

Works with any library — pandas, fastapi, your internal SDK, anything Claude
has used and made mistakes with.

## Quick Start

```bash
git clone https://github.com/ianhi/claudephant
cd claudephant
uv tool install -e .
```

Then open Claude Code and run:

```
/mine-api-mistakes
```

Or tell Claude what you want:

```
/mine-api-mistakes mine mistakes Claude makes with the pandas API
```

Claude handles everything: extraction, analysis, and compilation.

## How It Works

### The CLI tool

`claudephant mistakes` extracts turns where something went wrong. Each turn is
tagged with what triggered it:

- **`user_correction`** — you told Claude it was wrong (highest signal)
- **`error`** — a tool result had a traceback or error
- **`self_correction`** — Claude acknowledged its own mistake

```bash
# All errors across all sessions
claudephant mistakes

# Filter by project
claudephant mistakes -p myproject

# Filter by library keywords
claudephant mistakes -k pandas -k DataFrame -k 'pd\.'

# Recent sessions only
claudephant mistakes -p mylib --since 2026-03-01

# Pipe through jq for just user corrections
claudephant mistakes | jq '.[].turns[] | select(.signal[] == "user_correction")'
```

### The slash command

`/mine-api-mistakes` wraps the CLI tool with agent intelligence:

1. **Discover** — lists your sessions to understand what's available
2. **Extract** — runs `claudephant mistakes` with appropriate filters
3. **Analyze** — fans out parallel subagents to find patterns, weighting
   user corrections highest
4. **Compile** — produces a shareable markdown catalog

## What You Get

A markdown file listing recurring mistake patterns, ranked by frequency:

```markdown
## Moves require rearrange_session, not writable_session

**Frequency:** 4+ occurrences across 4 sessions

    # WRONG
    session = repo.writable_session("main")
    session.move("/a", "/b")       # IcechunkError: need rearrange session

    # CORRECT
    session = repo.rearrange_session("main")
    session.move("/a", "/b")
```

## What To Do With It

**Paste into a CLAUDE.md** so Claude avoids those mistakes in future sessions.

**Save as a skill file.** Put it in `.claude/skills/` in any project. The
[scientific-python-skills](https://github.com/ianhi/scientific-python-skills)
repo has pre-built skill files for icechunk, zarr, and xarray produced this way:

```bash
mkdir -p .claude/skills
curl -o .claude/skills/icechunk.md \
  https://raw.githubusercontent.com/ianhi/scientific-python-skills/main/skills/icechunk.md
```

**Share with your team.** The output has no personal data — just patterns and
code examples.

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- Claude Code conversation history in `~/.claude/projects/`
