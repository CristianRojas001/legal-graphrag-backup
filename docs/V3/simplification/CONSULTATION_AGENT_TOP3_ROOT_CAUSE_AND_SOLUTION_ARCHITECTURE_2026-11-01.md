# LegalGraphRAG consultation agent — top-3 root cause and solution architecture (2026-11-01)

> **Status: FINAL (investigation and design; no application code changed; no paid calls).** Written incrementally at the owner's request. Sections A–J are the deliverable. §0 at the end is the chronological evidence record that A–J cite.
>
> **Scope limits:**
> - The JEV-triage / Repair V2 campaign (`impl/jev-triage-20261101`, `0de2b56a`) could not be inspected (absent from both remotes); see OD-1.
> - Three delegated code-tracing subagents were lost when the session environment restarted. All code facts in this report were traced directly by Opus.

Evidence labels used throughout: **[E]** confirmed from code or recorded evidence; **[S]** strongly supported; **[H]** hypothesis; **[P]** proposal/projection.

---

## A. Executive diagnosis

### A.1 The three problems and their root causes

| # | Problem (observed) | Primary root cause | Confidence |
|---|---|---|---|
| 1 | Correct answers are rewritten, de-specified or occasionally emptied by validation/repair. Repair rate did not fall after the number-validator fix. | **The repair protocol has no unit of change.**<br>• Any violation of any code triggers one *whole-submission* resubmission (`loop.py:192`, `:109-129`, `:368`).<br>• The repaired candidate is accepted wholesale without re-validation or comparison (`loop.py:386-394`).<br>• Deterministic correctors exist (`finalize`, `validator.py:1778`) but run only *after* the rewrite.<br>• "Change only those spans" (F3) is advisory and the model does not follow it (E-B H-N3). | Confirmed (code + exhaustive diff of 65 E-A and 78 E-B/monitor repaired turns) |
| 2 | Wrong `unknown_by_user`; blanket «No lo sé»; asked questions that vanish; repeated questions; related propositions confused. | **Proposition identity and item disposition are implicit, and the epistemic vocabulary has two states.**<br>• `fact_key` is invented per turn.<br>• A reply settles an asked item only if the model happens to emit an op for that key.<br>• Only `value` or `unknown_by_user` exist.<br>• The ignorance guard tests the quote's wording, not which proposition it answers (`validator.py:1191-1198`, `epistemic_es.py`).<br>• Repair advice routes refusals to deletion; `state.py:546-556` then drops every unanswered item of any issue that received an answer. | Confirmed (state reconstructions + code) |
| 3 | General rule found but a decisive exception, precondition, consequence or alternative qualification missed. | **The analysis contract checks citations, not applicability.** Nothing binds each operative consequence (rate, amount, obligation, regime) to the provision that establishes it *for this actor and transaction*. Nothing checks that the issue frame the model sets itself covers the action-relevant consequences. Exceptions rely on prompt text only (§B/§C of `system_v1.md`). Retrieval is *not* the bottleneck (E-B: 34/36 gold core units read; every flagged non-corpus miss except H-P3 had the decisive text read; H-P3's was excluded by the model's own issue frame). | Strongly supported (E-B grader flags × read sets; H-P3 five-run miss; H-N1 anatomy). Mechanism of the cure: hypothesis until measured |

### A.2 Shared architectural cause

All three share one defect. **The main model's single free-form submission is the only carrier of meaning, and the deterministic layer can only accept it, annotate it, delete parts of it, or demand that it be regenerated in full.** There is no smaller, typed channel through which the system can:
- ask for or apply *one* correction (Problem 1);
- record *one* disposition per asked question (Problem 2);
- check *one* consequence against the text that should establish it (Problem 3).

The causal links between the problems are evidenced, not assumed (§C):
- fact-state violations trigger 21 of 65 E-A repair rounds;
- the repair advice for refusals manufactures the asked-unsettled anomalies;
- a mis-bound fact (H-M4 `forma_retribucion`) produced an unsupported "contraprestación — se cumple" line.

### A.3 Recommended solution (one package, three parts)

1. **Patch repair with preservation and candidate selection (PR).**
   - A violation registry classifies every code as `DETERMINISTIC_FIX`, `PATCH`, `FACT_DISPOSITION` or `STRUCTURAL`.
   - Deterministic fixes run before any model call.
   - The model repairs through a typed `repair_patch/1` limited to the violated paths.
   - The applier enforces the path allow-list and an anchor-preservation invariant, then re-validates.
   - The controller chooses deterministically between "original + deterministic finalisation" and "patched + finalisation".
2. **Clarification ledger with explicit item dispositions (CL).**
   - A per-case proposition registry (`fact_key` + `proposition_es` + relations).
   - Each asked item has a closed lifecycle: `open`, `answered`, `unknown_by_user`, `declined`, `deferred_by_user`, `withdrawn_by_agent`, `superseded`, `conflicted`.
   - The submission must disposition every open item exactly once.
   - Non-value dispositions are verified (Jev reformulated as one multi-item disposition decision, shadow until calibrated).
   - Attribution text comes from the ledger, never from model narration.
3. **Applicability audit with a material-completeness standard (AA).**
   - One bounded structured pass over the finished draft's decisive conclusions, against the full text of the units they cite (already read).
   - It checks that each operative consequence is established *for these facts* (MC1).
   - It checks that no clause of the governing text that excludes or conditions it is left unreflected (MC2).
   - It checks that explicit cross-references the consequence depends on are resolved (MC3).
   - For qualification issues, it checks that the action-relevant consequence is stated or scoped out (MC4, with one bounded research-again step).
   - Findings feed the *same single* patch round as validator violations, so the turn never gets a second model rewrite.

### A.4 Expected impact — evidenced vs projected

| Claim | Status |
|---|---|
| PR removes out-of-scope rewrites: no anchor outside a violated sentence can change | **By construction** (deterministic applier); verifiable offline with recorded first submissions + synthetic patches |
| PR reduces repair *harm* to ~0. Baseline harm: 8/65 E-A repaired turns lost statute pointers across the whole answer, and 10/65 lost conclusion text. In E-B baseline the per-result counter flags up to 7/30 and 4/30; that is an upper bound, because it also counts citation-token renames and re-keyed results. H-N3.01 is a diff-verified genuine case | Projected from the diff; requires live confirmation |
| Deterministic pre-repair fixes remove a model round in 5/65 (E-A) and 7/30 (E-B baseline) repaired turns | Projected from recorded first-report codes |
| Repair *frequency* falls substantially | **Not claimed.** E-B replay shows most remaining violations are genuine. The target metric is changed to "harm per repaired turn" and "repair output tokens" |
| CL eliminates the four asked-unsettled anomalies and the EA-B04 re-ask | By construction (coverage invariant + `declined` state); requires live confirmation of model compliance |
| CL removes blanket broadcast attribution (EA-B02) | Projected from the Jev pilot (D2 0/15 broadcasts accepted) and the shared-span rule; verifier enforcement remains gated on calibration |
| AA catches H-N1-type unbound consequences and N01-type omitted sub-rules | **Hypothesis**; first test is a small paid shadow run (not authorised in this mission) |
| AA/MC4 fixes H-P3 frame omission | **Hypothesis**; H-P3 is the designated discriminating case (five-run baseline miss) |

---

## B. Evidence and execution-path reconstruction

The chronological discovery record is in §0 below; this section is its structured summary per problem.

### B.1 Problem 1 — validation and repair

**Execution path (R = `impl/reliability-eb-20261031`; identical control flow at `d4304d10`).**
```
AgentLoop.run (loop.py:170)
 └─ model calls submit_consultation(full SubmissionV1)          # tool desc loop.py:192; all fields required :121
     ├─ SubmissionV1.model_validate (loop.py:352) ─ fail → SCHEMA_INVALID report (one retry)
     ├─ validate_fn → validator.validate (validator.py:1472) → _Checks.run (:737)
     │    sources V2/V3/V4 (:746) · markers V5 (:821) · calculations V7 (:862) · numbers V6 (:916)
     │    authority V9 (:1103) · conversation V8 (:1123)
     ├─ report and not repaired (loop.py:368) → send report; repaired=True; tool_choice forced to submit
     └─ second submission → NOT re-validated for selection → finalize_fn (loop.py:386)
          └─ validator.finalize (:1778): re-check; annotate V2/V5/V6/V7, relabel V9, drop facts/results
             first submission reused only if repair has no results (loop.py:388-394)
```

**Contracts.**
- Input: `SubmissionV1` (issue_ops, context_ops, fact_ops, scenario_ops, results[sections, conclusions[conditions, cite_ids], clarification_items, gaps], citations[cite_id, unit_id, version_id, pinpoint_es, quote_fragments, role], calculations, confirm_target).
- Output of validation: `validation_report/1` {ok, violations[{check, code, path, detail}], instruction "Corrija las infracciones y vuelva a enviar la consulta una sola vez."}.
- All violations share one severity.

**Representative failures.** All are diff-verified (§0.3, §0.3b):
- V24.00: "artículo 331.1 de la LGSS" removed (UNTRACED only).
- V28.00: arts. 82–86, 18, 81.3, 86.2 removed during a *contract* repair.
- V45.01: the art. 32.1 rule statement removed.
- V10.00: "(art. 4.Uno y art. 11.Uno LIVA)" removed.
- E-B H-N3.01: five pointers removed despite F3's "change only characters 215-219".

**Root-cause chain.**
1. Any violation leads to a full rewrite.
2. The model regenerates every field and strips number-like anchors to be safe.
3. There is no preservation check.
4. The rewrite is accepted wholesale.
5. Residuals are annotated, producing markers on what remains.

