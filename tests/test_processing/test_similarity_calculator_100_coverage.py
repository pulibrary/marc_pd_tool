# tests/test_processing/test_similarity_calculator_100_coverage.py

"""Additional tests for similarity_calculator.py to achieve 100% coverage"""

# Standard library imports
from unittest.mock import Mock
from unittest.mock import patch

# Third party imports
import pytest

# Local imports
from marc_pd_tool.processing.similarity_calculator import SimilarityCalculator
from marc_pd_tool.infrastructure.config_loader import ConfigLoader
from marc_pd_tool.data.publication import Publication


class TestSimilarityCalculatorEdgeCases:
    """Test edge cases in SimilarityCalculator"""
    
    def test_calculate_title_similarity_no_abbreviation_expansion(self):
        """Test title similarity without abbreviation expansion"""
        # Test lines 72-73 - when abbreviation expansion is disabled
        
        # Create a mock config that disables abbreviation expansion
        mock_config = Mock(spec=ConfigLoader)
        mock_config.get_config.return_value = {
            "matching": {
                "word_based": {
                    "enable_abbreviation_expansion": False,
                    "enable_stemming": True,
                    "default_language": "eng"
                }
            }
        }
        mock_config.get_author_stopwords.return_value = []
        mock_config.get_publisher_stopwords.return_value = []
        
        calculator = SimilarityCalculator(config=mock_config)
        
        score = calculator.calculate_title_similarity(
            "Test Co. Ltd.",
            "Test Co. Ltd."
        )
        assert score > 0
    
    def test_calculate_title_similarity_no_stemming(self):
        """Test title similarity without stemming"""
        # Test lines 98-99 - when stemming is disabled
        
        # Create a mock config that disables stemming
        mock_config = Mock(spec=ConfigLoader)
        mock_config.get_config.return_value = {
            "matching": {
                "word_based": {
                    "enable_abbreviation_expansion": True,
                    "enable_stemming": False,
                    "default_language": "eng"
                }
            }
        }
        mock_config.get_author_stopwords.return_value = []
        mock_config.get_publisher_stopwords.return_value = []
        
        calculator = SimilarityCalculator(config=mock_config)
        
        score = calculator.calculate_title_similarity(
            "Running books quickly",
            "Running books quickly"
        )
        assert score == 100.0  # Exact match without stemming
    
    def test_preprocess_author_empty(self):
        """Test author preprocessing with empty input"""
        # Test line 211 - empty author
        calculator = SimilarityCalculator()
        
        result = calculator._preprocess_author("")
        assert result == ""
        
        result = calculator._preprocess_author(None)
        assert result == ""
    
    def test_preprocess_author_no_abbreviation_expansion(self):
        """Test author preprocessing without abbreviation expansion"""
        # Test line 217 - when abbreviation expansion is disabled
        
        mock_config = Mock(spec=ConfigLoader)
        mock_config.get_config.return_value = {
            "matching": {
                "word_based": {
                    "enable_abbreviation_expansion": False,
                    "enable_stemming": True,
                    "default_language": "eng"
                }
            }
        }
        mock_config.get_author_stopwords.return_value = []
        mock_config.get_publisher_stopwords.return_value = []
        
        calculator = SimilarityCalculator(config=mock_config)
        
        result = calculator._preprocess_author("Smith, J.")
        # Should not expand J.
        assert "j" in result.lower()
    
    def test_preprocess_publisher_empty(self):
        """Test publisher preprocessing with empty input"""
        # Test line 236 - empty publisher
        calculator = SimilarityCalculator()
        
        result = calculator._preprocess_publisher("")
        assert result == ""
        
        result = calculator._preprocess_publisher(None)
        assert result == ""
    
    def test_preprocess_publisher_no_abbreviation_expansion(self):
        """Test publisher preprocessing without abbreviation expansion"""
        # Test line 242 - when abbreviation expansion is disabled
        
        mock_config = Mock(spec=ConfigLoader)
        mock_config.get_config.return_value = {
            "matching": {
                "word_based": {
                    "enable_abbreviation_expansion": False,
                    "enable_stemming": True,
                    "default_language": "eng"
                }
            }
        }
        mock_config.get_author_stopwords.return_value = []
        mock_config.get_publisher_stopwords.return_value = []
        
        calculator = SimilarityCalculator(config=mock_config)
        
        result = calculator._preprocess_publisher("Random House Inc.")
        # Should not expand Inc.
        assert "inc" in result.lower()


