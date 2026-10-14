#!/usr/bin/env python3
"""Small helpers the loop shell calls, kept in Python so loop.sh needs no GNU-only tools.

  cards.py next <cards-dir>               -> <card path> | BLOCKED:<card path> | DONE
  cards.py status <card>                  -> the STATUS value
  cards.py set <card> <status...>         -> rewrite the STATUS line
  cards.py config <project> <key>         -> a value from .claude/pipeline.json (dotted keys ok)
  cards.py settings <project>             -> loop settings JSON (allow/deny) on stdout
  cards.py result <stream.jsonl>          -> one-line summary of the run's result event
  cards.py denied <result.json> <command> -> exit 0 if the command shows up in permission_denials
"""
import json
import pathlib
import re
import sys

DEFAULT_LOOP = {"model": "claude-opus-5-5", "effort": "high", "budget_usd": 0, "allow": []}

READ_ONLY = [
    "Read", "Grep", "Glob", "Edit", "Write", "Agent", "Skill", "TodoWrite",
    "Bash(git status*)", "Bash(git diff*)", "Bash(git log*)", "Bash(git show*)", "Bash(git blame*)",
    "Bash(git grep*)", "Bash(git ls-files*)", "Bash(git rev-parse*)", "Bash(git merge-base*)",
    "Bash(git branch --show-current)", "Bash(git fetch*)", "Bash(git ls-remote*)",
    "Bash(git add *)", "Bash(git commit *)",
    "Bash(ls*)", "Bash(cat *)", "Bash(head *)", "Bash(tail *)", "Bash(wc *)", "Bash(grep *)",
    "Bash(rg *)", "Bash(find *)", "Bash(sed -n *)", "Bash(diff *)", "Bash(mkdir *)",
]
DENY = [
    "Bash(git push*)", "Bash(gh pr*)", "Bash(gh api*)", "Bash(git stash*)", "Bash(git reset*)",
    "Bash(git clean*)", "Bash(git rebase*)", "Bash(git checkout*)", "Bash(git restore*)",
    "Bash(git switch*)", "Bash(git commit --amend*)", "Bash(git add -A*)", "Bash(git add --all*)",
    "Bash(git add .)", "Bash(rm -rf*)",
]


def card_status(text):
    m = re.search(r"^STATUS:\s*(.*)$", text, re.M)
    return m.group(1).strip() if m else ""


def open_forks(text):
    m = re.search(r"^##\s*Open forks[^\n]*\n(.*?)(?=^##\s|\Z)", text, re.M | re.S)
    if not m:
        return []
    body = re.sub(r"<!--.*?-->", "", m.group(1), flags=re.S)
    return [ln for ln in body.splitlines() if ln.strip().startswith("-") and ln.strip("- \t")]


def config(project):
    try:
        return json.loads((pathlib.Path(project) / ".claude" / "pipeline.json").read_text())
    except (OSError, ValueError):
        return {}


def main(argv):
    cmd, args = argv[0], argv[1:]
    if cmd == "next":
        d = pathlib.Path(args[0])
        for card in sorted(d.glob("*.md")) if d.is_dir() else []:
            text = card.read_text()
            if card_status(text).startswith("READY"):
                print(("BLOCKED:" if open_forks(text) else "") + str(card))
                return
        print("DONE")
    elif cmd == "status":
        print(card_status(pathlib.Path(args[0]).read_text()))
    elif cmd == "set":
        p = pathlib.Path(args[0])
        p.write_text(re.sub(r"^STATUS:.*$", "STATUS: " + " ".join(args[1:]), p.read_text(), count=1, flags=re.M))
    elif cmd == "config":
        v = config(args[0])
        for k in args[1].split("."):
            v = v.get(k) if isinstance(v, dict) else None
        if v is None:
            v = DEFAULT_LOOP.get(args[1].split(".")[-1], "") if args[1].startswith("loop.") else ""
        print(v)
    elif cmd == "settings":
        cfg = config(args[0])
        loop = dict(DEFAULT_LOOP, **cfg.get("loop", {}))
        allow = READ_ONLY + [f"Bash({c})" for c in (cfg.get("build"), cfg.get("test")) if c] + loop["allow"]
        out = {"permissions": {"allow": allow, "deny": DENY}}
        if cfg.get("block_attribution"):
            out["attribution"] = {"commit": "", "pr": ""}
        print(json.dumps(out, indent=2))
    elif cmd == "result":
        last = None
        for line in pathlib.Path(args[0]).read_text().splitlines():
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            if ev.get("type") == "result":
                last = ev
        if not last:
            print("no result event (session crashed or was killed)")
            return
        pathlib.Path(args[0]).with_suffix(".result.json").write_text(json.dumps(last, indent=2))
        print(f"cost ${last.get('total_cost_usd', '?')} · turns {last.get('num_turns', '?')} · "
              f"{last.get('subtype', '?')} · denials {len(last.get('permission_denials') or [])}")
    elif cmd == "denied":
        try:
            d = json.loads(pathlib.Path(args[0]).read_text())
        except (OSError, ValueError):
            sys.exit(1)
        hits = [x for x in d.get("permission_denials") or []
                if args[1] in (x.get("tool_input") or {}).get("command", "")]
        sys.exit(0 if hits else 1)
    else:
        sys.exit(__doc__)


main(sys.argv[1:])
