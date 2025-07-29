# marc_pd_tool/exporters/csv_exporter.py

"""CSV export functionality for publication match results"""

# Standard library imports
from csv import writer
from os.path import splitext

# Local imports
from marc_pd_tool.data.publication import Publication
from marc_pd_tool.utils.types import CSVWriter


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
        csv_writer.writerow(
            [
                "MARC ID",
                "MARC Title",
                "Registration Title",
                "Renewal Title",
                "Registration Title Score",
                "Renewal Title Score",
                "MARC Author (245c)",
                "MARC Main Author (1xx)",
                "Registration Author",
                "Renewal Author",
                "Registration Author Score",
                "Renewal Author Score",
                "MARC Year",
                "Registration Date",
                "Renewal Date",
                "MARC Publisher",
                "Registration Publisher",
                "Renewal Publisher",
                "Registration Publisher Score",
                "Renewal Publisher Score",
                "Registration Similarity Score",
                "Renewal Similarity Score",
                "MARC Place",
                "MARC Edition",
                "MARC LCCN",
                "MARC Normalized LCCN",
                "Language Code",
                "Language Detection Status",
                "Country Code",
                "Country Classification",
                "Copyright Status",
                "Generic Title Detected",
                "Generic Detection Reason",
                "Registration Generic Title",
                "Renewal Generic Title",
                "Registration Source ID",
                "Renewal Entry ID",
                "Registration Match Type",
                "Renewal Match Type",
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
        # Get single match data for registration
        reg_source_id = pub.registration_match.source_id if pub.registration_match else ""
        reg_title = pub.registration_match.matched_title if pub.registration_match else ""
        reg_author = pub.registration_match.matched_author if pub.registration_match else ""
        reg_date = pub.registration_match.matched_date if pub.registration_match else ""
        reg_similarity_score = (
            f"{pub.registration_match.similarity_score:.1f}" if pub.registration_match else ""
        )
        reg_title_score = (
            f"{pub.registration_match.title_score:.1f}" if pub.registration_match else ""
        )
        reg_author_score = (
            f"{pub.registration_match.author_score:.1f}" if pub.registration_match else ""
        )
        reg_publisher = (
            pub.registration_match.matched_publisher or "" if pub.registration_match else ""
        )
        reg_publisher_score = (
            f"{pub.registration_match.publisher_score:.1f}" if pub.registration_match else ""
        )

        # Get single match data for renewal
        ren_entry_id = pub.renewal_match.source_id if pub.renewal_match else ""
        ren_title = pub.renewal_match.matched_title if pub.renewal_match else ""
        ren_author = pub.renewal_match.matched_author if pub.renewal_match else ""
        ren_date = pub.renewal_match.matched_date if pub.renewal_match else ""
        ren_similarity_score = (
            f"{pub.renewal_match.similarity_score:.1f}" if pub.renewal_match else ""
        )
        ren_title_score = f"{pub.renewal_match.title_score:.1f}" if pub.renewal_match else ""
        ren_author_score = f"{pub.renewal_match.author_score:.1f}" if pub.renewal_match else ""

        # Get renewal publisher data
        ren_publisher = pub.renewal_match.matched_publisher or "" if pub.renewal_match else ""
        ren_publisher_score = (
            f"{pub.renewal_match.publisher_score:.1f}" if pub.renewal_match else ""
        )

        csv_writer.writerow(
            [
                pub.source_id,
                pub.original_title,
                reg_title,
                ren_title,
                reg_title_score,
                ren_title_score,
                pub.original_author,
                pub.original_main_author,
                reg_author,
                ren_author,
                reg_author_score,
                ren_author_score,
                pub.year,
                reg_date,
                ren_date,
                pub.original_publisher,
                reg_publisher,
                ren_publisher,
                reg_publisher_score,
                ren_publisher_score,
                reg_similarity_score,
                ren_similarity_score,
                pub.original_place,
                pub.original_edition,
                pub.lccn or "",
                pub.normalized_lccn or "",
                pub.language_code,
                pub.language_detection_status,
                pub.country_code,
                pub.country_classification.value,
                pub.copyright_status.value,
                pub.generic_title_detected,
                pub.generic_detection_reason,
                pub.registration_generic_title,
                pub.renewal_generic_title,
                reg_source_id,
                ren_entry_id,
                pub.registration_match.match_type.value if pub.registration_match else "",
                pub.renewal_match.match_type.value if pub.renewal_match else "",
            ]
        )
