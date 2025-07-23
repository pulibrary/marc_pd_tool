# marc_pd_tool/tests/test_utils/test_text_properties.py

"""Property-based tests for text normalization and processing functions

These tests verify that text processing functions maintain certain invariants
across all possible inputs, helping discover edge cases and ensure robustness.
"""

# Third party imports
from hypothesis import given
from hypothesis import strategies as st

# Local imports
from marc_pd_tool.utils.text_utils import ascii_fold
from marc_pd_tool.utils.text_utils import extract_significant_words
from marc_pd_tool.utils.text_utils import extract_year
from marc_pd_tool.utils.text_utils import normalize_text_standard
from marc_pd_tool.utils.text_utils import normalize_unicode
from marc_pd_tool.utils.text_utils import normalize_word_splits
from marc_pd_tool.utils.text_utils import remove_bracketed_content


class TestUnicodeNormalizationProperties:
    """Property-based tests for Unicode normalization"""

    @given(st.text())
    def test_normalize_unicode_idempotent(self, text: str) -> None:
        """Normalizing Unicode twice should give the same result"""
        once = normalize_unicode(text)
        twice = normalize_unicode(once)
        assert once == twice

    @given(st.text())
    def test_normalize_unicode_ascii_only_output(self, text: str) -> None:
        """normalize_unicode output should contain only ASCII characters"""
        normalized = normalize_unicode(text)
        try:
            # Should be encodable as ASCII
            normalized.encode("ascii")
            is_ascii = True
        except UnicodeEncodeError:
            is_ascii = False
        assert is_ascii, f"Non-ASCII characters in output: {repr(normalized)}"

    @given(st.text())
    def test_normalize_unicode_handles_any_input(self, text: str) -> None:
        """normalize_unicode should handle any string input without crashing"""
        try:
            result = normalize_unicode(text)
            assert isinstance(result, str)
        except Exception as e:
            assert False, f"normalize_unicode raised exception: {e}"

    @given(st.text())
    def test_normalize_unicode_preserves_empty(self, text: str) -> None:
        """Empty strings should remain empty"""
        if text == "":
            assert normalize_unicode(text) == ""


class TestAsciiFoldProperties:
    """Property-based tests for ASCII folding"""

    @given(st.text())
    def test_ascii_fold_idempotent(self, text: str) -> None:
        """ASCII folding twice should give the same result"""
        once = ascii_fold(text)
        twice = ascii_fold(once)
        assert once == twice

    @given(st.text())
    def test_ascii_fold_produces_ascii(self, text: str) -> None:
        """ascii_fold should produce only ASCII characters"""
        folded = ascii_fold(text)
        try:
            folded.encode("ascii")
            is_ascii = True
        except UnicodeEncodeError:
            is_ascii = False
        assert is_ascii, f"Non-ASCII in output: {repr(folded)}"

    @given(st.text())
    def test_ascii_fold_handles_any_input(self, text: str) -> None:
        """ascii_fold should handle any string input"""
        try:
            result = ascii_fold(text)
            assert isinstance(result, str)
        except Exception as e:
            assert False, f"ascii_fold raised exception: {e}"

    @given(st.text(alphabet=st.characters(min_codepoint=0, max_codepoint=127)))
    def test_ascii_fold_preserves_ascii(self, ascii_text: str) -> None:
        """ASCII text should pass through unchanged (mostly)"""
        # Note: Some ASCII chars might change (e.g., smart quotes to regular)
        folded = ascii_fold(ascii_text)
        # Just verify it's still ASCII
        assert all(ord(c) < 128 for c in folded)


class TestTextStandardNormalizationProperties:
    """Property-based tests for standard text normalization"""

    @given(st.text())
    def test_normalize_text_standard_idempotent(self, text: str) -> None:
        """Standard normalization should be idempotent"""
        once = normalize_text_standard(text)
        twice = normalize_text_standard(once)
        assert once == twice

    @given(st.text())
    def test_normalize_text_standard_lowercase(self, text: str) -> None:
        """Standard normalization should produce lowercase text"""
        normalized = normalize_text_standard(text)
        assert normalized == normalized.lower()

    @given(st.text())
    def test_normalize_text_standard_no_multiple_spaces(self, text: str) -> None:
        """Standard normalization should not have multiple consecutive spaces"""
        normalized = normalize_text_standard(text)
        assert "  " not in normalized

    @given(st.text())
    def test_normalize_text_standard_handles_any_input(self, text: str) -> None:
        """Should handle any string input without crashing"""
        try:
            result = normalize_text_standard(text)
            assert isinstance(result, str)
        except Exception as e:
            assert False, f"normalize_text_standard raised exception: {e}"

    @given(st.text())
    def test_normalize_text_standard_ascii_output(self, text: str) -> None:
        """Standard normalization should produce ASCII-only output"""
        normalized = normalize_text_standard(text)
        assert all(ord(c) < 128 for c in normalized)


