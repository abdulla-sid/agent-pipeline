#!/usr/bin/env python3
"""SessionStart hook: tell a loop session whether facts on its card are stale.

A card records where a fact came from, not just the fact:

    Pinned: ../frontend origin/feature/orders @ 3f2a9c1

"Don't trust stale facts" can't be followed, because staleness isn't visible on a
fact. Comparing the pinned sha with the remote's current head makes it visible.

Only active when the loop exported PIPELINE_CARD.
"""
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pipeline_config import project_root  # noqa: E402

PIN = re.compile(r"^Pinned:\s*(\S+)\s+(?:origin/)?(\S+)\s*@\s*([0-9a-f]{7,40})", re.M)


def check(repo, branch, sha, root):
    path = repo if os.path.isabs(repo) else os.path.join(root, repo)
    try:
        out = subprocess.run(["git", "-C", path, "ls-remote", "origin", branch],
                             capture_output=True, text=True, timeout=25).stdout.split()
    except Exception as exc:
        return f"{repo} {branch}: could not reach the remote ({exc}). Treat facts pinned to it as unverified."
    if not out:
        return f"{repo} {branch}: branch did not resolve on origin. Treat facts pinned to it as unverified."
    if out[0].startswith(sha):
        return f"{repo} {branch} @ {sha[:8]} is still the head. Facts pinned to it are current."
    return (f"{repo} {branch} moved: pinned {sha[:8]}, now {out[0][:8]}. Re-verify every fact pinned to it "
            f"(git -C {repo} show origin/{branch}:<path>) before relying on it, and record the change on the card.")


def main():
    card = os.environ.get("PIPELINE_CARD")
    if not card:
        return
    try:
        text = open(card, encoding="utf-8").read()
    except OSError:
        return
    pins = PIN.findall(text)
    if not pins:
        return
    root = project_root()
    note = "[pin_freshness] " + " | ".join(check(r, b, s, root) for r, b, s in pins)
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": note}}))


main()