**Historical interventions.**

| Intervention | Outcome | Why it did not move the user outcome |
|---|---|---|
| S5 (N1–N5 provenance) | UNTRACED rose to 26/83 Cohort A turns; markers not reduced | Receipt-literal grounding broke (RC1); detail had no location |
| F1/F2/F3 (E-B Workstream A) | Replay: UNTRACED spans 146→61, turns 67→38, cifra markers 41→11, 0 must-reject regressions | Only UNTRACED changed; turns with any violation 69→61/102, so the repair rate can fall by ≤8 pp. Live: 20/22 vs 19/22 repaired. F3 location is advisory: H-N3 still de-specified |
| JEV triage + Repair V2 (`impl/jev-triage-20261101`, `0de2b56a`) | **Not inspectable** (absent from both remotes) | Unknown. The brief says code-only triage plus a disabled Repair V2; no claim is made here about what it solves |

**Uncertain.**
- Exact live repair-harm rate under a patch protocol.
- Whether DeepSeek reliably emits a typed patch (compliance).
- What the unavailable Repair V2 already implements. If it is a patch protocol, PR should be reconciled with it rather than duplicated (§J open decision OD-1).

### B.2 Problem 2 — semantic fact management

**Execution path.**
```
user message ─► main model (prompt §A.2, §D "«no lo sé» → mark_unknown … Do not ask it again")
  └─ fact_ops[{op: assert|correct|retract|mark_unknown, fact_key (free), value, user_quote, issue_refs}]
     clarification_items[{fact_key, question_es, answer_shape, choices, depends_on, …}]
validator V8 (validator.py:1123-1383)
  ├─ QUOTE_NOT_IN_USER_MESSAGES (:1177), FACT_VALUE_UNSUPPORTED (:1201)
  ├─ mark_unknown: states_ignorance(user_quote) (epistemic_es regex) and no assert quote inside (:1191-1198)
  └─ CONCLUSION_FACT_UNKNOWN (:1343), DECIDED_CONDITION_UNBOUND (:1341), UNKNOWN_FACT_REASKED (:1317)…
repair (whole submission) — detail for UNKNOWN_NOT_STATED: "If the client simply did not answer, leave the fact out; it remains askable."
StateUpdater (state.py)
  ├─ FactEventV1 per op (J adds .verification; enforce requires it)
  └─ pending recompute (state.py:545-558): old item survives iff key ∉ settled∪new AND issue ∉ replaced AND issue ∉ parked
       replaced = issues with any non-NOT_ADDRESSED result this turn  ← silent drop   (removed in J, 224531f2)
context next turn: facts with quotes, pending items, asked_log
Jev (J, off by default): records only for ops the model proposed + pending items;
  D1 fact_response/2 five labels (fact_verifier.py:23-36); D2 general_reply_scope noul (:39-47)
```

**Representative failures** (§0.5, §0.5b):

| Case | What happened |
|---|---|
| EA-B02 | Blanket «No lo sé.» produced six `unknown_by_user` events. `fecha_entrega` and `fecha_entrega_aprox` coexist. |
| EA-B04, EA-B05 | Refusal was proposed as `mark_unknown`, correctly rejected, deleted on repair, and the items dropped. EA-B05 also invented the never-asked key `reclamacion_tienda_fecha`. |
| H-M4 | `forma_retribucion` was settled with evidence about direction/subordination; `otras_rentas` was dropped. |
| H-N2 | `tipo_alumnado_clases` was asked twice, then the model tried to "close" it via `mark_unknown` with an unrelated quote; it was rejected and dropped. |
| E-B monitor | EA-B04 re-asks the declined items and says "Son datos que el cliente conoce". |

**Root-cause chain.**
1. The proposition is identified only by a model-invented key.
2. The reply-to-item binding is a side effect of op emission.
3. The only non-value state is `unknown_by_user`.
4. The guard rightly rejects non-ignorance.
5. The repair advice says "leave it out".
6. The pending recompute drops the item (R), or carry-forward re-asks it forever (J).
7. The answer text narrates a status that the state does not hold.

**Jev experiment — what was wrong with the formulation, not with Jev.**
- (a) **Label overlap.** `STATES_NOT_KNOWN` includes "have not been able to check" (temporary inability, which the owner policy classes as UNCLEAR) and "a general statement that … plainly covers every open question" (the D2 question). D1 was instructed to make the broadcast decision, and did: it accepted all 15 bare «No lo sé» replies, while D2 accepted 0/15.
- (b) **The wrong decision boundary.** Jev gates an op DeepSeek already proposed ("accept this `mark_unknown`?"). It is not asked "what is the disposition of each open question?", so items for which no op was proposed are never examined.
- (c) **`UNCLEAR` is a sink.** It merges refusal, deferral, vagueness and contradiction. Its only consequence is "abstain → fact absent", which then hits the drop or re-ask defect.
- (d) **Too little context in the label set.** The label set cannot express "answered approximately" separately from hedging, so hedged values become NOT_KNOWN (3 false accepts).

These are formulation defects. Jev's language understanding was strong: recall 0.977, and D2 0 false broadcasts.

**Historical interventions.**
- S2 G1 lexicon (precision-first): it eliminated E-1's false "usted ya indicó", but has recall 0.547 and cannot express refusal.
- S4 IT-3 pending-from-batch: it created the drop.
- J carry-forward: it fixes the drop and exposes re-ask.
- Jev D1+D2 pilot: precision 0.884 (AC-1 fail) and stability 2.34 % (AC-6 fail). Not enforce-ready under its own gates.

**Uncertain.**
- DeepSeek compliance with a mandatory per-item disposition list.
- Calibration of a reformulated Jev decision (needs annotated data; paid).

### B.3 Problem 3 — exceptions and competing qualifications

**Execution path.**
```
prompt §B (read completely; look for exceptions, related provisions cited_by/cites; "Check for exceptions first")
prompt §C (rule → requirements → facts → result; conditions satisfied/not/unknown/assumed; LEGAL_AMBIGUITY)
model: issue_ops.open{title_es, question_es}  ← self-set frame (H-P3: classification only)
tools: search_law, read_provision, get_related_provisions, get_document_outline, list_corpus_documents (0 calls in 104 E-A turns)
submission: conclusions{kind, basis, conditions[{description_es, fact_key, status, cite_ids}], cite_ids}
validator: V2 cited-read, V4 quote fragments, V9 binding_law needs ≥1 read normativa citation (any)
           — no check that a consequence is established by the cited text for this actor/transaction
```

**Representative failures** (§0.6, §0.6b):
- **H-P3**: classificatory frame, LGSS art. 305 never read at turn 0 in five independent runs, and read in every reply turn.
- **H-N1.01**: REBU arts. 135–138 and art. 91 read; the margin is taxed at the author's 10 % by an unstated, uncited consequence.
- **N01**: art. 96 read, sub-rule 96.4 omitted.
- **H-M4** (E-A): unsupported "contraprestación — se cumple" line built on a mis-bound fact.

**Root-cause chain.**
- Frame set by the model without a coverage check → research targets the frame → frame-external decisive provision unread (H-P3).
- Or: the conclusion's regime conditions are well-bound, but its operative consequence (rate/amount) is implicit and inherited → validator only checks "some read normativa is cited" → error passes (H-N1).

**Historical interventions.**
- Prompt hardening: an earlier pre-registered A/B failed (P1–P13 report).
- P7-A exception cues at read time: median 18 cue sentences per turn, no CORRECT gain, +26.5 % latency, +8 identifier leaks.
- P7-B alternatives field on every application conclusion: no gain, +41 % latency, +33 markers from malformed citation tokens, +4 leaks.

Why they could not work:
- **P7-A** acts *before* reasoning, lexically, on every read. It increases context noise at the research stage, which E-B showed was not the bottleneck.
- **P7-B** asks the *drafting* model to self-critique in the same pass, enlarging the schema. That is the same pass and the same blind spot, with more output to get wrong.
- Neither acts at the two failing boundaries: frame coverage and consequence-to-text binding.

**Uncertain.**
- Whether a separate audit pass detects H-N1/N01-type defects at useful precision.
- Whether MC4 (frame coverage) avoids increasing scope drift (H-N2, P8).
- Both need a small paid shadow run.

---

## C. Root-cause interaction analysis

| Link | Evidence | Status |
|---|---|---|
| P2 → P1: fact-state defects create repair rounds | Fact-family codes (`CONCLUSION_FACT_UNKNOWN`, `DECIDED_CONDITION_UNBOUND`, `UNKNOWN_NOT_STATED`, `QUOTE_NOT_IN_USER_MESSAGES`, `FACT_VALUE_UNSUPPORTED`, `SCENARIO_PREMISE_MISSING`) in the first report of 21/65 repaired E-A turns (8 fact-only); 7/19 monitor repaired turns | Confirmed |
| P1 → P2: repair advice destroys fact information | EA-B04, EA-B05, H-N2: the ops are deleted on repair, then the items drop | Confirmed |
| P2 → P3: a mis-bound fact yields an unsupported legal line | H-M4: `forma_retribucion` settled from direction evidence; turn-0 structured line "Obtención de una contraprestación — se cumple" unsupported (E-A grade P) | Strongly supported (a single case) |
| P2 → scope drift: unresolved items keep unrequested issues alive | H-N2: `tipo_alumnado_clases` (only relevant to the unrequested IVA issue) asked twice; reply turns drift into IVA | Strongly supported |
| P1 → P3: repair de-specification hides the provision basis | V28, V45, H-N3: anchors removed; legal polarity unchanged in every inspected case | Confirmed as a verifiability loss; **not** a cause of missed exceptions |
| P1 ↔ P3 accidental correction | H-N1 E-A: the repair deleted legally wrong figures | Confirmed: repair effects are uncontrolled in both directions |
| P3 → P1 | No evidence that missed exceptions trigger violations: they pass validation | Confirmed absence (that is the problem) |

