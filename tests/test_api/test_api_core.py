# tests/test_api/test_api_core.py

"""Tests for API core functionality"""

# Standard library imports
from pathlib import Path
from unittest.mock import Mock
from unittest.mock import MagicMock
from unittest.mock import patch
import json
import os
import pickle
import tempfile

# Third party imports
import pytest

# Local imports
from marc_pd_tool.api import AnalysisResults
from marc_pd_tool.api import MarcCopyrightAnalyzer
from marc_pd_tool.data.enums import CopyrightStatus
from marc_pd_tool.data.enums import CountryClassification
from marc_pd_tool.data.publication import Publication
from marc_pd_tool.infrastructure.cache_manager import CacheManager
from marc_pd_tool.infrastructure.config_loader import ConfigLoader
from marc_pd_tool.processing.matching_engine import process_batch


class TestAnalysisResults:
    """Test the AnalysisResults class"""
    
    def test_init(self):
        """Test AnalysisResults initialization"""
        results = AnalysisResults()
        assert results.publications == []
        assert results.result_file_paths == []
        assert results.statistics["total_records"] == 0
        assert results.statistics["us_records"] == 0
        assert results.statistics["non_us_records"] == 0
        assert results.statistics["registration_matches"] == 0
        assert results.statistics["renewal_matches"] == 0
        assert results.statistics["no_matches"] == 0
    
    def test_add_publication(self):
        """Test adding publications updates statistics"""
        results = AnalysisResults()
        
        # Add US publication
        pub1 = Publication(
            title="Test Book 1",
            pub_date="1960",
            source_id="001",
            country_code="xxu",
            country_classification=CountryClassification.US
        )
        results.add_publication(pub1)
        
        assert len(results.publications) == 1
        assert results.statistics["total_records"] == 1
        assert results.statistics["us_records"] == 1
        assert results.statistics["non_us_records"] == 0
        
        # Add non-US publication
        pub2 = Publication(
            title="Test Book 2",
            pub_date="1960",
            source_id="002",
            country_code="xxk",
            country_classification=CountryClassification.NON_US
        )
        results.add_publication(pub2)
        
        assert len(results.publications) == 2
        assert results.statistics["total_records"] == 2
        assert results.statistics["us_records"] == 1
        assert results.statistics["non_us_records"] == 1
    
    def test_add_result_file(self):
        """Test adding result files"""
        results = AnalysisResults()
        results.add_result_file("test.json")
        results.add_result_file("test.csv")
        
        assert len(results.result_file_paths) == 2
        assert "test.json" in results.result_file_paths
        assert "test.csv" in results.result_file_paths


