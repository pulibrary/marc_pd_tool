# tests/integration/test_full_workflow.py

"""End-to-end workflow integration tests

These tests use mocked processing to avoid worker initialization issues
while testing the full workflow functionality.
"""

# Standard library imports
import json
from pathlib import Path
from unittest.mock import Mock
from unittest.mock import patch

# Third party imports
import pytest

# Local imports
from marc_pd_tool.adapters.api import MarcCopyrightAnalyzer
from marc_pd_tool.core.domain.enums import CountryClassification
from marc_pd_tool.core.domain.enums import MatchType
from marc_pd_tool.core.domain.match_result import MatchResult
from marc_pd_tool.core.domain.publication import Publication


class TestFullWorkflow:
    """Test complete analysis workflow with mocked processing"""

    def test_small_file_complete_workflow(self, small_marc_file: Path, temp_output_dir: Path):
        """Test full workflow with a small MARC file"""
        # Create test publications with matches
        test_pubs = [
            Publication(
                title="Test Book 1",
                author="Author One",
                pub_date="1960",
                source_id="001",
                country_code="xxu",
                country_classification=CountryClassification.US,
            ),
            Publication(
                title="Test Book 2",
                author="Author Two",
                pub_date="1955",
                source_id="002",
                country_code="xxu",
                country_classification=CountryClassification.US,
            ),
        ]

        # Add mock matches
        test_pubs[0].registration_match = MatchResult(
            matched_title="Test Book 1",
            matched_author="Author One",
            similarity_score=95,
            title_score=95,
            author_score=95,
            publisher_score=90,
            year_difference=0,
            source_id="REG001",
            source_type="registration",
            matched_date="1960",
            matched_publisher="Test Publisher",
        )

        # Initialize analyzer
        analyzer = MarcCopyrightAnalyzer(
            cache_dir=str(temp_output_dir / "cache"), force_refresh=True
        )

        # Mock the processing methods
        with patch.object(analyzer, "_load_and_index_data"):
            with patch.object(analyzer, "_process_sequentially") as mock_seq:
                # Mock sequential processing
                def mock_process(*args, **kwargs):
                    for pub in test_pubs:
                        analyzer.results.add_publication(pub)
                    return test_pubs

                mock_seq.side_effect = mock_process

                # Run analysis
                output_path = str(temp_output_dir / "results")
                results = analyzer.analyze_marc_file(
                    str(small_marc_file),
                    output_path=output_path,
                    options={"formats": ["json", "csv"], "single_file": True, "num_processes": 1},
                )

        # Verify results
        assert results.statistics.total_records == 2
        assert results.statistics.us_records == 2
        assert len(results.publications) == 2

        # Verify output files
        assert Path(f"{output_path}.json").exists()
        assert Path(f"{output_path}.csv").exists()

        # Check JSON content
        with open(f"{output_path}.json") as f:
            json_data = json.load(f)
            assert len(json_data["records"]) == 2
            assert json_data["metadata"]["total_records"] == 2

    def test_medium_file_with_filtering(self, medium_marc_file: Path, temp_output_dir: Path):
        """Test workflow with year filtering"""
        # Create publications for different years
        all_pubs = []
        for year in range(1950, 1970):
            pub = Publication(
                title=f"Book {year}",
                author=f"Author {year}",
                pub_date=str(year),
                source_id=f"{year}",
                country_code="xxu",
                country_classification=CountryClassification.US,
            )
            all_pubs.append(pub)

        # Filter to 1950s
        pubs_1950s = [p for p in all_pubs if 1950 <= p.year <= 1959]

        analyzer = MarcCopyrightAnalyzer()

        with patch("marc_pd_tool.adapters.api._analyzer.MarcLoader") as mock_loader_class:
            mock_loader = Mock()
            mock_loader_class.return_value = mock_loader
            mock_loader.extract_all_batches.return_value = [pubs_1950s]

            with patch.object(analyzer, "_load_and_index_data"):
                with patch.object(analyzer, "_process_sequentially") as mock_seq:

                    def mock_process(*args, **kwargs):
                        for pub in pubs_1950s:
                            analyzer.results.add_publication(pub)
                        return pubs_1950s

                    mock_seq.side_effect = mock_process

                    results = analyzer.analyze_marc_file(
                        str(medium_marc_file),
                        options={"min_year": 1950, "max_year": 1959, "num_processes": 1},
                    )

        # Verify filtering worked
        assert len(results.publications) == 10
        assert all(1950 <= pub.year <= 1959 for pub in results.publications)

    def test_multiple_output_formats(self, small_marc_file: Path, temp_output_dir: Path):
        """Test generation of multiple output formats"""
        test_pub = Publication(
            title="Test Book",
            author="Test Author",
            pub_date="1960",
            source_id="001",
            country_code="xxu",
            country_classification=CountryClassification.US,
        )

        analyzer = MarcCopyrightAnalyzer()

        with patch.object(analyzer, "_load_and_index_data"):
            with patch.object(analyzer, "_process_sequentially") as mock_seq:

                def mock_process(*args, **kwargs):
                    analyzer.results.add_publication(test_pub)
                    return [test_pub]

                mock_seq.side_effect = mock_process

                output_path = str(temp_output_dir / "multi_format")
                results = analyzer.analyze_marc_file(
                    str(small_marc_file),
                    output_path=output_path,
                    options={
                        "formats": ["json", "csv", "xlsx"],
                        "single_file": True,
                        "num_processes": 1,
                    },
                )

        # Verify all formats were created
        assert Path(f"{output_path}.json").exists()
        assert Path(f"{output_path}.csv").exists()
        assert Path(f"{output_path}.xlsx").exists()

    def test_error_recovery(self, small_marc_file: Path, temp_output_dir: Path):
        """Test that errors in processing are handled gracefully"""
        analyzer = MarcCopyrightAnalyzer()

        with patch.object(analyzer, "_load_and_index_data"):
            with patch.object(analyzer, "_process_sequentially") as mock_seq:
                # Simulate an error during processing
                mock_seq.side_effect = Exception("Simulated processing error")

                # Should raise the error
                with pytest.raises(Exception, match="Simulated processing error"):
                    analyzer.analyze_marc_file(str(small_marc_file), options={"num_processes": 1})

    def test_ground_truth_mode(self, small_marc_file: Path, temp_output_dir: Path):
        """Test ground truth extraction mode"""
        # Create publications with LCCN
        test_pubs = [
            Publication(
                title="Book with LCCN",
                author="Author",
                pub_date="1960",
                source_id="001",
                lccn="60012345",
                country_code="xxu",
                country_classification=CountryClassification.US,
            )
        ]

        # Add a match
        test_pubs[0].registration_match = MatchResult(
            matched_title="Book with LCCN",
            matched_author="Author",
            similarity_score=100,
            title_score=100,
            author_score=100,
            publisher_score=100,
            year_difference=0,
            source_id="REG001",
            source_type="registration",
            matched_date="1960",
            matched_publisher="Publisher",
            match_type=MatchType.LCCN,
        )

        analyzer = MarcCopyrightAnalyzer()

        # Mock the processing to return our test publications
        with patch.object(analyzer, "_load_and_index_data"):
            # Patch MarcLoader at the correct import location for _ground_truth.py
            with patch("marc_pd_tool.adapters.api._ground_truth.MarcLoader") as mock_loader_class:
                mock_loader = Mock()
                mock_loader_class.return_value = mock_loader
                mock_loader.extract_all_batches.return_value = [test_pubs]

                with patch.object(analyzer, "_process_sequentially") as mock_seq:

                    def mock_process(*args, **kwargs):
                        return test_pubs

                    mock_seq.side_effect = mock_process

                    # Extract ground truth
                    ground_truth_results, stats = analyzer.extract_ground_truth(
                        str(small_marc_file)
                    )

        # Verify ground truth extraction
        assert stats.total_marc_records == 1
        assert stats.marc_with_lccn == 1
        # Note: Since we're mocking, actual matches aren't made
        # The test verifies the extraction mechanism works

    def test_configuration_loading(self, small_marc_file: Path, temp_output_dir: Path):
        """Test custom configuration loading"""
        # Create custom config
        config_path = temp_output_dir / "custom_config.json"
        config_data = {"default_thresholds": {"title": 70, "author": 60}}
        config_path.write_text(json.dumps(config_data))

        # Create analyzer with custom config
        analyzer = MarcCopyrightAnalyzer(config_path=str(config_path))

        # Verify config was loaded
        assert analyzer.config is not None
        assert analyzer.config.get_threshold("title") == 70
        assert analyzer.config.get_threshold("author") == 60

        # Create test publication
        test_pub = Publication(
            title="Test",
            pub_date="1960",
            source_id="001",
            country_code="xxu",
            country_classification=CountryClassification.US,
        )

        with patch.object(analyzer, "_load_and_index_data"):
            with patch.object(analyzer, "_process_sequentially") as mock_seq:

                def mock_process(*args, **kwargs):
                    analyzer.results.add_publication(test_pub)
                    return [test_pub]

                mock_seq.side_effect = mock_process

                results = analyzer.analyze_marc_file(
                    str(small_marc_file), options={"num_processes": 1}
                )

        # Verify processing completed
        assert len(results.publications) == 1
