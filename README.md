# agent-pipeline

A Claude Code plugin and shell loop for running a multi-ticket epic one ticket per fresh session:
- git guards enforced by hooks rather than prose rules;
- a card file per ticket as the only state that carries between sessions;
- review that only reports findings it can prove.

It works in any repo. Everything project-specific lives in `.claude/pipeline.json`.

## The flow

```
kickoff ──► you approve the plan ──► cards ──► loop: one fresh session per card ──► you push + open PRs
  (one approval)                     READY      implement → build/test → review →
                                                commit locally → write card → COMMITTED
```

You have three decisions in the whole flow:
1. Approve the epic plan.
2. Answer open forks: questions a card can't run without, or a review judgment call.
3. Push.

Nothing else stops for approval. Local commits are easy to undo.

## What's in it

| Part | What it does |
| --- | --- |
| `plugin/hooks/git_guard.py` | Denies: staging local-only paths (judged by what `git add` would really stage); committing on a protected branch; pushing to a protected branch; force pushes; creating branches that would track a protected branch (`checkout -b x origin/main`). Optionally denies Claude attribution trailers. |
| `plugin/hooks/card_guard.py` | Loop only. Stops a session from ending while its card still says IN_PROGRESS. |
| `plugin/hooks/pin_freshness.py` | Loop only. For each `Pinned: <repo> <branch> @ <sha>` line on a card, tells the session whether that ref has moved since. |
| `/agent-pipeline:kickoff` | Turns an epic into `.pipeline/<EPIC>/PLAN.md` plus one card per ticket. |
| `/agent-pipeline:ticket` | Works one card end to end. The loop runs it for every card; you can also run it yourself. |
| `/agent-pipeline:review` | Finds candidate issues, then a separate verifier with no shared context must produce receipts for each: the quoted line, how it's reached, the rule it breaks, the impact. Unproven candidates are dropped. |
| `loop/loop.sh` | Runs each READY card in a fresh `claude -p`. It runs a self-test first, re-runs the gate itself, stops on anything unexpected and never pushes. |
| `CLAUDE.snippet.md` | Five always-on working rules to paste into a project's CLAUDE.md. |

## Install (once per machine)

```bash
claude plugin marketplace add ~/Projects/agent-pipeline
claude plugin install agent-pipeline@agent-pipeline
```

After editing this repo, run `claude plugin marketplace update agent-pipeline` so installed sessions pick up the change. The loop always loads the plugin straight from this folder with `--plugin-dir`, so it never needs updating.

## Use in a project

1. **Config.** Copy `templates/pipeline.json` to `<project>/.claude/pipeline.json` and set the real build and test commands. Every key is optional; defaults live in `plugin/hooks/pipeline_config.py`. `loop.allow` adds allowlist rules for headless runs, e.g. `"Bash(npx eslint *)"`.
2. **Working rules (optional).** Paste `CLAUDE.snippet.md` into the project's CLAUDE.md.
3. **Plan the epic.** In a session, run `/agent-pipeline:kickoff <epic link or description>` and approve the plan.
4. **Run tickets.** From a working branch in the project root:
   ```bash
   EPIC=<key> ~/Projects/agent-pipeline/loop/loop.sh --one   # first time: one ticket, then look
   EPIC=<key> ~/Projects/agent-pipeline/loop/loop.sh         # every READY card in order
   ```
   Per-run overrides: `MODEL=`, `EFFORT=`, `BUDGET=` (USD cap per session; 0 means none).
5. **Ship.** Read the commits, push, and open PRs using each card's `## PR body`.

Cards, run logs and the plan live in `.pipeline/`. Kickoff adds that folder to `.git/info/exclude`, so it stays local and never shows up in `git status`.

## Design choices

- **One process per ticket.** Each ticket gets a fresh context, its own model and effort, and its own budget cap. A wrong call dies with its session unless it was written to the card, where you can review it.
- **Sessions never push.** Push and PR stay with you. Between sessions the shell runs the build and tests itself rather than trusting the session's report.
- **Guards live in hooks and deny rules, not prose.** A prose "never push to main" didn't stop a GUI Sync button. Each check sits in the cheapest layer that can decide it:
  - string match → deny rule;
  - needs the live repo → hook;
  - can wait until the session ends → the shell.
- **Prove the guards are live.** A hook that silently does nothing looks the same as no hook. The loop's self-test makes Haiku attempt a denied command and checks the denial in `permission_denials`, for under a cent.
- **The card records where facts came from, not just conclusions.** "Verified at `branch @ sha`" can be checked mechanically; "the frontend sends X" quietly goes stale.
- **Decisions in force and Dismissed findings sit on the card,** so review doesn't re-argue settled choices every ticket.
- **The reviewer doesn't see the plan.** It checks whether the code is correct, not whether it matches the plan. A separate verifier, which isn't told the original reasoning, must reproduce each finding from the code.
- **One fix round, no review ping-pong.** Clear proven bugs get fixed. Judgment calls go back to you as a BLOCKED card.

## Keeping token use down

- **Keep CLAUDE.md and always-loaded rules small.** They're paid for by every session and every subagent.
  - Use path-scoped rules (`paths:` frontmatter in `.claude/rules/*.md`) so a rule loads only when matching files are touched.
  - Move review-only checklists out of always-loaded rules.
- **One session does the implementation.** Subagents are for parallel independent work, wide searches and the review verifier, not a delegation hop on every edit.
- **Make checks scripts, not LLM checklists.** If a check is a grep, put it in a script or lint rule.

## Tests

```bash
python3 -m unittest discover tests
```

## Not included (patterns worth adding per project)

- **A target-system guard.** Before a destructive command such as a migration, ask the target itself whether it's the local one (e.g. `SELECT @@hostname`), and refuse if it can't answer. A tunnel to shared staging looks exactly like localhost.
- **A false-positives file.** `.claude/review-false-positives.md`, appended to whenever you reject a review finding. The review skill reads it.
