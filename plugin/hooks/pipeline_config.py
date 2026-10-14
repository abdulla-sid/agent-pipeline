"""Shared helpers for the agent-pipeline hooks.

Project settings live in `.claude/pipeline.json` at the project root. Every key is
optional; DEFAULTS applies for anything missing. Python 3.9 compatible (macOS system python).
"""
import fnmatch
import json
import os
import subprocess
import sys

DEFAULTS = {
    "protected_branches": ["main", "master", "development", "develop", "production", "release/*"],
    "local_only": [".pipeline/", ".env"],
}


def project_root():
    root = os.environ.get("CLAUDE_PROJECT_DIR")
    if root:
        return root
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, timeout=5).stdout.strip()
        return out or os.getcwd()
    except Exception:
        return os.getcwd()


def load_config(root=None):
    cfg = dict(DEFAULTS)
    path = os.path.join(root or project_root(), ".claude", "pipeline.json")
    try:
        with open(path, encoding="utf-8") as f:
            cfg.update(json.load(f))
    except (OSError, ValueError):
        pass
    return cfg


def is_protected(branch, cfg):
    branch = branch.replace("refs/heads/", "", 1)
    return any(fnmatch.fnmatch(branch, pat) for pat in cfg["protected_branches"])


def read_event():
    try:
        return json.load(sys.stdin)
    except Exception:
        return {}


def deny(reason):
    """PreToolUse deny: the reason reaches the model verbatim."""
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}))
    sys.exit(0)


def card_status(path):
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.startswith("STATUS:"):
                    return line[len("STATUS:"):].strip()
    except OSError:
        pass
    return ""
