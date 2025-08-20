# tests/unit/application/processing/test_matching_engine.py

"""Comprehensive tests for the matching engine and related functionality"""

# Standard library imports
from os import makedirs
from os import unlink
from os.path import exists
from os.path import join
from pickle import UnpicklingError
from pickle import dump as pickle_dump
from pickle import load as pickle_load
from tempfile import NamedTemporaryFile
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock
from unittest.mock import Mock
from unittest.mock import patch

# Third party imports
from pytest import fixture
from pytest import raises

# Local imports
from marc_pd_tool.application.models.batch_stats import BatchStats
from marc_pd_tool.application.processing.matching._match_builder import (
    MatchResultBuilder,
)
from marc_pd_tool.application.processing.matching._score_combiner import ScoreCombiner
from marc_pd_tool.application.processing.matching_engine import DataMatcher
from marc_pd_tool.application.processing.matching_engine import init_worker
from marc_pd_tool.application.processing.matching_engine import process_batch
from marc_pd_tool.application.processing.similarity_calculator import (
    SimilarityCalculator,
)
from marc_pd_tool.application.processing.text_processing import GenericTitleDetector
from marc_pd_tool.application.processing.text_processing import LanguageProcessor
from marc_pd_tool.application.processing.text_processing import MultiLanguageStemmer
from marc_pd_tool.application.processing.text_processing import expand_abbreviations
from marc_pd_tool.core.domain.enums import CountryClassification
from marc_pd_tool.core.domain.enums import MatchType
from marc_pd_tool.core.domain.publication import Publication
from marc_pd_tool.infrastructure.config import ConfigLoader
from marc_pd_tool.infrastructure.config import get_config

# =============================================================================
# Process Batch Tests (for coverage of lines 267-427)
# =============================================================================


