"""Renewal data TSV loader for publications"""

# Standard library imports
from csv import DictReader
from logging import getLogger
from pathlib import Path
from re import search
from re import sub
from typing import List
from typing import Optional

# Local imports
from marc_pd_tool.data.publication import Publication

logger = getLogger(__name__)


class RenewalDataLoader:
    def __init__(self, renewal_dir: str):
        self.renewal_dir = Path(renewal_dir)

    def load_all_renewal_data(self) -> List[Publication]:
        """Load all renewal data from TSV files"""
        logger.info("Loading all renewal data...")

        all_publications = []
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

    def _extract_from_file(self, tsv_file: Path) -> List[Publication]:
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

    def _extract_from_row(self, row: dict) -> Optional[Publication]:
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

            # Extract volume and part information from TSV columns
            volume = row.get("volume", "").strip()
            part = row.get("part", "").strip()

            # Use volume as part_number and part as part_name if available
            part_number = volume if volume else ""
            part_name = part if part else ""

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
                part_number=part_number,  # Extracted from volume column
                part_name=part_name,  # Extracted from part column
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

                # Remove final parenthetical code (usually single letter in parens)
                # Pattern: " (A)" or " (PWH)" at the end
                after_renewal = sub(r"\s*\([^)]*\)\s*$", "", after_renewal)

                # Clean up common suffixes and prefixes
                publisher = after_renewal.strip()

                # Remove common trailing punctuation
                publisher = sub(r"[.,;]+$", "", publisher)

                return publisher.strip()

            # Fallback: try to extract anything that looks like publisher names
            # Look for text after copyright symbol and dates
            copyright_match = search(
                r"©.*?(\d{4}).*?R\d+.*?,\s*\d{1,2}[A-Za-z]{3}\d{2,4},\s*([^(]+)", full_text
            )
            if copyright_match:
                publisher_candidate = copyright_match.group(2).strip()
                publisher_candidate = sub(r"[.,;]+$", "", publisher_candidate)
                return publisher_candidate

            return ""

        except Exception as e:
            logger.debug(f"Error extracting publisher from full_text: {e}")
            return ""
