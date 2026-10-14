---
name: ticket
description: Implement one ticket from its card (.pipeline/<EPIC>/cards/*.md) end to end, from reading the card through build, tests, proof-gated review and local commits, then write the result back to the card. Used by the headless loop for every ticket, and interactively when the user says to work a card or run the next ticket.
---

# One ticket, end to end

The card is the only state that crosses sessions. Read it, work from it, write back to it. Don't read other `.pipeline/` files unless the card cites them.

## Steps
1. **Read the card and set `STATUS: IN_PROGRESS`.** Read `.claude/pipeline.json` for the build and test commands.
2. **Check Open forks.** If any are there, set `STATUS: BLOCKED <the question>` and stop.
3. **Check pinned facts.** If the SessionStart note says a pinned ref moved, re-check every fact pinned to it and record what changed on the card.
4. **Plan, if it's more than a few files.** Add a short `## Plan` to the card with decisions, interfaces, exact names and test names. Don't write code in the plan; code in prose drifts from the real code.
5. **Implement it yourself.** Before using any existing symbol, find it (`file:line`). The nearest existing sibling file is the spec for a new one. Use subagents only for independent chunks that can run in parallel, or for wide searches. Don't hand off everything as a matter of routine.
6. **Gate.** Run the build and then the tests. Both must pass. Never report a test count from a failed build.
7. **Review.** Run the `review` skill on the diff against the branch base. Give it the card's Decisions in force and Dismissed findings, but not your plan.
   - Fix VERIFIED findings that have a clear, receipted fix. Then re-run the gate once; don't start another review round.
   - Some findings are judgment calls: a trade-off between failure modes, a conflict with a decision in force, or a change to an agreed contract. For those, set `STATUS: BLOCKED <the choice>` and stop. Don't pick for the human.
8. **Commit locally.** Use one commit per intent and stage files by explicit path. **Never push**, never amend, never stash, reset or clean.
   - If a person is in the session and the project's CLAUDE.md requires approval to commit, follow that instead.
9. **Write back to the card:**
   - Fill in `## PR body` (what changed and why, how it was tested, follow-ups).
   - Append one line to `## Log`.
   - Set `STATUS: COMMITTED`, or `FAILED <why>`.

The last line of your final message is exactly: `CARD_WRITTEN <TICKET> <STATUS>`
