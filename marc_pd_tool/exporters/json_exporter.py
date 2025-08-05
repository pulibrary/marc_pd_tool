# marc_pd_tool/exporters/json_exporter.py

"""JSON export functionality for publication match results with comprehensive data"""

# Standard library imports
from datetime import datetime
import gzip
import json
from typing import cast

# Local imports
from marc_pd_tool.data.publication import Publication
from marc_pd_tool.utils.types import JSONDict


def save_matches_json(
    marc_publications: list[Publication],
    json_file: str,
    pretty: bool = True,
    compress: bool = False,
    parameters: dict[str, str | int | float | bool] | None = None,
) -> None:
    """Save results to JSON file with comprehensive match data

    Args:
        marc_publications: List of publications to save
        json_file: Output filename
        pretty: If True, format JSON with indentation (default).
        compress: If True, use gzip compression.
        parameters: Processing parameters used (for metadata).
    """

    # Always create a single file with all records
    data = {
        "metadata": _create_metadata(marc_publications, parameters=parameters),
        "records": [_publication_to_comprehensive_dict(pub) for pub in marc_publications],
    }

    output_path = json_file if not compress else f"{json_file}.gz"
    if compress:
        with gzip.open(output_path, "wt", encoding="utf-8") as f:
            if pretty:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            else:
                json.dump(data, f, ensure_ascii=False, default=str)
    else:
        with open(output_path, "w", encoding="utf-8") as f:
            if pretty:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            else:
                json.dump(data, f, ensure_ascii=False, default=str)


def _create_metadata(
    publications: list[Publication], parameters: dict[str, str | int | float | bool] | None = None
) -> JSONDict:
    """Create enhanced metadata section for JSON output"""
    metadata = {
        "processing_date": datetime.now().isoformat(),
        "total_records": len(publications),
        "tool_version": "2.0.0",  # Updated for new reporting format
    }

    if parameters:
        metadata["parameters"] = parameters

    # Count by status
    status_counts: dict[str, int] = {}
    for pub in publications:
        s = pub.copyright_status
        status_counts[s] = status_counts.get(s, 0) + 1
    metadata["status_counts"] = status_counts

    # Count match types
    match_type_counts: dict[str, int] = {
        "lccn_matches": 0,
        "similarity_matches": 0,
        "no_matches": 0,
    }
    for pub in publications:
        if pub.registration_match or pub.renewal_match:
            if (pub.registration_match and pub.registration_match.match_type.value == "lccn") or (
                pub.renewal_match and pub.renewal_match.match_type.value == "lccn"
            ):
                match_type_counts["lccn_matches"] += 1
            else:
                match_type_counts["similarity_matches"] += 1
        else:
            match_type_counts["no_matches"] += 1
    metadata["match_type_counts"] = match_type_counts

    return cast(JSONDict, metadata)


def _publication_to_dict(pub: Publication) -> JSONDict:
    """Convert a Publication to a dictionary for JSON serialization"""
    data = {
        "marc_record": {
            "id": pub.source_id,
            "title": pub.original_title,
            "author_245c": pub.original_author,
            "author_1xx": pub.original_main_author,
            "year": pub.year,
            "publisher": pub.original_publisher,
            "place": pub.original_place,
            "edition": pub.original_edition,
            "lccn": pub.lccn,
            "normalized_lccn": pub.normalized_lccn,
            "language_code": pub.language_code,
            "language_detection_status": pub.language_detection_status,
            "country_code": pub.country_code,
            "country_classification": pub.country_classification.value,
        },
        "analysis": {
            "copyright_status": pub.copyright_status,
            "generic_title_detected": pub.generic_title_detected,
            "generic_detection_reason": pub.generic_detection_reason,
            "registration_generic_title": pub.registration_generic_title,
            "renewal_generic_title": pub.renewal_generic_title,
        },
    }

    # Add registration match if exists
    if pub.registration_match:
        data["registration_match"] = {
            "source_id": pub.registration_match.source_id,
            "title": pub.registration_match.matched_title,
            "author": pub.registration_match.matched_author,
            "publisher": pub.registration_match.matched_publisher,
            "date": pub.registration_match.matched_date,
            "scores": {
                "overall": pub.registration_match.similarity_score,
                "title": pub.registration_match.title_score,
                "author": pub.registration_match.author_score,
                "publisher": pub.registration_match.publisher_score,
            },
            "match_type": pub.registration_match.match_type.value,
        }

    # Add renewal match if exists
    if pub.renewal_match:
        data["renewal_match"] = {
            "source_id": pub.renewal_match.source_id,
            "title": pub.renewal_match.matched_title,
            "author": pub.renewal_match.matched_author,
            "publisher": pub.renewal_match.matched_publisher,
            "date": pub.renewal_match.matched_date,
            "scores": {
                "overall": pub.renewal_match.similarity_score,
                "title": pub.renewal_match.title_score,
                "author": pub.renewal_match.author_score,
                "publisher": pub.renewal_match.publisher_score,
            },
            "match_type": pub.renewal_match.match_type.value,
        }

    return cast(JSONDict, data)


