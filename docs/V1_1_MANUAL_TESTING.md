# V1.1 Manual Testing Guide

Quick reference for manually testing the V1.1 fixes.

---

## Prerequisites

1. Backend running: `cd backend && python manage.py runserver`
2. Gemini API key configured in `.env`
3. PostgreSQL with corpus data loaded

---

## Test 1: Hierarchy Questions (Authority Pack)

### Query 1: Top norm
```bash
curl -X POST http://localhost:8000/api/v1.1/chat/ \
  -H "Content-Type: application/json" \
  -d '{
    "query": "¿Cuál es la norma con mayor rango jurídico en España?"
  }'
```

**Expected**:
- ✅ Answer mentions "Constitución española"
- ✅ `metadata.authority_question: true`
- ✅ `metadata.authority_pack_added: true`
- ✅ Direct answer (not "no hay información")

---

### Query 2: Reglamento vs Ley
```bash
curl -X POST http://localhost:8000/api/v1.1/chat/ \
  -H "Content-Type: application/json" \
  -d '{
    "query": "¿Puede un reglamento contradecir una ley?"
  }'
```

**Expected**:
- ✅ Answer says "No, prevalece la ley"
- ✅ Authority pack citation
- ✅ `metadata.authority_question: true`

---

### Query 3: Ley Orgánica vs Ordinaria
```bash
curl -X POST http://localhost:8000/api/v1.1/chat/ \
  -H "Content-Type: application/json" \
  -d '{
    "query": "¿Qué diferencia hay entre ley orgánica y ley ordinaria?"
  }'
```

**Expected**:
- ✅ Explains difference (materias, mayoría)
- ✅ Authority pack sources
- ✅ `metadata.authority_question: true`

---

## Test 2: Unicode/Accent Preservation

### Query: Accents in question
```bash
curl -X POST http://localhost:8000/api/v1.1/chat/ \
  -H "Content-Type: application/json" \
  -d '{
    "query": "¿Qué tipos de retenciones existen en IRPF?"
  }'
```

**Expected**:
- ✅ Response contains proper Spanish: "más", "típicos", "retención"
- ✅ NO question marks replacing accents: "m?s", "t?picos"
- ✅ `metadata.expanded_queries` shows proper accents

---

## Test 3: No Crashes (Post-Processing Robustness)

### Query: Edge case
```bash
curl -X POST http://localhost:8000/api/v1.1/chat/ \
  -H "Content-Type: application/json" \
  -d '{
    "query": "¿Cómo se calcula el IVA en servicios digitales internacionales?"
  }'
```

**Expected**:
- ✅ Returns 200 (not 500)
- ✅ If errors occur, check `metadata.postprocess_errors`
- ✅ Always returns some answer (even if fallback)

---

## Test 4: Regular Questions (No Authority Pack)

### Query: Procedimiento administrativo
```bash
curl -X POST http://localhost:8000/api/v1.1/chat/ \
  -H "Content-Type: application/json" \
  -d '{
    "query": "¿Cómo se aplica el procedimiento administrativo común?"
  }'
```

**Expected**:
- ✅ `metadata.authority_question: false`
- ✅ `metadata.authority_pack_added: false`
- ✅ Regular retrieval (no synthetic sources)

---

## Metadata to Check

For all queries, inspect the response metadata:

```json
{
  "metadata": {
    "version": "v1_1",
    "expanded_queries": [...],          // Should show 2-8 queries
    "authority_question": true/false,    // Correctly detected?
    "authority_pack_added": true/false,  // Added when needed?
    "authority_pack_count": 0-5,         // How many synthetic sources?
    "abstained": true/false,             // Metadata only, not control flow
    "judge": {
      "verdict": "PASS"/"REDO",
      "reasons": [...]
    },
    "redo_performed": true/false,
    "postprocess_errors": null/[...],    // Should be null (no errors)
    "retrieval_counts": {
      "combined_results": 80,
      "fused_pre_filter": {...},
      "post_filter": {...}
    }
  }
}
```

---

## Common Issues to Look For

### Issue 1: Encoding
**Symptom**: `?` instead of `á`, `é`, `í`, `ó`, `ú`, `ñ`

**Check**:
1. Response body is UTF-8
2. `Content-Type: application/json; charset=utf-8` header
3. Database connection uses UTF-8

**Fixed by**: Settings.py changes + QueryExpander fixes

---

### Issue 2: "No evidence" answers despite sources
**Symptom**: Answer says "no puedo afirmar" but `total_sources > 0`

**Check**:
1. `metadata.abstained` - should be metadata only
2. Answer should ALWAYS try to help (even with low evidence)
3. For hierarchy questions, check `authority_pack_added: true`

**Fixed by**: Removed abstain control flow

---

### Issue 3: 500 errors
**Symptom**: "Failed to generate answer" instead of response

**Check**:
1. Backend logs for exceptions
2. `metadata.postprocess_errors` (if response received)

**Fixed by**: Non-fatal post-processing with try/except

---

## Python Test Script

Alternative to curl:

```python
import requests

response = requests.post(
    'http://localhost:8000/api/v1.1/chat/',
    json={'query': '¿Cuál es la norma con mayor rango jurídico en España?'}
)

data = response.json()
print("Status:", response.status_code)
print("Answer:", data['answer'][:200])
print("Authority question:", data['metadata']['authority_question'])
print("Authority pack added:", data['metadata']['authority_pack_added'])
print("Total sources:", data['metadata']['total_sources'])
```

---

## Frontend Testing

1. Start frontend: `cd frontend-legal && npm run dev`
2. Open: `http://localhost:3000`
3. Test queries in chat interface

**Check**:
- Accents render correctly in UI
- No "Failed to generate answer" errors
- Authority pack citations show up
- Response is helpful (not just "no information")

---

## Success Criteria

✅ **All hierarchy questions** return direct answers with authority citations
✅ **All responses** preserve Spanish accents (á, é, í, ó, ú, ñ)
✅ **Zero 500 errors** from post-processing failures
✅ **Metadata** accurately reflects query type and processing

---

## Troubleshooting

### If authority pack not triggering:
1. Check query contains trigger words: "jerarquía", "rango", "norma superior"
2. Verify Excel file exists: `corpus_normativo_artisting_enriched_clean.xlsx`
3. Check logs for authority pack loading errors

### If accents still broken:
1. Verify database encoding: `\l` in psql should show UTF8
2. Check REST Framework settings: `UNICODE_JSON: True`
3. Test with simple query: `{"query": "más"}`

### If still getting 500 errors:
1. Check backend logs for specific exception
2. Look for `postprocess_errors` in metadata
3. Verify all try/except blocks are in place

---

## Quick Sanity Check

Run this single query to verify all fixes:

```bash
curl -X POST http://localhost:8000/api/v1.1/chat/ \
  -H "Content-Type: application/json" \
  -d '{"query": "¿Cuál es la jerarquía normativa en España?"}' \
  | jq '.metadata | {authority_question, authority_pack_added, abstained, postprocess_errors}'
```

**Expected output**:
```json
{
  "authority_question": true,
  "authority_pack_added": true,
  "abstained": false,
  "postprocess_errors": null
}
```

✅ All fixes working if this passes!
