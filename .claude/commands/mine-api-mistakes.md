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

## Step 2: Assess volume, then extract

First, get a quick overview with `--stats` (this scans sessions but doesn't
dump JSON):

```
claudephant mistakes [OPTIONS] --stats
```

This prints session counts, signal breakdown, and top projects. Use it to
decide whether to add `-k` filters or proceed.

**Then extract once.** Don't run extraction before `--stats` — both scan all
sessions, so running both is redundant. After `--stats`, choose your approach:

- **Small data (under ~50 error turns):** Use `--top 50` and skip batching —
  go straight to Step 4.
- **Medium data (50–100 turns):** Use `--top 100` and go to Step 4.
- **Large data (100+ turns):** Do a quick first pass with `--top 30` to get
  the highest-value turns (mostly `user_correction`). Analyze those yourself
  or with a single subagent. If the patterns are well-covered, stop. If you
  suspect more patterns exist in the tail, proceed to Step 3.

## Step 3: Batch and analyze in parallel

Use the built-in `--split` to create balanced batch files:

```
claudephant mistakes [OPTIONS] --split 5 --out-dir .mistakes-tmp
```

This writes `.mistakes-tmp/batch_0.json` through `.mistakes-tmp/batch_4.json`,
balanced by total error turns per batch. Turns are capped at 25 per session
(override with `--max-per-session N`) and prioritized: `user_correction` first,
then `error`, then `self_correction`.

**Use subagents for analysis, not grep/jq.** Grep can count signals but can't
understand code patterns. Launch subagents in parallel, one per batch. Use
haiku for initial triage or sonnet for deeper analysis — the user may specify
a preference. Each subagent reads its batch file and identifies concrete API
mistake patterns: wrong code, correct code, error message, frequency.

If the user has a local checkout of the library being analyzed (check common
locations like `~/Documents/dev/LIBNAME` or `../LIBNAME`), **read key source
files yourself (main agent)** to understand the current API surface, then
include a brief API summary in each subagent's prompt. Subagents cannot read
files outside the project directory — don't delegate source reading to them.

### Subagent skip-criteria

Most turns in a batch will be false positives — errors in projects that happen
to use the target library but where the actual mistake is unrelated. The
subagent prompt must include guidance on how to triage efficiently. Adapt this
to the specific library being analyzed:

> "Triage each turn by signal type:
>
> - **`user_correction` turns**: Always read carefully. The user may be
>   correcting a bug, pointing out a better idiom, or teaching Claude
>   something about the API. These are high-value even when there's no error.
> - **`error` turns**: Read the traceback/error first. If the error doesn't
>   involve [LIBRARY] APIs — e.g. it's a linting failure, a build tool issue,
>   or an unrelated test — skip it. But don't skip just because the traceback
>   comes from a different package; [LIBRARY] errors can surface through
>   wrapper libraries, backends, or downstream consumers.
> - **`self_correction` turns**: Skim only. High false-positive rate. Only
>   analyze if the correction is clearly about [LIBRARY] usage."

## Step 4: Compile the catalog

**Check for an existing catalog first.** If `api_mistakes.md` already exists,
read it before compiling. Tell subagents what patterns are already documented
so they focus on NEW patterns. Update the existing file incrementally rather
than rewriting from scratch.

Merge all findings into `api_mistakes.md` in the current directory:

- Deduplicate patterns that appeared across multiple batches/sessions
- Rank by frequency and severity
- Group into categories (e.g. lifecycle, async/sync, over-specification,
  version migration, wrong method names)
- Each entry: pattern name, wrong code, correct code, error message, frequency
- Include corrections and idiom improvements from `user_correction` turns,
  not just errors — "here's a better way" is as valuable as "this is broken"
- Add a "Meta-patterns" section grouping mistakes by root cause
- Include a header with: date range of sessions analyzed, number of sessions
  scanned, number of error turns found

Strip session IDs and local file paths — the output should be shareable.

Tell the user what they can do with it:
- Paste into a CLAUDE.md so Claude avoids these mistakes in future sessions
- Save as a `.claude/skills/` file for automatic loading
- Share with teammates or post publicly

$ARGUMENTS
