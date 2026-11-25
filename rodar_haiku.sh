#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
set -a; . ./.env; set +a
for c in completo sem_requisito sem_spec; do
  python juiz_llm.py --repo ./RESTestBench --modelo claude-haiku-5-5 --condicao $c
  python juiz_llm.py --repo ./RESTestBench --modelo claude-haiku-5-5 --condicao $c   # repete falhas
done
echo FIM
