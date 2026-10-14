#!/usr/bin/env python3
"""PreToolUse(Bash) guard for git. Denies, with a reason the model reads:

  - `git add` that would stage a local-only path (asks git itself via --dry-run,
    so `git add .` is judged by what it expands to, not by its text)
  - `git commit` while on a protected branch
  - `git push` whose destination is a protected branch, or any force push
  - creating a branch that would track a protected branch (`checkout -b x origin/main`),
    or pointing an upstream at one; this is how a "Sync" click lands commits on main
  - optional: commit messages carrying a Claude attribution trailer

Exit 0 with no output = allow. Anything this script cannot parse is allowed:
deny rules in settings are the place for string-matchable bans.
Escape hatch for one command: PIPELINE_GUARD=off in the environment.
"""
import os
import re
import shlex
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pipeline_config import deny, is_protected, load_config, project_root, read_event  # noqa: E402

SEPARATORS = {";", "&&", "||", "|", "&", "(", ")"}
ATTRIBUTION = re.compile(r"co-authored-by:\s*claude|generated with \[?claude", re.I)


def git(cwd, *args):
    try:
        r = subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True, timeout=20)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def invocations(cmd):
    """Yield (cwd_override, subcommand, args) for every `git ...` in a shell command."""
    try:
        lex = shlex.shlex(cmd, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        tokens = list(lex)
    except ValueError:
        tokens = cmd.split()
    segments, cur = [], []
    for t in tokens:
        if t in SEPARATORS:
            segments.append(cur)
            cur = []
        else:
            cur.append(t)
    segments.append(cur)
    for seg in segments:
        for i, t in enumerate(seg):
            if t != "git" and not t.endswith("/git"):
                continue
            rest, cwd = seg[i + 1:], None
            while rest and rest[0].startswith("-"):
                opt = rest.pop(0)
                if opt in ("-C", "-c", "--git-dir", "--work-tree") and rest:
                    val = rest.pop(0)
                    if opt == "-C":
                        cwd = val
            if rest:
                yield cwd, rest[0], rest[1:]


def under(path, pattern):
    path = os.path.normpath(path)
    pat = os.path.normpath(pattern)
    return path == pat or path.startswith(pat + "/") or os.path.basename(path) == pat


def check_add(cwd, args, cfg):
    skip = {"-n", "--dry-run", "-v", "--verbose", "-p", "--patch", "-i", "--interactive", "--"}
    passthrough = [a for a in args if a not in skip]
    paths = [a for a in passthrough if not a.startswith("-")]
    hits = [p for p in paths for pat in cfg["local_only"] if under(p, pat)]
    try:
        r = subprocess.run(["git", "-C", cwd, "add", "--dry-run", *passthrough],
                           capture_output=True, text=True, timeout=20)
        for line in r.stdout.splitlines():
            p = line.split("'")[1] if "'" in line else line.strip()
            if any(under(p, pat) for pat in cfg["local_only"]):
                hits.append(p)
    except Exception:
        pass
    if hits:
        shown = "\n  ".join(sorted(set(hits))[:8])
        deny("git_guard: this would stage local-only files:\n  " + shown +
             "\nStage the files you mean by explicit path. Local-only paths are set in "
             ".claude/pipeline.json `local_only`.")


def remote_branch(ref, remotes):
    """'origin/main' -> 'main' when 'origin' is a configured remote, else None."""
    head, _, tail = ref.partition("/")
    return tail if tail and head in remotes else None


def check_push(cwd, args, cfg):
    if any(a in ("-f", "--force", "--mirror", "--all") or a.startswith("--force") for a in args):
        deny("git_guard: force / --all / --mirror pushes are not run from a session. "
             "Show the user the exact command and let them run it.")
    with_value = {"-o", "--push-option", "--repo", "--receive-pack", "--exec"}
    pos, skip_next = [], False
    for a in args:
        if skip_next:
            skip_next = False
        elif a in with_value:
            skip_next = True
        elif not a.startswith("-"):
            pos.append(a)
    current = git(cwd, "branch", "--show-current")
    refspecs = pos[1:]
    if not refspecs:
        upstream = git(cwd, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
        dests = [upstream.split("/", 1)[1] if "/" in upstream else current]
    else:
        dests = []
        for spec in refspecs:
            if spec.startswith("+"):
                deny("git_guard: `+refspec` is a force push. Let the user run it.")
            src, _, dst = spec.partition(":")
            dests.append(dst if dst else (current if src == "HEAD" else src))
    for d in dests:
        if d and is_protected(d, cfg):
            deny(f"git_guard: this push lands on protected branch `{d}` "
                 f"(you are on `{current}`). Protected branches only change through a reviewed PR. "
                 f"Push your own branch explicitly: git push -u origin {current}:refs/heads/{current}")


def check_tracking(cwd, sub, args, cfg):
    remotes = set(git(cwd, "remote").split())
    if "--no-track" in args:
        return
    current = git(cwd, "branch", "--show-current")
    # --set-upstream-to / -u on `git branch`
    for i, a in enumerate(args):
        target = None
        if a.startswith("--set-upstream-to="):
            target = a.split("=", 1)[1]
        elif a in ("--set-upstream-to", "-u") and sub == "branch" and i + 1 < len(args):
            target = args[i + 1]
        if target:
            local = next((x for x in args[i + 2:] if not x.startswith("-")), current)
            upstream = remote_branch(target, remotes) or target
            if is_protected(upstream, cfg) and upstream != local:
                deny(f"git_guard: pointing `{local}` at protected `{target}` means a bare push from "
                     f"`{local}` lands on `{upstream}`. Set the upstream on first push instead: "
                     f"git push -u origin {local}")
            return
    # branch creation from a remote-tracking ref: checkout -b X origin/main, switch -c X origin/main, branch X origin/main
    pos = [a for a in args if not a.startswith("-")]
    creating = (sub == "branch") or any(a in ("-b", "-B", "-c", "-C", "--create", "--force-create") for a in args)
    if not creating or len(pos) < 2:
        return
    new, start = pos[0], pos[1]
    upstream = remote_branch(start, remotes)
    if upstream and is_protected(upstream, cfg) and upstream != new:
        deny(f"git_guard: `{new}` created from `{start}` would track `{upstream}`, so a later bare push "
             f"lands there. Re-run with --no-track (e.g. git {sub} --no-track ... {new} {start}), "
             f"then set the upstream on first push: git push -u origin {new}")


def main():
    ev = read_event()
    if ev.get("tool_name") != "Bash" or os.environ.get("PIPELINE_GUARD", "").lower() == "off":
        return
    cmd = (ev.get("tool_input") or {}).get("command", "")
    if "git" not in cmd:
        return
    root = project_root()
    cfg = load_config(root)
    for cwd, sub, args in invocations(cmd):
        cwd = os.path.join(ev.get("cwd") or root, cwd) if cwd else (ev.get("cwd") or root)
        if sub == "add":
            check_add(cwd, args, cfg)
        elif sub == "commit":
            current = git(cwd, "branch", "--show-current")
            if current and is_protected(current, cfg):
                deny(f"git_guard: you are on protected branch `{current}`. "
                     f"Create a working branch first (git switch -c <name>), then commit.")
            if cfg.get("block_attribution") and ATTRIBUTION.search(cmd):
                deny("git_guard: this project does not allow Claude attribution in commits. "
                     "Commit again without the trailer.")
        elif sub == "push":
            check_push(cwd, args, cfg)
        elif sub in ("checkout", "switch", "branch"):
            check_tracking(cwd, sub, args, cfg)


main()
