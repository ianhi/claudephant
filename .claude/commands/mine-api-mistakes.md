You are mining the user's Claude Code conversation history for API mistakes
Claude makes with specific libraries. Your goal: produce a shareable catalog
of recurring mistake patterns with correct alternatives.

## Understanding the request

The user may specify libraries, project names, or nothing. Examples:
- "mine mistakes with pandas" → use `-k pandas -k pd -k DataFrame`
- "--project mylib" → pass through to extraction
- No arguments → scan everything, all errors

**Key insight:** `-k` (keywords) searches turn content, not project names. Since
Python libraries are imported by name (`import zarr`, `import pandas as pd`),
`-k` with the library name catches usage across ALL projects. This is almost
always better than `-p`, which only filters by project directory name.

Use `-k libraryname` as the primary filter. Add `-p` only if the user wants to
narrow to specific projects.

## Step 1: Check tool and extract

First verify the tool works:

```
claudephant list | head -5
```

If `claudephant` is not found, run `uv tool install -e .` first.

Then extract error turns. **Run extraction once, save to a file, and do all
subsequent analysis on that file.** Extraction scans every session and is slow —
never re-run it to pipe into different filters.

Use a project-relative directory so subagents can read the output files:

```
mkdir -p .mistakes-tmp
claudephant mistakes [OPTIONS] > .mistakes-tmp/mistakes.json 2>.mistakes-tmp/mistakes.log
```

Options:
- `-k/--keywords PATTERN` — only turns matching these patterns (repeatable)
- `-p/--project NAME` — filter by project directory (substring, repeatable)
- `-s/--since DATE` — recent sessions only
- `--stats` — print a summary (session/turn counts, signal breakdown, top projects) without full JSON
- `--top N` — emit only top N turns by signal priority (skip batching for small data)
- `--split N --out-dir .mistakes-tmp` — split into N balanced batch files directly
- `--max-per-session N` — cap turns per session (default 25 with --split)

Each turn in the output has a `signal` list with one or more of:
- `user_correction` — **highest value**: the user told Claude it was wrong
- `error` — a tool result had a traceback or error
- `self_correction` — lowest value, high false-positive rate (patterns like
  "should be" and "instead of" fire on ordinary explanations, not just mistakes).
  Be skeptical of turns that only have this signal.

A single turn can have multiple signals (e.g. both `error` and `user_correction`).

Cast a wide net. If the user named a specific library, use `-k` with the library
name (which matches `import libraryname` statements), common abbreviations
(`pd`, `xr`, `np`), and key class names. Don't use `-p` unless the user
specifically asked to narrow by project — the library is likely used across
multiple projects.

**Note:** Content is truncated in the output (assistant text to 2000 chars, tool
results to 1000 chars). Truncated turns may lack full context — if a pattern
looks interesting but the context is cut off, use `claudephant session ID --turn N --full`
to get the complete turn.

**If scanning many sessions:** Tell the user it may take a minute. If scanning
100+ sessions with no filters, suggest adding `-k` to speed things up.

Report how many sessions and error turns were found.

**If no results:** Tell the user no matching errors were found. Suggest trying
without `-k` to verify sessions exist, or broadening the search. Don't proceed
with empty data.

## Step 2: Assess the data volume

First, get a quick overview with `--stats`:

```
claudephant mistakes [OPTIONS] --stats
```

This prints session counts, signal breakdown, and top projects without dumping
JSON. Use it to decide whether to add `-k` filters or proceed with full
extraction.

Read `.mistakes-tmp/mistakes.json` to check the size. If it's small enough to
analyze directly (under ~100 error turns total), use `--top 100` and skip
batching — go straight to Step 4.

If it's large (100+ error turns):

## Step 3: Batch and analyze in parallel

Use the built-in `--split` to create balanced batch files:

```
claudephant mistakes [OPTIONS] --split 5 --out-dir .mistakes-tmp
```

This writes `.mistakes-tmp/batch_0.json` through `.mistakes-tmp/batch_4.json`,
balanced by total error turns per batch. Turns are capped at 25 per session
(override with `--max-per-session N`) and prioritized: `user_correction` first,
then `error`, then `self_correction`.

**Use sonnet subagents for analysis, not grep/jq.** Grep can count signals but
can't understand code patterns. Launch sonnet subagents in parallel, one per
batch. Each reads its batch file and identifies concrete API mistake patterns:
wrong code, correct code, error message, frequency. Subagents are cheap and
can understand context that text matching cannot.

If the user has a local checkout of the library being analyzed (check common
locations like `~/Documents/dev/LIBNAME` or `../LIBNAME`), **read key source
files yourself (main agent)** to understand the current API surface, then
include a brief API summary in each subagent's prompt. Subagents cannot read
files outside the project directory — don't delegate source reading to them.

## Step 4: Compile the catalog

Merge all findings into `api_mistakes.md` in the current directory:

- Deduplicate patterns that appeared across multiple batches/sessions
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
