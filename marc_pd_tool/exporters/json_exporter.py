# marc_pd_tool/exporters/json_exporter.py

"""JSON export functionality for publication match results"""

# Standard library imports
from datetime import datetime
import json
from pathlib import Path
from typing import cast

# Local imports
from marc_pd_tool.data.publication import Publication
from marc_pd_tool.utils.types import JSONDict


def save_matches_json(
    marc_publications: list[Publication],
    json_file: str,
    single_file: bool = False,
    pretty: bool = True,
) -> None:
    """Save results to JSON file(s) with copyright status information

    Args:
        marc_publications: List of publications to save
        json_file: Base output filename
        single_file: If True, save all records to a single file.
                    If False, create separate files by copyright status (default).
        pretty: If True, format JSON with indentation (default).
    """

    if single_file:
        # Single file mode: all records in one file
        data = {
            "metadata": _create_metadata(marc_publications),
            "publications": [_publication_to_dict(pub) for pub in marc_publications],
        }

        with open(json_file, "w", encoding="utf-8") as f:
            if pretty:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            else:
                json.dump(data, f, ensure_ascii=False, default=str)
    else:
        # Multiple files: separate files by copyright status
        # Group publications by copyright status
        status_groups: dict[str, list[Publication]] = {}
        for pub in marc_publications:
            status = pub.copyright_status.value
            if status not in status_groups:
                status_groups[status] = []
            status_groups[status].append(pub)

        # Get base filename without extension
        path = Path(json_file)
        base_name = path.stem
        ext = path.suffix or ".json"
        parent = path.parent

        # Create separate file for each status
        for status, publications in status_groups.items():
            # Convert status to lowercase filename format
            status_filename = status.lower()
            output_file = parent / f"{base_name}_{status_filename}{ext}"

            data = {
                "metadata": _create_metadata(publications, status),
                "publications": [_publication_to_dict(pub) for pub in publications],
            }

            with open(output_file, "w", encoding="utf-8") as f:
                if pretty:
                    json.dump(data, f, indent=2, ensure_ascii=False, default=str)
                else:
                    json.dump(data, f, ensure_ascii=False, default=str)


def _create_metadata(publications: list[Publication], status: str | None = None) -> JSONDict:
    """Create metadata section for JSON output"""
    metadata = {
        "export_date": datetime.now().isoformat(),
        "total_records": len(publications),
        "tool_version": "1.1.0",  # Could be made dynamic
    }

    if status:
        metadata["copyright_status"] = status
    else:
        # Count by status
        status_counts: dict[str, int] = {}
        for pub in publications:
            s = pub.copyright_status.value
            status_counts[s] = status_counts.get(s, 0) + 1
        metadata["status_counts"] = status_counts

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
            "copyright_status": pub.copyright_status.value,
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
            "match_type": pub.registration_match.match_type,
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
            "match_type": pub.renewal_match.match_type,
        }

    return cast(JSONDict, data)
