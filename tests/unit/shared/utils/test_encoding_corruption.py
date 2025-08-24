# tests/unit/shared/utils/test_encoding_corruption.py

"""Test encoding corruption detection and fixing"""

# Local imports
from marc_pd_tool.shared.utils.text_utils import fix_latin1_corruption
from marc_pd_tool.shared.utils.text_utils import normalize_unicode


class TestEncodingCorruption:
    """Test encoding corruption fixes for Pattern 4 from matching edge cases"""

    def test_fix_latin1_corruption_basic(self):
        """Test basic Latin-1 mojibake fixing"""
        # Common Spanish text corrupted
        corrupted = "José García"  # José García
        fixed = fix_latin1_corruption(corrupted)
        # After fixing mojibake, normalize_unicode will convert to ASCII
        assert "Jos" in normalize_unicode(fixed)

    def test_fix_latin1_corruption_hebrew_example(self):
        """Test the Hebrew example from ground truth"""
        # From 9917858543506420
        corrupted = "RevÃ£rend's hand bukh"
        fixed = fix_latin1_corruption(corrupted)
        # Can't fully recover Hebrew, but should remove obvious corruption
        assert "Ã£" not in fixed

    def test_fix_latin1_corruption_no_mojibake(self):
        """Test that normal text is not modified"""
        normal = "This is normal English text"
        fixed = fix_latin1_corruption(normal)
        assert fixed == normal

    def test_fix_latin1_corruption_smart_quotes(self):
        """Test fixing smart quotes mojibake"""
        corrupted = "â€œHello worldâ€"
        fixed = fix_latin1_corruption(corrupted)
        # Should fix smart quotes
        assert "â€" not in fixed

    def test_fix_latin1_corruption_empty_string(self):
        """Test handling of empty strings"""
        assert fix_latin1_corruption("") == ""
        assert fix_latin1_corruption(None or "") == ""

    def test_normalize_unicode_with_mojibake(self):
        """Test full pipeline with mojibake"""
        corrupted = "José"  # José with consistent mojibake
        normalized = normalize_unicode(corrupted)
        # Should fix mojibake and then ASCII fold
        assert "Jose" == normalized

    def test_partial_mojibake(self):
        """Test text with partial mojibake"""
        # Mix of corrupted and normal text
        mixed = "Normal text and José García"
        fixed = fix_latin1_corruption(mixed)
        # Should fix corrupted part while preserving normal part
        assert "Normal text" in fixed
        assert "Ã©" not in fixed

    def test_double_encoding(self):
        """Test handling of double encoding errors"""
        # UTF-8 → Latin-1 → UTF-8 → Latin-1 (double corruption)
        double_corrupted = "Ã\x83Â£"  # Even more corrupted
        fixed = fix_latin1_corruption(double_corrupted)
        # Should at least not crash and return something
        assert fixed is not None

    def test_eastern_european_mojibake(self):
        """Test Eastern European character mojibake"""
        corrupted = "PraÅ¾skÃ½"  # Pražský (Czech)
        fix_latin1_corruption(corrupted)
        normalized = normalize_unicode(corrupted)
        # After full normalization should be ASCII
        assert "Å¾" not in normalized
        assert "Ã½" not in normalized

    def test_validation_prevents_data_loss(self):
        """Test that validation prevents significant data loss"""
        # Text that might be incorrectly identified as mojibake
        text_with_special = "Ärztekammer"  # German medical chamber
        fixed = fix_latin1_corruption(text_with_special)
        # Should preserve text if fix would cause significant loss
        assert len(fixed) >= len(text_with_special) * 0.5
