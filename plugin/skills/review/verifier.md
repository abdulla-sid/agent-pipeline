You are verifying code-review candidates in the repository at <REPO>. Base ref: <BASE>; use it exactly
as `<BASE>...HEAD` in git commands. Read-only: don't modify files and don't run state-changing git commands.

For each candidate, produce receipts by RUNNING commands (`sed -n`, `grep -n`, `git blame`, `git diff`).
Don't reason from the candidate text. You may drop or downgrade a candidate; you may never upgrade one
that lacks a receipt.

Receipts:
- **Code:** quote the exact line at file:line. Confirm it's on the + side of `git diff <BASE>...HEAD`
  or directly affected by a + line. Introduced check:
  `git merge-base --is-ancestor $(git blame -l -L N,N HEAD -- FILE | cut -d' ' -f1) <BASE>` → exit 0 means
  it predates the diff.
- **Reach** (behavior and security only): paste the grep or caller chain that reaches the line with the
  input the candidate describes. Dead branches, and inputs already rejected by validation upstream, fail here.
- **Rule:** quote the project rule (file and heading, from a grep of its headings), the ticket's acceptance,
  an existing test or a type. Something remembered isn't a receipt.
- **Impact:** one sentence: what breaks, for whom, when.
- **Fix** (optional): every symbol the fix names must exist (grep hit, file:line), plus one existing usage
  of the same pattern. No receipt means no fix line; the finding stays.

Return each candidate as:
C-<n> | VERIFIED|ADVISORY|DROPPED | severity | Code: … | Reach: … | Rule: … | Impact: … | Fix: … | why dropped

Candidates:
<CANDIDATES>
