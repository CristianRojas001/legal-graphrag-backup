# Day 4: Intent Classifier - Testing Instructions for Codex

## Document Information
- **Created**: 2025-12-13
- **Component**: Intent Classifier (Keyword-based)
- **Status**: Ready for Testing
- **Implementation**: `backend/apps/legal_graphrag/services/intent_classifier.py`

---

## What Was Implemented

A keyword-based intent classifier that categorizes legal queries into specific areas:
- **Fiscal** (taxes, IVA, IRPF, deductions)
- **Laboral** (employment, contracts, autónomo)
- **Propiedad Intelectual** (copyright, SGAE, royalties)
- **Contabilidad** (accounting, books, balance)
- **Subvenciones** (grants, subsidies, funding)
- **Societario** (corporate, company formation)
- **Administrativo** (licenses, permits, procedures)

The classifier uses simple keyword matching to assign queries to the most relevant legal area.

---

## Testing Instructions for Codex

### 1. Basic Functionality Tests

**Objective**: Verify the classifier correctly identifies legal areas.

#### Test 1.1: Fiscal Queries
```bash
# Navigate to backend directory
cd "d:\IT workspace\Legal GraphRAG\backend"

# Start Django shell
python manage.py shell
```

```python
from apps.legal_graphrag.services.intent_classifier import IntentClassifier

classifier = IntentClassifier()

# Test fiscal queries
test_queries = [
    "¿Puedo deducir gastos de mi home studio?",
    "¿Cómo declaro el IVA como artista?",
    "¿Qué retenciones de IRPF aplican a músicos?",
    "¿Cuáles son los gastos deducibles en Hacienda?",
    "¿Tengo que pagar impuestos por mecenazgo?"
]

print("=== FISCAL QUERIES TEST ===\n")
for query in test_queries:
    area = classifier.classify_area(query)
    print(f"Query: {query}")
    print(f"Classified as: {area}")
    print(f"Expected: Fiscal")
    print(f"✓ PASS" if area == "Fiscal" else f"✗ FAIL")
    print()
```

**Expected Result**: All queries should be classified as "Fiscal"

#### Test 1.2: Laboral Queries
```python
# Test laboral queries
test_queries = [
    "¿Cómo me doy de alta como autónomo?",
    "¿Qué cotización de Seguridad Social tengo que pagar?",
    "¿Puedo contratar a un empleado siendo artista autónomo?",
    "¿Qué pasa si me dan de baja en la Seguridad Social?",
    "¿Cuándo tengo que afiliarme al RETA?"
]

print("=== LABORAL QUERIES TEST ===\n")
for query in test_queries:
    area = classifier.classify_area(query)
    print(f"Query: {query}")
    print(f"Classified as: {area}")
    print(f"Expected: Laboral")
    print(f"✓ PASS" if area == "Laboral" else f"✗ FAIL")
    print()
```

**Expected Result**: All queries should be classified as "Laboral"

#### Test 1.3: Propiedad Intelectual Queries
```python
# Test IP queries
test_queries = [
    "¿Cómo registro mis derechos de autor?",
    "¿Qué hace la SGAE con mis royalties?",
    "¿Puedo denunciar por plagio de mi obra?",
    "¿Cuánto tiempo duran los derechos de autor?",
    "¿Necesito licencia para usar una canción en mi vídeo?"
]

print("=== PROPIEDAD INTELECTUAL QUERIES TEST ===\n")
for query in test_queries:
    area = classifier.classify_area(query)
    print(f"Query: {query}")
    print(f"Classified as: {area}")
    print(f"Expected: Propiedad Intelectual")
    print(f"✓ PASS" if area == "Propiedad Intelectual" else f"✗ FAIL")
    print()
```

**Expected Result**: All queries should be classified as "Propiedad Intelectual"

---

### 2. Edge Cases Tests