**Implication for sequencing.**
- PR and CL must ship together. CL changes the fact codes (new dispositions replace deletions), and PR is what keeps those corrections local.
- AA depends on PR, because its findings must be applied through the same bounded patch round, or it would reintroduce a second full rewrite (the P7 latency failure mode).

---

## D. Recommended target architecture

### D.1 Principles kept

These are unchanged:
- one drafting agent (DeepSeek via OpenRouter), its tools, prompt structure and `SubmissionV1`;
- deterministic validator checks V1–V9 (none weakened);
- `finalize` residual policies;
- S1–S7 guards and F1–F3;
- hypothetical scenarios (S3);
- the Jev transport, ledger and budget code (J);
- the reviewer hook (ADR-6).

What changes is *the channels* between model and deterministic layer, not who decides. LLMs interpret meaning; deterministic code enforces identity, coverage, allow-lists, preservation and selection.

### D.2 Turn data flow (new elements marked ★)

```
 user message
     │
     ▼
 ContextBuilder ── ★ ledger view: propositions + open items (with batch, asks, hold) + closed items with status
     │
     ▼
 Drafting agent (research tools, unchanged) ──► submit_consultation(SubmissionV1 ★ + item_dispositions)
     │
     ▼
 normalize (existing _normalize, S6) ─► ★ DeterministicFixer (registry class DETERMINISTIC_FIX)
     │
     ▼
 validate (V1–V9, ★ CL checks: coverage, key binding, proposition registration)
     │
     ├─► ★ DispositionVerifier (Jev reply_disposition/1; off|shadow|enforce)   [only if non-value dispositions]
     ├─► ★ ApplicabilityAudit (evolved reviewer; off|shadow|on)                [only eligible conclusions]
     ▼
 findings = violations ∪ audit findings ∪ verifier disagreements
     │ empty ─────────────────────────────────────────────┐
     ▼ non-empty                                          │
 ★ PatchRound (one model call, tool repair_consultation,   │
   ≤2 read_provision only if a finding requests it)       │
     ▼                                                    │
 ★ PatchApplier (allow-list, anchor preservation) ─► C1   │  C0 = fixed original
     ▼                                                    ▼
 validate(C1)  ─────────► ★ CandidateSelector (C0 vs C1, deterministic)
                                   │
                                   ▼
                     finalize (existing residual policies)
                                   │
                                   ▼
             StateUpdater ★ ClarificationLedger commit (no silent drops)
                                   │
                                   ▼
             render ★ attribution/status lines from ledger, not model prose
```

### D.3 Component responsibilities

| Component | Owns | Must not |
|---|---|---|
| Drafting agent | legal research, interpretation, conclusions, proposing fact ops and item dispositions, patch content | decide what state an item is in without a disposition; rewrite outside a patch scope |
| ViolationRegistry (★, static table) | class, severity and patch scope of every code | contain semantic logic |
| DeterministicFixer (★) | mechanical corrections with unique, provable results (fragment order, unused citations, unambiguous marker tokens, duplicate items) | change any prose word other than the token it fixes |
| Validator (existing + CL checks) | structural/provenance/epistemic-evidence checks | rewrite meaning |
| DispositionVerifier (★, Jev reformulated) | semantic check of non-value dispositions and broadcasts | create dispositions; enforce while uncalibrated |
| ApplicabilityAudit (★, evolves `reviewer.py`) | MC1–MC4 findings with verbatim evidence from read units | block publication; rewrite; use outside knowledge without a research request |
| PatchRound + PatchApplier (★) | one bounded correction; enforce allow-list and preservation | accept full resubmissions |
| CandidateSelector (★) | choose C0 vs C1 by a fixed rule | use model judgement |
| finalize (existing) | residual annotate/relabel/drop on the selected candidate | — |
| ClarificationLedger (★, in StateUpdater) | proposition registry, item lifecycle, re-ask policy | drop items; infer dispositions |
| Renderer (existing + ★) | client-visible attribution and status lines from the ledger | print raw identifiers or model-narrated status |

### D.4 What remains, changes, is replaced, stays disabled

| Mechanism | Decision |
|---|---|
| Whole-submission repair (`loop.py:192`, `:368-394`) | **Replaced** by PatchRound behind `AGENT_REPAIR_MODE=patch`; `full` kept as rollback |
| `finalize` | **Kept**; runs on the selected candidate |
| F1/F2/F3 | **Kept**. F3 locations become the patch scope (sentence indices) |
| S2 lexicon `states_ignorance` | **Kept** as the deterministic precondition for `unknown_by_user` when the verifier is off/shadow. Its *repair advice* changes (no "leave it out") |
| `state.py:546-556` `replaced` filter | **Removed** (as in J `224531f2`) and superseded by the ledger lifecycle |
| J carry-forward | **Kept**, constrained by the re-ask policy (max 2 asks, never after `declined`/`unknown_by_user`) |
| Jev D1 `fact_response/2` + D2 `general_reply_scope` | **Replaced** by `reply_disposition/1` (one multi-item question). Transport, ledger, cache, bands code reused |
| Reviewer ADR-6 (`reviewer.py`, `reviewer_v1.md`) | **Evolved** into ApplicabilityAudit: evidence spans, MC kinds, findings routed to the patch round, runs before (not after) repair |
| P7-A / P7-B flags | **Stay disabled** (rejected by E-B). Not reused |
| Unknown JEV-triage / Repair V2 (`0de2b56a`) | **Owner reconciliation required** (OD-1): if it is a code-only triage, it maps onto the ViolationRegistry; if Repair V2 is a patch protocol, PR adopts its transport and keeps this spec's invariants |

### D.5 Decision boundaries (who decides what)

- **Is the answer legally right?** The drafting agent. The audit can only raise evidence-grounded findings; the agent may dismiss a finding with a reason and evidence (recorded).
- **What did the user's reply do to each open question?** The drafting agent proposes; the verifier checks non-value dispositions; deterministic code enforces coverage and binding. Uncertainty resolves to `open` + `hold` (ask to confirm), never to `unknown_by_user`.
- **What may a repair change?** Deterministic: only the registry scope of each addressed finding.
- **Which version ships?** Deterministic `CandidateSelector`.
- **Research again?** Only through an audit `research_request` or a `CITED_NOT_READ` patch, with ≤2 reads, inside the same patch round.

---

## E. Implementation-ready data contracts

All contracts are Pydantic `ContractModel`s in `agent/contracts.py` unless stated. New schema strings are versioned. "R" means required, "O" optional.

### E.1 ViolationRegistry (`agent/violation_registry.py`, new, static)

```python
ViolationClass = Literal["DETERMINISTIC_FIX", "PATCH", "FACT_DISPOSITION", "STRUCTURAL"]
Severity      = Literal["blocking", "degradable"]
PatchScope    = Literal["token", "sentence", "citation", "conclusion", "result", "fact_op", "disposition", "item"]

class RegistryEntry(NamedTuple):
    code: str; check: str; cls: ViolationClass; severity: Severity; scope: PatchScope
```

| Code(s) | Class | Severity | Scope | Deterministic fix / note |
|---|---|---|---|---|
| QUOTE_FRAGMENT_ORDER | DETERMINISTIC_FIX | degradable | citation | reorder fragments by first offset in unit text |
| CITATION_UNUSED | DETERMINISTIC_FIX | degradable | citation | drop citation not referenced anywhere |
| DUPLICATE_ITEM | DETERMINISTIC_FIX | degradable | item | keep first |
| MARKER_UNRESOLVED | DETERMINISTIC_FIX **iff** a unique mapping exists, else PATCH | degradable | token | unique mapping rules: the token equals a cite_id after case-fold/strip; or `[[c:N]]` where exactly one cite_id ends in `-N`/`N`. Never map a calc id to a cite id |
| UNTRACED_NUMBER, CALC_UNKNOWN, CALC_MISMATCH | PATCH | degradable | sentence | F3 sentence indices define the scope |
| QUOTE_FRAGMENT_NOT_FOUND, VERSION_MISMATCH, UNIT_NOT_RESOLVABLE | PATCH | degradable | citation | — |
| CITED_NOT_READ | PATCH | **blocking** when the citation is the only governing support of a binding_law conclusion, else degradable | citation (+ markers that reference it) | patch may read (≤2) |
| NOT_VALID_AT_LEGAL_DATE, TERRITORY_MISMATCH, BASIS_AUTHORITY_MISMATCH | PATCH | blocking | conclusion | — |
| MISSING_RESULT, OUTCOME_SHAPE, ISSUE_REF_INVALID, SCENARIO_PREMISE_MISSING | STRUCTURAL | blocking | result | — |
| UNKNOWN_NOT_STATED, QUOTE_NOT_IN_USER_MESSAGES, FACT_VALUE_UNSUPPORTED, ASSERT_ON_KNOWN_KEY, DUPLICATE_FACT_KEY | FACT_DISPOSITION | blocking | fact_op / disposition | — |
| KNOWN_FACT_ASKED, UNKNOWN_FACT_REASKED, REPEAT_WITHOUT_REASON, QUESTION_CEILING, QUESTION_NOT_FACT_GAP | FACT_DISPOSITION | degradable | item | — |
| CONCLUSION_FACT_UNKNOWN, DECIDED_CONDITION_UNBOUND | FACT_DISPOSITION | blocking | conclusion | — |
| ★ DISPOSITION_MISSING, DISPOSITION_KEY_MISMATCH, PROPOSITION_UNREGISTERED, DUPLICATE_PROPOSITION | FACT_DISPOSITION | blocking | disposition | §E.3 |
| ★ AA_CONSEQUENCE_NOT_ESTABLISHED, AA_UNREFLECTED_CLAUSE, AA_UNRESOLVED_REFERENCE, AA_ACTION_CONSEQUENCE_MISSING | PATCH | degradable | conclusion / result | §E.4 |