class TestProcessBatchFunction:
    """Test the process_batch function with full matching logic"""

    def test_process_batch_with_registration_matches(self):
        """Test process_batch with registration matches found"""
        # Create a test batch with publications
        test_pub = Publication(
            title="Test Book",
            author="Test Author",
            publisher="Test Publisher",
            year=1950,
            source_id="test001",
        )

        # Create a pickled batch file
        with NamedTemporaryFile(mode="wb", delete=False, suffix=".pkl") as f:
            pickle_dump([test_pub], f)
            batch_path = f.name

        # Create mock indexes
        mock_registration_index = Mock()
        mock_registration_index.find_candidates.return_value = [0]
        mock_registration_index.publications = [
            {
                "title": "Test Book",
                "author": "Test Author",
                "publisher": "Test Publisher",
                "year": 1950,
                "source_id": "reg001",
                "pub_date": "1950-01-01",
                "normalized_title": "test book",
                "normalized_author": "test author",
                "normalized_publisher": "test publisher",
            }
        ]

        # Create batch info tuple
        with TemporaryDirectory() as temp_dir:
            batch_info = (
                1,  # batch_id
                batch_path,  # batch_path
                temp_dir,  # worker_cache_dir
                "/copyright",  # copyright_dir
                "/renewal",  # renewal_dir
                "hash123",  # config_hash
                {"min_title_length": 3},  # detector_config
                10,  # total_batches
                40,  # title_threshold
                30,  # author_threshold
                30,  # publisher_threshold
                1,  # year_tolerance
                95,  # early_exit_title
                90,  # early_exit_author
                90,  # early_exit_publisher
                False,  # score_everything
                20,  # minimum_combined_score
                False,  # brute_force_missing_year
                1923,  # min_year
                1977,  # max_year
                temp_dir,  # result_temp_dir
            )

            # Mock the global variables
            # Local imports
            import marc_pd_tool.application.processing.matching_engine as me

            me._worker_registration_index = mock_registration_index
            me._worker_renewal_index = None
            me._worker_generic_detector = None
            me._worker_config = get_config()

            # Call process_batch
            with patch.object(DataMatcher, "find_best_match") as mock_find:
                mock_find.return_value = {
                    "copyright_record": mock_registration_index.publications[0],
                    "similarity_scores": {
                        "title": 100.0,
                        "author": 100.0,
                        "publisher": 100.0,
                        "combined": 100.0,
                    },
                    "is_lccn_match": False,
                }

                batch_id, result_path, stats = process_batch(batch_info)

                assert batch_id == 1
                assert isinstance(stats, BatchStats)
                assert stats.registration_matches_found == 1
                assert stats.marc_count == 1

                # Load the result to verify
                with open(result_path, "rb") as f:
                    processed_pubs = pickle_load(f)
                    assert len(processed_pubs) == 1
                    assert processed_pubs[0].registration_match is not None

        # Cleanup
        if exists(batch_path):
            unlink(batch_path)

    def test_process_batch_with_renewal_matches(self):
        """Test process_batch with renewal matches found"""
        # Create a test batch with publications
        test_pub = Publication(
            title="Test Book",
            author="Test Author",
            publisher="Test Publisher",
            year=1950,
            source_id="test001",
        )

        # Create a pickled batch file
        with NamedTemporaryFile(mode="wb", delete=False, suffix=".pkl") as f:
            pickle_dump([test_pub], f)
            batch_path = f.name

        # Create mock indexes
        mock_renewal_index = Mock()
        mock_renewal_index.find_candidates.return_value = [0]
        mock_renewal_index.publications = [
            {
                "title": "Test Book",
                "author": "Test Author",
                "publisher": "Test Publisher",
                "year": 1950,
                "source_id": "ren001",
                "pub_date": "1978-01-01",
                "normalized_title": "test book",
                "normalized_author": "test author",
                "normalized_publisher": "test publisher",
            }
        ]

        # Create batch info tuple
        with TemporaryDirectory() as temp_dir:
            batch_info = (
                1,  # batch_id
                batch_path,  # batch_path
                temp_dir,  # worker_cache_dir
                "/copyright",  # copyright_dir
                "/renewal",  # renewal_dir
                "hash123",  # config_hash
                {"min_title_length": 3},  # detector_config
                10,  # total_batches
                40,  # title_threshold
                30,  # author_threshold
                30,  # publisher_threshold
                1,  # year_tolerance
                95,  # early_exit_title
                90,  # early_exit_author
                90,  # early_exit_publisher
                False,  # score_everything
                20,  # minimum_combined_score
                False,  # brute_force_missing_year
                1923,  # min_year
                1977,  # max_year
                temp_dir,  # result_temp_dir
            )

            # Mock the global variables
            # Local imports
            import marc_pd_tool.application.processing.matching_engine as me

            me._worker_registration_index = None
            me._worker_renewal_index = mock_renewal_index
            me._worker_generic_detector = None
            me._worker_config = get_config()

            # Call process_batch
            with patch.object(DataMatcher, "find_best_match") as mock_find:
                mock_find.return_value = {
                    "copyright_record": mock_renewal_index.publications[0],
                    "similarity_scores": {
                        "title": 100.0,
                        "author": 100.0,
                        "publisher": 100.0,
                        "combined": 100.0,
                    },
                    "is_lccn_match": False,
                }

                batch_id, result_path, stats = process_batch(batch_info)

                assert batch_id == 1
                assert isinstance(stats, BatchStats)
                assert stats.renewal_matches_found == 1
                assert stats.marc_count == 1

                # Load the result to verify
                with open(result_path, "rb") as f:
                    processed_pubs = pickle_load(f)
                    assert len(processed_pubs) == 1
                    assert processed_pubs[0].renewal_match is not None

        # Cleanup
        if exists(batch_path):
            unlink(batch_path)

    def test_process_batch_with_generic_title_detection(self):
        """Test process_batch with generic title detection"""
        # Create a test batch with publications
        test_pub = Publication(
            title="Report", author="Test Author", year=1950, source_id="test001"  # Generic title
        )

        # Create a pickled batch file
        with NamedTemporaryFile(mode="wb", delete=False, suffix=".pkl") as f:
            pickle_dump([test_pub], f)
            batch_path = f.name

        # Create mock indexes
        mock_registration_index = Mock()
        mock_registration_index.find_candidates.return_value = [0]
        mock_registration_index.publications = [
            {
                "title": "Annual Report",
                "author": "Test Author",
                "year": 1950,
                "source_id": "reg001",
                "pub_date": "1950-01-01",
                "normalized_title": "annual report",
                "normalized_author": "test author",
            }
        ]

        # Create batch info tuple
        with TemporaryDirectory() as temp_dir:
            batch_info = (
                1,  # batch_id
                batch_path,  # batch_path
                temp_dir,  # worker_cache_dir
                "/copyright",  # copyright_dir
                "/renewal",  # renewal_dir
                "hash123",  # config_hash
                {"min_title_length": 3},  # detector_config
                10,  # total_batches
                40,  # title_threshold
                30,  # author_threshold
                30,  # publisher_threshold
                1,  # year_tolerance
                95,  # early_exit_title
                90,  # early_exit_author
                90,  # early_exit_publisher
                False,  # score_everything
                20,  # minimum_combined_score
                False,  # brute_force_missing_year
                1923,  # min_year
                1977,  # max_year
                temp_dir,  # result_temp_dir
            )

            # Mock the global variables
            # Local imports
            import marc_pd_tool.application.processing.matching_engine as me

            me._worker_registration_index = mock_registration_index
            me._worker_renewal_index = None
            me._worker_generic_detector = GenericTitleDetector(get_config())
            me._worker_config = get_config()

            # Call process_batch
            with patch.object(DataMatcher, "find_best_match") as mock_find:
                mock_find.return_value = {
                    "copyright_record": mock_registration_index.publications[0],
                    "similarity_scores": {"title": 80.0, "author": 100.0, "combined": 90.0},
                    "is_lccn_match": False,
                    "generic_title_info": {
                        "has_generic_title": True,
                        "marc_title_is_generic": True,
                        "marc_detection_reason": "exact_match",
                        "copyright_detection_reason": "pattern_match",
                    },
                }

                batch_id, result_path, stats = process_batch(batch_info)

                # Load the result to verify
                with open(result_path, "rb") as f:
                    processed_pubs = pickle_load(f)
                    assert len(processed_pubs) == 1
                    assert processed_pubs[0].generic_title_detected is True
                    assert processed_pubs[0].registration_generic_title is True
                    assert processed_pubs[0].generic_detection_reason == "exact_match"

        # Cleanup
        if exists(batch_path):
            unlink(batch_path)

    def test_process_batch_with_lccn_match(self):
        """Test process_batch with LCCN match type"""
        # Create a test batch with publications
        test_pub = Publication(
            title="Test Book", author="Test Author", year=1950, source_id="test001", lccn="50012345"
        )

        # Create a pickled batch file
        with NamedTemporaryFile(mode="wb", delete=False, suffix=".pkl") as f:
            pickle_dump([test_pub], f)
            batch_path = f.name

        # Create mock indexes
        mock_registration_index = Mock()
        mock_registration_index.find_candidates.return_value = [0]
        mock_registration_index.publications = [
            {
                "title": "Test Book",
                "author": "Test Author",
                "year": 1950,
                "source_id": "reg001",
                "lccn": "50012345",
                "pub_date": "1950-01-01",
                "normalized_title": "test book",
                "normalized_author": "test author",
            }
        ]

        # Create batch info tuple
        with TemporaryDirectory() as temp_dir:
            batch_info = (
                1,  # batch_id
                batch_path,  # batch_path
                temp_dir,  # worker_cache_dir
                "/copyright",  # copyright_dir
                "/renewal",  # renewal_dir
                "hash123",  # config_hash
                {"min_title_length": 3},  # detector_config
                10,  # total_batches
                40,  # title_threshold
                30,  # author_threshold
                30,  # publisher_threshold
                1,  # year_tolerance
                95,  # early_exit_title
                90,  # early_exit_author
                90,  # early_exit_publisher
                False,  # score_everything
                20,  # minimum_combined_score
                False,  # brute_force_missing_year
                1923,  # min_year
                1977,  # max_year
                temp_dir,  # result_temp_dir
            )

            # Mock the global variables
            # Local imports
            import marc_pd_tool.application.processing.matching_engine as me

            me._worker_registration_index = mock_registration_index
            me._worker_renewal_index = None
            me._worker_generic_detector = None
            me._worker_config = get_config()

            # Call process_batch
            with patch.object(DataMatcher, "find_best_match") as mock_find:
                mock_find.return_value = {
                    "copyright_record": mock_registration_index.publications[0],
                    "similarity_scores": {"title": 100.0, "author": 100.0, "combined": 100.0},
                    "is_lccn_match": True,  # LCCN match
                }

                batch_id, result_path, stats = process_batch(batch_info)

                # Load the result to verify
                with open(result_path, "rb") as f:
                    processed_pubs = pickle_load(f)
                    assert len(processed_pubs) == 1
                    assert processed_pubs[0].registration_match is not None
                    assert processed_pubs[0].registration_match.match_type == MatchType.LCCN

        # Cleanup
        if exists(batch_path):
            unlink(batch_path)

    def test_process_batch_with_brute_force_match(self):
        """Test process_batch with brute force match for missing year"""
        # Create a test batch with publications WITHOUT year
        test_pub = Publication(
            title="Test Book", author="Test Author", year=None, source_id="test001"  # No year
        )

        # Create a pickled batch file
        with NamedTemporaryFile(mode="wb", delete=False, suffix=".pkl") as f:
            pickle_dump([test_pub], f)
            batch_path = f.name

        # Create mock indexes
        mock_registration_index = Mock()
        mock_registration_index.find_candidates.return_value = [0]
        mock_registration_index.publications = [
            {
                "title": "Test Book",
                "author": "Test Author",
                "year": 1950,
                "source_id": "reg001",
                "pub_date": "1950-01-01",
                "normalized_title": "test book",
                "normalized_author": "test author",
            }
        ]

        # Create batch info tuple with brute_force_missing_year=True
        with TemporaryDirectory() as temp_dir:
            batch_info = (
                1,  # batch_id
                batch_path,  # batch_path
                temp_dir,  # worker_cache_dir
                "/copyright",  # copyright_dir
                "/renewal",  # renewal_dir
                "hash123",  # config_hash
                {"min_title_length": 3},  # detector_config
                10,  # total_batches
                40,  # title_threshold
                30,  # author_threshold
                30,  # publisher_threshold
                1,  # year_tolerance
                95,  # early_exit_title
                90,  # early_exit_author
                90,  # early_exit_publisher
                False,  # score_everything
                20,  # minimum_combined_score
                True,  # brute_force_missing_year = TRUE
                1923,  # min_year
                1977,  # max_year
                temp_dir,  # result_temp_dir
            )

            # Mock the global variables
            # Local imports
            import marc_pd_tool.application.processing.matching_engine as me

            me._worker_registration_index = mock_registration_index
            me._worker_renewal_index = None
            me._worker_generic_detector = None
            me._worker_config = get_config()

            # Call process_batch
            with patch.object(DataMatcher, "find_best_match") as mock_find:
                mock_find.return_value = {
                    "copyright_record": mock_registration_index.publications[0],
                    "similarity_scores": {"title": 100.0, "author": 100.0, "combined": 100.0},
                    "is_lccn_match": False,
                }

                batch_id, result_path, stats = process_batch(batch_info)

                # Load the result to verify
                with open(result_path, "rb") as f:
                    processed_pubs = pickle_load(f)
                    assert len(processed_pubs) == 1
                    assert processed_pubs[0].registration_match is not None
                    assert (
                        processed_pubs[0].registration_match.match_type
                        == MatchType.BRUTE_FORCE_WITHOUT_YEAR
                    )

        # Cleanup
        if exists(batch_path):
            unlink(batch_path)

    def test_process_batch_file_cleanup_error(self):
        """Test process_batch handles file cleanup errors gracefully"""
        # Create a test batch
        test_pub = Publication(title="Test", source_id="test001")

        # Create a pickled batch file
        with NamedTemporaryFile(mode="wb", delete=False, suffix=".pkl") as f:
            pickle_dump([test_pub], f)
            batch_path = f.name

        # Create batch info tuple
        with TemporaryDirectory() as temp_dir:
            batch_info = (
                1,  # batch_id
                batch_path,  # batch_path
                temp_dir,  # worker_cache_dir
                "/copyright",  # copyright_dir
                "/renewal",  # renewal_dir
                "hash123",  # config_hash
                {"min_title_length": 3},  # detector_config
                10,  # total_batches
                40,  # title_threshold
                30,  # author_threshold
                30,  # publisher_threshold
                1,  # year_tolerance
                95,  # early_exit_title
                90,  # early_exit_author
                90,  # early_exit_publisher
                False,  # score_everything
                20,  # minimum_combined_score
                False,  # brute_force_missing_year
                1923,  # min_year
                1977,  # max_year
                temp_dir,  # result_temp_dir
            )

            # Mock the global variables
            # Local imports
            import marc_pd_tool.application.processing.matching_engine as me

            me._worker_registration_index = None
            me._worker_renewal_index = None
            me._worker_generic_detector = None
            me._worker_config = get_config()

            # Mock unlink to raise an exception
            with patch("marc_pd_tool.application.processing.matching_engine.unlink") as mock_unlink:
                mock_unlink.side_effect = OSError("Permission denied")

                # Should not raise, just ignore the error
                batch_id, result_path, stats = process_batch(batch_info)

                assert batch_id == 1
                assert isinstance(stats, BatchStats)
                mock_unlink.assert_called_once_with(batch_path)

        # Cleanup
        if exists(batch_path):
            unlink(batch_path)

    def test_process_batch_with_score_everything_mode(self):
        """Test process_batch in score_everything mode"""
        # Create a test batch
        test_pub = Publication(
            title="Test Book", author="Test Author", year=1950, source_id="test001"
        )

        # Create a pickled batch file
        with NamedTemporaryFile(mode="wb", delete=False, suffix=".pkl") as f:
            pickle_dump([test_pub], f)
            batch_path = f.name

        # Create mock indexes
        mock_registration_index = Mock()
        mock_registration_index.find_candidates.return_value = [0]
        mock_registration_index.publications = [
            {
                "title": "Different Title",
                "author": "Test Author",
                "year": 1950,
                "source_id": "reg001",
                "pub_date": "1950-01-01",
                "normalized_title": "different title",
                "normalized_author": "test author",
            }
        ]

        # Create batch info tuple with score_everything=True
        with TemporaryDirectory() as temp_dir:
            batch_info = (
                1,  # batch_id
                batch_path,  # batch_path
                temp_dir,  # worker_cache_dir
                "/copyright",  # copyright_dir
                "/renewal",  # renewal_dir
                "hash123",  # config_hash
                {"min_title_length": 3},  # detector_config
                10,  # total_batches
                40,  # title_threshold
                30,  # author_threshold
                30,  # publisher_threshold
                1,  # year_tolerance
                95,  # early_exit_title
                90,  # early_exit_author
                90,  # early_exit_publisher
                True,  # score_everything = TRUE
                20,  # minimum_combined_score
                False,  # brute_force_missing_year
                1923,  # min_year
                1977,  # max_year
                temp_dir,  # result_temp_dir
            )

            # Mock the global variables
            # Local imports
            import marc_pd_tool.application.processing.matching_engine as me

            me._worker_registration_index = mock_registration_index
            me._worker_renewal_index = None
            me._worker_generic_detector = None
            me._worker_config = get_config()

            # Call process_batch
            with patch.object(DataMatcher, "find_best_match_ignore_thresholds") as mock_find:
                mock_find.return_value = {
                    "copyright_record": mock_registration_index.publications[0],
                    "similarity_scores": {"title": 50.0, "author": 100.0, "combined": 75.0},
                    "is_lccn_match": False,
                }

                batch_id, result_path, stats = process_batch(batch_info)

                # Verify find_best_match_ignore_thresholds was called (not find_best_match)
                mock_find.assert_called_once()
                assert batch_id == 1
                assert stats.registration_matches_found == 1

        # Cleanup
        if exists(batch_path):
            unlink(batch_path)


# =============================================================================
# Language Processing Tests
# =============================================================================


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


# =============================================================================
# Multilingual Stemming Tests
# =============================================================================


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


# =============================================================================
# Abbreviation Expansion Tests
# =============================================================================


class TestPublishingAbbreviations:
    """Test publishing abbreviation expansion"""

    def test_abbreviations_dictionary(self):
        """Test abbreviations expansion functionality"""
        # Test original abbreviations get expanded
        assert expand_abbreviations("Vol.") == "volume."
        assert expand_abbreviations("Co.") == "company."
        assert expand_abbreviations("Ed.") == "edition."

        # Test new AACR2 abbreviations get expanded
        assert expand_abbreviations("Ms.") == "manuscript."
        assert expand_abbreviations("Suppl.") == "supplement."
        assert expand_abbreviations("Ca.") == "circa."

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


