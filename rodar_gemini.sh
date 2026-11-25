#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
set -a; . ./.env; set +a
for i in 1 2 3; do   # repete para tentar pares que falharam
  python -u juiz_llm.py --repo ./RESTestBench --provedor openai --modelo gemini-3.5-flash-lite \
    --base-url https://generativelanguage.googleapis.com/v1beta/openai/ --subamostra 100 --pausa 4
done
echo FIM
