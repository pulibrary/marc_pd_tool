# tests/test_processing/test_matching.py

"""Tests for word-based matching implementation"""

# Standard library imports
from unittest.mock import MagicMock
from unittest.mock import patch

# Third party imports
import pytest

# Local imports
from marc_pd_tool.data.publication import CountryClassification
from marc_pd_tool.data.publication import Publication
from marc_pd_tool.infrastructure.config_loader import ConfigLoader
from marc_pd_tool.processing.matching_engine import DataMatcher
from marc_pd_tool.processing.similarity_calculator import SimilarityCalculator
from marc_pd_tool.processing.text_processing import LanguageProcessor
from marc_pd_tool.processing.text_processing import MultiLanguageStemmer
from marc_pd_tool.processing.text_processing import PUBLISHING_ABBREVIATIONS
from marc_pd_tool.processing.text_processing import expand_abbreviations


class TestLanguageProcessor:
    """Test language processing for stopword removal"""

    def test_language_processor_init(self):
        """Test LanguageProcessor initialization"""
        processor = LanguageProcessor()
        assert "eng" in processor.stopwords
        assert "fre" in processor.stopwords
        assert "ger" in processor.stopwords

    def test_remove_stopwords_english(self):
        """Test English stopword removal"""
        processor = LanguageProcessor()
        result = processor.remove_stopwords("the great adventures of sherlock holmes", "eng")

        # Should remove 'the' and 'of' but keep significant words
        assert "great" in result
        assert "adventures" in result
        assert "sherlock" in result
        assert "holmes" in result
        assert "the" not in result
        assert "of" not in result

    def test_remove_stopwords_french(self):
        """Test French stopword removal"""
        processor = LanguageProcessor()
        result = processor.remove_stopwords("les aventures de sherlock holmes", "fre")

        # Should remove French stopwords
        assert "aventures" in result
        assert "sherlock" in result
        assert "holmes" in result
        assert "les" not in result
        assert "de" not in result

    def test_remove_stopwords_empty_text(self):
        """Test stopword removal with empty text"""
        processor = LanguageProcessor()
        result = processor.remove_stopwords("", "eng")
        assert result == []

    def test_remove_stopwords_unknown_language(self):
        """Test stopword removal falls back to English for unknown languages"""
        processor = LanguageProcessor()
        result = processor.remove_stopwords("the great book", "unknown")

        # Should use English stopwords as fallback
        assert "great" in result
        assert "book" in result
        assert "the" not in result

    def test_remove_stopwords_filters_short_words(self):
        """Test that words shorter than 2 characters are filtered"""
        processor = LanguageProcessor()
        result = processor.remove_stopwords("a great book by x", "eng")

        assert "great" in result
        assert "book" in result
        # 'by' is a stopword so it should be removed
        assert "by" not in result
        assert "x" not in result  # Single character filtered


class TestMultiLanguageStemmer:
    """Test multilingual stemming functionality"""

    def test_stemmer_init(self):
        """Test MultiLanguageStemmer initialization"""
        stemmer = MultiLanguageStemmer()
        # Test lazy initialization by calling _get_stemmers
        stemmers = stemmer._get_stemmers()
        assert "eng" in stemmers
        assert "fre" in stemmers
        assert "ger" in stemmers

    def test_stem_words_english(self):
        """Test English word stemming"""
        stemmer = MultiLanguageStemmer()
        words = ["running", "books", "cats", "swimming"]
        result = stemmer.stem_words(words, "eng")

        # Should stem words to their roots
        assert "run" in result or "runn" in result  # stemming may vary
        assert "book" in result
        assert "cat" in result
        assert "swim" in result

    def test_stem_words_empty_list(self):
        """Test stemming with empty word list"""
        stemmer = MultiLanguageStemmer()
        result = stemmer.stem_words([], "eng")
        assert result == []

    def test_stem_words_unknown_language(self):
        """Test stemming falls back to English for unknown languages"""
        stemmer = MultiLanguageStemmer()
        words = ["running", "books"]
        result = stemmer.stem_words(words, "unknown")

        # Should use English stemmer as fallback
        assert len(result) == 2


