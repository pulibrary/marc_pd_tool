# tests/unit/infrastructure/config/test_loader.py

"""Test configuration loading and management"""

# Standard library imports
from json import dumps
from os import unlink
from re import compile
from tempfile import NamedTemporaryFile

# Local imports
from marc_pd_tool.infrastructure.config import ConfigLoader
from marc_pd_tool.infrastructure.config import get_config


class TestConfigLoader:
    """Test the ConfigLoader class"""

    def test_default_config_values(self):
        """Test that default configuration values are loaded correctly"""
        config = ConfigLoader()

        # Test scoring weights
        normal_weights = config.get_scoring_weights("normal_with_publisher")
        assert normal_weights["title"] == 0.6
        assert normal_weights["author"] == 0.25
        assert normal_weights["publisher"] == 0.15

        # Test thresholds - updated defaults for better performance
        assert config.get_threshold("title") == 25
        assert config.get_threshold("author") == 20
        assert config.get_threshold("publisher") == 50  # From config.json

        # Test word lists
        stopwords = config.stopwords_set
        assert "the" in stopwords
        assert "and" in stopwords
        assert len(stopwords) > 10

    def test_custom_config_file(self):
        """Test loading from custom JSON configuration file"""
        custom_config = {
            "scoring_weights": {
                "normal_with_publisher": {"title": 0.8, "author": 0.15, "publisher": 0.05}
            },
            "default_thresholds": {"title": 90, "author": 80},
        }

        with NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write(dumps(custom_config))
            config_path = f.name

        try:
            config = ConfigLoader(config_path)

            # Test custom values are loaded
            weights = config.get_scoring_weights("normal_with_publisher")
            assert weights["title"] == 0.8
            assert weights["author"] == 0.15
            assert weights["publisher"] == 0.05

            assert config.get_threshold("title") == 90
            assert config.get_threshold("author") == 80

            # Test that unspecified values fall back to defaults
            assert config.get_threshold("publisher") == 50  # Default value

        finally:

            unlink(config_path)

    def test_partial_config_override(self):
        """Test that partial configuration overrides work with defaults"""
        partial_config = {"default_thresholds": {"title": 85}}  # Only override title threshold

        with NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write(dumps(partial_config))
            config_path = f.name

        try:
            config = ConfigLoader(config_path)

            # Test overridden value
            assert config.get_threshold("title") == 85

            # Test that other values remain at defaults
            assert config.get_threshold("author") == 20
            assert config.get_threshold("publisher") == 50

            # Test that scoring weights are unchanged
            weights = config.get_scoring_weights("normal_with_publisher")
            assert weights["title"] == 0.6

        finally:

            unlink(config_path)

    def test_invalid_config_file(self):
        """Test graceful handling of invalid JSON files"""
        with NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{ invalid json }")
            config_path = f.name

        try:
            # Should not raise exception, should fall back to defaults
            config = ConfigLoader(config_path)
            assert config.get_threshold("title") == 25  # Default value

        finally:

            unlink(config_path)

    def test_missing_config_file(self):
        """Test handling of missing configuration file"""
        config = ConfigLoader("nonexistent_file.json")

        # Should fall back to defaults
        assert config.get_threshold("title") == 25
        assert config.get_threshold("author") == 20

    def test_word_list_access(self):
        """Test accessing word lists from configuration"""
        config = ConfigLoader()

        # Test stopwords
        stopwords = config.stopwords_set
        assert isinstance(stopwords, set)
        assert "the" in stopwords

        # Test publisher stopwords
        pub_stopwords = config.publisher_stopwords
        assert isinstance(pub_stopwords, set)
        assert "publishing" in pub_stopwords  # Changed from "press" which is no longer a stopword

        # Test edition stopwords
        ed_stopwords = config.edition_stopwords
        assert isinstance(ed_stopwords, set)
        assert "edition" in ed_stopwords

    def test_get_config_function(self):
        """Test the global get_config function"""
        config = get_config()
        assert isinstance(config, ConfigLoader)
        assert config.get_threshold("title") == 25

    def test_config_dict_access(self):
        """Test accessing the config as dict"""
        config = ConfigLoader()
        config_dict = config.config
        assert isinstance(config_dict, dict)
        assert "scoring_weights" in config_dict
        assert "default_thresholds" in config_dict

    def test_partial_merge_behavior(self):
        """Test that partial configs merge correctly"""
        custom_config = {
            "scoring_weights": {
                "normal_with_publisher": {
                    "title": 0.7,
                    "author": 0.2,
                    "publisher": 0.1,
                }  # Must sum to 1.0
            }
        }

        with NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write(dumps(custom_config))
            config_path = f.name

        try:
            config = ConfigLoader(config_path)
            weights = config.get_scoring_weights("normal_with_publisher")
            # With Pydantic validation, weights must sum to 1.0
            assert weights["title"] == 0.7  # Overridden
            assert weights["author"] == 0.2  # Overridden
            assert weights["publisher"] == 0.1  # Overridden
        finally:

            unlink(config_path)

    def test_generic_detector_config(self):
        """Test generic title detector configuration access"""
        config = ConfigLoader()

        detector_config = config.generic_detector
        assert hasattr(detector_config, "frequency_threshold")
        assert detector_config.frequency_threshold == 10