#### Test 2.1: Ambiguous Queries (Multiple Areas)
```python
# Test queries that could match multiple areas
ambiguous_queries = [
    {
        'query': "¿Tengo que declarar los ingresos de mi contrato como autónomo?",
        'possible_areas': ['Fiscal', 'Laboral']
    },
    {
        'query': "¿Cómo tributan los derechos de autor en el IRPF?",
        'possible_areas': ['Fiscal', 'Propiedad Intelectual']
    },
    {
        'query': "¿Necesito licencia para abrir un estudio de grabación?",
        'possible_areas': ['Administrativo', 'Laboral']
    }
]

print("=== AMBIGUOUS QUERIES TEST ===\n")
for test in ambiguous_queries:
    result = classifier.classify_with_confidence(test['query'])
    print(f"Query: {test['query']}")
    print(f"Classified as: {result['area']} (confidence: {result['confidence']:.2%})")
    print(f"Score breakdown: {result['scores']}")
    print(f"Expected one of: {test['possible_areas']}")
    print(f"✓ PASS" if result['area'] in test['possible_areas'] else f"⚠ CHECK")
    print()
```

**Expected Result**: Classifier should pick the area with the highest score. Confidence should reflect ambiguity (lower confidence for ambiguous queries).

#### Test 2.2: Queries with No Clear Area
```python
# Test queries that don't match any area clearly
unclear_queries = [
    "¿Dónde está la oficina de Hacienda más cercana?",
    "¿Qué hora es?",
    "Hola, ¿cómo estás?",
    "¿Cuál es la capital de España?",
    "¿Puedo comprar pan en la tienda?"
]

print("=== UNCLEAR QUERIES TEST ===\n")
for query in unclear_queries:
    area = classifier.classify_area(query)
    print(f"Query: {query}")
    print(f"Classified as: {area}")
    print(f"Expected: None (or weak classification)")
    print(f"✓ PASS" if area is None else f"⚠ WEAK CLASSIFICATION: {area}")
    print()
```

**Expected Result**: Most should return `None` or have very low confidence.

#### Test 2.3: Empty and Malformed Queries
```python
# Test edge cases
edge_cases = [
    "",
    "   ",
    "?",
    "¿?",
    "123456",
    "a" * 1000  # Very long query
]

print("=== EDGE CASES TEST ===\n")
for query in edge_cases:
    try:
        area = classifier.classify_area(query)
        print(f"Query: '{query[:50]}{'...' if len(query) > 50 else ''}'")
        print(f"Result: {area}")
        print("✓ PASS (no crash)")
    except Exception as e:
        print(f"Query: '{query[:50]}{'...' if len(query) > 50 else ''}'")
        print(f"✗ FAIL: {type(e).__name__}: {e}")
    print()
```

**Expected Result**: No crashes, graceful handling with `None` or weak classification.

---

### 3. Keyword Extraction Tests

#### Test 3.1: Basic Keyword Extraction
```python
# Test keyword extraction
test_cases = [
    {
        'query': "¿Cómo puedo deducir los gastos de mi estudio?",
        'expected_keywords': ['cómo', 'puedo', 'deducir', 'gastos', 'estudio']
    },
    {
        'query': "¿Qué retenciones de IRPF aplican?",
        'expected_keywords': ['retenciones', 'irpf', 'aplican']
    },
    {
        'query': "Dar de alta en Seguridad Social",
        'expected_keywords': ['alta', 'seguridad', 'social']
    }
]

print("=== KEYWORD EXTRACTION TEST ===\n")
for test in test_cases:
    keywords = classifier.extract_keywords(test['query'])
    print(f"Query: {test['query']}")
    print(f"Extracted: {keywords}")
    print(f"Expected: {test['expected_keywords']}")

    # Check if important keywords are present
    missing = [k for k in test['expected_keywords'] if k not in keywords]
    extra = [k for k in keywords if k not in test['expected_keywords']]

    if not missing:
        print("✓ PASS (all expected keywords found)")
    else:
        print(f"⚠ Missing keywords: {missing}")

    if extra:
        print(f"ℹ Extra keywords found: {extra}")
    print()
```

**Expected Result**: Should extract meaningful keywords, filter out stopwords.

---

### 4. Utility Methods Tests

#### Test 4.1: Get All Areas
```python
# Test get_all_areas method
print("=== GET ALL AREAS TEST ===\n")
areas = classifier.get_all_areas()
print(f"Available areas: {areas}")
print(f"Total areas: {len(areas)}")

expected_areas = ['Fiscal', 'Laboral', 'Propiedad Intelectual', 'Contabilidad',
                  'Subvenciones', 'Societario', 'Administrativo']

missing_areas = [a for a in expected_areas if a not in areas]
extra_areas = [a for a in areas if a not in expected_areas]

if not missing_areas and not extra_areas:
    print("✓ PASS (all expected areas present)")
else:
    if missing_areas:
        print(f"⚠ Missing areas: {missing_areas}")
    if extra_areas:
        print(f"ℹ Extra areas: {extra_areas}")
print()
```