class TestPublishingAbbreviations:
    """Test publishing abbreviation expansion"""

    def test_abbreviations_dictionary(self):
        """Test abbreviations dictionary has expected entries"""
        # Test original abbreviations
        assert "vol" in PUBLISHING_ABBREVIATIONS
        assert "co" in PUBLISHING_ABBREVIATIONS
        assert "ed" in PUBLISHING_ABBREVIATIONS
        assert PUBLISHING_ABBREVIATIONS["ed"] == "edition"

        # Test new AACR2 abbreviations
        assert "ms" in PUBLISHING_ABBREVIATIONS
        assert PUBLISHING_ABBREVIATIONS["ms"] == "manuscript"
        assert "suppl" in PUBLISHING_ABBREVIATIONS
        assert PUBLISHING_ABBREVIATIONS["suppl"] == "supplement"
        assert "ca" in PUBLISHING_ABBREVIATIONS
        assert PUBLISHING_ABBREVIATIONS["ca"] == "circa"

    def test_expand_abbreviations_basic(self):
        """Test basic abbreviation expansion"""
        result = expand_abbreviations("vol. 1 by smith co.")

        assert "volume" in result
        assert "company" in result

    def test_expand_abbreviations_with_periods(self):
        """Test expansion works with periods"""
        result = expand_abbreviations("pub. by univ. press")

        assert "publisher" in result
        assert "university" in result

    def test_expand_abbreviations_empty_text(self):
        """Test expansion with empty text"""
        result = expand_abbreviations("")
        assert result == ""

    def test_expand_abbreviations_no_matches(self):
        """Test expansion when no abbreviations are found"""
        original = "this text has no abbreviations"
        result = expand_abbreviations(original)
        assert result == original

    def test_expand_abbreviations_aacr2(self):
        """Test expansion of AACR2 bibliographic abbreviations"""
        # Test manuscript abbreviations
        result = expand_abbreviations("ancient ms. from ca. 1500")
        assert "manuscript" in result
        assert "circa" in result

        # Test supplement and series
        result = expand_abbreviations("n.s. vol. 5, suppl.")
        assert "new series" in result
        assert "volume" in result
        assert "supplement" in result

        # Test multilingual abbreviations
        result = expand_abbreviations("nouv. ed. rev.")
        assert "nouvelle" in result  # French: new
        assert "edition" in result
        assert "revised" in result


