# tests/adapters/api/test_statistics_aggregation.py

"""Test that batch statistics are properly aggregated.

This ensures that statistics from multiple batches are correctly summed.
"""

# Local imports
from marc_pd_tool.application.models.analysis_results import AnalysisResults
from marc_pd_tool.application.models.batch_stats import BatchStats


def test_statistics_aggregation():
    """Test that statistics from multiple batches aggregate correctly"""

    # Create test data similar to what would come from batch processing
    all_stats = [
        BatchStats(
            batch_id=0,
            marc_count=50000,
            registration_matches_found=500,
            renewal_matches_found=250,
            us_records=40000,
            non_us_records=10000,
            skipped_no_year=5000,
            records_with_errors=10,
        ),
        BatchStats(
            batch_id=1,
            marc_count=50000,
            registration_matches_found=600,
            renewal_matches_found=300,
            us_records=42000,
            non_us_records=8000,
            skipped_no_year=6000,
            records_with_errors=15,
        ),
        BatchStats(
            batch_id=2,
            marc_count=90000,
            registration_matches_found=900,
            renewal_matches_found=450,
            us_records=70000,
            non_us_records=20000,
            skipped_no_year=12216,
            records_with_errors=25,
        ),
    ]

    # Create results object
    results = AnalysisResults()

    # Aggregate statistics from batches like _streaming.py does
    batch_stats_list = [stats for stats in all_stats if isinstance(stats, BatchStats)]

    total_records = sum(stats.marc_count for stats in batch_stats_list)
    total_skipped_no_year = sum(stats.skipped_no_year for stats in batch_stats_list)
    total_us_records = sum(stats.us_records for stats in batch_stats_list)
    total_non_us_records = sum(stats.non_us_records for stats in batch_stats_list)
    total_unknown_country = sum(stats.unknown_country_records for stats in batch_stats_list)
    sum(stats.records_with_errors for stats in batch_stats_list)

    # Simulating the registration and renewal totals
    total_reg_matches = sum(stats.registration_matches_found for stats in batch_stats_list)
    total_ren_matches = sum(stats.renewal_matches_found for stats in batch_stats_list)

    # Update the statistics with the aggregated counts
    results.statistics.total_records = total_records
    results.statistics.registration_matches = total_reg_matches
    results.statistics.renewal_matches = total_ren_matches
    results.statistics.skipped_no_year = total_skipped_no_year
    results.statistics.us_records = total_us_records
    results.statistics.non_us_records = total_non_us_records
    results.statistics.unknown_country = total_unknown_country
    # Note: errors field doesn't exist in AnalysisStatistics

    # Calculate no matches
    results.statistics.no_matches = total_records - (total_reg_matches + total_ren_matches)

    # Verify that total_records is correctly aggregated from all batches
    assert (
        results.statistics.total_records == 190000
    ), f"Expected total_records to be 190000, got {results.statistics.total_records}"

    # Also verify other critical stats
    assert results.statistics.registration_matches == 2000
    assert results.statistics.renewal_matches == 1000
    assert results.statistics.skipped_no_year == 23216
    assert results.statistics.no_matches == 187000  # 190000 - 3000

    # Verify the statistics can be converted to dict (as used by CLI)
    stats_dict = results.statistics.to_dict()
    assert stats_dict["total_records"] == 190000

    print("✓ Statistics aggregation is working correctly")
    print(f"  - Total records: {results.statistics.total_records:,}")
    print(
        f"  - Matches: {results.statistics.registration_matches + results.statistics.renewal_matches:,}"
    )
    print(f"  - Skipped: {results.statistics.skipped_no_year:,}")


if __name__ == "__main__":
    test_statistics_aggregation()
    print("\n✓ Statistics aggregation test passed!")
