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

Conclusion-level damage (all 10 turns where a conclusion's text has no ≥0.8 match after repair were read) [E]. The dominant pattern is **de-specification**: the conclusion survives but loses its verifiable anchor.
- V28.00: "procedimiento general del Reglamento del IRPF (arts. 82 a 86)" → "…de retenciones del Reglamento del IRPF"; "reducciones del art. 18 de la Ley" → "reducciones por rendimientos irregulares"; "porque el art. 81.3 lo excluye cuando rige el tipo mínimo del art. 86.2" → "porque la norma que lo regula lo excluye…".
- V45.01 (code UNTRACED_NUMBER only): "El límite de cita del artículo 32.1 exige, acumulativamente: …" (the rule statement) removed; "decaería la cobertura del artículo 32.3 y se debilitaría la del 32.1" → "decaería la cobertura del límite de ilustración … y se debilitaría la del límite de cita".
- V10.00 (UNTRACED only): "(art. 4.Uno y art. 11.Uno LIVA)" removed from the conclusion.
- **H-N1.01** (MARKER_UNRESOLVED + UNTRACED): "margen = 230 €; base = 230 ÷ 1,10 = 209,09 €; cuota = 20,91 €" → the base and quota figures are removed entirely ("la cuota … queda comprendida en el precio"). **Correction (see §0.6b):** these figures are arithmetically consistent but apply the author's 10 % rate to the gallery's REBU margin, which the gold scores as wrong (general rate). Here the repair *accidentally* removed a legal error. This shows that repair outcomes are uncontrolled in both directions; it is not an example of correct content lost.
- H-N4.01: "dividiendo el precio entre 1,21" → "deshaciendo el impuesto incluido".
- EA-B02.02 / EA-B04.02 / EA-B05.02: state-summary conclusions rewritten (no legal loss; EA-B05 gained a Código de Comercio art. 342 reference).
None of the 10 changed a legal conclusion's polarity. The harm is lower precision and verifiability, and occasionally a missing answer figure.

Interpretation so far:
1. **[E] Repair damage is a prose phenomenon, not a citation-structure phenomenon.** The structured citation layer is protected; the free-text rewriting the model performs during a whole-submission resubmission is not.
2. **[E] Damage is not confined to number violations.** V28.00 shows a contract-only report producing prose loss: the repair protocol asks the model to resubmit the *entire* submission, so any violation licenses a full rewrite.
3. **[E] At `d4304d10` the UNTRACED detail carried no location and no value**, so the model scrubbed statute numbers elsewhere. F3 (E-B branch) adds field/sentence/offset location; this addresses one trigger, not the whole-resubmission mechanism.

### 0.3b Discovery 1b — Localised repair details (F3) do not stop the rewrite (E-B, post-fix)

Same diff over the E-B branch run outputs (`reliability_eb_2026-10-31/eb/diagnostics`, `monitor/diagnostics`; validator with F1/F2/F3) [E]:

| Arm | Turns | Repaired | Read-cited unit lost | Turns with conclusion text gone | Turns with fewer figures |
|---|---|---|---|---|---|
| E-B baseline | 54 | 30 | 0 | 4 | 13 |
| E-B P7-A | 50 | 29 | 0 | 0 | 13 |
| E-B P7-B | 51 | 29 | 0 | 2 | 10 |
| Monitor (8 E-A cases) | 22 | 19 | 0 | 4 | 11 |

Decisive example, **H-N3.baseline.01.followup**: the report contains one `UNTRACED_NUMBER` whose F3 detail reads "Untraced figure(s) in results.0.conclusions.2.text_es, sentence(s) 1 (characters 215-219). **Change only those spans and keep all other content as it is.**" (plus a `QUOTE_FRAGMENT_ORDER` on a citation). The repaired prose nevertheless loses five statute pointers in other fields: "el artículo 99.2 de la LIRPF" → "la Ley del IRPF"; "el artículo 76.1.c) del Reglamento" → "el Reglamento"; "artículo 27 de la LIRPF y … artículo 95.2.b).1.º del Reglamento" → "la Ley del IRPF y … el Reglamento"; "la previsión del artículo 99.5 de la LIRPF" → "la previsión del mismo precepto".

Interpretation **[E]**: the protocol asks the model to resubmit the *whole* submission. An instruction to change only some spans is advisory; the model regenerates and "plays safe" by stripping anchors that look like numbers. F3 reduced *how often* that happens (fewer UNTRACED turns) but did not change *what a repair is allowed to touch*. Preservation must be enforced structurally, not requested.

Metric caveat: the "article mention" counter also matches citation-token ids that contain an article number (e.g. `[[c:art7lirpf]]` renamed to `[[c:c1]]` in V12.baseline.00 — not damage). Every damage example quoted in this report was read in the diff, not taken from the counter.

### 0.4 Discovery 2 — Why F1/F2/F3 did not lower repair frequency (from E-B replay data)

`workstream_a/replay_summary.json` on the E-B branch, 102 replayable E-A first submissions [E]:

- Violation-code counts before → after F1/F2/F3: **only `UNTRACED_NUMBER` changed (67 → 38)**; every other code is identical (UNKNOWN_NOT_STATED 19, CONCLUSION_FACT_UNKNOWN 16, DECIDED_CONDITION_UNBOUND 13, MARKER_UNRESOLVED 12, QUOTE_FRAGMENT_NOT_FOUND 10, QUOTE_NOT_IN_USER_MESSAGES 8, BASIS_AUTHORITY_MISMATCH 8, CITED_NOT_READ 7, CITATION_UNUSED 6, MISSING_RESULT 5, QUOTE_FRAGMENT_ORDER 5, …).
- Only 8 of 102 first submissions become violation-free.
- Per-turn replay: first submissions with **any** violation fall only from **69 to 61 of 102**.
- Repair is triggered by **any** violation (one round per turn, whole-submission). Removing number false positives could therefore, by construction, lower the repair *rate* by at most 8 turns per 102 (≈8 percentage points). The live result (no measurable drop) is consistent with that ceiling plus run-to-run variance. **[S] The repair-rate metric is governed by the binary "any violation ⇒ full resubmission" policy, not by the accuracy of any single check.**

### 0.5 Discovery 3 — Fact-state reconstructions from recorded E-A states (zero cost)

Source: `state_before` / `state_after` (`consultation_agent` block) of each E-A turn file; new `fact_events`, `pending_clarification.items`, `asked_log` per turn [E].

**EA-B02 (blanket «No lo sé»).**
- Turn 0, user: "No recuerdo la fecha exacta de entrega ni cuándo avisé a la tienda." → `mark_unknown fecha_entrega`, `mark_unknown fecha_aviso_tienda` (correct). The model then **asks** `fecha_entrega_aprox` ("¿podría situar la entrega … en un periodo aproximado?"), plus `destino_horno`, `momento_dano`, `conserva_documentos`, `medio_aviso`, `vendedor_establecimiento`.
- Reply 1, user: "No lo sé." → **six** `mark_unknown` events, each quoting "No lo sé.", including `destino_horno` (personal vs professional use) and `vendedor_establecimiento`. All six asked items flip to `settled: true`.
- Follow-up, user: "No he podido comprobar esas fechas. ¿Puedes dejar constancia de que no las sé…?" → `mark_unknown` re-emitted for `fecha_entrega`, `fecha_aviso_tienda` **and** `fecha_entrega_aprox`, quoting "dejar constancia de que no las sé".
- Observations: (a) the quote is the whole reply, so the S2 quote-containment + lexicon guard is satisfied for every op — the guard verifies *that* ignorance was expressed, never *about which proposition*; (b) two keys coexist for related but different propositions (exact delivery date vs approximate period) — the E-A grader saw them as a duplicate pending line.

**EA-B04 / EA-B05 (paraphrased refusal; asked-unsettled).**
- EA-B04 reply: "El contrato atribuye al arrendatario el mantenimiento ordinario…; no sé qué causó esta avería y no puedo responder a los demás datos que falten." → `assert contrato_contenido_mantenimiento`, `mark_unknown causa_averia`. The three other asked items (`comunicacion_arrendador_averia`, `quien_asumia_reparaciones_anteriores`, `destino_taller`) get **no event**, stay `settled: false` in `asked_log`, and **disappear from `pending_clarification`** (which becomes empty). In E-B the same case later re-asks those three and the answer text says "Son datos que el cliente conoce".
- EA-B05 reply: "La entrega fue el 3 de septiembre de 2026; no recuerdo cuándo avisé a la tienda ni puedo responder a los otros datos que falten." → `assert delivery_date`, and `mark_unknown` on a **newly invented key `reclamacion_tienda_fecha`** that was never asked. The five asked keys (`purchase_capacity`, `purchase_date`, `defect_type`, `seller_establishment`, `conserva_prueba_escrita`) receive no event, remain unsettled, and leave pending.

**H-M4 (mis-bound proposition; asked-unsettled).**
- Turn 0 asks `forma_retribucion`, `otras_rentas`, `importe_colaboracion`.
- Reply: "La galería me paga 300 euros por tres días… El galerista me dice cada día qué hacer y en qué horario…" → `assert importe_colaboracion = 300` (correct) and **`assert forma_retribucion = "Prestación personal bajo las instrucciones y el horario del galerista…"`** quoting the direction sentence. A remuneration-form proposition was settled with evidence about *subordination/direction* — a different legal proposition, which already has its own key (`direccion_galeria`). `otras_rentas` is never answered and silently leaves pending.
- Follow-up correction ("en realidad no me pagan nada… organizo yo cómo montarlo") is handled correctly with `correct` ops — the correction path works when the proposition identity is right.

**H-N2 (repeated question on an unrequested issue).** `tipo_alumnado_clases` (relevant only to the IVA exemption the user did not ask about) is asked in turn 0 and again in reply 1; neither reply answers it; after reply 2 it leaves pending with `settled: false` in both asked_log entries.

Interpretation so far:
1. **[E] Proposition identity is invented by the main model on every turn** (`fact_key` free snake_case). Nothing forces an answer to bind to the asked item's key (EA-B05 `reclamacion_tienda_fecha`), nothing prevents two keys for neighbouring propositions (EA-B02 `fecha_entrega` / `fecha_entrega_aprox`), and nothing checks that the evidence quoted is about the key's proposition (H-M4 `forma_retribucion`).
2. **[E] The disposition of each asked item is implicit.** A reply settles an item only if the model happens to emit an op for that key. Items with no op neither become unknown nor stay pending — the four asked-unsettled anomalies follow mechanically.
3. **[E] The epistemic vocabulary of the state is too small for the replies users actually give.** The state can record a value, `unknown_by_user`, or nothing. "No puedo responder", "lo busco luego", "creo que en marzo, no estoy seguro" have no faithful representation, so they are either over-promoted to `unknown_by_user` (B02, and the Jev D1 over-reading of UNCLEAR) or lost (B04/B05). **[S]** This is also why Jev D1's 5-class output could not be applied safely: the state applier has only one non-value destination.
4. **[S] The guard asks the wrong question.** S2's lexicon (and the Jev D1 formulation) ask "does this text express ignorance?". The decision that matters is "which asked proposition does each clause of the reply answer, and how?" — an item-level disposition problem, which D2 only partially approximates via shared-span groups.

### 0.5b Discovery 3b — The asked-unsettled anomalies are produced by guard + repair + pending recomputation together

Source: first vs repaired `fact_ops`, validation report, and `clarification_items` in the E-A diagnostics [E].

| Turn | First submission | Validator | Repaired submission | State result |
|---|---|---|---|---|
| EA-B04.01 | `mark_unknown` × 3 (`comunicacion_arrendador_averia`, `quien_asumia_reparaciones_anteriores`, `destino_taller`) quoting "no puedo responder a los demás datos que falten" | `UNKNOWN_NOT_STATED` × 3 (correct: inability/refusal is not ignorance) | the 3 ops deleted; **no `clarification_items`** | 3 items asked, never settled, gone from pending |
| EA-B05.01 | `mark_unknown` × 5 quoting "no puedo responder a los otros datos…" (quote also slightly mis-copied) | `UNKNOWN_NOT_STATED` + `QUOTE_NOT_IN_USER_MESSAGES` × 5 | 5 ops deleted; no clarification items | 5 items lost |
| H-N2.02 | `mark_unknown tipo_alumnado_clases` quoting an unrelated sentence ("Sí: unos 15 alumnos…") — the model wants to stop asking | `UNKNOWN_NOT_STATED` | op deleted; no clarification items | item lost |
| EA-B02.00 | `mark_unknown fecha_aviso_tienda` quoting "ni cuándo avisé a la tienda" | `UNKNOWN_NOT_STATED` (the lexicon needs the "No recuerdo" head of the coordinated clause) | quote widened to the whole sentence | accepted (correct outcome, but a repair round spent on a lexical artefact) |

Causal chain **[E]**:
1. The main model correctly perceives that the reply disposes of every asked item, and tries to record it.
2. The only non-value disposition in the contract is `mark_unknown` (= `unknown_by_user`). The guard rightly refuses it for refusal/inability.
3. The repair detail says "If the client simply did not answer, leave the fact out; it remains askable." The model complies by deleting the ops.
4. It is *not* actually kept askable: pending is rebuilt from the model's next `clarification_items`, which the repaired submission leaves empty (the model had just been told the client cannot answer). The item vanishes from both "pending" and "settled".

So the anomaly is not a recall failure of the lexicon (as E-A hypothesised) but a **missing state**: "the client declined / cannot answer" has nowhere to go, and the validator's repair advice routes it to deletion. A better lexicon or Jev D1 recall would make this worse, not better, if it promoted refusal to `unknown_by_user` (the owner policy correctly labels refusal UNCLEAR).

Cross-problem link: fact-state codes (`CONCLUSION_FACT_UNKNOWN`, `DECIDED_CONDITION_UNBOUND`, `UNKNOWN_NOT_STATED`, `QUOTE_NOT_IN_USER_MESSAGES`, `FACT_VALUE_UNSUPPORTED`, `SCENARIO_PREMISE_MISSING`) appear in the first report of **21 of 65** repaired E-A turns (8 of them fact-only). Problem 2 is therefore a direct contributor to Problem 1's repair frequency. Other families: number 35 (20 number-only), citation/quote/marker 28, result-shape 10 (overlapping).

### 0.5c Discovery 5 — Code-level mechanisms (traced directly)

Code read at `origin/impl/reliability-eb-20261031` (R; validator identical to `d4304d10` except F1–F3) and `origin/impl/jev-semantic-fact-verification-v1` (J). Path prefix `backend/apps/legal_graphrag/services/v3/agent/` [E].

**Repair protocol (`loop.py`).**
- `loop.py:192`: the `submit_consultation` tool description says "Submit the COMPLETE consultation for validation, including unchanged fields after repair. Never send a partial update." `loop.py:109-129` (`submission_tool_schema`) makes every property required, so a partial/delta repair cannot be expressed.
- `loop.py:368`: `if report is not None and not repaired:` — only the **first** submission's report triggers a repair. The repaired submission's validation report is not used to decide anything; the candidate goes straight to `finalize_fn` (`loop.py:386`).
- `loop.py:388-394`: the first submission is reused **only** when the repair has no results at all (`salvaged='empty_repair'`). There is no comparison of first vs repaired content and no preservation check.
- Consequence: exactly one model round per violated turn; the repaired candidate is accepted wholesale; anything it deleted is lost; anything still wrong is annotated or dropped by `finalize`.

**Finalisation (`validator.py:1778-2117`, `finalize`).** It re-runs the checks on the accepted candidate and applies residual policies:
- annotate (V2/V5 "(referencia no verificada)", V6 "(cifra no localizada en las fuentes consultadas)", V7 "(cálculo no verificado)"; table `_ANNOTATIONS` at `validator.py:48-54`);
- relabel (V9 "(criterio interpretativo, no norma)");
- drop (fact ops, results under D-1);
- normalize (cite ids, conditions).
These are the deterministic correctors that already exist. They are applied only **after** the model rewrite, never **instead of** it.

**Violation catalogue (emission lines in `validator.py`).** V2 `CITED_NOT_READ` 762, `UNIT_NOT_RESOLVABLE` 770, `VERSION_MISMATCH` 778; V3 `NOT_VALID_AT_LEGAL_DATE` 793, `TERRITORY_MISMATCH` 805; V5 `MARKER_UNRESOLVED` 751, `CITATION_UNUSED` 860; V6 `UNTRACED_NUMBER` (`numbers`, 916-1102; detail builder `_untraced_detail` 168); V7 `CALC_UNKNOWN` 881, `CALC_MISMATCH` 902; V8 `SCENARIO_PREMISE_MISSING` 1156, `QUOTE_NOT_IN_USER_MESSAGES` 1177, `OUTCOME_SHAPE` 1182, `UNKNOWN_NOT_STATED` 1198, `FACT_VALUE_UNSUPPORTED` 1201, `ASSERT_ON_KNOWN_KEY` 1209, `DUPLICATE_FACT_KEY` 1216, `QUESTION_NOT_FACT_GAP` 1295, `KNOWN_FACT_ASKED` 1302, `UNKNOWN_FACT_REASKED` 1317, `REPEAT_WITHOUT_REASON` 1322, `DUPLICATE_ITEM` 1324, `QUESTION_CEILING` 1327, `DECIDED_CONDITION_UNBOUND` 1341, `CONCLUSION_FACT_UNKNOWN` 1343, `MISSING_RESULT` 1347; V9 `BASIS_AUTHORITY_MISMATCH` 1121; V4 quote-fragment codes in `sources` (746-820). All codes share one severity: any of them triggers the single whole-submission repair.

**Ignorance guard.** `validator.py:1191-1198`: a `mark_unknown` passes iff `states_ignorance(op.user_quote)` and the quote does not contain another op's assert quote. `epistemic_es.py` (`EPISTEMIC_LEXICON_VERSION='1'`) is a regex cue list applied **to the quote only**. It knows nothing about which proposition is meant. It also accepts cues the owner policy classes as UNCLEAR: hedging ("no estoy seguro") and temporary inability ("tendría que consultar").

**Pending recomputation — the silent-drop line.** `state.py:545-558` (R and `d4304d10`): old pending items survive only `if i.fact_key not in settled_keys | new_keys and i.issue_ref not in replaced and i.issue_ref not in parked`. Here `replaced` (`state.py:546`) is every issue that received any non-`NOT_ADDRESSED` result this turn. **Any new answer on an issue silently deletes that issue's unanswered questions.** This is exactly the H-M4 / H-N2 / EA-B04 / EA-B05 drop.
- J (commit `224531f2` "preserve unanswered clarification items") removes the `replaced` filter, so unanswered items carry forward. This fixes the silent drop, but on its own it turns refused items into **repeated questions**: there is still no "declined" state. That is exactly the E-B monitor observation that "EA-B04 asks again for 3 facts after the client refused".
- J also adds `FactEventV1.verification` and `require_verification` (`state.py`, StateUpdater): in Jev enforce mode a `mark_unknown` without a verifier record raises `fact_verification_missing`. Jev enforce is off by default (uncalibrated snapshot ⇒ runs as shadow).

### 0.6 Discovery 4 — H-P3 omission is an issue-framing failure, not a reading failure

Source: E-A diagnostic for `H-P3.00.initial` (read set, search hits, `issue_ops`, conclusions) [E].

- User: "Desde hace tres años coordino de manera continuada, asumiendo yo el riesgo económico, el montaje de exposiciones para varias instituciones…" (an implicit "what am I / what must I do?").
- The model opened one issue whose `question_es` is purely classificatory: "¿es trabajador por cuenta ajena, trabajador autónomo ordinario o TRADE?".
- Searches: only two (`TRADE dependencia económica 75%`, `definición trabajador por cuenta ajena…`). Read set: LETA arts. 1, 2, 11, 11 bis; ET art. 1. **LGSS art. 305 (RETA inclusion) was neither searched for, surfaced nor read**; LGSS arts. 317/333 were surfaced and not read.
- Conclusions (5) are all correct *within the frame*: not employee; TRADE conditional on 75 %; TRADE procedure. The consequence that matters most to the client — mandatory RETA registration and the three-year retroactive exposure — is outside the frame the model set for itself, so research never reached it. The same omission occurred in E-1 (independent run), so it is systematic, not sampling noise.
- Contrast H-M4.00 (same legal family): the model framed the issue as "consecuencias fiscales y de Seguridad Social (alta en el RETA)", searched for "RETA … artículo 305" and read LGSS art. 305.

Interpretation: **[S]** the decisive-provision miss is caused upstream of retrieval, at *issue framing*: the issue question the model writes for itself defines the research target, and nothing checks that the frame covers the legal consequences (obligations, regime, deadlines) a client in that situation needs. No exception wording, read-time cue (P7-A) or "list alternatives" field (P7-B) acts at that boundary — consistent with E-B finding no gain.

### 0.6b Discovery 6 — E-B grader flags against read sets (Problem 3)

Source: `reliability_eb_2026-10-31/grading/{aa..ad}_{X,Y}.tsv` + `eb/BLIND_KEY.jsonl` + per-turn `read_set` from `eb/diagnostics` [E].

Every case-arm a grader flagged for `missed_exc`, `exc_over` or `unsupported` falls into one of four classes:

| Class | Cases (arm) | Decisive text read? | Stage |
|---|---|---|---|
| Technical failure (503) | N03 ×3, V47 ×3, H-B3 (p7a, p7b) | n/a | provider |
| Corpus gap | H-B2 ×3 (IGIC rates / franquicia) | not in corpus | corpus |
| **Frame omission** | **H-P3** — grader: "T0 never names RETA" (p7b) | LGSS art. 305 **not read at turn 0 in any of the 3 arms**; read in the reply turn of all 3 arms | issue framing |
| **Consequence not bound to a rule** | **H-N1 turn 1** (baseline, p7a): gallery margin taxed at 10 % ("revendedor exclusion missed") | LIVA arts. 135–138 and 91 **read** in both arms | application |
| Sub-rule omitted within a read unit | N01 (p7b): "art 96.4 omitted" | LIRPF art. 96 **read** in all arms | application |
| Contested qualification | V12 (p7a): "classifies rendimiento del trabajo, not in gold" | arts. 7/17/33 LIRPF read in all arms (E-B RESULTS) | needs jurist |

**H-P3 is now a five-run systematic miss.** It occurred at turn 0 in E-1, E-A, E-B baseline, E-B P7-A and E-B P7-B, each time with the same classificatory frame, and each time the reply turn (where the user mentions alta/RETA-adjacent facts) reads art. 305. It is not variance. Neither P7 arm changed it, because neither acts on the frame.

**H-N1 anatomy** (`H-N1.baseline.01.reply1`).
- The model writes two well-structured application conclusions: (1) the author's delivery at 10 % (art. 91.Uno.4 governing, conditions satisfied, correct); (2) the gallery's resale under REBU (arts. 135–138, conditions satisfied: habitual reseller, acquired at reduced rate, no election of the general regime).
- Conclusion (2) then states "base … 209,09 €, con una cuota de 20,91 €", i.e. 230/1,10. That is the **10 % rate silently carried over from conclusion (1)**.
- The rate applicable to the margin is a decisive legal consequence. It is **not stated as a proposition, has no condition and no citation**. V9 is satisfied because the conclusion cites *some* normativa (arts. 135–138), and V6 is satisfied because 1,10 is grounded by F1 rate constants from the cited art. 91.
- The structure *rule → requirements → result* covers whether the regime applies, but not *which rule fixes each consequence*.

Interpretation:
- **[E]** Apart from corpus gaps and provider failures, every flagged legal miss in E-B involves provisions that were found. Two had the decisive text read and misapplied (H-N1, N01). One (H-P3) is a systematic frame omission at turn 0.
- **[S]** The two general mechanisms are:
  - (a) the issue frame is set by the model with no check that it covers what the client must *do* or *owe*;
  - (b) a conclusion's operative consequences (rate, amount, deadline, regime, obligation) are not individually bound to the provision that fixes them, so an unbound consequence can be inherited from a neighbouring conclusion.
- **[S]** E-B's own metric "gold CORE units read 34/36" already shows retrieval is not the bottleneck. More research (P7-A cues on every read: median 18 sentences per turn) adds noise at the wrong stage.

### 0.7 Pending (in progress)

- Code-path tracing of validator → repair → finalize (violation table, repair eligibility, original-vs-repaired handling).
- Fact path: message → fact op → V8/lexicon/Jev → state → context next turn; status enumeration and the asked-unsettled drop mechanism.
- Exception path: contracts for conditions/alternatives, prompt §D, read/related tools, P7-A/P7-B mechanism, E-B grader flags vs read sets.
- Sections A–J.
