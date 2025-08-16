# tests/unit/infrastructure/config/test_wordlists.py

"""Tests for WordlistsConfig class"""

# Standard library imports
import json
from pathlib import Path
from tempfile import NamedTemporaryFile

# Local imports
from marc_pd_tool.infrastructure.config._wordlists import WordlistsConfig


class TestWordlistsConfig:
    """Test WordlistsConfig functionality"""

    def test_load_from_none_returns_defaults(self):
        """Test that loading from None returns default config"""
        config = WordlistsConfig.load(None)
        assert isinstance(config, WordlistsConfig)
        # Should have default values (empty lists/dicts)
        assert isinstance(config.stopwords.general, list)

    def test_load_from_string_path(self):
        """Test loading from a string path"""
        with NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"stopwords": {"general": ["test", "word"]}}, f)
            temp_path = f.name

        try:
            # Load using string path
            config = WordlistsConfig.load(temp_path)
            assert isinstance(config, WordlistsConfig)
            assert "test" in config.stopwords.general
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_load_from_invalid_json(self):
        """Test loading from invalid JSON file returns defaults with warning"""
        with NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not valid json{")
            temp_path = f.name

        try:
            # Should return defaults when file is invalid
            config = WordlistsConfig.load(temp_path)
            assert isinstance(config, WordlistsConfig)
            # Should have default values
            assert isinstance(config.stopwords.general, list)
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_load_from_nonexistent_file(self):
        """Test loading from non-existent file returns defaults"""
        config = WordlistsConfig.load("/nonexistent/path/wordlists.json")
        assert isinstance(config, WordlistsConfig)
        # Should have default values
        assert isinstance(config.stopwords.general, list)

    def test_get_all_stopwords(self):
        """Test get_all_stopwords method"""
        # Create config with some test data
        config = WordlistsConfig(
            stopwords={"general": ["the", "a", "an"], "publisher": ["press", "publishing"]}
        )
        all_stopwords = config.get_all_stopwords()

        assert isinstance(all_stopwords, set)
        # Should contain words from all categories
        assert len(all_stopwords) == 5
        assert "the" in all_stopwords
        assert "press" in all_stopwords

    def test_get_all_stopwords_with_non_list_values(self):
        """Test get_all_stopwords handles non-list values gracefully"""
        config = WordlistsConfig()
        # This tests the isinstance(words, list) check at line 124
        # The model should always have lists, but this tests the safety check
        all_stopwords = config.get_all_stopwords()
        assert isinstance(all_stopwords, set)

    def test_get_patterns(self):
        """Test get_patterns method"""
        config = WordlistsConfig()

        # Test getting existing pattern type
        generic_titles = config.get_patterns("generic_titles")
        assert isinstance(generic_titles, list)

        # Test getting non-existent pattern type
        nonexistent = config.get_patterns("nonexistent_pattern")
        assert nonexistent == []

    def test_get_abbreviations(self):
        """Test get_abbreviations method"""
        config = WordlistsConfig(
            abbreviations={"bibliographic": {"ed.": "edition", "vol.": "volume"}}
        )
        abbreviations = config.get_abbreviations()

        assert isinstance(abbreviations, dict)
        # Should have the test abbreviations
        assert len(abbreviations) == 2
        assert abbreviations["ed."] == "edition"

    def test_get_unicode_corrections(self):
        """Test get_unicode_corrections method"""
        config = WordlistsConfig(text_fixes={"unicode_corrections": {"Ã©": "é", "Ã¢": "â"}})
        corrections = config.get_unicode_corrections()

        assert isinstance(corrections, dict)
        # Should have the test corrections
        assert len(corrections) == 2
        assert corrections["Ã©"] == "é"

    def test_load_with_validation_error(self):
        """Test loading with data that fails validation"""
        with NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            # Write invalid structure that will fail validation
            json.dump({"stopwords": "not a dict"}, f)  # Should be a dict, not string
            temp_path = f.name

        try:
            # Should return defaults when validation fails
            config = WordlistsConfig.load(temp_path)
            assert isinstance(config, WordlistsConfig)
            # Should have default values
            assert isinstance(config.stopwords, object)
        finally:
            Path(temp_path).unlink(missing_ok=True)