#### Test 4.2: Get Keywords for Area
```python
# Test get_keywords_for_area method
print("=== GET KEYWORDS FOR AREA TEST ===\n")

test_areas = ['Fiscal', 'Laboral', 'InvalidArea']

for area in test_areas:
    keywords = classifier.get_keywords_for_area(area)
    print(f"Area: {area}")
    print(f"Keywords count: {len(keywords)}")
    if area == 'InvalidArea':
        print(f"Expected: Empty list")
        print(f"✓ PASS" if keywords == [] else f"✗ FAIL")
    else:
        print(f"Sample keywords: {keywords[:5]}")
        print(f"✓ PASS" if len(keywords) > 0 else f"✗ FAIL")
    print()
```

---

### 5. Confidence Scoring Tests

#### Test 5.1: High Confidence Classification
```python
# Test classify_with_confidence for clear queries
print("=== HIGH CONFIDENCE TEST ===\n")

clear_queries = [
    "¿Puedo deducir gastos de IVA en mi declaración de IRPF?",
    "¿Cómo me doy de alta como trabajador autónomo?",
    "¿Dónde registro mis derechos de autor musicales?"
]

for query in clear_queries:
    result = classifier.classify_with_confidence(query)
    print(f"Query: {query}")
    print(f"Area: {result['area']}")
    print(f"Confidence: {result['confidence']:.2%}")
    print(f"Scores: {result['scores']}")
    print(f"✓ HIGH CONFIDENCE" if result['confidence'] > 0.5 else f"⚠ LOW CONFIDENCE")
    print()
```

**Expected Result**: Confidence should be >50% for clear queries.

#### Test 5.2: Low Confidence Classification
```python
# Test classify_with_confidence for ambiguous queries
print("=== LOW CONFIDENCE TEST ===\n")

ambiguous_queries = [
    "¿Qué documentos necesito?",
    "¿Cuáles son mis obligaciones?",
    "¿Dónde tengo que ir?"
]

for query in ambiguous_queries:
    result = classifier.classify_with_confidence(query)
    print(f"Query: {query}")
    print(f"Area: {result['area']}")
    print(f"Confidence: {result['confidence']:.2%}")
    print(f"Scores: {result['scores']}")
    print(f"✓ EXPECTED LOW CONFIDENCE" if result['confidence'] < 0.5 or result['area'] is None else f"⚠ UNEXPECTEDLY HIGH")
    print()
```

**Expected Result**: Confidence should be low (<50%) or None.

---

### 6. Performance Tests

#### Test 6.1: Response Time
```python
import time

print("=== PERFORMANCE TEST ===\n")

# Test classification speed
test_queries = [
    "¿Puedo deducir gastos de mi home studio?",
    "¿Cómo me doy de alta como autónomo?",
    "¿Dónde registro mis derechos de autor?"
] * 100  # 300 queries

start_time = time.time()

for query in test_queries:
    _ = classifier.classify_area(query)

end_time = time.time()
elapsed = end_time - start_time

print(f"Total queries: {len(test_queries)}")
print(f"Total time: {elapsed:.2f}s")
print(f"Average time per query: {elapsed/len(test_queries)*1000:.2f}ms")
print(f"Queries per second: {len(test_queries)/elapsed:.0f}")

# Should be very fast (keyword matching is O(n*m) where n=keywords, m=query_words)
if elapsed < 1.0:
    print("✓ PASS (fast enough for production)")
else:
    print("⚠ SLOW (consider optimization)")
print()
```

**Expected Result**: Should be <1ms per query (keyword matching is very fast).

---

### 7. Integration Test with Real Data

