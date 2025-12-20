# V1.1 Sprint Plan - Multi-Query Retrieval + Judge Pipeline

Goal: Improve P1 recall and answer usefulness while preserving legal hierarchy and NorthStarGoal.md constraints.

Versioning rule: All changes to scripts must be in V1.1 versions (new files or new versioned entry points). No edits to V1.0 code paths.

## Scope
- Add a V1.1 pipeline that:
  - Expands queries (deterministic + limited LLM variants).
  - Retrieves per query.
  - Fuses and deduplicates within hierarchy buckets.
  - Generates answer from fused chunks.
  - Runs a judge pass to validate usefulness and support, then optionally redoes.
- Add logging/metadata for judge verdict and redo.
- Update documentation to reference V1.1 pipeline and sprint outputs.

Out of scope:
- Rewriting the data model.
- Changing the ingestion pipeline.
- Removing or weakening hierarchy ordering.

## Deliverables
1) V1.1 pipeline spec (inputs, outputs, steps, and hierarchy rules).
2) V1.1 scripts (new versioned modules/entry points).
3) Logging/metadata schema for judge results.
4) Updated docs referencing V1.1 behavior.
5) A/B evaluation on P1 question set with report.

## Sprint Tasks
### 1) Spec and design
- Draft V1.1 pipeline spec (per-step inputs/outputs).
- Define hierarchy-safe fusion rules.
- Define judge rubric aligned to NorthStarGoal.md + AUTOMATED_EVAL_RULES.md.
- Define redo conditions (unsupported claims, incoherent or not useful, answer contradicts sources).

### 2) Query expansion design
- Deterministic templates: law number, BOE ID, acronym expansion, "objeto de", "ambito de".
- LLM variants: max 2-3, filtered for relevance.
- Limit total expanded queries to avoid noise.

### 3) Implementation (V1.1 only)
- New versioned script/modules (no edits to V1.0 code path).
- Per-query retrieval and per-bucket fusion.
- Dedup by document_id + chunk_label.
- Answer generation from fused chunks.
- Judge pass and optional redo (no new retrieval during redo).

### 4) Instrumentation and evaluation
- Persist judge verdict + reasons in metadata.
- Update evaluation scripts to compare V1.0 vs V1.1 on P1 set.
- Create a report summarizing hit rate and answer quality changes.

## Acceptance Criteria
- Hierarchy preserved: Normativa > Doctrina > Jurisprudencia in output.
- Retrieval hit rate improves vs baseline on P1 set.
- Judge rejects unsupported claims; no hallucinated citations.
- Answer usefulness improves on the 25-question subset.

## Metrics
- Retrieval hit rate on P1 set.
- Percentage of answers that abstain despite relevant sources (should drop).
- Judge pass rate and redo rate.
- Average sources per answer (by category).

## Artifacts
- docs/Chat Evaluation/P1_eval_questions.json
- docs/Chat Evaluation/P1_eval_retrieval_report.md
- docs/Chat Evaluation/P1_eval_answer_report.md
- New V1.1 evaluation report (to be generated)

## Risks and Mitigations
- Query expansion noise: cap variants, filter by similarity.
- Judge over-rejecting: tune rubric to focus on grounded support.
- Performance hit: cache expanded query embeddings when possible.
