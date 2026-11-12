#!/usr/bin/env bash
# Scheduler wrapper (PAPER): ./run.sh <news|scan|trade|close_all|update|report|team_review> [args]
# Appends output to logs/cron_YYYY-MM-DD.log. Each script takes its own lock, so overlaps are safe.
cd "$(dirname "$0")" || exit 1
step="$1"; shift
python3 "${step}.py" "$@" 2>&1 | grep -v findfont | tee -a "logs/cron_$(date +%F).log"
