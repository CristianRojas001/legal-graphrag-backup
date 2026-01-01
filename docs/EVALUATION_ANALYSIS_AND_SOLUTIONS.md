# Evaluation Analysis & Solution Proposals

**Date:** 2025-12-27
**Evaluation:** 50-case comprehensive test
**Status:** 3 quality gates failed, root causes identified

---

## Executive Summary

The 50-case evaluation revealed **two distinct failure patterns**:

1. **Abstention False Positives (8 cases)**: System abstaining on answerable questions
2. **Citation Failures (20 cases)**: Two sub-patterns:
   - **Pattern A**: Found right documents but didn't cite them (e.g., F02)
   - **Pattern B**: No documents retrieved at all, triggered abstention (e.g., F04)

**Key Insight**: Pattern B is actually an **abstention problem disguised as a citation problem**. The real issues are:
- 8 pure abstention failures (F04, F05 turn 2, etc.)
- ~12 actual citation extraction failures (F02, A43, A45, etc.)

---

## Issue 1: Abstention False Positives (Primary Issue)

### Current Behavior

```python
# settings.py
RAG_MIN_STRICT_MATCHES = 0  # No strict requirement
RAG_MIN_TOKEN_MATCHES = 1   # Require at least 1 token match

# Abstention logic (legal_rag_engine_v1_1.py:1437-1508)
def _should_abstain(...):
    # Gate 1: Zero sources → abstain (CORRECT)
    if total_sources == 0:
        return True

    # Gate 2: Strict tokens (law names) - DISABLED (min=0)
    if strict_matches < self._min_strict_matches:  # 0, so never triggers
        return True

    # Gate 3: Priority sources check
    priority_sources = len(normativa) + len(doctrina)
    if priority_sources < 1:  # PROBLEM: Too strict!
        return True

    # Gate 4: Token matching
    if token_matches < self._min_token_matches:  # Need >= 1
        return True
```

### What's Failing

**Case F04**: "Facturo a una empresa española como artista. ¿Debo aplicar retención?"
- **Expected**: Answer with IRPF (BOE-A-2006-20764) + LGT (BOE-A-2003-23186)
- **Actual**: Abstained (no sources retrieved)
- **Root cause**: Gate 3 triggered - found 0 normativa sources

**Case F05 (turn 2)**: "Por ejemplo, cliente empresa con VAT ID"
- **Expected**: Answer with IVA law + EU directive
- **Actual**: Abstained
- **Root cause**: Follow-up query too vague, retrieval failed → Gate 1 or 3

### Root Cause Analysis

The abstention logic has **layered gates** that are too conservative:

1. ✅ **Gate 1 (zero sources)**: Correct - can't answer without any sources
2. ⚠️ **Gate 2 (strict tokens)**: Currently disabled, working as intended
3. ❌ **Gate 3 (priority sources < 1)**: **TOO STRICT** - requires at least 1 normativa/doctrina
   - Problem: If retrieval finds only jurisprudencia or FAQ docs, it abstains
   - Should be: Accept ANY source type if relevant
4. ⚠️ **Gate 4 (token matching)**: Works, but threshold=1 might be too high for broad questions

### Why This Happens

**Retrieval failure cascade**:
```
Query: "¿Debo aplicar retención?"
  ↓
Area filter: "Fiscal" → matches all 14 fiscal docs ✅
  ↓
Vector + Lexical search: "retención" "artista" "empresa"
  ↓
Problem: Query is conceptual, not specific enough to match article text
  ↓
Retrieved: 0-2 low-scoring chunks (below relevance threshold)
  ↓
Gate 3: priority_sources < 1 → ABSTAIN ❌
```

**The real issue**: Retrieval is failing on conceptual questions that don't contain specific legal terms.

---

## Issue 2: Citation Extraction Failures

### Pattern A: Found Documents But Didn't Cite

**Case F02**: "Soy ilustradora y trabajo desde casa. ¿Puedo deducir parte del alquiler?"
- **Retrieved**: BOE-A-2006-20764 (IRPF law) ✅
- **Cited**: NONE ❌
- **Additional**: BOE-A-2006-20764 (listed as "retrieved but not cited")