class TestSimilarityCalculator:
    """Test enhanced word-based similarity calculation"""

    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration"""
        config = MagicMock(spec=ConfigLoader)
        config.get_config.return_value = {
            "matching": {
                "word_based": {
                    "default_language": "eng",
                    "enable_stemming": True,
                    "enable_abbreviation_expansion": True,
                }
            }
        }
        # Add method mocks for stopwords
        config.get_author_stopwords.return_value = {
            "by",
            "edited",
            "compiled",
            "translated",
            "author",
            "editor",
        }
        config.get_publisher_stopwords.return_value = {
            "publishing",
            "publishers",
            "company",
            "corp",
            "corporation",
            "inc",
            "incorporated",
        }
        return config

    @pytest.fixture
    def calculator(self, mock_config):
        """Create calculator with mock config"""
        return SimilarityCalculator(mock_config)

    def test_calculator_initialization(self, mock_config):
        """Test calculator initialization"""
        calc = SimilarityCalculator(mock_config)
        assert calc.default_language == "eng"
        assert calc.enable_stemming is True
        assert calc.enable_abbreviation_expansion is True

    def test_calculate_title_similarity_exact_match(self, calculator):
        """Test title similarity for exact matches"""
        score = calculator.calculate_title_similarity("the great gatsby", "the great gatsby")
        assert score == 100.0

    def test_calculate_title_similarity_word_overlap(self, calculator):
        """Test title similarity with partial word overlap"""
        score = calculator.calculate_title_similarity(
            "the adventures of sherlock holmes", "sherlock holmes adventures"
        )
        # Should have high similarity due to word overlap after stopword removal
        assert score > 60.0

    def test_calculate_title_similarity_no_overlap(self, calculator):
        """Test title similarity with no word overlap"""
        score = calculator.calculate_title_similarity("pride and prejudice", "war and peace")
        # Should have some similarity due to 'and' but low overall
        assert score < 50.0

    def test_calculate_title_similarity_partial_match(self, calculator):
        """Test title similarity with partial/truncated titles"""
        # Test case from ground truth: shorter title contained in longer
        score = calculator.calculate_title_similarity(
            "iduna robiat", "iduna robiat historischer roman aus merans vergangenheit"
        )
        # Should score much higher than the original 33.3%
        assert score > 50.0

        # Another case: "enoch arden im riesengebirge" vs full title with author
        score = calculator.calculate_title_similarity(
            "enoch arden im riesengebirge",
            "enoch arden im riesengebirge roman von gertrud weymar hey",
        )
        assert score > 60.0

    def test_calculate_title_similarity_partial_match_minimum_words(self, calculator):
        """Test that partial matching requires at least 2 words"""
        # Single word shouldn't trigger partial matching boost
        score = calculator.calculate_title_similarity(
            "shakespeare", "shakespeare complete works volume one"
        )
        # Should get standard Jaccard score, not boosted
        assert score < 40.0

    def test_calculate_title_similarity_short_title_keeps_stopwords(self, calculator):
        """Test that short titles (≤6 words) keep stopwords"""
        # German short title that would be reduced to almost nothing with stopwords
        score = calculator.calculate_title_similarity(
            "ich will was ich soll",  # 5 words - should keep stopwords
            "ich will was ich soll roman einzig berechtigte",  # longer version
            "ger",
        )
        # Should score much higher than if stopwords were removed
        assert score > 50.0

        # Test English short title
        score = calculator.calculate_title_similarity(
            "the great gatsby",  # 3 words - should keep stopwords
            "the great gatsby a novel",  # longer version
            "eng",
        )
        assert score > 60.0

    def test_calculate_title_similarity_long_title_removes_stopwords(self, calculator):
        """Test that longer titles still get stopword removal"""
        # Create a long title (>5 words) that should get stopword removal
        long_title1 = "the great adventures of sherlock holmes detective"  # 7 words
        long_title2 = (
            "great adventures sherlock holmes detective mystery"  # similar without stopwords
        )

        score = calculator.calculate_title_similarity(long_title1, long_title2, "eng")
        # Should still score well even with stopword removal
        assert score > 60.0

    def test_calculate_title_similarity_empty_titles(self, calculator):
        """Test title similarity with empty titles"""
        score = calculator.calculate_title_similarity("", "")
        assert score == 100.0  # Both empty

        score = calculator.calculate_title_similarity("title", "")
        assert score == 0.0  # One empty, one not

        score = calculator.calculate_title_similarity("", "title")
        assert score == 0.0  # One empty, one not

    @patch("marc_pd_tool.processing.similarity_calculator.fuzz")
    def test_calculate_author_similarity_uses_fuzzy_matching(self, mock_fuzz, calculator):
        """Test author similarity uses fuzzy matching with preprocessing"""
        mock_fuzz.ratio.return_value = 85.0

        score = calculator.calculate_author_similarity("Smith, John", "John Smith")

        assert score == 85.0
        mock_fuzz.ratio.assert_called_once()

    def test_calculate_author_similarity_empty_authors(self, calculator):
        """Test author similarity with empty authors"""
        score = calculator.calculate_author_similarity("", "Smith, John")
        assert score == 0.0

        score = calculator.calculate_author_similarity("Smith, John", "")
        assert score == 0.0

    @patch("marc_pd_tool.processing.similarity_calculator.fuzz")
    def test_calculate_publisher_similarity_direct(self, mock_fuzz, calculator):
        """Test publisher similarity for direct comparison"""
        mock_fuzz.ratio.return_value = 90.0

        score = calculator.calculate_publisher_similarity("Random House", "Random House Inc", "")

        assert score == 90.0
        mock_fuzz.ratio.assert_called_once()

    @patch("marc_pd_tool.processing.similarity_calculator.fuzz")
    def test_calculate_publisher_similarity_full_text(self, mock_fuzz, calculator):
        """Test publisher similarity against full text"""
        mock_fuzz.partial_ratio.return_value = 75.0

        score = calculator.calculate_publisher_similarity(
            "Random House", "", "Published by Random House in New York"
        )

        assert score == 75.0
        mock_fuzz.partial_ratio.assert_called_once()

    def test_preprocess_author_removes_qualifiers(self, calculator):
        """Test author preprocessing removes common qualifiers"""
        result = calculator._preprocess_author("edited by John Smith")
        assert "edited" not in result.lower()
        assert "john" in result.lower()
        assert "smith" in result.lower()

    def test_preprocess_publisher_removes_stopwords(self, calculator):
        """Test publisher preprocessing removes publisher stopwords"""
        result = calculator._preprocess_publisher("Random House Publishing Company")
        assert "random" in result.lower()
        assert "house" in result.lower()
        assert "publishing" not in result.lower()
        assert "company" not in result.lower()


class TestDataMatcher:
    """Test enhanced word-based matching engine"""

    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration"""
        config = MagicMock(spec=ConfigLoader)
        config.get_config.return_value = {
            "matching": {
                "word_based": {
                    "default_language": "eng",
                    "enable_stemming": True,
                    "enable_abbreviation_expansion": True,
                }
            },
            "scoring_weights": {
                "normal_with_publisher": {"title": 0.6, "author": 0.25, "publisher": 0.15},
                "generic_with_publisher": {"title": 0.3, "author": 0.45, "publisher": 0.25},
                "normal_no_publisher": {"title": 0.7, "author": 0.3},
                "generic_no_publisher": {"title": 0.4, "author": 0.6},
            },
        }
        config.get_threshold.side_effect = lambda name: {
            "title": 80,
            "author": 70,
            "publisher": 60,
            "early_exit_title": 95,
            "early_exit_author": 90,
            "year_tolerance": 2,
        }.get(name, 80)
        config.get_scoring_weights.side_effect = lambda scenario: {
            "normal_with_publisher": {"title": 0.6, "author": 0.25, "publisher": 0.15},
            "generic_with_publisher": {"title": 0.3, "author": 0.45, "publisher": 0.25},
            "normal_no_publisher": {"title": 0.7, "author": 0.3},
            "generic_no_publisher": {"title": 0.4, "author": 0.6},
        }.get(scenario, {"title": 0.6, "author": 0.25, "publisher": 0.15})
        return config

    @pytest.fixture
    def marc_pub(self):
        """Create a sample MARC publication"""
        return Publication(
            title="The Adventures of Sherlock Holmes",
            author="Doyle, Arthur Conan",
            main_author="Doyle, Arthur Conan",
            pub_date="1892",
            publisher="George Newnes",
            place="London",
            source="MARC",
            country_classification=CountryClassification.US,
        )

    @pytest.fixture
    def copyright_pubs(self):
        """Create sample copyright publications"""
        return [
            Publication(
                title="Adventures of Sherlock Holmes",
                author="Arthur Conan Doyle",
                pub_date="1892",
                publisher="Newnes",
                source="Registration",
                source_id="A123456",
            ),
            Publication(
                title="Study in Scarlet",
                author="Arthur Conan Doyle",
                pub_date="1887",
                publisher="Ward Lock",
                source="Registration",
                source_id="A654321",
            ),
        ]

    def test_engine_initialization(self, mock_config):
        """Test word-based matching engine initialization"""
        engine = DataMatcher(config=mock_config)
        assert engine.config == mock_config
        assert isinstance(engine.similarity_calculator, SimilarityCalculator)

    def test_find_best_match_perfect_match(self, mock_config, marc_pub, copyright_pubs):
        """Test finding perfect match"""
        engine = DataMatcher(config=mock_config)

        result = engine.find_best_match(
            marc_pub, copyright_pubs, 50, 50, 5, 50, 95, 90  # Lower thresholds
        )

        assert result is not None
        assert result["copyright_record"]["source_id"] == "A123456"

    def test_find_best_match_no_candidates(self, mock_config, marc_pub):
        """Test with no copyright publications"""
        engine = DataMatcher(config=mock_config)

        result = engine.find_best_match(marc_pub, [], 80, 70, 2, 60, 95, 90)

        assert result is None

    def test_find_best_match_year_filtering(self, mock_config, marc_pub, copyright_pubs):
        """Test year filtering works"""
        engine = DataMatcher(config=mock_config)

        # Set strict year tolerance that should exclude second publication
        result = engine.find_best_match(
            marc_pub, copyright_pubs, 50, 50, 1, 50, 95, 90  # year_tolerance=1, lower thresholds
        )

        # Should still find the 1892 match but not the 1887 one
        assert result is not None
        assert result["copyright_record"]["year"] == 1892

    def test_find_best_match_dual_author_scoring(self, mock_config, copyright_pubs):
        """Test dual author scoring (245c vs 1xx)"""
        engine = DataMatcher(config=mock_config)

        # Create MARC pub with different author formats
        marc_pub = Publication(
            title="Adventures of Sherlock Holmes",
            author="by Arthur Conan Doyle",  # 245c format
            main_author="Doyle, Arthur Conan",  # 1xx format
            pub_date="1892",
            source="MARC",
            country_classification=CountryClassification.US,
        )

        result = engine.find_best_match(
            marc_pub, copyright_pubs, 50, 50, 5, 50, 95, 90  # Lower thresholds
        )

        assert result is not None
        # Should use the better of the two author matches
        assert result["similarity_scores"]["author"] > 0

    def test_find_best_match_early_exit(self, mock_config, marc_pub, copyright_pubs):
        """Test early exit functionality"""
        engine = DataMatcher(config=mock_config)

        # Mock high-confidence match to trigger early exit
        with (
            patch.object(
                engine.similarity_calculator, "calculate_title_similarity", return_value=96.0
            ),
            patch.object(
                engine.similarity_calculator, "calculate_author_similarity", return_value=92.0
            ),
        ):

            result = engine.find_best_match(marc_pub, copyright_pubs, 80, 70, 2, 60, 95, 90)

            assert result is not None
            # Should exit early and return first high-confidence match

    def test_create_match_result_structure(self, mock_config, marc_pub, copyright_pubs):
        """Test match result structure is correct"""
        engine = DataMatcher(config=mock_config)

        result = engine.find_best_match(
            marc_pub, copyright_pubs, 50, 50, 5, 50, 95, 90  # Lower thresholds
        )

        assert result is not None

        # Check result structure
        assert "copyright_record" in result
        assert "similarity_scores" in result

        # Check copyright record fields
        copyright_record = result["copyright_record"]
        assert "title" in copyright_record
        assert "author" in copyright_record
        assert "year" in copyright_record
        assert "publisher" in copyright_record
        assert "source_id" in copyright_record

        # Check similarity scores
        scores = result["similarity_scores"]
        assert "title" in scores
        assert "author" in scores
        assert "publisher" in scores
        assert "combined" in scores


