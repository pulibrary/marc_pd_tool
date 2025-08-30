# tests/adapters/cli/test_copyright_status_categorization.py

"""Tests for copyright status categorization in CLI summary"""

pass

# Local imports
from marc_pd_tool.application.models.analysis_results import AnalysisStatistics


def test_copyright_status_categorization():
    """Test that copyright statuses are properly categorized into PD, Not PD, and Undetermined"""

    # Create statistics with various copyright statuses
    stats = AnalysisStatistics()

    # Add some regular fields
    stats.total_records = 1000
    stats.registration_matches = 400
    stats.renewal_matches = 200

    # Add copyright status counts to extra_fields
    # Public Domain statuses
    stats.extra_fields["us_registered_not_renewed"] = 150
    stats.extra_fields["us_pre_1929"] = 50
    stats.extra_fields["foreign_pre_1929_gbr"] = 10

    # Not Public Domain statuses
    stats.extra_fields["us_renewed"] = 100
    stats.extra_fields["foreign_renewed_fra"] = 20
    stats.extra_fields["in_copyright"] = 30

    # Undetermined statuses
    stats.extra_fields["us_no_match"] = 400
    stats.extra_fields["country_unknown_no_match"] = 50
    stats.extra_fields["foreign_no_match_deu"] = 40
    stats.extra_fields["out_of_data_range_1992"] = 10

    # Convert to dict
    stats_dict = stats.to_dict()

    # Now simulate the categorization logic from main.py
    pd_records = 0
    not_pd_records = 0
    undetermined_records = 0

    for key, value in stats_dict.items():
        key_lower = key.lower()

        # Skip non-copyright status fields
        if key in [
            "total_records",
            "us_records",
            "non_us_records",
            "unknown_country",
            "registration_matches",
            "renewal_matches",
            "no_matches",
            "skipped_no_year",
        ]:
            continue

        # Public Domain statuses
        if any(
            pd_status in key_lower
            for pd_status in [
                "us_registered_not_renewed",
                "us_pre_",
                "foreign_pre_",
                "pd_pre",
                "pd_us",
                "research_us_only_pd",
            ]
        ):
            pd_records += int(value)
        # Not Public Domain statuses
        elif any(
            not_pd_status in key_lower
            for not_pd_status in ["us_renewed", "foreign_renewed", "in_copyright"]
        ):
            not_pd_records += int(value)
        # Undetermined statuses
        elif any(
            unknown_status in key_lower
            for unknown_status in [
                "us_no_match",
                "unknown",
                "country_unknown",
                "research_us_status",
                "foreign_registered_not_renewed",
                "foreign_no_match",
                "out_of_data_range",
            ]
        ):
            undetermined_records += int(value)

    # Verify categorization
    assert pd_records == 210  # 150 + 50 + 10
    assert not_pd_records == 150  # 100 + 20 + 30
    assert undetermined_records == 500  # 400 + 50 + 40 + 10

    # Verify total adds up
    assert pd_records + not_pd_records + undetermined_records == 860


def test_empty_copyright_statuses():
    """Test handling when there are no copyright status counts"""

    stats = AnalysisStatistics()
    stats.total_records = 100
    stats_dict = stats.to_dict()

    pd_records = 0
    not_pd_records = 0
    undetermined_records = 0

    for key, value in stats_dict.items():
        key_lower = key.lower()

        if key in [
            "total_records",
            "us_records",
            "non_us_records",
            "unknown_country",
            "registration_matches",
            "renewal_matches",
            "no_matches",
            "skipped_no_year",
        ]:
            continue

        if any(
            pd_status in key_lower
            for pd_status in [
                "us_registered_not_renewed",
                "us_pre_",
                "foreign_pre_",
                "pd_pre",
                "pd_us",
                "research_us_only_pd",
            ]
        ):
            pd_records += int(value)
        elif any(
            not_pd_status in key_lower
            for not_pd_status in ["us_renewed", "foreign_renewed", "in_copyright"]
        ):
            not_pd_records += int(value)
        elif any(
            unknown_status in key_lower
            for unknown_status in [
                "us_no_match",
                "unknown",
                "country_unknown",
                "research_us_status",
                "foreign_registered_not_renewed",
                "foreign_no_match",
                "out_of_data_range",
            ]
        ):
            undetermined_records += int(value)

    assert pd_records == 0
    assert not_pd_records == 0
    assert undetermined_records == 0


