---
name: conversation-miner
description: |
  Use this skill when the user wants to mine Claude Code conversation history for
  repeatable patterns, build new skills from past sessions, or analyze their workflow.
  Trigger when the user says things like "find skill candidates", "what patterns repeat",
  "mine my conversations", "build a skill from history", "analyze my sessions",
  "make a skill from what I just did", "turn that into a skill", or
  "what do I keep asking Claude to do".
---

# Conversation Miner: Finding and Building Skills from History

You have access to `claudephant`, a CLI that parses Claude Code JSONL transcripts
from `~/.claude/projects/`. Use it to discover repeatable patterns worth converting
into Claude Code skills.

If you need a full reference for claudephant's commands and filters, run
`claudephant --agent-help` (~1k tokens). For subagents, include the output of
`--agent-help` in their prompt so they know how to use the tool.

## Two Entry Points

This skill supports two distinct modes. Ask the user which applies, or infer from context:

1. **"Mine my history"** — The user wants to discover patterns across many sessions.
   Start at Phase 1 (Discovery).
2. **"Turn that into a skill"** — The user just did something and wants to capture it
   immediately. Skip to Phase 2 (Deep Dive) using the current or most recent session.

## Context Conservation Strategy

Session transcripts are large and noisy. **Never read raw transcripts in the main
conversation.** Instead, delegate reading to cheap subagents (haiku or sonnet) that
process the details and return only the important parts.

The pattern: spawn many small subagents in parallel, each processing one session or
one aspect, returning a focused summary. The main agent synthesizes across summaries
and drives the conversation with the user.

See "Subagent Patterns" section below for specific prompts.

## Workflow Overview

This is an **incremental, collaborative process**. Never dump a wall of data.
Guide the user through discovery → refinement → extraction in stages.

## Phase 1: Discovery — Find Candidate Patterns

Use this phase when the user wants to explore broadly. Skip this entirely if the user
already knows what they want to turn into a skill.

### Step 1: Gather raw data (subagent)

Spawn a **haiku** subagent to run the broad analysis. Prompt:

```
Run these commands and return a structured summary:
1. `claudephant summary --project <name>`
2. `claudephant prompts --project <name>`

From the output, identify:
- Prompts that appear 3+ times (with exact count and example wording)
- Semantic clusters: prompts that ask for the same kind of thing even if
  worded differently (e.g. "fix the test" / "run tests and fix" = testing pattern)
- The top 5 most-used tools and what they suggest about workflow type
- Files modified across 3+ sessions

Return ONLY:
- A numbered list of candidate patterns (one line each + count + example prompts)
- The tool usage summary
- The hot files list
Do not return raw command output.
```

### Step 2: Present candidates to the user

Take the subagent's summary and present it. Prompts appearing 3+ times are strong
automatic candidates, but even a single occurrence can be worth capturing if the
user found it valuable or painful.

**CRITICAL: Stop here and confirm with the user before proceeding.**

- "I found N candidate patterns. Here are the top ones:"
- For each: one-line description + how many times it appeared + example prompts
- Ask: "Which of these would be most valuable as a reusable skill?"

Do NOT proceed to Phase 2 until the user picks a pattern.

## Phase 2: Deep Dive — Understand the Pattern

Once the user selects a pattern — or points you at a specific session — drill in.

### Step 3: Find the relevant sessions

Run `claudephant list --project <name>` yourself (this is small output).
Identify the session IDs to inspect — either the one the user pointed at, or 2-4
sessions that match the selected pattern.

### Step 4: Parallel session analysis (subagents)

Spawn one **haiku** or **sonnet** subagent **per session**, all in parallel. Each
subagent analyzes one session independently. Use haiku for shorter sessions
and sonnet for longer/more complex ones.

Prompt for each subagent:

```
Analyze this Claude Code session for reusable workflow patterns.

Run these commands and study the output:
1. `claudephant session <id> --tools` — the full flow with tool calls
2. `claudephant session <id> --edits` — file modifications
3. `claudephant session <id> --bash` — shell commands run

Return a structured analysis:

## Session Summary
One-paragraph description of what happened in this session.

## Workflow Steps
Numbered list of the key actions taken, in order. For each step note:
- What the user asked for or what triggered it
- What tool(s) were used
- What the outcome was

## Interesting Moments
Flag any of these if they appear:
- Points where the user corrected course or gave new direction
- Complex multi-step operations that would be hard to reproduce from memory
- Reusable command sequences or tool call patterns
- Error recovery patterns (something failed, then was fixed)

## Files Touched
List of files modified, with a one-line note on what changed in each.

## Candidate Skill Elements
What parts of this session look reusable? What would need to be parameterized?
```

### Step 5: Synthesize across sessions

Read the subagent summaries (NOT the raw transcripts — those stay in subagent
context). Look for:

For **multiple sessions** — what's common across them:
- **Common steps** — What sequence appears in every instance?
- **Inputs** — What varies between instances? (file paths, names, config values)
- **Interesting moments** that multiple subagents flagged

For a **single session** — what generalizes:
- **Steps** — Which are essential vs incidental?
- **Inputs** — What was specific to this instance vs what would change next time?

