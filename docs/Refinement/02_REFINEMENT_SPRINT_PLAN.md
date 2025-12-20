# Legal GraphRAG – Refinement Sprint Plan (Quality, Citations, Evaluation)

**Version**: 1.0  
**Last Updated**: 2025-12-13  
**Owner**: Codex + Developer  
**Duration**: 5 days (adjustable)  
**Primary Goal**: Stop hallucinated/irrelevant citations and produce safe, evidence-based answers with a measurable evaluation loop.

---

## 1. Sprint Goal

Deliver a RAG pipeline that:
- Abstains when the corpus lacks relevant evidence.
- Produces citations that are always grounded in retrieved chunks.
- Provides measurable quality results on 10 “artist scenarios”.

---

## 2. Definition of Done (DoD)

### Functional
- [ ] For the 10 scenarios, **0 invalid citations** (every citation maps to retrieved sources).
- [ ] For the 10 scenarios, **0 unsupported numeric claims** (percentages/dates/thresholds without explicit support).
- [ ] For scenarios where evidence is missing (P1-only gaps), system returns **abstain + guidance**.

### Engineering
- [x] Automated runner produces a report artifact (JSON/MD) with results.
- [ ] Unit tests cover gating and citation validation logic.
- [x] CI-local execution: `python -m pytest` passes.

---

## 3. Inputs

### 3.1 Scenario Set (Initial 10)
These are the canonical scenarios to evaluate end-to-end:
1) Home studio deducción IRPF (autónomo)
2) Retención IRPF actuaciones en directo
3) IVA entradas concierto pequeño
4) Duración derechos de autor canción (España)
5) Cesión derechos uso obra musical (contrato)
6) Gastos desplazamiento/dietas en gira
7) Facturar bolo a cliente UE (IVA/inversión)
8) Obligaciones al vender merchandising online
9) Alta autónomos para actuar esporádicamente
10) IVA servicios culturales a ONG

Note: With P1-only ingestion, some may be “coverage gaps”; expected behavior is abstain.

---

## 4. Work Breakdown (Day-by-Day)

### Day 1: Evaluation Harness + Baseline Report
- [x] Add an evaluation runner script (calls `/chat/` with the 10 queries).
- [x] Save outputs: answer, sources, latency, model, intent metadata.
- [ ] Add a simple parser to extract citations from output (initial heuristic).
- [x] Produce baseline report in `docs/Refinement/` (markdown summary + JSON artifact).

**Deliverable**: Baseline report shows current failure modes (irrelevant citations, numeric hallucinations).

### Day 2: Answerability Gating (“Abstain Mode”)
- [x] Implement evidence quality scoring in backend before LLM generation.
- [x] Add threshold configuration (settings/env):
  - min keyword overlap
  - must-have law family match per intent
  - min similarity/rrf threshold
- [x] Implement abstain response template (same section format, conversational).

**Deliverable**: Scenarios without evidence no longer produce invented claims/citations.

### Day 3: Citation Grounding + Validation
- [x] Change the answer format to cite using only provided source identifiers.
- [ ] Add post-generation validator:
  - remove/flag citations not present in retrieved sources
  - fail-safe to abstain if validator detects unsupported numeric claims
- [ ] Add tests for validator and numeric claim detection.

**Deliverable**: 0 invalid citations in the scenario suite (or abstain).

### Day 4: Retrieval Tightening (Intent Routing + Re-ranking)
- [ ] Improve intent classification robustness for fiscal/IVA/IRPF/PI/laboral.
- [ ] Add routing filters to reduce off-topic sources.
- [ ] Add re-ranking (keyword+law-family boosts, penalties for mismatched families).
- [ ] Re-run evaluation; compare relevance metrics.

**Deliverable**: More scenarios retrieve correct “law family” evidence (IRPF/IVA/PI) rather than Comercio/LSC/PGC.

### Day 5: Review, Fixes, and “Corpus Gap” Decision
- [ ] Human review of the 10 scenario outputs focusing on:
  - correctness of claims
  - whether abstentions are appropriate
  - citation relevance
- [ ] Decide if P1-only is sufficient:
  - classify failures: ranking vs coverage
  - if coverage: define minimal ingestion additions required
- [ ] Update sprint plan + final report in `docs/Refinement/`.

**Deliverable**: “Go/No-go” for expanding corpus beyond P1; final refinement report.

---

## 5. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| P1 corpus lacks needed laws | High | High | Abstain mode + targeted ingestion plan |
| LLM still fabricates | Medium | High | Citation validator + quote-required numeric claims |
| Retrieval still noisy | Medium | Medium | Intent routing + re-ranking + diversity constraints |
| Latency increases | Medium | Medium | Keep gating cheap; optimize after correctness |

---

## 6. Acceptance Test Checklist (Quick)

- [ ] Each scenario returns either (a) grounded answer with citations or (b) abstain with guidance.
- [ ] No scenario returns a numeric rate/percent unless quoted from a retrieved chunk.
- [ ] Citations: all refer to provided source IDs/labels.
- [ ] Evaluation runner produces a stable report.
