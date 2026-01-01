# Chat Evaluation Requirements

This document captures the current evaluation plan for the Legal GraphRAG chat, covering the 6+ turn thread, KPIs, logging, and execution flow discussed with the team.

## Goals

1. Maintain the North Star goal intact (no edits to `NorthStarGoal.md`).
2. Evaluate at least one deterministic 6+ turn thread anchored on the CSV cases `F01,F11,L15,P28,S38,U48,A45`.
3. Keep the orchestrator LLM-driven, ensure `ORCHESTRATOR_V1_1=1`, `X-Developer-Debug: 1`, and when needed `DEBUG_TRACE=1`.
4. Verify usefulness: answers must be at least `--min-answer-len` characters long (default 250), enforce through KPI gating.
5. Capture full developer logs for each turn via `--log-jsonl`.
6. Retain mixture of ANSWER/ASK/ABSTAIN cases, including the CSV-specified `expect_abstain` rows plus manual missing-info cases.
7. Gate citations, abstentions, follow-ups, latency, and short answers via `--enforce` thresholds.
8. Run in a controlled environment with fixed corpus (P1 sources + any ingested P2/P3 updates) and recorded `max_sources` if desired.

## Execution

1. Confirm `backend/.env` (model + retrieval knobs) and workflow values (`GEMINI_CHAT_MODEL`, `RAG_*` env).
2. Start the backend with `ORCHESTRATOR_V1_1=1` and `DEBUG_TRACE=1` when you need full traces logged.
3. Run the evaluator:

   ```bash
   python backend/scripts/evaluate_chat_cases.py \
     --api-url http://localhost:8000 \
     --thread-case-ids F01,F11,L15,P28,S38,U48,A45 \
     --results-path docs/Chat\ Evaluation/CHAT_EVAL_THREAD_RESULTS.csv \
     --summary-path docs/Chat\ Evaluation/CHAT_EVAL_THREAD_SUMMARY.txt \
     --log-jsonl docs/Chat\ Evaluation/CHAT_EVAL_THREAD_LOG.jsonl \
     --enforce \
     --max-abstain-mismatch 2 \
     --max-citation-miss 5 \
     --max-latency-p95-ms 9000 \
     --min-answer-len 250 \
     --max-short-answers 1
   ```

4. Optionally add `--preflight-docs` and `--max-sources <n>` or adjust `--case-ids` for additional runs.
5. Review outputs:
   - CSV `CHAT_EVAL_THREAD_RESULTS.csv`
   - Summary text file
   - JSONL log for developer traces + full turn history

6. Track KPI violations (abstain mismatches, citation misses, short answers, latency). Failures surface via `--enforce`.

7. Store new results alongside prior reports (see `docs/Chat Evaluation/` versioned files).

## Next Steps

- Consider autotuning knobs once these requirements are stabilized.
- Keep the core thread constant while experimenting with supplemental CSV cases.

