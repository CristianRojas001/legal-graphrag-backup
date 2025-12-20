"""
Regression tests for citation confetti fixes (V1.1)

Tests:
1. Meta queries return no sources
2. Legal queries with no citations have no "Fuentes utilizadas"
3. Legal queries with citations only list cited sources
4. IVA rate questions abstain/Two-Lane when missing rate evidence
5. IVA conceptual questions work without rate evidence
"""

import os
import sys
import json
import django

# Setup Django
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ovra_backend.settings')
django.setup()

from apps.legal_graphrag.services.v1_1.legal_rag_engine_v1_1 import LegalRAGEngineV1_1
import re


class TestCitationFixes:
    def __init__(self):
        self.engine = LegalRAGEngineV1_1()
        self.passed = 0
        self.failed = 0
        self.results = []

    def assert_true(self, condition, test_name, error_msg=""):
        """Helper assertion method"""
        if condition:
            print(f"  PASS: {test_name}")
            self.passed += 1
            return True
        else:
            print(f"  FAIL: {test_name}")
            if error_msg:
                print(f"    Error: {error_msg}")
            self.failed += 1
            return False

    def test_meta_query_no_sources(self):
        """Test 1: Meta query should return no sources"""
        print("\nTest 1: Meta query returns no sources")
        result = self.engine.answer_query(query="Que puedes hacer?", max_sources=10)

        total_sources = result.get('metadata', {}).get('total_sources', 0)
        has_fuentes = "**Fuentes utilizadas**:" in result.get('answer', '')
        is_meta = result.get('metadata', {}).get('is_meta_query', False)

        self.assert_true(is_meta, "Query detected as meta")
        self.assert_true(total_sources == 0, "total_sources == 0", f"Got {total_sources}")
        self.assert_true(not has_fuentes, "No 'Fuentes utilizadas' section")

        self.results.append({
            "test": "meta_query_no_sources",
            "passed": is_meta and total_sources == 0 and not has_fuentes,
            "total_sources": total_sources,
            "has_fuentes": has_fuentes,
            "is_meta": is_meta
        })

    def test_legal_no_citations_no_fuentes(self):
        """Test 2: If LLM doesn't cite anything, no 'Fuentes utilizadas' section"""
        print("\nTest 2: Legal query with no citations has no 'Fuentes utilizadas'")

        # Use a very specific query that might not trigger citations
        result = self.engine.answer_query(
            query="Explica brevemente que es el derecho administrativo",
            max_sources=10
        )

        answer = result.get('answer', '')
        cited_ids = set(re.findall(r"\[ID:\s*([^\]]+)\]", answer))
        has_fuentes = "**Fuentes utilizadas**:" in answer

        # This test might vary based on LLM response, so we just check consistency
        if len(cited_ids) == 0:
            self.assert_true(not has_fuentes, "No citations => No 'Fuentes utilizadas'")
            consistent = True
        else:
            # If there are citations, Fuentes should exist
            consistent = has_fuentes
            print(f"  INFO: {len(cited_ids)} citations found, Fuentes section exists: {has_fuentes}")

        self.results.append({
            "test": "legal_no_citations_no_fuentes",
            "passed": consistent,
            "cited_ids_count": len(cited_ids),
            "has_fuentes": has_fuentes
        })

    def test_legal_only_cited_sources(self):
        """Test 3: 'Fuentes utilizadas' only contains cited IDs"""
        print("\nTest 3: 'Fuentes utilizadas' only contains actually cited sources")

        result = self.engine.answer_query(
            query="Cual es la ley que regula el IRPF?",
            max_sources=10
        )

        answer = result.get('answer', '')
        cited_ids = set(re.findall(r"\[ID:\s*([^\]]+)\]", answer))

        # Extract IDs from "Fuentes utilizadas" section
        fuentes_section = ""
        if "**Fuentes utilizadas**:" in answer:
            fuentes_section = answer.split("**Fuentes utilizadas**:")[1]

        fuentes_ids = set(re.findall(r"\[ID:\s*([^\]]+)\]", fuentes_section))

        # Check: fuentes_ids should be subset of (or equal to) cited_ids
        extra_ids = fuentes_ids - cited_ids
        missing_ids = cited_ids - fuentes_ids

        self.assert_true(
            len(extra_ids) == 0,
            "No uncited sources in 'Fuentes utilizadas'",
            f"Extra IDs: {extra_ids}"
        )
        self.assert_true(
            len(missing_ids) == 0,
            "All cited sources in 'Fuentes utilizadas'",
            f"Missing IDs: {missing_ids}"
        )

        self.results.append({
            "test": "legal_only_cited_sources",
            "passed": len(extra_ids) == 0 and len(missing_ids) == 0,
            "cited_ids": list(cited_ids),
            "fuentes_ids": list(fuentes_ids),
            "extra_ids": list(extra_ids),
            "missing_ids": list(missing_ids)
        })

    def test_iva_rate_missing_evidence(self):
        """Test 4: IVA rate question with missing evidence should abstain or use Two-Lane"""
        print("\nTest 4: IVA rate question with missing evidence")

        result = self.engine.answer_query(
            query="Cual es el tipo de IVA aplicable a servicios de interpretacion musical?",
            max_sources=10
        )

        answer = result.get('answer', '')
        abstained = result.get('metadata', {}).get('abstained', False)

        # Check if answer makes unsupported rate claims
        found_rates = re.findall(r"(\d+)\s*%", answer)

        # Either abstained OR uses Two-Lane mode (mentions "orientación general" or similar)
        is_two_lane = any(keyword in answer.lower() for keyword in [
            "orientación general",
            "lo que sí puedo afirmar",
            "para afinar",
            "verificación"
        ])

        safe_response = abstained or is_two_lane or len(found_rates) == 0

        self.assert_true(
            safe_response,
            "Safe response (abstain, Two-Lane, or no unsupported rates)",
            f"abstained={abstained}, is_two_lane={is_two_lane}, rates={found_rates}"
        )

        self.results.append({
            "test": "iva_rate_missing_evidence",
            "passed": safe_response,
            "abstained": abstained,
            "is_two_lane": is_two_lane,
            "found_rates": found_rates
        })

    def test_iva_conceptual_no_abstain(self):
        """Test 5: IVA conceptual question should NOT abstain just for missing rates"""
        print("\nTest 5: IVA conceptual question works without rate evidence")

        result = self.engine.answer_query(
            query="Que obligaciones tiene un autonomo respecto al IVA?",
            max_sources=10
        )

        answer = result.get('answer', '')
        abstained = result.get('metadata', {}).get('abstained', False)
        answer_length = len(answer)

        # Should get a substantive answer (not abstained)
        # Or if abstained, should be because of truly missing evidence (not just missing rates)
        is_helpful = answer_length > 200 and not abstained

        self.assert_true(
            is_helpful or not abstained,
            "Helpful answer or non-abstain response",
            f"abstained={abstained}, length={answer_length}"
        )

        self.results.append({
            "test": "iva_conceptual_no_abstain",
            "passed": is_helpful or not abstained,
            "abstained": abstained,
            "answer_length": answer_length
        })

    def run_all(self):
        """Run all tests"""
        print("="*80)
        print("Citation Confetti Fix - Regression Tests")
        print("="*80)

        self.test_meta_query_no_sources()
        self.test_legal_no_citations_no_fuentes()
        self.test_legal_only_cited_sources()
        self.test_iva_rate_missing_evidence()
        self.test_iva_conceptual_no_abstain()

        print("\n" + "="*80)
        print(f"Results: {self.passed} passed, {self.failed} failed")
        print("="*80)

        # Save results
        with open('test_citation_fixes_results.json', 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)

        print("\nResults saved to test_citation_fixes_results.json")

        return self.failed == 0


if __name__ == '__main__':
    tester = TestCitationFixes()
    success = tester.run_all()
    sys.exit(0 if success else 1)
