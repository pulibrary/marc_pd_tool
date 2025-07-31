# marc_pd_tool/exporters/csv_exporter.py

"""CSV export functionality for publication match results"""

# Standard library imports
from csv import writer
from os.path import splitext

# Local imports
from marc_pd_tool.data.enums import MatchType
from marc_pd_tool.data.publication import Publication
from marc_pd_tool.utils.types import CSVWriter


def _calculate_confidence(pub: Publication) -> str:
    """Calculate confidence level based on match scores and type

    Returns:
        HIGH, MEDIUM, LOW, or WARNING
    """
    # If we have an LCCN match, it's always HIGH confidence
    if pub.registration_match and pub.registration_match.match_type == MatchType.LCCN:
        return "HIGH"
    if pub.renewal_match and pub.renewal_match.match_type == MatchType.LCCN:
        return "HIGH"

    # Calculate best combined score
    best_score = 0.0
    if pub.registration_match:
        best_score = max(best_score, pub.registration_match.similarity_score)
    if pub.renewal_match:
        best_score = max(best_score, pub.renewal_match.similarity_score)

    # Apply confidence thresholds
    if best_score >= 85:
        return "HIGH"
    elif best_score >= 60:
        return "MEDIUM"
    elif best_score > 0:
        return "LOW"
    else:
        return "WARNING"


def _format_match_summary(pub: Publication) -> str:
    """Format a concise match summary

    Returns:
        String like "Reg: 95%, Ren: None" or "Reg: LCCN, Ren: 82%"
    """
    parts = []

    if pub.registration_match:
        if pub.registration_match.match_type == MatchType.LCCN:
            parts.append("Reg: LCCN")
        else:
            parts.append(f"Reg: {pub.registration_match.similarity_score:.0f}%")
    else:
        parts.append("Reg: None")

    if pub.renewal_match:
        if pub.renewal_match.match_type == MatchType.LCCN:
            parts.append("Ren: LCCN")
        else:
            parts.append(f"Ren: {pub.renewal_match.similarity_score:.0f}%")
    else:
        parts.append("Ren: None")

    return ", ".join(parts)


def _get_warnings(pub: Publication) -> str:
    """Get warning indicators for the record

    Returns:
        Comma-separated warnings or empty string
    """
    warnings = []

    if pub.generic_title_detected:
        warnings.append("Generic title")

    if not pub.year:
        warnings.append("No year")

    if pub.country_classification.value == "Unknown":
        warnings.append("Unknown country")

    return ", ".join(warnings)


def save_matches_csv(
    marc_publications: list[Publication], csv_file: str, single_file: bool = False
) -> None:
    """Save results to CSV file(s) with country and status information

    Args:
        marc_publications: List of publications to save
        csv_file: Base output filename
        single_file: If True, save all records to a single file.
                    If False, create separate files by copyright status (default).
    """

    def write_header(csv_writer: CSVWriter) -> None:
        """Write the CSV header row"""
        # Simplified headers for better readability
        csv_writer.writerow(
            [
                "ID",
                "Title",
                "Author",
                "Year",
                "Publisher",
                "Country",
                "Status",
                "Match Summary",
                "Confidence",
                "Warning",
                "Registration Source ID",
                "Renewal Entry ID",
            ]
        )

    if single_file:
        # Single file mode: all records in one file
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            csv_writer = writer(f)
            write_header(csv_writer)
            _write_publications_to_csv(csv_writer, marc_publications)
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
        base_name, ext = splitext(csv_file)

        # Create separate file for each status
        for status, publications in status_groups.items():
            # Convert status to lowercase filename format
            status_filename = status.lower()
            output_file = f"{base_name}_{status_filename}{ext}"

            with open(output_file, "w", newline="", encoding="utf-8") as f:
                csv_writer = writer(f)
                write_header(csv_writer)
                _write_publications_to_csv(csv_writer, publications)


def _write_publications_to_csv(csv_writer: CSVWriter, marc_publications: list[Publication]) -> None:
    """Helper function to write publication data to CSV writer"""
    for pub in marc_publications:
        # Simplified output - use 245c author if available, otherwise fall back to 1xx
        author = pub.original_author or pub.original_main_author or ""

        # Get source IDs for verification
        reg_source_id = pub.registration_match.source_id if pub.registration_match else ""
        ren_entry_id = pub.renewal_match.source_id if pub.renewal_match else ""

        csv_writer.writerow(
            [
                pub.source_id,
                pub.original_title,
                author,
                pub.year or "",
                pub.original_publisher or "",
                pub.country_classification.value,
                pub.copyright_status.value,
                _format_match_summary(pub),
                _calculate_confidence(pub),
                _get_warnings(pub),
                reg_source_id,
                ren_entry_id,
            ]
        )