def _publication_to_comprehensive_dict(pub: Publication) -> JSONDict:
    """Convert a Publication to comprehensive dictionary with all match details"""
    # MARC data with original and normalized versions
    marc_data = {
        "id": pub.source_id,
        "original": {
            "title": pub.original_title,
            "author_245c": pub.original_author,
            "author_1xx": pub.original_main_author,
            "publisher": pub.original_publisher,
            "place": pub.original_place,
            "edition": pub.original_edition,
            "year": pub.year,
            "lccn": pub.lccn,
        },
        "normalized": {
            "title": pub.title,
            "author": pub.author,
            "main_author": pub.main_author,
            "publisher": pub.publisher,
            "place": pub.place,
            "edition": pub.edition,
            "lccn": pub.normalized_lccn,
        },
        "metadata": {
            "language_code": pub.language_code,
            "language_detection_status": pub.language_detection_status,
            "country_code": pub.country_code,
            "country_classification": pub.country_classification.value,
        },
    }

    # Match data with detailed quality indicators
    matches = {}

    if pub.registration_match:
        rm = pub.registration_match
        matches["registration"] = {
            "found": True,
            "id": rm.source_id,
            "original": {
                "title": rm.matched_title,
                "author": rm.matched_author,
                "publisher": rm.matched_publisher,
                "date": rm.matched_date,
            },
            "normalized": {
                "title": rm.normalized_title,
                "author": rm.normalized_author,
                "publisher": rm.normalized_publisher,
            },
            "scores": {
                "overall": rm.similarity_score,
                "title": rm.title_score,
                "author": rm.author_score,
                "publisher": rm.publisher_score,
            },
            "year_difference": rm.year_difference,
            "match_type": rm.match_type.value,
        }
    else:
        matches["registration"] = {"found": False}

    if pub.renewal_match:
        ren = pub.renewal_match
        matches["renewal"] = {
            "found": True,
            "id": ren.source_id,
            "original": {
                "title": ren.matched_title,
                "author": ren.matched_author,
                "publisher": ren.matched_publisher,
                "date": ren.matched_date,
            },
            "normalized": {
                "title": ren.normalized_title,
                "author": ren.normalized_author,
                "publisher": ren.normalized_publisher,
            },
            "scores": {
                "overall": ren.similarity_score,
                "title": ren.title_score,
                "author": ren.author_score,
                "publisher": ren.publisher_score,
            },
            "year_difference": ren.year_difference,
            "match_type": ren.match_type.value,
        }
    else:
        matches["renewal"] = {"found": False}

    # Analysis results
    analysis = {
        "status": pub.copyright_status,
        "status_rule": pub.status_rule.value if pub.status_rule else "",
        "sort_score": pub.sort_score,
        "data_completeness": pub.data_completeness,
        "generic_title": {
            "detected": pub.generic_title_detected,
            "reason": pub.generic_detection_reason,
            "in_registration": pub.registration_generic_title,
            "in_renewal": pub.renewal_generic_title,
        },
    }

    return cast(JSONDict, {"marc": marc_data, "matches": matches, "analysis": analysis})
