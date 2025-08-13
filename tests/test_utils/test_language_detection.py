# tests/test_utils/test_language_detection.py

"""Tests for MARC language detection functionality"""

# Standard library imports
from unittest import TestCase

# Local imports
from marc_pd_tool.shared.utils.marc_utilities import MARC_LANGUAGE_MAPPING
from marc_pd_tool.shared.utils.marc_utilities import extract_language_from_marc


class TestMARCLanguageMapping(TestCase):
    """Test MARC language code mapping"""

    def test_mapping_contains_expected_languages(self):
        """Test that mapping contains our target languages"""
        # English variants
        assert "eng" in MARC_LANGUAGE_MAPPING
        assert "en" in MARC_LANGUAGE_MAPPING

        # French variants
        assert "fre" in MARC_LANGUAGE_MAPPING
        assert "fr" in MARC_LANGUAGE_MAPPING
        assert "fra" in MARC_LANGUAGE_MAPPING

        # German variants
        assert "ger" in MARC_LANGUAGE_MAPPING
        assert "de" in MARC_LANGUAGE_MAPPING
        assert "deu" in MARC_LANGUAGE_MAPPING

        # Spanish variants
        assert "spa" in MARC_LANGUAGE_MAPPING
        assert "es" in MARC_LANGUAGE_MAPPING
        assert "esp" in MARC_LANGUAGE_MAPPING

        # Italian variants
        assert "ita" in MARC_LANGUAGE_MAPPING
        assert "it" in MARC_LANGUAGE_MAPPING
        assert "ital" in MARC_LANGUAGE_MAPPING

    def test_mapping_values_are_processing_languages(self):
        """Test that all mapping values are our processing language codes"""
        expected_processing_languages = {"eng", "fre", "ger", "spa", "ita"}
        actual_values = set(MARC_LANGUAGE_MAPPING.values())
        assert actual_values == expected_processing_languages


class TestExtractLanguageFromMARC(TestCase):
    """Test extract_language_from_marc function"""

    def test_english_language_detection(self):
        """Test English language code detection"""
        language, status = extract_language_from_marc("eng")
        assert language == "eng"
        assert status == "detected"

        language, status = extract_language_from_marc("en")
        assert language == "eng"
        assert status == "detected"

    def test_french_language_detection(self):
        """Test French language code detection"""
        language, status = extract_language_from_marc("fre")
        assert language == "fre"
        assert status == "detected"

        language, status = extract_language_from_marc("fr")
        assert language == "fre"
        assert status == "detected"

        language, status = extract_language_from_marc("fra")
        assert language == "fre"
        assert status == "detected"

    def test_german_language_detection(self):
        """Test German language code detection"""
        language, status = extract_language_from_marc("ger")
        assert language == "ger"
        assert status == "detected"

        language, status = extract_language_from_marc("de")
        assert language == "ger"
        assert status == "detected"

        language, status = extract_language_from_marc("deu")
        assert language == "ger"
        assert status == "detected"

    def test_spanish_language_detection(self):
        """Test Spanish language code detection"""
        language, status = extract_language_from_marc("spa")
        assert language == "spa"
        assert status == "detected"

        language, status = extract_language_from_marc("es")
        assert language == "spa"
        assert status == "detected"

        language, status = extract_language_from_marc("esp")
        assert language == "spa"
        assert status == "detected"

    def test_italian_language_detection(self):
        """Test Italian language code detection"""
        language, status = extract_language_from_marc("ita")
        assert language == "ita"
        assert status == "detected"

        language, status = extract_language_from_marc("it")
        assert language == "ita"
        assert status == "detected"

        language, status = extract_language_from_marc("ital")
        assert language == "ita"
        assert status == "detected"

    def test_case_insensitive_detection(self):
        """Test that language detection is case insensitive"""
        language, status = extract_language_from_marc("ENG")
        assert language == "eng"
        assert status == "detected"

        language, status = extract_language_from_marc("FR")
        assert language == "fre"
        assert status == "detected"

        language, status = extract_language_from_marc("DE")
        assert language == "ger"
        assert status == "detected"

    def test_whitespace_handling(self):
        """Test that whitespace is handled correctly"""
        language, status = extract_language_from_marc(" eng ")
        assert language == "eng"
        assert status == "detected"

        language, status = extract_language_from_marc("\tfre\n")
        assert language == "fre"
        assert status == "detected"

    def test_empty_language_code_fallback(self):
        """Test fallback behavior for empty language codes"""
        language, status = extract_language_from_marc("")
        assert language == "eng"
        assert status == "fallback_english"

        language, status = extract_language_from_marc(None)
        assert language == "eng"
        assert status == "fallback_english"

        language, status = extract_language_from_marc("   ")
        assert language == "eng"
        assert status == "fallback_english"

    def test_unknown_language_code_fallback(self):
        """Test fallback behavior for unknown language codes"""
        language, status = extract_language_from_marc("xyz")
        assert language == "eng"
        assert status == "unknown_code"

        language, status = extract_language_from_marc("abc123")
        assert language == "eng"
        assert status == "unknown_code"

        language, status = extract_language_from_marc("latin")
        assert language == "eng"
        assert status == "unknown_code"

    def test_detection_status_values(self):
        """Test that detection status values are as expected"""
        # Detected status
        _, status = extract_language_from_marc("eng")
        assert status == "detected"

        # Fallback English status
        _, status = extract_language_from_marc("")
        assert status == "fallback_english"

        # Unknown code status
        _, status = extract_language_from_marc("unknown")
        assert status == "unknown_code"

    def test_return_value_types(self):
        """Test that return values are the correct types"""
        language, status = extract_language_from_marc("eng")
        assert isinstance(language, str)
        assert isinstance(status, str)

        language, status = extract_language_from_marc("")
        assert isinstance(language, str)
        assert isinstance(status, str)
