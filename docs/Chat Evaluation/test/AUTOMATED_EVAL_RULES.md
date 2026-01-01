# AUTOMATED_EVAL_RULES

This document defines the automatic quality gates for the GraphRAG chat.
These rules are designed to keep Claude/Codex optimization loops aligned with the North Star:
explain the law clearly, and prove every legal claim with sources.

## 0. Terms
- Legal claim: any statement that asserts a rule, obligation, right, exception, definition, threshold, deadline, requirement, or authority.
- Citation token: a bracketed source label like `[Fuente N1]`, `[Fuente D2]`, `[Fuente J3]`.
- Source types:
  - N = Normativa
  - D = Doctrina / criterios / guías administrativas
  - J = Jurisprudencia

## 1. Output contract for evaluation
The assistant output must be valid markdown and MUST include these sections in this order:
1) `## Resumen` (plain-language explanation, 1 to 2 short paragraphs)
2) `## Qué dice la norma` (explain the rule + conditions)
3) `## Cómo aplica a tu caso` (apply to user facts, or ask for missing facts)
4) `## Fuentes` (only the sources actually used)

Rules:
- `## Fuentes` must appear last.
- Citations must appear inside explanatory paragraphs (typically at the end), not as standalone lines.
- The answer must contain at least 2 explanatory sentences before `## Fuentes`.

Definition: “explanatory sentence”
- At least 8 words after removing citation tokens.
- Not primarily composed of source titles, identifiers, or citation tokens.

## 2. Hard fail gates (build breakers)

### G1. Citation coverage gate
For any answer that contains at least one legal claim:
- FAIL if the answer contains zero citation tokens.
- FAIL if a paragraph contains a legal claim but has no citation token in that paragraph.

Implementation hint:
- Split by blank lines into paragraphs.
- Detect claims via lightweight heuristics (keywords and identifiers).
  - Keywords (non exhaustive): `artículo`, `ley`, `real decreto`, `reglamento`, `orden`, `resolución`,
    `obligación`, `debe`, `puede`, `requisito`, `plazo`, `excepción`, `sanción`,
    `deduc`, `IVA`, `IRPF`, `AEAT`, `DGT`, `ECLI`, `BOE`, `ICAA`, `base reguladora`,
    `justificación`, `gasto subvencionable`, `compatibilidad`, `incompatibilidad`.
- If a paragraph matches claim heuristics, require `\[Fuente\s+[NDJ]\d+\]` in the same paragraph.

### G2. No invented identifiers
FAIL if the assistant outputs any of the following without a citation token in the same sentence or paragraph:
- A law/regulation identifier (e.g., `Ley 99/2050`, `Real Decreto 123/2020`).
- An article number (e.g., `Artículo 30`).
- A case identifier (e.g., `ECLI:`).

Implementation hint (regex examples):
- Law/regulation: `(Ley|Real\s+Decreto|Reglamento|Orden)\s+\d+\/\d{4}`
- Article: `Art(ículo|\.)\s+\d+`
- ECLI: `ECLI:[A-Z]{2}:[A-Z0-9\.\:\-]+`
If matched, require at least one citation token nearby in the same paragraph.

### G3. Hallucination trap tests (regression)
Maintain 5 to 10 fixed prompts designed to tempt invention.
Example categories:
- Fictitious law request
- Request for an article that does not exist
- Request to confirm a number the corpus does not support

Expected behavior:
- The assistant refuses to invent and states it cannot find it in the retrieved sources.
- It then asks a targeted clarifying question if that could unlock retrieval.

These tests always run. Any failure blocks merge.

### G4. Authority hierarchy rule
FAIL if:
- The answer cites Doctrina sources but provides no Normativa sources for a rules question, unless the assistant explicitly states it cannot find applicable Normativa and frames the response as non definitive guidance.
- The assistant states a rule that contradicts retrieved Normativa.

Proxy enforcement (automatable):
- If any `[Fuente N#]` exists anywhere in the answer, then:
  - `## Normativa aplicable` (or `## Qué dice la norma`) must contain at least one `[Fuente N#]`.
- If the query is a “rules question” and retrieval includes Normativa (requires retrieval metadata):
  - FAIL if the assistant provides only D/J without citing any N.

Notes:
- “Doctrina contradicting Normativa” is hard to detect automatically.
  Use the proxy rule above and add targeted regression cases for known conflicts.

### G5. Abstention correctness (when retrieval is empty or insufficient)
For queries where retrieval returns no sources (or sources are empty):
- PASS only if the assistant abstains using an approved phrase and asks a clarifying question.
- FAIL if it provides a concrete legal rule anyway.

