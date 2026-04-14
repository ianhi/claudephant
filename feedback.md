# Feedback: Running `/mine-api-mistakes` end-to-end

Notes from running the full workflow on 2026-04-14, mining zarr API mistakes
across 68 sessions / 982 error turns.

## Problem: every run requires ad-hoc Python to wrangle JSON

The `claudephant mistakes` output is a single JSON array on one line. The
workflow *always* needs to: count turns, check signal breakdown, prioritize
high-value turns, split into batches, and pretty-print for subagent
consumption. Every one of those steps currently requires a throwaway Python
script. The prompt even prescribes the batching algorithm — a sign that this
logic belongs in the tool, not in the agent's improvisation.

### Suggested CLI changes

**`--pretty`** (or make it the default for TTY stdout)

The minified single-line JSON output is hostile to every downstream consumer:
- Subagents using the `Read` tool can't paginate it (Read uses line-based
  offset/limit; one line = entire file).
- `grep` matches the entire file on every hit.
- `jq` works fine, but subagents don't have `jq`.

Pretty-printing by default (or when stdout is a TTY) costs negligible disk
and eliminates a manual `python -m json.tool` step that was required every
run.

**`--stats`**

Print a summary without dumping the full JSON. Something like:

```
Sessions matched: 68 / 114
Error turns: 982
  user_correction: 46
  error: 734
  self_correction: 257
Top projects:
  icechunk-ian: 24 sessions, 412 turns
  icepyck: 5 sessions, 98 turns
  ...
```

This lets the agent (or a human) decide whether to add `-k` filters or
proceed with full extraction before waiting for the slow scan. Currently,
the only way to get these numbers is to run the full extraction, then parse
the JSON with Python.

A `--dry-run` variant that just counts matching sessions/turns without
extracting content would be even faster, but `--stats` on the full output
covers most of the need.

**`--split N --out-dir DIR`**

Split output into N balanced batch files, writing `DIR/batch_0.json` through
`DIR/batch_{N-1}.json`. "Balanced" means roughly equal total error turns per
batch, not equal sessions. Include built-in priority ordering: keep
`user_correction` turns first, then `error`, then `self_correction`. Pair
with `--max-per-session M` to cap turns per session (default: 25).

This is the single highest-leverage change. The prompt prescribes this exact
algorithm in prose, and I had to translate it into a Python script every time.
The split logic is deterministic and identical across runs — it belongs in the
CLI.

The output files should be pretty-printed (multi-line JSON) so subagents can
read them with the `Read` tool without an extra formatting step.

**`--top N`**

Emit only the N highest-value turns across all sessions, ranked by signal
priority. For small-to-medium datasets (under ~100 turns), this lets the
agent skip batching entirely and analyze everything in one pass. Saves
spinning up 5 subagents when the data fits in one context window.

## Problem: prompt uses `/tmp/` for intermediate files

The prompt says:

```
claudephant mistakes [OPTIONS] > /tmp/mistakes.json 2>/tmp/mistakes.log
```

Subagents spawned by Claude Code cannot read `/tmp/` — their file access is
scoped to the project directory and explicitly listed additional working
directories. This caused two full rounds of wasted subagent launches (12
agents total, all failing on permission errors) before I figured out I needed
to copy files into the project directory.

**Fix:** The prompt should use a project-relative directory:

```
mkdir -p .mistakes-tmp
claudephant mistakes [OPTIONS] > .mistakes-tmp/mistakes.json 2>.mistakes-tmp/mistakes.log
```

Or, if `--split` and `--out-dir` are implemented, just:

```
claudephant mistakes [OPTIONS] --split 5 --out-dir .mistakes-tmp/
```

The `.mistakes-tmp/` directory (or `.claudephant-tmp/`, whatever) should be
added to `.gitignore` by the prompt or the tool.

## Problem: subagents can't read project source for API verification

Step 4 of the prompt says to read the library's source to verify "correct"
alternatives. Subagents couldn't read `~/Documents/dev/zarr-python/` either —
same permission scoping issue. The main agent can (if the user approves), but
delegating this to a subagent doesn't work.

Two options:
1. The prompt should have the *main* agent read the API surface and include a
   summary in each subagent's prompt (not a separate subagent).
2. Or: skip source reading entirely and rely on the main agent's knowledge to
   verify during the compilation step (Step 4). This is what actually happened
   in practice.

## Minor observations

- **Subagent model should be explicit in the prompt.** The prompt says "launch
  haiku or sonnet subagents" but doesn't specify which. Being explicit
  (e.g., "use sonnet for analysis subagents") avoids ambiguity and ensures
  consistent quality.

- **Content truncation in the output** (assistant text to 2000 chars, tool
  results to 1000 chars) was occasionally limiting. Some patterns were only
  identifiable from the error message in `tool_results`, which was cut off.
  Consider raising the tool result limit to ~2000 chars, or making it
  configurable via `--tool-result-chars N`.

- **The `self_correction` signal has a very high false positive rate** in
  practice. Most "self correction" turns were ordinary explanations containing
  phrases like "should be" or "instead of." The prompt already warns about
  this, which is good — but it might be worth tightening the signal detection
  or adding a confidence score.

## Summary

| Change | Type | Effort | Impact |
|--------|------|--------|--------|
| Pretty-print JSON output | CLI | Small | Unblocks subagent reads |
| `--stats` summary | CLI | Small | Avoids blind extraction |
| `--split N --out-dir DIR` | CLI | Medium | Eliminates all batching scripts |
| `--max-per-session N` | CLI | Small | Pairs with `--split` |
| `--top N` | CLI | Small | Skips batching for small data |
| Prompt: use CWD not `/tmp/` | Prompt | Trivial | Fixes subagent permissions |
| Prompt: main agent reads API surface | Prompt | Trivial | Fixes source reading |
| Prompt: specify subagent model | Prompt | Trivial | Consistency |
