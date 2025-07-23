# tests/test_utils/test_bracketed_content_removal.py

"""Tests for bracketed content removal functionality"""

# Third party imports
from pytest import mark
from pytest import param

# Local imports
from marc_pd_tool.utils.text_utils import remove_bracketed_content


class TestBracketedContentRemoval:
    """Test removal of bracketed content from titles"""

    def test_basic_removal(self):
        """Test basic bracketed content removal"""
        assert remove_bracketed_content("Title [microform]") == "Title"
        assert remove_bracketed_content("Title [electronic resource]") == "Title"
        assert remove_bracketed_content("Title [videorecording]") == "Title"
        assert remove_bracketed_content("Title [sound recording]") == "Title"

    def test_multiple_brackets(self):
        """Test removal of multiple bracketed sections"""
        assert remove_bracketed_content("Title [part 1] [microform]") == "Title"
        assert remove_bracketed_content("[Series] Title [electronic resource]") == "Title"
        assert (
            remove_bracketed_content("Title [version 2] : subtitle [microform]")
            == "Title : subtitle"
        )

    def test_preserves_non_bracketed_text(self):
        """Test that non-bracketed text is preserved"""
        assert remove_bracketed_content("Title with no brackets") == "Title with no brackets"
        assert remove_bracketed_content("Title (with parentheses)") == "Title (with parentheses)"
        assert remove_bracketed_content("Title {with braces}") == "Title {with braces}"

    def test_whitespace_normalization(self):
        """Test that whitespace is normalized after removal"""
        assert remove_bracketed_content("Title  [microform]  subtitle") == "Title subtitle"
        assert remove_bracketed_content("Title[microform]") == "Title"
        assert remove_bracketed_content("  Title  [electronic resource]  ") == "Title"

    def test_empty_brackets(self):
        """Test handling of empty brackets"""
        assert remove_bracketed_content("Title []") == "Title"
        assert remove_bracketed_content("Title [ ]") == "Title"
        assert remove_bracketed_content("Title [  ]") == "Title"

    def test_nested_brackets(self):
        """Test handling of nested brackets (rare but possible)"""
        # Square brackets typically aren't nested in MARC, but test anyway
        assert remove_bracketed_content("Title [note [subnote]]") == "Title"
        assert remove_bracketed_content("Title [[nested]]") == "Title"

    def test_edge_cases(self):
        """Test edge cases"""
        assert remove_bracketed_content("") == ""
        assert remove_bracketed_content(None) == ""
        assert remove_bracketed_content("   ") == ""
        assert remove_bracketed_content("[only brackets]") == ""
        assert remove_bracketed_content("[]") == ""

    def test_unmatched_brackets(self):
        """Test handling of unmatched brackets"""
        # These should be preserved as-is since they're not complete bracketed sections
        assert remove_bracketed_content("Title [unclosed") == "Title [unclosed"
        assert remove_bracketed_content("Title closed]") == "Title closed]"
        assert remove_bracketed_content("Title ]wrong[ order") == "Title ]wrong[ order"

    @mark.parametrize(
        "title,expected",
        [
            param("Complete works [microform]", "Complete works", id="complete_works"),
            param(
                "Poems, 1900-1950 [electronic resource]", "Poems, 1900-1950", id="poems_with_dates"
            ),
            param("Letters [microform] : vol. 1", "Letters : vol. 1", id="letters_with_volume"),
            param("Title [1st ed.] [microform]", "Title", id="edition_and_format"),
            param("The [?] mystery [sound recording]", "The mystery", id="question_mark_bracket"),
        ],
    )
    def test_real_world_examples(self, title, expected):
        """Test with real-world MARC title examples"""
        assert remove_bracketed_content(title) == expected

    def test_integration_with_normalization(self):
        """Test that bracketed content removal works with text normalization"""
        # Local imports
        from marc_pd_tool.utils.text_utils import normalize_text_standard

        # Test that normalize_text_standard doesn't interfere with bracketed content
        # (it should be removed before normalization in the pipeline)
        original = "Title [microform] : subtitle"
        without_brackets = remove_bracketed_content(original)
        normalized = normalize_text_standard(without_brackets)

        assert without_brackets == "Title : subtitle"
        assert normalized == "title subtitle"  # normalize_text_standard removes punctuation

    def test_common_marc_format_designators(self):
        """Test removal of common MARC format designators"""
        format_designators = [
            "[microform]",
            "[electronic resource]",
            "[videorecording]",
            "[sound recording]",
            "[music]",
            "[manuscript]",
            "[computer file]",
            "[kit]",
            "[realia]",
            "[cartographic material]",
            "[graphic]",
            "[motion picture]",
            "[filmstrip]",
            "[transparency]",
            "[slide]",
        ]

        for designator in format_designators:
            title = f"Sample Title {designator}"
            assert remove_bracketed_content(title) == "Sample Title"
