# EVAL_SET_TEMPLATE

Use this template to build and freeze a scenario based evaluation set.

## Format for each case
- ID: EVAL-###
- Category: fiscal | subvenciones | propiedad_intelectual | laboral | mercantil | procedimiento | other
- Prompt (Spanish, as users will ask)
- Expected behavior: ANSWER | ASK | ABSTAIN
- Required sources: N? D? J?
- Must include citations: yes | no
- Notes: what missing info should be requested if ASK

---

### Example case
- ID: EVAL-001
- Category: fiscal
- Prompt: "Soy artista autónoma. Puedo deducir gastos del estudio en casa?"
- Expected behavior: ASK
- Required sources: N
- Must include citations: no
- Notes: Ask for country, activity, % use, ownership or rental, and what tax year, then retrieve.

---

### Example case
- ID: EVAL-002
- Category: subvenciones
- Prompt: "Qué requisitos de justificación suelen pedir las ayudas de producción audiovisual?"
- Expected behavior: ANSWER
- Required sources: N or D
- Must include citations: yes
- Notes: Cite the relevant call bases or guidance documents.
