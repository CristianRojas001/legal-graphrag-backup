# LegalGraphRAG consultation agent — top-3 root cause and solution architecture (2026-11-01)

> **Status: WORK IN PROGRESS.** This file is pushed incrementally at the owner's request. Sections A–J will be filled in as the investigation proceeds. Until the status line reads FINAL, treat every conclusion here as provisional. The running evidence log (§0) records discoveries in the order they were made.

Evidence labels used throughout: **[E]** confirmed from code or recorded evidence; **[S]** strongly supported; **[H]** hypothesis; **[P]** proposal/projection.

---

## 0. Evidence log (running)

### 0.1 Repository and evidence verification

| Item | Finding |
|---|---|
| Code repository | `CristianRojas001/legalgraphrag.v2.0`, local clone `/home/user/legalgraphrag.v2.0` (shallow), checked out at `analysis/consultation-agent-solutions-20261030` @ `9e3fdb06` (the P1–P13 investigation). Clean tree, single worktree. |
| Report repository | This report is committed to `CristianRojas001/legal-graphrag-backup`, branch `claude/friendly-meitner-ji0v9m` (the only push-authorised branch in this session). The previous Jev design (`docs/design/JEV_SEMANTIC_FACT_VERIFICATION_DESIGN_2026-10-31.md`) lives here too. |
| Frozen consultation implementation | `impl/consultation-agent-s1-s7-20261030` @ `d4304d10` — present on remote, fetched read-only. |
| Revised E-A evaluation | `eval/consultation-agent-ea-20261030` @ `3abf3541` — present. |
| Numerical-validator + E-B campaign | `impl/reliability-eb-20261031` @ `4d28729d` (11 commits on `d4304d10`) — **present on the remote** (the brief described it as local/unpushed). |
| Jev semantic-fact verification | `impl/jev-semantic-fact-verification-v1` @ `168b7cc2` (21 commits on `d4304d10`, diverging from the E-B branch) — present on remote. Contains the Jev 1.14 A/B pilot (`docs/evidence/v3/jev114-ab-evaluation-20261031/REPORT.md`). |
| **JEV triage + Repair V2 campaign** | `impl/jev-triage-20261101`, commit `0de2b56a` — **NOT FOUND**: absent from `git ls-remote` of both repositories, `0de2b56a` is not a valid object locally, and no file in any fetched branch mentions "triage" or "Repair V2" in the agent code/docs. Every statement in this report about that campaign is therefore limited to what the brief says about it; none of its code or `RESULTS.md` could be inspected. |
| Agent code location | `backend/apps/legal_graphrag/services/v3/agent/` (`validator.py` ≈2.1k lines, `loop.py`, `turn_manager.py`, `state.py`, `context.py`, `contracts.py`, `render.py`, `numbers_es.py`, `epistemic_es.py`, `tools/`, `prompts/`). Jev branch adds `fact_verifier.py`, `fact_runtime.py`, `fact_reconciliation.py`, `llm/decisions.py`, `prompts/system_v4.md`. |
| E-A raw evidence | `docs/V3/simplification/live_ea_s1_s7_2026-10-30/raw/ea_run_2/` on the E-A branch: 104 turn files, 104 diagnostics, `PER_TURN_ROWS.jsonl`. **Each diagnostic retains the full model transcript, including the first `submit_consultation` arguments, the validation report returned to the model, and the final accepted submission.** This makes an exhaustive, zero-cost first-vs-final repair diff possible (the E-A evaluation only sampled 7 turns). |

### 0.2 Prior conclusions carried in (not re-tested)

- P1–P13 report (`solution_architecture_review_2026-10-30/OPUS_FINAL_DECISION_REPORT.md`): critical defects were deterministic state-integrity defects; S1–S7 fixed 409s, empty overrides, hypothetical overwrites, identifier leakage [E].
- Revised E-A (`INDEPENDENT_LEGAL_RELIABILITY_EVALUATION.md`): turn-0 legal substance 32/36, as-delivered 27/36; repair turns 66/104 (63 %), not improved vs E-1 (54 %); `UNTRACED_NUMBER` the dominant first-report code; four asked-unsettled anomalies (H-M4, H-N2, EA-B04, EA-B05); blanket «No lo sé» over-binding (EA-B02); paraphrased refusal not bound (EA-B04/B05); H-P3 omission of RETA/alta; `list_corpus_documents` called 0 times [E].
- E-B `RESULTS.md`: F1/F2/F3 cut UNTRACED spans 146→61 on deterministic replay with 0 must-reject regressions, but live repair turns did not fall (monitor 20/22 vs 19/22; matched 27 vs 24). P7-A and P7-B rejected: no CORRECT gain, +26 %/+41 % latency, +8/+4 identifier leaks, P7-B +33 markers mostly from malformed citation tokens [E].
- Jev 1.14 pilot: D1+D2 precision 0.884 / recall 0.977 vs lexicon 0.448 / 0.547; D1 alone over-reads UNCLEAR as STATES_NOT_KNOWN (UNCLEAR recall 0.323); D2 was required to block blanket «No lo sé» broadcasts (0/15 accepted) [E].

### 0.3 Discovery 1 — Exhaustive repair diff on E-A (new, zero cost)

