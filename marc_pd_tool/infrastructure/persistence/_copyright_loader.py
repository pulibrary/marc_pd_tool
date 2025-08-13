# marc_pd_tool/infrastructure/persistence/_copyright_loader.py

"""Copyright data XML loader for publications"""

# Standard library imports
from functools import cached_property
from logging import getLogger
from pathlib import Path
from re import search
import xml.etree.ElementTree as ET

# Local imports
from marc_pd_tool.core.domain.publication import Publication
from marc_pd_tool.shared.mixins.mixins import YearFilterableMixin
from marc_pd_tool.shared.utils.text_utils import extract_year

logger = getLogger(__name__)


class CopyrightDataLoader(YearFilterableMixin):
    def __init__(self, copyright_dir: str) -> None:
        self.copyright_dir = Path(copyright_dir)

    def load_all_copyright_data(
        self, min_year: int | None = None, max_year: int | None = None
    ) -> list[Publication]:
        """Load copyright data, optionally filtered by year range

        Args:
            min_year: Minimum year to include (inclusive)
            max_year: Maximum year to include (inclusive)

        Returns:
            List of Publication objects
        """
        self._log_year_filtering(min_year, max_year, "copyright")

        all_publications: list[Publication] = []
        xml_files = sorted(self.copyright_dir.rglob("*.xml"), key=lambda x: str(x))
        logger.info(f"Found {len(xml_files)} XML files in copyright directory")

        batch_start_count = 0
        for i, xml_file in enumerate(xml_files):
            if i % 10 == 0:
                batch_start_count = len(all_publications)
                end_file = min(i + 10, len(xml_files))
                logger.debug(
                    f"Processing copyright files {i+1}-{end_file}/{len(xml_files)}: starting with {xml_file.name}"
                )

            pubs = self._extract_from_file(xml_file)

            # Use mixin for year filtering
            pubs = self._filter_by_year(pubs, min_year, max_year)

            all_publications.extend(pubs)

            # Log summary after completing each batch of 10 (or at the end)
            if (i + 1) % 10 == 0 or i == len(xml_files) - 1:
                batch_entries = len(all_publications) - batch_start_count
                files_in_batch = (
                    min(10, len(xml_files) - (i // 10) * 10) if i == len(xml_files) - 1 else 10
                )
                logger.debug(
                    f"  Completed {files_in_batch} files: {batch_entries:,} entries from this batch (Total: {len(all_publications):,})"
                )

        logger.info(
            f"Loaded {len(all_publications):,} copyright entries from {len(xml_files)} files"
        )
        return all_publications

    def _extract_year_from_filename(self, filename: str) -> str:
        year_match = search(r"\b(19|20)\d{2}\b", filename)
        return year_match.group() if year_match else ""

    def _extract_from_file(self, xml_file: Path) -> list[Publication]:
        publications = []

        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()

            for entry in root.findall(".//copyrightEntry"):
                pub = self._extract_from_entry(entry)
                if pub:
                    publications.append(pub)

        except Exception as e:
            logger.warning(f"Error parsing {xml_file}: {e}")

        return publications

    def _extract_from_entry(self, entry: ET.Element) -> Publication | None:
        try:
            # Extract title
            title_elem = entry.find(".//title")
            title = title_elem.text if title_elem is not None else ""

            if not title:
                return None

            # Extract author
            author_elem = entry.find(".//author/authorName")
            author = author_elem.text if author_elem is not None else ""

            # Extract publication date - try multiple sources
            pub_date = ""

            # First try publication date
            pub_date_elem = entry.find(".//publisher/pubDate")
            if pub_date_elem is not None:
                pub_date = pub_date_elem.get("date", pub_date_elem.text or "")

            # If no publication date, try registration date
            if not pub_date:
                reg_date_elem = entry.find(".//regDate")
                if reg_date_elem is not None:
                    pub_date = reg_date_elem.get("date", reg_date_elem.text or "")

            # If still no date, try affidavit date
            if not pub_date:
                aff_date_elem = entry.find(".//affDate")
                if aff_date_elem is not None:
                    pub_date = aff_date_elem.get("date", aff_date_elem.text or "")

            # Extract publisher
            publisher_elem = entry.find(".//publisher/pubName")
            publisher = publisher_elem.text if publisher_elem is not None else ""

            # Extract place
            place_elem = entry.find(".//publisher/pubPlace")
            place = place_elem.text if place_elem is not None else ""

            # Extract volume information from <vol> tag and append to title
            vol_elem = entry.find(".//vol")
            volume_info = vol_elem.text if vol_elem is not None else ""

            if volume_info:
                # Append volume information to title (this is actual bibliographic info, unlike renewal data)
                title = f"{title} {volume_info.strip()}"

            # Extract LCCN
            lccn_elem = entry.find(".//lccn")
            lccn = lccn_elem.text if lccn_elem is not None and lccn_elem.text else ""

            # Extract entry ID
            source_id = entry.get("id", entry.get("regnum", ""))

            # Extract year from pub_date
            # Local imports
            from marc_pd_tool.shared.utils.text_utils import extract_year

            year = extract_year(pub_date) if pub_date else None

            return Publication(
                title=title,
                author=author,
                main_author="",  # Copyright data doesn't have separate main author field
                pub_date=pub_date,
                publisher=publisher,
                place=place,
                lccn=lccn,
                source="Copyright",
                source_id=source_id,
                year=year,
            )

        except Exception:
            return None

    @cached_property
    def year_range(self) -> tuple[int | None, int | None]:
        """Get the year range (min, max) of copyright data without loading full publications

        Returns:
            Tuple of (min_year, max_year) or (None, None) if no valid years found
        """
        logger.info("Analyzing year range in copyright data...")

        xml_files = sorted(self.copyright_dir.rglob("*.xml"), key=lambda x: str(x))
        if not xml_files:
            logger.warning("No copyright XML files found")
            return None, None

        min_year = None
        max_year = None
        valid_years = 0
        total_entries = 0

        for xml_file in xml_files:
            try:
                # Use iterparse for memory efficiency with large files
                context = ET.iterparse(xml_file, events=("start", "end"))
                event, root = next(context)

                for event, elem in context:
                    if event == "end" and elem.tag == "copyrightEntry":
                        total_entries += 1
                        year = self._extract_year_from_entry(elem)

                        if year is not None:
                            valid_years += 1
                            if min_year is None or year < min_year:
                                min_year = year
                            if max_year is None or year > max_year:
                                max_year = year

                        # Clear element to save memory
                        elem.clear()
                        root.clear()

            except Exception as e:
                logger.warning(f"Error analyzing years in {xml_file}: {e}")
                continue

        logger.info(
            f"Copyright data year analysis: {valid_years:,}/{total_entries:,} entries with valid years"
        )
        if min_year is not None and max_year is not None:
            logger.info(f"Copyright data year range: {min_year} - {max_year}")
        else:
            logger.warning("No valid years found in copyright data")

        return min_year, max_year

    def _extract_year_from_entry(self, entry: ET.Element) -> int | None:
        """Extract year from a copyright entry without creating Publication object

        Args:
            entry: XML element for a copyright entry

        Returns:
            Extracted year or None if not found
        """
        try:
            # Extract publication date - try multiple sources (same logic as _extract_from_entry)
            pub_date = ""

            # First try publication date
            pub_date_elem = entry.find(".//publisher/pubDate")
            if pub_date_elem is not None:
                pub_date = pub_date_elem.get("date", pub_date_elem.text or "")

            # If no publication date, try registration date
            if not pub_date:
                reg_date_elem = entry.find(".//regDate")
                if reg_date_elem is not None:
                    pub_date = reg_date_elem.get("date", reg_date_elem.text or "")

            # If still no date, try affidavit date
            if not pub_date:
                aff_date_elem = entry.find(".//affDate")
                if aff_date_elem is not None:
                    pub_date = aff_date_elem.get("date", aff_date_elem.text or "")

            if not pub_date:
                return None

            # Use centralized year extraction
            return extract_year(pub_date)

        except Exception:
            return None

    @cached_property
    def max_data_year(self) -> int | None:
        """Scan copyright directory to find the latest year of data available

        Returns:
            Maximum year found in the copyright data directory, or None if no year directories found
        """
        if not self.copyright_dir.exists():
            logger.warning(f"Copyright directory does not exist: {self.copyright_dir}")
            return None

        # Look for year-named directories (e.g., "1977")
        year_dirs = []
        for item in self.copyright_dir.iterdir():
            if item.is_dir() and item.name.isdigit() and len(item.name) == 4:
                try:
                    year = int(item.name)
                    # Sanity check - copyright data should be between 1900 and 2100
                    if 1900 <= year <= 2100:
                        year_dirs.append(year)
                except ValueError:
                    continue

        if year_dirs:
            max_year = max(year_dirs)
            logger.debug(f"Maximum copyright data year detected: {max_year}")
            return max_year

        logger.warning("No year directories found in copyright data")
        return None
