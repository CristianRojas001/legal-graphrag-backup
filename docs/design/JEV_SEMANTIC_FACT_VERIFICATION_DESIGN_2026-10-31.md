# LegalGraphRAG — Jev-based semantic verification of conversational facts

**Type:** architecture and implementation design (no code changed, no paid calls made)
**Date:** 2026-10-31
**Target repository:** `CristianRojas001/LegalGraphRag.V2.0`
**Frozen implementation inspected:** `d4304d102af40132660208e35e9aa494f13736ed` (S0–S7)
**Evidence inspected:** `eval/consultation-agent-ea-20261030` @ `ff4c36a8836949356abac1e26990e4f8b8fba64d`, `docs/V3/simplification/live_ea_s1_s7_2026-10-30/` (44 cases, 104 turns, full diagnostics)
**Prior reviews consulted:** `docs/V3/simplification/solution_architecture_review_2026-10-30/*` (FE-1 … FE-4), `docs/evidence/v3/analyzer-acl-jev-rebuild/*` (earlier Jev 1.13 experiments), `backend/apps/legal_graphrag/eval/openrouter_jev_adapter.py`, `services/v3/consultation/link_meaning_check.py`
**Audience:** the owner (decisions) and Claude Sonnet (implementation)

Labels used throughout:

- **[E]** Evidence-backed finding. Each one cites a file, line, or recorded artefact.
- **[P]** Design proposal.
- **[U]** Unverified. It must be checked before anyone relies on it.

---

## 0. Executive summary

1. **[E] There are two opposite failures, and both have the same root cause.** The check `epistemic_es.states_ignorance(user_quote)` asks only whether a quote *contains* a Spanish ignorance phrase. It never asks what that phrase is *about*.
   - **It rejects valid unknowns.** In the E-A run, 18 first-pass `mark_unknown` ops were valid and rejected. 14 of them were never recovered, covering 11 distinct facts that were permanently lost.
   - **It accepts invalid ones.** A bare «No lo sé.» sent after a 3- or 6-question batch was stored as `unknown_by_user` for **every** item: 15 events across EA-B01/B02/B03. That includes facts the client almost certainly knows, such as what the kiln is used for or whether there are minors on the list.
   - Adding more regexes can only shift recall. It cannot fix the missing link between the words and the fact.
2. **[E] A state-machine defect makes rejections expensive.** In `state.py` (`replaced`, around l.548), all unanswered items of the old pending batch are deleted whenever the issue gets a new real result.
   - So a rejected `mark_unknown` leaves the fact neither unknown nor pending.
   - EA-B04 and EA-B05 then could not answer «¿qué datos siguen pendientes?».
   - Jev alone will not fix this. It is a prerequisite change.
3. **[P] Recommended decomposition: one per-fact Jev decision plus one conditional reply-scope decision.** Python keeps all state authority.
   - **D1 `fact_response`** is a 5-way `choice`, asked per *(fact, client message)*: `STATES_VALUE`, `STATES_NOT_KNOWN`, `NOT_ADDRESSED`, `HYPOTHETICAL_ONLY`, `UNCLEAR`.
   - **D2 `general_reply_scope`** is a `noul`. It is asked only when one general statement is being used as evidence for two or more facts.
   - **Correction is not a Jev decision.** Python already knows whether a prior value exists and whether it differs.
   - **"One fact or several" is not a separate decision either.** Asking per fact answers it, and D2 settles the one case per-fact framing cannot (bare general replies).
4. **[P] Two-key rule.** A conversational fact event is written only when DeepSeek *proposes* it **and** Jev *independently* agrees, inside a calibrated acceptance band.
   - Jev never sees DeepSeek's proposed op, quote or value. This follows a lesson the repo already learned: a verdict leak invalidated an earlier Jev comparison (`openrouter_jev_adapter.py`, `_CURRENT_SYSTEM_VERDICT_FIELDS`).
   - Jev can **veto** or **preserve** (keep a question pending). It can never **create** evidence.
5. **[P] Fail-safe.** If Jev is unavailable, times out, returns an invalid shape or serves an uncalibrated snapshot, the system falls back to today's behaviour: the frozen lexicon. The lexicon is kept as a degraded-mode floor and is never expanded again.
6. **[U] The live 1.14 contract was not verified in this session.** `docs.typesafe.ai` and `openrouter.ai` are blocked by this session's network policy.
   - The request/response shape below is the one the repo **verified live on `jev-1.13`** (contract smoke, 2026-09-22).
   - A one-request contract smoke on `typesafe/jev-1.14` is Stage 0 of the plan. It needs your authorization, at roughly €0.001.
   - **Spanish-language accuracy of Jev is unproven.** That is the main risk, and the evaluation in §6 exists to measure it.

---

## 1. Verified root cause and architectural diagnosis

### 1.1 How a `mark_unknown` is judged today [E]

| Step | Code (frozen SHA) | Behaviour |
|---|---|---|
| Lexicon | `agent/epistemic_es.py` (`EPISTEMIC_LEXICON_VERSION='1'`) | 13 accent-folded regexes, such as `no (lo) sé`, `desconozco`, `no recuerdo`, `no estoy seguro`, `no puedo saber`. `states_ignorance(quote)` returns true if any regex matches **the quote**. |
| V8 check | `validator.py` l.1107–1114 | `mark_unknown` gets `UNKNOWN_NOT_STATED` if `not states_ignorance(op.user_quote)`, or if the quote contains another assert/correct quote (G2). |
| Quote check | `validator.py` l.1089–1093 | `QUOTE_NOT_IN_USER_MESSAGES` if the quote is not an exact substring of a user message. |
| Repair | `loop.py` l.355–370 | One repair round. The model receives the violation text: *"Quote only the words where they say so. If the client simply did not answer, leave the fact out; it remains askable."* |
| Finalize | `validator.py` l.1818–1820 | V8 violations are **dropped**. The fact op disappears. |
| State | `state.py` l.408–425, 541–556 | `asked_log` stays `settled=False`. However, old pending items of an issue with any new real, non-`NOT_ADDRESSED` result are removed (`replaced`). |
| Re-ask block | `validator.py` l.1219–1233 | Once a fact is `unknown_by_user`, asking it again is a violation (`UNKNOWN_FACT_REASKED`) unless a later `correct` exists. So a false unknown also silences the question **permanently**. |
| UI | `render.py` l.23–26 | The footer tells clients: *«Puede responder solo a las que sepa; si no conoce algún dato, escriba «no lo sé»…»*. The product itself invites a bare «no lo sé» to a multi-item batch. |

### 1.2 What the E-A run recorded [E]

I extracted these from `raw/ea_run_2/cases/*.json` and `diagnostics/*.json` by reading the first submission in the transcript, `first_report.violations`, the final submission and `state_after`. The extraction scripts are reproducible.

**A. Valid unknowns rejected (recall failures): 18 first-pass `UNKNOWN_NOT_STATED` rejections, 14 never recovered (11 distinct facts), plus 2 related losses at finalize or the quote check**

| Turn | Client words (verbatim) | Proposed key(s) | Fate |
|---|---|---|---|
| EA-B01.02 | «Sigo sin saber qué causó el fallo.» | `causa_fallo_electrico` | Rejected, then removed in the repair round. **Lost.** The client stated it in two turns and it was never stored. |
| EA-B01.00 *(quote check, not lexicon)* | «…ni sé qué causó el fallo» | `causa_fallo_electrico` | DeepSeek paraphrased the quote as «no sé…», which failed `QUOTE_NOT_IN_USER_MESSAGES` and was dropped. **Lost.** |
| EA-B03.00 | «…ni qué texto tenía» (elliptical coordination) | `texto_aviso_privacidad` | **Lost.** |
| EA-B04.01 | «no puedo responder a los demás datos que falten» | 3 keys | **Lost**, and the 3 pending questions were erased as well (see C). |
| EA-B04.02 | (DeepSeek retried using the earlier quote) | 3 keys | Rejected again. **Lost.** |
| EA-B05.00 *(finalize residual)* | «…ni recuerdo cuándo escribí a la tienda» | `fecha_comunicacion_tienda` | Residual `UNKNOWN_NOT_STATED` led to a drop. It was recovered one turn later, when the client repeated it. |
| EA-B05.01 | «…ni puedo responder a los otros datos que falten» | 5 keys | **Lost**, and the questions were erased. |
| EA-B07.01 | «No he comprobado que exista esa cláusula.» | `structural_clause_exists` | **Lost.** The repair then *asked the same fact again* as a clarification item, after the client had said they could not check it. |
| EA-B02.00 / EA-B02.02 | «ni cuándo avisé a la tienda» / «No he podido comprobar esas fechas.» | 4 keys | Recovered only through **quote shopping**: the repair picked a different span that the regex happens to match («…dejar constancia de que no las sé»). |

