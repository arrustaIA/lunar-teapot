# Supporto Analista Notizie (LLM)

Script di sola lettura per le run successive dell'analisi LLM.

```
cd /workspace/paper-trading
python3 news_llm/extract_new_news.py --json          # notizie più recenti di data/news_llm_state.json
python3 news_llm/extract_new_news.py --hours 24 --json
```

- Legge `data/news.sqlite` in sola lettura (`mode=ro`) e `data/news_llm_state.json`.
- Cursore: `(last_published, last_news_id)`.
- Non scrive sul database, non tocca `news.py` né `data/ledger.sqlite`.
- La struttura dei giudizi è documentata in `../README.md`, sezione «Analisi LLM delle notizie».