**This means**:
1. ✅ Retrieval worked (found the right law)
2. ✅ Abstention logic passed (didn't abstain)
3. ❌ LLM generated answer WITHOUT citing the source it used

### Pattern B: Found Wrong Documents

**Case A43**: "¿Cuándo me conviene ser autónomo vs crear una SL?"
- **Expected**: BOE-A-2006-20764 (IRPF), BOE-A-2014-12328 (Sociedades)
- **Cited**: BOE-A-2022-4583 (wrong law, repeated 3x)
- **Additional**: BOE-A-1985-17303 (also wrong - labor law)

**This means**:
1. ❌ Retrieval found wrong documents (labor laws instead of fiscal/corporate)
2. ✅ Abstention logic passed
3. ⚠️ LLM cited what it retrieved (but wrong docs)

### Root Cause Analysis

**Citation Pattern A** (found but didn't cite):
- **Issue**: LLM not following citation instructions in prompt
- **Frequency**: ~12 cases
- **Severity**: Medium (answer quality likely OK, just missing formal citation)

**Citation Pattern B** (cited wrong docs):
- **Issue**: Retrieval returning irrelevant documents
- **Frequency**: ~8 cases
- **Severity**: High (wrong legal guidance!)

**Why LLM doesn't cite retrieved sources**:
```python
# Prompt includes citation instructions:
"**En la práctica, SIEMPRE cita mediante <!--CITED_IDS: BOE-..., BOE-... -->**"

# But LLM might skip if:
1. Retrieved chunk text is generic/not specific enough
2. LLM doesn't find direct answer in chunk text
3. LLM relies on parametric knowledge instead of retrieved context
```

---

## Solution Proposals

### Solution 1: Fix Abstention Logic (Highest Impact)

**Problem**: Gate 3 (`priority_sources < 1`) is too strict

**Proposed Fix A - Lower threshold** (conservative):
```python
# BEFORE:
if priority_sources < 1:
    return True

# AFTER:
if priority_sources < 1 and total_sources < 2:
    # Only abstain if we have <1 normativa AND <2 sources total
    # This allows: 1 jurisprudencia + 1 FAQ = can answer
    return True
```

**Impact**:
- ✅ Reduces false positive abstentions
- ⚠️ Risk: Might answer with low-quality sources (FAQ-only responses)
- **Estimated fix**: 4-6 of 8 abstention failures

**Proposed Fix B - Remove priority source requirement** (aggressive):
```python
# REMOVE Gate 3 entirely
# Keep only Gates 1, 2, 4 (zero sources, strict tokens, token matching)

# Rationale: If sources match tokens AND passed retrieval scoring, trust them
# regardless of source type (normativa vs doctrina vs jurisprudencia)
```

**Impact**:
- ✅ Fixes most abstention failures
- ❌ Risk: Higher chance of low-quality answers from non-authoritative sources
- **Estimated fix**: 7-8 of 8 abstention failures

**Proposed Fix C - Improve retrieval first** (best long-term):
```python
# Don't change abstention logic
# Instead, improve retrieval so conceptual queries find relevant docs

# Options:
1. Query expansion: "retención artista" → "retención IRPF rendimientos trabajo profesional"
2. Boost normativa in ranking (already partially done)
3. Lower similarity thresholds for well-formed queries
4. Hybrid approach: If initial retrieval fails, retry with relaxed filters
```

**Impact**:
- ✅ Addresses root cause (retrieval failure)
- ✅ No risk of lowering answer quality
- ⏱️ Time: Requires more testing/tuning
- **Estimated fix**: 6-8 of 8 failures

**Recommendation**: **Fix C (improve retrieval)** is best, but takes time.
**Quick win**: **Fix A (lower threshold)** as temporary measure.

---

### Solution 2: Fix Citation Extraction

**Problem**: LLM not citing sources even when retrieved

**Proposed Fix A - Stricter prompt** (quick):
```python
# Add to prompt BEFORE examples:
"CRITICAL: You MUST cite every source you reference.
If you mention a law, regulation, or concept from a source,
you MUST include its ID in <!--CITED_IDS: ... -->.

NO EXCEPTIONS. If you cannot cite sources, do not answer."
```

**Impact**:
- ✅ Easy to implement
- ⚠️ Risk: Might increase abstentions (LLM refuses to answer if can't cite)
- **Estimated fix**: 6-8 of 12 citation failures

**Proposed Fix B - Post-processing validation** (robust):
```python
def _validate_citations(answer_text, retrieved_sources):
    """
    Check if answer cites at least 1 retrieved source.
    If not, force abstention or regenerate.
    """
    cited_ids = extract_cited_ids(answer_text)  # Parse <!--CITED_IDS: ... -->

    if not cited_ids and len(retrieved_sources) > 0:
        # LLM didn't cite anything despite having sources!
        # Option A: Force abstention
        return "Lo siento, no puedo responder sin citar fuentes específicas."

        # Option B: Retry with stricter prompt
        return regenerate_with_citation_enforcement()
```

**Impact**:
- ✅ Guarantees citation compliance
- ⚠️ Adds latency (validation + potential retry)
- **Estimated fix**: 10-12 of 12 citation failures

**Proposed Fix C - Few-shot examples in context** (experimental):
```python
# Add retrieved source snippets DIRECTLY in prompt as examples:

"Ejemplo con fuentes reales recuperadas:
---
Fuente: BOE-A-2006-20764, Artículo 95.2
'Los rendimientos de actividades profesionales estarán sujetos a retención...'

Tu respuesta basada en esta fuente:
Los artistas autónomos están sujetos a retención del 15% sobre sus rendimientos profesionales.
<!--CITED_IDS: BOE-A-2006-20764 -->
---"
```

**Impact**:
- ✅ Shows LLM exactly how to cite
- ⚠️ Increases prompt size (adds latency)
- **Estimated fix**: 8-10 of 12 failures

**Recommendation**: **Fix A (stricter prompt)** for quick win.
**Fix B (validation)** for production robustness.

---

### Solution 3: Fix Wrong Document Retrieval

**Problem**: Queries like "autónomo vs SL" returning labor laws instead of fiscal/corporate

**Root Cause**: Semantic search matching on "autónomo" (worker type) instead of understanding query intent (tax comparison)

**Proposed Fix A - Query intent classification** (already exists, improve it):
```python
# Current: Intent classifier returns "Fiscal" or "Laboral"
# Problem: "autónomo vs SL" → might classify as "Laboral" (wrong!)

# Fix: Add secondary classification for hybrid queries
class QueryIntent:
    primary_area: str  # "Fiscal"
    secondary_areas: List[str]  # ["Societario", "Laboral"]
    intent_type: str  # "comparison", "procedural", "conceptual", "rate-seeking"

# Use in retrieval:
if intent_type == "comparison":
    # Retrieve from ALL mentioned areas
    retrieve_multi_area(primary + secondary_areas)
```

**Impact**:
- ✅ Fixes hybrid/comparison queries
- ⚠️ More complex retrieval logic
- **Estimated fix**: 4-6 of 8 wrong-doc retrievals

**Proposed Fix A - Negative filtering** (quick):
```python
# For fiscal questions, explicitly EXCLUDE labor laws from results
EXCLUSION_MAP = {
    "Fiscal": ["Laboral", "Seguridad Social"],
    "Laboral": [],  # Labor can reference fiscal (retenciones)
}

# In retrieval:
if area_principal == "Fiscal":
    exclude_areas = EXCLUSION_MAP["Fiscal"]
    results = [r for r in results
               if r['source_area'] not in exclude_areas]
```

**Impact**:
- ✅ Quick fix for obvious mis-matches
- ❌ Risk: Might exclude relevant cross-area sources
- **Estimated fix**: 3-4 of 8 failures

**Recommendation**: **Improve query understanding** (Fix A) for better long-term results.

---

## Risk Analysis: What Could Go Wrong

### Risk 1: Over-Tuning for Eval Set

**Concern**: We tune thresholds to pass the 50-case eval, but break other queries

**Mitigation**:
1. Test on DIFFERENT query set before/after changes
2. Monitor production logs for abstention rate changes
3. Use A/B testing (50% traffic old logic, 50% new logic)

### Risk 2: Lower Quality Answers

**Concern**: Lowering abstention threshold leads to answers based on weak sources

**Mitigation**:
1. Require citation validation (Solution 2B)
2. Monitor user feedback/ratings
3. Re-enable lightweight judge for quality checks (10% sampling)

### Risk 3: Latency Regression

**Concern**: Adding validation/retry logic increases latency

**Mitigation**:
1. Implement validation WITHOUT retry first (fast fail)
2. Use streaming to hide latency
3. Monitor P95 latency in production

---

## Recommended Implementation Order

### Phase 1: Quick Wins (1-2 hours)
1. ✅ **Lower abstention threshold** (Solution 1A)
   - Change `priority_sources < 1` to `priority_sources < 1 and total_sources < 2`
2. ✅ **Stricter citation prompt** (Solution 2A)
   - Add "CRITICAL: You MUST cite..." to prompt

**Expected Impact**: 10-15 fewer failures (8 abstentions → 4, 12 citations → 6)

### Phase 2: Validation (2-3 hours)
3. ✅ **Citation post-processing** (Solution 2B)
   - Validate citations, force abstention if missing
4. ✅ **Re-run 50-case eval** to measure improvement

**Expected Impact**: Pass citation gate (20 → <5 failures)

### Phase 3: Retrieval Improvements (1-2 days)
5. ⏱️ **Improve query expansion** (Solution 1C)
   - Make conceptual queries more specific
6. ⏱️ **Multi-area retrieval** for hybrid queries (Solution 3A)
7. ⏱️ **Re-run eval + production monitoring**

**Expected Impact**: Pass all gates consistently

---

## Comparison: Before vs After (Projected)

| Metric | Current | After Phase 1 | After Phase 2 | After Phase 3 |
|--------|---------|---------------|---------------|---------------|
| Abstain mismatches | 8 | **4** ✅ | **2** ✅ | **1** ✅ |
| Citation misses | 20 | **12** | **4** ✅ | **2** ✅ |
| P95 latency (ms) | 21,106 | 21,500 | 22,000 | 20,000 |
| Avg latency (ms) | 14,222 | 14,500 | 15,000 | 13,500 |

**Phase 1 gets us 60% of the way** with minimal risk.
**Phase 2 gets us to production-ready** (all gates pass).
**Phase 3 optimizes** for best-in-class quality.

---

## Conclusion

The failures are **systemic but fixable**:

1. **Abstention**: Too conservative, can be tuned safely
2. **Citations**: LLM prompt issue, solvable with validation
3. **Retrieval**: Needs smarter query understanding for edge cases

**No showstoppers found** - all issues have clear solutions with acceptable tradeoffs.

**Recommendation**: Start with Phase 1 (2 hours), validate with re-run, then proceed to Phase 2 if needed.