class TestMarcCopyrightAnalyzer:
    """Test the MarcCopyrightAnalyzer class"""
    
    def test_init_defaults(self):
        """Test analyzer initialization with defaults"""
        analyzer = MarcCopyrightAnalyzer()
        assert analyzer.config is not None
        assert analyzer.cache_manager is not None
        assert analyzer.results is not None
        assert analyzer.cache_dir == ".marcpd_cache"
    
    def test_init_with_config(self, tmp_path):
        """Test analyzer initialization with custom config"""
        config_path = tmp_path / "test_config.json"
        config_data = {
            "default_thresholds": {
                "title": 50,
                "author": 40
            }
        }
        config_path.write_text(json.dumps(config_data))
        
        analyzer = MarcCopyrightAnalyzer(config_path=str(config_path))
        assert analyzer.config.get_threshold("title") == 50
        assert analyzer.config.get_threshold("author") == 40
    
    def test_init_with_force_refresh(self, tmp_path):
        """Test analyzer initialization with force refresh"""
        cache_dir = tmp_path / "test_cache"
        
        with patch('marc_pd_tool.api.CacheManager') as mock_cache_class:
            mock_cache = Mock()
            mock_cache_class.return_value = mock_cache
            
            analyzer = MarcCopyrightAnalyzer(
                cache_dir=str(cache_dir),
                force_refresh=True
            )
            
            mock_cache.clear_all_caches.assert_called_once()
    
    def test_compute_config_hash(self):
        """Test config hash computation"""
        analyzer = MarcCopyrightAnalyzer()
        
        config1 = {"key1": "value1", "key2": 123}
        config2 = {"key1": "value1", "key2": 123}
        config3 = {"key1": "value2", "key2": 123}
        
        hash1 = analyzer._compute_config_hash(config1)
        hash2 = analyzer._compute_config_hash(config2)
        hash3 = analyzer._compute_config_hash(config3)
        
        # Same config should produce same hash
        assert hash1 == hash2
        # Different config should produce different hash
        assert hash1 != hash3
    
    def test_process_sequentially(self, tmp_path):
        """Test sequential processing"""
        analyzer = MarcCopyrightAnalyzer()
        
        # Create test publications
        publications = [
            Publication(
                title=f"Book {i}",
                pub_date="1960",
                source_id=f"{i}",
                country_code="xxu",
                country_classification=CountryClassification.US
            )
            for i in range(5)
        ]
        
        # Mock process_batch to avoid actual processing
        with patch('marc_pd_tool.api.process_batch') as mock_process:
            # Mock the return values
            def mock_process_batch(batch_info):
                batch_stats = {
                    "batch_id": 1,
                    "marc_count": len(publications),
                    "registration_matches_found": 0,
                    "renewal_matches_found": 0,
                    "skipped_records": 0,
                    "processing_time": 0.1,
                    "records_with_errors": 0
                }
                # Create result file
                # batch_info is a tuple, extract result_temp_dir (last element)
                result_temp_dir = batch_info[-1] if isinstance(batch_info, tuple) else batch_info.result_temp_dir
                result_path = result_temp_dir + "/batch_00001_result.pkl"
                os.makedirs(os.path.dirname(result_path), exist_ok=True)
                with open(result_path, 'wb') as f:
                    # The actual process_batch saves publications directly, not a dict
                    pickle.dump(publications, f)
                return (1, result_path, batch_stats)
            
            mock_process.side_effect = mock_process_batch
            
            # Process publications
            results = analyzer._process_sequentially(
                publications=publications,
                title_threshold=40,
                author_threshold=30,
                publisher_threshold=20,
                year_tolerance=1,
                early_exit_title=95,
                early_exit_author=90,
                score_everything_mode=False,
                minimum_combined_score=None,
                brute_force_missing_year=False,
                min_year=None,
                max_year=None
            )
            
            assert len(results) == 5
            assert all(isinstance(pub, Publication) for pub in results)
    
    def test_analyze_marc_records(self):
        """Test analyze_marc_records method"""
        analyzer = MarcCopyrightAnalyzer()
        
        # Create test publications
        publications = [
            Publication(
                title="Test Book",
                pub_date="1960",
                source_id="001",
                country_code="xxu",
                country_classification=CountryClassification.US
            )
        ]
        
        # Mock dependencies
        with patch.object(analyzer, '_load_and_index_data'):
            with patch.object(analyzer, '_process_sequentially') as mock_seq:
                mock_seq.return_value = publications
                
                results = analyzer.analyze_marc_records(
                    publications,
                    options={"num_processes": 1}
                )
                
                assert len(results) == 1
                assert results[0].original_title == "Test Book"  # Check original_title, not normalized title
    
    def test_export_results_single_file(self, tmp_path):
        """Test export results with single file option"""
        analyzer = MarcCopyrightAnalyzer()
        
        # Add test publication
        pub = Publication(
            title="Export Test",
            pub_date="1960",
            source_id="001",
            country_code="xxu",
            country_classification=CountryClassification.US
        )
        analyzer.results.add_publication(pub)
        
        # Mock the exporters
        with patch('marc_pd_tool.api.save_matches_json') as mock_json:
            with patch('marc_pd_tool.exporters.csv_exporter.CSVExporter') as mock_csv_class:
                mock_csv = Mock()
                mock_csv_class.return_value = mock_csv
                
                # Export results
                output_path = str(tmp_path / "test_export")
                analyzer.export_results(
                    output_path,
                    formats=["json", "csv"],
                    single_file=True
                )
                
                # Verify exporters were called
                mock_json.assert_called_once()
                mock_csv.export.assert_called_once()
                
                # Check JSON call arguments
                json_call_args = mock_json.call_args
                assert json_call_args[0][0] == [pub]  # First arg is publications list
                assert json_call_args[0][1] == f"{output_path}.json"  # Second arg is filename
                
                # Check CSV exporter was created with correct arguments
                csv_init_args = mock_csv_class.call_args
                assert csv_init_args[0][0] == f"{output_path}.json"  # JSON input path
                assert csv_init_args[0][1] == f"{output_path}.csv"  # CSV output path
                assert csv_init_args[1]["single_file"] is True  # single_file parameter


