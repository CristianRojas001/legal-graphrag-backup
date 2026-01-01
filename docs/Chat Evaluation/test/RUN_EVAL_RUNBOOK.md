# RUN_EVAL_RUNBOOK

## What this runbook is for
A minimal, repeatable way to run the evaluation suite and interpret results.

## Suites
1. Unit: fast, deterministic, no network
2. Integration: GraphRAG retrieval + answer formatting
3. System: end to end, API and DB, optional
4. Performance: latency and throughput
5. UAT: manual spot checks with artists

## Standard command flow (example)
1. Run unit tests
2. Run retrieval integration tests
3. Run system tests on the frozen eval set
4. Review hard gate failures first, then soft score dips
5. Only then tune prompts or ranking

## System eval (frozen CSV)
Runs the frozen 50-case CSV against the v1.1 chat endpoint and writes:
- `docs/Chat Evaluation/CHAT_EVAL_50_RESULTS.csv`
- `docs/Chat Evaluation/CHAT_EVAL_50_SUMMARY.txt`

```bash
python backend/scripts/evaluate_chat_cases.py --api-url http://localhost:8000
```

## 6+ turn “thread” eval (shared session_id)
Runs a single continuous conversation (shared `session_id`) across a fixed list of case IDs.

Example frozen core thread (8 turns because `F01` has 2 turns in the CSV):
```bash
python backend/scripts/evaluate_chat_cases.py --api-url http://localhost:8000 `
  --thread-case-ids F01,F11,L15,P28,S38,U48,A45 `
  --results-path "docs/Chat Evaluation/CHAT_EVAL_THREAD_RESULTS.csv" `
  --summary-path "docs/Chat Evaluation/CHAT_EVAL_THREAD_SUMMARY.txt" `
  --log-jsonl "docs/Chat Evaluation/CHAT_EVAL_THREAD_LOG.jsonl"
```

Optional: preflight that `expected_docs` are present via `/search`:
```bash
python backend/scripts/evaluate_chat_cases.py --api-url http://localhost:8000 `
  --thread-case-ids F01,F11,L15,P28,S38,U48,A45 `
  --preflight-docs
```

Optional: enforce KPI thresholds (start loose; tighten gradually):
```bash
python backend/scripts/evaluate_chat_cases.py --api-url http://localhost:8000 `
  --thread-case-ids F01,F11,L15,P28,S38,U48,A45 `
  --enforce `
  --max-abstain-mismatch 2 `
  --max-citation-miss 5 `
  --max-latency-p95-ms 9000 `
  --min-answer-len 250 `
  --max-short-answers 1
```

## Triage order
1. Hallucination or missing citation (hard fail)
2. Wrong hierarchy behavior
3. Wrong retrieval (missing key chunk)
4. Helpfulness and clarity
5. Performance

## Reporting
After each iteration, write a short changelog:
- What changed
- Which eval cases improved or regressed
- Metrics summary: accuracy, hallucination rate, usefulness proxy, latency
