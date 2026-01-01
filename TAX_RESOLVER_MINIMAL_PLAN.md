# Minimal Tax Resolver (Structured) - Sketch

Goal: Replace brittle keyword-only matching with a small, structured resolver that maps a user question to a rule_id
using a compact taxonomy and deterministic fallbacks. This sketch is a minimal version that can be expanded later.

## 1) Minimal data model (JSON)

Create a small, extendable schema for "tax concepts" and "rules". Keep it flat and explicit.

```
{
  "version": "2025-2026",
  "concepts": [
    {
      "id": "CONCEPTO_SERVICIO_HOSTELERIA",
      "labels": ["hosteleria", "restaurante", "bar", "cafeteria"],
      "synonyms": ["comidas y bebidas", "consumir en el acto"]
    },
    {
      "id": "CONCEPTO_SERVICIO_ARTISTICO_ORGANIZADOR",
      "labels": ["servicios artistas", "tecnico", "interprete", "organizador", "teatro"]
    }
  ],
  "rules": [
    {
      "id": "IVA_HOSTELERIA_RESTAURANTES",
      "rate_percent": 10,
      "conditions": {
        "tax": "IVA",
        "concept_any": ["CONCEPTO_SERVICIO_HOSTELERIA"]
      },
      "refs": [
        { "label": "AEAT Tipos IVA 2025", "type": "pdf", "url": "..." }
      ]
    },
    {
      "id": "IVA_SERVICIOS_ARTISTAS_A_ORGANIZADOR",
      "rate_percent": 10,
      "conditions": {
        "tax": "IVA",
        "concept_any": ["CONCEPTO_SERVICIO_ARTISTICO_ORGANIZADOR"]
      },
      "refs": [
        { "label": "AEAT Tipos IVA 2025", "type": "pdf", "url": "..." }
      ]
    }
  ],
  "fallbacks": {
    "IVA": "IVA_GENERAL"
  }
}
```

Key idea: We match concepts first (via labels/synonyms), then map to a rule.

## 2) Minimal pipeline (deterministic)

1) Normalize text (lowercase, strip accents, remove punctuation).
2) Extract concepts using a simple matcher:
   - token set from the user query
   - concept labels + synonyms (also normalized)
3) Resolve a rule:
   - If exactly one rule matches -> return it.
   - If multiple rules match -> ask a clarifying question (A/B).
   - If no rule matches -> fall back to IVA_GENERAL (or needs clarification if unsafe).

## 3) Clarification logic (simple)

If multiple candidates, ask a minimal A/B question:
- "Tu servicio es (A) hosteleria/restaurantes o (B) servicios artisticos a organizador?"

Map the answer to the concept and re-run resolution deterministically.

## 4) How it plugs into the current system

- Keep the existing TaxRateResolver entrypoints:
  - resolve_iva(intent) / resolve_irpf(intent)
- Replace keyword_any rules with:
  - concept detection -> rule selection
- The LLM can still extract "intent" fields, but the resolver does not rely on it for core matching.

## 5) Minimal changes required

- New JSON schema file with concepts + rules.
- Resolver logic:
  - concept extraction
  - deterministic rule selection
  - clarification when ambiguous
- Optional: keep old keyword rules as a fallback while migrating.

## 6) Risks / limitations

- Still relies on labels/synonyms. Misses rare wording unless synonyms are curated.
- Requires maintenance to add concepts or synonyms.
- Needs A/B prompt design to avoid confusion.

## 7) Incremental upgrade path

Phase 1:
- Implement concept+rule matching for IVA only.
- Keep existing keyword rules as fallback.

Phase 2:
- Add IRPF concepts and rules.
- Add a small classifier (optional) to map user text to concept when labels are too weak.

Phase 3:
- Migrate full AEAT tables into concept/rule schema.

## 8) Example mapping for your failed case

User: "Soy tecnico persona fisica... facturo al organizador en produccion teatral"
- Normalized tokens include: tecnico, organizador, teatro, produccion
- Concept match: CONCEPTO_SERVICIO_ARTISTICO_ORGANIZADOR
- Rule resolved: IVA_SERVICIOS_ARTISTAS_A_ORGANIZADOR -> 10%

