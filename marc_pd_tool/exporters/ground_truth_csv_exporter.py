# marc_pd_tool/exporters/ground_truth_csv_exporter.py

"""CSV export for ground truth data using standard Publication/MatchResult structure"""

# Standard library imports
import csv
from logging import getLogger
from os.path import splitext

# Local imports
from marc_pd_tool.data.publication import Publication
from marc_pd_tool.processing.text_processing import LanguageProcessor
from marc_pd_tool.processing.text_processing import MultiLanguageStemmer
from marc_pd_tool.utils.text_utils import normalize_text_standard

logger = getLogger(__name__)


def export_ground_truth_csv(publications: list[Publication], output_path: str) -> None:
    """Export ground truth MARC publications with LCCN matches to CSV

    Args:
        publications: List of MARC publications with registration/renewal matches
        output_path: Path for output CSV file
    """
    # Ensure .csv extension
    if not output_path.endswith(".csv"):
        base, _ = splitext(output_path)
        csv_path = f"{base}.csv"
    else:
        csv_path = output_path

    logger.info(f"Exporting ground truth to CSV: {csv_path}")

    # Initialize text processors
    language_processor = LanguageProcessor()
    stemmer = MultiLanguageStemmer()

    # Define CSV headers
    headers = [
        # MARC record fields
        "marc_id",
        "marc_title_original",
        "marc_title_normalized",
        "marc_title_stemmed",
        "marc_author_original",
        "marc_author_normalized",
        "marc_author_stemmed",
        "marc_main_author_original",
        "marc_main_author_normalized",
        "marc_main_author_stemmed",
        "marc_publisher_original",
        "marc_publisher_normalized",
        "marc_publisher_stemmed",
        "marc_year",
        "marc_lccn",
        "marc_lccn_normalized",
        "marc_country_code",
        "marc_language_code",
        # Match record fields
        "match_type",  # "registration" or "renewal"
        "match_title",
        "match_title_normalized",
        "match_author",
        "match_author_normalized",
        "match_publisher",
        "match_publisher_normalized",
        "match_year",
        "match_source_id",
        "match_date",
        # Matching Scores
        "title_score",
        "author_score",
        "publisher_score",
        "combined_score",
        "year_difference",
        "copyright_status",
    ]

    # Write CSV
    with open(csv_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=headers)
        writer.writeheader()

        for marc in publications:
            # Process both registration and renewal matches
            matches_to_export = []

            if marc.registration_match:
                matches_to_export.append(("registration", marc.registration_match))
            if marc.renewal_match:
                matches_to_export.append(("renewal", marc.renewal_match))

            for match_type, match_result in matches_to_export:
                # Process MARC text fields
                marc_title_norm = (
                    normalize_text_standard(marc.original_title) if marc.original_title else ""
                )
                marc_title_words = (
                    language_processor.remove_stopwords(marc_title_norm) if marc_title_norm else []
                )
                marc_title_stem = (
                    " ".join(stemmer.stem_words(marc_title_words)) if marc_title_words else ""
                )

                marc_author_norm = (
                    normalize_text_standard(marc.original_author) if marc.original_author else ""
                )
                marc_author_words = (
                    language_processor.remove_stopwords(marc_author_norm)
                    if marc_author_norm
                    else []
                )
                marc_author_stem = (
                    " ".join(stemmer.stem_words(marc_author_words)) if marc_author_words else ""
                )

                marc_main_author_norm = (
                    normalize_text_standard(marc.original_main_author)
                    if marc.original_main_author
                    else ""
                )
                marc_main_author_words = (
                    language_processor.remove_stopwords(marc_main_author_norm)
                    if marc_main_author_norm
                    else []
                )
                marc_main_author_stem = (
                    " ".join(stemmer.stem_words(marc_main_author_words))
                    if marc_main_author_words
                    else ""
                )

                marc_publisher_norm = (
                    normalize_text_standard(marc.original_publisher)
                    if marc.original_publisher
                    else ""
                )
                marc_publisher_words = (
                    language_processor.remove_stopwords(marc_publisher_norm)
                    if marc_publisher_norm
                    else []
                )
                marc_publisher_stem = (
                    " ".join(stemmer.stem_words(marc_publisher_words))
                    if marc_publisher_words
                    else ""
                )

                # Process match text fields (from MatchResult)
                match_title_norm = (
                    normalize_text_standard(match_result.matched_title)
                    if match_result.matched_title
                    else ""
                )
                match_author_norm = (
                    normalize_text_standard(match_result.matched_author)
                    if match_result.matched_author
                    else ""
                )
                match_publisher_norm = (
                    normalize_text_standard(match_result.matched_publisher)
                    if match_result.matched_publisher
                    else ""
                )

                # Extract year from MatchResult
                # The year_difference tells us how far off the years are
                # We can infer the match year from MARC year and year_difference
                match_year = ""
                if marc.year and match_result.year_difference is not None:
                    # This is approximate - we don't know if it's +/- difference
                    # But for ground truth both should have same year or very close
                    match_year = str(marc.year)  # Best guess without the original

                # Build row
                row = {
                    # MARC data
                    "marc_id": marc.source_id or "",
                    "marc_title_original": marc.original_title or "",
                    "marc_title_normalized": marc_title_norm,
                    "marc_title_stemmed": marc_title_stem,
                    "marc_author_original": marc.original_author or "",
                    "marc_author_normalized": marc_author_norm,
                    "marc_author_stemmed": marc_author_stem,
                    "marc_main_author_original": marc.original_main_author or "",
                    "marc_main_author_normalized": marc_main_author_norm,
                    "marc_main_author_stemmed": marc_main_author_stem,
                    "marc_publisher_original": marc.original_publisher or "",
                    "marc_publisher_normalized": marc_publisher_norm,
                    "marc_publisher_stemmed": marc_publisher_stem,
                    "marc_year": marc.year or "",
                    "marc_lccn": marc.lccn or "",
                    "marc_lccn_normalized": marc.normalized_lccn or "",
                    "marc_country_code": marc.country_code or "",
                    "marc_language_code": marc.language_code or "",
                    # Match data (from MatchResult)
                    "match_type": match_type,
                    "match_title": match_result.matched_title or "",
                    "match_title_normalized": match_title_norm,
                    "match_author": match_result.matched_author or "",
                    "match_author_normalized": match_author_norm,
                    "match_publisher": match_result.matched_publisher or "",
                    "match_publisher_normalized": match_publisher_norm,
                    "match_year": match_year,
                    "match_source_id": match_result.source_id or "",
                    "match_date": match_result.matched_date or "",
                    # Scores
                    "title_score": match_result.title_score or "",
                    "author_score": match_result.author_score or "",
                    "publisher_score": match_result.publisher_score or "",
                    "combined_score": match_result.similarity_score or "",
                    "year_difference": match_result.year_difference or "",
                    "copyright_status": str(marc.copyright_status) if marc.copyright_status else "",
                }

                writer.writerow(row)

    total_rows = sum(
        1 if pub.registration_match else 0 + 1 if pub.renewal_match else 0 for pub in publications
    )
    logger.info(
        f"✓ Exported ground truth CSV to {csv_path} ({len(publications)} publications, {total_rows} matches)"
    )
