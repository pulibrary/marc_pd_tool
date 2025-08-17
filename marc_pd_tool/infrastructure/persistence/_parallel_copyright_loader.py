# marc_pd_tool/infrastructure/persistence/_parallel_copyright_loader.py

"""Parallel loader for copyright registration XML files"""

# Standard library imports
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures import as_completed
from glob import glob
from logging import getLogger
from os.path import exists
from os.path import join
from time import time
from xml.etree import ElementTree as ET

# Local imports
from marc_pd_tool.core.domain.publication import Publication

logger = getLogger(__name__)


class ParallelCopyrightLoader:
    """Parallel loader for copyright XML files using multiprocessing"""

    def __init__(
        self,
        copyright_dir: str,
        min_year: int | None = None,
        max_year: int | None = None,
        num_workers: int | None = None,
    ):
        """Initialize parallel copyright loader

        Args:
            copyright_dir: Directory containing copyright XML files
            min_year: Minimum year to load (inclusive)
            max_year: Maximum year to load (inclusive)
            num_workers: Number of parallel workers (default: cpu_count - 4)
        """
        self.copyright_dir = copyright_dir
        self.min_year = min_year
        self.max_year = max_year

        # Use specified number of workers, with fallback
        if num_workers is None:
            # Standard library imports
            from multiprocessing import cpu_count

            num_workers = max(1, cpu_count() - 4)
            logger.debug(f"No worker count specified, using default: {num_workers}")
        else:
            logger.debug(f"Using specified worker count: {num_workers}")
        self.num_workers = num_workers

        # Get list of XML files to process
        self.xml_files = self._get_xml_files()

    def _get_xml_files(self) -> list[str]:
        """Get list of XML files to process based on year range

        Returns:
            List of XML file paths
        """
        if not exists(self.copyright_dir):
            logger.warning(f"Copyright directory does not exist: {self.copyright_dir}")
            return []

        # Find all XML files recursively
        pattern = join(self.copyright_dir, "**", "*.xml")
        all_files = glob(pattern, recursive=True)

        if not self.min_year and not self.max_year:
            return all_files

        # Filter by year if specified
        filtered_files = []
        for file_path in all_files:
            # Try to extract year from path (e.g., /1950/file.xml or /1950_v1.xml)
            year = self._extract_year_from_path(file_path)
            if year:
                if self.min_year and year < self.min_year:
                    continue
                if self.max_year and year > self.max_year:
                    continue
            filtered_files.append(file_path)

        return filtered_files

    def _extract_year_from_path(self, file_path: str) -> int | None:
        """Extract year from file path

        Args:
            file_path: Path to XML file

        Returns:
            Year or None if not found
        """
        # Try to find 4-digit year in path
        # Standard library imports
        import re

        match = re.search(r"/(\d{4})/", file_path)
        if match:
            return int(match.group(1))

        # Also check filename
        filename = file_path.split("/")[-1]
        match = re.match(r"(\d{4})", filename)
        if match:
            return int(match.group(1))

        return None

    def load_all_parallel(self) -> list[Publication]:
        """Load all copyright files in parallel

        Returns:
            List of Publication objects
        """
        if not self.xml_files:
            logger.info("No XML files to process")
            return []

        if self.min_year or self.max_year:
            year_filter = f" (years {self.min_year or 'earliest'}-{self.max_year or 'latest'})"
        else:
            year_filter = ""

        # Create chunks for better load balancing
        # Aim for 3-4 chunks per worker for hybrid approach
        chunks_per_worker = 3
        total_chunks = min(len(self.xml_files), self.num_workers * chunks_per_worker)
        chunk_size = max(1, len(self.xml_files) // total_chunks)

        # Create chunks of file paths
        file_chunks = []
        for i in range(0, len(self.xml_files), chunk_size):
            chunk = self.xml_files[i : i + chunk_size]
            if chunk:  # Don't add empty chunks
                file_chunks.append(chunk)

        logger.info(
            f"Parallel loading {len(self.xml_files)} copyright XML files{year_filter} "
            f"using {self.num_workers} worker{'s' if self.num_workers != 1 else ''} "
            f"({len(file_chunks)} chunks)"
        )

        start_time = time()
        all_publications = []
        chunks_processed = 0
        total_files_processed = 0
        files_with_errors = 0

        # Use ProcessPoolExecutor for true parallelism
        with ProcessPoolExecutor(max_workers=self.num_workers) as executor:
            # Submit chunks for processing
            future_to_chunk = {
                executor.submit(
                    _load_multiple_xml_files_static, chunk, self.min_year, self.max_year
                ): chunk
                for chunk in file_chunks
            }

            # Process results as they complete
            for future in as_completed(future_to_chunk):
                chunk = future_to_chunk[future]
                chunks_processed += 1

                try:
                    publications, chunk_errors = future.result()
                    all_publications.extend(publications)
                    total_files_processed += len(chunk)
                    files_with_errors += chunk_errors

                    # Progress reporting
                    elapsed = time() - start_time
                    rate = total_files_processed / elapsed if elapsed > 0 else 0
                    logger.info(
                        f"Progress: {chunks_processed}/{len(file_chunks)} chunks "
                        f"({total_files_processed}/{len(self.xml_files)} files, "
                        f"{rate:.1f} files/sec)"
                    )

                except Exception as e:
                    files_with_errors += len(chunk)
                    logger.warning(f"Error processing chunk: {e}")

        elapsed = time() - start_time
        logger.info(
            f"Loaded {len(all_publications):,} copyright records from "
            f"{total_files_processed} files in {elapsed:.1f}s "
            f"({len(all_publications) / elapsed:.0f} records/sec)"
        )

        if files_with_errors:
            logger.warning(f"Failed to process {files_with_errors} files")

        return all_publications


def _load_multiple_xml_files_static(
    file_paths: list[str], min_year: int | None, max_year: int | None
) -> tuple[list[Publication], int]:
    """Load multiple XML files in a worker process

    This processes a chunk of files to reduce task submission overhead.

    Args:
        file_paths: List of XML file paths to process
        min_year: Minimum year filter
        max_year: Maximum year filter

    Returns:
        Tuple of (list of Publication objects, number of files with errors)
    """
    all_publications = []
    files_with_errors = 0

    for file_path in file_paths:
        try:
            publications = _load_single_xml_file_static(file_path, min_year, max_year)
            all_publications.extend(publications)
        except Exception:
            files_with_errors += 1
            # Errors are already logged in _load_single_xml_file_static

    return all_publications, files_with_errors


def _load_single_xml_file_static(
    file_path: str, min_year: int | None, max_year: int | None
) -> list[Publication]:
    """Static method to load a single XML file

    This must be a module-level function for multiprocessing to pickle it.
    Replicates the logic from CopyrightDataLoader._extract_from_entry exactly.

    Args:
        file_path: Path to XML file
        min_year: Minimum year filter
        max_year: Maximum year filter

    Returns:
        List of Publication objects from this file
    """
    publications = []

    try:
        tree = ET.parse(file_path)
        root = tree.getroot()

        # Process each copyright entry
        for entry in root.findall(".//copyrightEntry"):
            try:
                # Extract title
                title_elem = entry.find(".//title")
                title = title_elem.text if title_elem is not None else ""

                if not title:
                    continue

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
                # Local imports - need to import at function level for multiprocessing
                # Local imports
                from marc_pd_tool.shared.utils.text_utils import extract_year

                year = extract_year(pub_date) if pub_date else None

                # Apply year filter
                if year is not None:
                    if min_year and year < min_year:
                        continue
                    if max_year and year > max_year:
                        continue

                # Create Publication object matching CopyrightDataLoader exactly
                pub = Publication(
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
                publications.append(pub)

            except (AttributeError, KeyError, ValueError):
                # AttributeError: missing XML attributes
                # KeyError: missing expected elements
                # ValueError: invalid data in fields
                continue

    except (ET.ParseError, OSError, UnicodeDecodeError) as e:
        # ET.ParseError: malformed XML
        # OSError: file access issues
        # UnicodeDecodeError: encoding problems
        logger.warning(f"Error parsing {file_path}: {e}")

    return publications
