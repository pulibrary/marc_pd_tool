# tests/test_utils/test_unicode_normalization.py

"""Tests for Unicode normalization functionality"""

# Third party imports

# Local imports
from marc_pd_tool.shared.utils.text_utils import ascii_fold
from marc_pd_tool.shared.utils.text_utils import normalize_text_standard
from marc_pd_tool.shared.utils.text_utils import normalize_unicode
from marc_pd_tool.shared.utils.text_utils import normalize_word_splits


class TestAsciiFolding:
    """Test ASCII folding functionality"""

    def test_ascii_fold_basic_accents(self):
        """Test basic accented character folding"""
        assert ascii_fold("café") == "cafe"
        assert ascii_fold("naïve") == "naive"
        assert ascii_fold("résumé") == "resume"
        assert ascii_fold("piñata") == "pinata"
        assert ascii_fold("Zürich") == "Zurich"

    def test_ascii_fold_all_variants(self):
        """Test comprehensive accent variants"""
        # A variants
        assert ascii_fold("àáâãäåæ") == "aaaaaaae"
        assert ascii_fold("ÀÁÂÃÄÅÆ") == "AAAAAAAE"
        # E variants
        assert ascii_fold("èéêë") == "eeee"
        assert ascii_fold("ÈÉÊË") == "EEEE"
        # I variants
        assert ascii_fold("ìíîï") == "iiii"
        # O variants
        assert ascii_fold("òóôõöøœ") == "oooooooe"
        # U variants
        assert ascii_fold("ùúûü") == "uuuu"
        # Special characters
        assert ascii_fold("ß") == "ss"
        assert ascii_fold("Þþ") == "Thth"  # unidecode converts Þ to "Th", not "TH"

    def test_ascii_fold_mixed_text(self):
        """Test folding in mixed text"""
        assert ascii_fold("La bête et le château") == "La bete et le chateau"
        assert ascii_fold("São Paulo, Brasil") == "Sao Paulo, Brasil"
        assert ascii_fold("Åse Håvard Øyvind") == "Ase Havard Oyvind"

    def test_ascii_fold_empty_input(self):
        """Test empty input"""
        assert ascii_fold("") == ""

    def test_ascii_fold_no_changes_needed(self):
        """Test text that doesn't need folding"""
        assert ascii_fold("Hello World") == "Hello World"
        assert ascii_fold("12345") == "12345"
        assert ascii_fold("ASCII text only") == "ASCII text only"


class TestUnicodeNormalization:
    """Test Unicode normalization for encoding issues"""

    def test_normalize_unicode_encoding_corruptions(self):
        """Test fixing common UTF-8/Latin-1 corruptions and ASCII folding"""
        # Test cases from ground truth analysis - now with ASCII folding
        assert normalize_unicode("la b√™te hurlante") == "la bete hurlante"
        assert normalize_unicode("Les Mis√©rables") == "Les Miserables"
        assert normalize_unicode("caf√©") == "cafe"
        assert normalize_unicode("na√Øve") == "naive"

    def test_normalize_unicode_multiple_corruptions(self):
        """Test text with multiple corruptions and ASCII folding"""
        # All accented characters are folded to ASCII
        assert normalize_unicode("√† la caf√© fran√ßais") == "a la cafe francais"

    def test_normalize_unicode_nfc_normalization(self):
        """Test NFC normalization of combining characters with ASCII folding"""
        # é can be represented as single character or e + combining acute
        combining = "café"  # e + combining acute
        precomposed = "café"  # single é character

        # Both should normalize to the same ASCII form
        assert normalize_unicode(combining) == "cafe"
        assert normalize_unicode(precomposed) == "cafe"

    def test_normalize_unicode_empty_input(self):
        """Test empty input"""
        assert normalize_unicode("") == ""

    def test_normalize_unicode_no_changes_needed(self):
        """Test text that doesn't need normalization"""
        assert normalize_unicode("Hello World") == "Hello World"
        assert normalize_unicode("12345") == "12345"

    def test_normalize_text_with_unicode(self):
        """Test full text normalization pipeline with Unicode and ASCII folding"""
        # Should normalize Unicode, fold to ASCII, lowercase, and remove punctuation
        assert normalize_text_standard("La B√™te Hurlante!") == "la bete hurlante"
        assert normalize_text_standard("Les Mis√©rables (1862)") == "les miserables 1862"
        assert normalize_text_standard("CAF√© société") == "cafe societe"

    def test_normalize_text_preserves_hyphens(self):
        """Test that hyphens are preserved after Unicode normalization and ASCII folding"""
        assert (
            normalize_text_standard("Jean-Fran√ßois") == "jean francois"
        )  # Hyphens become spaces, ç→c
        assert normalize_text_standard("self-contained") == "self contained"


class TestWordSplitNormalization:
    """Test word split normalization functionality"""

    def test_normalize_word_splits_basic(self):
        """Test basic single letter joining"""
        assert normalize_word_splits("a b c") == "abc"
        assert normalize_word_splits("u s a") == "usa"
        assert normalize_word_splits("p h d") == "phd"

    def test_normalize_word_splits_mixed_text(self):
        """Test joining within larger text"""
        assert normalize_word_splits("the a b c of the league") == "the abc of the league"
        assert normalize_word_splits("u s a amerikas forenede") == "usa amerikas forenede"
        assert normalize_word_splits("volume v i") == "volume vi"

    def test_normalize_word_splits_edge_cases(self):
        """Test edge cases"""
        assert normalize_word_splits("") == ""
        assert normalize_word_splits("a") == "a"  # Single letter unchanged
        assert normalize_word_splits("ab cd") == "ab cd"  # Multi-letter unchanged
        assert normalize_word_splits("a b") == "ab"  # Two letters joined

    def test_normalize_word_splits_boundaries(self):
        """Test word boundary preservation"""
        assert normalize_word_splits("a b c def") == "abc def"
        assert normalize_word_splits("xyz a b c") == "xyz abc"
        assert normalize_word_splits("before a b c after") == "before abc after"

    def test_normalize_text_includes_word_splits(self):
        """Test that normalize_text includes word split normalization"""
        assert normalize_text_standard("The A.B.C. of the League") == "the abc of the league"
        assert normalize_text_standard("U.S.A. - Amerika") == "usa amerika"


class TestLanguageProcessorWithUnicode:
    """Test language processor handles Unicode correctly"""

    def test_remove_stopwords_with_unicode_corruption(self):
        """Test stopword removal with Unicode corruption and ASCII folding"""
        # Local imports
        from marc_pd_tool.application.processing.text_processing import (
            LanguageProcessor,
        )

        processor = LanguageProcessor()

        # French text with corrupted encoding
        result = processor.remove_stopwords("la b√™te et le prince", "fre")

        # "la", "et", "le" are French stopwords, should be removed
        # "bete" should be normalized to ASCII and kept, "prince" should be kept
        assert "bete" in result
        assert "prince" in result
        assert "la" not in result
        assert "et" not in result
        assert "le" not in result

    def test_remove_stopwords_with_ascii_folding(self):
        """Test that accented characters are folded to ASCII"""
        # Local imports
        from marc_pd_tool.application.processing.text_processing import (
            LanguageProcessor,
        )

        processor = LanguageProcessor()

        # French text with proper encoding
        result = processor.remove_stopwords("château français élégant", "fre")

        # All three words should be kept (not stopwords) but folded to ASCII
        assert "chateau" in result
        assert "francais" in result
        assert "elegant" in result