Method: for each of the 104 E-A diagnostics, parse every `submit_consultation` call in the transcript, the validation report returned to it, and compare the **first** with the **last** model submission. Script kept in the session scratchpad (`repair_diff.py`); reproducible from the E-A branch alone.

Results [E]:

| Measure (65 repaired turns; 39 turns had a single accepted submission) | Value |
|---|---|
| Submissions per turn | 2 in all 65 repaired turns (exactly one repair round each); 1 wall-clock salvage; 0 forced submissions |
| First-report category | 31 format/provenance-only, 18 contract/state-only, 16 mixed |
| First-report codes (turns) | UNTRACED_NUMBER 35; CONCLUSION_FACT_UNKNOWN 10; UNKNOWN_NOT_STATED 9; MARKER_UNRESOLVED 8; QUOTE_FRAGMENT_NOT_FOUND 7; DECIDED_CONDITION_UNBOUND 7; CITED_NOT_READ 6; BASIS_AUTHORITY_MISMATCH 6; MISSING_RESULT 5; QUOTE_FRAGMENT_ORDER 4; SCENARIO_PREMISE_MISSING 3; QUOTE_NOT_IN_USER_MESSAGES 3; others ≤2 |
| Turns where the repair dropped a **structured citation to a provision that had been read** | **0 / 65** |
| Turns where the repair dropped a citation to an unread unit | 3 (correct behaviour) |
| Turns losing statute mentions in prose ("artículo N", "art. N") across all results | **8 / 65**, 38 of 491 mentions |
| Turns where ≥1 conclusion text disappeared (no ≥0.8 match after repair) | 10 / 65 (14 of 313 conclusions) |
| Turns where figures in prose decreased | 27 / 65 |
| Turns where an issue outcome changed | 6 / 65 (mostly MISSING_RESULT adding a result) |

Representative damage (first → repaired):
- **V24.00** (sole code `UNTRACED_NUMBER`, no location in detail): "causas tasadas del artículo 331.1 de la LGSS" → "causas tasadas legalmente". The statute number was read as an untraced figure and the model deleted it.
- **V28.00** (codes `DECIDED_CONDITION_UNBOUND`, `CONCLUSION_FACT_UNKNOWN`): "Reglamento del IRPF (arts. 82 a 86)" → pointer removed; "(art. 83)" → "[[c:c4]]"; "reducciones del artículo 18 de la Ley" → "reducciones"; "(no se tiene en cuenta la circunstancia del art. 61.2.ª …)" deleted. Repair of a *contract* defect rewrote unrelated prose.
- **H-N2.02**: "sujeta al IVA por el artículo 4.Uno de la Ley del IVA" → "sujeta al IVA".
- **V09.00**: arts. 90/91 pointers removed (already reported by E-A).

Interpretation so far:
1. **[E] Repair damage is a prose phenomenon, not a citation-structure phenomenon.** The structured citation layer is protected; the free-text rewriting the model performs during a whole-submission resubmission is not.
2. **[E] Damage is not confined to number violations.** V28.00 shows a contract-only report producing prose loss: the repair protocol asks the model to resubmit the *entire* submission, so any violation licenses a full rewrite.
3. **[E] At `d4304d10` the UNTRACED detail carried no location and no value**, so the model scrubbed statute numbers elsewhere. F3 (E-B branch) adds field/sentence/offset location; this addresses one trigger, not the whole-resubmission mechanism.

### 0.4 Discovery 2 — Why F1/F2/F3 did not lower repair frequency (from E-B replay data)

`workstream_a/replay_summary.json` on the E-B branch, 102 replayable E-A first submissions [E]:

- Violation-code counts before → after F1/F2/F3: **only `UNTRACED_NUMBER` changed (67 → 38)**; every other code is identical (UNKNOWN_NOT_STATED 19, CONCLUSION_FACT_UNKNOWN 16, DECIDED_CONDITION_UNBOUND 13, MARKER_UNRESOLVED 12, QUOTE_FRAGMENT_NOT_FOUND 10, QUOTE_NOT_IN_USER_MESSAGES 8, BASIS_AUTHORITY_MISMATCH 8, CITED_NOT_READ 7, CITATION_UNUSED 6, MISSING_RESULT 5, QUOTE_FRAGMENT_ORDER 5, …).
- Only 8 of 102 first submissions become violation-free.
- Repair is triggered by **any** violation (one round per turn, whole-submission). Since ~57 of the 65 repaired turns still carry at least one non-UNTRACED violation or a residual UNTRACED span, removing number false positives could, by construction, lower the repair *rate* by at most ~8 turns per 104. The live result (no measurable drop) is consistent with that ceiling plus run-to-run variance. **[S] The repair-rate metric is governed by the binary "any violation ⇒ full resubmission" policy, not by the accuracy of any single check.**

### 0.5 Pending (in progress)

- Code-path tracing of validator → repair → finalize (violation table, repair eligibility, original-vs-repaired handling).
- Fact path: message → fact op → V8/lexicon/Jev → state → context next turn; status enumeration and the asked-unsettled drop mechanism.
- Exception path: contracts for conditions/alternatives, prompt §D, read/related tools, P7-A/P7-B mechanism, E-B grader flags vs read sets.
- Sections A–J.
