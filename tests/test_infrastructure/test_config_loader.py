# tests/test_infrastructure/test_config_loader.py

"""Test configuration loading and management"""

# Standard library imports
from json import dumps
from tempfile import NamedTemporaryFile

# Local imports
from marc_pd_tool.infrastructure.config_loader import ConfigLoader
from marc_pd_tool.infrastructure.config_loader import get_config
from marc_pd_tool.infrastructure.config_loader import load_config


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

        # Test thresholds - values from config.json
        assert config.get_threshold("title") == 40
        assert config.get_threshold("author") == 30
        assert config.get_threshold("publisher") == 30

        # Test word lists
        stopwords = config.get_stopwords()
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
            assert config.get_threshold("publisher") == 60  # Default value

        finally:
            # Standard library imports
            import os

            os.unlink(config_path)

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
            assert config.get_threshold("author") == 30
            assert config.get_threshold("publisher") == 60

            # Test that scoring weights are unchanged
            weights = config.get_scoring_weights("normal_with_publisher")
            assert weights["title"] == 0.6

        finally:
            # Standard library imports
            import os

            os.unlink(config_path)

    def test_invalid_config_file(self):
        """Test graceful handling of invalid JSON files"""
        with NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{ invalid json }")
            config_path = f.name

        try:
            # Should not raise exception, should fall back to defaults
            config = ConfigLoader(config_path)
            assert config.get_threshold("title") == 40  # Default value

        finally:
            # Standard library imports
            import os

            os.unlink(config_path)

    def test_missing_config_file(self):
        """Test handling of missing configuration file"""
        config = ConfigLoader("nonexistent_file.json")

        # Should fall back to defaults
        assert config.get_threshold("title") == 40
        assert config.get_threshold("author") == 30

    def test_word_list_access(self):
        """Test accessing word lists from configuration"""
        config = ConfigLoader()

        # Test stopwords
        stopwords = config.get_stopwords_set()
        assert isinstance(stopwords, set)
        assert "the" in stopwords

        # Test publisher stopwords
        pub_stopwords = config.get_publisher_stopwords()
        assert isinstance(pub_stopwords, set)
        assert "publishing" in pub_stopwords  # Changed from "press" which is no longer a stopword

        # Test edition stopwords
        ed_stopwords = config.get_edition_stopwords()
        assert isinstance(ed_stopwords, set)
        assert "edition" in ed_stopwords

    def test_get_config_function(self):
        """Test the global get_config function"""
        config = get_config()
        assert isinstance(config, ConfigLoader)
        assert config.get_threshold("title") == 40

    def test_load_config_function(self):
        """Test the load_config function"""
        config_dict = load_config()
        assert isinstance(config_dict, dict)
        assert "scoring_weights" in config_dict
        assert "default_thresholds" in config_dict

    def test_deep_merge(self):
        """Test that deep merging works correctly"""
        config_loader = ConfigLoader()

        base = {"level1": {"level2": {"key1": "value1", "key2": "value2"}, "other": "value"}}

        update = {
            "level1": {
                "level2": {"key1": "new_value1", "key3": "value3"}  # Override  # Add new
                # Don't override "other"
            }
        }

        result = config_loader._deep_merge(base, update)

        assert result["level1"]["level2"]["key1"] == "new_value1"  # Overridden
        assert result["level1"]["level2"]["key2"] == "value2"  # Preserved
        assert result["level1"]["level2"]["key3"] == "value3"  # Added
        assert result["level1"]["other"] == "value"  # Preserved

    def test_generic_detector_config(self):
        """Test generic title detector configuration access"""
        config = ConfigLoader()

        detector_config = config.get_generic_detector_config()
        assert isinstance(detector_config, dict)
        assert "frequency_threshold" in detector_config
        assert detector_config["frequency_threshold"] == 10