**B. Invalid unknowns accepted (precision failures): 15 events**

| Turn | Client words | Events written |
|---|---|---|
| EA-B01.01 | «No lo sé.» | `mark_unknown` × 3 (contract clause, location of the fault, notice to landlord) |
| EA-B02.01 | «No lo sé.» | × 6, including `destino_horno`, `vendedor_establecimiento`, `conserva_documentos` |
| EA-B03.01 | «No lo sé.» | × 6, including `naturaleza_juridica`, `hay_menores`, `canal_inscripcion` |

Each of these facts is now blocked from being asked again. G2 does not trigger, because there is no assert quote, and the lexicon matches «No lo sé.». The check cannot tell whether the client's single sentence covers one question or all six.

**C. Lost clarification questions (state defect)**

- EA-B04.01 and EA-B05.01 end with `pending_clarification = null` even though 3 and 5 requested items were never answered.
- Cause: `state.apply` drops `old_items` of any issue in `replaced` (l.541–556), and the repaired submission carried no clarification items.
- The follow-up question «¿Qué datos… siguen sin respuesta?» therefore had nothing in state to answer from. DeepSeek tried `mark_unknown` again (EA-B04.02) and was rejected again.

**D. Epistemic content bypassing the epistemic check**

- **EA-B07.00:** «desconozco qué cláusula regula ese tipo de reparación» was stored as `assert client_knows_clause = false`. That makes ignorance a *known boolean*, and the substantive fact (which clause) is never marked unknown.
- **EA-B03.02:** `correct aviso_privacidad_formulario = false` with the quote «¿Puedes conservarlo como dato desconocido». The client asked to keep the fact unknown, and the system wrote a known `false`. This is real-fact contamination that no current check catches, because assert/correct quotes are never semantically checked.

**E. Hypotheticals (EA-B06/07/08)**

- Structurally correct: overrides went to `scenario_ops.open`, and no real fact event was written.
- In EA-B07.01 the real-world counterpart («No he comprobado…») was lost (row A).
- The existing scenario/override contract is sound. The gap is the real-scope epistemic event next to it.

**F. True negatives the new design must keep**

- **V08.00:** `mark_unknown condicion_destinatario` with the quote «un visitante establecido en Francia». The model was misusing `mark_unknown` to mean "not stated".
- **H-N2.02:** `mark_unknown` quoting a full factual answer.
- The prior review's **P2/H-P3** false «usted ya indicó…».

The current guard correctly rejected all of these. The replacement must preserve that.

### 1.3 Diagnosis [E → P]

| # | Root cause | Consequence |
|---|---|---|
| RC1 | **Lexical recall.** Unknown Spanish forms are rejected: aspectual («sigo sin saber»), elliptical «ni …», ability-based («no puedo responder»), verification-based («no he comprobado»). | Valid unknowns lost; extra clarification rounds. |
| RC2 | **Fact-agnostic check.** The guard evaluates the quote, never the relation *(quote, fact, conversation)*. | One «No lo sé.» becomes N false unknowns, and those questions are silenced permanently. |
| RC3 | **The quote-relative cue can be gamed.** The repair round teaches the model to pick a span the regex likes. | Acceptance depends on span choice, not on meaning. |
| RC4 | **Only `mark_unknown` is checked epistemically.** `assert`/`correct` can encode ignorance or contradict the client's words. | Real-fact contamination (D). |
| RC5 | **State replacement drops unanswered items.** | Lost clarification questions (C). |
| RC6 | **Remediation is drop-only.** There is no "unresolved, keep asking" outcome distinct from "rejected". | Every uncertainty becomes either a silent loss or a forced guess. |

**Where semantic verification belongs:**

- It belongs at the **fact-transition boundary**, between DeepSeek's proposed `fact_ops` and `state.apply`.
- Concretely, it goes inside the `validate_fn` closure in `turn_manager.py`, and its verdicts are passed into the deterministic `_Checks`. It must not sit inside the regex helper.
- The validator stays a pure function of its inputs: submission, state, messages, **verdicts**. It is testable with fixture verdicts and needs no network.

---

## 2. Recommended Jev decision design

### 2.1 Division of responsibility [P]

| Actor | Owns | Must not |
|---|---|---|
| **DeepSeek (agent)** | Interpreting the conversation. Proposing `fact_ops` (key, value, quote, issue_refs), `scenario_ops`, and results. Supplying a neutral question for a fact that was never asked (`fact_question_es`, new and optional). | Write state. Its proposal is a claim, not evidence. |
| **Jev (verifier)** | An independent, closed-choice semantic judgement of what the client's **verbatim message** says about **one named fact**, in context. Also the scope of general replies. | See DeepSeek's op type, quote or value. Create events. Choose fact keys. Decide legal relevance. |
| **Python (validator + state)** | Structure: schemas, key format, verbatim-quote provenance, quote/turn binding. The acceptance policy (bands). Two-key reconciliation. Correction detection (prior value exists and differs). Hypothetical isolation (override vs real). Pending-batch lifecycle. Degraded mode. Telemetry. | Interpret Spanish meaning. That covers the lexicon after the migration, except as the degraded floor. |

### 2.2 Why this decomposition, and not the initial four categories [P]

| Proposed category | Treatment | Reason |
|---|---|---|
| Supplied / uncertain / unanswered / ambiguous | **D1**, one choice | Mutually exclusive answers to one question. A single distribution gives probabilities that sum to 1, so Python can use top-1 margin. Separate yes/no questions would give inconsistent probabilities and need extra combination rules. |
| Real vs hypothetical | **Folded into D1** (`HYPOTHETICAL_ONLY`, plus a priority rule) | What matters is "what does the message say about the *real* value of this fact". A separate real/hypothetical question would be asked of the whole message, which mixes facts. In the cortocircuito example the cause is unknown in reality *and* hypothesised, and only a per-fact framing gives both answers correctly. |
| Correction | **Python** | "Is there a prior known value and does the new value differ?" is fully determined by state (`current_facts`). Jev only has to confirm the client *states a real value* (`STATES_VALUE`). |
| One fact vs several | **Per-fact framing, plus D2 when needed** | Asking each fact separately means the "which facts" question never needs answering as such. The one irreducibly cross-fact case is a single general statement used for several facts, and D2 targets exactly that. |

Two decisions cover all observed failures (§1.2 A–E) and the stated objectives. The extra decision I considered was **D3, value entailment** ("does the message state value V?"). I do not recommend it now. D1 already catches the contamination observed (EA-B03.02 is `STATES_NOT_KNOWN`, not `STATES_VALUE`), and value checks belong to the separate FE-2 value-domain work.

### 2.3 When Jev is called (deterministic triggers) [P]

Build the set **R** of D1 records for the turn from three sources, deduplicated by `(fact_key, message_turn)`:

1. Every `mark_unknown` op in the submission, paired with the client message of its `quote_turn`.
2. Every `assert`/`correct` op with `scope=real`, paired with its `quote_turn` message. **Phase 1 is shadow-only for these.** See §5.3.
3. Every item in `pending_clarification.items` that the current turn could be answering, paired with the **current** message, even when DeepSeek proposed no op for it.
   - This turns "DeepSeek forgot it" into a measurable disagreement instead of a silent loss.
   - It never creates an event.

