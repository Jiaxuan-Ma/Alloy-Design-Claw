---
name: self-improving
description: Learn from explicit user corrections and completed-task reflections inside this project. Use when the user corrects the agent, asks what has been learned, asks to remember or forget a preference, or when the agent finishes a significant task and should record a reusable lesson.
---

# Self-Improving

## Purpose

This skill helps the project agent improve over time without relying on external services. It records explicit corrections, confirmed preferences, and short reflections in files under `Skills/self-improving/`.

Use this skill when:

- The user corrects an answer, workflow, command, UI behavior, or assumption.
- The user says to remember, always do, never do, forget, or update a preference.
- The user asks what the agent has learned, memory stats, or project patterns.
- A significant multi-step task finishes and there is a reusable lesson worth recording.
- A tool, script, or workflow failed and the fix should influence future behavior.

Do not use this skill for one-off task details that are not reusable.

## Local Files

All state is local to this project:

- `Skills/self-improving/memory.md`: confirmed HOT preferences and recurring project rules.
- `Skills/self-improving/corrections.md`: recent explicit corrections and lessons.
- `Skills/self-improving/reflections.md`: short task-end reflections.
- `Skills/self-improving/boundaries.md`: privacy and safety limits.
- `Skills/self-improving/operations.md`: maintenance and compaction guidance.
- `Skills/self-improving/heartbeat-state.md`: optional maintenance state.

If folders are needed, create them under `Skills/self-improving/`, not under the user's home directory.

## Required Workflow

1. Read this `SKILL.md`.
2. Read `boundaries.md` before storing anything.
3. For correction or preference updates, read `memory.md` and `corrections.md`.
4. Decide whether the item is safe and reusable.
5. Append a concise entry to the right file. Keep entries short and source-tagged.
6. Tell the user what was recorded, or explain why nothing was stored.

## What To Store

Store only:

- Explicit user corrections.
- Explicit user preferences.
- Project-specific workflow lessons that are likely to recur.
- Self-reflections after significant work when the lesson is concrete and actionable.

Do not store:

- API keys, tokens, passwords, or credentials.
- Medical, financial, biometric, or sensitive personal data.
- Third-party personal information.
- Guesses about user preferences.
- One-off instructions that only apply to the current turn.

## Entry Formats

### corrections.md

```markdown
## YYYY-MM-DD HH:MM
- Correction: [what the user corrected]
- Context: [what task or behavior caused it]
- Lesson: [what to do differently next time]
- Scope: [global | project | file/workflow name]
```

### memory.md

```markdown
- YYYY-MM-DD | Scope: [global/project/workflow] | Rule: [confirmed reusable preference or rule] | Source: [user correction/request]
```

### reflections.md

```markdown
## YYYY-MM-DD HH:MM
- Context: [completed task]
- Reflection: [what could be improved]
- Lesson: [specific future behavior]
```

## Promotion Rules

- A single explicit correction goes to `corrections.md`.
- A user saying "remember", "always", or "never" may go directly to `memory.md` if safe.
- Repeated corrections with the same lesson can be summarized into `memory.md`.
- Never delete memory without user confirmation.

## Query Handling

When the user asks:

- "What have you learned?" read and summarize `memory.md` and recent `corrections.md`.
- "Memory stats" count non-empty entries in `memory.md`, `corrections.md`, and `reflections.md`.
- "Forget X" confirm first, then remove or mark the matching entry as forgotten.
- "Show patterns" display relevant entries with file names.

## Important Boundaries

This skill must stay inside the project directory. Do not read or write `~/self-improving/`. Do not access email, calendar, contacts, browser history, or external services.
