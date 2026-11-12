#!/usr/bin/env bash
# Sincronizzazione box <-> GitHub del bot PAPER (soldi finti).
#   ./sync_github.sh pull   scarica lo stato live (ledger, barre, notizie, log, report) dal branch `state`
#   ./sync_github.sh push   pubblica su `main` le modifiche al codice e i giudizi di Natasia (data/news_llm*.json[l])
#   ./sync_github.sh news   pubblica SOLO i giudizi di Natasia (data/news_llm*.json[l]); il codice resta locale
#   ./sync_github.sh        entrambi (prima pull, poi push)
# Il push passa sempre dal controllo dati sensibili (gh/secret_check.py): il repo è PUBBLICO.
set -u
cd "$(dirname "$0")" || exit 1
mode="${1:-all}"
do_pull() { python3 gh/state.py pull --box; }
do_push() {
  git add -A
  if git diff --cached --quiet; then echo "nessuna modifica da pubblicare"; else
    python3 gh/secret_check.py $(git diff --cached --name-only --diff-filter=AM) || { git reset -q; exit 2; }
    what=$(git diff --cached --name-only | head -5 | tr '\n' ' ')
    git commit -q -m "box: aggiornamento ${what}" && echo "commit: ${what}"
  fi
  git pull -q --rebase origin main || { echo "ATTENZIONE: rebase non riuscito, risolvere a mano"; git rebase --abort; exit 3; }
  git push -q origin HEAD:main && echo "main aggiornato su GitHub"
}
do_news() {
  git add data/news_llm.json data/news_llm_history.jsonl data/news_llm_state.json 2>/dev/null
  if git diff --cached --quiet -- data/; then echo "giudizi notizie già pubblicati"; return 0; fi
  python3 gh/secret_check.py data/news_llm.json data/news_llm_history.jsonl data/news_llm_state.json || { git reset -q; exit 2; }
  git commit -q -m "box: giudizi notizie" -- data/news_llm.json data/news_llm_history.jsonl data/news_llm_state.json
  git stash -q --include-untracked || true
  git pull -q --rebase origin main; rc=$?
  git stash pop -q 2>/dev/null || true
  [ $rc -eq 0 ] && git push -q origin HEAD:main && echo "giudizi notizie pubblicati su main"
}
case "$mode" in
  news) do_news ;;
  pull) do_pull ;;
  push) do_push ;;
  all)  do_pull; do_push ;;
  *) echo "uso: $0 [pull|push]"; exit 1 ;;
esac