D2 is called once per *(message, evidence span)* when **two or more** `mark_unknown` ops share the same quote, or overlapping quotes, from the same `quote_turn`. This trigger is structural: it compares strings, with no language rules.

Typical cost per turn is 1 HTTP request: all D1 questions plus at most one D2, over one shared state. §4.4 explains why per-record requests are kept as a measured alternative.

---

## 3. Exact reusable Jev questions and API examples

### 3.1 Wire contract (as verified on `jev-1.13`) [E] / [U for 1.14]

Confirmed live by the repo on `typesafe/jev-1.13` (`openrouter_jev_adapter.py`, notes dated 2026-09-22 and 2026-09-26; `link_meaning_check.py`):

- `POST https://openrouter.ai/api/alpha/decisions` with `Authorization: Bearer $OPENROUTER_API_KEY`.
- Body: `{"model": "<id>", "state": {...}, "questions": {"<key>": {"type": "noul"|"choice", "instructions": "<text>", "criteria": {<answer>: <text>}}}}`.
- `criteria` must be an **object** keyed by the answer values. A string is rejected with `invalid_type`.
  - `noul` keys are `"true"` and `"false"`.
  - `choice` keys are the exact option labels.
- Response: `{"model": "...", "provider": "...", "answers": {"<key>": {...}}, "usage": {...}}`.
  - Noul: `{"type": "noul", "noul": <float>}`.
  - Choice: `{"choice": "<LABEL>", "confidence": <float>, "probabilities": {"<LABEL>": <float>, ...}}`.
- The response `model` is a **dated snapshot**, for example `typesafe/jev-1.13-20260917`. The repo accepts only the pinned id or `<pinned>-YYYYMMDD` (`link_meaning_check.model_identity_ok`).
- Operational precedent: at most **8 records** and **28,000 bytes** per request (`link_meaning_check.MAX_RECORDS_PER_REQUEST`, `MAX_REQUEST_BYTES`).

From public search results for `jev-1.14`, not first-hand:

- Released 2026-10-14. A dated page `typesafe/jev-1.14-20261014` exists.
- Context of 262,144 tokens.
- About $0.042 per million input tokens, with no output charge.
- A separate `/api/v1/systemone` path exists for TypeSafe SDK users.
- A third-party note says requests above 32 KiB switch to a long-context mode.

**[U] Stage 0 must confirm on 1.14:**

1. The response shape is unchanged, including `probabilities` for `choice`.
2. Whether a dated id can be **requested** directly, rather than only reported.
3. Behaviour above 32 KiB.
4. The maximum number of questions per request.
5. Error envelopes.

This report does **not** cover the separate *Jev Router* product. Nothing here routes between models.

### 3.2 Language of instructions [P]

- Instructions and criteria are in **English**, matching every Jev integration already in the repo.
- The state carries the **verbatim Spanish** text.
- The evaluation (§6) includes a Spanish-instruction arm. If it wins on the held-out set, switch to it. The question text is versioned (`question_version`) so the switch is a config change.

### 3.3 D1 — `fact_response` (choice)

**Question key:** `<record_key>__fact_response`, where `record_key = "f" + sha256(fact_key|message_turn)[:10]`. The key is opaque, so field names do not leak semantics.

**Instructions** (version `fact_response/1`):

> For record {record_key}: The state contains a legal consultation between a client and an assistant. Read `records.{record_key}.client_message`, the client's own words. Decide what those words say about the client's REAL situation regarding the single question in `records.{record_key}.target_question`. Use `conversation.previous_assistant_message` and `conversation.open_questions` only to understand what the client is replying to; the assistant's words are never evidence of what the client knows or states. Judge meaning, not wording: the client may use any phrasing, register, regional variant, spelling errors or missing accents. If the client says they do not know the real answer AND poses a supposition about it, choose STATES_NOT_KNOWN. If the client gives a real answer AND a supposition, choose STATES_VALUE. Choose exactly one option.

**Criteria:**

| Answer | Criterion text (sent verbatim) | Meaning for Python |
|---|---|---|
| `STATES_VALUE` | "The client affirms an answer to the target question as true of their real situation. This includes yes/no answers, approximate answers, partial answers and corrections of something they said earlier." | The client supplied a real value. It supports `assert`/`correct`. It **contradicts** `mark_unknown`. |
| `STATES_NOT_KNOWN` | "The client says, in any wording, that they do not know, do not remember, have not been able to check or verify, or cannot provide the answer to the target question for their real situation. The statement must concern this target question: it names or clearly refers to it, or it is a general statement that, in context, plainly covers every open question the client has not otherwise answered." | The client explicitly lacks the fact. It supports `mark_unknown`. |
| `NOT_ADDRESSED` | "The client's words say nothing about the target question: they answer other questions, ask something else, or change the subject." | Unanswered. The item stays askable or pending. |
| `HYPOTHETICAL_ONLY` | "The client mentions an answer to the target question only as a supposition, hypothesis, example or condition (for instance 'si fuera…', 'supón que…', 'imagina que…', 'en el caso de que…'), and does not state the real answer or that they do not know it." | Allowed only as a scenario override. Never a real event. |
| `UNCLEAR` | "The client's words concern the target question but it cannot be determined which option applies: the reply might refer to a different question, is self-contradictory, or is too vague to classify." | Abstain. Keep pending, and possibly confirm. |

The criteria contain a few Spanish *examples*. That is deliberate. They are illustrations of a category, not a closed list, and the instructions explicitly say to judge meaning. The evaluation tests forms that are not among the examples.

**Record state** (per D1 record):

```json
{
  "target_question": "¿Sabe qué causó el fallo de la instalación eléctrica?",
  "answer_shape": "text",
  "choices": [],
  "client_message_turn": 3,
  "client_message": "Sigo sin saber qué causó el fallo. ¿Puedes mantener ese dato como desconocido e indicarme qué documento podría consultar?"
}
```

- `target_question` source, in priority order:
  1. the `question_es` of the pending or most recently asked `ClarificationItemV1` for that key;
  2. the condition text in `last_results` that references the key;
  3. DeepSeek's `fact_question_es` on the op. This is new, and is the only DeepSeek-authored field Jev sees. It describes the *question*, never the answer.
- Never sent: `fact_key` (it is English or Spanish snake_case with potential bias, such as `client_knows_clause`), DeepSeek's `op`, `user_quote`, `value`, `display_es`, issue titles and legal text.

**Shared conversation state** (one per request):

```json
{
  "previous_assistant_message": "<verbatim last assistant message before client_message, truncated to 6,000 chars from the end>",
  "open_questions": [
    {"n": 1, "question": "¿Su contrato contiene alguna cláusula sobre quién asume las reparaciones…?"},
    {"n": 2, "question": "El fallo, ¿afecta solo a la instalación interna de su local o también a un elemento común?"},
    {"n": 3, "question": "¿Ha comunicado ya la avería al arrendador?"}
  ]
}
```

- `open_questions` holds the `question_es` of the pending items **as rendered to the client**, in render order. These are the "listed questions" the client is replying to.
- **Record `client_message` per record**, not once. Records in one request may come from different `quote_turn`s.

### 3.4 D2 — `general_reply_scope` (noul)

**Question key:** `<scope_key>__general_reply_scope`, with `scope_key = "s" + sha256(message_turn|span)[:10]`.

**Instructions** (version `general_reply_scope/1`):

> For record {scope_key}: `records.{scope_key}.client_message` is the client's reply to the numbered questions in `conversation.open_questions`. Decide whether the client's message contains a general statement of not knowing, not remembering, or not being able to answer that — read in context — is meant to cover EVERY listed question that the message does not answer specifically. Judge the client's words only; the assistant's invitation to reply «no lo sé» is not evidence of what the client meant.

**Criteria:**

```json
{
  "true":  "The general statement plainly covers every listed question the client did not answer specifically (for example it refers to 'the rest', 'the others', 'none of them', 'any of that', or there was only one open question).",
  "false": "The statement may refer to only one or some of the questions, it is unclear which questions it refers to, or there is no general statement."
}
```

