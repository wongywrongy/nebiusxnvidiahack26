#!/bin/bash
# usage: run.sh <arm> [extra env...]  -- one arm of the A/B, shared cache and ledger, production caps
arm=$1; shift
cd /home/kyle/code/nebiusxnvidiahack26/.cache/accuracy-arms
mkdir -p runs/arms/$arm
env SPECCHECK_MODE=live \
  CACHE_DIR=/home/kyle/code/nebiusxnvidiahack26/.cache \
  CAMPAIGN_BUDGET_FILE=/home/kyle/code/nebiusxnvidiahack26/evidence/budget/campaign.sqlite3 \
  BUDGET_USD_PER_DAY=18.04944932 BUDGET_USD_PER_RUN=3 \
  BUDGET_TAVILY_CREDITS_PER_DAY=586 BUDGET_TAVILY_CREDITS_PER_ITEM=60 \
  FIX_MAX_CANDIDATES=1 FIX_CREDIT_CAP=12 INVESTIGATE_MAX_STEPS=6 INVESTIGATE_CREDIT_CAP=8 \
  MAX_CONCURRENCY=2 MAX_OUTPUT_TOKENS=65536 \
  RUNS_DIR=$PWD/runs/arms/$arm RECORDED_DIR=$PWD/runs/arms/$arm/recorded SCORES_FILE=$PWD/runs/arms/$arm/scores.json \
  BUDGET_USD_PER_RUN=6 "$@" .venv/bin/python scripts/record_live.py > runs/arms/$arm.log 2>&1
echo "exit $?" >> runs/arms/$arm.log
