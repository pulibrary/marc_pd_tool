# tests/test_api/test_analysis_results.py

"""Tests for AnalysisResults class in the API module"""

# Standard library imports

# Third party imports

# Local imports
from marc_pd_tool.api import AnalysisResults
from marc_pd_tool.data.enums import CopyrightStatus
from marc_pd_tool.data.enums import CountryClassification
from marc_pd_tool.data.ground_truth import GroundTruthAnalysis
from marc_pd_tool.data.ground_truth import GroundTruthPair
from tests.fixtures.publications import PublicationBuilder


class TestAnalysisResults:
    """Test the AnalysisResults container class"""

    def test_init_empty_results(self):
        """Test initialization creates proper empty state"""
        results = AnalysisResults()

        assert results.publications == []
        assert results.result_file_paths == []
        assert results.ground_truth_analysis is None
        assert results.ground_truth_pairs is None
        assert results.ground_truth_stats is None
        assert results.result_temp_dir is None

        # Check statistics are initialized
        assert results.statistics["total_records"] == 0
        assert results.statistics["us_records"] == 0
        assert results.statistics["non_us_records"] == 0
        assert results.statistics["unknown_country"] == 0
        assert results.statistics["registration_matches"] == 0
        assert results.statistics["renewal_matches"] == 0
        assert results.statistics["no_matches"] == 0
        assert results.statistics["pd_us_not_renewed"] == 0
        assert results.statistics["pd_pre_min_year"] == 0
        assert results.statistics["in_copyright"] == 0
        assert results.statistics["research_us_status"] == 0
        assert results.statistics["research_us_only_pd"] == 0
        assert results.statistics["country_unknown"] == 0

    def test_add_publication_updates_statistics(self):
        """Test that adding publications correctly updates statistics"""
        results = AnalysisResults()

        # US publication with registration match
        pub1 = PublicationBuilder.basic_us_publication()
        pub1 = PublicationBuilder.with_registration_match(pub1)
        pub1.copyright_status = CopyrightStatus.PD_US_NOT_RENEWED
        results.add_publication(pub1)

        assert len(results.publications) == 1
        assert results.statistics["total_records"] == 1
        assert results.statistics["us_records"] == 1
        assert results.statistics["registration_matches"] == 1
        assert results.statistics["pd_us_not_renewed"] == 1

        # Non-US publication with renewal match
        pub2 = PublicationBuilder.basic_us_publication(
            country_code="xxk", country_classification=CountryClassification.NON_US
        )
        pub2 = PublicationBuilder.with_renewal_match(pub2)
        pub2.copyright_status = CopyrightStatus.IN_COPYRIGHT
        results.add_publication(pub2)

        assert len(results.publications) == 2
        assert results.statistics["total_records"] == 2
        assert results.statistics["non_us_records"] == 1
        assert results.statistics["renewal_matches"] == 1
        assert results.statistics["in_copyright"] == 1

        # Publication with no matches
        pub3 = PublicationBuilder.basic_us_publication()
        pub3.copyright_status = CopyrightStatus.RESEARCH_US_STATUS
        results.add_publication(pub3)

        assert len(results.publications) == 3
        assert results.statistics["total_records"] == 3
        assert results.statistics["no_matches"] == 1
        assert results.statistics["research_us_status"] == 1

    def test_add_result_file_tracking(self):
        """Test that result file paths are tracked correctly"""
        results = AnalysisResults()

        # Add some file paths
        results.add_result_file("/tmp/batch1.pkl")
        results.add_result_file("/tmp/batch2.pkl")
        results.add_result_file("/tmp/batch3.pkl")

        assert len(results.result_file_paths) == 3
        assert "/tmp/batch1.pkl" in results.result_file_paths
        assert "/tmp/batch2.pkl" in results.result_file_paths
        assert "/tmp/batch3.pkl" in results.result_file_paths

    def test_update_statistics_from_batch(self):
        """Test updating statistics without storing publications"""
        results = AnalysisResults()

        # Create a batch of publications
        batch = []
        for i in range(5):
            pub = PublicationBuilder.basic_us_publication(source_id=f"test-{i}")
            if i % 2 == 0:
                pub = PublicationBuilder.with_registration_match(pub)
                pub.copyright_status = CopyrightStatus.PD_US_NOT_RENEWED
            else:
                pub.copyright_status = CopyrightStatus.RESEARCH_US_STATUS
            batch.append(pub)

        # Update statistics from batch
        results.update_statistics_from_batch(batch)

        # Publications should not be stored
        assert len(results.publications) == 0

        # But statistics should be updated
        assert results.statistics["total_records"] == 5
        assert results.statistics["us_records"] == 5
        assert results.statistics["registration_matches"] == 3
        assert results.statistics["pd_us_not_renewed"] == 3
        assert results.statistics["research_us_status"] == 2

    def test_statistics_for_all_statuses(self):
        """Test that all copyright statuses are tracked correctly"""
        results = AnalysisResults()

        # Test each copyright status
        statuses = [
            CopyrightStatus.PD_US_NOT_RENEWED,
            CopyrightStatus.PD_PRE_MIN_YEAR,
            CopyrightStatus.IN_COPYRIGHT,
            CopyrightStatus.RESEARCH_US_STATUS,
            CopyrightStatus.RESEARCH_US_ONLY_PD,
            CopyrightStatus.COUNTRY_UNKNOWN,
        ]

        for i, status in enumerate(statuses):
            pub = PublicationBuilder.basic_us_publication(source_id=f"test-{i}")
            pub.copyright_status = status
            results.add_publication(pub)

        # Check all status counters
        assert results.statistics["pd_us_not_renewed"] == 1
        assert results.statistics["pd_pre_min_year"] == 1
        assert results.statistics["in_copyright"] == 1
        assert results.statistics["research_us_status"] == 1
        assert results.statistics["research_us_only_pd"] == 1
        assert results.statistics["country_unknown"] == 1

    def test_country_classification_tracking(self):
        """Test that country classifications are tracked correctly"""
        results = AnalysisResults()

        # US publication
        pub1 = PublicationBuilder.basic_us_publication()
        results.add_publication(pub1)

        # Non-US publication
        pub2 = PublicationBuilder.basic_us_publication(
            country_code="xxk", country_classification=CountryClassification.NON_US
        )
        results.add_publication(pub2)

        # Unknown country publication
        pub3 = PublicationBuilder.basic_us_publication(
            country_code="xxx", country_classification=CountryClassification.UNKNOWN
        )
        results.add_publication(pub3)

        assert results.statistics["us_records"] == 1
        assert results.statistics["non_us_records"] == 1
        assert results.statistics["unknown_country"] == 1

    def test_match_tracking(self):
        """Test that matches are tracked independently of status"""
        results = AnalysisResults()

        # Registration match only
        pub1 = PublicationBuilder.basic_us_publication()
        pub1 = PublicationBuilder.with_registration_match(pub1)
        results.add_publication(pub1)

        # Renewal match only
        pub2 = PublicationBuilder.basic_us_publication()
        pub2 = PublicationBuilder.with_renewal_match(pub2)
        results.add_publication(pub2)

        # Both matches
        pub3 = PublicationBuilder.basic_us_publication()
        pub3 = PublicationBuilder.with_registration_match(pub3)
        pub3 = PublicationBuilder.with_renewal_match(pub3)
        results.add_publication(pub3)

        # No matches
        pub4 = PublicationBuilder.basic_us_publication()
        results.add_publication(pub4)

        assert results.statistics["registration_matches"] == 2
        assert results.statistics["renewal_matches"] == 2
        assert results.statistics["no_matches"] == 1  # Only pub4 has no matches at all

    def test_ground_truth_storage(self):
        """Test storage of ground truth analysis results"""
        results = AnalysisResults()

        # Create mock ground truth data
        # Local imports
        from marc_pd_tool.data.ground_truth import ScoreDistribution

        gt_analysis = GroundTruthAnalysis(
            total_pairs=10,
            registration_pairs=6,
            renewal_pairs=4,
            title_distribution=ScoreDistribution("title", [90.0, 95.0, 85.0]),
            author_distribution=ScoreDistribution("author", [85.0, 90.0, 80.0]),
            publisher_distribution=ScoreDistribution("publisher", [70.0, 75.0, 65.0]),
            combined_distribution=ScoreDistribution("combined", [85.0, 90.0, 80.0]),
            pairs_by_match_type={"registration": [], "renewal": []},
        )

        # Create proper GroundTruthPair
        marc_pub = PublicationBuilder.basic_us_publication()
        marc_pub.normalized_lccn = "12345678"
        copyright_pub = PublicationBuilder.basic_us_publication()
        copyright_pub.normalized_lccn = "12345678"

        gt_pairs = [
            GroundTruthPair(
                marc_record=marc_pub,
                copyright_record=copyright_pub,
                match_type="registration",
                lccn="12345678",
            )
        ]

        # Store ground truth data
        results.ground_truth_analysis = gt_analysis
        results.ground_truth_pairs = gt_pairs

        assert results.ground_truth_analysis.total_pairs == 10
        assert results.ground_truth_analysis.registration_pairs == 6
        assert results.ground_truth_analysis.renewal_pairs == 4
        assert len(results.ground_truth_pairs) == 1

    def test_result_temp_dir_tracking(self):
        """Test tracking of temporary directory for results"""
        results = AnalysisResults()

        # Set temp dir
        results.result_temp_dir = "/tmp/marc_results_12345"

        assert results.result_temp_dir == "/tmp/marc_results_12345"
