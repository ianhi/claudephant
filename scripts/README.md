# Mining API Mistakes from Claude Code History

Find what Claude gets wrong when working with your libraries. This scans your
Claude Code conversation history, finds every time Claude used an API
incorrectly, and compiles a catalog of mistake patterns you can share.

Works with any library — pandas, fastapi, your internal SDK, anything Claude
has used and made mistakes with.

## Quick Start

### 1. Clone and install

```bash
git clone git@github.com:ianhi/claudephant.git
cd claudephant
uv tool install -e .
```

### 2. Open Claude Code in this directory

```bash
claude
```

### 3. Run the command

For a specific library:

```
/mine-api-mistakes mine mistakes Claude makes with pandas
```

Or scan everything:

```
/mine-api-mistakes
```

That's it. Claude does the rest — it figures out what keywords to search for,
extracts error turns from your history, fans out parallel subagents to analyze
patterns, and compiles a shareable markdown catalog.

### 4. Use the output

Claude writes `api_mistakes.md` in the current directory. You can:

- **Paste it into a CLAUDE.md** in any project so Claude avoids those mistakes
- **Save it as `.claude/skills/mistakes.md`** for automatic loading
- **Send it to co-workers** — the output has no personal data

## Example output

```markdown
## group.create_array() does not accept data= with explicit shape/dtype

**Frequency:** 3 occurrences across 3 sessions

    # WRONG (zarr v2 pattern)
    group.create_array("arr", shape=(3,), dtype="i4", data=np.array([1, 2, 3]))

    # CORRECT (zarr v3)
    arr = group.create_array("arr", shape=(3,), dtype="i4")
    arr[:] = np.array([1, 2, 3])
```

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

# Filter by library keywords (catches usage in ALL projects)
claudephant mistakes -k pandas -k DataFrame -k pd

# Filter by project directory
claudephant mistakes -p myproject

# Recent sessions only
claudephant mistakes --since 2026-03-01
```

Keywords (`-k`) search turn content — since Python libraries are imported by
name (`import pandas as pd`), `-k pandas` catches usage across every project,
not just ones named "pandas".

### The slash command

`/mine-api-mistakes` wraps the CLI tool with agent intelligence:

1. **Extract** — runs `claudephant mistakes` once, saves to a file
2. **Assess** — checks volume; if small, analyzes directly
3. **Analyze** — for large datasets, fans out parallel subagents to find
   patterns, weighting user corrections highest
4. **Compile** — merges findings into a shareable markdown catalog

## Pre-built skill files

The [scientific-python-skills](https://github.com/ianhi/scientific-python-skills)
repo has skill files for icechunk, zarr, and xarray that were built using this
pipeline. Install them directly without running the mining:

```bash
mkdir -p .claude/skills
curl -o .claude/skills/zarr.md \
  https://raw.githubusercontent.com/ianhi/scientific-python-skills/main/skills/zarr.md
curl -o .claude/skills/icechunk.md \
  https://raw.githubusercontent.com/ianhi/scientific-python-skills/main/skills/icechunk.md
```

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code)
- Conversation history in `~/.claude/projects/` (you need to have used Claude
  Code with the target library — the more sessions the better)