def test_mixed_case_status_keys():
    """Test that categorization works regardless of case"""

    stats = AnalysisStatistics()

    # Add statuses with different cases (though they should be lowercase in practice)
    stats.extra_fields["US_RENEWED"] = 50  # Should still be caught
    stats.extra_fields["Us_Registered_Not_Renewed"] = 30
    stats.extra_fields["us_no_match"] = 20

    stats_dict = stats.to_dict()

    pd_records = 0
    not_pd_records = 0
    undetermined_records = 0

    for key, value in stats_dict.items():
        key_lower = key.lower()

        if key in [
            "total_records",
            "us_records",
            "non_us_records",
            "unknown_country",
            "registration_matches",
            "renewal_matches",
            "no_matches",
            "skipped_no_year",
        ]:
            continue

        if any(
            pd_status in key_lower
            for pd_status in [
                "us_registered_not_renewed",
                "us_pre_",
                "foreign_pre_",
                "pd_pre",
                "pd_us",
                "research_us_only_pd",
            ]
        ):
            pd_records += int(value)
        elif any(
            not_pd_status in key_lower
            for not_pd_status in ["us_renewed", "foreign_renewed", "in_copyright"]
        ):
            not_pd_records += int(value)
        elif any(
            unknown_status in key_lower
            for unknown_status in [
                "us_no_match",
                "unknown",
                "country_unknown",
                "research_us_status",
                "foreign_registered_not_renewed",
                "foreign_no_match",
                "out_of_data_range",
            ]
        ):
            undetermined_records += int(value)

    # All should be categorized correctly based on lowercase comparison
    assert pd_records == 30  # Us_Registered_Not_Renewed
    assert not_pd_records == 50  # US_RENEWED
    assert undetermined_records == 20  # us_no_match


def test_edge_case_statuses():
    """Test edge cases like statuses with country codes"""

    stats = AnalysisStatistics()

    # Various foreign statuses with country codes
    stats.extra_fields["foreign_renewed_gbr"] = 10
    stats.extra_fields["foreign_renewed_fra"] = 15
    stats.extra_fields["foreign_no_match_deu"] = 20
    stats.extra_fields["foreign_no_match_jpn"] = 25
    stats.extra_fields["foreign_registered_not_renewed_ita"] = 30
    stats.extra_fields["foreign_pre_1929_esp"] = 35

    # Out of data range with years
    stats.extra_fields["out_of_data_range_1992"] = 5
    stats.extra_fields["out_of_data_range_1993"] = 7

    stats_dict = stats.to_dict()

    pd_records = 0
    not_pd_records = 0
    undetermined_records = 0

    for key, value in stats_dict.items():
        key_lower = key.lower()

        if key in [
            "total_records",
            "us_records",
            "non_us_records",
            "unknown_country",
            "registration_matches",
            "renewal_matches",
            "no_matches",
            "skipped_no_year",
        ]:
            continue

        if any(
            pd_status in key_lower
            for pd_status in [
                "us_registered_not_renewed",
                "us_pre_",
                "foreign_pre_",
                "pd_pre",
                "pd_us",
                "research_us_only_pd",
            ]
        ):
            pd_records += int(value)
        elif any(
            not_pd_status in key_lower
            for not_pd_status in ["us_renewed", "foreign_renewed", "in_copyright"]
        ):
            not_pd_records += int(value)
        elif any(
            unknown_status in key_lower
            for unknown_status in [
                "us_no_match",
                "unknown",
                "country_unknown",
                "research_us_status",
                "foreign_registered_not_renewed",
                "foreign_no_match",
                "out_of_data_range",
            ]
        ):
            undetermined_records += int(value)

    assert pd_records == 35  # foreign_pre_1929_esp
    assert not_pd_records == 25  # foreign_renewed_gbr + foreign_renewed_fra
    assert (
        undetermined_records == 87
    )  # foreign_no_match + foreign_registered_not_renewed + out_of_data_range