**Record state:**

```json
{"client_message_turn": 2, "client_message": "No lo sé."}
```

**Effect:**

- When D2 ≥ τ₂, every broadcast `mark_unknown` whose D1 is `STATES_NOT_KNOWN` is accepted.
- Otherwise none of the broadcast ops is accepted, the items stay pending, and the turn requests a confirmation (§5.4).

### 3.5 Full request example (EA-B04 reply, one request) [P]

```json
{
  "model": "typesafe/jev-1.14",
  "state": {
    "conversation": {
      "previous_assistant_message": "…Para continuar necesito los siguientes datos:\n1. ¿Qué establece su contrato sobre el mantenimiento de las instalaciones fijas?\n2. ¿Sabe qué causó la avería?\n3. ¿Ha comunicado la avería al arrendador?\n4. ¿Quién asumía antes las reparaciones de este tipo?\n5. ¿A qué destina el taller?\nPuede responder solo a las que sepa; si no conoce algún dato, escriba «no lo sé» y lo trataré como desconocido.",
      "open_questions": [
        {"n": 1, "question": "¿Qué establece su contrato sobre el mantenimiento de las instalaciones fijas?"},
        {"n": 2, "question": "¿Sabe qué causó la avería?"},
        {"n": 3, "question": "¿Ha comunicado la avería al arrendador?"},
        {"n": 4, "question": "¿Quién asumía antes las reparaciones de este tipo?"},
        {"n": 5, "question": "¿A qué destina el taller?"}
      ]
    },
    "records": {
      "f3a91c0d2e7": {"target_question": "¿Qué establece su contrato sobre el mantenimiento de las instalaciones fijas?", "answer_shape": "text", "choices": [], "client_message_turn": 2,
                      "client_message": "El contrato atribuye al arrendatario el mantenimiento ordinario de las instalaciones; no sé qué causó esta avería y no puedo responder a los demás datos que falten."},
      "f0b2d99e1a4": {"target_question": "¿Sabe qué causó la avería?", "answer_shape": "text", "choices": [], "client_message_turn": 2,
                      "client_message": "El contrato atribuye al arrendatario el mantenimiento ordinario de las instalaciones; no sé qué causó esta avería y no puedo responder a los demás datos que falten."},
      "f77c1e0b5d2": {"target_question": "¿Ha comunicado la avería al arrendador?", "answer_shape": "yes_no", "choices": [], "client_message_turn": 2,
                      "client_message": "El contrato atribuye al arrendatario el mantenimiento ordinario de las instalaciones; no sé qué causó esta avería y no puedo responder a los demás datos que falten."},
      "s5e0aa13c9f": {"client_message_turn": 2,
                      "client_message": "El contrato atribuye al arrendatario el mantenimiento ordinario de las instalaciones; no sé qué causó esta avería y no puedo responder a los demás datos que falten."}
    }
  },
  "questions": {
    "f3a91c0d2e7__fact_response": {
      "type": "choice",
      "instructions": "For record f3a91c0d2e7: The state contains a legal consultation between a client and an assistant. Read `records.f3a91c0d2e7.client_message`, the client's own words. Decide what those words say about the client's REAL situation regarding the single question in `records.f3a91c0d2e7.target_question`. Use `conversation.previous_assistant_message` and `conversation.open_questions` only to understand what the client is replying to; the assistant's words are never evidence of what the client knows or states. Judge meaning, not wording: the client may use any phrasing, register, regional variant, spelling errors or missing accents. If the client says they do not know the real answer AND poses a supposition about it, choose STATES_NOT_KNOWN. If the client gives a real answer AND a supposition, choose STATES_VALUE. Choose exactly one option.",
      "criteria": {
        "STATES_VALUE": "The client affirms an answer to the target question as true of their real situation. This includes yes/no answers, approximate answers, partial answers and corrections of something they said earlier.",
        "STATES_NOT_KNOWN": "The client says, in any wording, that they do not know, do not remember, have not been able to check or verify, or cannot provide the answer to the target question for their real situation. The statement must concern this target question: it names or clearly refers to it, or it is a general statement that, in context, plainly covers every open question the client has not otherwise answered.",
        "NOT_ADDRESSED": "The client's words say nothing about the target question: they answer other questions, ask something else, or change the subject.",
        "HYPOTHETICAL_ONLY": "The client mentions an answer to the target question only as a supposition, hypothesis, example or condition (for instance 'si fuera…', 'supón que…', 'imagina que…', 'en el caso de que…'), and does not state the real answer or that they do not know it.",
        "UNCLEAR": "The client's words concern the target question but it cannot be determined which option applies: the reply might refer to a different question, is self-contradictory, or is too vague to classify."
      }
    },
    "f0b2d99e1a4__fact_response": {"type": "choice", "instructions": "For record f0b2d99e1a4: …(identical text, record key substituted)…", "criteria": {"…": "identical to above"}},
    "f77c1e0b5d2__fact_response": {"type": "choice", "instructions": "For record f77c1e0b5d2: …", "criteria": {"…": "identical"}},
    "s5e0aa13c9f__general_reply_scope": {
      "type": "noul",
      "instructions": "For record s5e0aa13c9f: `records.s5e0aa13c9f.client_message` is the client's reply to the numbered questions in `conversation.open_questions`. Decide whether the client's message contains a general statement of not knowing, not remembering, or not being able to answer that — read in context — is meant to cover EVERY listed question that the message does not answer specifically. Judge the client's words only; the assistant's invitation to reply «no lo sé» is not evidence of what the client meant.",
      "criteria": {
        "true": "The general statement plainly covers every listed question the client did not answer specifically (for example it refers to 'the rest', 'the others', 'none of them', 'any of that', or there was only one open question).",
        "false": "The statement may refer to only one or some of the questions, it is unclear which questions it refers to, or there is no general statement."
      }
    }
  }
}
```

The `…` placeholders stand for the identical text. The implementation generates them from one constant. Records 4 and 5 are omitted for brevity.

**Expected labels (gold):**

| Record | Expected |
|---|---|
| Q1 | `STATES_VALUE` |
| Q2 | `STATES_NOT_KNOWN` (specific) |
| Q3–Q5 | `STATES_NOT_KNOWN` (via the general statement) |
| D2 | `true` |

**Expected response shape** (as on 1.13; [U] for 1.14):

```json
{
  "model": "typesafe/jev-1.14-20261014",
  "provider": "Typesafe",
  "answers": {
    "f3a91c0d2e7__fact_response": {"choice": "STATES_VALUE", "confidence": 0.93, "probabilities": {"STATES_VALUE": 0.93, "STATES_NOT_KNOWN": 0.03, "NOT_ADDRESSED": 0.02, "UNCLEAR": 0.02, "HYPOTHETICAL_ONLY": 0.0}},
    "s5e0aa13c9f__general_reply_scope": {"type": "noul", "noul": 0.91}
  },
  "usage": {"input_tokens": 0, "output_tokens": 0, "cost": 0}
}
```

The numbers are illustrative only. No call was made.

### 3.6 The hypothetical example [P]

Client: «No sé qué causó la avería, pero si fue un cortocircuito, ¿quién paga?»

**Correct DeepSeek proposal:**

- `mark_unknown causa_averia`, quote «No sé qué causó la avería».
- `scenario_ops.open` with `overrides: {causa_averia: {type: "text", value: "cortocircuito", …}}`.

**D1** for `causa_averia` returns `STATES_NOT_KNOWN`, by the priority rule.

**Outcomes:**

- The real event is `unknown_by_user`, and the scenario carries the override. Nothing is contaminated.
- If DeepSeek wrongly proposes `assert causa_averia = cortocircuito` as a real fact, then D1 is not `STATES_VALUE`, so the assert is vetoed (§5.3). The deterministic guard also fires: the asserted real value equals a same-turn override for the same key.

---

## 4. Input/output data contracts