# =============================================================================
# Similarity Calculator Tests
# =============================================================================


class TestSimilarityCalculator:
    """Test enhanced word-based similarity calculation"""

    @fixture
    def mock_config(self):
        """Create a mock configuration"""
        config = MagicMock(spec=ConfigLoader)
        config.config = {
            "matching": {
                "word_based": {
                    "default_language": "eng",
                    "enable_stemming": True,
                    "enable_abbreviation_expansion": True,
                }
            }
        }
        # Add method mocks for stopwords
        config.author_stopwords = {"by", "edited", "compiled", "translated", "author", "editor"}
        config.publisher_stopwords = {
            "publishing",
            "publishers",
            "company",
            "corp",
            "corporation",
            "inc",
            "incorporated",
        }
        return config

    @fixture
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
        # With fuzzy matching, partial matches score lower than with Jaccard
        # The short title is only a small part of the longer one
        assert score > 30.0  # Fuzzy matching gives ~37%

        # Another case: "enoch arden im riesengebirge" vs full title with author
        score = calculator.calculate_title_similarity(
            "enoch arden im riesengebirge",
            "enoch arden im riesengebirge roman von gertrud weymar hey",
        )
        assert score > 60.0

    def test_calculate_title_similarity_partial_match_minimum_words(self, calculator):
        """Test fuzzy matching behavior with single words"""
        # Single word match in longer title
        score = calculator.calculate_title_similarity(
            "shakespeare", "shakespeare complete works volume one"
        )
        # With fuzzy matching, this scores higher due to the shared word
        assert score > 40.0  # Fuzzy matching gives ~47%

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

    @patch("marc_pd_tool.application.processing.similarity_calculator.fuzz")
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

    @patch("marc_pd_tool.application.processing.similarity_calculator.fuzz")
    def test_calculate_publisher_similarity_direct(self, mock_fuzz, calculator):
        """Test publisher similarity for direct comparison"""
        mock_fuzz.ratio.return_value = 90.0

        score = calculator.calculate_publisher_similarity("Random House", "Random House Inc", "")

        assert score == 90.0
        mock_fuzz.ratio.assert_called_once()

    @patch("marc_pd_tool.application.processing.similarity_calculator.fuzz")
    def test_calculate_publisher_similarity_full_text(self, mock_fuzz, calculator):
        """Test publisher similarity against full text"""
        mock_fuzz.partial_ratio.return_value = 75.0

        score = calculator.calculate_publisher_similarity(
            "Random House", "", "Published by Random House in New York"
        )

        assert score == 75.0
        mock_fuzz.partial_ratio.assert_called_once()

    def test_preprocess_author_removes_qualifiers(self, calculator):
        """Test author preprocessing removes common stopwords"""
        # Custom stopwords based on ground truth are more minimal
        # "by" is removed as a stopword, but "edited" is kept
        result = calculator._preprocess_author("edited by John Smith")
        assert "by" not in result.lower()
        assert "john" in result.lower()
        assert "smith" in result.lower()

    def test_preprocess_publisher_removes_stopwords(self, calculator):
        """Test publisher preprocessing keeps meaningful publisher terms"""
        # Based on ground truth analysis, "publishing" and "company" are preserved
        result = calculator._preprocess_publisher("Random House Publishing Company")
        assert "random" in result.lower()
        assert "house" in result.lower()
        # These are preserved words for publishers
        assert "publishing" in result.lower()
        assert "company" in result.lower()


# =============================================================================
# Enhanced Matching Tests
# =============================================================================


