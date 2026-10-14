# <TICKET> — <title>
STATUS: READY
Branch: <working branch>   Ticket: <tracker link or ->

<!-- STATUS: READY | IN_PROGRESS | COMMITTED | BLOCKED <question> | FAILED <why> | DONE
     The session moves READY -> IN_PROGRESS -> COMMITTED/BLOCKED/FAILED. You set READY and DONE. -->

## Goal
<2-4 lines: what exists when this ticket is done, in user-visible terms>

## Acceptance
- <checkable statement>

## Facts (each with where it came from)
<!-- Provenance, not conclusions. A fact from another repo gets a Pinned line so the
     SessionStart hook can tell the session whether it went stale. -->
Pinned: <../other-repo> <origin/branch> @ <sha>
- <fact> — <file:line or command that shows it>

## Decisions in force
<!-- Settled choices. Reviewers must not re-raise these. One line each: id, choice, why. -->
- <D-1> <choice> — <why>

## Dismissed findings
<!-- Review findings you rejected, so the next review round doesn't repeat them. -->
- <finding> — rejected because <one line>

## Open forks
<!-- Questions only a human can answer. Must be EMPTY for the loop to start this card. -->

## PR body
<!-- Written by the session as its last act. -->

## Log
<!-- One line per session, appended: date — outcome — commits. -->