Invariants:
- Every code the validator can emit has exactly one entry; a unit test enumerates `self.add("V…", "<CODE>"` literals in `validator.py` and fails on a missing entry.
- **Blocking** means that, if unresolved after the patch round, `finalize` must remove or relabel the offending element (existing drop/relabel policies). **Degradable** means `finalize` may annotate.
- No code is downgraded from its current finalize action. The registry adds routing only; it weakens no check.

### E.2 Repair patch (`repair_patch/1`) and selection

Validation report gains finding ids (backward-compatible field):
```json
{"schema":"validation_report/2","ok":false,
 "findings":[{"id":"v-1","source":"validator","check":"V6","code":"UNTRACED_NUMBER",
              "path":"results.0.sections.answer_es","scope":{"kind":"sentence","field":"results.0.sections.answer_es","sentence_indices":[2]},
              "detail":"…F3 text…"},
             {"id":"a-1","source":"audit","code":"AA_CONSEQUENCE_NOT_ESTABLISHED","path":"results.0.conclusions.1",
              "scope":{"kind":"conclusion","path":"results.0.conclusions.1"},
              "detail":"…","evidence":[{"unit_id":"BOE-A-1992-28740::art-91","quote":"…"}]}],
 "instruction":"Corrija solo los elementos indicados mediante repair_consultation. No reenvíe la consulta completa."}
```

Tool `repair_consultation` (forced `tool_choice` in the patch round). Arguments `RepairPatchV1`:
```json
{"schema":"repair_patch/1",
 "ops":[
  {"op":"replace_sentence","field":"results.0.sections.answer_es","sentence_index":2,"text_es":"…","addresses":["v-1"]},
  {"op":"set_field","path":"results.0.conclusions.4.basis","value":"interpretive","addresses":["v-5"]},
  {"op":"set_conclusion_text","conclusion_path":"results.0.conclusions.1","text_es":"…","addresses":["a-1"]},
  {"op":"add_condition","conclusion_path":"results.0.conclusions.1","condition":{"…ConditionV1"},"addresses":["a-1"]},
  {"op":"set_condition","path":"results.0.conclusions.1.conditions.0","condition":{"…"},"addresses":["v-7"]},
  {"op":"add_conclusion","result_path":"results.0","after_conclusion_id":"c2","conclusion":{"…ConclusionV1"},"answer_sentence_es":"…","addresses":["a-2"]},
  {"op":"add_citation","citation":{"…CitationV1"},"addresses":["v-3"]},
  {"op":"remove_citation","cite_id":"c3","addresses":["v-3"]},
  {"op":"set_quote_fragments","cite_id":"c3","fragments":["…"],"addresses":["v-4"]},
  {"op":"add_calculation","calculation":{"…"},"addresses":["v-1"]},
  {"op":"set_fact_op","index":3,"fact_op":{"…FactOpV1"} ,"addresses":["v-8"]},
  {"op":"set_disposition","fact_key":"destino_taller","disposition":{"…ItemDispositionV1"},"addresses":["v-9"]},
  {"op":"add_result","result":{"…IssueResultV1"},"addresses":["v-10"]},
  {"op":"dismiss_finding","finding_id":"a-1","reason_es":"…","evidence":[{"unit_id":"…","quote":"…"}]}
 ]}
```
Field semantics and rules (PatchApplier, `agent/patch.py`, new):
1. **Addressing.** Every op except `dismiss_finding` has `addresses` ⊆ report finding ids (R, non-empty). `dismiss_finding` is allowed only for `source=="audit"` findings and requires ≥1 verbatim evidence quote from a read unit (checked with the V4 matcher).
2. **Allow-list.** An op's target must lie inside the `scope` of at least one addressed finding:
   - `sentence`: `replace_sentence` on that field and index only.
   - `citation`: citation ops on that cite_id, plus `replace_sentence` for sentences containing its marker.
   - `conclusion`: `set_conclusion_text`, conditions, `add_conclusion` after it, citation additions it references, and one `replace_sentence` per answer section that mentions the conclusion.
   - `result`: `add_result`/`set_field` under that result.
   - `fact_op`/`disposition`: the indexed fact op or the named item.

   Anything else is rejected with `PATCH_OP_OUT_OF_SCOPE`.
3. **Anchor preservation.** Let `anchors(s)` be the multiset of:
   - (a) statute pointers: the regex `\b(?:art(?:[íi]culo)?s?\.?|disposici[óo]n\s+(?:adicional|transitoria|final))\s*[\dºª.]+(?:\.[A-Za-z]+)*(?:\s*(?:,|y|a)\s*[\dºª.]+)*` plus `Ley \d+/\d{4}` and `Real Decreto(?: Legislativo)? \d+/\d{4}`, matched only outside `[[…]]` tokens;
   - (b) citation tokens `[[c:id]]` resolved to `unit_id`;
   - (c) figures that the V6 tracer grounds;
   - (d) `(conclusion_id, kind, basis)`;
   - (e) `(conclusion_id, condition fact_key, status)`.

   For each accepted text op, every anchor of the original target text must also appear in the new text, **except** anchors that are the subject of an addressed finding (the untraced figure span, the removed cite id, the changed basis). On failure the op is rejected with `PATCH_ANCHOR_LOSS` and the original text kept. Anchors outside any op target are untouched by construction.
4. **Ordering.** Ops are applied in list order on the deterministically fixed original (C0 source). Index-based ops are resolved against the original before any insertion.
5. **Result.** C1 = the patched submission, re-parsed with `SubmissionV1`. If parsing fails, C1 is discarded.

CandidateSelector (`agent/patch.py`):
```
v0 = validate(C0) ; v1 = validate(C1)   # C0 = deterministically fixed original
blocking(x) = count of blocking-class findings ; total(x) = all findings (validator + unresolved audit)
# audit findings dismissed by a valid dismiss_finding op count as resolved in v1
select C1 iff  blocking(v1) <= blocking(v0)
           and total(v1)    <  total(v0)
           and no PATCH_ANCHOR_LOSS was *accepted*   (always true by rule 3)
otherwise C0.  Ties → C0.
```
Then `finalize(selected)`. The existing `empty_repair` rule is subsumed (an empty C1 can never have fewer blocking findings than a non-empty C0 with results).

Persisted record (`ResidualV1`-adjacent, in `LoopOutcomeV1`; JSON-safe):
```json
{"schema":"repair_record/1","mode":"patch","first_submission_sha256":"…","findings":12,
 "deterministic_fixes":[{"code":"QUOTE_FRAGMENT_ORDER","path":"citations.2"}],
 "ops_total":7,"ops_accepted":6,"ops_rejected":[{"index":4,"reason":"PATCH_ANCHOR_LOSS"}],
 "dismissed_findings":["a-2"],"selected":"patched","blocking_before":2,"blocking_after":0,"total_before":5,"total_after":1}
```
Invalid states:
- `selected=="patched"` with `blocking_after > blocking_before`;
- an accepted op with empty `addresses`;
- `mode=="patch"` with a second `submit_consultation` in the same turn.

### E.3 Clarification ledger

**Proposition registry** (state field `propositions`, new):
```python
class PropositionRelationV1(ContractModel):
    kind: Literal["narrower_of", "broader_of", "alternative_to", "derived_from"]
    fact_key: str
class PropositionV1(ContractModel):
    fact_key: str                    # R, FACT_KEY_PATTERN, unique per case
    proposition_es: str              # R, 8–240 chars, the statement whose value/truth is sought; immutable
    answer_shape: Literal["yes_no","choice","number","money","date","text","territory"]  # R
    introduced_turn: int             # R
    introduced_by: Literal["question", "assertion", "migration"]  # R
    relations: list[PropositionRelationV1] = []
```
Submission additions (all O at schema level; validator enforces when applicable):
- `ClarificationItemV1.proposition_es` (R by validator for a new key);
- `FactOpV1.proposition_es` (R by validator when the op introduces a new key);
- `FactOpV1.relations` (O).

Rules:
- PROPOSITION_UNREGISTERED: a new key without `proposition_es`.
- DUPLICATE_PROPOSITION: a new key whose `casefold`-normalised `proposition_es` equals an existing one's. That is the only deterministic duplicate test; semantic overlap is declared by the model through `relations`, and the renderer groups related keys.
- `proposition_es` is never changed; a changed meaning needs a new key with `derived_from`.

**Item disposition** (new submission field `item_dispositions: list[ItemDispositionV1]`):
```python
DispositionKind = Literal["answered", "answered_approx", "unknown_by_user", "declined",
                          "deferred_by_user", "not_addressed", "withdrawn"]
class ItemDispositionV1(ContractModel):
    fact_key: str                         # R: an item open at turn start
    batch_id: str                         # R: its batch
    kind: DispositionKind                 # R
    user_quote: str | None                # R unless kind in {"not_addressed","withdrawn"}; verbatim from CURRENT message
    fact_op_index: int | None             # R iff kind in {"answered","answered_approx"}: index of an assert/correct on the SAME fact_key
    withdraw_reason: Literal["no_longer_material","issue_parked","answered_by_other_fact"] | None  # R iff kind=="withdrawn"
    answered_by_fact_key: str | None      # R iff withdraw_reason=="answered_by_other_fact"
```
Validator rules (V8, FACT_DISPOSITION class):

