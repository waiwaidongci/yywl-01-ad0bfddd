#!/bin/bash
set -euo pipefail

LOG_DIR="${YEL003_LOGS_DIR:-/logs/verifier}"
TEST_DIR="${YEL003_TESTS_DIR:-/tests}"
# Verification image wiring: /tests/score.py and /tests/scoring.json.
# Reward contract: /logs/verifier/reward.txt.
REWARD_FILE="${YEL003_REWARD_FILE:-/logs/verifier/reward.txt}"
STATUS_FILE="$LOG_DIR/verification-status.txt"
TEST_LOG="$LOG_DIR/test-stdout.txt"
REPORT="$LOG_DIR/pytest-results.xml"
VENV_DIR="$LOG_DIR/verifier-venv"
completed=0

mkdir -p "$LOG_DIR"

write_reward() {
  local value="$1"
  chmod 0644 "$REWARD_FILE" 2>/dev/null || true
  printf '%s\n' "$value" > "${REWARD_FILE:-/logs/verifier/reward.txt}"
  chmod 0444 "$REWARD_FILE"
}

write_status() {
  chmod 0644 "$STATUS_FILE" 2>/dev/null || true
  printf '%s\n' "$1" > "$STATUS_FILE"
  chmod 0444 "$STATUS_FILE"
}

on_exit() {
  if [ "$completed" -ne 1 ]; then
    write_status "INCOMPLETE: verifier exited before pytest completion"
    write_reward 0.000
  fi
}

on_signal() {
  write_status "INCOMPLETE: verifier interrupted before pytest completion"
  write_reward 0.000
  completed=1
  exit 0
}

write_reward 0.000
write_status "INCOMPLETE: pytest has not completed"
trap on_exit EXIT
trap on_signal INT TERM HUP

chmod 0644 "$REPORT" "$TEST_LOG" 2>/dev/null || true
rm -f "$REPORT" "$TEST_LOG"
python3 -m venv "$VENV_DIR"

if [ -d "$TEST_DIR/wheels" ]; then
  "$VENV_DIR/bin/python" -m pip install \
    --disable-pip-version-check \
    --no-cache-dir \
    --no-index \
    --find-links "$TEST_DIR/wheels" \
    "pytest==8.4.1" >/dev/null
fi

set +e
timeout --signal=TERM --kill-after=10s 100s \
  "$VENV_DIR/bin/python" -u -m pytest \
  -p no:cacheprovider \
  -s \
  -o cache_dir=/nonexistent \
  --junitxml="$REPORT" \
  "$TEST_DIR/test_outputs.py" -rA > "$TEST_LOG" 2>&1
RC=$?
set -e

cat "$TEST_LOG" 2>/dev/null || true

if [ "$RC" -ne 0 ] && [ "$RC" -ne 1 ]; then
  case "$RC" in
    124|125|126|127|137|143)
      write_status "INCOMPLETE: pytest did not complete; runner exited with code $RC"
      ;;
    *)
      write_status "INCOMPLETE: pytest exited before a scoreable report with code $RC"
      ;;
  esac
  write_reward 0.000
elif [ ! -s "$REPORT" ]; then
  write_status "INCOMPLETE: pytest completion report missing"
  write_reward 0.000
else
  if python3 "$TEST_DIR/score.py" \
    --config "$TEST_DIR/scoring.json" \
    --junit "$REPORT" \
    --report-out "$LOG_DIR/scoring-report.json" \
    --reward-out "$REWARD_FILE"; then
    REWARD=$(cat "$REWARD_FILE")
    case "$REWARD" in
      0.[0-9][0-9][0-9]|1.000) ;;
      *)
        write_status "INCOMPLETE: weighted scorer produced invalid reward"
        write_reward 0.000
        completed=1
        exit 0
        ;;
    esac
    chmod 0444 "$REWARD_FILE"
    write_status "COMPLETED: weighted scoring finished with reward=$REWARD"
  else
    write_status "INCOMPLETE: weighted scoring rejected the report"
    write_reward 0.000
  fi
fi

completed=1
exit 0
