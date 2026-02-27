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

## Two Entry Points

This skill supports two distinct modes. Ask the user which applies, or infer from context:

1. **"Mine my history"** — The user wants to discover patterns across many sessions.
   Start at Phase 1 (Discovery).
2. **"Turn that into a skill"** — The user just did something and wants to capture it
   immediately. Skip to Phase 2 (Deep Dive) using the current or most recent session.

## Workflow Overview

This is an **incremental, collaborative process**. Never dump a wall of data.
Guide the user through discovery → refinement → extraction in stages.

## Phase 1: Discovery — Find Candidate Patterns

Use this phase when the user wants to explore broadly. Skip this entirely if the user
already knows what they want to turn into a skill.

### Step 1: Cross-session prompt analysis

```bash
uv run claudephant summary --project <name>
```

This shows:
- **Most Common Prompts** — repeated user instructions (skill candidates!)
- **Tool Usage** — which tools dominate (signals the type of work)
- **Most Modified Files** — hot paths in the codebase

Prompts appearing 3+ times are strong automatic candidates, but even a single
occurrence can be worth capturing if the user found it valuable or painful.

### Step 2: Extract all prompts for a project

```bash
uv run claudephant prompts --project <name>
```

Scan the output for **semantic clusters** — prompts that ask for the same kind of
thing even if worded differently. Examples:
- Multiple "fix the test" / "run tests and fix failures" → testing skill
- Multiple "review this PR" / "check the PR comments" → PR review skill
- Multiple "update the docs" / "add docstrings" → documentation skill

### Step 3: Present candidates to the user

**CRITICAL: Stop here and confirm with the user before proceeding.**

Present your findings as a short list:
- "I found N candidate patterns. Here are the top ones:"
- For each: one-line description + how many times it appeared + example prompts
- Ask: "Which of these would be most valuable as a reusable skill?"

Do NOT proceed to Phase 2 until the user picks a pattern.

## Phase 2: Deep Dive — Understand the Pattern

Once the user selects a pattern — or points you at a specific session — drill in.

If the user wants to capture a **specific recent session**, find it:

```bash
# Find the most recent sessions
uv run claudephant list --project <name> --since <recent-date>
```

If mining from **multiple sessions**, find ones matching the selected pattern:

```bash
uv run claudephant list --project <name>
```

### Inspect the session(s)

For a single session, examine it thoroughly. For a recurring pattern, pick 2-3
representative sessions and compare them:

```bash
# See the overall flow — what did the user ask, what did Claude do?
uv run claudephant session <id> --tools

# See what files were changed
uv run claudephant session <id> --edits

# See what commands were run
uv run claudephant session <id> --bash

# Search for specific aspects of the pattern
uv run claudephant session <id> --grep "keyword"
```

### Identify the reusable core

For **multiple sessions**, look for what's common across them:
- **Common steps** — What sequence of actions appears in every instance?
- **Inputs** — What varies between instances? (file paths, names, config values)

For a **single session**, look for what generalizes:
- **Steps** — What was the sequence of actions? Which are essential vs incidental?
- **Inputs** — What was specific to this instance vs what would change next time?

In both cases, also identify:
- **Decision points** — Where does the approach branch based on context?
- **Tool sequences** — What tools are always used and in what order?
- **Output format** — Is there a consistent deliverable?

### Step 7: Confirm the extraction plan

**CRITICAL: Stop here and confirm with the user again.**

Present:
- "Here's what I found the pattern actually does, step by step:"
- The common workflow (numbered steps)
- What varies (the inputs/parameters)
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

### Step 9: Verify with examples

Test the skill description against 2-3 past sessions:
- Would the trigger conditions have activated?
- Do the steps match what actually happened?
- Are the decision points in the right places?

Present the verification to the user.

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

## Anti-patterns to Avoid

- **Frequency isn't the only signal.** A pattern appearing 3+ times is an obvious candidate,
  but a single complex workflow the user wants to repeat is equally valid. If the user says
  "make this a skill", trust them — they know what they'll reuse.
- **Don't create skills that are just "do X".** Good skills encode *how* and *when*, not just *what*.
- **Don't skip user confirmation.** The user knows their workflow better than the data shows.
- **Don't include session-specific details.** File paths, branch names, and error messages from specific sessions should be generalized.
- **Don't make the skill too broad.** "Handle all code changes" is useless. "Review and apply PR feedback for Python projects" is useful.