| Rule | Code |
|---|---|
| `{d.fact_key}` must equal the set of open items at turn start (status `open`, including `hold`) | DISPOSITION_MISSING (missing) / invalid (extra) |
| answered* ⇒ `fact_ops[fact_op_index].fact_key == d.fact_key` and that op passes the existing quote/value checks | DISPOSITION_KEY_MISMATCH. EA-B05 would fail with DISPOSITION_MISSING: its five open items received no disposition, and the new key `reclamacion_tienda_fecha` is allowed only with `proposition_es`. H-M4 passes this rule (same key, verbatim quote); see note |
| `mark_unknown` on an open item requires a disposition `unknown_by_user` for the same key | DISPOSITION_KEY_MISMATCH |
| `unknown_by_user` ⇒ `states_ignorance(user_quote)` (lexicon) when the verifier is not enforcing | UNKNOWN_NOT_STATED (existing code, **new detail**, below) |
| The same `user_quote` span used by >1 `unknown_by_user` disposition | committed as `hold` unless verifier-confirmed broadcast (not a violation) |
| `declined`/`deferred_by_user` ⇒ `user_quote` contained in the current message | QUOTE_NOT_IN_USER_MESSAGES |

Note on H-M4: whether `forma_retribucion = "prestación bajo instrucciones…"` answers the remuneration proposition is semantic. CL makes it *checkable* (proposition_es is explicit and the verifier sees it). The deterministic layer cannot and must not decide it.

New detail for UNKNOWN_NOT_STATED (replaces "If the client simply did not answer, leave the fact out; it remains askable."):
> "The quoted words do not say the client does not know this item. Choose the disposition that matches: `declined` if they cannot or will not provide it, `deferred_by_user` if they will check later, `answered_approx` if they gave an approximate value, `not_addressed` if the reply does not concern it. Do not delete the item."

**Ledger item** (replaces `AskedItemV1` in state; `asked_log` becomes a derived view):
```python
LedgerStatus = Literal["open", "answered", "unknown_by_user", "declined", "deferred_by_user",
                       "withdrawn", "superseded", "conflicted"]
class LedgerItemV1(ContractModel):
    fact_key: str; batch_id: str; issue_ids: list[str]
    asked_turns: list[int]                       # ≥1
    status: LedgerStatus
    status_turn: int
    hold: Literal["broadcast_unconfirmed", "verifier_ambiguous"] | None = None   # only with status "open"
    quote: str | None = None                     # disposition quote
    verification: FactVerificationV1 | None = None   # existing J contract
    withdraw_reason: str | None = None
```
Transitions (deterministic, StateUpdater):

| From | Event | To |
|---|---|---|
| (none) | item asked | open |
| open | `answered`/`answered_approx` + accepted assert/correct same key | answered (value precision recorded) |
| open | `unknown_by_user` accepted (lexicon, or verifier per mode) | unknown_by_user |
| open | `unknown_by_user` sharing a span with others, broadcast unconfirmed | open, hold=broadcast_unconfirmed |
| open | `declined` | declined |
| open | `deferred_by_user` | deferred_by_user (re-askable once, next turn) |
| open | `not_addressed` | open (no new ask counted unless re-asked) |
| open | asked again | open, asked_turns += turn |
| open | `len(asked_turns) == 2` and `not_addressed` again | withdrawn(`max_asks`) (controller) |
| open | `withdrawn` (model) | withdrawn |
| any closed | later assert/correct on the key | answered (supersedes; FE-3 reopen rule satisfied by the explicit event) |
| answered | conflicting assert without `correct` | conflicted (FactViewV1 `conflicted` already exists) + one auto confirmation item |
| any | key superseded via a `derived_from` relation and the model withdraws | superseded |

Invariants:
- Items are never deleted. `pending_clarification.items` = ledger items with status `open` (and due `deferred_by_user`).
- Re-asking an item with status `unknown_by_user`, `declined` or `withdrawn` raises `UNKNOWN_FACT_REASKED`/`REPEAT_WITHOUT_REASON` unless reopened by a later user statement.
- Legal conditions on a key whose status ≠ `answered` must have status `unknown` or `assumed` (existing DECIDED_CONDITION_UNBOUND covers this once it reads ledger status).

**Attribution rendering** (renderer, from ledger only):

| Status | Client-visible phrase (Spanish, fixed templates) |
|---|---|
| unknown_by_user | "Ha indicado que no conoce: {proposition_es}." |
| declined | "No ha podido facilitar: {proposition_es}." |
| deferred_by_user | "Queda pendiente que confirme: {proposition_es}." |
| open + hold | (existing J S6 scope-confirmation line) "Entiendo que no dispone de {list}; si conoce alguno, indíquelo." |
| withdrawn/no_longer_material | nothing |

The prompt instructs the model not to narrate these statuses in prose. A soft telemetry probe counts model prose phrases "usted (ya) indicó"/"ha indicado"/"datos que el cliente conoce" (not a validator rule).

**Disposition verifier** (`fact_verifier.py`, question `reply_disposition/1`; replaces D1/D2 for asked items; D1 kept only for `mark_unknown` on *unasked* keys):
- One request per turn with ≥1 non-value disposition or any shared quote span.
- Context: the previous assistant message, numbered open questions (each with `proposition_es`), and the current message.
- One `choice` question per open item.
- Labels (mutually exclusive):
  - `ANSWERED` — affirms a value for *this* question;
  - `ANSWERED_APPROX` — an approximate or hedged value ("creo que en marzo");
  - `NOT_KNOWN` — says they do not know or remember *this* item, explicitly or by a collective expression that names a set including it ("ninguno de esos datos"). A bare «No lo sé» after several questions is **not** NOT_KNOWN;
  - `DECLINED` — cannot or will not provide it; no claim about knowing;
  - `DEFERRED` — will check or look it up later;
  - `NOT_ADDRESSED`;
  - `HYPOTHETICAL_ONLY`;
  - `AMBIGUOUS` — cannot tell which question is meant, or self-contradictory.
- Mapping: agreement → commit. Model `unknown_by_user` with verifier `DECLINED`/`DEFERRED`/`ANSWERED_APPROX` → commit the verifier's kind if `enforce`, else commit the model's kind and log a disagreement. Verifier `AMBIGUOUS`/`NOT_ADDRESSED` against a model non-value kind → `open` + `hold=verifier_ambiguous` in `enforce`.
- Bands reuse `choice_band` with a new policy version. Enforcement requires the owner calibration gates from the Jev design (AC-1 precision Wilson-lower ≥0.95 on `NOT_KNOWN`; stability ≤2 %).

### E.4 Applicability audit (`agent/reviewer.py` evolved; prompt `prompts/applicability_audit_v1.md`)

Eligibility (deterministic):
- Conclusions with `basis == "binding_law"` and `kind ∈ {"application","conditional","calculation_result"}`, ordered by (has figure, has conditions, position).
- Max 8 conclusions and max 8 units per turn.
- Unit text is the full read text from the read set/provision store, capped at 12 000 chars per unit, with the cited pinpoint segment guaranteed included.
- Skip when the turn outcome is clarification-only, or when the remaining turn budget is below the patch-round reserve.

Request `applicability_audit_request/1`:
```json
{"schema":"applicability_audit_request/1","legal_date":"2026-10-15",
 "issues":[{"issue_ref":"issue-1","question_es":"…","client_messages_es":["…"]}],
 "facts":[{"fact_key":"…","proposition_es":"…","status":"answered|unknown_by_user|declined|open|…","value_display_es":"…"}],
 "conclusions":[{"conclusion_id":"c2","issue_ref":"issue-1","kind":"application","text_es":"…",
                 "conditions":[{"description_es":"…","fact_key":"…","status":"satisfied","cite_ids":["c4"]}],"cite_ids":["c4","c5"]}],
 "units":[{"unit_id":"BOE-A-1992-28740::art-91","label_es":"…","text_es":"…"}]}
```
Response (forced tool `submit_audit`) `applicability_audit/1`:
```json
{"findings":[{"conclusion_id":"c2",
  "kind":"consequence_not_established|unreflected_limiting_clause|unresolved_cross_reference|action_consequence_missing",
  "consequence_es":"tipo aplicable al margen del revendedor",
  "evidence":[{"unit_id":"…","quote":"≤400 chars verbatim"}],
  "affected_fact_keys":["…"],
  "proposed_resolution":"add_condition|add_branch|correct_consequence|read_reference|state_or_scope_out",
  "research_request":{"query_es":"…","reason_es":"…"} }]}
```
Deterministic post-check:
- `conclusion_id` exists.
- Evidence quotes are verbatim in the supplied unit text (V4 matcher). They are required for the first three kinds.
- `action_consequence_missing` requires `research_request`.
- Failures → `AUDIT_UNGROUNDED` (logged, finding dropped).
- Surviving findings become `AA_*` findings (registry §E.1) with `source:"audit"`.

**Material-completeness standard** (what the audit checks; what "complete" means):
- **MC1 Consequence binding.** Each operative consequence a conclusion states (qualification, regime, rate, amount, deadline, obligation, right, prohibition) is established by a supplied unit *for this actor, transaction and time*.
- **MC2 Limiting clauses.** Every clause in the cited units that, on the case facts, excludes, limits or conditions that consequence (exception, exclusion, precondition, threshold, time limit) is reflected as a condition or branch, or is ruled out by a stated fact.
- **MC3 Dependent references.** An explicit cross-reference in a cited unit on which the consequence depends ("en los términos del artículo X", "lo dispuesto en…") is read, or recorded as `UNRESOLVED_REQUIRED_REFERENCE`.
- **MC4 Action consequence (qualification issues only).** When a conclusion classifies the client (worker, taxpayer, contract type, regime), the principal legal consequence requiring client action (registration, filing, withholding, formalisation) is stated, or explicitly scoped out in `limitations`. It is found through ≤1 research request.
- **Out of scope by definition:** exceptions not textually connected to cited units or their explicit references, and doctrine not in the corpus. The agent is not expected to discover these.

