You are mining the user's Claude Code conversation history for API mistakes
Claude makes with specific libraries. Your goal: produce a shareable catalog
of recurring mistake patterns with correct alternatives.

## Understanding the request

The user may specify libraries, project names, or nothing. Examples:
- "mine mistakes with pandas" → use `-k pandas -k pd -k DataFrame`
- "--project mylib" → pass through to extraction
- No arguments → scan everything, all errors

## Step 0: Check tool availability

Run `claudephant --help` to verify the tool is installed. If it fails, run:

```
uv tool install -e .
```

Then retry.

## Step 1: Discover what's available

```
claudephant list
```

Look at the output to understand what projects and sessions exist. Note project
names and session counts. Use this to decide what `-p` and `-k` flags to use.

Remember: a library may be used in projects not named after it (e.g. xarray
used in a climate-analysis project). When in doubt, skip `-p` and rely on `-k`.

## Step 2: Extract error turns

```
claudephant mistakes [OPTIONS] > mistakes.json
```

Options:
- `-p/--project NAME` — filter by project directory (substring, repeatable)
- `-k/--keywords PATTERN` — only turns matching these patterns (repeatable)
- `-s/--since DATE` — recent sessions only

Each turn in the output has a `signal` list with one or more of:
- `user_correction` — **highest value**: the user told Claude it was wrong
- `error` — a tool result had a traceback or error
- `self_correction` — Claude acknowledged its own mistake

A single turn can have multiple signals (e.g. both `error` and `user_correction`).

Cast a wide net. If the user named a specific library, use `-k` with the library
name, common abbreviations (`pd`, `xr`, `np`), and key class names.

Report how many sessions and error turns were found.

**If no results:** Tell the user no matching errors were found. Suggest trying
without `-k` to verify sessions exist, or broadening the search. Don't proceed
with empty data.

## Step 3: Assess the data volume

Read `mistakes.json` to check the size. If it's small enough to analyze
directly (under ~100 error turns total), skip batching and go straight to Step 5.

If it's large:

## Step 4: Batch and analyze in parallel

Write a short Python script (in /tmp, not in the repo) to split `mistakes.json`
into 4-6 batches, sampling the most informative turns per session. Prioritize:
1. Turns with `user_correction` signal (highest weight — a human said it was wrong)
2. Turns with `error` signal containing AttributeError/TypeError (classic wrong-API)
3. Turns with `self_correction` signal

Launch sonnet subagents in parallel, one per batch. Each should find concrete
API mistake patterns: wrong code, correct code, error message, frequency.

If the user has a local checkout of the library being analyzed, read key source
files to understand the current API surface. This helps distinguish real mistakes
from correct-but-unfamiliar code, and lets you verify the "correct" alternative
is actually correct.

## Step 5: Compile the catalog

Merge all findings into `api_mistakes.md` in the current directory:

- Deduplicate patterns that appeared across multiple batches
- Rank by frequency and severity
- Group into categories (e.g. lifecycle, async/sync, over-specification,
  version migration, wrong method names)
- Each entry: pattern name, wrong code, correct code, error message, frequency
- Add a "Meta-patterns" section grouping mistakes by root cause
- Include a header with: date range of sessions analyzed, number of sessions
  scanned, number of error turns found

Strip session IDs and local file paths — the output should be shareable.

Tell the user what they can do with it:
- Paste into a CLAUDE.md so Claude avoids these mistakes in future sessions
- Save as a `.claude/skills/` file for automatic loading
- Share with teammates or post publicly

$ARGUMENTS
