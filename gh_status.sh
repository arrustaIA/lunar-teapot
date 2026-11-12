#!/usr/bin/env bash
# Salute delle sessioni GitHub Actions del bot PAPER: ultimi run + età dell'heartbeat nello stato scaricato.
cd "$(dirname "$0")"
REPO=$(git remote get-url origin | sed -E 's#.*github.com[:/]##; s#\.git$##')
gh run list -R "$REPO" -w session.yml -L 6 --json status,conclusion,event,createdAt,displayTitle \
  --jq '.[] | "\(.createdAt) \(.event) \(.status) \(.conclusion // "-")"' 2>/dev/null | while read -r ts ev st co; do
  echo "run $(TZ=Europe/Rome date -d "$ts" '+%d/%m %H:%M') (Roma) $ev $st $co"; done
if [ -f logs/scheduler_heartbeat ]; then
  hb=$(cat logs/scheduler_heartbeat); age=$(( ( $(date +%s) - $(date -d "$hb" +%s) ) / 60 ))
  echo "heartbeat scheduler GitHub: $hb (ora di Roma), $age min fa (stato scaricato con ./sync_github.sh pull)"
fi