class TestMatchingIntegration:
    """Integration tests for enhanced matching system"""

    def test_enhanced_matching_with_stemming_disabled(self):
        """Test enhanced matching with stemming disabled"""
        config = MagicMock(spec=ConfigLoader)
        config.get_config.return_value = {
            "matching": {
                "word_based": {
                    "default_language": "eng",
                    "enable_stemming": False,  # Disabled
                    "enable_abbreviation_expansion": True,
                }
            }
        }

        calc = SimilarityCalculator(config)
        assert not calc.enable_stemming

    def test_enhanced_matching_with_abbreviation_expansion_disabled(self):
        """Test enhanced matching with abbreviation expansion disabled"""
        config = MagicMock(spec=ConfigLoader)
        config.get_config.return_value = {
            "matching": {
                "word_based": {
                    "default_language": "eng",
                    "enable_stemming": True,
                    "enable_abbreviation_expansion": False,  # Disabled
                }
            }
        }

        calc = SimilarityCalculator(config)
        assert not calc.enable_abbreviation_expansion

    def test_enhanced_matching_different_languages(self):
        """Test enhanced matching with different default languages"""
        config = MagicMock(spec=ConfigLoader)
        config.get_config.return_value = {
            "matching": {
                "word_based": {
                    "default_language": "fre",  # French
                    "enable_stemming": True,
                    "enable_abbreviation_expansion": True,
                }
            }
        }

        calc = SimilarityCalculator(config)
        assert calc.default_language == "fre"
