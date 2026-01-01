# Legal RAG Engine V1.1 - Improvements & Fixes

**Document Version**: 1.1
**Date**: 2025-12-21
**Status**: 🔥 **EMERGENCY - CATASTROPHIC LATENCY ISSUE**
**Related**: [01_ARCHITECTURE.md](./01_ARCHITECTURE.md)

---

## Executive Summary

⚠️ **CRITICAL ISSUE**: The Legal RAG Engine V1.1 has **catastrophic latency problems** that make it **unusable in production**.

- **Current latency**: 28.7s avg / 37.6s p95 (10-15x too slow)
- **Target latency**: <3s avg / <5s p95
- **Root cause**: Sequential LLM calls + slow model choice
- **Impact**: **System cannot be deployed** until fixed

This document outlines **17 actionable fixes** (4 emergency latency fixes + 13 quality improvements) across 3 priority levels.

**Overall Grade**: C+ (70/100) - **Excellent architecture, catastrophic performance**
**Status**: 🔴 **NOT production-ready** until P0-0 latency fixes are deployed

---

## Priority 0 - Critical Fixes (Do First)

### **⚠️ P0-0: FIX CATASTROPHIC LATENCY (28.7s avg / 37.6s p95)**

**CRITICAL EMERGENCY - DO THIS FIRST**

**Current State**: System is **10-15x slower than acceptable**
- Average: **28.7s** (target: <3s)
- P95: **37.6s** (target: <5s)
- Range: 14s - 40s

**Root Cause Analysis**:

1. **Sequential LLM calls** (cannot parallelize):
   ```
   Intent Classification (8-12s)
        ↓
   Query Expansion (8-12s, 50% of queries)
        ↓
   Answer Generation (8-12s)
   = 24-36 seconds total
   ```

2. **Using `gemini-2.0-flash-lite`** which is surprisingly slow
3. **No caching** - every similar query pays full cost
4. **No parallelization** - calls are sequential

**IMMEDIATE FIXES (P0-0a, b, c)**:

#### **P0-0a: Switch to Faster Model** (2 hours, -50% latency)

```python
# In settings.py - CHANGE THIS NOW
GEMINI_CHAT_MODEL = os.getenv('GEMINI_CHAT_MODEL', 'gemini-1.5-flash-8b')  # Much faster
# OR
GEMINI_CHAT_MODEL = os.getenv('GEMINI_CHAT_MODEL', 'gemini-2.0-flash-thinking-exp')  # Fast + better

# Deploy:
# export GEMINI_CHAT_MODEL=gemini-1.5-flash-8b
```

**Expected**: 28.7s → **15s avg** (50% reduction)

#### **P0-0b: Parallelize Intent + Expansion** (4 hours, -30% latency)

```python
# In legal_rag_engine_v1_1.py answer_query()
import concurrent.futures

def answer_query(self, query: str, **kwargs):
    # ... meta query check ...

    # PARALLELIZE intent classification + query expansion
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        # Submit both tasks simultaneously
        intent_future = executor.submit(
            self.intent_classifier.classify_with_confidence, query
        )
        expansion_future = executor.submit(
            self.query_expander.expand,
            query,
            max_total=4,
            llm_variants=1
        )

        # Wait for both
        area_classification = intent_future.result()
        expanded_queries = expansion_future.result()

    # Continue with retrieval...
```

**Expected**: 15s → **10s avg** (30% reduction from sequential)

#### **P0-0c: Add Intent Classification Cache** (2 hours, -20% latency)

```python
# In intent_classifier.py
from collections import OrderedDict
import hashlib

class IntentClassifier:
    def __init__(self):
        self._cache: OrderedDict[str, dict] = OrderedDict()
        self._cache_max_size = 1000

    def classify_with_confidence(self, query: str) -> dict:
        # Normalize and cache
        cache_key = hashlib.md5(query.lower().strip().encode()).hexdigest()

        if cache_key in self._cache:
            self._cache.move_to_end(cache_key)
            cached = self._cache[cache_key]
            logger.info(f"Intent cache HIT: {cached['area']}")
            return cached

        # ... existing classification ...

        # Store in cache
        result = {"area": area, "confidence": confidence, "scores": scores}
        self._cache[cache_key] = result
        self._cache.move_to_end(cache_key)

        while len(self._cache) > self._cache_max_size:
            self._cache.popitem(last=False)

        return result
```

**Expected**: 10s → **8s avg** (20% cache hit reduction)

#### **P0-0d: Disable Query Expansion for Simple Queries** (1 hour, -15% latency)

```python
# In _build_retrieval_plan()
def _build_retrieval_plan(self, query, intent_confidence, router_decision):
    token_count = len(re.findall(r"\w+", query or ""))
    mode = (router_decision or {}).get("mode") if router_decision else None
    is_follow_up = mode in {"FOLLOWUP_SLOT_FILL", "FOLLOWUP_REFERENTIAL"}
    simple = token_count <= 8

    # DISABLE LLM expansion for most queries
    if is_follow_up or simple or intent_confidence >= 0.7:
        return {
            "max_total": 2,
            "llm_variants": 0,  # NO LLM expansion
            "per_query_limit": 8,
            "mode": "light",
        }

    # Only expand complex, low-confidence queries
    if intent_confidence < 0.5:
        return {
            "max_total": 4,
            "llm_variants": 1,  # Reduced from 3
            "per_query_limit": 12,
            "mode": "balanced",
        }

    return {
        "max_total": 2,
        "llm_variants": 0,  # Default: no expansion
        "per_query_limit": 8,
        "mode": "light",
    }
```