class TestCalculatorConfiguration:
    """Test different calculator configurations"""
    
    def test_all_features_disabled(self):
        """Test calculator with all features disabled"""
        
        mock_config = Mock(spec=ConfigLoader)
        mock_config.get_config.return_value = {
            "matching": {
                "word_based": {
                    "enable_abbreviation_expansion": False,
                    "enable_stemming": False,
                    "default_language": "eng"
                }
            }
        }
        mock_config.get_author_stopwords.return_value = []
        mock_config.get_publisher_stopwords.return_value = []
        
        calculator = SimilarityCalculator(config=mock_config)
        
        # Should get perfect scores since minimal preprocessing
        title_score = calculator.calculate_title_similarity(
            "The Running Books Co.",
            "The Running Books Co."
        )
        author_score = calculator.calculate_author_similarity(
            "Smith, J.",
            "Smith, J."
        )
        publisher_score = calculator.calculate_publisher_similarity(
            "Random House Inc.",
            "Random House Inc.",
            copyright_full_text=""
        )
        
        assert title_score > 95  # Very high match
        assert author_score == 100.0  # Exact match
        assert publisher_score == 100.0  # Exact match
    
    def test_mixed_configurations(self):
        """Test calculator with mixed configurations"""
        # Enable abbreviation but not stemming
        mock_config = Mock(spec=ConfigLoader)
        mock_config.get_config.return_value = {
            "matching": {
                "word_based": {
                    "enable_abbreviation_expansion": True,
                    "enable_stemming": False,
                    "default_language": "eng"
                }
            }
        }
        mock_config.get_author_stopwords.return_value = []
        mock_config.get_publisher_stopwords.return_value = []
        
        calculator = SimilarityCalculator(config=mock_config)
        
        score = calculator.calculate_title_similarity(
            "Test Co. Publications",
            "Test Company Publications"
        )
        assert score > 40  # Should match after abbreviation expansion


class TestPublicationObjectHandling:
    """Test handling of Publication objects"""
    
    def test_calculate_similarity_with_publications(self):
        """Test similarity calculation using Publication objects"""
        calculator = SimilarityCalculator()
        
        marc_pub = Publication(
            title="Test Book",
            author="Test Author",
            publisher="Test Publisher",
            source_id="001"
        )
        
        copyright_pub = Publication(
            title="Test Book",
            author="Test Author",
            publisher="Test Publisher",
            source_id="c001"
        )
        
        # Calculate similarities using publication attributes
        title_score = calculator.calculate_title_similarity(
            marc_pub.title,
            copyright_pub.title
        )
        author_score = calculator.calculate_author_similarity(
            marc_pub.author or "",
            copyright_pub.author or ""
        )
        publisher_score = calculator.calculate_publisher_similarity(
            marc_pub.publisher or "",
            copyright_pub.publisher or "",
            copyright_full_text=""
        )
        
        assert title_score == 100.0
        assert author_score == 100.0
        assert publisher_score == 100.0


class TestEdgeCasesWithSpecialCharacters:
    """Test edge cases with special characters and formatting"""
    
    def test_titles_with_special_characters(self):
        """Test titles with special characters"""
        calculator = SimilarityCalculator()
        
        score = calculator.calculate_title_similarity(
            "Test & Co., Inc.",
            "Test and Company, Incorporated"
        )
        
        assert score > 10  # Should have some match with special characters
    
    def test_empty_fields_handling(self):
        """Test handling of empty fields"""
        calculator = SimilarityCalculator()
        
        # Should handle empty fields gracefully
        title_score = calculator.calculate_title_similarity("", "Test Title")
        author_score = calculator.calculate_author_similarity("", "Test Author")
        publisher_score = calculator.calculate_publisher_similarity("", "Test Publisher", copyright_full_text="")
        
        assert title_score == 0.0
        assert author_score == 0.0
        assert publisher_score >= 0.0  # Should handle empty fields gracefully


class TestLanguageSpecificProcessing:
    """Test language-specific processing"""
    
    def test_non_english_processing(self):
        """Test processing with non-English language"""
        calculator = SimilarityCalculator()
        
        # Should use French stopwords
        score = calculator.calculate_title_similarity(
            "Le Grand Livre",
            "Le Grand Livre",
            language="fre"
        )
        assert score == 100.0
    
    def test_language_fallback(self):
        """Test language fallback for unsupported languages"""
        calculator = SimilarityCalculator()
        
        # Should fall back to English for unsupported language
        score = calculator.calculate_title_similarity(
            "The Book",
            "The Book",
            language="jpn"  # Not supported
        )
        assert score == 100.0