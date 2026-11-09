"""
Unit and Integration Tests for Keyword Expansion Module in Nyaya Saathi.

Step 15: Controlled Bilingual Keyword Expansion Tests.
Verifies language detection, phrase matching, statutory concept mapping,
preservation of query provenance, and strict abstention from LLM API calls or term fabrication.
"""

from typing import List, Tuple
import pytest

from src.keyword_expansion import (
    CONTROLLED_VOCABULARY,
    contains_devanagari,
    detect_query_language,
    expand_query_terms,
)


class TestKeywordExpansion:
    """Test suite for keyword expansion and language detection."""

    def test_01_contains_devanagari_detection(self):
        """Verifies accurate detection of Devanagari script."""
        assert contains_devanagari("टूटा हुआ सामान") is True
        assert contains_devanagari("उपभोक्ता फोरम") is True
        assert contains_devanagari("Mixed Devanagari और English") is True
        assert contains_devanagari("Pure English text") is False
        assert contains_devanagari("Hinglish me text hai") is False
        assert contains_devanagari("") is False

    def test_02_detect_query_language(self):
        """Verifies classification into 'hi', 'hinglish', and 'en'."""
        assert detect_query_language("दुकानदार पैसे वापस नहीं कर रहा") == "hi"
        assert detect_query_language("product damaged hai aur refund nahi mila") == "hinglish"
        assert detect_query_language("seller call nahi utha raha") == "hinglish"
        assert detect_query_language("order deliver nahi hua") == "hinglish"
        assert detect_query_language("I received a damaged laptop from the seller") == "en"
        assert detect_query_language("What is the pecuniary jurisdiction of District Commission?") == "en"
        assert detect_query_language("") == "en"

    def test_03_hindi_damaged_goods_expansion(self):
        """Verifies mapping of Hindi damaged goods expressions."""
        query = "मुझे डिलीवरी में टूटा हुआ सामान मिला है"
        terms, matched, lang = expand_query_terms(query)

        assert lang == "hi"
        assert "टूटा हुआ सामान" in matched or "टूटा हुआ" in matched
        assert "defective goods" in terms
        assert "defect" in terms
        assert "damaged goods" in terms

    def test_04_hindi_refund_query_expansion(self):
        """Verifies mapping of Hindi refund queries."""
        query = "दुकानदार पैसे वापस नहीं कर रहा है"
        terms, matched, lang = expand_query_terms(query)

        assert lang == "hi"
        assert any("पैसे वापस" in m for m in matched)
        assert "refund" in terms
        assert "repayment" in terms

    def test_05_hinglish_damaged_product_expansion(self):
        """Verifies mapping of Hinglish damaged product expressions."""
        query = "Flipkart pe product damaged hai"
        terms, matched, lang = expand_query_terms(query)

        assert lang == "hinglish"
        assert "product damaged hai" in matched or "product damaged" in matched
        assert "defective goods" in terms
        assert "defect" in terms

    def test_06_hinglish_refund_query_expansion(self):
        """Verifies mapping of Hinglish refund queries."""
        query = "seller se refund nahi mil raha"
        terms, matched, lang = expand_query_terms(query)

        assert lang == "hinglish"
        assert "refund nahi mil raha" in matched
        assert "refund" in terms
        assert "repayment" in terms

    def test_07_hinglish_seller_refusal_expansion(self):
        """Verifies mapping of Hinglish seller refusal and call avoidance."""
        query = "seller call nahi utha raha aur replacement reject kar diya"
        terms, matched, lang = expand_query_terms(query)

        assert lang == "hinglish"
        assert "seller call nahi utha raha" in matched
        assert "replacement reject kar diya" in matched
        assert "seller" in terms
        assert "replacement" in terms

    def test_08_hinglish_non_delivery_expansion(self):
        """Verifies mapping of Hinglish non-delivery expressions."""
        query = "mera order deliver nahi hua abhi tak"
        terms, matched, lang = expand_query_terms(query)

        assert lang == "hinglish"
        assert "order deliver nahi hua" in matched
        assert "non-delivery" in terms
        assert "delivery" in terms

    def test_09_no_invented_section_citations(self):
        """Verifies that keyword expansion never invents statutory section or rule numbers."""
        test_queries = [
            "टूटा हुआ सामान",
            "दुकानदार पैसे वापस नहीं दे रहा",
            "seller call nahi utha raha",
            "order deliver nahi hua",
            "product damaged hai",
        ]
        for q in test_queries:
            terms, _, _ = expand_query_terms(q)
            for t in terms:
                # Terms must be conceptual English phrases, never specific section references
                assert not t.lower().startswith("section "), f"Fabricated section citation in term: {t}"
                assert not t.lower().startswith("rule "), f"Fabricated rule citation in term: {t}"
                assert not t.lower().startswith("clause "), f"Fabricated clause citation in term: {t}"

    def test_10_unrelated_query_no_hallucination(self):
        """Verifies that queries with no consumer dispute terms return an empty expansion."""
        query = "How do I bake a chocolate cake using fresh strawberries?"
        terms, matched, lang = expand_query_terms(query)

        assert lang == "en"
        assert matched == []
        assert terms == []

    def test_11_empty_and_whitespace_queries(self):
        """Verifies safe handling of empty and whitespace queries."""
        assert expand_query_terms("") == ([], [], "en")
        assert expand_query_terms("   ") == ([], [], "en")
        assert expand_query_terms(None) == ([], [], "en")

    def test_12_controlled_vocabulary_integrity(self):
        """Verifies that all concepts in the controlled vocabulary have valid English terms."""
        for entry in CONTROLLED_VOCABULARY:
            assert "concept" in entry
            assert "english_terms" in entry
            assert len(entry["english_terms"]) > 0
            for term in entry["english_terms"]:
                assert isinstance(term, str) and term.strip()