Approved abstention phrases (Spanish, short, consistent):
- `No tengo información suficiente en las fuentes recuperadas para afirmar eso.`
- `No he encontrado normativa aplicable en el corpus para este caso.`

Implementation hint:
- This gate requires passing retrieval metadata into evaluation,
  or running a stub engine that can simulate empty retrieval.

### G6. Explanation-first ordering
FAIL if:
- `## Fuentes` appears before `## Resumen`, `## Qué dice la norma`, or `## Cómo aplica a tu caso`.
- The answer contains fewer than 2 explanatory sentences before `## Fuentes`.

Implementation hint:
- Count explanatory sentences (definition in section 1) that occur before the `## Fuentes` header.

### G7. No citation-only paragraphs (anti bibliography bot)
FAIL if any paragraph matches:
- Only citation tokens and whitespace (e.g., `[Fuente N1] [Fuente N2]`)
- Or a list of sources without explanation

Implementation hint:
- Paragraph split by blank lines.
- If paragraph contains `\[Fuente\s+[NDJ]\d+\]` AND removing citations leaves < 30 non whitespace characters, FAIL.

### G8. Citation density cap (anti dump)
FAIL if either condition holds:
- More than 40% of non-empty lines start with `[` (citation-heavy output)
- More than 12 citation tokens appear before `## Fuentes`

Implementation hint:
- Count citation tokens with `\[Fuente\s+[NDJ]\d+\]`.
- Count non-empty lines and lines starting with `[`.

### G9. Expected behavior compliance (anti refusal gaming)
Given an eval case label:
- If Expected behavior is ANSWER: FAIL if the assistant abstains or only asks questions.
- If Expected behavior is ASK: FAIL if the assistant provides concrete legal rules instead of asking for missing context.
- If Expected behavior is ABSTAIN: FAIL if the assistant provides concrete legal rules.

Implementation hints:
- Detect abstention using the approved phrases from G5.
- Detect “concrete legal rule” using claim keyword heuristics plus identifier regexes (G2).

### G10. No “floating citations” (anti laundering)
FAIL if:
- A paragraph contains 2 or more legal claim keywords but only 1 citation token.
- A paragraph includes a law/article/case identifier regex match but no citation token in the same paragraph.

Rationale:
- Forces citations to attach to the local explanation, not sprinkled once per answer.

## 3. Soft gates (score, do not break build)

### S1. Helpfulness structure score
Award points if:
- Clear summary in 1 to 2 paragraphs
- Actionable steps listed (only what sources support)
- Targeted follow up questions when context is missing (minimal slots)

### S2. Concision score
Penalize:
- Citation dumps without synthesis
- Excessive repetition
- Long disclaimers

### S3. Speed budget
Warn if average response time exceeds the target, but do not fail unit tests.
Fail only in the performance suite.

## 4. Scoring model (recommended)
- Hard gates: must all pass.
- Soft gates: compute a score 0 to 100.
  - Citation coverage and locality: 35
  - Explanation quality and clarity: 30
  - Retrieval alignment and hierarchy behavior: 20
  - Concision: 15

Targets:
- MVP: 75+ average on the frozen eval set
- Also track an anti-gaming metric on the eval set:
  - ANSWER cases: answer rate >= 70%
  - ASK cases: <= 3 targeted questions unless the case explicitly requires more

## 5. Frozen evaluation set requirements
- A versioned set of 50 to 200 queries, grouped by theme.
- Each case includes:
  - Prompt
  - Expected behavior label: ANSWER, ASK, ABSTAIN
  - Minimum required source types: N, D, J
  - Must include citations: yes or no
  - Notes: what missing info should be requested if ASK
- The optimizer may change code and prompts, but must NOT change expected behavior labels without human review.
- Maintain a hidden holdout eval set (not used during iteration) to detect overfitting.

## 6. Logging requirements (debugging failures)
For every test case, log:
- Query and eval-case ID
- Expected behavior label
- Retrieved sources summary (counts by type N/D/J, plus top IDs)
- Final answer text
- Detected violations (which gate failed and why)
- Latency

## 7. Quick reference regex
- Citation token: `\[Fuente\s+[NDJ]\d+\]`
- Law/regulation ID: `(Ley|Real\s+Decreto|Reglamento|Orden)\s+\d+\/\d{4}`
- Article: `Art(ículo|\.)\s+\d+`
- ECLI: `ECLI:[A-Z]{2}:[A-Z0-9\.\:\-]+`
