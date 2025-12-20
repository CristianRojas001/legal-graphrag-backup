# Legal GraphRAG – RAG Quality & Citation Grounding Plan

**Last updated**: 2025-12-13  
**Owner**: Codex + Developer  
**Scope**: Backend RAG behavior, citation integrity, evaluation harness, and safe abstention when evidence is missing.

---

## 1. Problem Statement

Current answers are frequently **generic** and often include **irrelevant or incorrect citations**, e.g.:
- IRPF questions cited with non-relevant IRPF articles (e.g. “borrador”), plus IVA/IS/mercantile sources.
- IVA question produced an incorrect “tipo general 15%” claim, apparently copied from an outdated chunk.
- Many answers cite sources that do not support the claim (high hallucination risk).

This is not only an LLM prompting issue; it is primarily **evidence quality + citation freedom**:
1. Retrieval returns off-topic chunks (coverage + ranking).
2. The LLM is still required to produce a “legal” answer, even when evidence is weak.
3. The LLM can freely invent citations or overgeneralize from weak context.

---

## 2. Goals (What “Works as Planned” Means)

### 2.1 Safety & Truthfulness (Primary)
- If the corpus lacks relevant evidence, the system must **abstain** and provide a helpful “what to do next” answer.
- The system must **not** output numeric/legal claims (rates, deadlines, conditions) unless they are **explicitly supported by retrieved text**.

### 2.2 Citation Integrity (Primary)
- Citations must be **grounded**: every citation refers to an actually retrieved chunk.
- Citations must be **relevant**: cited chunks must contain supporting text for the associated claim.

### 2.3 Usefulness (Secondary)
- When evidence exists, answers should be specific and actionable.
- Multi-turn follow-ups should reuse prior context only when it remains relevant and supported.

### 2.4 Measurability (Primary)
- A repeatable evaluation harness runs a fixed set of scenarios and outputs a report:
  - retrieval quality metrics
  - citation validity metrics
  - abstention rate
  - latency

---

## 3. Non-goals (For This Refinement Phase)
- No “perfect legal advice” guarantee.
- No broad corpus ingestion redesign (unless triggered by measured coverage gaps).
- No major UI redesign; focus is backend correctness and evaluation.

---

## 4. Constraint: Is “Only P1 Data” the Problem?

**It is a problem for coverage**, not for safety.

- Many artist scenarios require very specific regulations and/or administrative doctrine (AEAT/DGT/TGSS) that might not be present in the current P1 ingest set.
- With P1-only, the correct behavior in many cases is: **abstain + guidance**, not “best-effort guess with citations”.

Therefore, the plan is:
1) Make the system safe and citation-grounded **with the current corpus**.
2) Measure which scenarios fail due to **coverage** vs **ranking**.
3) Expand corpus *only* when metrics show a true knowledge gap.

---

## 5. Proposed Architecture Changes (Strategic Order)

### 5.1 Evaluation Harness (Baseline)
Create a deterministic evaluation runner for a canonical scenario set (initially 10 “artist scenarios”).

**What it captures**:
- query
- predicted intent/area
- retrieval results (top-k chunk metadata + scores)
- final answer text
- extracted citations (structured)
- pass/fail flags

**Why first**: prevents “fixing blindly”; enables safe iteration and regression detection.

### 5.2 Answerability Gating (“Abstain Mode”)
Before generation, score “evidence quality”. If insufficient, do **not** call the LLM (or call with an “abstain format”).

**Evidence Quality Score (EQS)** proposal (simple, explainable):
- `intent_confidence`: 0..1 (from classifier)
- `keyword_overlap`: 0..1 (query keywords found in top chunks)
- `law_family_match`: 0..1 (top chunks contain expected law family for intent)
- `score_strength`: 0..1 (top chunk similarity/rrf above thresholds)
- `diversity`: 0..1 (not all chunks from clearly unrelated sources)

**Trigger**:
- If `law_family_match` is false OR `keyword_overlap` below threshold → abstain.
- If top source types are mismatched (e.g., mercantile law for IRPF) → abstain.

**Abstain answer format**:
- Acknowledge limits: “No tengo información específica en las fuentes disponibles…”
- Ask 2–3 clarifying questions.
- Suggest next steps (consult AEAT/DGT, add missing corpus sources, etc.).
- Keep titles consistent with the conversational format:
  - **Normativa aplicable**
  - **Criterios administrativos**
  - **Jurisprudencia relevante**
  - **Requisitos y notas**

### 5.3 Retrieval Tightening (Intent Routing + Re-ranking)
Improve “what context is fed to the LLM”.

**Tactics**:
- Intent routing: restrict candidate sources by area (Fiscal/PI/Laboral).
- Add hard filters for key queries:
  - IRPF/retenciones → prefer IRPF + reglamento + LGT + AEAT/DGT
  - IVA → prefer Ley IVA + reglamento + doctrina (if present)
  - PI → prefer TRLPI
  - Autónomos/RETA → prefer SS / criterios admin (if present)
- Re-rank retrieved chunks using an interpretable score:
  - base (vector/rrf)
  - + keyword hit bonus
  - + law family match bonus
  - − penalty for unrelated law families (LSC/PGC/Comercio when Fiscal query)
- Ensure diversity: require at least 1 chunk from best-matching law family if available.

### 5.4 Citation Grounding (Make Citations Non-forgeable)
Stop free-text citations.

**Change**:
- Provide the LLM with sources in a strict schema and require citations by `source_id` + `label` (or `chunk_id`).
- Post-validate citations in the generated answer:
  - If a cited id/label isn’t present in retrieved sources → remove it and flag.
  - If the answer contains numbers/percentages/dates without an explicit quote in sources → flag and force abstain or re-ask.

**Optional** (stronger):
- “Quote-required” rule for numeric claims:
  - For any numeric/legal claim, the answer must include a quoted excerpt from a retrieved chunk.

### 5.5 Corpus Expansion Trigger (Only if Needed)
After gating/grounding/retrieval improvements, run the scenario suite:
- If failures are due to “no relevant sources exist in top-N even after rerank”, classify as **coverage gap**.
- Expand only with the exact missing materials (e.g., IRPF retenciones rules, IVA cultural types/exemptions, TGSS criteria).

---

## 6. Metrics & Acceptance Criteria

### 6.1 Required (MVP Refinement)
- **Citation validity**: 0 invalid citations in the 10-scenario suite.
- **No unsupported numeric claims**: 0 occurrences.
- **Abstain correctness**: when evidence is missing, abstain is used instead of fabricated claims.

### 6.2 Target Improvements
- Retrieval relevance: at least 1 “law-family match” source in top-5 for ≥ 80% scenarios (or abstain).
- Latency: keep within existing budget; optimize later.

---

## 7. Implementation Notes (Pragmatic)

1) Start with gating + citation validation (highest safety ROI).
2) Only then tune retrieval and re-ranking.
3) Keep the changes reversible and behind flags/config where possible.
4) Log internal diagnostics (intent, EQS, selected sources) for debugging.

