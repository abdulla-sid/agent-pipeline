#!/usr/bin/env python3
"""Stop hook: a loop session may not end while its card still says IN_PROGRESS.

Blocking a stop continues the same context, so this is a "you forgot the last
step" reminder, not a way to get more work done. It blocks once per stop
(stop_hook_active), then lets the session end; the loop marks the card FAILED.

Only active when the loop exported PIPELINE_CARD; a no-op in interactive sessions.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pipeline_config import card_status, read_event  # noqa: E402

card = os.environ.get("PIPELINE_CARD")
ev = read_event()
if card and not ev.get("stop_hook_active") and card_status(card).startswith("IN_PROGRESS"):
    print(f"{card} still says STATUS: IN_PROGRESS. Before stopping, set STATUS to "
          "COMMITTED, BLOCKED <question> or FAILED <why>, and fill in the PR body section.",
          file=sys.stderr)
    sys.exit(2)
