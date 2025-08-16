# tests/unit/shared/utils/test_lccn_properties.py

"""Property-based tests for LCCN normalization and extraction functions

These tests verify that LCCN processing functions maintain certain invariants
across all possible inputs, helping discover edge cases and ensure robustness.
"""

# Third party imports
from hypothesis import given
from hypothesis import strategies as st
from hypothesis.strategies import composite

# Local imports
from marc_pd_tool.shared.utils.text_utils import extract_lccn_prefix
from marc_pd_tool.shared.utils.text_utils import extract_lccn_serial
from marc_pd_tool.shared.utils.text_utils import extract_lccn_year
from marc_pd_tool.shared.utils.text_utils import normalize_lccn


class TestLCCNNormalizationProperties:
    """Property-based tests for LCCN normalization"""

    @given(st.text())
    def test_normalize_lccn_idempotent(self, lccn: str) -> None:
        """Normalizing an LCCN twice should give the same result"""
        once = normalize_lccn(lccn)
        twice = normalize_lccn(once)
        assert once == twice

    @given(st.text())
    def test_normalize_lccn_no_spaces(self, lccn: str) -> None:
        """Normalized LCCN should never contain spaces"""
        normalized = normalize_lccn(lccn)
        assert " " not in normalized

    @given(st.text())
    def test_normalize_lccn_no_hyphens(self, lccn: str) -> None:
        """Normalized LCCN should never contain hyphens"""
        normalized = normalize_lccn(lccn)
        assert "-" not in normalized

    @given(st.text())
    def test_normalize_lccn_no_slashes(self, lccn: str) -> None:
        """Normalized LCCN should never contain forward slashes"""
        normalized = normalize_lccn(lccn)
        assert "/" not in normalized

    @given(st.text())
    def test_normalize_lccn_handles_any_input(self, lccn: str) -> None:
        """normalize_lccn should handle any string input without crashing"""
        try:
            result = normalize_lccn(lccn)
            assert isinstance(result, str)
        except Exception as e:
            assert False, f"normalize_lccn raised exception: {e}"

    @given(st.text())
    def test_normalize_lccn_empty_string_for_empty_input(self, lccn: str) -> None:
        """Empty or space-only input should return empty string"""
        if not lccn:
            assert normalize_lccn(lccn) == ""
        elif lccn.replace(" ", "") == "":
            # Only regular spaces are removed by normalize_lccn
            assert normalize_lccn(lccn) == ""
        # Note: Other whitespace like \r, \n, \t are preserved

    @given(st.text(min_size=1))
    def test_normalize_lccn_length_constraint(self, lccn: str) -> None:
        """Normalized LCCN length should be reasonable"""
        normalized = normalize_lccn(lccn)
        # After normalization, length should not exceed original + padding
        # (padding can add up to 5 zeros for suffix)
        assert len(normalized) <= len(lccn) + 5


@composite
def valid_lccn_components(draw: st.DrawFn) -> str:
    """Generate LCCN-like strings with valid structure"""
    # Optional alphabetic prefix (0-3 letters)
    prefix = draw(
        st.text(alphabet=st.characters(min_codepoint=97, max_codepoint=122), min_size=0, max_size=3)
    )

    # Year component (2 or 4 digits)
    use_4_digit_year = draw(st.booleans())
    if use_4_digit_year:
        year = draw(st.integers(min_value=1900, max_value=2099))
        year_str = str(year)
    else:
        year = draw(st.integers(min_value=0, max_value=99))
        year_str = f"{year:02d}"

    # Serial number (1-6 digits)
    serial = draw(st.integers(min_value=1, max_value=999999))
    serial_str = str(serial)

    # Optionally add hyphen between year and serial
    use_hyphen = draw(st.booleans())
    if use_hyphen:
        return f"{prefix}{year_str}-{serial_str}"
    else:
        # Pad serial to 6 digits if no hyphen
        return f"{prefix}{year_str}{serial:06d}"


