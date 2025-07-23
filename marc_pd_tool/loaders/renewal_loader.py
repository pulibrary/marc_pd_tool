# marc_pd_tool/loaders/renewal_loader.py

"""Renewal data TSV loader for publications"""

# Standard library imports
from csv import DictReader
from logging import getLogger
from pathlib import Path
from re import search

# Local imports
from marc_pd_tool.data.publication import Publication
from marc_pd_tool.utils.mixins import YearFilterableMixin
from marc_pd_tool.utils.publisher_utils import clean_publisher_suffix
from marc_pd_tool.utils.text_utils import extract_year

logger = getLogger(__name__)


class RenewalDataLoader(YearFilterableMixin):
    def __init__(self, renewal_dir: str) -> None:
        self.renewal_dir = Path(renewal_dir)

    def load_all_renewal_data(
        self, min_year: int | None = None, max_year: int | None = None
    ) -> list[Publication]:
        """Load renewal data, optionally filtered by year range

        Args:
            min_year: Minimum year to include (inclusive)
            max_year: Maximum year to include (inclusive)

        Returns:
            List of Publication objects
        """
        self._log_year_filtering(min_year, max_year, "renewal")

        all_publications: list[Publication] = []
        tsv_files = sorted(self.renewal_dir.glob("*.tsv"), key=lambda x: str(x))
        logger.info(f"Found {len(tsv_files)} TSV files in renewal directory")

        batch_start_count = 0
        for i, tsv_file in enumerate(tsv_files):
            if i % 10 == 0:
                batch_start_count = len(all_publications)
                end_file = min(i + 10, len(tsv_files))
                logger.debug(
                    f"Processing renewal files {i+1}-{end_file}/{len(tsv_files)}: starting with {tsv_file.name}"
                )

            pubs = self._extract_from_file(tsv_file)

            # Use mixin for year filtering
            pubs = self._filter_by_year(pubs, min_year, max_year)

            all_publications.extend(pubs)

            # Log summary after completing each batch of 10 (or at the end)
            if (i + 1) % 10 == 0 or i == len(tsv_files) - 1:
                batch_entries = len(all_publications) - batch_start_count
                files_in_batch = (
                    min(10, len(tsv_files) - (i // 10) * 10) if i == len(tsv_files) - 1 else 10
                )
                logger.debug(
                    f"  Completed {files_in_batch} files: {batch_entries:,} entries from this batch (Total: {len(all_publications):,})"
                )

        logger.info(f"Loaded {len(all_publications):,} renewal entries from {len(tsv_files)} files")
        return all_publications

    def _extract_from_file(self, tsv_file: Path) -> list[Publication]:
        publications = []

        try:
            with open(tsv_file, "r", encoding="utf-8") as file:
                reader = DictReader(file, delimiter="\t")

                for row in reader:
                    pub = self._extract_from_row(row)
                    if pub:
                        publications.append(pub)

        except Exception as e:
            logger.warning(f"Error parsing {tsv_file}: {e}")

        return publications

    def _extract_from_row(self, row: dict[str, str]) -> Publication | None:
        """Extract Publication from TSV row"""
        try:
            # Extract title
            title = row.get("title", "").strip()
            if not title:
                return None

            # Extract author
            author = row.get("author", "").strip()

            # Extract publication date - use original registration date (odat)
            pub_date = row.get("odat", "").strip()

            # Extract entry_id for source_id (direct lookup in TSV files)
            entry_id = row.get("entry_id", "").strip()
            source_id = entry_id

            # Extract volume and part information from TSV columns (but don't append to title for better matching)
            row.get("volume", "").strip()
            row.get("part", "").strip()

            # Note: Volume/part information available but not concatenated to avoid match pollution

            # Store full_text for publisher fuzzy matching (don't extract publisher)
            full_text = row.get("full_text", "").strip()
            publisher = ""  # Will be populated from full_text during fuzzy matching
            place = ""

            return Publication(
                title=title,
                author=author,
                main_author="",  # Renewal data doesn't have separate main author field
                pub_date=pub_date,
                publisher=publisher,
                place=place,
                lccn="",  # Renewal data doesn't contain LCCN information
                source="Renewal",
                source_id=source_id,
                full_text=full_text,
            )

        except Exception as e:
            logger.debug(f"Error extracting from row: {e}")
            return None

    def _extract_publisher_from_full_text(self, full_text: str) -> str:
        """Extract publisher from the full_text field

        The full_text field typically contains publisher information after the renewal date.
        Format examples:
        - "TITLE © date, regnum. Rdate, renewal_date, Publisher Name (code)"
        - "TITLE © date, regnum. Rdate, renewal_date, Publisher Name, successor to Other Publisher (code)"
        """
        if not full_text:
            return ""

        try:
            # Look for pattern: date, then publisher before final parentheses
            # Common pattern: "Rxxxxxx, DDMmmYY, Publisher Name (CODE)"

            # Split on renewal ID pattern (R followed by numbers, then comma and date)
            renewal_pattern = r"R\d+,\s*\d{1,2}[A-Za-z]{3}\d{2,4},"
            match = search(renewal_pattern, full_text)

            if match:
                # Get text after the renewal date
                after_renewal = full_text[match.end() :].strip()

                # Use centralized publisher cleaning
                publisher = clean_publisher_suffix(after_renewal)

                return publisher

            # Fallback: try to extract anything that looks like publisher names
            # Look for text after copyright symbol and dates
            copyright_match = search(
                r"©.*?(\d{4}).*?R\d+.*?,\s*\d{1,2}[A-Za-z]{3}\d{2,4},\s*([^(]+)", full_text
            )
            if copyright_match:
                publisher_candidate = copyright_match.group(2).strip()
                return clean_publisher_suffix(publisher_candidate)

            return ""

        except Exception as e:
            logger.debug(f"Error extracting publisher from full_text: {e}")
            return ""

    def get_year_range(self) -> tuple[int | None, int | None]:
        """Get the year range (min, max) of renewal data without loading full publications

        Returns:
            Tuple of (min_year, max_year) or (None, None) if no valid years found
        """
        logger.info("Analyzing year range in renewal data...")

        tsv_files = sorted(self.renewal_dir.rglob("*.tsv"), key=lambda x: str(x))
        if not tsv_files:
            logger.warning("No renewal TSV files found")
            return None, None

        min_year = None
        max_year = None
        valid_years = 0
        total_entries = 0

        for tsv_file in tsv_files:
            try:
                with open(tsv_file, "r", encoding="utf-8") as f:
                    reader = DictReader(f, delimiter="\t")

                    for row in reader:
                        total_entries += 1
                        year = self._extract_year_from_row(row)

                        if year is not None:
                            valid_years += 1
                            if min_year is None or year < min_year:
                                min_year = year
                            if max_year is None or year > max_year:
                                max_year = year

            except Exception as e:
                logger.warning(f"Error analyzing years in {tsv_file}: {e}")
                continue

        logger.info(
            f"Renewal data year analysis: {valid_years:,}/{total_entries:,} entries with valid years"
        )
        if min_year is not None and max_year is not None:
            logger.info(f"Renewal data year range: {min_year} - {max_year}")
        else:
            logger.warning("No valid years found in renewal data")

        return min_year, max_year

    def _extract_year_from_row(self, row: dict[str, str]) -> int | None:
        """Extract year from a renewal row without creating Publication object

        Args:
            row: Dictionary representing a TSV row

        Returns:
            Extracted year or None if not found
        """
        try:
            # Extract publication date - use original registration date (odat) - same logic as _extract_from_row
            pub_date = row.get("odat", "").strip()

            if not pub_date:
                return None

            # Use centralized year extraction
            return extract_year(pub_date)

        except Exception:
            return None
