# tests/test_processing/test_matching_engine_additional_fixed.py

"""Additional tests for matching_engine.py to reach 100% coverage"""

# Standard library imports
from unittest.mock import Mock
from unittest.mock import patch
import pickle
import tempfile
import os

# Third party imports
import pytest

# Local imports
from marc_pd_tool.processing.matching_engine import DataMatcher
from marc_pd_tool.processing.matching_engine import process_batch
from marc_pd_tool.processing.matching_engine import _worker_data
from marc_pd_tool.data.publication import Publication
from marc_pd_tool.data.enums import CountryClassification
from marc_pd_tool.processing.similarity_calculator import SimilarityCalculator
from marc_pd_tool.utils.types import BatchProcessingInfo


class TestProcessBatch:
    """Test process_batch function"""
    
    def setup_method(self):
        """Ensure _worker_data is reset before each test"""
        # Initialize _worker_data to a non-empty dict so it's truthy
        import marc_pd_tool.processing.matching_engine
        marc_pd_tool.processing.matching_engine._worker_data = {"initialized": True}
    
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
                country_classification=CountryClassification.US
            ),
            Publication(
                title="Book 2", 
                author="Author 2",
                pub_date="1960",
                source_id="002",
                country_code="xxu",
                country_classification=CountryClassification.US
            )
        ]
        
        # Create batch file
        batch_file = batch_dir / "batch_00001.pkl"
        with open(batch_file, 'wb') as f:
            pickle.dump(publications, f)
        
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
            False,  # score_everything_mode
            None,  # minimum_combined_score
            False,  # brute_force_missing_year
            1950,  # min_year
            1960,  # max_year
            str(result_dir)  # result_temp_dir
        )
        
        # Create mock indexes that return empty lists for no matches
        mock_reg_index = Mock()
        mock_reg_index.get_candidates_list.return_value = []
        
        mock_ren_index = Mock()
        mock_ren_index.get_candidates_list.return_value = []
        
        # Create a real DataMatcher instance
        real_matcher = DataMatcher()
        
        # Patch _worker_data at the module level
        with patch('marc_pd_tool.processing.matching_engine._worker_data', {
            'registration_index': mock_reg_index,
            'renewal_index': mock_ren_index,
            'generic_detector': Mock(is_generic=Mock(return_value=False)),
            'matching_engine': real_matcher
        }):
            # Process batch
            batch_id, result_path, stats = process_batch(batch_info)
            
            assert batch_id == 1
            assert os.path.exists(result_path)
            assert isinstance(stats, dict)
            assert stats['batch_id'] == 1
            assert stats['marc_count'] == 2
            assert stats['registration_matches_found'] == 0
            assert stats['renewal_matches_found'] == 0
    
    def test_process_batch_with_matches(self, tmp_path):
        """Test batch processing with actual matches"""
        # Create batch and result directories
        batch_dir = tmp_path / "batches"
        result_dir = tmp_path / "results"
        batch_dir.mkdir()
        result_dir.mkdir()
        
        # Create test publication
        marc_pub = Publication(
            title="The Great Gatsby",
            author="F. Scott Fitzgerald",
            pub_date="1925",
            source_id="001",
            country_code="xxu",
            country_classification=CountryClassification.US
        )
        
        # Create batch file
        batch_file = batch_dir / "batch_00001.pkl"
        with open(batch_file, 'wb') as f:
            pickle.dump([marc_pub], f)
        
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
            False,  # score_everything_mode
            None,  # minimum_combined_score
            False,  # brute_force_missing_year
            1920,  # min_year
            1930,  # max_year
            str(result_dir)  # result_temp_dir
        )
        
        # Create a mock copyright publication that will match
        mock_copyright_pub = Publication(
            title="The Great Gatsby",
            author="Fitzgerald, F. Scott",
            publisher="Scribner",
            pub_date="1925",
            source_id="A00001"
        )
        
        # Create a mock matching engine that will return proper candidates
        mock_matcher = DataMatcher()
        
        # Mock worker data with matches
        mock_reg_index = Mock()
        # Return the copyright publication when candidates are requested
        mock_reg_index.get_candidates_list.return_value = [mock_copyright_pub]
        
        with patch('marc_pd_tool.processing.matching_engine._worker_data', {
            'registration_index': mock_reg_index,
            'renewal_index': Mock(get_candidates_list=Mock(return_value=[])),
            'generic_detector': Mock(is_generic=Mock(return_value=False)),
            'matching_engine': mock_matcher
        }):
            # Process batch
            batch_id, result_path, stats = process_batch(batch_info)
            
            assert batch_id == 1
            assert os.path.exists(result_path)
            assert stats['marc_count'] == 1
            assert stats['registration_matches_found'] == 1
            
            # Load and verify results
            with open(result_path, 'rb') as f:
                results = pickle.load(f)
            
            assert len(results) == 1
            assert results[0].registration_match is not None
    
    def test_process_batch_with_pickle_error(self, tmp_path):
        """Test batch processing with pickle loading error"""
        # Create batch file with invalid pickle data
        batch_file = tmp_path / "bad_batch.pkl"
        with open(batch_file, 'wb') as f:
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
            False,  # score_everything_mode
            None,  # minimum_combined_score
            False,  # brute_force_missing_year
            1950,  # min_year
            1960,  # max_year
            str(result_dir)  # result_temp_dir
        )
        
        # Process batch - the function raises on pickle error
        with patch('marc_pd_tool.processing.matching_engine._worker_data', {
            'registration_index': Mock(),
            'renewal_index': Mock(),
            'generic_detector': Mock(),
            'matching_engine': DataMatcher()
        }):
            # Expect the exception to be raised
            with pytest.raises(pickle.UnpicklingError):
                process_batch(batch_info)


