---
name: review
description: Proof-gated code review of a PR or local diff. Every finding must carry receipts (the quoted line, how it's reached, the rule or requirement it breaks, the impact), checked by a separate fresh-context verifier; anything unproven is dropped. Use when the user asks to review, check or audit a PR, branch or diff, or as the review step of a ticket.
---

# Proof-gated review

A finding is something you **showed** is wrong, not something that might be. Made-up findings are, by construction, the most plausible ones, so confidence can't filter them; only evidence can. Unproven candidates are dropped, never softened into "consider…".

## Inputs
- **Target:** a PR (`gh pr diff <n>`), a branch, or the local diff. Base = the PR base, or `git merge-base HEAD <default branch>`.
- **Settled ground:** if a card exists, its Decisions in force and Dismissed findings. Also `.claude/review-false-positives.md` if present. Anything that collides with these is auto-dismissed.
- **Not given:** the implementation plan or the author's reasoning. A reviewer that reads the plan checks that the code matches the plan, which is a weaker question than whether it's correct.

## Steps
1. **Mechanical.** Run the build and tests (commands in `.claude/pipeline.json`), plus a linter or type checker if the project has one. Skip this if the calling session just ran them on this exact tree. Tool output is its own receipt.
2. **Candidates.** Read the changed hunks and enough surrounding code to follow each change. List suspicions as:
   `C-<n> | file:line | behavior|convention|test|security | one-line suspicion | rule § or concrete scenario (input → wrong output)`
   - "Might break if null" isn't a candidate. Name the input that reaches the line and what goes wrong.
   - For a diff over ~400 lines, split candidate-finding across two parallel subagents on different axes: (a) correctness and integration, (b) conventions and design. The disagreement between them is the value.
3. **Verify.** If there are no candidates, skip this step. Otherwise dispatch **one** fresh `general-purpose` subagent with only the candidate list, the base ref and `verifier.md` from this skill's folder. Don't pass your argument for why each candidate is real; the context that produced a hallucination will confirm it.
4. **Sort what comes back:**
   - **VERIFIED:** every receipt is present and the line was introduced by this diff. It can be Critical, Major or Minor.
   - **ADVISORY:** the code and the rule are proven but reachability isn't (an external caller, another repo). Listed, never blocking.
   - **Dropped:** a receipt is missing, or the line predates the diff. A severe pre-existing issue gets one line under *Out of scope*.
5. **Report**, then stop. Post to GitHub only after the user confirms.

## Report format
```
## Review: <target> (base <ref>, head <sha7>)
Mechanical: build ✅ · tests ✅ (<summary line>) · lint ✅
### Critical / Major / Minor   (VERIFIED only, one receipt block each)
#### [V-1] <title> · <severity>
- Code: file:line — `<quoted line>` — introduced: yes (<sha7>)
- Reach: <caller chain with file:line, or N/A — why it always runs>
- Rule: <file §heading — quoted sentence | ticket acceptance | existing test>
- Impact: <what breaks, for whom, when>
- Fix: <only if the verifier receipted it>
### Advisory
### Out of scope
### Dropped: <count> (one line each, why)
VERDICT: SAFE TO MERGE | NOT SAFE
```
NOT SAFE means at least one VERIFIED Critical or Major finding.

When the user rejects a finding, offer to append it to `.claude/review-false-positives.md` (`date · pattern · why it's correct`), or to the card's Dismissed findings.
