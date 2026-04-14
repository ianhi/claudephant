You are running the API mistake mining pipeline. This scans the user's Claude Code
conversation history, finds sessions where Claude made mistakes with specific
library APIs, and produces a shareable mistake catalog.

## What to do

Run the full pipeline automatically. Do not ask the user to run commands — you
run everything. Report progress as you go.

### 1. Extract error turns

Run this, passing through any $ARGUMENTS the user provided:

```
uv run python scripts/extract_api_mistakes.py $ARGUMENTS
```

If no arguments were given, run it with no flags (scans all icechunk/zarr/xarray
sessions). This produces `scripts/api_mistakes_data/` with one JSON per session.

Report how many sessions were scanned and how many error turns were found.

### 2. Prepare batches

```
uv run python scripts/prepare_batches.py
```

This scores turns by informativeness and distributes them across 6 balanced
batches in `scripts/api_mistakes_batches/`.

### 3. Analyze in parallel

Launch 6 sonnet subagents in the background, one per batch file. Each agent
should read its batch and identify concrete API mistake patterns. Use this
prompt for each:

> Read `scripts/api_mistakes_batches/batch_N.json`. These are turns from Claude
> Code sessions where errors occurred while using icechunk, zarr-python, or
> xarray APIs.
>
> Find specific, concrete API mistakes. For each pattern:
> - **Pattern name**: short descriptive name
> - **Wrong code**: what Claude wrote (exact)
> - **Right code**: what the correct approach is
> - **Error**: the error message or user correction
> - **Count**: how many times you saw this in the batch
>
> Skip generic Python errors, git issues, formatting, CI config. Focus on wrong
> API calls, wrong arguments, outdated patterns, lifecycle confusion, and
> over-specific internal imports.

### 4. Compile the catalog

Once all 6 agents report back, merge their findings into a single catalog:

- Deduplicate patterns that appeared in multiple batches
- Rank by frequency (how many occurrences) and severity
- Group into categories: lifecycle mistakes, async/sync confusion,
  over-specification, v2-to-v3 migration, etc.
- For each pattern, include: wrong code, correct code, error message, count

Write the catalog to `scripts/api_mistake_catalog.md`. Use the format from the
existing file at that path as a template.

### 5. Produce shareable output

The catalog contains session IDs and local paths — strip these for the shareable
version. Create `scripts/api_mistakes_shareable.md` with:

- No session IDs, timestamps, or local file paths
- Just the patterns: name, wrong code, right code, explanation, frequency
- A "Meta-patterns" section grouping mistakes by root cause
- A header noting how many sessions/turns were analyzed and the date range

Tell the user: "The shareable catalog is at `scripts/api_mistakes_shareable.md`.
You can paste it into a CLAUDE.md, a skill file, or share it directly."

## Customizing for other libraries

Tell the user: to mine for a different library, edit `API_KEYWORDS` in
`scripts/extract_api_mistakes.py` to match your library's API surface, and
adjust the `--project` filter.

$ARGUMENTS
