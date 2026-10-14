#!/usr/bin/env bash
# One iteration = one card = one fresh `claude -p` session.
#
# Sessions commit locally and never push. Between sessions the shell re-runs the
# build and tests itself (it doesn't trust the session's report) and stops on
# anything that isn't a clean COMMITTED card. Pushing and opening the PR is yours.
#
#   EPIC=<key> loop.sh                run every READY card in filename order
#   EPIC=<key> loop.sh --one          run one card, then stop
#   EPIC=<key> loop.sh --skip-selftest
#
# Run from the project root. macOS bash 3.2 compatible; needs python3, git, claude.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN="$HERE/../plugin"
CARDS_PY="python3 $HERE/cards.py"
PROJECT="$(git rev-parse --show-toplevel)" || exit 1
cd "$PROJECT"
EPIC="${EPIC:?set EPIC=<epic key>}"
DIR=".pipeline/$EPIC"; CARDS="$DIR/cards"; RUNS="$DIR/runs"
ONE=0; SELFTEST=1
for a in "$@"; do case "$a" in --one) ONE=1;; --skip-selftest) SELFTEST=0;; esac; done

cfg() { $CARDS_PY config "$PROJECT" "$1"; }
BUILD="$(cfg build)"; TEST="$(cfg test)"
MODEL="${MODEL:-$(cfg loop.model)}"; EFFORT="${EFFORT:-$(cfg loop.effort)}"; BUDGET="${BUDGET:-$(cfg loop.budget_usd)}"
note() { echo "loop: $1"; command -v osascript >/dev/null && osascript -e "display notification \"$1\" with title \"agent-pipeline\"" 2>/dev/null; }

[ -n "$BUILD$TEST" ] || { echo "loop: set build/test in .claude/pipeline.json first"; exit 1; }
[ -d "$CARDS" ] || { echo "loop: no cards at $CARDS (run the kickoff skill first)"; exit 1; }
[ -z "$(git status --porcelain --untracked-files=no)" ] || { echo "loop: tracked files have uncommitted changes; commit or set them aside first"; exit 1; }
BRANCH="$(git branch --show-current)"
if PIPELINE_GUARD= python3 -c "import sys; sys.path.insert(0, '$PLUGIN/hooks'); from pipeline_config import *; sys.exit(0 if is_protected('$BRANCH', load_config('$PROJECT')) else 1)"; then
  echo "loop: you are on protected branch '$BRANCH'; switch to a working branch first"; exit 1
fi

mkdir -p "$RUNS"
LOCK="$RUNS/.lock"
mkdir "$LOCK" 2>/dev/null || { echo "loop: another run holds $LOCK (remove it if that run is dead)"; exit 1; }
trap 'rmdir "$LOCK" 2>/dev/null' EXIT

SETTINGS="$RUNS/settings.json"
$CARDS_PY settings "$PROJECT" > "$SETTINGS"
# --setting-sources project: don't inherit your personal allowlist from user/local settings.
# --plugin-dir: loads this plugin's hooks and skills even though user settings are skipped.
COMMON=(--permission-mode acceptEdits --permission-prompts none --setting-sources project
        --settings "$SETTINGS" --plugin-dir "$PLUGIN")

# --- prove the guards are live, not just configured ---------------------------
# A silently broken hook looks exactly like a missing one. The probe has to be a command
# the model will actually attempt; a command CLAUDE.md bans gets declined with no tool
# call, and a live guard then reads as dead.
probe() {  # $1 command, $2 label
  local out="$RUNS/selftest-$2.json"
  claude -p "Run exactly this shell command and report its output verbatim: $1" \
    "${COMMON[@]}" --model claude-haiku-5-5 --max-budget-usd 0.5 --output-format json \
    < /dev/null > "$out" 2>/dev/null
  $CARDS_PY denied "$out" "$1"
}
if [ "$SELFTEST" = 1 ]; then
  echo "loop: self-test (a deny rule and the git_guard hook must both fire)..."
  touch "$DIR/.selftest"
  probe "git stash list" rule || { note "SELF-TEST FAILED: deny rule did not fire. Not starting."; exit 1; }
  probe "git add $DIR/.selftest" hook || { note "SELF-TEST FAILED: git_guard hook did not fire. Not starting."; exit 1; }
  echo "loop: self-test passed"
fi

while :; do
  next="$($CARDS_PY next "$CARDS")"
  case "$next" in
    DONE) note "no READY cards left"; break ;;
    BLOCKED:*) note "$(basename "${next#BLOCKED:}") has open forks; answer them on the card"; break ;;
  esac
  card="$next"; ticket="$(basename "$card" .md)"
  start="$(git rev-parse HEAD)"
  echo "=== $ticket — $(date '+%H:%M:%S') ==="

  budget_args=(); [ "${BUDGET:-0}" != 0 ] && budget_args=(--max-budget-usd "$BUDGET")
  # Print mode kills background subagents after 600s by default, which can lose a
  # finished ticket's commit and card; 0 waits as long as they need.
  PIPELINE_CARD="$PROJECT/$card" CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0 \
  claude -p "Use the agent-pipeline:ticket skill on the card at $card. You are headless: nobody can approve a prompt, so only allowlisted commands run. Run shell commands one at a time (no chaining with && ; |, no cd prefix), and create or edit files with Write/Edit, not echo or redirects. If a command is denied, read the reason, adjust and continue; set BLOCKED only if you genuinely cannot proceed." \
    --name "$ticket" --model "$MODEL" --effort "$EFFORT" "${COMMON[@]}" \
    ${budget_args[@]+"${budget_args[@]}"} --output-format stream-json --verbose \
    < /dev/null > "$RUNS/$ticket.stream.jsonl" 2> "$RUNS/$ticket.stderr"
  echo "  $($CARDS_PY result "$RUNS/$ticket.stream.jsonl")"

  status="$($CARDS_PY status "$card")"
  case "$status" in
    COMMITTED*) ;;
    BLOCKED*|FAILED*) note "$ticket: $status"; break ;;
    *) $CARDS_PY set "$card" "FAILED session ended without writing the card"
       note "$ticket ended without writing its card"; break ;;
  esac
  if [ "$(git rev-parse HEAD)" = "$start" ]; then
    $CARDS_PY set "$card" "FAILED card says COMMITTED but there are no new commits"
    note "$ticket: no new commits"; break
  fi

  echo "  gate: $BUILD && $TEST"
  if ! (eval "$BUILD" && eval "$TEST") > "$RUNS/$ticket.gate.log" 2>&1; then
    $CARDS_PY set "$card" "FAILED shell gate red, see $RUNS/$ticket.gate.log"
    note "$ticket: gate red"; break
  fi
  echo "  gate green · $(git rev-list --count "$start"..HEAD) commit(s)"
  [ "$ONE" = 1 ] && break
done

echo
echo "loop: finished on $BRANCH. Nothing was pushed."
echo "  review:  git log --oneline @{u}..HEAD 2>/dev/null || git log --oneline -10"
echo "  then:    git push -u origin $BRANCH   (PR bodies are on the cards)"