class TestConfigLoaderCachedProperties:
    """Test cached property methods of ConfigLoader"""

    def test_author_stopwords(self):
        """Test author stopwords property"""
        loader = ConfigLoader()
        stopwords = loader.author_stopwords
        assert isinstance(stopwords, set)

    def test_title_stopwords(self):
        """Test title stopwords property"""
        loader = ConfigLoader()
        stopwords = loader.title_stopwords
        assert isinstance(stopwords, set)

    def test_all_stopwords(self):
        """Test all stopwords combined property"""
        loader = ConfigLoader()
        stopwords = loader.all_stopwords
        assert isinstance(stopwords, set)
        # Should be a combination of all stopword types
        assert len(stopwords) > 0

    def test_generic_title_patterns(self):
        """Test generic title patterns property"""
        loader = ConfigLoader()
        patterns = loader.generic_title_patterns
        assert isinstance(patterns, set)

    def test_ordinal_terms(self):
        """Test ordinal terms property"""
        loader = ConfigLoader()
        terms = loader.ordinal_terms
        assert isinstance(terms, set)

    def test_abbreviations(self):
        """Test abbreviations property"""
        loader = ConfigLoader()
        abbrevs = loader.abbreviations
        assert isinstance(abbrevs, dict)
        # Should have some default abbreviations
        assert len(abbrevs) > 0

    def test_unicode_corrections(self):
        """Test unicode corrections property"""
        loader = ConfigLoader()
        corrections = loader.unicode_corrections
        assert isinstance(corrections, dict)

    def test_publisher_suffixes(self):
        """Test publisher suffixes property"""
        loader = ConfigLoader()
        suffixes = loader.publisher_suffixes
        assert isinstance(suffixes, list)

    def test_publisher_suffix_regex(self):
        """Test publisher suffix regex property"""
        loader = ConfigLoader()
        regex = loader.publisher_suffix_regex
        assert isinstance(regex, str)
        # Should generate a valid regex pattern
        if regex:
            # Should be compilable
            compile(regex)

    def test_publisher_suffix_regex_with_special_words(self):
        """Test publisher suffix regex handles special words"""
        # Standard library imports
        import json
        import tempfile

        # Create config with special publisher suffixes
        config = {
            "wordlists": {
                "patterns": {"publisher_suffixes": ["publisher", "book", "press", "company"]}
            }
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config, f)
            temp_path = f.name

        try:
            loader = ConfigLoader(config_path=temp_path)
            regex = loader.publisher_suffix_regex

            # Should handle plurals for special words
            assert "publishers?" in regex or "publisher" in regex
            assert "books?" in regex or "book" in regex
            assert "press" in regex
            assert "company" in regex
        finally:

            unlink(temp_path)

    def test_title_processing(self):
        """Test title processing configuration property"""
        loader = ConfigLoader()
        processing = loader.title_processing
        assert isinstance(processing, dict)
        assert "stopwords" in processing
        assert isinstance(processing["stopwords"], list)

    def test_author_processing(self):
        """Test author processing configuration property"""
        loader = ConfigLoader()
        processing = loader.author_processing
        assert isinstance(processing, dict)
        assert "stopwords" in processing
        assert isinstance(processing["stopwords"], list)

    def test_cached_properties_without_wordlists(self):
        """Test cached properties return empty when wordlists is None"""
        # Standard library imports
        import json
        import tempfile

        # Create minimal config without wordlists
        config = {"default_thresholds": {"title": 40, "author": 30}}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config, f)
            temp_path = f.name

        try:
            loader = ConfigLoader(config_path=temp_path)
            # Force _wordlists to None
            loader._wordlists = None

            # All these should return empty collections
            assert loader.author_stopwords == set()
            assert loader.title_stopwords == set()
            assert loader.all_stopwords == set()
            assert loader.generic_title_patterns == set()
            assert loader.ordinal_terms == set()
            assert loader.abbreviations == {}
            assert loader.unicode_corrections == {}
            assert loader.publisher_suffixes == []
            assert loader.publisher_suffix_regex == ""

        finally:

            unlink(temp_path)