Patch-round handling: the agent may correct, add a condition or branch, read ≤2 units (only for `read_reference`/`action_consequence_missing`), or `dismiss_finding` with evidence. If an `AA_*` finding is unresolved after selection, v1 behaviour is **log only** (no client-visible marker) until AA precision is measured (OD-3).

### E.5 Controller transitions and limits

```
DRAFT ─schema invalid→ SCHEMA_RETRY(1) ─invalid→ salvage(schema_retry) as today
DRAFT ─ok→ FIX → VALIDATE → [VERIFY] → [AUDIT] → findings?
   none → FINALIZE(C0) → COMMIT → RENDER                              outcome as drafted
   some → PATCH_ROUND(1 call; tools: repair_consultation, read_provision≤2 if requested)
           ├ provider error / budget denial / wall-clock → SELECT=C0 (salvage reason recorded)
           ├ patch schema invalid → SELECT=C0
           └ ok → APPLY → VALIDATE(C1) → SELECT → FINALIZE → COMMIT → RENDER
```
Limits:
- ≤1 patch round per turn;
- ≤2 extra reads;
- the AA call counts against `turn_budget_eur` and wall-clock (`check_clock` before the call; skip AA if it could overrun).

The reviewer's old post-repair revision (`loop.py`, the `reviewed` branch) is disabled when `AGENT_AUDIT_MODE != off`, so there is at most one model rewrite.

### E.6 Backward compatibility, migration, flags

| Item | Rule |
|---|---|
| State schema | `consultation_agent_state/2`: adds `propositions`, `ledger` (replaces `asked_log`). Lazy migration on load: each `AskedItemV1` → `LedgerItemV1` (settled ⇒ status from the latest fact event for the key: assert/correct→answered, mark_unknown→unknown_by_user; unsettled ⇒ `open`); propositions from the first item `question_es` or the first event `display_es` (`introduced_by:"migration"`). `asked_log` stays as a derived read-only view for telemetry and old tooling |
| SubmissionV1 | new optional fields only (`item_dispositions`, `proposition_es`, `relations`); old fixtures parse unchanged |
| Validation report | `validation_report/2` adds `findings[].id/scope/source`; `validation_report/1` kept when `AGENT_REPAIR_MODE=full` |
| Flags (config.py + `.env.example` + docs) | `AGENT_REPAIR_MODE=full\|patch` (default `full` until acceptance); `AGENT_CLARIFICATION_LEDGER=off\|on` (default `off`); `AGENT_FACT_VERIFIER` (existing J flag: off\|shadow\|enforce) with question version `reply_disposition/1`; `AGENT_AUDIT_MODE=off\|shadow\|on`; `AGENT_AUDIT_MODEL`; `AGENT_AUDIT_MAX_CONCLUSIONS=8`. `AGENT_REVIEWER_ENABLED` becomes an alias of `AGENT_AUDIT_MODE=on` for one release, then removed |
| Mutual exclusion | `AGENT_AUDIT_MODE=on` requires `AGENT_REPAIR_MODE=patch` (config validation error otherwise) |

### E.7 Telemetry (CLAUDE.md permanent rule)

New turn-metric keys (export in `consultation/telemetry.py` `turn_metrics`, aggregate in `ops_report.py`, document in `TELEMETRY_RUNBOOK.md`, add to `REQUIRED_TURN_KEYS` in `tests/v3/test_consultation_telemetry_coverage.py`):
- `repair_mode`;
- `det_fixes_count`;
- `patch_ops_total`, `patch_ops_accepted`;
- `patch_ops_rejected_by_reason` (closed codes `PATCH_OP_OUT_OF_SCOPE`, `PATCH_ANCHOR_LOSS`, `PATCH_SCHEMA`);
- `candidate_selected` (`original|patched`);
- `blocking_before`, `blocking_after`;
- `anchor_count_first`, `anchor_count_final`;
- `ledger_items_open_start`, `dispositions_by_kind`, `disposition_coverage_ok`, `ledger_holds`;
- `verifier_disagreements_by_pair`;
- `items_withdrawn_max_asks`;
- `audit_mode`, `audit_conclusions`, `audit_findings_by_kind`, `audit_ungrounded`, `audit_dismissed`, `audit_resolved`;
- `research_again_reads`.

All values are counts, closed codes or hashes; never text. Failures in bookkeeping are swallowed (fault-injection test).

---

## F. Failure handling and safety