In both cases, also identify:
- **Decision points** — Where does the approach branch based on context?
- **Tool sequences** — What tools are always used and in what order?
- **Output format** — Is there a consistent deliverable?

### Step 6: Confirm the extraction plan

**CRITICAL: Stop here and confirm with the user.**

Present:
- "Here's what I found the pattern actually does, step by step:"
- The common workflow (numbered steps)
- What varies (the inputs/parameters)
- Interesting moments the subagents flagged (quote the specific findings)
- What could be automated vs what needs human judgment
- Ask: "Does this capture the pattern? Anything to add or change?"

## Phase 3: Build the Skill

### Step 8: Create the skill

Create a SKILL.md with this structure:

```yaml
---
name: descriptive-skill-name
description: |
  When to trigger this skill. Use specific phrases the user might say.
  Be generous with trigger conditions — better to activate and confirm
  than to miss a valid use case.
---
```

The skill body should contain:
1. **Purpose** — one paragraph on what this skill does
2. **Workflow** — numbered steps, imperative form
3. **Inputs** — what the user needs to provide or what to detect from context
4. **Decision points** — where to ask the user vs proceed automatically
5. **Output** — what the deliverable looks like

### Skill writing principles

- **Be specific about actions** — "Run `pytest -x` and check for failures" not "run tests"
- **Include the tool calls** — If the pattern always uses Edit on a specific file, say so
- **Preserve decision points** — If the human always made a choice at step 3, keep that as an interaction point
- **Don't over-generalize** — A skill for "fix pytest failures in icechunk" is better than "fix any test in any project"
- **Keep it under 200 lines** — Move reference material to `references/` subdirectory

### Step 9: Verify with examples (subagent)

Spawn a **haiku** subagent to validate the draft skill against past sessions:

```
Here is a draft skill definition:

<paste the SKILL.md content>

Now check it against these sessions by running:
- `claudephant session <id> --tools` for each session ID: <list ids>

For each session, answer:
1. Would the trigger description have matched the user's initial prompt?
2. Do the skill's workflow steps match what actually happened? Note any gaps.
3. Are the decision points in the right places — did the user make choices
   at the points the skill says to ask?
4. Are there steps in the session that the skill missed?

Return a brief verdict per session and any suggested improvements.
```

Present the subagent's findings to the user.

## Useful Claudephant Filters

These compose — combine them to narrow down exactly what you need:

| Filter | Purpose |
|--------|---------|
| `--project <name>` | Scope to one project |
| `--since YYYY-MM-DD` | Recent sessions only |
| `--grep <pattern>` | Turns matching a keyword |
| `--file <path>` | Turns that touched a file |
| `--tool <name>` | Turns using a specific tool (Edit, Bash, etc.) |
| `--edits` | Only file modifications |
| `--bash` | Only shell commands |
| `--tools` | Include tool names and key inputs |
| `--compact-segment N` | Specific segment between compactions |
| `--head N` / `--tail N` | First/last N turns |
| `--turn N` / `--turns N-M` | Specific turns |
| `--json` | Machine-readable output |

## Subagent Patterns

### Principles

- **The main agent never reads raw transcripts.** Subagents read, the main agent synthesizes.
- **Use haiku for most session analysis** — it's cheap and fast. Use sonnet for sessions
  that are very long or where the pattern is subtle.
- **Spawn in parallel** — If analyzing 4 sessions, spawn 4 subagents at once, don't do them
  sequentially. The Task tool supports this (multiple tool calls in one message).
- **Give structured output templates** — Tell the subagent exactly what format to return.
  Bullet lists and headers, not prose.
- **Quote specifics in the return** — The subagent should include exact command strings,
  file paths, and key phrases from user prompts so the main agent can reference them
  without re-reading the session.

### When to use which model

| Task | Model | Why |
|------|-------|-----|
| Run claudephant + summarize output | haiku | Mechanical extraction, fast |
| Analyze a short session (<50 turns) | haiku | Straightforward reading |
| Analyze a long/complex session | sonnet | Needs to track nuance across many turns |
| Cross-session comparison | main agent | Synthesizing across subagent summaries |
| Skill writing | main agent | Requires user context and creative judgment |
| Skill verification | haiku | Mechanical: compare steps to transcript |

### Context budget

Each subagent gets its own context window. A typical session's `--tools` output
is 5-20K tokens — well within haiku's capacity. By splitting sessions across
subagents, you can analyze an arbitrarily large number of sessions without
filling the main conversation's context.

## Anti-patterns to Avoid

- **Frequency isn't the only signal.** A pattern appearing 3+ times is an obvious candidate,
  but a single complex workflow the user wants to repeat is equally valid. If the user says
  "make this a skill", trust them — they know what they'll reuse.
- **Don't create skills that are just "do X".** Good skills encode *how* and *when*, not just *what*.
- **Don't skip user confirmation.** The user knows their workflow better than the data shows.
- **Don't include session-specific details.** File paths, branch names, and error messages from specific sessions should be generalized.
- **Don't make the skill too broad.** "Handle all code changes" is useless. "Review and apply PR feedback for Python projects" is useful.
