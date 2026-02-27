---
name: conversation-miner
description: |
  Use this skill when the user wants to mine Claude Code conversation history for
  repeatable patterns, build new skills from past sessions, or analyze their workflow.
  Trigger when the user says things like "find skill candidates", "what patterns repeat",
  "mine my conversations", "build a skill from history", "analyze my sessions", or
  "what do I keep asking Claude to do".
---

# Conversation Miner: Finding and Building Skills from History

You have access to `claudephant`, a CLI that parses Claude Code JSONL transcripts
from `~/.claude/projects/`. Use it to discover repeatable patterns worth converting
into Claude Code skills.

## Workflow Overview

This is an **incremental, collaborative process**. Never dump a wall of data.
Guide the user through discovery → refinement → extraction in stages.

## Phase 1: Discovery — Find Candidate Patterns

Start broad: identify what the user does repeatedly across sessions.

### Step 1: Cross-session prompt analysis

```bash
uv run claudephant summary --project <name>
```

This shows:
- **Most Common Prompts** — repeated user instructions (skill candidates!)
- **Tool Usage** — which tools dominate (signals the type of work)
- **Most Modified Files** — hot paths in the codebase

Look for prompts appearing 3+ times. These are strong skill candidates.

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

Once the user selects a pattern, drill into the sessions where it appeared.

### Step 4: List relevant sessions

```bash
uv run claudephant list --project <name>
```

Find sessions whose first prompt or content matches the selected pattern.

### Step 5: Inspect representative sessions

Pick 2-3 sessions that best represent the pattern and examine them:

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

### Step 6: Identify the reusable core

Look for:
- **Common steps** — What sequence of actions appears in every instance?
- **Inputs** — What varies between instances? (file paths, names, config values)
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

- **Don't extract one-off tasks as skills.** A pattern needs 3+ occurrences to be worth it.
- **Don't create skills that are just "do X".** Good skills encode *how* and *when*, not just *what*.
- **Don't skip user confirmation.** The user knows their workflow better than the data shows.
- **Don't include session-specific details.** File paths, branch names, and error messages from specific sessions should be generalized.
- **Don't make the skill too broad.** "Handle all code changes" is useless. "Review and apply PR feedback for Python projects" is useful.