| Situation | Behaviour | Outcome class |
|---|---|---|
| LLM produces inconsistent interpretations (draft says X, patch says not-X) | Selector picks by blocking/total counts only; both candidates are logged (`repair_record`). Polarity change of a conclusion is allowed only via an op addressing an AA or blocking finding | answer from the selected candidate |
| Validator uncertain whether a figure/claim is supported | No new uncertainty band: V6/V2/V9 stay binary and conservative (must-reject fixture of 25 stays). Uncertainty is handled by *where* the fix may happen (patch scope), not by relaxing the check | answer with a residual marker if unrepaired |
| A repair would delete previously supported material | `PATCH_ANCHOR_LOSS` rejects the op; original text kept; finding falls to `finalize` | answer (original content + residual) |
| Patch introduces new violations | Counted in `total(v1)`; the selector prefers C0 unless strictly better | answer |
| Two user statements conflict | Ledger `conflicted`; both events retained; conditions on the key forced to `unknown`; one confirmation item auto-generated (bypasses the max-ask rule once) | conditional answer + clarification |
| One answer ambiguously applies to several questions | Shared-span `unknown_by_user` → `open + hold` (no attribution, scope-confirmation line). Verifier `AMBIGUOUS` → same | conditional answer + confirmation line |
| User refuses / cannot answer | `declined`: no re-ask; conditions `unknown`; neutral attribution | conditional answer |
| User will check later | `deferred_by_user`: one re-ask next turn | conditional answer |
| Item ignored twice | `withdrawn(max_asks)`; conditions `unknown` | conditional answer |
| Material exception unresolved (AA finding remains) | v1: logged only; the agent's answer stands (ADR-6 principle: the reviewer cannot block). Owner decision OD-3 after measurement: optional limitation line | answer |
| Corpus lacks decisive evidence | Unchanged: `CORPUS_INSUFFICIENCY` gap; no figure from memory; AA `research_request` may run ≤2 reads but cannot add memory claims | partial answer / abstention on that point |
| Provider failure or budget exhaustion during AA | AA skipped (`audit_skipped_reason`); the patch round proceeds with validator findings only | as without AA |
| Provider failure or budget exhaustion during the patch round | C0 selected and finalized (same as today's salvage semantics, but from the *original*, not a partial rewrite) | answer with residuals |
| Verifier unavailable | `off`/degraded: lexicon gate + shared-span hold; never promotes to `unknown_by_user` on uncertainty | as specified |

**When the system answers, clarifies, researches again or abstains:**
- *Answer* whenever at least one supported conclusion exists (conditional if any decisive fact ≠ `answered`).
- *Clarify* only items that are open, not re-ask-blocked, and changing a conclusion (existing §D policy, enforced by the ledger).
- *Research again* only via `CITED_NOT_READ` or an audit `research_request`, inside the single patch round, ≤2 reads.
- *Abstain* on a point only with a classified gap (unchanged).

---

## G. Alternatives and architectural decisions

### G.1 Repair (Problem 1)

| Option | Verdict | Reason / evidence |
|---|---|---|
| **PR: typed patch + allow-list + anchor preservation + deterministic selection** | **Chosen** | Attacks the confirmed mechanism (whole rewrite, no preservation, no selection). Deterministic guarantees; no check weakened |
| More accurate checks (F1/F2/F3-style) only | Rejected as sufficient | Already done; changed only UNTRACED; turns with any violation 69→61/102; live repair rate unchanged; F3 location ignored (H-N3) |
| Stronger "keep all correct content" prompt wording | Rejected | Already in prompt (`system_v1.md` step 5) and in F3 detail; diff shows non-compliance |
| Skip repair; finalize the first draft directly (annotate everything) | Rejected | Loses the 11+ necessary contract repairs (E-A §6.3) and turns every residual into a client-visible marker |
| Relax V6/V2 to cut repairs | Rejected | 25 must-reject figures; would pass unsupported claims (non-negotiable) |
| Diff-and-merge of a full resubmission (keep original where the rewrite changed un-flagged parts) | Rejected | Needs semantic alignment of free text; fragile; the patch makes it unnecessary |
| Two repair rounds | Rejected | Cost +47 % per repaired turn already; latency gate |
| Adopt unknown Repair V2 | Undecidable here | Code unavailable (OD-1) |

Costs and risks of PR:
- One new tool schema.
- Model compliance with typed patches (risk: SCHEMA errors; mitigated by C0 fallback).
- Sentence segmentation must match F3's `_sentence_bounds` (`validator.py:158`).

Remaining uncertainty: live compliance rate, and the repair-output token reduction.

### G.2 Facts (Problem 2)

| Option | Verdict | Reason / evidence |
|---|---|---|
| **CL: proposition registry + mandatory per-item dispositions + 8-state lifecycle + verifier on non-value kinds** | **Chosen** | Fixes the confirmed missing state and implicit disposition; makes the semantic question checkable |
| Better ignorance lexicon / paraphrase recall | Rejected | Would promote refusals to `unknown_by_user` (owner policy: refusal = UNCLEAR); E-A B04/B05 cause is a missing state, not recall |
| Enforce Jev D1+D2 as built | Rejected now | Fails its own AC-1 (0.884) and AC-6 (2.34 %); label definitions overlap (§B.2); gates only proposed ops |
| Carry-forward only (J `224531f2`) | Necessary, insufficient | Converts silent drop into repeated questions (E-B EA-B04) |
| Deterministic semantic dedupe of fact keys (string similarity) | Rejected | Semantic correctness must not be regex; the exact-normalised duplicate check only, plus declared relations |
| Global fact ontology per law | Rejected | Violates "no law-specific runtime programming" |

Costs and risks of CL:
- A larger submission (one disposition per open item; ≤6 items).
- One more repair class.
- A state migration.
- The verifier calls are cheap (pilot: EUR 6e-05, p95 343 ms).

Remaining uncertainty: model compliance with the coverage invariant; calibration of `reply_disposition/1` (paid).

### G.3 Exceptions and qualifications (Problem 3)

| Option | Verdict | Reason / evidence |
|---|---|---|
| **AA: evolve the ADR-6 reviewer into an evidence-span applicability audit with MC1–MC4, feeding the single patch round** | **Chosen (shadow first)** | Acts at the two failing boundaries (consequence binding; frame/action consequence); grounded in already-read text; reuses existing code; bounded |
| P7-A exception cues at read time | Rejected (E-B) | No gain, +26.5 % latency, +8 leaks; acts at the research stage, which is not the bottleneck |
| P7-B alternatives field in drafting | Rejected (E-B) | No gain, +41 % latency, +33 markers; same-pass self-critique |
| More prompt rules on exceptions | Rejected | Prompt §B/§C already say it; a prior pre-registered prompt A/B failed |
| Mandatory `consequences[]` field in the drafting schema | Rejected | P7-B lesson: drafting schema load raised markers/latency. AA extracts consequences itself |
| Law-specific exception tables | Rejected | Non-negotiable principle |
| Unbounded research loop | Rejected | Cost/latency; retrieval is not the bottleneck (E-B core units 34/36) |
| ADR-6 reviewer as built (post-repair revision) | Rejected as is | Adds a second full rewrite, inheriting Problem 1; defects need no evidence spans; never measured |

Costs and risks of AA:
- One extra model call per eligible turn (estimate EUR 0.003–0.006, +5–12 s).
- False positives could push correct answers away. Mitigations: evidence-span requirement, the agent's dismiss right, log-only for unresolved findings, and shadow measurement before `on`.

Remaining uncertainty: AA detection rate and precision. This is **the main unproven element** of the package.

### G.4 Why earlier work did not prove improvement

- **P7-A/P7-B** intervened before or within drafting and added load. The decisive failures (H-P3 frame; H-N1 unbound consequence) are invisible at those points.
- **F1–F3** improved the accuracy of one check, while the user-facing harm is governed by the repair *protocol*. Measured repair frequency is dominated by genuine violations and by non-number codes.
- **Jev pilot**: the decision formulation (§B.2 a–d) and the absence of a target state for refusals, not the model's language ability.
- **JEV triage / Repair V2**: not assessable (absent).

---

## H. Sonnet implementation specification

Base branch (OD-2, owner):
- Create `impl/top3-reliability-<date>` from a merge of `impl/reliability-eb-20261031` (F1–F3, P7 flags off) and `impl/jev-semantic-fact-verification-v1` (carry-forward, Jev transport).
- Both descend from `d4304d10`; expected conflicts in `validator.py`, `contracts.py`, `config.py`, `telemetry.py`, `state.py`, `turn_manager.py`.
- If the owner's local `impl/jev-triage-20261101` exists, merge it too, and reconcile with §D.4 before H2.

Every slice: own commit(s); verification command `cd backend && .venv\Scripts\pytest apps/legal_graphrag/tests/v3/agent -q` plus `ruff check .`; record results in the commit body.

| # | Slice | Files | Required behaviour | Acceptance | Indispensable? |
|---|---|---|---|---|---|
| H0 | Integration base | merge only | Resolve conflicts; F1–F3 and J behaviours both present | Full agent suite passes (≥868 R tests + J tests); `test_flag_off_*` byte-identity tests still pass | yes |
| H1 | Replay/diff instrument | `scripts/e2e_eval_v4/repair_diff.py` (port of this mission's scratch script), `test_repair_diff.py` | First-vs-final diff over a diagnostics dir: read-cited units lost, anchor loss (§E.2 rule 3 regex), conclusions gone, selection | Reproduces §0.3 numbers on E-A (65 repaired; 0 read units lost; 8 turns statute loss) | yes |
| H2 | ViolationRegistry + DeterministicFixer | `agent/violation_registry.py`, `agent/validator.py` (call fixer after `_normalize`), tests | Registry table §E.1; fixer for QUOTE_FRAGMENT_ORDER, CITATION_UNUSED, DUPLICATE_ITEM, unique MARKER_UNRESOLVED | Static test: every emitted code registered. Replay on E-A/E-B first submissions: fixer-resolved findings counted; 0 prose changes outside tokens; must-reject fixture unchanged | yes |
| H3 | Patch protocol | `agent/contracts.py` (`RepairPatchV1`, ops, `validation_report/2`), `agent/patch.py` (applier, anchors, selector), `agent/loop.py` (patch round, tool `repair_consultation`, forced tool_choice, C0/C1), `config.py` (`AGENT_REPAIR_MODE`) | §E.2 exactly; `full` mode byte-identical to today | Unit: allow-list (each scope), anchor loss rejection, ordering, selector truth table, C0 fallback on schema/provider error. Offline synthetic: for every repaired E-A/E-B turn, apply a patch that rewrites only flagged sentences → anchor loss outside = 0. `full`-mode transcript byte-identity test | yes |
| H4 | Clarification ledger | `contracts.py` (`PropositionV1`, `ItemDispositionV1`, `LedgerItemV1`, state v2), `state.py` (lifecycle, migration, remove `replaced` filter if still present), `validator.py` (DISPOSITION_*, PROPOSITION_*, new UNKNOWN_NOT_STATED detail), `context.py` (ledger view), `render.py` (attribution templates), `prompts/system_v1.md` (§D «no lo sé» line → disposition instruction; behind `AGENT_CLARIFICATION_LEDGER`) | §E.3 exactly | Layer-B replays (zero cost) of EA-B02/B04/B05, H-M4, H-N2 with oracle dispositions: no item leaves pending without a terminal status; refused items never re-asked; blanket «No lo sé» on 6 items → 6 × hold, 0 × `unknown_by_user`. Migration test on all 104 E-A `state_after` blobs: loads, round-trips, item counts preserved | yes |
| H5 | Disposition verifier question | `fact_verifier.py` (`reply_disposition/1`, labels §E.3), `epistemic_policy_v1.json` (new policy version, uncalibrated) | Shadow by default; enforce refused while uncalibrated (existing rule) | Offline: request builder snapshot; parser; mapping table tests; cache key includes question version | yes (shadow) |
| H6 | Applicability audit | `reviewer.py` → audit mode, `prompts/applicability_audit_v1.md`, contracts §E.4, `loop.py` (call before the patch round; disable old post-repair review when audit on), `config.py` | §E.4 exactly; `shadow` = run and log, no findings to the patch round | Offline (fake LLM): eligibility selection, evidence-span verification, AUDIT_UNGROUNDED, conversion to AA findings, dismiss rule, budget/clock skip | yes (shadow) |
| H7 | Telemetry | `consultation/telemetry.py`, `ops_report.py`, `TELEMETRY_RUNBOOK.md`, coverage tests | §E.7 keys | `test_consultation_telemetry_coverage.py`, `test_telemetry_enforcement.py` pass; privacy scan passes; fault-injection test | yes |
| H8 | Docs/env | `.env.example`, `docs/V3/simplification/04_SELECTED_ARCHITECTURE.md` addendum, `05_DATA_CONTRACTS.md` addendum | New flags and contracts documented | Review | yes |
| H9 | Optional: MC4 research request execution | `loop.py` patch-round tool set (`read_provision`≤2), search pre-execution of `query_es` | §E.4 | Fake-LLM tests | optional (needed for H-P3) |
| H10 | Optional: unresolved-AA limitation line | `finalize` | OD-3 | — | optional |

Dependency order: H0 → H1 → H2 → H3 → H4 → (H5 ∥ H6) → H7 → H8; H9 after H6.

Feature-flag rollout:
1. Ship H2–H8 with defaults `full/off/off/off` (byte-identical baseline).
2. Run offline acceptance.
3. Owner authorises the live controlled run (§I.3), first with `patch + ledger` and `audit=shadow`.
4. Then `audit=on` only if the AA gates pass.

Rollback: each flag independently back to its default. The state v2 migration is forward-only but lossless: `asked_log` is still derivable. Keep a v2→v1 export function for rollback reads.

Regression protections (must stay green):
- the `must_still_reject.json` fixture (25);
- the EXP-7 mutation suite;
- the S1–S7 guard tests;
- `test_flag_off_*` byte-identity;
- Jev S5 safeguards;
- the H-P3 "no false usted ya indicó" test.

---

## I. Testing and measurement

### I.1 Contract tests (offline, deterministic, zero cost)

| Area | Tests (minimum) |
|---|---|
| Registry | every emitted code registered; severities match §E.1 |
| Fixer | each fix on recorded E-A/E-B first submissions that carry the code; property test: fixer output differs from input only in the fixed token/field |
| Patch applier | one test per op × scope; anchor-loss reject (statute pointer, citation token, grounded figure, condition tuple); flagged-anchor exemption; out-of-scope reject; index resolution after insertions |
| Selector | truth table (blocking/total combos, ties → C0); C0 on schema/provider/budget errors |
| **Historical damage regressions** | V24.00 (art. 331.1), V28.00 (arts. 82–86, 18, 81.3, 86.2), V45.01 (art. 32.1 rule), V10.00 (arts. 4.Uno/11.Uno), E-B H-N3.01 (arts. 99.2, 76.1.c, 27, 95.2.b, 99.5). Feed the recorded *repaired* text as a patch for the flagged sentences only → the lost pointers are preserved or the op is rejected |
| **Genuine unsupported claims must still fail** | `must_still_reject.json` (25); category-e UNTRACED spans from `workstream_a/untraced_labels.json`; a CITED_NOT_READ governing citation stays blocking |
| Ledger | each transition row of §E.3; never-delete invariant (property test over random event sequences, 3 000 trials as in EXP-9); migration of 104 E-A states |
| **False unknown attribution** | EA-B02 reply «No lo sé.» with 6 open items → 6 holds, no `unknown_by_user`; EA-B04/B05 «no puedo responder…» → `declined`, no re-ask in the next turn; H-N2 `tipo_alumnado_clases` unrelated quote → `not_addressed`, then `withdrawn(max_asks)` |
| **Paraphrased / ambiguous replies** | Reuse the frozen Jev dataset (`jev114-ab-evaluation-20261031/dataset_frozen.jsonl`, 264 consensus rows). The lexicon gate on its rows must not accept any refusal/temporary-inability row as `unknown_by_user`. The 15 bare multi-question «No lo sé» rows → hold |
| **Related propositions** | EA-B02 `fecha_entrega` vs `fecha_entrega_aprox`: both registered with distinct `proposition_es` + relation; DUPLICATE_PROPOSITION on an exact duplicate; EA-B05 answer bound to a new key without a disposition for the asked items → DISPOSITION_MISSING |
| Multi-turn consistency | scripted 4-turn replay (fake LLM): ask → partial → refuse → correction reopens; state and rendered attribution agree each turn |
| AA (fake LLM) | evidence-span verification; ungrounded drop; dismiss requires evidence; eligibility caps; budget skip |
| **Citation preservation** | across all patch tests: read-cited unit set of C1 ⊇ C0's unless a `remove_citation` addresses a CITED_NOT_READ/QUOTE finding |

### I.2 Offline replay measurements (zero cost, before any live run)

- **R1:** H1 on E-A + E-B with `AGENT_REPAIR_MODE=full`. The numbers must match §0.3/§0.3b (instrument validity).
- **R2:** deterministic-fix coverage. Replayed findings resolved by the fixer, and the projected number of turns needing no model round (expected ≈5/65 E-A, ≈7/30 E-B baseline).
- **R3:** ledger layer-B. Recorded user messages + oracle dispositions (labelled by two annotators on the 26 E-A/E-B turns with open batches) → 0 asked-unsettled, 0 re-ask after declined.

### I.3 Controlled live experiment (requires owner authorisation; not run in this mission)

**Design.** Paired, same cases, same model/route/date.
- Arms: **A0** = H0 base with flags default; **A1** = `patch + ledger` (verifier shadow, audit shadow); **A2** = A1 + `audit=on`.
- Cases: the E-B 25 rule-based cases + Cohort B 8 + **12 untouched cases from `eval/gold36-b-20261031`** (unseen; generalisation, not calibration).
- **3 repeats per case-arm.** E-B showed a ~4/36 flip noise floor with 1 repeat.
- Cost envelope: E-B cost ≈ EUR 0.054 per case-arm (EUR 3.72 / 69 case-arms), so 45 cases × 3 arms × 3 repeats ≈ 405 case-arms ≈ EUR 22, plus AA calls in A2 (≈ EUR 1–2). Owner cap required (suggest EUR 25).

**Primary metrics (denominators explicit).**

| Metric | Denominator | Gate (A1 vs A0) |
|---|---|---|
| Repaired turns with anchor loss outside flagged spans | repaired turns | A1 = 0 (hard) |
| Repaired turns with any conclusion text gone | repaired turns | A1 ≤ ½ of A0 |
| Read-cited units lost by repair | repaired turns | 0 in both (must hold) |
| Must-reject leakage (unsupported figure/citation in final) | final answers | A1 ≤ A0 (hard: no increase) |
| Asked-unsettled items (no terminal status, not pending) | asked items | A1 = 0 (hard) |
| Re-ask after `declined`/`unknown_by_user` | such items | A1 = 0 (hard) |
| False `unknown_by_user` (human-checked against the message) | `unknown_by_user` events | A1 ≤ A0 and ≤ 2 % |
| Turn-0 + final CORRECT (as delivered, strict marker rule) | case-repeats | A1 ≥ A0 − noise (non-inferiority, margin 1 case/36 per repeat) |
| Median latency | turns | A1 ≤ A0 × 1.10; A2 ≤ A0 × 1.25 |
| Repair output tokens | repaired turns | report (expect A1 < A0) |

**AA gates (A2 vs A1).**
- AA findings precision ≥ 0.7 (two independent graders + owner/jurist adjudication on disagreements).
- ≥1 of {H-N1 margin rate, N01 art. 96.4, H-P3 RETA at turn 0} fixed in ≥2/3 repeats.
- 0 correct conclusions changed to incorrect.
- P9 leaks not increased.

Retain:
- diagnostics;
- `repair_record/1`;
- ledger snapshots;
- the AA request/response;
- blinded outputs;
- grader TSVs with notes.

### I.4 Adjudication rule

AI graders are triage only. Every gate-deciding disagreement and every claimed AA catch is adjudicated by the owner or a jurist against the statute text. No legal-correctness claim rests on AI grading alone.

---

## J. Final prioritized decisions

| # | Root cause | Proposed solution | Confidence (cause / cure) | Expected gain | Difficulty | Dependencies | Most important acceptance test |
|---|---|---|---|---|---|---|---|
| 1 | Whole-submission repair with no unit of change, no preservation, no selection (`loop.py:192/368/386`) | **PR**: registry + deterministic fixes + typed patch + anchor preservation + C0/C1 selection | High / High (by construction) | Repair damage → 0 outside flagged spans; fewer repair tokens; model round avoided in 5/65 E-A and 7/30 E-B-baseline repaired turns (projection) | Medium | H0, H1, H2 | Historical damage regressions (V24, V28, V45, V10, H-N3) preserved under patch; must-reject fixture unchanged |
| 2 | Implicit proposition identity and item disposition; two-state epistemic vocabulary; repair advice deletes; `replaced` drop (`state.py:546-556`) | **CL**: proposition registry, mandatory dispositions, 8-state ledger, new repair advice, ledger-rendered attribution | High / High for state integrity; Medium for model compliance | Eliminates asked-unsettled and re-ask-after-refusal; removes blanket attribution; routes the fact-family findings present in 21/65 E-A repaired turns to dispositions instead of deletion | Medium–High (state migration) | H0, H3 | EA-B02/B04/B05/H-N2 layer-B replays: 0 lost items, 0 re-asks after `declined`, 0 broadcast `unknown_by_user` |
| 3 | Jev task formulation (overlapping labels; gates proposed ops; UNCLEAR sink) | `reply_disposition/1` multi-item question, shadow until calibrated | High / Medium | Semantic check where the deterministic layer cannot decide (H-M4-type binding) | Low–Medium | H4 | Offline mapping tests; later calibration on the frozen dataset + new DECLINED/DEFERRED labels |
| 4 | No applicability check of consequences against cited text; frame not checked (H-N1, N01, H-P3) | **AA**: evolved ADR-6 reviewer with evidence spans, MC1–MC4, findings into the single patch round | Strongly supported / **Hypothesis** | Catch read-but-misapplied consequences; fix the H-P3 five-run miss | Medium | H3, H6 (+H9 for H-P3) | A2 shadow: AA precision ≥0.7 and ≥1 of the three named misses fixed in ≥2/3 repeats, 0 harmful flips |

**Smallest coherent package likely to produce a substantial improvement across all three problems:** H0 + H1 + H2 + H3 + H4 + H7 (PR + CL + telemetry), with H6 in **shadow**.
- **Problems 1 and 2:** PR and CL fix them by construction and can be validated mostly offline.
- **Problem 3:** shadow AA produces the evidence needed to switch it on without risking answers. H-P3 additionally needs H9.

**Genuinely unresolved decisions (owner):**
- **OD-1:** reconcile with the unavailable `impl/jev-triage-20261101` / `0de2b56a` (code-only triage, Repair V2) before H2/H3. Provide the branch or confirm it is superseded.
- **OD-2:** integration base = merge of `impl/reliability-eb-20261031` and `impl/jev-semantic-fact-verification-v1` (recommended).
- **OD-3:** client-visible handling of unresolved AA findings (recommended: log only until AA precision is measured).
- **OD-4:** live-run budget and authorisation for §I.3 (≈EUR 25 cap) and for verifier calibration labelling.
- **OD-5:** the attribution templates in §E.3 (wording is a product/legal-UX choice).
- **Carried:** corpus ingestion (IGIC, IPSI, LAU/CC, TRLGDCU, RGPD, Orden cotización 2026) remains the only lever for H-B2/V22/Cohort B and is outside this package.

---

## 0. Evidence log (chronological discovery record)

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
