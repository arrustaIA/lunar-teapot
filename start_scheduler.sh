#!/usr/bin/env bash
# PAPER. Il bot ora gira su GitHub Actions: sul box lo scheduler resta SPENTO (altrimenti due scheduler
# opererebbero sullo stesso ledger). Questo script mostra lo stato delle sessioni GitHub.
# Solo in emergenza (GitHub fermo per giorni): PT_LOCAL_SCHEDULER=1 ./start_scheduler.sh --local
cd "$(dirname "$0")"
if [ "$1" = "--local" ] && [ "$PT_LOCAL_SCHEDULER" = "1" ]; then
  pgrep -f "python3 scheduler.py" >/dev/null && { echo "scheduler locale già attivo"; exit 0; }
  PT_LOCAL_SCHEDULER=1 nohup setsid python3 scheduler.py >> logs/scheduler.log 2>&1 &
  echo "scheduler LOCALE avviato (ricordati di disattivare il workflow GitHub)"; exit 0
fi
echo "scheduler locale disattivato: il bot gira su GitHub Actions."
exec ./gh_status.sh