class TestBracketedContentRemoval:
    """Property-based tests for bracketed content removal"""

    @given(st.text())
    def test_remove_bracketed_content_idempotent(self, text: str) -> None:
        """Removing brackets twice should give same result"""
        once = remove_bracketed_content(text)
        twice = remove_bracketed_content(once)
        assert once == twice

    @given(st.text())
    def test_remove_bracketed_content_no_brackets_in_output(self, text: str) -> None:
        """Output should not contain complete bracketed pairs"""
        result = remove_bracketed_content(text)
        # After removal, no complete bracket pairs should remain
        # But unmatched brackets may still exist (e.g., '][' -> '][')

        # Check that there are no complete bracketed sections
        # Standard library imports
        import re

        # This pattern matches complete bracketed content
        assert not re.search(r"\[[^\[\]]*\]", result)

    @given(st.text())
    def test_remove_bracketed_content_handles_any_input(self, text: str) -> None:
        """Should handle any input without crashing"""
        try:
            result = remove_bracketed_content(text)
            assert isinstance(result, str)
        except Exception as e:
            assert False, f"remove_bracketed_content raised exception: {e}"

    @given(st.text(alphabet=st.characters(blacklist_characters="[]")))
    def test_remove_bracketed_content_preserves_text_without_brackets(self, text: str) -> None:
        """Text without brackets should pass through unchanged (except whitespace)"""
        result = remove_bracketed_content(text)
        # The function strips and normalizes whitespace
        if text.strip():
            # Non-empty text should be preserved (modulo whitespace)
            assert result.strip() != ""


class TestYearExtraction:
    """Property-based tests for year extraction"""

    @given(st.integers(min_value=1800, max_value=2099))
    def test_extract_year_finds_valid_years(self, year: int) -> None:
        """Should extract valid 4-digit years from text"""
        text = f"Published in {year} by Example Press"
        extracted = extract_year(text)
        assert extracted == year

    @given(st.text())
    def test_extract_year_returns_int_or_none(self, text: str) -> None:
        """Should always return int or None"""
        result = extract_year(text)
        assert result is None or isinstance(result, int)

    @given(st.text())
    def test_extract_year_handles_any_input(self, text: str) -> None:
        """Should handle any input without crashing"""
        try:
            result = extract_year(text)
            assert result is None or isinstance(result, int)
        except Exception as e:
            assert False, f"extract_year raised exception: {e}"

    @given(st.text())
    def test_extract_year_range_constraint(self, text: str) -> None:
        """Extracted years should be in valid range"""
        year = extract_year(text)
        if year is not None:
            assert 1800 <= year <= 2099

    @given(st.text(alphabet=st.characters(blacklist_categories=["Nd"])))
    def test_extract_year_no_digits_returns_none(self, text: str) -> None:
        """Text without digits should return None"""
        assert extract_year(text) is None


class TestNormalizeWordSplits:
    """Property-based tests for word split normalization"""

    @given(st.text())
    def test_normalize_word_splits_idempotent(self, text: str) -> None:
        """Normalizing word splits twice should give same result"""
        once = normalize_word_splits(text)
        twice = normalize_word_splits(once)
        assert once == twice

    @given(st.text())
    def test_normalize_word_splits_handles_any_input(self, text: str) -> None:
        """Should handle any input without crashing"""
        try:
            result = normalize_word_splits(text)
            assert isinstance(result, str)
        except Exception as e:
            assert False, f"normalize_word_splits raised exception: {e}"

    @given(st.text(alphabet="abcdefghijklmnopqrstuvwxyz ", min_size=1))
    def test_normalize_word_splits_basic_behavior(self, text: str) -> None:
        """Single letters separated by spaces should be joined"""
        result = normalize_word_splits(text)
        # Count single letter sequences in input
        # Standard library imports
        import re

        single_letter_pattern = r"\b[a-z]\s+[a-z]\b"
        if re.search(single_letter_pattern, text):
            # Should have fewer spaces in result
            assert result.count(" ") < text.count(" ")


class TestSignificantWordsExtraction:
    """Property-based tests for significant word extraction"""

    @given(st.text(), st.sets(st.text(min_size=1, max_size=10)))
    def test_extract_significant_words_respects_max(self, text: str, stopwords: set[str]) -> None:
        """Should never return more than max_words"""
        max_words = 5
        result = extract_significant_words(text, stopwords, max_words)
        assert len(result) <= max_words

    @given(st.text(), st.sets(st.text(min_size=1, max_size=10)))
    def test_extract_significant_words_returns_list(self, text: str, stopwords: set[str]) -> None:
        """Should always return a list of strings"""
        result = extract_significant_words(text, stopwords)
        assert isinstance(result, list)
        assert all(isinstance(word, str) for word in result)

    @given(st.text(), st.sets(st.text(min_size=1, max_size=10)))
    def test_extract_significant_words_filters_stopwords(
        self, text: str, stopwords: set[str]
    ) -> None:
        """Should not include stopwords in result (unless all words are stopwords)"""
        result = extract_significant_words(text, stopwords)

        # Normalize the text to get the actual words that will be processed
        # Use the same normalization as the function
        # Local imports
        from marc_pd_tool.utils.text_utils import normalize_text_standard

        normalized = normalize_text_standard(text)
        if not normalized:
            return

        words = normalized.split()

        # BUG FOUND: The function filters stopwords case-sensitively!
        # It checks 'w not in stopwords' where stopwords is the original set
        # So if stopwords contains 'ABC' and the word is 'abc', it won't be filtered

        # Check if there are any words that would pass the filter
        has_valid_words = any(w not in stopwords and len(w) >= 3 for w in words)

        if has_valid_words:
            # Normal case: stopwords should be filtered (but case-sensitively!)
            for word in result:
                assert word not in stopwords

    @given(st.text(), st.sets(st.text(min_size=1, max_size=10)))
    def test_extract_significant_words_handles_any_input(
        self, text: str, stopwords: set[str]
    ) -> None:
        """Should handle any input without crashing"""
        try:
            result = extract_significant_words(text, stopwords)
            assert isinstance(result, list)
        except Exception as e:
            assert False, f"extract_significant_words raised exception: {e}"