All new models are pydantic `ContractModel` in `agent/contracts.py`. Every field is optional or defaulted, so `consultation_agent_state/1` and `submission/1` stay readable. **There is no schema version bump for persisted state.** The additions are optional fields.

### 4.1 DeepSeek → validator (submission) [P]

```python
class FactOpV1(ContractModel):          # existing, plus one optional field
    op: Literal["assert", "correct", "mark_unknown", "retract"]
    fact_key: str
    value: FactValueV1 | None = None
    user_quote: str
    issue_refs: list[str] = []
    fact_question_es: str | None = Field(None, max_length=200)   # NEW: neutral question for the fact, no answer in it
```

V8 `OUTCOME_SHAPE` applies when `op=="mark_unknown"`, the key has no pending, asked or `last_results` question text, and `fact_question_es` is empty.

### 4.2 Verifier input (built by Python, never by DeepSeek) [P]

```python
class FactCheckRecordV1(ContractModel):
    record_key: str                      # opaque hash
    fact_key: str                        # NOT sent to Jev
    origin: Literal["mark_unknown_op", "real_assert_op", "pending_item"]
    target_question_es: str
    question_source: Literal["pending_item", "asked_item", "last_result_condition", "fact_op"]
    answer_shape: str
    choices: list[str] = []
    message_turn: int
    message_sha256: str                  # binds the verdict to the exact text judged
class ScopeCheckRecordV1(ContractModel):
    record_key: str
    message_turn: int
    message_sha256: str
    span: str                            # the shared DeepSeek quote that triggered D2 (NOT sent to Jev)
    fact_keys: list[str]
```

### 4.3 Verifier output → validator [P]

```python
Choice = Literal["STATES_VALUE", "STATES_NOT_KNOWN", "NOT_ADDRESSED", "HYPOTHETICAL_ONLY", "UNCLEAR"]
class FactDecisionV1(ContractModel):
    record_key: str
    fact_key: str
    message_turn: int
    message_sha256: str
    status: Literal["ok", "failed"]
    failure_code: str | None = None      # closed codes: timeout, http_4xx, http_5xx, shape, model_identity, snapshot_uncalibrated, budget_denied, missing_answer
    choice: Choice | None = None
    probabilities: dict[str, float] = {}
    band: Literal["accept", "reject", "abstain"] | None = None   # computed by Python policy, not by Jev
    question_version: str                # "fact_response/1"
    model_snapshot: str | None = None    # e.g. typesafe/jev-1.14-20261014
class ScopeDecisionV1(ContractModel):
    record_key: str
    message_turn: int
    message_sha256: str
    status: Literal["ok", "failed"]
    failure_code: str | None = None
    noul: float | None = None
    band: Literal["accept", "reject", "abstain"] | None = None
    question_version: str                # "general_reply_scope/1"
    model_snapshot: str | None = None
class FactVerdictsV1(ContractModel):
    schema_: Literal["fact_verdicts/1"] = Field("fact_verdicts/1", alias="schema")
    mode: Literal["off", "shadow", "enforce", "degraded"]
    policy_version: str                  # thresholds file version
    facts: list[FactDecisionV1] = []
    scopes: list[ScopeDecisionV1] = []
    requests: int = 0
    latency_ms: int = 0
    cost_eur: float = 0.0
```

### 4.4 Validator → state (persisted provenance) [P]

```python
class FactVerificationV1(ContractModel):
    method: Literal["jev", "lexicon_degraded", "legacy"]   # legacy = events written before this change
    decision: str | None = None          # D1 choice
    p: float | None = None               # probability of the accepted choice
    scope_noul: float | None = None
    record_key: str | None = None        # joins to diagnostic artefact
    question_version: str | None = None
    model_snapshot: str | None = None
    policy_version: str | None = None
class FactEventV1(ContractModel):        # existing, plus one optional field
    ...
    verification: FactVerificationV1 | None = None   # NEW; required (by V8) for new mark_unknown events in enforce mode
```

**Integrity invariants enforced by Python [P]:**

- **I1.** `user_quote` is a verbatim substring of the client message at `quote_turn`. The existing check is kept, plus deterministic alignment (§5.6).
- **I2.** A verdict is used only if its `message_sha256` equals the hash of the message that holds the quote. A verdict about one message cannot validate a quote from another.
- **I3.** No event is created without a DeepSeek op (the two-key rule). A pending item with a `STATES_NOT_KNOWN` verdict but no op stays pending and is counted as `verifier_only_unknown`.
- **I4.** An accepted `unknown_by_user` from a broadcast span requires D2 in band `accept`.
- **I5.** A real `assert`/`correct` must not equal a scenario override opened in the same submission for the same key (deterministic, language-free).
- **I6.** `correct` vs `assert` is decided only by state: a prior known value exists and its identity differs (existing `_fact_identity`).

### 4.5 Distinguishing the five epistemic situations [P]

| Situation | Stored as | Source of truth |
|---|---|---|
| Explicitly unknown to the user | `FactEventV1 op=mark_unknown`, `verification.method=jev`, `decision=STATES_NOT_KNOWN` | DeepSeek op + D1 accept (+ D2 accept if broadcast) |
| Not answered | **No event.** Item remains in `pending_clarification` (carry-forward fix) and `asked_log.settled=False` | Absence of an accepted op |
| Ambiguous answer | No event. Item remains pending, plus a confirmation request (§5.4). Telemetry records `abstain` | D1 `UNCLEAR`/abstain, or D2 not accept |
| Hypothetical | `ScenarioV1.overrides[fact_key]` only. **Never** a real event | `scenario_ops` + I5 + D1 veto |
| Corrected | `FactEventV1 op=correct`, `supersedes_event_id` set | Python I6 + D1 `STATES_VALUE` (shadow first) |

---

## 5. Confidence, ambiguity and failure-handling policies

### 5.1 Bands, not raw confidence [P]

- Prior repo evidence [E] (`jev-condition-batching-experiment-v32-20260928/owner-review.md`): Jev 1.13 answers near 0.5 **flipped across identical repeats**, for example condition 2 `SATISFIED` 0.52 versus `MISSING_USER_FACT` 0.59.
- **Batching changed the probabilities materially.** For condition 3, `LEGAL_EVIDENCE` was 0.41 unbatched and `NONE` 0.95 batched.
- Therefore confidence is **not** correctness, and thresholds must be calibrated in the exact request configuration used in production.

**Policy** (values are *placeholders until calibration*, kept in `agent/epistemic_policy_v1.json`):

| Decision | `accept` band | `reject` band | Otherwise |
|---|---|---|---|
| D1 for a `mark_unknown` op | `choice==STATES_NOT_KNOWN` **and** p ≥ 0.85 **and** p − p₂ ≥ 0.40 | `choice ∈ {STATES_VALUE, NOT_ADDRESSED, HYPOTHETICAL_ONLY}` with p ≥ 0.70 | `abstain` |
| D2 | noul ≥ 0.85 | noul ≤ 0.30 | `abstain` |
| D1 veto of a real `assert`/`correct` (Phase 2) | n/a | `choice ∈ {STATES_NOT_KNOWN, HYPOTHETICAL_ONLY}` with p ≥ 0.85 | no veto |

`p₂` is the second-highest probability.

**Asymmetry is deliberate:**

- A false `unknown_by_user` silences a decisive question permanently. Given `UNKNOWN_FACT_REASKED`, it cannot even be re-asked without a correction.
- A missed unknown costs one more question.
- So acceptance is strict and abstention is cheap.

**Calibration rule:** choose the smallest accept threshold whose **lower 95 % Wilson bound** on precision is ≥ 0.97 on the dev split. Then confirm it on the held-out split.

### 5.2 Reconciliation table for `mark_unknown` [P]

