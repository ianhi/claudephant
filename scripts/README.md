# Mining API Mistakes from Claude Code History

Find what Claude gets wrong when working with your libraries. This pipeline
scans your Claude Code conversation history, extracts turns where API errors
occurred, and uses parallel AI analysis to identify recurring mistake patterns.

## Quick Start

```bash
git clone https://github.com/ianhi/claudephant
cd claudephant
```

Then open Claude Code and run:

```
/mine-api-mistakes
```

That's it. Claude runs the full pipeline (extract, batch, analyze, compile) and
produces a shareable markdown catalog of mistake patterns.

## What You Get

A markdown file (`scripts/api_mistakes_shareable.md`) listing every recurring
mistake pattern, ranked by frequency. Each entry has:

- The **wrong code** Claude wrote
- The **correct alternative**
- The **error message** that resulted
- How many times it happened

Example entry:

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

## What You Can Do With It

**Paste into a CLAUDE.md.** Drop the catalog (or the patterns that matter most)
into your project's `CLAUDE.md` so Claude avoids those mistakes in future
sessions.

**Turn it into a skill file.** The
[scientific-python-skills](https://github.com/ianhi/scientific-python-skills)
repo has pre-built skill files for icechunk, zarr, and xarray that were produced
this way. Copy them to `.claude/skills/` in any project:

```bash
mkdir -p .claude/skills
curl -o .claude/skills/icechunk.md \
  https://raw.githubusercontent.com/ianhi/scientific-python-skills/main/skills/icechunk.md
curl -o .claude/skills/zarr.md \
  https://raw.githubusercontent.com/ianhi/scientific-python-skills/main/skills/zarr.md
```

**Share with your team.** The shareable catalog has no personal data (session
IDs and local paths are stripped). Send it to co-workers or post it in a repo.

## Filtering

Pass arguments to narrow the search:

```
/mine-api-mistakes --project mylib --since 2026-01-01
```

- `--project NAME` filters sessions by project directory name (substring match)
- `--since YYYY-MM-DD` filters to sessions after a date

## Mining for Other Libraries

The default targets are icechunk, zarr-python, and xarray. To mine mistakes for
a different library:

1. Edit `API_KEYWORDS` in `scripts/extract_api_mistakes.py` — add your library's
   function names, class names, and common import patterns
2. Run `/mine-api-mistakes --project yourlib`

The rest of the pipeline (batching, analysis, compilation) works unchanged.

## How It Works

The pipeline has four stages:

```
┌──────────────────────────────────────────────────────────────┐
│ 1. EXTRACT                                                   │
│    claudephant scans ~/.claude/projects/**/*.jsonl            │
│    Filters to sessions matching target libraries             │
│    Keeps only turns with errors, corrections, or retries     │
│    → scripts/api_mistakes_data/{session_id}.json             │
├──────────────────────────────────────────────────────────────┤
│ 2. BATCH                                                     │
│    Scores turns by informativeness:                          │
│      error tracebacks > self-corrections > user corrections  │
│    Samples top 25 per session                                │
│    Distributes across 6 balanced batches (~170KB each)       │
│    → scripts/api_mistakes_batches/batch_{0-5}.json           │
├──────────────────────────────────────────────────────────────┤
│ 3. ANALYZE (parallel)                                        │
│    6 sonnet subagents run simultaneously                     │
│    Each reads one batch and identifies mistake patterns      │
│    Reports: wrong code, correct code, error, frequency       │
├──────────────────────────────────────────────────────────────┤
│ 4. COMPILE                                                   │
│    Merges findings from all 6 agents                         │
│    Deduplicates, ranks by frequency, groups by category      │
│    → scripts/api_mistake_catalog.md (with session refs)      │
│    → scripts/api_mistakes_shareable.md (clean, no PII)       │
└──────────────────────────────────────────────────────────────┘
```

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- Claude Code conversation history in `~/.claude/projects/` (you need to have
  actually used Claude Code with the target libraries)
- The pipeline takes 3-5 minutes depending on how many sessions you have