class TestWorkerFunctions:
    """Test worker-related functions"""
    
    def test_process_batch(self, tmp_path):
        """Test process_batch function"""
        # Create test batch file
        batch_path = tmp_path / "test_batch.pkl"
        test_pubs = [
            Publication(
                title="Batch Test",
                pub_date="1960",
                source_id="001",
                country_code="xxu",
                country_classification=CountryClassification.US
            )
        ]
        
        with open(batch_path, "wb") as f:
            pickle.dump(test_pubs, f)
        
        # Create directories
        cache_dir = tmp_path / "cache"
        copyright_dir = tmp_path / "copyright"
        renewal_dir = tmp_path / "renewal"
        result_dir = tmp_path / "results"
        
        cache_dir.mkdir()
        copyright_dir.mkdir()
        renewal_dir.mkdir()
        result_dir.mkdir()
        
        # Create minimal data files
        copyright_file = copyright_dir / "test.xml"
        copyright_file.write_text("""<?xml version="1.0" encoding="UTF-8"?>
        <copyrightEntries></copyrightEntries>""")
        
        renewal_file = renewal_dir / "test.tsv"
        renewal_file.write_text("title\tauthor\toreg\todat\tid\trdat\tclaimants\n")
        
        # Create batch info as a tuple (BatchProcessingInfo is a tuple type)
        from marc_pd_tool.utils.types import BatchProcessingInfo
        batch_info = (
            1,  # batch_id
            str(batch_path),  # batch_path
            str(cache_dir),  # cache_dir
            str(copyright_dir),  # copyright_dir
            str(renewal_dir),  # renewal_dir
            "test_hash",  # config_hash
            {},  # detector_config
            1,  # total_batches
            40,  # title_threshold
            30,  # author_threshold
            20,  # publisher_threshold
            1,  # year_tolerance
            95,  # early_exit_title
            90,  # early_exit_author
            False,  # score_everything_mode
            None,  # minimum_combined_score
            False,  # brute_force_missing_year
            None,  # min_year
            None,  # max_year
            str(result_dir)  # result_temp_dir
        )
        
        # Mock the dependencies
        with patch('marc_pd_tool.processing.matching_engine.init_worker'):
            with patch('marc_pd_tool.processing.matching_engine._worker_data', {
                'cache_manager': Mock(),
                'registration_index': Mock(),
                'renewal_index': Mock(),
                'registration_matcher': Mock(find_best_match=Mock(return_value=(None, None))),
                'renewal_matcher': Mock(find_best_match=Mock(return_value=(None, None))),
                'generic_detector': Mock()
            }):
                from marc_pd_tool.utils.types import BatchStats
                batch_id, result_path, stats = process_batch(batch_info)
                
                assert batch_id == 1
                assert Path(result_path).exists()
                assert isinstance(stats, dict)
                # Verify stats has expected fields
                assert 'batch_id' in stats
                assert stats['batch_id'] == 1


class TestAnalysisMethods:
    """Test analysis methods"""
    
    def test_analyze_with_config_hash(self, tmp_path):
        """Test that config hash is properly computed and used"""
        analyzer = MarcCopyrightAnalyzer(cache_dir=str(tmp_path))
        
        # Create test publications
        publications = [
            Publication(
                title="Test Book",
                pub_date="1960",
                source_id="001",
                country_code="xxu",
                country_classification=CountryClassification.US
            )
        ]
        
        # Mock both _load_and_index_data and process_batch
        with patch.object(analyzer, '_load_and_index_data'):
            with patch('marc_pd_tool.api.process_batch') as mock_process:
                # Setup mock return
                def mock_process_batch(batch_info):
                    result_path = batch_info[-1] + "/result.pkl"
                    os.makedirs(os.path.dirname(result_path), exist_ok=True)
                    with open(result_path, 'wb') as f:
                        pickle.dump(publications, f)
                    stats = {
                        "batch_id": 1,
                        "marc_count": 1,
                        "registration_matches_found": 0,
                        "renewal_matches_found": 0,
                        "skipped_records": 0,
                        "processing_time": 0.1,
                        "records_with_errors": 0
                    }
                    return (1, result_path, stats)
                
                mock_process.side_effect = mock_process_batch
                
                # Analyze with specific config
                results = analyzer.analyze_marc_records(
                    publications,
                    options={"num_processes": 1, "title_threshold": 50}
                )
                
                # Verify config was used in batch_info
                batch_info = mock_process.call_args[0][0]
                assert batch_info[8] == 50  # title_threshold at index 8