class TestDataMatcherInternalMethods:
    """Test internal methods of DataMatcher"""
    
    def test_calculate_combined_score_no_author(self):
        """Test combined score calculation without author"""
        matcher = DataMatcher()
        
        marc_pub = Publication(
            title="Book Title",
            author="",  # Empty author
            publisher="Publisher",
            pub_date="1950",
            source_id="001"
        )
        
        copyright_pub = Publication(
            title="Book Title",
            author="",  # Empty author
            publisher="Publisher",
            pub_date="1950",
            source_id="c001"
        )
        
        # Call the actual internal method name
        score = matcher._combine_scores(
            title_score=90.0,
            author_score=0.0,
            publisher_score=80.0,
            marc_pub=marc_pub,
            copyright_pub=copyright_pub,
            generic_detector=None
        )
        
        # Without author, weight should be redistributed
        assert score > 0
    
    def test_calculate_combined_score_only_title(self):
        """Test combined score with only title available"""
        matcher = DataMatcher()
        
        marc_pub = Publication(
            title="Book Title",
            author="",  # Empty author
            publisher="",  # Empty publisher
            pub_date="1950",
            source_id="001"
        )
        
        copyright_pub = Publication(
            title="Book Title",
            pub_date="1950",
            source_id="c001"
        )
        
        score = matcher._combine_scores(
            title_score=85.0,
            author_score=0.0,
            publisher_score=0.0,
            marc_pub=marc_pub,
            copyright_pub=copyright_pub,
            generic_detector=None
        )
        
        # With only title, it should get full weight
        assert score == 85.0
    
    def test_find_best_match_no_matches_below_threshold(self):
        """Test find_best_match when all candidates are below threshold"""
        matcher = DataMatcher()
        
        marc_pub = Publication(
            title="Unique Book Title That Won't Match",
            author="Unknown Author",
            pub_date="1950",
            source_id="001"
        )
        
        copyright_pubs = [
            Publication(
                title="Completely Different Title",
                author="Different Author",
                pub_date="1950",
                source_id="c001"
            ),
            Publication(
                title="Another Different Title",
                author="Another Author",
                pub_date="1950",
                source_id="c002"
            )
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
            generic_detector=None
        )
        
        # Should return None when no matches meet threshold
        assert result is None
    
    def test_find_best_match_with_abbreviated_author(self):
        """Test matching with abbreviated author names"""
        matcher = DataMatcher()
        
        marc_pub = Publication(
            title="Book Title",
            author="Smith, John",  # Full author name
            pub_date="1950",
            source_id="001"
        )
        
        copyright_pubs = [
            Publication(
                title="Book Title",
                author="Smith, J.",  # Abbreviated match
                pub_date="1950",
                source_id="c001"
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
            generic_detector=None
        )
        
        # Should find match even with abbreviated author
        assert result is not None
        assert result['copyright_record']['source_id'] == "c001"