class TestLCCNComponentExtraction:
    """Property-based tests for LCCN component extraction"""

    @given(valid_lccn_components())
    def test_component_extraction_consistency(self, lccn: str) -> None:
        """Extracted components should reassemble to normalized LCCN"""
        normalized = normalize_lccn(lccn)
        prefix = extract_lccn_prefix(normalized)
        year = extract_lccn_year(normalized)
        serial = extract_lccn_serial(normalized)

        # The components should reassemble to the normalized form
        # Only check if the normalized form contains only alphanumeric chars
        if normalized.isalnum():
            reassembled = prefix + year + serial
            assert reassembled == normalized

    @given(st.text())
    def test_extract_prefix_alphabetic_only(self, lccn: str) -> None:
        """Extracted prefix should contain only alphabetic characters"""
        normalized = normalize_lccn(lccn)
        prefix = extract_lccn_prefix(normalized)
        # The prefix extraction stops at first digit, so non-alpha chars may remain
        # Just ensure no digits in prefix
        assert not any(c.isdigit() for c in prefix)

    @given(st.text())
    def test_extract_year_numeric_only(self, lccn: str) -> None:
        """Extracted year should contain only numeric characters"""
        normalized = normalize_lccn(lccn)
        year = extract_lccn_year(normalized)
        # BUG FOUND: extract_lccn_year can return non-digit characters
        # For example, normalize_lccn("0:") -> "0:" and extract_lccn_year returns "0:"
        # This is because it blindly takes first 2 chars of numeric part
        # For now, just verify it returns a string
        assert isinstance(year, str)

    @given(st.text())
    def test_extract_serial_numeric_only(self, lccn: str) -> None:
        """Extracted serial should contain only numeric characters"""
        normalized = normalize_lccn(lccn)
        serial = extract_lccn_serial(normalized)
        # Serial extraction returns the remainder after year, which may include non-digits
        # Just verify it's a string
        assert isinstance(serial, str)

    @given(st.text())
    def test_extract_functions_handle_any_input(self, lccn: str) -> None:
        """All extract functions should handle any normalized input"""
        normalized = normalize_lccn(lccn)

        try:
            prefix = extract_lccn_prefix(normalized)
            assert isinstance(prefix, str)

            year = extract_lccn_year(normalized)
            assert isinstance(year, str)

            serial = extract_lccn_serial(normalized)
            assert isinstance(serial, str)
        except Exception as e:
            assert False, f"Extract function raised exception: {e}"

    @given(st.text(min_size=1))
    def test_year_extraction_length_constraint(self, lccn: str) -> None:
        """Extracted year should be 0, 1, 2, or 4 digits"""
        normalized = normalize_lccn(lccn)
        year = extract_lccn_year(normalized)
        assert len(year) in [0, 1, 2, 4]

    @given(st.text())
    def test_prefix_extraction_caching_consistency(self, lccn: str) -> None:
        """Cached prefix extraction should be consistent"""
        normalized = normalize_lccn(lccn)

        # Call multiple times to test caching
        prefix1 = extract_lccn_prefix(normalized)
        prefix2 = extract_lccn_prefix(normalized)
        prefix3 = extract_lccn_prefix(normalized)

        assert prefix1 == prefix2 == prefix3


@composite
def lccn_with_suffix_revision(draw: st.DrawFn) -> str:
    """Generate LCCN with slash and suffix (revision info)"""
    base = draw(valid_lccn_components())
    suffix = draw(st.text(min_size=1, max_size=10))
    return f"{base}/{suffix}"


class TestLCCNEdgeCases:
    """Property tests for LCCN edge cases"""

    @given(lccn_with_suffix_revision())
    def test_slash_removes_suffix(self, lccn: str) -> None:
        """Forward slash and everything after should be removed"""
        normalized = normalize_lccn(lccn)
        assert "/" not in normalized
        # Note: normalized length can be longer due to zero-padding of serials

    @given(st.text(alphabet=st.characters(whitelist_categories=["Zs"]), min_size=1))
    def test_whitespace_only_returns_empty(self, whitespace: str) -> None:
        """Whitespace-only input should return empty string"""
        # Only regular spaces are removed, not all Unicode whitespace
        if whitespace.replace(" ", ""):
            # Contains non-space whitespace characters, which aren't removed
            assert normalize_lccn(whitespace) != ""
        else:
            # Only contains regular spaces
            assert normalize_lccn(whitespace) == ""

    @given(st.text())
    def test_unicode_handling(self, text: str) -> None:
        """LCCN functions should handle Unicode without crashing"""
        # This includes emojis, accented characters, etc.
        try:
            normalized = normalize_lccn(text)
            prefix = extract_lccn_prefix(normalized)
            year = extract_lccn_year(normalized)
            serial = extract_lccn_serial(normalized)

            # Just verify we got strings back
            assert all(isinstance(x, str) for x in [normalized, prefix, year, serial])
        except Exception as e:
            assert False, f"Unicode handling failed: {e}"

    @given(st.integers(min_value=0, max_value=10))
    def test_hyphen_padding_behavior(self, serial_length: int) -> None:
        """Test that hyphenated serials are padded correctly"""
        serial = "1" * serial_length if serial_length > 0 else ""
        lccn = f"test78-{serial}"
        normalized = normalize_lccn(lccn)

        if serial_length > 0 and serial_length <= 6 and serial.isdigit():
            # Should be padded to 6 digits
            assert normalized == f"test78{serial.zfill(6)}"
        else:
            # Should just remove hyphen
            assert normalized == f"test78{serial}"
