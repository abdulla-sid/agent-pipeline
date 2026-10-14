---
name: kickoff
description: Start a multi-ticket epic. Turns an epic (tracker link or a description) into an approved plan plus one card per ticket under .pipeline/<EPIC>/, so each ticket can then run in its own fresh session or in the headless loop. Use when the user wants to plan or kick off an epic, feature set or batch of tickets.
---

# Kickoff

This is the **only planning approval** for the whole epic. Spend the thinking here so ticket sessions don't need to stop.

## Inputs (ask only if missing)
- The epic: a tracker link (use whatever tracker MCP is connected) or the user's description.
- An epic key for folder names, e.g. `ORD-12` or a short slug.

## Steps
1. **Read the epic and its tickets.** Then read just enough code to order the work and spot risks: the files each ticket will touch and their nearest existing siblings. Don't plan the inside of each ticket; its own session does that.
2. **Write `.pipeline/<EPIC>/PLAN.md`** from `plan.md` in this skill's folder.
3. **Make `.pipeline/` local-only.** If it isn't already listed, append `.pipeline/` to `.git/info/exclude`. That file is never committed and the change stays on this machine.
4. **Show the plan and stop.** Iterate until the user approves it.
5. **On approval, write one card per ticket** at `.pipeline/<EPIC>/cards/<NN>-<TICKET>.md` from `card.md` in this skill's folder. `NN` is the run order: 01, 02, …
   - Goal and Acceptance come from the ticket, not invented.
   - Facts carry where they came from (`file:line`, a command). A fact that depends on another repo gets a `Pinned: <repo> <origin/branch> @ <sha>` line.
   - Anything only a human can decide goes under **Open forks**. A card with an open fork won't run until it's answered.
   - Choices made while approving the plan go under **Decisions in force**, so reviewers don't re-raise them.
6. **If `.claude/pipeline.json` is missing,** offer to create it from the project's real build and test commands. Read them from `package.json`, `Makefile` or equivalent; don't guess.

## Report
```
Epic <EPIC>: <N> cards in .pipeline/<EPIC>/cards/ (local-only)
Blocked on open forks: <list or none>
Next: run one ticket with /agent-pipeline:ticket <card path>, or the loop: EPIC=<EPIC> ~/Projects/agent-pipeline/loop/loop.sh --one
```
