# Intent Classifier Test Results

**Date**: 2025-12-13  
**Tester**: Codex  
**Status**: PASS

## Summary
- Basic classification: PASS (Fiscal 5/5, Laboral 5/5, Propiedad Intelectual 5/5)
- Ambiguous/edge handling: PASS (3/3 ambiguous matched expected areas; 1 unclear query weak-classified as Fiscal, rest returned None; no crashes on empty/malformed inputs)
- Keyword extraction & utilities: PASS (expected keywords surfaced; get_all_areas/get_keywords_for_area ok)
- Confidence scoring: PASS (clear queries >50% confidence; generic queries <50% or None)
- Performance: 0.0968s for 300 queries (~0.32ms/query, ~3.1k qps)
- Real-world accuracy: 100% (12/12 domain queries)

## Detailed Results
1. Basic functionality – PASS  
   Fiscal 5/5, Laboral 5/5, Propiedad Intelectual 5/5.
2. Edge cases – PASS  
   Ambiguous 3/3 matched expected sets; unclear queries 4/5 returned None (Hacienda location query classified Fiscal); edge inputs (empty/whitespace/symbols/long) handled without errors.
3. Keyword extraction – PASS  
   Expected tokens kept; stopwords trimmed.
4. Utility methods – PASS  
   `get_all_areas()` returned 7 areas; `get_keywords_for_area()` populated for valid areas and empty for invalid.
5. Confidence scoring – PASS  
   Clear queries high confidence; generic questions low confidence/None.
6. Performance – PASS  
   300 queries in 0.0968s (avg 0.3227ms/query, ~3.1k qps).
7. Real-world integration – PASS  
   12/12 artist queries correctly classified (100%).

## Issues Found
- Unclear query `"Donde esta la oficina de Hacienda mas cercana?"` classified as Fiscal because of the Hacienda keyword; treated as a weak classification for a location-style question.

## Recommendations
- Consider down-weighting single-keyword matches on location-style queries so `classify_area` can return `None` when intent is clearly informational and not legal.

## Commands
- `cd "Legal GraphRAG/backend" && python scripts/run_intent_classifier_tests.py`
