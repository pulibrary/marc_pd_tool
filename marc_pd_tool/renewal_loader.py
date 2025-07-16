"""Renewal data TSV loader for publications"""

# Standard library imports
import csv
import logging
from pathlib import Path
from typing import List
from typing import Optional

# Local imports
from marc_pd_tool.publication import Publication

logger = logging.getLogger(__name__)


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
                logger.info(
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
                logger.info(
                    f"  Completed {files_in_batch} files: {batch_entries:,} entries from this batch (Total: {len(all_publications):,})"
                )

        logger.info(f"Loaded {len(all_publications):,} renewal entries from {len(tsv_files)} files")
        return all_publications

    def _extract_from_file(self, tsv_file: Path) -> List[Publication]:
        publications = []

        try:
            with open(tsv_file, "r", encoding="utf-8") as file:
                reader = csv.DictReader(file, delimiter="\t")

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

            # Extract renewal information for source_id
            renewal_id = row.get("id", "").strip()
            renewal_date = row.get("rdat", "").strip()
            original_reg = row.get("oreg", "").strip()

            # Create composite source_id with renewal and original registration info
            source_id_parts = []
            if renewal_id:
                source_id_parts.append(f"R{renewal_id}")
            if original_reg:
                source_id_parts.append(f"Orig:{original_reg}")
            source_id = "|".join(source_id_parts) if source_id_parts else ""

            # No publisher/place in renewal data, leave empty
            publisher = ""
            place = ""

            return Publication(
                title=title,
                author=author,
                pub_date=pub_date,
                publisher=publisher,
                place=place,
                source="Renewal",
                source_id=source_id,
            )

        except Exception as e:
            logger.debug(f"Error extracting from row: {e}")
            return None
