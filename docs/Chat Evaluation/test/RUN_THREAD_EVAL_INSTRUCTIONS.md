# Run Thread Eval Instructions

This file is the minimal checklist to run the 6+ turn chat evaluation thread and capture the required artifacts.

## Prerequisites

1. Backend is running and reachable at `http://localhost:8000`.
2. Local Postgres has data ingested (documents + chunks), not only sources.
3. Evaluation set exists: `docs/Chat Evaluation/CHAT_EVAL_50_CASES.csv`.

## Optional (recommended for developer traces)

- Set backend env `ORCHESTRATOR_V1_1=1`
- Set backend env `DEBUG_TRACE=1`
- The runner sends `X-Developer-Debug: 1` automatically.

## Run the frozen 6+ turn thread

```bash
python backend/scripts/evaluate_chat_cases.py \
  --api-url http://localhost:8000 \
  --thread-case-ids F01,F11,L15,P28,S38,U48,A45 \
  --results-path "docs/Chat Evaluation/CHAT_EVAL_THREAD_RESULTS.csv" \
  --summary-path "docs/Chat Evaluation/CHAT_EVAL_THREAD_SUMMARY.txt" \
  --log-jsonl "docs/Chat Evaluation/CHAT_EVAL_THREAD_LOG.jsonl" \
  --enforce \
  --max-abstain-mismatch 2 \
  --max-citation-miss 5 \
  --max-latency-p95-ms 9000 \
  --min-answer-len 250 \
  --max-short-answers 1
```

## Outputs

- CSV per-turn results: `docs/Chat Evaluation/CHAT_EVAL_THREAD_RESULTS.csv`
- Text summary: `docs/Chat Evaluation/CHAT_EVAL_THREAD_SUMMARY.txt`
- Full per-turn JSONL log (request/response + dev traces when enabled): `docs/Chat Evaluation/CHAT_EVAL_THREAD_LOG.jsonl`