class TestMatchingIntegration:
    """Integration tests for enhanced matching system"""

    def test_enhanced_matching_with_stemming_disabled(self):
        """Test enhanced matching with stemming disabled"""
        config = MagicMock(spec=ConfigLoader)
        config.config = {
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
        config.config = {
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
        config.config = {
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


# =============================================================================
# DataMatcher Core Functionality Tests
# =============================================================================


class TestDataMatcherAdditional:
    """Additional tests for DataMatcher to increase coverage"""

    def test_find_best_match_ignore_thresholds_with_generic_detector(self):
        """Test find_best_match_ignore_thresholds with generic_detector set (line 108)"""
        config = get_config()
        matcher = DataMatcher(config=config)

        # Create test data
        marc_pub = Publication(title="Report", author="Test Author", year=1950, source_id="marc001")

        copyright_pubs = [
            Publication(title="Annual Report", author="Test Author", year=1950, source_id="reg001")
        ]

        # Create a generic detector
        generic_detector = GenericTitleDetector(config)

        # Call with generic_detector set
        result = matcher.find_best_match_ignore_thresholds(
            marc_pub=marc_pub,
            copyright_pubs=copyright_pubs,
            year_tolerance=1,
            minimum_combined_score=20,
            generic_detector=generic_detector,  # This sets line 108
        )

        # The matcher should have the generic detector set
        assert matcher.core_matcher.generic_detector is not None


class TestWorkerInitialization:
    """Test worker initialization functions"""

    def test_init_worker_failure(self):
        """Test init_worker RuntimeError when indexes fail to load (line 157)"""
        with patch("marc_pd_tool.infrastructure.CacheManager") as MockCacheManager:
            # Mock the cache manager to return None (failed to load)
            mock_instance = MockCacheManager.return_value
            mock_instance.get_cached_indexes.return_value = None

            # This should raise RuntimeError
            with raises(RuntimeError, match="Failed to load indexes from cache"):
                init_worker(
                    cache_dir="/cache",
                    copyright_dir="/copyright",
                    renewal_dir="/renewal",
                    config_hash="hash123",
                    detector_config={"min_title_length": 3},
                    min_year=1923,
                    max_year=1977,
                    brute_force=False,
                )


class TestDataMatcher:
    """Test enhanced word-based matching engine"""

    @fixture
    def mock_config(self):
        """Create a mock configuration"""
        config = MagicMock(spec=ConfigLoader)
        config.config = {
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

    @fixture
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

    @fixture
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

    def test_process_batch_with_renewal_score_everything_mode(self):
        """Test process_batch with renewal matches in score_everything mode (line 354)"""
        # Create a test batch with publications
        test_pub = Publication(
            title="Test Book",
            author="Test Author",
            publisher="Test Publisher",
            year=1950,
            source_id="test001",
        )

        # Create a pickled batch file
        with NamedTemporaryFile(mode="wb", delete=False, suffix=".pkl") as f:
            pickle_dump([test_pub], f)
            batch_path = f.name

        # Create mock indexes
        mock_registration_index = Mock()
        mock_registration_index.find_candidates.return_value = []  # No registration matches

        mock_renewal_index = Mock()
        mock_renewal_index.find_candidates.return_value = [0]
        mock_renewal_index.publications = [
            {
                "title": "Test Book",
                "author": "Test Author",
                "publisher": "Test Publisher",
                "year": 1950,
                "source_id": "ren001",
                "pub_date": "1950-01-01",
                "normalized_title": "test book",
                "normalized_author": "test author",
                "normalized_publisher": "test publisher",
            }
        ]

        # Create batch info tuple with score_everything=True
        with TemporaryDirectory() as temp_dir:
            batch_info = (
                1,  # batch_id
                batch_path,  # batch_path
                temp_dir,  # worker_cache_dir
                "/copyright",  # copyright_dir
                "/renewal",  # renewal_dir
                "hash123",  # config_hash
                {"min_title_length": 3},  # detector_config
                10,  # total_batches
                40,  # title_threshold
                30,  # author_threshold
                30,  # publisher_threshold
                1,  # year_tolerance
                95,  # early_exit_title
                90,  # early_exit_author
                None,  # early_exit_publisher
                True,  # score_everything - THIS IS THE KEY CHANGE
                70,  # minimum_combined_score
                False,  # brute_force_missing_year
                None,  # min_year
                None,  # max_year
                temp_dir,  # result_temp_dir
            )

            # Patch globals and mock dependencies
            with patch(
                "marc_pd_tool.application.processing.matching_engine._worker_registration_index",
                mock_registration_index,
            ):
                with patch(
                    "marc_pd_tool.application.processing.matching_engine._worker_renewal_index",
                    mock_renewal_index,
                ):
                    with patch(
                        "marc_pd_tool.application.processing.matching_engine._worker_generic_detector",
                        None,
                    ):
                        with patch(
                            "marc_pd_tool.application.processing.matching_engine._worker_config",
                            get_config(),
                        ):
                            with patch.object(
                                DataMatcher, "find_best_match_ignore_thresholds"
                            ) as mock_find:
                                # Configure the mock to return a match
                                mock_find.return_value = {
                                    "copyright_record": mock_renewal_index.publications[0],
                                    "similarity_scores": {
                                        "title": 100.0,
                                        "author": 100.0,
                                        "publisher": 100.0,
                                        "combined": 100.0,
                                    },
                                    "is_lccn_match": False,
                                }

                                batch_num, result_file, stats = process_batch(batch_info)

                                # Verify find_best_match_ignore_thresholds was called for renewal
                                assert mock_find.called
                                # Check that the match was recorded as renewal
                                assert stats.renewal_matches_found == 1

        # Clean up
        if exists(batch_path):
            unlink(batch_path)

    def test_process_batch_with_renewal_generic_title_marc_not_generic(self):
        """Test renewal match generic title when MARC is not generic (lines 426-427)"""
        # Create a test batch with publications
        test_pub = Publication(
            title="Test Book",
            author="Test Author",
            publisher="Test Publisher",
            year=1950,
            source_id="test001",
        )
        test_pub.generic_detection_reason = "none"  # MARC is not generic initially

        # Create a pickled batch file
        with NamedTemporaryFile(mode="wb", delete=False, suffix=".pkl") as f:
            pickle_dump([test_pub], f)
            batch_path = f.name

        # Create mock indexes
        mock_registration_index = Mock()
        mock_registration_index.find_candidates.return_value = []  # No registration matches

        mock_renewal_index = Mock()
        mock_renewal_index.find_candidates.return_value = [0]
        mock_renewal_index.publications = [
            {
                "title": "Annual Report",  # Generic title
                "author": "Test Author",
                "publisher": "Test Publisher",
                "year": 1950,
                "source_id": "ren001",
                "pub_date": "1950-01-01",
                "normalized_title": "annual report",
                "normalized_author": "test author",
                "normalized_publisher": "test publisher",
            }
        ]

        # Create batch info tuple
        with TemporaryDirectory() as temp_dir:
            batch_info = (
                1,  # batch_id
                batch_path,  # batch_path
                temp_dir,  # worker_cache_dir
                "/copyright",  # copyright_dir
                "/renewal",  # renewal_dir
                "hash123",  # config_hash
                {"min_title_length": 3},  # detector_config
                10,  # total_batches
                40,  # title_threshold
                30,  # author_threshold
                30,  # publisher_threshold
                1,  # year_tolerance
                95,  # early_exit_title
                90,  # early_exit_author
                None,  # early_exit_publisher
                False,  # score_everything
                None,  # minimum_combined_score
                False,  # brute_force_missing_year
                None,  # min_year
                None,  # max_year
                temp_dir,  # result_temp_dir
            )

            # Patch globals and mock dependencies
            with patch(
                "marc_pd_tool.application.processing.matching_engine._worker_registration_index",
                mock_registration_index,
            ):
                with patch(
                    "marc_pd_tool.application.processing.matching_engine._worker_renewal_index",
                    mock_renewal_index,
                ):
                    with patch(
                        "marc_pd_tool.application.processing.matching_engine._worker_generic_detector",
                        None,
                    ):
                        with patch(
                            "marc_pd_tool.application.processing.matching_engine._worker_config",
                            get_config(),
                        ):
                            with patch.object(DataMatcher, "find_best_match") as mock_find:
                                # Configure the mock to return a match with generic title info
                                mock_find.return_value = {
                                    "copyright_record": mock_renewal_index.publications[0],
                                    "similarity_scores": {
                                        "title": 100.0,
                                        "author": 100.0,
                                        "publisher": 100.0,
                                        "combined": 100.0,
                                    },
                                    "is_lccn_match": False,
                                    "generic_title_info": {
                                        "has_generic_title": True,
                                        "marc_title_is_generic": False,  # MARC is not generic
                                        "copyright_detection_reason": (
                                            "pattern:annual_report"  # Copyright is generic
                                        ),
                                    },
                                }

                                batch_num, result_file, stats = process_batch(batch_info)

                                # Verify the match was processed
                                assert stats.renewal_matches_found == 1

                                # Load the result to check the publication's generic detection
                                with open(result_file, "rb") as f:
                                    processed_pubs = pickle_load(f)

                                assert len(processed_pubs) == 1
                                pub = processed_pubs[0]
                                assert pub.generic_title_detected is True
                                assert pub.renewal_generic_title is True
                                # This tests line 427 - copyright_detection_reason is used
                                assert pub.generic_detection_reason == "pattern:annual_report"

        # Clean up
        if exists(batch_path):
            unlink(batch_path)

    def test_process_batch_slow_processing_warning(self):
        """Test slow processing warning log"""
        # Create a test batch with a small number of publications
        # To trigger warning: elapsed > 60 OR (elapsed > 10 AND records_per_sec < 2)
        # We'll test the first condition: processing taking > 60 seconds
        test_pubs = [
            Publication(
                title=f"Test Book {i}",
                author="Test Author",
                publisher="Test Publisher",
                year=1950,
                source_id=f"test{i:03d}",
            )
            for i in range(100)  # 100 records processed in 61 seconds = 1.6 rec/s
        ]

        # Create a pickled batch file
        with NamedTemporaryFile(mode="wb", delete=False, suffix=".pkl") as f:
            pickle_dump(test_pubs, f)
            batch_path = f.name

        # Create mock indexes
        mock_registration_index = Mock()
        mock_registration_index.find_candidates.return_value = []  # No matches

        mock_renewal_index = Mock()
        mock_renewal_index.find_candidates.return_value = []  # No matches

        # Create batch info tuple
        with TemporaryDirectory() as temp_dir:
            batch_info = (
                1,  # batch_id
                batch_path,  # batch_path
                temp_dir,  # worker_cache_dir
                "/copyright",  # copyright_dir
                "/renewal",  # renewal_dir
                "hash123",  # config_hash
                {"min_title_length": 3},  # detector_config
                10,  # total_batches
                40,  # title_threshold
                30,  # author_threshold
                30,  # publisher_threshold
                1,  # year_tolerance
                95,  # early_exit_title
                90,  # early_exit_author
                None,  # early_exit_publisher
                False,  # score_everything
                None,  # minimum_combined_score
                False,  # brute_force_missing_year
                None,  # min_year
                None,  # max_year
                temp_dir,  # result_temp_dir
            )

            # Patch globals and mock dependencies
            with patch(
                "marc_pd_tool.application.processing.matching_engine._worker_registration_index",
                mock_registration_index,
            ):
                with patch(
                    "marc_pd_tool.application.processing.matching_engine._worker_renewal_index",
                    mock_renewal_index,
                ):
                    with patch(
                        "marc_pd_tool.application.processing.matching_engine._worker_generic_detector",
                        None,
                    ):
                        with patch(
                            "marc_pd_tool.application.processing.matching_engine._worker_config",
                            get_config(),
                        ):
                            # Mock time to simulate slow processing (elapsed > 60)
                            with patch(
                                "marc_pd_tool.application.processing.matching_engine.time"
                            ) as mock_time:
                                # time() is called twice: start_time and after processing
                                # We want elapsed = 61 seconds, with 100 records = 1.6 rec/s
                                mock_time.side_effect = [0, 61]  # start_time=0, end_time=61

                                with patch(
                                    "marc_pd_tool.application.processing.matching_engine.logger"
                                ) as mock_logger:
                                    batch_num, result_file, stats = process_batch(batch_info)

                                    # Check the stats to verify processing
                                    assert stats.marc_count == 100  # All records processed
                                    assert stats.processing_time == 61  # 61 seconds elapsed

                                    # Verify the warning was logged
                                    # elapsed=61 > 60, so warning should trigger
                                    mock_logger.warning.assert_called_once()
                                    warning_call = mock_logger.warning.call_args[0][0]
                                    assert "Slow processing detected" in warning_call
                                    assert "1.6 rec/s" in warning_call or "1.6" in warning_call
                                    assert "61.0s" in warning_call or "61s" in warning_call

        # Clean up
        if exists(batch_path):
            unlink(batch_path)

    def test_process_batch_with_registration_generic_title_copyright_reason(self):
        """Test registration match where copyright reason is used for generic title (line 343)"""
        # Create a test batch with publications
        test_pub = Publication(
            title="Test Book",
            author="Test Author",
            publisher="Test Publisher",
            year=1950,
            source_id="test001",
        )
        test_pub.generic_detection_reason = "none"  # MARC is not generic initially

        # Create a pickled batch file
        with NamedTemporaryFile(mode="wb", delete=False, suffix=".pkl") as f:
            pickle_dump([test_pub], f)
            batch_path = f.name

        # Create mock indexes
        mock_registration_index = Mock()
        mock_registration_index.find_candidates.return_value = [0]
        mock_registration_index.publications = [
            {
                "title": "Annual Report",  # Generic title
                "author": "Test Author",
                "publisher": "Test Publisher",
                "year": 1950,
                "source_id": "reg001",
                "pub_date": "1950-01-01",
                "normalized_title": "annual report",
                "normalized_author": "test author",
                "normalized_publisher": "test publisher",
            }
        ]

        mock_renewal_index = Mock()
        mock_renewal_index.find_candidates.return_value = []  # No renewal matches

        # Create batch info tuple
        with TemporaryDirectory() as temp_dir:
            batch_info = (
                1,  # batch_id
                batch_path,  # batch_path
                temp_dir,  # worker_cache_dir
                "/copyright",  # copyright_dir
                "/renewal",  # renewal_dir
                "hash123",  # config_hash
                {"min_title_length": 3},  # detector_config
                10,  # total_batches
                40,  # title_threshold
                30,  # author_threshold
                30,  # publisher_threshold
                1,  # year_tolerance
                95,  # early_exit_title
                90,  # early_exit_author
                None,  # early_exit_publisher
                False,  # score_everything
                None,  # minimum_combined_score
                False,  # brute_force_missing_year
                None,  # min_year
                None,  # max_year
                temp_dir,  # result_temp_dir
            )

            # Patch globals and mock dependencies
            with patch(
                "marc_pd_tool.application.processing.matching_engine._worker_registration_index",
                mock_registration_index,
            ):
                with patch(
                    "marc_pd_tool.application.processing.matching_engine._worker_renewal_index",
                    mock_renewal_index,
                ):
                    with patch(
                        "marc_pd_tool.application.processing.matching_engine._worker_generic_detector",
                        None,
                    ):
                        with patch(
                            "marc_pd_tool.application.processing.matching_engine._worker_config",
                            get_config(),
                        ):
                            with patch.object(DataMatcher, "find_best_match") as mock_find:
                                # Configure the mock to return a match with generic title info
                                mock_find.return_value = {
                                    "copyright_record": mock_registration_index.publications[0],
                                    "similarity_scores": {
                                        "title": 100.0,
                                        "author": 100.0,
                                        "publisher": 100.0,
                                        "combined": 100.0,
                                    },
                                    "is_lccn_match": False,
                                    "generic_title_info": {
                                        "has_generic_title": True,
                                        "marc_title_is_generic": False,  # MARC is not generic
                                        "copyright_detection_reason": (
                                            "pattern:annual_report"  # Copyright is generic
                                        ),
                                    },
                                }

                                batch_num, result_file, stats = process_batch(batch_info)

                                # Verify the match was processed
                                assert stats.registration_matches_found == 1

                                # Load the result to check the publication's generic detection
                                with open(result_file, "rb") as f:
                                    processed_pubs = pickle_load(f)

                                assert len(processed_pubs) == 1
                                pub = processed_pubs[0]
                                assert pub.generic_title_detected is True
                                assert pub.registration_generic_title is True
                                # This tests line 343 - copyright_detection_reason is used
                                assert pub.generic_detection_reason == "pattern:annual_report"

        # Clean up
        if exists(batch_path):
            unlink(batch_path)


# =============================================================================
# DataMatcher Edge Cases Tests
# =============================================================================


class TestDataMatcherEdgeCases:
    """Test edge cases in DataMatcher"""

    def test_find_best_match_no_generic_detector(self):
        """Test matching without generic detector"""
        matcher = DataMatcher()

        marc_pub = Publication(
            title="Test Book", author="Test Author", pub_date="1950", source_id="001"
        )

        copyright_pubs = [
            Publication(title="Test Book", author="Test Author", pub_date="1950", source_id="c001")
        ]

        # Test without generic detector (line 127)
        result = matcher.find_best_match(
            marc_pub,
            copyright_pubs,
            year_tolerance=2,
            title_threshold=40,
            author_threshold=30,
            publisher_threshold=20,
            early_exit_title=95,
            early_exit_author=90,
            generic_detector=None,  # No generic detector
        )

        assert result is not None
        assert result["copyright_record"]["source_id"] == "c001"

    def test_find_best_match_lccn_match(self):
        """Test LCCN matching when both have same LCCN"""
        matcher = DataMatcher()

        marc_pub = Publication(
            title="Test Book", author="Test Author", pub_date="1950", source_id="001"
        )
        marc_pub.normalized_lccn = "2001012345"

        copyright_pub = Publication(
            title="Different Title",  # Different metadata
            author="Different Author",
            pub_date="1950",  # Same year to pass year filter
            source_id="c001",
        )
        copyright_pub.normalized_lccn = "2001012345"  # Same LCCN

        result = matcher.find_best_match(
            marc_pub,
            [copyright_pub],
            year_tolerance=2,
            title_threshold=40,
            author_threshold=30,
            publisher_threshold=20,
            early_exit_title=95,
            early_exit_author=90,
        )

        # Should find match based on LCCN even with different metadata
        assert result is not None
        assert result["is_lccn_match"] is True

    def test_combine_scores_generic_title(self):
        """Test score combination with generic title"""
        matcher = DataMatcher()

        # Create publications with generic title
        marc_pub = Publication(
            title="Annual Report",
            author="Company Name",
            publisher="Publisher",
            pub_date="1950",
            source_id="001",
        )

        copyright_pub = Publication(
            title="Annual Report",
            author="Company Name",
            publisher="Publisher",
            pub_date="1950",
            source_id="c001",
        )

        # Create generic detector that marks "Annual Report" as generic
        generic_detector = Mock()
        generic_detector.is_generic.return_value = True
        generic_detector.get_detection_reason.return_value = "pattern: annual report"

        # Test through public API - should find match but with adjusted scoring
        result = matcher.find_best_match(
            marc_pub,
            [copyright_pub],
            title_threshold=40,
            author_threshold=30,
            year_tolerance=1,
            publisher_threshold=20,
            early_exit_title=95,
            early_exit_author=90,
            generic_detector=generic_detector,
        )

        # Should find a match
        assert result is not None
        # Even with generic title penalty, when all scores are 100%,
        # the normalized weights still produce 100% combined score
        assert result["similarity_scores"]["combined"] == 100.0

    def test_find_best_match_no_year_in_copyright(self):
        """Test matching when copyright publication has no year"""
        matcher = DataMatcher()

        marc_pub = Publication(
            title="Test Book", author="Test Author", pub_date="1950", source_id="001"
        )

        # Copyright pub with no year
        copyright_pub = Publication(
            title="Test Book", author="Test Author", pub_date=None, source_id="c001"  # No year
        )
        copyright_pub.year = None

        # Test line 185 - copyright year is None
        result = matcher.find_best_match(
            marc_pub,
            [copyright_pub],
            year_tolerance=2,
            title_threshold=40,
            author_threshold=30,
            publisher_threshold=20,
            early_exit_title=95,
            early_exit_author=90,
        )

        # Should still match based on title/author
        assert result is not None

    def test_find_best_match_zero_year_tolerance(self):
        """Test matching with zero year tolerance"""
        matcher = DataMatcher()

        marc_pub = Publication(
            title="Test Book", author="Test Author", pub_date="1950", source_id="001"
        )

        copyright_pubs = [
            Publication(
                title="Test Book",
                author="Test Author",
                pub_date="1951",  # One year off
                source_id="c001",
            )
        ]

        # Test line 191 - year difference > tolerance (0)
        result = matcher.find_best_match(
            marc_pub,
            copyright_pubs,
            year_tolerance=0,  # Zero tolerance
            title_threshold=40,
            author_threshold=30,
            publisher_threshold=20,
            early_exit_title=95,
            early_exit_author=90,
        )

        # Should not match due to year difference
        assert result is None

    def test_combine_scores_no_publisher_handling(self):
        """Test score combination when publications have no publisher"""
        matcher = DataMatcher()

        # Create publications with no publisher
        marc_pub = Publication(
            title="Test Book",
            author="Test Author",
            publisher=None,
            pub_date="1950",
            source_id="001",
        )

        copyright_pub = Publication(
            title="Test Book",
            author="Test Author",
            publisher=None,
            pub_date="1950",
            source_id="c001",
        )

        # Test through public API - should work without publisher data
        result = matcher.find_best_match(
            marc_pub,
            [copyright_pub],
            title_threshold=40,
            author_threshold=30,
            year_tolerance=1,
            publisher_threshold=20,  # Won't be applied since no publisher data
            early_exit_title=95,
            early_exit_author=90,
        )

        # Should find a match based on title and author
        assert result is not None
        # Publisher score should be 0 since no publisher data
        assert result["similarity_scores"]["publisher"] == 0.0
        # Combined score with exact title/author match but no publisher
        # The actual score is 83.33 based on the weight distribution
        assert result["similarity_scores"]["combined"] == 83.33

    def test_find_best_match_with_abbreviated_author(self):
        """Test matching with abbreviated author names"""
        matcher = DataMatcher()

        marc_pub = Publication(
            title="Book Title",
            author="Smith, John",  # Full author name
            pub_date="1950",
            source_id="001",
        )

        copyright_pubs = [
            Publication(
                title="Book Title",
                author="Smith, J.",  # Abbreviated match
                pub_date="1950",
                source_id="c001",
            )
        ]

        result = matcher.find_best_match(
            marc_pub,
            copyright_pubs,
            year_tolerance=2,
            title_threshold=40,
            author_threshold=30,
            publisher_threshold=20,
            early_exit_title=95,
            early_exit_author=90,
            generic_detector=None,
        )

        # Should find match even with abbreviated author
        assert result is not None
        assert result["copyright_record"]["source_id"] == "c001"


# =============================================================================
# Ignore Thresholds Mode Tests
# =============================================================================


class TestDataMatcherIgnoreThresholds:
    """Test DataMatcher find_best_match_ignore_thresholds functionality"""

    def test_find_best_match_ignore_thresholds_with_minimum_score(self):
        """Test ignore thresholds mode with minimum combined score filter"""
        matcher = DataMatcher()

        marc_pub = Publication(
            title="The Great Gatsby", author="F. Scott Fitzgerald", pub_date="1925", source_id="001"
        )

        copyright_pubs = [
            Publication(
                title="The Not So Great Gatsby",
                author="Scott Fitzgerald",
                pub_date="1925",
                source_id="c001",
            ),
            Publication(
                title="Something Completely Different",
                author="John Doe",
                pub_date="1925",
                source_id="c002",
            ),
        ]

        GenericTitleDetector()

        # Test with minimum score that filters out low matches
        result = matcher.find_best_match_ignore_thresholds(
            marc_pub,
            copyright_pubs,
            year_tolerance=2,
            minimum_combined_score=50,  # Should filter out the second publication
        )

        assert result is not None
        assert result["copyright_record"]["source_id"] == "c001"
        assert result["similarity_scores"]["combined"] > 50

    def test_find_best_match_ignore_thresholds_best_above_minimum(self):
        """Test ignore thresholds mode with best match above minimum"""
        matcher = DataMatcher()

        marc_pub = Publication(
            title="Test Book", author="Test Author", pub_date="1950", source_id="001"
        )

        copyright_pubs = [
            Publication(
                title="Different Title",
                author="Different Author",
                pub_date="1950",
                source_id="c001",
            ),
            Publication(
                title="Test Book Modified", author="Test Author", pub_date="1950", source_id="c002"
            ),
        ]

        # Use find_best_match_ignore_thresholds method
        result = matcher.find_best_match_ignore_thresholds(
            marc_pub, copyright_pubs, year_tolerance=2, minimum_combined_score=30.0
        )

        assert result is not None
        assert result["copyright_record"]["source_id"] == "c002"

    def test_find_best_match_ignore_thresholds_lccn_match(self):
        """Test ignore thresholds mode with LCCN exact match"""
        matcher = DataMatcher()

        marc_pub = Publication(
            title="The Great Gatsby",
            author="F. Scott Fitzgerald",
            pub_date="1925",
            source_id="001",
            lccn="25012345",
        )
        marc_pub.normalized_lccn = "25012345"

        copyright_pubs = [
            Publication(
                title="Different Title",
                author="Different Author",
                pub_date="1926",
                source_id="c001",
            ),
            Publication(
                title="The Great Gatsby",
                author="F. Scott Fitzgerald",
                pub_date="1925",
                source_id="c002",
                lccn="25012345",
            ),
        ]
        copyright_pubs[1].normalized_lccn = "25012345"

        GenericTitleDetector()

        result = matcher.find_best_match_ignore_thresholds(
            marc_pub, copyright_pubs, year_tolerance=2
        )

        assert result is not None
        assert result["copyright_record"]["source_id"] == "c002"
        assert result["is_lccn_match"] == True

    def test_find_best_match_ignore_thresholds_year_tolerance(self):
        """Test ignore thresholds mode respects year tolerance"""
        matcher = DataMatcher()

        marc_pub = Publication(
            title="The Great Gatsby", author="F. Scott Fitzgerald", pub_date="1925", source_id="001"
        )

        copyright_pubs = [
            Publication(
                title="The Great Gatsby",
                author="F. Scott Fitzgerald",
                pub_date="1930",  # Outside year tolerance
                source_id="c001",
            ),
            Publication(
                title="The Great Gatsby",
                author="F. Scott Fitzgerald",
                pub_date="1926",  # Within tolerance
                source_id="c002",
            ),
        ]

        GenericTitleDetector()

        result = matcher.find_best_match_ignore_thresholds(
            marc_pub, copyright_pubs, year_tolerance=2  # Only allows 1926, not 1930
        )

        assert result is not None
        assert result["copyright_record"]["source_id"] == "c002"

    def test_find_best_match_ignore_thresholds_no_year_in_marc(self):
        """Test ignore thresholds mode when MARC has no year"""
        matcher = DataMatcher()

        marc_pub = Publication(
            title="The Great Gatsby",
            author="F. Scott Fitzgerald",
            pub_date=None,  # No year
            source_id="001",
        )

        copyright_pubs = [
            Publication(
                title="The Great Gatsby",
                author="F. Scott Fitzgerald",
                pub_date="1925",
                source_id="c001",
            )
        ]

        GenericTitleDetector()

        result = matcher.find_best_match_ignore_thresholds(
            marc_pub, copyright_pubs, year_tolerance=2
        )

        # Should still match when MARC has no year
        assert result is not None
        assert result["copyright_record"]["source_id"] == "c001"


# =============================================================================
# Publisher Early Exit Tests
# =============================================================================


class TestPublisherEarlyExit:
    """Test that publisher score is included in early exit decision"""

    def test_early_exit_with_all_high_scores(self):
        """Test early exit when title, author, and publisher all meet thresholds"""
        matcher = DataMatcher()

        marc_pub = Publication(
            title="The Great Gatsby",
            author="F. Scott Fitzgerald",
            publisher="Charles Scribner's Sons",
            pub_date="1925",
            source_id="001",
        )

        # Create many candidates to test early exit
        copyright_pubs = []

        # First publication should trigger early exit
        perfect_match = Publication(
            title="The Great Gatsby",
            author="F. Scott Fitzgerald",
            publisher="Charles Scribner's Sons",
            pub_date="1925",
            source_id="c001",
        )
        copyright_pubs.append(perfect_match)

        # Add many more that should not be evaluated due to early exit
        for i in range(2, 100):
            pub = Publication(
                title=f"Different Book {i}",
                author=f"Different Author {i}",
                publisher=f"Different Publisher {i}",
                pub_date="1925",
                source_id=f"c{i:03d}",
            )
            copyright_pubs.append(pub)

        # Mock the similarity calculator to track calls
        with patch.object(
            matcher.similarity_calculator, "calculate_title_similarity"
        ) as mock_title:
            with patch.object(
                matcher.similarity_calculator, "calculate_author_similarity"
            ) as mock_author:
                with patch.object(
                    matcher.similarity_calculator, "calculate_publisher_similarity"
                ) as mock_publisher:
                    # Set up return values for the first match
                    mock_title.return_value = 100.0
                    mock_author.return_value = 100.0
                    mock_publisher.return_value = 100.0

                    result = matcher.find_best_match(
                        marc_pub,
                        copyright_pubs,
                        title_threshold=40,
                        author_threshold=30,
                        year_tolerance=1,
                        publisher_threshold=30,
                        early_exit_title=95,
                        early_exit_author=90,
                        early_exit_publisher=85,
                        generic_detector=None,
                    )

                    assert result is not None
                    assert result["copyright_record"]["source_id"] == "c001"

                    # Should have only evaluated the first candidate due to early exit
                    assert mock_title.call_count == 1
                    assert mock_author.call_count == 1
                    assert mock_publisher.call_count == 1

    def test_no_early_exit_when_publisher_low(self):
        """Test no early exit when publisher score is below threshold"""
        matcher = DataMatcher()

        marc_pub = Publication(
            title="The Great Gatsby",
            author="F. Scott Fitzgerald",
            publisher="Charles Scribner's Sons",
            pub_date="1925",
            source_id="001",
        )

        copyright_pubs = [
            Publication(
                title="The Great Gatsby",
                author="F. Scott Fitzgerald",
                publisher="Different Publisher",  # Low publisher match
                pub_date="1925",
                source_id="c001",
            ),
            Publication(
                title="The Great Gatsby",
                author="F. Scott Fitzgerald",
                publisher="Charles Scribner's Sons",  # Perfect publisher match
                pub_date="1925",
                source_id="c002",
            ),
        ]

        # Mock the similarity calculator
        with patch.object(
            matcher.similarity_calculator, "calculate_title_similarity"
        ) as mock_title:
            with patch.object(
                matcher.similarity_calculator, "calculate_author_similarity"
            ) as mock_author:
                with patch.object(
                    matcher.similarity_calculator, "calculate_publisher_similarity"
                ) as mock_publisher:
                    mock_title.return_value = 100.0
                    mock_author.return_value = 100.0

                    # First call returns low score, second returns high score
                    mock_publisher.side_effect = [20.0, 100.0]

                    result = matcher.find_best_match(
                        marc_pub,
                        copyright_pubs,
                        title_threshold=40,
                        author_threshold=30,
                        year_tolerance=1,
                        publisher_threshold=30,
                        early_exit_title=95,
                        early_exit_author=90,
                        early_exit_publisher=85,  # High threshold
                        generic_detector=None,
                    )

                    assert result is not None
                    # Should have evaluated both candidates (no early exit on first)
                    assert mock_title.call_count == 2
                    assert mock_author.call_count == 2
                    assert mock_publisher.call_count == 2

                    # Should return the second match (better combined score)
                    assert result["copyright_record"]["source_id"] == "c002"

    def test_early_exit_without_publisher_data(self):
        """Test early exit still works when no publisher data exists"""
        matcher = DataMatcher()

        marc_pub = Publication(
            title="The Great Gatsby",
            author="F. Scott Fitzgerald",
            # No publisher data
            pub_date="1925",
            source_id="001",
        )

        copyright_pubs = [
            Publication(
                title="The Great Gatsby",
                author="F. Scott Fitzgerald",
                # No publisher data
                pub_date="1925",
                source_id="c001",
            ),
            Publication(
                title="Another Book", author="Another Author", pub_date="1925", source_id="c002"
            ),
        ]

        # Mock the similarity calculator
        with patch.object(
            matcher.similarity_calculator, "calculate_title_similarity"
        ) as mock_title:
            with patch.object(
                matcher.similarity_calculator, "calculate_author_similarity"
            ) as mock_author:
                with patch.object(
                    matcher.similarity_calculator, "calculate_publisher_similarity"
                ) as mock_publisher:
                    mock_title.side_effect = [100.0, 0.0]
                    mock_author.side_effect = [100.0, 0.0]
                    mock_publisher.return_value = 0.0  # No publisher data

                    result = matcher.find_best_match(
                        marc_pub,
                        copyright_pubs,
                        title_threshold=40,
                        author_threshold=30,
                        year_tolerance=1,
                        publisher_threshold=30,
                        early_exit_title=95,
                        early_exit_author=90,
                        early_exit_publisher=85,
                        generic_detector=None,
                    )

                    assert result is not None
                    assert result["copyright_record"]["source_id"] == "c001"

                    # Should have only evaluated first candidate (early exit)
                    # When no publisher data, publisher similarity is not calculated
                    assert mock_title.call_count == 1
                    assert mock_author.call_count == 1
                    # Publisher similarity not called when no publisher data
                    assert mock_publisher.call_count == 0

    def test_publisher_threshold_enforcement(self):
        """Test that publisher threshold is enforced when data exists"""
        matcher = DataMatcher()

        marc_pub = Publication(
            title="Test Book",
            author="Test Author",
            publisher="Test Publisher",
            pub_date="1950",
            source_id="001",
        )

        copyright_pubs = [
            Publication(
                title="Test Book",
                author="Test Author",
                publisher="Wrong Publisher",  # Should fail threshold
                pub_date="1950",
                source_id="c001",
            )
        ]

        result = matcher.find_best_match(
            marc_pub,
            copyright_pubs,
            title_threshold=40,
            author_threshold=30,
            year_tolerance=1,
            publisher_threshold=80,  # High threshold
            early_exit_title=95,
            early_exit_author=90,
            early_exit_publisher=85,
            generic_detector=None,
        )

        # Should not find a match due to publisher threshold
        assert result is None


# =============================================================================
# Match Result Creation Tests
# =============================================================================


class TestMatchResultCreation:
    """Test match result creation edge cases"""

    def test_create_match_result_year_difference(self):
        """Test match result creation with year calculation"""
        matcher = DataMatcher()

        # MARC pub with year
        marc_pub = Publication(
            title="Test Book", author="Test Author", pub_date="1950", source_id="001"
        )

        copyright_pub = Publication(
            title="Test Book",
            author="Test Author",
            publisher="Test Publisher",
            pub_date="1952",  # Different year
            source_id="c001",
        )

        # Test through public API - should find match despite year difference
        result = matcher.find_best_match(
            marc_pub,
            [copyright_pub],
            title_threshold=40,
            author_threshold=30,
            year_tolerance=2,  # Allow 2 year difference
            publisher_threshold=20,
            early_exit_title=95,
            early_exit_author=90,
        )

        # Check result structure
        assert result is not None
        assert "copyright_record" in result
        assert "similarity_scores" in result
        # Should have high similarity scores
        assert result["similarity_scores"]["title"] > 90
        assert result["similarity_scores"]["author"] > 90

    def test_create_match_result_regular(self):
        """Test create_match_result for regular match"""
        copyright_pub = Publication(
            title="Test Book",
            author="Test Author",
            publisher="Test Publisher",
            pub_date="1950",
            source_id="c001",
        )

        marc_pub = Publication(
            title="Test Book", author="Test Author", pub_date="1950", source_id="m001"
        )

        generic_detector = GenericTitleDetector()

        result = MatchResultBuilder.create_match_result(
            marc_pub,
            copyright_pub,
            85.0,  # title_score
            90.0,  # author_score
            75.0,  # publisher_score
            85.0,  # combined_score
            generic_detector,
            is_lccn_match=False,
        )

        assert isinstance(result, dict)
        assert result["is_lccn_match"] == False
        assert result["similarity_scores"]["title"] == 85.0
        assert result["similarity_scores"]["author"] == 90.0
        assert result["similarity_scores"]["publisher"] == 75.0
        assert result["similarity_scores"]["combined"] == 85.0

    def test_create_match_result_lccn(self):
        """Test create_match_result for LCCN match"""
        copyright_pub = Publication(
            title="Test Book",
            author="Test Author",
            pub_date="1950",
            source_id="c001",
            lccn="50012345",
        )

        marc_pub = Publication(
            title="Test Book",
            author="Test Author",
            pub_date="1950",
            source_id="m001",
            lccn="50012345",
        )

        generic_detector = GenericTitleDetector()

        result = MatchResultBuilder.create_match_result(
            marc_pub,
            copyright_pub,
            100.0,  # title_score
            100.0,  # author_score
            100.0,  # publisher_score
            100.0,  # combined_score
            generic_detector,
            is_lccn_match=True,
        )

        assert result["is_lccn_match"] == True
        assert all(
            result["similarity_scores"][field] == 100.0
            for field in ["title", "author", "publisher", "combined"]
        )


# =============================================================================
# Score Combination Tests
# =============================================================================


class TestScoreCombination:
    """Test score combination functionality"""

    def test_calculate_combined_score_no_author(self):
        """Test combined score calculation without author"""
        DataMatcher()

        marc_pub = Publication(
            title="Book Title",
            author="",  # Empty author
            publisher="Publisher",
            pub_date="1950",
            source_id="001",
        )

        copyright_pub = Publication(
            title="Book Title",
            author="",  # Empty author
            publisher="Publisher",
            pub_date="1950",
            source_id="c001",
        )

        # Use ScoreCombiner directly for testing score combination
        config = get_config()
        combiner = ScoreCombiner(config)
        score = combiner.combine_scores(
            title_score=90.0,
            author_score=0.0,
            publisher_score=80.0,
            has_generic_title=False,
            use_config_weights=True,
        )

        # Without author, weight should be redistributed
        assert score > 0

    def test_calculate_combined_score_only_title(self):
        """Test combined score with only title available"""
        DataMatcher()

        marc_pub = Publication(
            title="Book Title",
            author="",  # Empty author
            publisher="",  # Empty publisher
            pub_date="1950",
            source_id="001",
        )

        copyright_pub = Publication(title="Book Title", pub_date="1950", source_id="c001")

        # Use ScoreCombiner directly for testing score combination
        config = get_config()
        combiner = ScoreCombiner(config)
        score = combiner.combine_scores(
            title_score=85.0,
            author_score=0.0,
            publisher_score=0.0,
            has_generic_title=False,
            use_config_weights=True,
        )

        # With default weights (0.5/0.3/0.2) and normalization,
        # when only title has a score, the combined score is lower
        assert score == 49.58

    def test_find_best_match_no_matches_below_threshold(self):
        """Test find_best_match when all candidates are below threshold"""
        matcher = DataMatcher()

        marc_pub = Publication(
            title="Unique Book Title That Won't Match",
            author="Unknown Author",
            pub_date="1950",
            source_id="001",
        )

        copyright_pubs = [
            Publication(
                title="Completely Different Title",
                author="Different Author",
                pub_date="1950",
                source_id="c001",
            ),
            Publication(
                title="Another Different Title",
                author="Another Author",
                pub_date="1950",
                source_id="c002",
            ),
        ]

        result = matcher.find_best_match(
            marc_pub,
            copyright_pubs,
            year_tolerance=2,
            title_threshold=80,  # High threshold
            author_threshold=80,  # High threshold
            publisher_threshold=80,
            early_exit_title=95,
            early_exit_author=90,
            generic_detector=None,
        )

        # Should return None when no matches meet threshold
        assert result is None


# =============================================================================
# Worker Initialization Tests
# =============================================================================


class TestWorkerFunctions:
    """Test worker-related functions"""

    def test_init_worker_with_detector_config(self):
        """Test worker initialization with detector config"""
        # Create temp directories and files
        with TemporaryDirectory() as tmpdir:
            cache_dir = join(tmpdir, "cache")
            copyright_dir = join(tmpdir, "copyright")
            renewal_dir = join(tmpdir, "renewal")

            makedirs(cache_dir)
            makedirs(copyright_dir)
            makedirs(renewal_dir)

            # Test with detector config
            detector_config = {"frequency_threshold": 10, "custom_patterns": {"test pattern"}}

            with patch("marc_pd_tool.infrastructure.CacheManager") as mock_cache_mgr:
                mock_cache = Mock()
                # Create mock indexes with size method
                mock_reg_index = Mock()
                mock_reg_index.size.return_value = 100
                mock_ren_index = Mock()
                mock_ren_index.size.return_value = 50
                # Return tuple of (registration_index, renewal_index)
                mock_cache.get_cached_indexes.return_value = (mock_reg_index, mock_ren_index)
                mock_cache.get_cached_generic_detector.return_value = (
                    Mock()
                )  # Mock generic detector
                mock_cache_mgr.return_value = mock_cache

                # Patch worker globals to None
                # Local imports
                import marc_pd_tool.application.processing.matching_engine

                with (
                    patch.object(
                        marc_pd_tool.application.processing.matching_engine,
                        "_worker_registration_index",
                        None,
                    ),
                    patch.object(
                        marc_pd_tool.application.processing.matching_engine,
                        "_worker_renewal_index",
                        None,
                    ),
                    patch.object(
                        marc_pd_tool.application.processing.matching_engine,
                        "_worker_generic_detector",
                        None,
                    ),
                    patch.object(
                        marc_pd_tool.application.processing.matching_engine, "_worker_config", None
                    ),
                ):
                    init_worker(
                        cache_dir,
                        copyright_dir,
                        renewal_dir,
                        "test_hash",
                        detector_config,
                        1950,  # min_year
                        1960,  # max_year
                        False,  # brute_force
                    )

                    # Worker initialization should succeed
                    assert mock_cache_mgr.called
                    assert mock_cache.get_cached_indexes.called

    def test_init_worker_with_cached_data(self, tmp_path):
        """Test worker initialization with cached indexes"""
        cache_dir = str(tmp_path / "cache")
        copyright_dir = str(tmp_path / "copyright")
        renewal_dir = str(tmp_path / "renewal")

        # Create directories
        makedirs(cache_dir, exist_ok=True)
        makedirs(copyright_dir, exist_ok=True)
        makedirs(renewal_dir, exist_ok=True)

        # Create minimal data files
        copyright_file = tmp_path / "copyright" / "test.xml"
        copyright_file.write_text(
            """<?xml version="1.0" encoding="UTF-8"?>
        <copyrightEntries></copyrightEntries>"""
        )

        renewal_file = tmp_path / "renewal" / "test.tsv"
        renewal_file.write_text("title\tauthor\toreg\todat\tid\trdat\tclaimants\n")

        with patch("marc_pd_tool.infrastructure.CacheManager") as mock_cache_class:
            mock_cache = Mock()
            mock_cache_class.return_value = mock_cache

            # Mock successful cache retrieval
            mock_reg_index = Mock()
            mock_reg_index.size.return_value = 100
            mock_ren_index = Mock()
            mock_ren_index.size.return_value = 50
            mock_detector = Mock()

            mock_cache.get_cached_indexes.return_value = (mock_reg_index, mock_ren_index)
            mock_cache.get_cached_generic_detector.return_value = mock_detector

            # Initialize worker (should succeed with mocked cache)
            with patch(
                "marc_pd_tool.application.processing.matching_engine.getpid", return_value=12345
            ):
                with patch("psutil.Process") as mock_process_class:
                    # Mock process memory info
                    mock_process = Mock()
                    mock_process.memory_info.return_value.rss = 1024 * 1024 * 100  # 100MB
                    mock_process_class.return_value = mock_process

                    init_worker(
                        cache_dir,
                        copyright_dir,
                        renewal_dir,
                        "test_hash",
                        {"min_length": 10},
                        min_year=1950,
                        max_year=1960,
                        brute_force=False,
                    )

            # The test succeeds if no exception is raised


# =============================================================================
# Batch Processing Tests
# =============================================================================


class TestProcessBatch:
    """Test process_batch function"""

    def setup_method(self):
        """Ensure worker globals are reset before each test"""
        # Local imports
        import marc_pd_tool.application.processing.matching_engine

        # Initialize worker globals
        marc_pd_tool.application.processing.matching_engine._worker_registration_index = None
        marc_pd_tool.application.processing.matching_engine._worker_renewal_index = None
        marc_pd_tool.application.processing.matching_engine._worker_generic_detector = None
        marc_pd_tool.application.processing.matching_engine._worker_config = None
        marc_pd_tool.application.processing.matching_engine._worker_options = None

    def test_process_batch_success(self, tmp_path):
        """Test successful batch processing"""
        # Create batch and result directories
        batch_dir = tmp_path / "batches"
        result_dir = tmp_path / "results"
        batch_dir.mkdir()
        result_dir.mkdir()

        # Create test publications
        publications = [
            Publication(
                title="Book 1",
                author="Author 1",
                pub_date="1955",
                source_id="001",
                country_code="xxu",
                country_classification=CountryClassification.US,
            ),
            Publication(
                title="Book 2",
                author="Author 2",
                pub_date="1960",
                source_id="002",
                country_code="xxu",
                country_classification=CountryClassification.US,
            ),
        ]

        # Create batch file
        batch_file = batch_dir / "batch_00001.pkl"
        with open(batch_file, "wb") as f:
            pickle_dump(publications, f)

        # Create BatchProcessingInfo tuple (20 fields)
        batch_info = (
            1,  # batch_id
            str(batch_file),  # batch_path
            str(tmp_path / "cache"),  # cache_dir
            str(tmp_path / "copyright"),  # copyright_dir
            str(tmp_path / "renewal"),  # renewal_dir
            "test_hash",  # config_hash
            {"min_length": 10},  # detector_config
            1,  # total_batches
            40,  # title_threshold
            30,  # author_threshold
            20,  # publisher_threshold
            2,  # year_tolerance
            95,  # early_exit_title
            90,  # early_exit_author
            85,  # early_exit_publisher
            False,  # score_everything_mode
            None,  # minimum_combined_score
            False,  # brute_force_missing_year
            1950,  # min_year
            1960,  # max_year
            str(result_dir),  # result_temp_dir
        )

        # Create mock indexes that return empty lists for no matches
        mock_reg_index = Mock()
        mock_reg_index.find_candidates = Mock(return_value=[])
        mock_reg_index.publications = []

        mock_ren_index = Mock()
        mock_ren_index.find_candidates = Mock(return_value=[])
        mock_ren_index.publications = []

        # Create a real DataMatcher instance
        DataMatcher()

        # Import the module
        # Local imports
        import marc_pd_tool.application.processing.matching_engine

        # Patch worker globals at the module level
        with (
            patch.object(
                marc_pd_tool.application.processing.matching_engine,
                "_worker_registration_index",
                mock_reg_index,
            ),
            patch.object(
                marc_pd_tool.application.processing.matching_engine,
                "_worker_renewal_index",
                mock_ren_index,
            ),
            patch.object(
                marc_pd_tool.application.processing.matching_engine,
                "_worker_generic_detector",
                Mock(is_generic=Mock(return_value=False)),
            ),
            patch.object(
                marc_pd_tool.application.processing.matching_engine, "_worker_config", None
            ),
        ):
            # Process batch
            batch_id, result_path, stats = process_batch(batch_info)

            assert batch_id == 1
            assert exists(result_path)
            # Stats is now a BatchStats Pydantic model
            assert isinstance(stats, BatchStats)
            assert stats.batch_id == 1
            assert stats.marc_count == 2
            assert stats.registration_matches_found == 0
            assert stats.renewal_matches_found == 0

    def test_process_batch_worker_not_initialized(self, tmp_path):
        """Test process_batch when worker is not initialized"""
        # Create a temporary batch file
        with NamedTemporaryFile(suffix=".pkl", delete=False) as f:
            batch_path = f.name
            pickle_dump([Publication(title="Test", source_id="001")], f)

        # Create result directory
        result_dir = tmp_path / "results"
        result_dir.mkdir()

        try:
            # Create a minimal batch info
            batch_info = (
                1,  # batch_id
                batch_path,  # batch_path
                "cache_dir",  # cache_dir
                "copyright_dir",  # copyright_dir
                "renewal_dir",  # renewal_dir
                "test_hash",  # config_hash
                None,  # detector_config
                1,  # total_batches
                40,  # title_threshold
                30,  # author_threshold
                20,  # publisher_threshold
                2,  # year_tolerance
                95,  # early_exit_title
                90,  # early_exit_author
                85,  # early_exit_publisher
                False,  # score_everything_mode
                None,  # minimum_combined_score
                False,  # brute_force_missing_year
                1950,  # min_year
                1960,  # max_year
                str(result_dir),  # result_temp_dir
            )

            # Clear worker globals to simulate uninitialized state
            # Local imports
            import marc_pd_tool.application.processing.matching_engine

            marc_pd_tool.application.processing.matching_engine._worker_registration_index = None
            marc_pd_tool.application.processing.matching_engine._worker_renewal_index = None
            marc_pd_tool.application.processing.matching_engine._worker_generic_detector = None
            marc_pd_tool.application.processing.matching_engine._worker_config = None
            marc_pd_tool.application.processing.matching_engine._worker_options = None

            # Process batch - error should be caught and handled
            batch_id, result_path, stats = process_batch(batch_info)

            # Check that the error was recorded
            assert batch_id == 1
            # Stats should be a BatchStats model
            assert isinstance(stats, BatchStats)
            assert stats.batch_id == 1
            assert hasattr(stats, "marc_count")

            # Result file should exist
            # The function now returns the normal result path even when workers are not initialized
            assert result_path.endswith("_result.pkl")

        finally:
            # Clean up
            if exists(batch_path):
                unlink(batch_path)

    def test_process_batch_with_pickle_error(self, tmp_path):
        """Test batch processing with pickle loading error"""
        # Create batch file with invalid pickle data
        batch_file = tmp_path / "bad_batch.pkl"
        with open(batch_file, "wb") as f:
            f.write(b"invalid pickle data")

        result_dir = tmp_path / "results"
        result_dir.mkdir()

        # Create BatchProcessingInfo tuple
        batch_info = (
            1,  # batch_id
            str(batch_file),  # batch_path
            str(tmp_path / "cache"),  # cache_dir
            str(tmp_path / "copyright"),  # copyright_dir
            str(tmp_path / "renewal"),  # renewal_dir
            "test_hash",  # config_hash
            {"min_length": 10},  # detector_config
            1,  # total_batches
            40,  # title_threshold
            30,  # author_threshold
            20,  # publisher_threshold
            2,  # year_tolerance
            95,  # early_exit_title
            90,  # early_exit_author
            85,  # early_exit_publisher
            False,  # score_everything_mode
            None,  # minimum_combined_score
            False,  # brute_force_missing_year
            1950,  # min_year
            1960,  # max_year
            str(result_dir),  # result_temp_dir
        )

        # Process batch - the function raises on pickle error
        # Local imports
        import marc_pd_tool.application.processing.matching_engine

        with (
            patch.object(
                marc_pd_tool.application.processing.matching_engine,
                "_worker_registration_index",
                Mock(),
            ),
            patch.object(
                marc_pd_tool.application.processing.matching_engine, "_worker_renewal_index", Mock()
            ),
            patch.object(
                marc_pd_tool.application.processing.matching_engine,
                "_worker_generic_detector",
                Mock(),
            ),
            patch.object(
                marc_pd_tool.application.processing.matching_engine, "_worker_config", None
            ),
        ):
            # Expect the exception to be raised
            with raises(UnpicklingError):
                process_batch(batch_info)


# =============================================================================
# Skip No Year Records Tests
# =============================================================================


class TestSkipNoYearRecords:
    """Test that MARC records without year data are handled correctly"""

    def _setup_mock_worker_data(self, monkeypatch, mock_index_class=None):
        """Helper to set up mock worker data for tests"""
        if mock_index_class is None:

            class MockIndex:
                def find_candidates(self, pub):
                    return []  # Return empty list of indices

                publications = []  # Empty publications list

                def get_stats(self):
                    return {"title_keys": 0, "author_keys": 0}

                def size(self):
                    return 0

            mock_index_class = MockIndex

        # Import matching_engine module to access global variables
        # Local imports
        from marc_pd_tool.application.processing import matching_engine
        from marc_pd_tool.infrastructure.config import get_config

        # Set up the mock worker globals
        mock_index = mock_index_class()
        matching_engine._worker_registration_index = mock_index
        matching_engine._worker_renewal_index = mock_index
        matching_engine._worker_generic_detector = None
        matching_engine._worker_config = get_config()  # Use actual Config object
        matching_engine._worker_options = None  # Add worker options

    @fixture
    def mock_batch_info_with_year(self, tmp_path):
        """Create batch info with MARC records that have year data"""
        # Create minimal cache directory structure
        cache_dir = tmp_path / "test_cache"
        cache_dir.mkdir()

        marc_pub_with_year = Publication(
            title="Test Book With Year",
            author="Smith, John",
            pub_date="2023",
            source="MARC",
            source_id="test001",
        )

        # Create pickle file for the batch
        batch_path = tmp_path / "batch_with_year.pkl"
        with open(batch_path, "wb") as f:
            pickle_dump([marc_pub_with_year], f)

        batch_info = (
            1,  # batch_id
            str(batch_path),  # batch_path
            str(cache_dir),  # cache_dir
            "copyright_dir",  # copyright_dir
            "renewal_dir",  # renewal_dir
            "config_hash",  # config_hash
            {"disabled": True},  # detector_config - disable generic detector for tests
            1,  # total_batches
            40,  # title_threshold
            30,  # author_threshold
            60,  # publisher_threshold
            1,  # year_tolerance
            95,  # early_exit_title
            90,  # early_exit_author
            85,  # early_exit_publisher
            False,  # score_everything
            40,  # minimum_combined_score
            False,  # brute_force_missing_year (default: skip no-year records)
            None,  # min_year
            None,  # max_year
            "/tmp/test_results",  # result_temp_dir
        )
        return batch_info

    @fixture
    def mock_batch_info_no_year(self, tmp_path):
        """Create batch info with MARC records that lack year data"""
        # Create minimal cache directory structure
        cache_dir = tmp_path / "test_cache"
        cache_dir.mkdir()

        marc_pub_no_year = Publication(
            title="Test Book Without Year",
            author="Jones, Jane",
            pub_date=None,  # No year
            source="MARC",
            source_id="test002",
        )

        # Create pickle file for the batch
        batch_path = tmp_path / "batch_no_year.pkl"
        with open(batch_path, "wb") as f:
            pickle_dump([marc_pub_no_year], f)

        batch_info = (
            1,  # batch_id
            str(batch_path),  # batch_path
            str(cache_dir),  # cache_dir
            "copyright_dir",  # copyright_dir
            "renewal_dir",  # renewal_dir
            "config_hash",  # config_hash
            {"disabled": True},  # detector_config - disable generic detector for tests
            1,  # total_batches
            40,  # title_threshold
            30,  # author_threshold
            60,  # publisher_threshold
            1,  # year_tolerance
            95,  # early_exit_title
            90,  # early_exit_author
            85,  # early_exit_publisher
            False,  # score_everything
            40,  # minimum_combined_score
            False,  # brute_force_missing_year (default: skip no-year records)
            None,  # min_year
            None,  # max_year
            "/tmp/test_results",  # result_temp_dir
        )
        return batch_info

    def test_skip_records_without_year_by_default(
        self, mock_batch_info_no_year, monkeypatch, tmp_path
    ):
        """Test that records without year are skipped by default"""

        # Set up mock worker data
        self._setup_mock_worker_data(monkeypatch)

        # Create temp directory for results
        result_dir = tmp_path / "results"
        result_dir.mkdir()

        # Update batch info with real temp directory
        batch_info_list = list(mock_batch_info_no_year)
        batch_info_list[-1] = str(result_dir)
        mock_batch_info_no_year = tuple(batch_info_list)

        # Process the batch
        batch_id, result_file_path, stats = process_batch(mock_batch_info_no_year)

        # Load the results from the pickle file
        with open(result_file_path, "rb") as f:
            processed_pubs = pickle_load(f)

        # The record should be skipped, so no publications should be processed
        assert len(processed_pubs) == 0
        assert stats.marc_count == 0
        assert stats.registration_matches_found == 0
        assert stats.renewal_matches_found == 0
        assert stats.skipped_no_year == 1  # Should track the skipped record

    def test_process_records_without_year_with_brute_force(
        self, mock_batch_info_no_year, monkeypatch, tmp_path
    ):
        """Test that records without year are processed when brute-force option is enabled"""
        # Create temp directory for results
        result_dir = tmp_path / "results"
        result_dir.mkdir()

        # Enable brute force mode and update temp directory
        batch_info_list = list(mock_batch_info_no_year)
        # The batch info tuple has brute_force_missing_year at index 17 (after adding early_exit_publisher)
        batch_info_list[17] = True  # Set brute_force_missing_year to True
        batch_info_list[-1] = str(result_dir)  # Update result_temp_dir
        batch_info_brute_force = tuple(batch_info_list)

        # Set up mock worker data
        self._setup_mock_worker_data(monkeypatch)

        # Process the batch
        batch_id, result_file_path, stats = process_batch(batch_info_brute_force)

        # Load the results from the pickle file
        with open(result_file_path, "rb") as f:
            processed_pubs = pickle_load(f)

        # The record should be processed even without a year
        assert len(processed_pubs) == 1
        assert stats.marc_count == 1
        assert processed_pubs[0].original_title == "Test Book Without Year"
