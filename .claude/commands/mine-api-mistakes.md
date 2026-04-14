Mine Claude Code conversation history for common API mistakes with scientific Python libraries (icechunk, zarr-python, xarray).

## What this does

1. Uses `claudephant` to scan your conversation history for sessions involving target libraries
2. Extracts turns containing errors, self-corrections, and user corrections
3. Scores and samples the most informative error turns per session
4. Fans out parallel sonnet subagents to analyze batches for mistake patterns
5. Compiles a consolidated catalog of API mistakes with correct alternatives

## Instructions

Run the extraction and batching pipeline, then analyze with subagents.

### Step 1: Extract error turns

Run the extraction script. You can filter by project name and date:

```
uv run python scripts/extract_api_mistakes.py
```

Or with filters:
```
uv run python scripts/extract_api_mistakes.py --project icechunk --since 2026-03-01
```

This creates `scripts/api_mistakes_data/` with one JSON file per session containing only API-relevant error turns.

### Step 2: Prepare batches for parallel analysis

```
uv run python scripts/prepare_batches.py
```

This creates `scripts/api_mistakes_batches/` with 6 balanced batch files, each containing sampled turns scored by informativeness (error tracebacks > self-corrections > user corrections).

### Step 3: Launch parallel subagents

For each batch file in `scripts/api_mistakes_batches/batch_*.json`, launch a sonnet subagent with this prompt template:

> You are analyzing Claude Code conversation transcripts to find common API mistakes with icechunk, zarr-python, and xarray.
>
> Read the batch file at `scripts/api_mistakes_batches/batch_N.json`.
>
> For each mistake pattern found, provide:
> - Pattern name
> - What Claude did wrong (exact code)
> - What the correct approach is (exact code)
> - Error message or user correction as evidence
> - How many times you saw it
>
> Focus on REAL API mistakes: wrong method names, wrong arguments, outdated patterns, lifecycle confusion, over-specific imports. Skip generic Python errors, git issues, formatting, CI config.

Launch all 6 in parallel as background agents. Each batch is ~170KB, well within context.

### Step 4: Compile the catalog

Once all agents report back, merge their findings:
- Deduplicate patterns that appear across batches
- Rank by frequency and impact
- Group into categories (lifecycle, async/sync, over-specification, v2->v3 migration)
- Write to `scripts/api_mistake_catalog.md`

The existing catalog at `scripts/api_mistake_catalog.md` shows the expected output format.

### Step 5: Update skill files

If you have a `scientific-python-skills` checkout, merge new findings into the existing skill files:
- `skills/icechunk.md` — icechunk-specific patterns
- `skills/zarr.md` — zarr v3 patterns
- `skills/xarray.md` — xarray integration patterns

## Customizing

To mine mistakes for a different library:
1. Edit `API_KEYWORDS` in `extract_api_mistakes.py` to match your library's API surface
2. Adjust `--project` filter to match your project directories
3. Run the same pipeline

$ARGUMENTS: Optional: --project NAME --since YYYY-MM-DD (filters passed to extraction)
