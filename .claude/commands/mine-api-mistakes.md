You are mining the user's Claude Code conversation history for API mistakes
Claude makes with specific libraries. Your goal: produce a shareable catalog
of recurring mistake patterns with correct alternatives.

## Understanding the request

The user may specify libraries, project names, or nothing. Examples:
- "mine mistakes with pandas" → use `-k pandas -k 'pd\.' -k DataFrame`
- "--project mylib" → pass through
- No arguments → scan everything

## Step 1: Discover what's available

```
claudephant list
```

Skim the output to understand what projects and sessions exist. Use this to
decide filtering strategy. Remember: a library may be used in projects not
named after it (e.g. xarray used in a climate-analysis project).

## Step 2: Extract error turns

```
claudephant mistakes [OPTIONS] > mistakes.json
```

Options:
- `-p/--project NAME` — filter by project directory (substring, repeatable)
- `-k/--keywords PATTERN` — only turns matching these regex patterns (repeatable)
- `-s/--since DATE` — recent sessions only

Each turn in the output has a `signal` field:
- `user_correction` — **highest value**: the user told Claude it was wrong
- `error` — a tool result had a traceback or error
- `self_correction` — Claude acknowledged its own mistake

Cast a wide net. You can filter later. If the user named a specific library,
use `-k` with the library name, common abbreviations, and key class names.

Report how many sessions and error turns were found.

## Step 3: Assess the data volume

Read `mistakes.json` to check the size. If it's small enough to analyze
directly (under ~100 turns), skip batching and go straight to Step 5.

If it's large:

## Step 4: Batch and analyze in parallel

Write a quick Python script to split the data into 4-6 batches, sampling the
most informative turns per session. Prioritize:
1. Turns with `user_correction` signal (highest weight)
2. Turns with `error` signal containing AttributeError/TypeError (wrong API)
3. Turns with `self_correction` signal

Launch sonnet subagents in parallel, one per batch. Each should find concrete
API mistake patterns: wrong code, correct code, error message, frequency.

If the user has a local checkout of the library being analyzed, read key source
files to understand the current API. This helps distinguish real mistakes from
correct-but-unfamiliar code.

## Step 5: Compile the catalog

Merge all findings into `api_mistakes.md`:

- Deduplicate patterns across batches
- Rank by frequency and severity
- Group into categories (e.g. lifecycle, async/sync, over-specification,
  version migration)
- Each entry: pattern name, wrong code, correct code, error message, frequency
- Add a "Meta-patterns" section grouping mistakes by root cause

Strip session IDs and local paths — the output should be shareable.

Tell the user what they can do with it:
- Paste into a CLAUDE.md so Claude avoids these mistakes
- Save as a `.claude/skills/` file
- Share with teammates

$ARGUMENTS
