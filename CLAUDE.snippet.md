<!-- Paste into a project's CLAUDE.md. Keep it short: this is loaded into every session and every subagent. -->

## Working rules
- **Prove it before you use it.** Before calling or relying on an existing function, field, column, constant or config key, find it and know its `file:line`. If you can't find it, say so; don't write code against a name you think exists.
- **The nearest existing sibling is the spec.** Before writing a new X, read the closest existing X. If a written rule and the code disagree, follow the code and say so.
- **Stage by explicit path.** Never `git add -A` or `git add .`. Never push to a protected branch. The agent-pipeline git guard enforces both.
- **Report honestly.** If the build or tests fail, say so and show the output. Never quote a test count from a run that didn't complete.
- **Comments explain why, not what.** Don't add defensive checks for inputs that can't happen; name the input that reaches the line or leave the check out.