#### Test 7.1: Test with Sample Legal Queries
```python
# Test with realistic artist queries
print("=== REAL-WORLD QUERIES TEST ===\n")

real_queries = [
    # Fiscal
    ("¿Puedo deducir el alquiler de mi estudio de música?", "Fiscal"),
    ("¿Cuánto IVA tengo que cobrar por un concierto?", "Fiscal"),
    ("¿Debo hacer retención de IRPF en facturas?", "Fiscal"),

    # Laboral
    ("¿Puedo estar en el paro y ser autónomo a la vez?", "Laboral"),
    ("¿Cuánto cuesta la cuota de autónomos para artistas?", "Laboral"),
    ("¿Necesito contratar a músicos con contrato?", "Laboral"),

    # Propiedad Intelectual
    ("¿Cómo cobro derechos de autor de Spotify?", "Propiedad Intelectual"),
    ("¿Puedo usar una foto de internet en mi disco?", "Propiedad Intelectual"),
    ("¿Qué hago si alguien copia mi canción?", "Propiedad Intelectual"),

    # Subvenciones
    ("¿Hay ayudas para grabar un disco en 2025?", "Subvenciones"),
    ("¿Cómo solicito una beca del Ministerio de Cultura?", "Subvenciones"),

    # Administrativo
    ("¿Necesito licencia de actividad para dar clases?", "Administrativo"),
]

total = len(real_queries)
correct = 0

for query, expected_area in real_queries:
    area = classifier.classify_area(query)
    is_correct = area == expected_area

    if is_correct:
        correct += 1

    print(f"Query: {query}")
    print(f"Expected: {expected_area}")
    print(f"Got: {area}")
    print(f"{'✓ PASS' if is_correct else '✗ FAIL'}")
    print()

accuracy = correct / total * 100
print(f"=== ACCURACY: {accuracy:.1f}% ({correct}/{total}) ===")

if accuracy >= 80:
    print("✓ EXCELLENT (>80% accuracy)")
elif accuracy >= 60:
    print("✓ GOOD (>60% accuracy)")
else:
    print("⚠ NEEDS IMPROVEMENT (<60% accuracy)")
```

**Expected Result**: Accuracy should be >80% for these clear, domain-specific queries.

---

## Success Criteria

✅ **PASS Criteria**:
1. Fiscal queries correctly classified as "Fiscal" (>80% accuracy)
2. Laboral queries correctly classified as "Laboral" (>80% accuracy)
3. IP queries correctly classified as "Propiedad Intelectual" (>80% accuracy)
4. No crashes on edge cases (empty strings, very long queries)
5. Keyword extraction removes stopwords correctly
6. `get_all_areas()` returns all 7 areas
7. `classify_with_confidence()` returns proper structure
8. Performance: <1ms per query on average
9. Overall accuracy >80% on real-world test set

⚠️ **EXPECTED LIMITATIONS** (acceptable for MVP):
- Ambiguous queries may have low confidence or mixed classification
- Generic queries (no legal keywords) may return `None`
- Multi-area queries will pick strongest match (this is expected behavior)

---

## Reporting Results

After testing, create a summary file: `DAY_4_INTENT_CLASSIFIER_TEST_RESULTS.md`

Include:
1. Date and time of testing
2. Pass/fail status for each test section
3. Overall accuracy percentage
4. Any bugs or issues found
5. Performance metrics
6. Recommendations for improvements

**Example format**:
```markdown
# Intent Classifier Test Results

**Date**: 2025-12-13
**Tester**: Codex
**Status**: PASS / FAIL

## Summary
- Total tests: 50
- Passed: 48
- Failed: 2
- Accuracy: 85%

## Test Results
1. ✓ Fiscal Queries: 100% (5/5)
2. ✓ Laboral Queries: 100% (5/5)
3. ✓ IP Queries: 100% (5/5)
...

## Issues Found
1. Query "..." was classified as X but expected Y
...

## Performance
- Average time: 0.05ms per query
- Throughput: 20,000 queries/second

## Recommendations
- Add more keywords for area X
- Improve handling of ambiguous queries
```

---

## Next Steps After Testing

Once testing is complete and passing:
1. ✅ Mark task as complete in sprint plan
2. Move to next task: **RAG Engine** (Day 4, Task 2)
3. Integration: RAG Engine will use this classifier via:
   ```python
   from apps.legal_graphrag.services.intent_classifier import IntentClassifier
   classifier = IntentClassifier()
   area = classifier.classify_area(user_query)
   ```

---

**Good luck, Codex! 🚀**