**Expected**: 8s → **6.8s avg** (15% fewer LLM calls)

#### **Combined Impact**:
- P0-0a (model switch): 28.7s → 15s
- P0-0b (parallelization): 15s → 10s
- P0-0c (intent cache): 10s → 8s
- P0-0d (disable expansion): 8s → 6.8s

**TOTAL: 28.7s → 6.8s (76% reduction)**

**Implementation Priority**:
1. **P0-0a** (2h) - Deploy immediately, biggest impact
2. **P0-0d** (1h) - Quick win, disable wasteful expansion
3. **P0-0c** (2h) - Add caching
4. **P0-0b** (4h) - Parallelization (most complex)

**Total effort**: 9 hours to fix catastrophic latency

---

### P0-1: Re-enable Judge Pipeline

**File**: [legal_rag_engine_v1_1.py:805-808](../backend/apps/legal_graphrag/services/v1_1/legal_rag_engine_v1_1.py#L805-L808)

**Current State**:
```python
# Step 11: Judge (DISABLED)
judge_result = {"verdict": "PASS", "reasons": ["judge_disabled_v1.1"]}
redo_performed = False
```

**Problem**:
- No quality gating on LLM outputs
- Hallucinations can slip through undetected
- Cannot auto-recover from poor answers
- Judge system exists but is completely disabled

**Impact**: High - Affects answer quality and user trust

**Recommended Fix**:
```python
# Re-enable with lightweight checks
judge_result = self.judge.evaluate_answer(
    query=query,
    answer=answer_text,
    sources=sources,
    area_principal=area_principal
)

if judge_result["verdict"] == "FAIL":
    # Log the failure
    self.flow_logger.log_judge_failure(judge_result["reasons"])

    # Option 1: Retry with different prompt
    if not redo_performed:
        answer_text = self._retry_with_stricter_prompt(query, sources)
        redo_performed = True

    # Option 2: Add disclaimer
    else:
        answer_text = self._add_low_confidence_disclaimer(answer_text)
```

**Effort**: 4-6 hours
**Files to modify**:
- `legal_rag_engine_v1_1.py` (lines 805-808)
- `judge_v1_1.py` (review and tune thresholds)

---

### P0-2: Fix Citation Extraction Fragility

**File**: [legal_rag_engine_v1_1.py:620-649, 779-791](../backend/apps/legal_graphrag/services/v1_1/legal_rag_engine_v1_1.py#L620-L649)

**Current State**:
```python
# Tries HTML comment first
<!--CITED_IDS: BOE-A-XXXX-XXXXX, BOE-A-YYYY-YYYYY -->

# Falls back to [ID: ...] markers
cited_ids.update(re.findall(r"\[ID:\s*([^\]]+)\]", answer))

# Fallback: if no citations, use first normativa source
if not cited_ids and not abstained:
    for item in sources.get("normativa", []):
        doc_id = item.get("document_id")
        if doc_id:
            cited_ids.add(doc_id)
            break
```

**Problems**:
1. LLM may forget to include HTML comment (not in training data)
2. Dual-format support adds complexity
3. Fallback to normativa[0] is arbitrary and misleading
4. No validation that cited sources were actually used in answer

**Impact**: High - Incorrect source attribution undermines trust

**Recommended Fix Option 1 - Structured Output** (Preferred):
```python
# Use Gemini's structured output feature
response_schema = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "cited_document_ids": {
            "type": "array",
            "items": {"type": "string"}
        }
    },
    "required": ["answer", "cited_document_ids"]
}

response = self.model.generate_content(
    prompt,
    generation_config={"response_mime_type": "application/json"}
)

result = json.loads(response.text)
answer_text = result["answer"]
cited_ids = set(result["cited_document_ids"])
```

**Recommended Fix Option 2 - Post-hoc Extraction**:
```python
def _extract_citations_from_answer(self, answer: str, sources: Dict) -> set:
    """Extract citations by checking which sources appear in answer."""
    cited_ids = set()

    for naturaleza, chunks in sources.items():
        for chunk in chunks:
            doc_id = chunk.get("document_id")
            doc_title = chunk.get("document_title", "")
            chunk_label = chunk.get("chunk_label", "")

            # Check if this source is referenced in the answer
            if doc_id and (
                doc_id in answer or
                doc_title in answer or
                (chunk_label and chunk_label in answer)
            ):
                cited_ids.add(doc_id)

    return cited_ids
```

**Effort**: 6-8 hours
**Files to modify**:
- `legal_rag_engine_v1_1.py` (citation extraction logic)
- Prompt template (remove HTML comment instructions if using structured output)

---

### P0-3: Add Query Expansion Caching

**File**: [query_expander_v1_1.py:99-149](../backend/apps/legal_graphrag/services/v1_1/query_expander_v1_1.py#L99-L149)

**Current State**:
```python
# LLM expansion called on EVERY query (no caching)
if self.model and len(queries) < max_total and llm_variants > 0:
    prompt = f"""Genera hasta {llm_variants} variantes..."""
    response = self.model.generate_content(prompt)  # 300ms per call
```

**Problems**:
1. ~50% of queries trigger LLM expansion (balanced/heavy mode)
2. Each LLM call adds 200-400ms latency
3. Similar queries generate same expansions (wasteful)
4. No cache means repeated cost for common queries

**Impact**: Medium-High - Adds 30-50% to retrieval latency

**Recommended Fix**:
```python
import hashlib
from collections import OrderedDict

class QueryExpanderV1_1:
    def __init__(self, model) -> None:
        self.model = model
        # LRU cache for expansions
        self._expansion_cache: OrderedDict[str, List[str]] = OrderedDict()
        self._cache_max_size = 500

    def _get_cache_key(self, query: str, max_total: int, llm_variants: int) -> str:
        """Generate cache key for query expansion."""
        normalized = self._to_ascii(query.lower().strip())
        key = f"{normalized}:{max_total}:{llm_variants}"
        return hashlib.md5(key.encode()).hexdigest()

    def expand(self, query: str, max_total: int = 8, llm_variants: int = 3) -> List[str]:
        # Check cache first
        cache_key = self._get_cache_key(query, max_total, llm_variants)
        if cache_key in self._expansion_cache:
            self._expansion_cache.move_to_end(cache_key)
            return self._expansion_cache[cache_key]

        # ... existing expansion logic ...

        # Store in cache
        self._expansion_cache[cache_key] = queries
        self._expansion_cache.move_to_end(cache_key)

        # Evict old entries
        while len(self._expansion_cache) > self._cache_max_size:
            self._expansion_cache.popitem(last=False)

        return queries
```

**Expected Improvement**:
- Cache hit rate: 40-60% (common queries)
- Latency reduction: 200-400ms per cache hit
- Cost reduction: 40-60% fewer LLM calls

**Effort**: 2-3 hours
**Files to modify**:
- `query_expander_v1_1.py`

---

## Priority 1 - Important Improvements (Do Soon)

### P1-1: Relax Abstain Logic

**File**: [legal_rag_engine_v1_1.py:975-1039](../backend/apps/legal_graphrag/services/v1_1/legal_rag_engine_v1_1.py#L975-L1039)

**Current State**:
```python
# Hard-coded token matching for IVA queries
if "iva" in norm_query and self._is_rate_seeking_query(query):
    iva_tokens = ["iva", "impuesto sobre el valor añadido", "tipo impositivo"]
    if not any(self._source_matches_tokens(src, iva_tokens) ...):
        return True  # Abstain
```

**Problems**:
1. Exact token matching misses valid paraphrases
2. Rate-seeking special case may abstain on conceptual IVA questions
3. `_min_strict_matches=1` is very low tolerance (any miss → abstain)
4. No semantic similarity - relies only on string matching

**Impact**: Medium - Too many false abstains on valid questions

**Recommended Fix**:
```python
def _source_matches_tokens_semantic(
    self,
    source: Dict[str, Any],
    tokens: List[str],
    threshold: float = 0.7
) -> bool:
    """Check if source matches tokens using semantic similarity."""
    source_text = self._normalize_text(
        source.get("chunk_text", "") + " " +
        source.get("chunk_label", "")
    )

    # Fall back to exact matching for short tokens
    for token in tokens:
        if len(token) <= 4 and token in source_text:
            return True

    # Use embedding similarity for longer phrases
    if len(tokens) > 0:
        source_embedding = self.embedding_service.embed(source_text[:500])

        for token in tokens:
            if len(token) > 4:
                token_embedding = self.embedding_service.embed(token)
                similarity = cosine_similarity(source_embedding, token_embedding)
                if similarity >= threshold:
                    return True

    return False

# Adjust thresholds
self._min_strict_matches = 0  # Allow conceptual matches
self._min_token_matches = 1   # Keep at 1
self._semantic_match_threshold = 0.7  # Tune based on eval
```

**Alternative - Make configurable**:
```python
# In settings.py
RAG_MIN_STRICT_MATCHES = int(os.getenv('RAG_MIN_STRICT_MATCHES', '0'))
RAG_MIN_TOKEN_MATCHES = int(os.getenv('RAG_MIN_TOKEN_MATCHES', '1'))
RAG_SEMANTIC_THRESHOLD = float(os.getenv('RAG_SEMANTIC_THRESHOLD', '0.7'))
```

**Effort**: 4-6 hours
**Files to modify**:
- `legal_rag_engine_v1_1.py` (abstain logic)
- `legal_rag_engine.py` (base class)
- `settings.py` (add config)

---

### P1-2: Add Retrieval Quality Benchmarks

**Current State**: No automated retrieval metrics

**Problems**:
1. No quantitative measure of retrieval quality
2. Cannot detect retrieval regressions
3. Hard to compare different retrieval strategies
4. Eval is manual (50-case chat evaluation)

**Impact**: Medium - Cannot measure improvements objectively

**Recommended Fix - Add Benchmark Suite**:

**Step 1 - Create benchmark dataset**:
```python
# File: backend/apps/legal_graphrag/tests/fixtures/retrieval_benchmark.json
[
  {
    "query": "¿Cuál es el tipo de IVA para servicios culturales?",
    "area": "Fiscal",
    "relevant_docs": [
      "BOE-A-1992-28740",  # Ley 37/1992 IVA
      "BOE-A-2006-20764"   # LIRPF (deductions)
    ],
    "expected_top_k": 5,
    "must_include": ["BOE-A-1992-28740"]
  },
  // ... 50-100 cases
]
```

**Step 2 - Create benchmark runner**:
```python
# File: backend/apps/legal_graphrag/tests/test_retrieval_benchmark.py
import pytest
from apps.legal_graphrag.services.v1_1.legal_rag_engine_v1_1 import LegalRAGEngineV1_1

def calculate_mrr(retrieved_ids: List[str], relevant_ids: List[str]) -> float:
    """Mean Reciprocal Rank."""
    for rank, doc_id in enumerate(retrieved_ids, 1):
        if doc_id in relevant_ids:
            return 1.0 / rank
    return 0.0

def calculate_recall_at_k(retrieved_ids: List[str], relevant_ids: List[str], k: int) -> float:
    """Recall@K."""
    retrieved_set = set(retrieved_ids[:k])
    relevant_set = set(relevant_ids)
    if not relevant_set:
        return 0.0
    return len(retrieved_set & relevant_set) / len(relevant_set)

class TestRetrievalBenchmark:
    @pytest.fixture
    def engine(self):
        return LegalRAGEngineV1_1()

    @pytest.fixture
    def benchmark_cases(self):
        import json
        with open('fixtures/retrieval_benchmark.json') as f:
            return json.load(f)

    def test_retrieval_metrics(self, engine, benchmark_cases):
        mrr_scores = []
        recall_at_5_scores = []
        recall_at_10_scores = []

        for case in benchmark_cases:
            # Retrieve
            sources, trace = engine._retrieve_hierarchical_sources_v1_1(
                query=case['query'],
                area_principal=case['area'],
                max_sources=10,
                expansion_max_total=4,
                expansion_llm_variants=1,
                per_query_limit=10,
                session_id='benchmark',
                intent_confidence=1.0,
                router_decision=None
            )

            # Extract retrieved IDs
            retrieved_ids = [
                src.get('document_id')
                for bucket in sources.values()
                for src in bucket
                if src.get('document_id')
            ]

            relevant_ids = case['relevant_docs']

            # Calculate metrics
            mrr_scores.append(calculate_mrr(retrieved_ids, relevant_ids))
            recall_at_5_scores.append(calculate_recall_at_k(retrieved_ids, relevant_ids, 5))
            recall_at_10_scores.append(calculate_recall_at_k(retrieved_ids, relevant_ids, 10))

            # Check must-include docs
            if 'must_include' in case:
                for must_doc in case['must_include']:
                    assert must_doc in retrieved_ids[:10], \
                        f"Must-include doc {must_doc} not in top-10 for query: {case['query']}"

        # Report metrics
        avg_mrr = sum(mrr_scores) / len(mrr_scores)
        avg_recall_5 = sum(recall_at_5_scores) / len(recall_at_5_scores)
        avg_recall_10 = sum(recall_at_10_scores) / len(recall_at_10_scores)

        print(f"\n=== Retrieval Benchmark Results ===")
        print(f"MRR: {avg_mrr:.3f}")
        print(f"Recall@5: {avg_recall_5:.3f}")
        print(f"Recall@10: {avg_recall_10:.3f}")

        # Set thresholds (adjust based on baseline)
        assert avg_mrr >= 0.60, f"MRR below threshold: {avg_mrr:.3f}"
        assert avg_recall_5 >= 0.70, f"Recall@5 below threshold: {avg_recall_5:.3f}"
        assert avg_recall_10 >= 0.85, f"Recall@10 below threshold: {avg_recall_10:.3f}"
```

**Step 3 - Add to CI pipeline**:
```yaml
# .github/workflows/test.yml
- name: Run retrieval benchmarks
  run: |
    pytest backend/apps/legal_graphrag/tests/test_retrieval_benchmark.py -v
```

**Effort**: 8-12 hours (includes creating benchmark dataset)
**Files to create**:
- `tests/fixtures/retrieval_benchmark.json`
- `tests/test_retrieval_benchmark.py`

---

### P1-3: Add Diversity to Retrieval

**File**: [legal_search_engine.py:180-249](../backend/apps/legal_graphrag/services/legal_search_engine.py#L180-L249)

**Current State**:
```python
# RRF fusion returns highest scoring chunks
# May return multiple chunks from same document
fused_results = sorted(chunk_scores.items(), key=lambda x: x[1], reverse=True)
```

**Problems**:
1. May retrieve 5 chunks from same document (low diversity)
2. User sees redundant information
3. Misses broader context from other documents

**Impact**: Medium - Reduces answer breadth and coverage

**Recommended Fix - MMR-style Diversity**:
```python
def _reciprocal_rank_fusion(
    self,
    vector_results: List[Dict[str, Any]],
    lexical_results: List[Dict[str, Any]],
    k: int = 60,
    vector_weight: float = 0.6,
    lexical_weight: float = 0.4,
    diversity_lambda: float = 0.7  # 0=max diversity, 1=no diversity
) -> List[Dict[str, Any]]:
    """
    Combine results using RRF with diversity enforcement.

    Uses Maximal Marginal Relevance (MMR) style selection:
    - diversity_lambda=1.0: Pure RRF (no diversity)
    - diversity_lambda=0.5: Balance relevance and diversity
    - diversity_lambda=0.0: Max diversity (greedy document spreading)
    """
    # ... existing RRF scoring ...

    # MMR-style selection with diversity
    fused_results = []
    selected_docs = set()
    remaining_chunks = sorted(chunk_scores.items(), key=lambda x: x[1], reverse=True)

    while remaining_chunks and len(fused_results) < len(chunk_scores):
        # Calculate diversity-adjusted scores
        best_chunk = None
        best_score = -float('inf')

        for chunk_id, rrf_score in remaining_chunks:
            doc_id = chunk_data[chunk_id].get('document_id')

            # Diversity penalty: lower score if document already selected
            doc_count = selected_docs.count(doc_id) if doc_id else 0
            diversity_penalty = 0.3 * doc_count  # 30% penalty per duplicate doc

            # MMR formula: λ * relevance - (1-λ) * diversity_penalty
            mmr_score = (diversity_lambda * rrf_score) - ((1 - diversity_lambda) * diversity_penalty)

            if mmr_score > best_score:
                best_score = mmr_score
                best_chunk = chunk_id

        if best_chunk:
            result = chunk_data[best_chunk]
            result['rrf_score'] = chunk_scores[best_chunk]
            result['mmr_score'] = best_score
            result['search_method'] = 'hybrid'
            fused_results.append(result)

            doc_id = result.get('document_id')
            if doc_id:
                selected_docs.add(doc_id)

            remaining_chunks = [(cid, score) for cid, score in remaining_chunks if cid != best_chunk]

    return fused_results
```

**Alternative - Simple max-per-document limit**:
```python
# Simpler approach: limit chunks per document
def _enforce_diversity(self, results: List[Dict], max_per_doc: int = 2) -> List[Dict]:
    """Limit chunks per document to enforce diversity."""
    doc_counts = {}
    diverse_results = []

    for result in results:
        doc_id = result.get('document_id')
        count = doc_counts.get(doc_id, 0)

        if count < max_per_doc:
            diverse_results.append(result)
            doc_counts[doc_id] = count + 1

    return diverse_results
```

**Effort**: 3-4 hours
**Files to modify**:
- `legal_search_engine.py` (RRF fusion)

---

### P1-4: Improve LLM Prompt with Few-Shot Examples

**File**: [legal_rag_engine_v1_1.py:577-618](../backend/apps/legal_graphrag/services/v1_1/legal_rag_engine_v1_1.py#L577-L618)

**Current State**:
```python
# Only instruction-based, no examples
prompt += (
    "\n\nCITACION OBLIGATORIA:\n"
    "Al final de tu respuesta, incluye un comentario HTML oculto con los IDs de documentos citados:\n\n"
    "<!--CITED_IDS: BOE-A-XXXX-XXXXX, BOE-A-YYYY-YYYYY -->\n\n"
    # ... rules ...
)
```

**Problems**:
1. No examples of good answers
2. No examples of proper citation format
3. No example of abstaining when evidence is weak
4. LLM must infer format from instructions alone

**Impact**: Medium - Inconsistent citation format, occasional format errors

**Recommended Fix - Add Few-Shot Examples**:
```python
def _build_hierarchical_prompt(
    self,
    query: str,
    sources: Dict[str, List[Dict[str, Any]]],
    area_principal: Optional[str]
) -> str:
    prompt = super()._build_hierarchical_prompt(query, sources, area_principal)

    # ... existing modifications ...

    # Add few-shot examples
    prompt += """

EJEMPLOS DE RESPUESTAS CORRECTAS:

Ejemplo 1 - Respuesta con evidencia clara:
---
Usuario: "¿Cuál es el tipo de IVA para servicios culturales?"

Respuesta:
Los servicios culturales tributan al tipo reducido del 10% en el IVA. Según el artículo 91.Uno.2.4º de la Ley 37/1992 del IVA, se aplica este tipo a las prestaciones de servicios relacionadas con exposiciones y ferias de carácter comercial.

<!--CITED_IDS: BOE-A-1992-28740 -->
---

Ejemplo 2 - Respuesta citando múltiples fuentes:
---
Usuario: "¿Qué retenciones aplican a artistas autónomos?"

Respuesta:
Los artistas en régimen de autónomos están sujetos a una retención del 15% sobre sus rendimientos profesionales, según el artículo 101.5.a) de la Ley 35/2006 del IRPF. Sin embargo, durante los tres primeros años de actividad, la retención se reduce al 7%, conforme al artículo 101.5.b) del mismo texto legal.

<!--CITED_IDS: BOE-A-2006-20764 -->
---

Ejemplo 3 - Abstención por falta de evidencia:
---
Usuario: "¿Cuánto cuesta registrar un nombre artístico en España?"

Respuesta:
Lo siento, no dispongo de información específica sobre los costes de registro de nombres artísticos en la documentación legal consultada. Esta información probablemente requiere consultar las tasas oficiales de la Oficina Española de Patentes y Marcas (OEPM) o del Registro Civil.

<!--CITED_IDS: -->
---

AHORA RESPONDE LA PREGUNTA DEL USUARIO SIGUIENDO ESTOS EJEMPLOS:
"""

    return prompt
```

**Expected Improvement**:
- More consistent citation format
- Better abstain behavior when appropriate
- Clearer, more structured answers

**Effort**: 1-2 hours
**Files to modify**:
- `legal_rag_engine_v1_1.py` (prompt building)

---

### P1-5: Optimize Intent Classification with Haiku

**File**: [legal_rag_engine.py:86-89](../backend/apps/legal_graphrag/services/legal_rag_engine.py#L86-L89)

**Current State**:
```python
# Uses Gemini Flash for all LLM calls
self.model = genai.GenerativeModel(
    model_name=getattr(settings, 'GEMINI_CHAT_MODEL', 'gemini-2.5-flash')
)
```

**Problems**:
1. Intent classification uses same model as answer generation
2. Flash model is overkill for simple classification
3. Adds ~200ms latency per query
4. Higher cost than necessary

**Impact**: Low-Medium - 15% of total latency, unnecessary cost

**Recommended Fix**:
```python
# In legal_rag_engine.py
class LegalRAGEngine:
    def __init__(self):
        # ... existing code ...

        # Separate models for different tasks
        self.classification_model = genai.GenerativeModel(
            model_name=getattr(settings, 'GEMINI_CLASSIFICATION_MODEL', 'gemini-2.0-flash')
        )
        self.generation_model = genai.GenerativeModel(
            model_name=getattr(settings, 'GEMINI_CHAT_MODEL', 'gemini-2.5-flash')
        )

        # Backward compatibility
        self.model = self.generation_model

# In intent_classifier.py
class IntentClassifier:
    def __init__(self, model=None):
        if model is None:
            # Use cheaper model for classification
            genai.configure(api_key=settings.GEMINI_API_KEY)
            self.model = genai.GenerativeModel(
                model_name=getattr(settings, 'GEMINI_CLASSIFICATION_MODEL', 'gemini-2.0-flash')
            )
        else:
            self.model = model

# In settings.py
GEMINI_CLASSIFICATION_MODEL = os.getenv('GEMINI_CLASSIFICATION_MODEL', 'gemini-2.0-flash')
GEMINI_CHAT_MODEL = os.getenv('GEMINI_CHAT_MODEL', 'gemini-2.5-flash')
```

**Expected Improvement**:
- 30-50% faster intent classification (200ms → 100ms)
- 50% cost reduction for classification calls
- No quality loss (classification is simpler task)

**Effort**: 2-3 hours
**Files to modify**:
- `legal_rag_engine.py`
- `intent_classifier.py`
- `settings.py`

---

## Priority 2 - Future Enhancements (Post-MVP)

### P2-1: Add Cross-Encoder Reranking

**Current State**: Uses RRF fusion only

**Recommended Approach**:
```python
from sentence_transformers import CrossEncoder

class LegalSearchEngine:
    def __init__(self):
        # ... existing code ...
        self.reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')

    def hybrid_search(self, query: str, limit: int = 10, rerank: bool = True):
        # ... existing RRF fusion ...

        if rerank and len(fused_results) > limit:
            # Rerank top-N candidates
            candidates = fused_results[:limit * 3]
            pairs = [(query, chunk['chunk_text']) for chunk in candidates]
            scores = self.reranker.predict(pairs)

            for chunk, score in zip(candidates, scores):
                chunk['rerank_score'] = score

            # Re-sort by rerank score
            fused_results = sorted(candidates, key=lambda x: x['rerank_score'], reverse=True)

        return fused_results[:limit]
```

**Effort**: 6-8 hours
**Expected Improvement**: +5-10% retrieval quality (MRR, Recall@K)

---

### P2-2: Query-Adaptive RRF Weights

**Current State**: Fixed weights (vector=0.6, lexical=0.4)

**Recommended Approach**:
```python
def _adaptive_weights(self, query: str) -> Tuple[float, float]:
    """Choose weights based on query characteristics."""

    # Legal citations → higher lexical weight
    if re.search(r'BOE-A-\d{4}-\d+|Ley \d+/\d{4}|Art\w*\.\s*\d+', query):
        return 0.3, 0.7  # lexical-heavy

    # Conceptual questions → higher vector weight
    if any(word in query.lower() for word in ['qué es', 'cómo funciona', 'diferencia entre']):
        return 0.8, 0.2  # vector-heavy

    # Default balanced
    return 0.6, 0.4
```

**Effort**: 3-4 hours
**Expected Improvement**: +2-5% retrieval quality on specific query types

---

### P2-3: Add Support for ECLI Citations (Jurisprudence)

**File**: [reference_resolver.py:19-24](../backend/apps/legal_graphrag/services/v1_1/reference_resolver.py#L19-L24)

**Current State**: Only supports BOE IDs, law titles, articles

**Recommended Enhancement**:
```python
class ExactReferenceResolver:
    ECLI_PATTERN = re.compile(r'\bECLI:ES:[A-Z]+:\d{4}:\d+\b', re.IGNORECASE)
    ORGANIC_LAW_PATTERN = re.compile(r'\bLey Orgánica\s+\d+/\d{4}\b', re.IGNORECASE)
    RD_LEG_PATTERN = re.compile(r'\bReal Decreto Legislativo\s+\d+/\d{4}\b', re.IGNORECASE)

    def _parse_references(self, query: str) -> dict:
        return {
            'boe_id': self.BOE_ID_PATTERN.search(query),
            'ecli': self.ECLI_PATTERN.search(query),
            'law_title': self.LAW_PATTERN.search(query),
            'organic_law': self.ORGANIC_LAW_PATTERN.search(query),
            'rd_leg': self.RD_LEG_PATTERN.search(query),
            'article': self.ARTICLE_PATTERN.search(query)
        }
```

**Effort**: 4-6 hours
**Expected Improvement**: Better handling of jurisprudence queries

---

### P2-4: Refactor `answer_query()` Method

**File**: [legal_rag_engine_v1_1.py:651-953](../backend/apps/legal_graphrag/services/v1_1/legal_rag_engine_v1_1.py#L651-L953)

**Current State**: 303-line monolithic method

**Recommended Refactor**:
```python
class LegalRAGEngineV1_1(LegalRAGEngine):
    def answer_query(self, query: str, **kwargs) -> Dict[str, Any]:
        """Main entry point - orchestrates pipeline stages."""
        self.flow_logger.start_query(query, session_id=kwargs.get('session_id'))

        # Stage 1: Query understanding
        if self._is_meta_query(query):
            return self._handle_meta_query(query)

        intent_info = self._classify_intent(query, kwargs)

        # Stage 2: Retrieval
        sources, trace = self._retrieve_and_filter(query, intent_info, kwargs)

        # Stage 3: Generation
        answer_info = self._generate_answer(query, sources, intent_info, kwargs)

        # Stage 4: Post-processing
        result = self._post_process_answer(answer_info, sources, trace, intent_info)

        self.flow_logger.finish_and_write()
        return result

    def _classify_intent(self, query: str, kwargs: dict) -> dict:
        """Extract to separate method."""
        # Lines 691-712
        pass

    def _retrieve_and_filter(self, query: str, intent_info: dict, kwargs: dict) -> tuple:
        """Extract to separate method."""
        # Lines 714-730
        pass

    def _generate_answer(self, query: str, sources: dict, intent_info: dict, kwargs: dict) -> dict:
        """Extract to separate method."""
        # Lines 732-754
        pass

    def _post_process_answer(self, answer_info: dict, sources: dict, trace: dict, intent_info: dict) -> dict:
        """Extract to separate method."""
        # Lines 756-953
        pass
```

**Effort**: 6-8 hours
**Benefit**: Better code organization, easier testing, clearer flow

---

## Configuration & Tuning

### Recommended Settings to Externalize

Add to `settings.py`:
```python
# RAG Engine Configuration
RAG_MIN_STRICT_MATCHES = int(os.getenv('RAG_MIN_STRICT_MATCHES', '0'))
RAG_MIN_TOKEN_MATCHES = int(os.getenv('RAG_MIN_TOKEN_MATCHES', '1'))
RAG_SEMANTIC_THRESHOLD = float(os.getenv('RAG_SEMANTIC_THRESHOLD', '0.7'))

# Query Expansion
RAG_EXPANSION_CACHE_SIZE = int(os.getenv('RAG_EXPANSION_CACHE_SIZE', '500'))
RAG_EXPANSION_ENABLE_LLM = os.getenv('RAG_EXPANSION_ENABLE_LLM', 'true').lower() == 'true'

# Retrieval
RAG_RETRIEVAL_CACHE_SIZE = int(os.getenv('RAG_RETRIEVAL_CACHE_SIZE', '64'))
RAG_HYBRID_VECTOR_WEIGHT = float(os.getenv('RAG_HYBRID_VECTOR_WEIGHT', '0.6'))
RAG_HYBRID_LEXICAL_WEIGHT = float(os.getenv('RAG_HYBRID_LEXICAL_WEIGHT', '0.4'))
RAG_DIVERSITY_LAMBDA = float(os.getenv('RAG_DIVERSITY_LAMBDA', '0.7'))

# Generation
GEMINI_CLASSIFICATION_MODEL = os.getenv('GEMINI_CLASSIFICATION_MODEL', 'gemini-2.0-flash')
GEMINI_EXPANSION_MODEL = os.getenv('GEMINI_EXPANSION_MODEL', 'gemini-2.0-flash')
GEMINI_CHAT_MODEL = os.getenv('GEMINI_CHAT_MODEL', 'gemini-2.5-flash')

# Judge
RAG_JUDGE_ENABLED = os.getenv('RAG_JUDGE_ENABLED', 'true').lower() == 'true'
RAG_JUDGE_RETRY_ENABLED = os.getenv('RAG_JUDGE_RETRY_ENABLED', 'false').lower() == 'true'
```

---

## Testing Requirements

### New Tests Needed

1. **Retrieval Benchmark Suite** (P1-2)
   - 50-100 test cases with ground truth
   - MRR, Recall@K, NDCG metrics
   - Regression detection

2. **Citation Extraction Tests**
   - Structured output parsing
   - Fallback handling
   - Edge cases (no citations, invalid IDs)

3. **Judge Pipeline Tests**
   - Quality detection
   - Retry logic
   - Edge cases

4. **Abstain Logic Tests**
   - Semantic matching
   - Configurable thresholds
   - False positive/negative rates

5. **Performance Tests**
   - Latency benchmarks per stage
   - Cache hit rate monitoring
   - Load testing

---

## Success Metrics

Track these metrics before/after improvements:

| Metric | Current | Target | Priority |
|--------|---------|--------|----------|
| **Latency (p50)** | **28.7s** 🔥 | <3.0s | **P0-0 (ALL)** |
| **Latency (p95)** | **37.6s** 🔥 | <5.0s | **P0-0 (ALL)** |
| **Citation Accuracy** | ~70% | >90% | P0-2 |
| **Abstain False Positive Rate** | ~15% | <5% | P1-1 |
| **MRR** | Unknown | >0.70 | P1-2 |
| **Recall@5** | Unknown | >0.80 | P1-2 |
| **Recall@10** | Unknown | >0.90 | P1-2 |
| **Cache Hit Rate** | 0% | >50% | P0-3 |
| **LLM Calls per Query** | 2.5 | <2.0 | P0-3, P1-5 |

---

## Implementation Roadmap

### Week 1 - EMERGENCY LATENCY FIXES (P0)

**⚠️ DO THESE IMMEDIATELY - System is unusably slow**

#### Day 1-2 (Critical Path):
- [x] **P0-0a**: Switch to gemini-1.5-flash-8b (2h) ← **DO THIS FIRST**
- [x] **P0-0d**: Disable query expansion for simple queries (1h)
- [x] **P0-0c**: Add intent classification cache (2h)
- [x] **P0-0b**: Parallelize intent + expansion (4h)
- [ ] Validate latency improvements (2h)

**Expected result**: 28.7s → **6.8s avg** (76% reduction)

#### Day 3-5 (Quality Fixes):
- [x] P0-1: Re-enable judge pipeline (4-6h)
- [x] P0-2: Fix citation extraction (6-8h)
- [x] P0-3: Move expansion caching to query_expander (2h)
- [ ] Test and validate fixes (4h)

**Total effort**: ~29 hours

### Week 2 - Important Improvements (P1)
- [x] P1-1: Relax abstain logic (4-6h)
- [x] P1-2: Add retrieval benchmarks (8-12h)
- [x] P1-3: Add diversity to retrieval (3-4h)
- [x] P1-4: Improve prompt with few-shot (1-2h)
- [ ] P1-5: Optimize with Haiku (2-3h)

**Total effort**: ~24 hours

### Week 3+ - Future Enhancements (P2)
- [x] P2-1: Cross-encoder reranking (6-8h)
- [x] P2-2: Query-adaptive weights (3-4h)
- [x] P2-3: ECLI citation support (4-6h)
- [x] P2-4: Refactor answer_query (6-8h)

**Total effort**: ~24 hours

---

## Monitoring & Alerts

### Recommended Monitoring

1. **Performance**
   - Latency by pipeline stage (retrieval, generation, post-processing)
   - Cache hit rates (expansion, retrieval)
   - LLM call counts and costs

2. **Quality**
   - Abstain rate by area
   - Citation accuracy (manual spot checks)
   - Judge verdict distribution

3. **Errors**
   - LLM API failures
   - Database query failures
   - Post-processing errors

### Recommended Alerts

```python
# Alert if latency p95 > 5s
if latency_p95 > 5000:
    alert("High latency detected")

# Alert if abstain rate > 20%
if abstain_rate > 0.20:
    alert("Excessive abstain rate")

# Alert if citation extraction fails > 10%
if citation_error_rate > 0.10:
    alert("Citation extraction issues")

# Alert if cache hit rate < 30%
if cache_hit_rate < 0.30:
    alert("Low cache effectiveness")
```

---

## Conclusion

This document outlines **13 actionable improvements** across 3 priority levels. Implementing P0 and P1 items will:

1. **Improve quality** - Judge pipeline, better citations, relaxed abstain
2. **Reduce latency** - Caching, cheaper models (2.5s → 2.0s p50)
3. **Lower costs** - 40-50% fewer LLM calls
4. **Better observability** - Retrieval benchmarks, metrics

**Next Steps**:
1. Review and prioritize items with team
2. Create GitHub issues for each P0/P1 item
3. Implement in priority order
4. Monitor metrics before/after

---

**Document End** | For questions, see [Architecture](./01_ARCHITECTURE.md) or contact the team.
