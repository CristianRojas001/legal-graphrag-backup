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