| DeepSeek op | D1 band | D2 (if broadcast) | Outcome | V8 code | Item |
|---|---|---|---|---|---|
| `mark_unknown` (specific span) | accept | — | Event written | — | settled |
| `mark_unknown` (broadcast span) | accept | accept | Event written | — | settled |
| `mark_unknown` (broadcast span) | accept | reject / abstain | Not written | `UNKNOWN_SCOPE_UNCLEAR` (new) | pending + confirmation |
| `mark_unknown` | reject | — | Not written | `UNKNOWN_NOT_STATED` (existing) | pending |
| `mark_unknown` | abstain or `UNCLEAR` | — | Not written | `UNKNOWN_UNVERIFIED` (new) | pending |
| none | D1 says `STATES_NOT_KNOWN` | — | No event (I3) | — (telemetry only) | pending |
| any | verifier failed | — | Degraded: frozen lexicon G1+G2 (today's behaviour) | as today | pending if rejected |

**Repair interaction:**

- Jev runs inside the first `validate_fn` call. Its V8 codes join the existing first report, so they are fixed in the repair round **that already happens in 66/104 turns**.
- Semantic codes alone do **not** start a repair round. They are applied in `finalize` as drop-and-keep-pending, to avoid adding about 30–90 s of DeepSeek latency.
- The second validation reuses cached verdicts, keyed by `(question_version, message_sha256, target_question_es)`. New ops in the repair get new D1 calls.
- The repair message for `UNKNOWN_UNVERIFIED` and `UNKNOWN_SCOPE_UNCLEAR` tells DeepSeek to leave the fact out and keep its question. It must **not** suggest picking a different quote, which is what produced the quote shopping in RC3.

### 5.3 Real `assert`/`correct` (hypothetical contamination) [P]

- **Phase 1 (enforce):** I5 only. It is deterministic.
- **Phase 1 (shadow):** D1 on real asserts is computed and logged as `assert_verdict_disagreements`.
- **Phase 2:** veto is enabled only in the bands where the held-out precision of `HYPOTHETICAL_ONLY` and `STATES_NOT_KNOWN` meets §6.4.
  - A vetoed assert becomes code `REAL_FACT_NOT_STATED` and is dropped.
  - Its pending item stays.

### 5.4 Ambiguity handling in the conversation [P]

- When any `UNKNOWN_SCOPE_UNCLEAR` exists, the renderer appends one line built from state, with no LLM text: «¿Su respuesta «{quote}» se refiere a todas las preguntas pendientes o solo a alguna? Indique cuáles no sabe.»
- The items remain pending, so the next turn reconciles them normally.
- This reuses the existing confirmation-prompt idea (`render.CONFIRMATION_PROMPT`) without needing the `confirm_target` contract.
- **Recommendation, an owner decision (OQ-3):** change the footer to *«…si no conoce algún dato, indique cuál (p. ej., «el 2 no lo sé»)»*. The current wording invites the ambiguity.

### 5.5 Failure handling, availability and cost [P]

| Condition | Behaviour | Telemetry code |
|---|---|---|
| `AGENT_EPISTEMIC_VERIFIER=off` | Lexicon (today) | `mode=off` |
| Timeout (hard 6 s, one retry for 5xx/timeout only if time remains in `wall_clock_s`) | Degraded lexicon for that turn | `timeout` |
| Non-2xx / unparsable / missing answer for a key | Degraded **for the affected records only** | `http_4xx`, `http_5xx`, `shape`, `missing_answer` |
| Response model is not the pinned id or `<id>-YYYYMMDD` | Reject all answers; degraded | `model_identity` |
| Valid snapshot ≠ the snapshot the policy was calibrated on (`policy.calibrated_snapshot`) | **Shadow** for that turn (compute, do not enforce) plus an alert | `snapshot_uncalibrated` |
| Ledger admission denied | Degraded | `budget_denied` |

Supporting figures:

- **Latency [E]:** recorded Jev 1.13 calls in `docs/evidence/v3/**` had a median of 454 ms, a p95 of 1.35 s and a max of 275 s across 33,540 rows. That tail is why there is a hard timeout and a degraded path.
- **Cost [E/U]:** at about $0.042 per million input tokens and roughly 2–6k tokens per request, this is about €0.0003 per turn. That is negligible against the €0.022 average DeepSeek turn in E-A.
- **Model pinning:** request `typesafe/jev-1.14`, or the dated id if Stage 0 shows it can be requested. Never use `~typesafe/jev-latest`. A new snapshot means recalibrating before enforcing.
- **Privacy:**
  - Client messages and assistant questions are sent to TypeSafe via OpenRouter. That is a **new subprocessor** next to DeepSeek; OQ-5 is to confirm OpenRouter's data policy and zero-data-retention option for this endpoint.
  - Send only the minimum: the current and quoted client messages, the last assistant message, and the question texts. No issue titles, legal text, or other session data.
  - Telemetry carries ids, hashes, counts, closed codes and timings only. Full request and response bodies go only to the restricted diagnostic artefact (`V3_CONSULTATION_DIAGNOSTIC_DIR`, mode 0600), per the RAG telemetry rule in `CLAUDE.md`.

### 5.6 Deterministic quote alignment (language-free) [P]

EA-B01.00 and EA-B05.01 failed `QUOTE_NOT_IN_USER_MESSAGES` because DeepSeek normalised «ni» to «no».

**Proposal:** if a quote is not verbatim, search the `quote_turn` message for the window with the highest `difflib.SequenceMatcher` ratio, keeping length within ±20 %.

- If the ratio is ≥ 0.90 and the window is unique, replace the quote with the verbatim window and record the normalisation residual `QUOTE_ALIGNED`.
- Otherwise the existing violation stands.

This involves no Spanish rules and never invents text: the stored quote is always the client's exact words.

### 5.7 Suitability of Jev for this task [E/P]

**For:**

- The task is exactly what Jev is for: closed, typed choices with probabilities over a supplied state. That holds both from public descriptions and from the repo's use.
- It is cheap, fast at the median, already integrated twice in the repo (eval adapter, `link_meaning_check`), and gives a distribution, which supports abstention.

**Against / unknown:**

- **[U] Spanish pragmatic accuracy.** This covers ellipsis («ni …»), aspect («sigo sin»), ability vs knowledge («no puedo responder»), and colloquial forms («ni idea», «vete a saber», «y yo qué sé»). None of the repo's prior Jev experiments measured conversational Spanish classification. They measured legal-text relevance and support.
- **[E] Run-to-run instability** near the decision boundary, and **sensitivity to batching** (§5.1).
- **[U] Long-context mode** above 32 KiB may change behaviour. Keep the state well below it: truncate the assistant message and cap 8 records per request, per the existing precedent.

**Verdict:** suitable as a **verifier inside a two-key, abstaining policy**. Not suitable as a sole source of truth. Adopt only if §6.4 passes.

---

## 6. Evaluation and acceptance criteria

The evaluation separates three layers so semantic accuracy is never confused with state correctness. **No paid call is run without authorization.** Layers A2 and C need it.

### 6.1 Layer A — semantic classification (Jev only)

**Dataset construction (zero cost):**

1. **Mined from E-A.** For every turn in 44 cases that follows an assistant message with pending items, create one record per (pending item × client message), plus one per DeepSeek fact op. That gives about 250–350 records. It includes all of §1.2 A, B, D and F.
2. **Adversarial and unseen.** At least 200 records, written by a Spanish speaker *before* any Jev run, covering:
   - **Not-known paraphrases not in the lexicon or the criteria:** «ni idea», «ni la más remota idea», «vete a saber», «¿y yo qué sé?», «se me ha olvidado», «no caigo», «a saber», «no me consta», «eso lo lleva mi gestor, yo no lo sé», «no lo tengo controlado», «no sabría decirle», misspellings («nose», «nolose», «no se» without accent), Latin American and Peninsular variants.
   - **Negation traps (not unknown):** «no se ha pagado» (reflexive, a value), «no sé por qué la tienda no contesta» (different topic), «no sé lo que es la base imponible» (legal-term ignorance), «no es que no lo sepa, prefiero no decirlo» (declines; OQ-1), «no estoy seguro, pero creo que fue en marzo» (hedged value).
   - **Multi-question replies:** bare «No lo sé.» after 1, 3 and 6 questions; «la 2 no la sé»; «lo del contrato no lo sé, lo demás: …»; «ninguna de esas»; «no sé nada de eso»; partial plus «lo demás no».
   - **Hypotheticals:** «si fuera…», «supón que…», «pongamos que…», «en el caso de que…», «imagina…», with and without a stated real value, and with real unknown plus hypothesis (the cortocircuito example).
   - **Corrections:** «perdón, fue en abril, no en marzo», «ya no estoy seguro de lo que dije» (should be `UNCLEAR`, not a value).
   - **Long conversations:** a fact answered three turns earlier, then «como le dije, no lo sé» in a later turn.
   - **Prior false positives:** V08, H-N2.02, H-P3 «usted ya indicó…».
3. **Labelling.**
   - Two independent Spanish-speaking annotators assign the D1 label (and the D2 label where applicable), following a written guideline containing the criteria texts.
   - Report Cohen's κ, adjudicate disagreements, then freeze and hash the labels **before** the first Jev run. This is the pre-registration practice already used in `live_ea_s1_s7_2026-10-30/`.
4. **Splits.** Mined records are split 40 % dev (calibration) and 60 % test. The adversarial set is held out entirely.

**Arms** (A2 is paid, about 1,500 calls × 3 repeats ≈ < €0.10):

| Arm | Description |
|---|---|
| L | Frozen lexicon (baseline, zero cost; computable offline now: A1) |
| DS | DeepSeek's recorded op (baseline from E-A artefacts; zero cost) |
| J-batch | D1/D2 per turn in one request (production candidate) |
| J-single | One record per request |
| J-es | J-batch with Spanish instructions and criteria |

**Metrics:**

- Per-class precision and recall with a confusion matrix.
- **Precision of `STATES_NOT_KNOWN` in the accept band**, as the critical metric.
- Recall of `STATES_NOT_KNOWN` against arm L.
- `HYPOTHETICAL_ONLY` → `STATES_VALUE` errors.
- Abstention rate.
- Flip rate across 3 repeats inside the accept band.
- Reliability diagram per band.
- A McNemar test against L on the not-known class.

### 6.2 Layer B — application to conversation state (deterministic, zero cost)

- Replay the recorded E-A DeepSeek submissions, from the diagnostics `transcript` submit calls, through `validator.finalize` and `state.apply` with **injected** verdicts:
  - (i) gold labels as an oracle, which isolates state logic;
  - (ii) recorded Jev verdicts from A2;
  - (iii) all-failed verdicts, which tests the degraded path.
- This extends the existing `tests/v3/agent/test_replay_loop_turn.py` style.
- Invariants checked per turn:
  - **B-1:** zero `unknown_by_user` events whose gold label ≠ `STATES_NOT_KNOWN`.
  - **B-2:** zero lost questions. Every `asked_log` item with `settled=False` is in `pending_clarification.items` or `deferred`, or the issue was explicitly re-scoped with a recorded reason.
  - **B-3:** zero real fact events equal to a same-turn override (I5).
  - **B-4:** every new `mark_unknown` event carries `verification` with a matching `message_sha256`.
  - **B-5:** the degraded path reproduces today's results byte-for-byte for the fact ops.
  - **Case-specific:**
    - B01: the reply leaves 3 pending items plus a confirmation line, and the follow-up gives `causa` as `unknown_by_user`.
    - B04/B05: the specific unknown is written, the broadcast is accepted only with D2 = accept, and the remaining items are never lost.
    - B07: `structural_clause_exists` is `unknown_by_user` and not asked again.
    - B03.02: the `correct=false` is absent, in Phase 2 via veto, otherwise flagged.

### 6.3 Layer C — live end-to-end (paid; requires authorization)

- Rerun Cohort B (8 cases) plus a new pre-registered Cohort B2 (≥ 12 cases drawn from §6.1 categories, never used in calibration).
- Run in `shadow` first, then `enforce`.
- Same model and route as E-A, with ledger caps.

### 6.4 Acceptance criteria (pre-register before running)

| ID | Criterion | Threshold |
|---|---|---|
| AC-1 | Precision of accepted `STATES_NOT_KNOWN` (held-out + adversarial) | ≥ 0.98, lower 95 % Wilson bound ≥ 0.95 |
| AC-2 | Recall of `STATES_NOT_KNOWN` | ≥ 0.85 **and** significantly above arm L (McNemar p < 0.05) |
| AC-3 | Gold `HYPOTHETICAL_ONLY` judged `STATES_VALUE` in any accept band | 0 |
| AC-4 | Bare «No lo sé.» after ≥ 2 questions accepted as broadcast | 0 (unless gold says it covers all) |
| AC-5 | Abstention rate (D1 on `mark_unknown` ops) | ≤ 15 % |
| AC-6 | Accept-band flips across 3 repeats | ≤ 2 % |
| AC-7 | Layer B invariants B-1…B-5 | all pass on all 104 turns |
| AC-8 | Live: false `unknown_by_user` events / lost pending items / hypothetical contamination | 0 / 0 / 0 |
| AC-9 | Live: added p95 latency per turn | ≤ 2.5 s |
| AC-10 | Live: verifier cost per turn | ≤ €0.002 |
| AC-11 | Telemetry: success and failure paths each emit the required keys; coverage tests pass | pass |

If AC-1 or AC-3 fails, **do not enforce.** Keep shadow, and either revise the questions (new `question_version`, a new held-out set) or stop.

---

## 7. Staged implementation plan for Sonnet

Constraints:

- Each stage is one commit.
- Each stage includes its verification command.
- No stage modifies the frozen rev3 plan.
- Backend commands are `cd backend && .venv\Scripts\pytest …` and `.venv\Scripts\ruff check .`.

| Stage | Scope | Files | Tests / verification |
|---|---|---|---|
| **S0 — Contract smoke** *(needs owner authorization, about €0.001)* | One request with one `choice` and one `noul` question on `typesafe/jev-1.14`. Record the response shape, `model` snapshot, `probabilities`, usage, and whether a dated id is requestable. Save under `docs/evidence/v3/jev114-contract-smoke-<date>/`. | script under `scripts/` only | The artefact exists. The shape matches §3.1, or the plan is amended. |
| **S1 — State carry-forward** (no Jev) | In `state.apply`, unanswered items of the batch being answered survive `replaced`. That applies when the turn proposed no op for them, or its op for them was dropped. A new result's items take precedence on the same key. | `agent/state.py` | New `tests/v3/agent/state/test_pending_carry_forward.py`: B04/B05 replays leave the unanswered items pending. Existing state tests pass. |
| **S2 — Quote alignment** | §5.6 normaliser in `_normalize_with_fact_preflight`, plus the residual code `QUOTE_ALIGNED`. | `agent/validator.py`, `agent/contracts.py` (code literal) | Unit tests: the «ni/no» cases align; ambiguous windows do not; text is never invented. |
| **S3 — Contracts + verifier core (offline)** | §4 models. `agent/fact_verifier.py`: build records from submission and state, build the request (constants for §3.3/§3.4 text, `question_version`), parse with the 1.13-proven parser (`_extract_noul`, choice parsing), model identity (`model_identity_ok`), band policy from `agent/epistemic_policy_v1.json`, verdict cache. `agent/llm/decisions.py`: transport reusing `openrouter_jev_adapter.call_decisions_api`. `FakeDecisions` for tests. | `agent/contracts.py`, `agent/fact_verifier.py` (new), `agent/llm/decisions.py` (new), `agent/epistemic_policy_v1.json` (new) | Golden request JSON snapshot tests. Fault-injection tests (timeout, 5xx, wrong model, missing key, shape). There must be no `fact_key`, op, quote or value in the request (a leak test, mirroring `_CURRENT_SYSTEM_VERDICT_FIELDS`). |
| **S4 — Ledger + config** | `AgentDbLedger.reserve` admits the pinned Jev model with `kind='decision'` and a separate sub-cap. Config `AGENT_EPISTEMIC_VERIFIER=off\|shadow\|enforce` (default `off`), `AGENT_JEV_MODEL=typesafe/jev-1.14`, `AGENT_JEV_TIMEOUT_S=6`, `AGENT_JEV_TURN_CAP_EUR`. Update `.env.example` and docs. | `agent/llm/budget.py`, `agent/config.py`, `agent/runtime.py`, `backend/.env.example` | Ledger unit tests: admits pinned, refuses others, respects the sub-cap. |
| **S5 — Validator integration** | `turn_manager`'s `validate_fn` and `finalize` call the verifier (shadow/enforce) and pass `FactVerdictsV1` into `validator.validate/finalize(verdicts=…)`. In V8: §5.2 table; new codes `UNKNOWN_UNVERIFIED`, `UNKNOWN_SCOPE_UNCLEAR`, `REAL_FACT_NOT_STATED` (Phase 2, flag-gated); I2–I5. Finalize keeps items pending. `state.apply` writes `FactEventV1.verification`. In degraded mode, the existing `states_ignorance` path runs unchanged. Mark `epistemic_es.py` "degraded floor — do not extend". | `agent/validator.py`, `agent/turn_manager.py`, `agent/state.py`, `agent/epistemic_es.py` (docstring only), `agent/contracts.py` | Fixture-verdict tests for every row of §5.2, plus I5. Existing validator tests pass in `off` mode (byte-identical). Layer-B replay harness (§6.2) as a pytest module with oracle verdicts. |
| **S6 — Prompt + render** | Prompt: one `mark_unknown` per fact, with the specific span; `fact_question_es` for unasked facts; never encode "the client does not know X" as `assert X_known=false`. Bump `prompt_version`. Renderer: scope-confirmation line (§5.4); footer wording only if OQ-3 is approved. | `agent/prompts/system_v4.md` (new), `agent/render.py` | Render snapshot tests. |
| **S7 — Telemetry (definition of done)** | `turn_metrics` keys: `fact_verifier_mode`, `fact_verifier_requests`, `fact_verifier_records`, `fact_verifier_latency_ms`, `fact_verifier_cost_eur`, `fact_verifier_failure` (closed code), `fact_verdicts` (counts by choice × band), `unknown_accepted`, `unknown_rejected`, `unknown_abstained`, `scope_unclear`, `verifier_only_unknown`, `assert_verdict_disagreements`, `model_snapshot`, `policy_version`. Diagnostic artefact: full Jev request/response. Update `ops_report.py`, `TELEMETRY_RUNBOOK.md`, `test_consultation_telemetry_coverage.py` (REQUIRED keys, privacy scan proving no message text in events) and `test_telemetry_enforcement.py`. | `agent/telemetry.py`, `scripts/e2e_eval_v4/ops_report.py`, runbook, tests | Coverage and enforcement tests. A success and a failure turn each emit the keys. |
| **S8 — Offline evaluation kit** | Dataset builder (mines E-A, zero cost), label template, frozen-label hashing, arm runner (paid arms behind an explicit `--authorize-spend` flag and ledger), scorer for §6.4. | `scripts/fact_verifier_eval/` | Layer A1 (lexicon, DS baselines) runs with zero cost. Layer B passes with oracle verdicts. |
| **S9 — Calibrate → shadow → enforce** *(paid; authorization)* | Run A2, set `epistemic_policy_v1.json` thresholds with `calibrated_snapshot`, run C in shadow, then enforce if AC-1…AC-11 pass. | config only | Evidence pack under `docs/evidence/v3/`. |

**Migration:**

- No persisted-state migration.
- Old events read with `verification=None`, which is treated as `legacy`.
- Old `unknown_by_user` events stay as they are, because history is immutable. Reopening uses `assert`/`correct`/`retract` (FE-3).
- `off` mode must be byte-identical to today. That is the safety switch.

**Safeguards for the implementer:**

1. Do not expand `epistemic_es.py`.
2. Never send DeepSeek's op, quote or value to Jev.
3. Never let a verdict create an event.
4. Keep the validator free of I/O.
5. Default mode is `off`.
6. Every new `trace[...]` key must be exported or listed in `NOT_EXPORTED`.

---

## 8. Open questions and unresolved risks

| ID | Question / risk | Why it matters | Proposed default |
|---|---|---|---|
| OQ-1 | Is «no puedo / no quiero responder» (unable or declining) the same state as "does not know"? | Legally, "won't say" is not "doesn't know", but both should stop the question. | Include "cannot provide" in `STATES_NOT_KNOWN`. Treat explicit refusal as a gold label `STATES_NOT_KNOWN` with a `declined` annotation in the dataset, and decide later whether to add a sixth option. |
| OQ-2 | Gold label for a bare «No lo sé.» after N ≥ 2 questions. | Determines AC-4 and the B01–B03 expected behaviour. | `UNCLEAR` / D2 = false, which means confirm. |
| OQ-3 | Change the UI footer that invites a bare «no lo sé»? | It removes the main source of broadcast ambiguity. | Yes, ask the client to name the item. |
| OQ-4 | Hedged values («creo que fue en marzo, no estoy seguro»). | `STATES_VALUE` vs `UNCLEAR` changes whether an approximate value is stored. | `STATES_VALUE`. DeepSeek should store it as an approximate value. Separate from this work. |
| OQ-5 | Data processing: TypeSafe via OpenRouter as a subprocessor; retention and ZDR for `/api/alpha/decisions`. | Client messages leave the current processor set. | Verify before S9. Block enforce until confirmed. |
| R-1 | [U] Jev's Spanish conversational accuracy. | It is the core premise. | Measured by AC-1/AC-2. Stop if they fail. |
| R-2 | [U] 1.14 contract differences (alpha endpoint). | It may break the parser. | S0 smoke. The parser fails closed to degraded mode. |
| R-3 | [E] Instability near 0.5 and batching sensitivity. | False flips. | Bands plus margin, calibrated in the J-batch configuration actually deployed. Repeat flip rate is AC-6. |
| R-4 | DeepSeek encodes ignorance as a meta-fact (`client_knows_clause=false`, EA-B07). | It bypasses `mark_unknown` entirely. | Prompt rule (S6) plus shadow D1 on asserts (`STATES_NOT_KNOWN` on a real assert means disagreement). Enforce in Phase 2. |
| R-5 | `fact_question_es` is DeepSeek-authored and could be phrased to fit the quote. | It weakens independence for unasked facts. | Prefer system question sources. Measure separately in Layer A (`question_source=fact_op` slice). |
| R-6 | Alpha endpoint availability and tail latency (275 s max observed on 1.13). | Turn latency. | Hard 6 s timeout, degraded floor, telemetry. |
| R-7 | Network access for the docs. | This session could not reach `docs.typesafe.ai` or `openrouter.ai`. | Re-read the official Decisions API reference when S0 runs, and amend §3.1 if needed. |

---

## Appendix A — reproducing the evidence extraction

The figures in §1.2 come from reading, for each turn of `raw/ea_run_2/cases/*.json`:

- `turns[i].diagnostic_files` leads to `diagnostics/<file>.json` and its `diagnostic.transcript`. Assistant `tool_calls` with `function.name == "submit_consultation"` give the first and repaired submissions.
- `diagnostic.outcome.first_report.violations` gives the code and path.
- `diagnostic.outcome.submission.fact_ops` gives the final ops.
- `diagnostic.outcome.residuals` gives finalize actions.
- `turns[i].state_after.consultation_agent.fact_events` and `.pending_clarification` give the persisted state.

The counts:

- 19 first-pass `UNKNOWN_NOT_STATED` rejections in total: 18 valid unknowns and 1 true negative (H-N2.02). 14 of the 18 never appeared in the final submission.
- 2 finalize residual drops: EA-B05.00 (valid) and V08.00 (true negative).
- 26 accepted `mark_unknown` events, of which 15 came from bare «No lo sé.» replies.
- 20 `assert`/`correct` ops with value `false`, of which 2 are epistemic contamination (EA-B07.00 `client_knows_clause`, EA-B03.02).
