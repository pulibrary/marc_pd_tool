# marc_pd_tool/infrastructure/persistence/_parallel_renewal_loader.py

"""Parallel loader for renewal TSV files"""

# Standard library imports
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures import as_completed
from csv import DictReader
from csv import Error
from glob import glob
from logging import getLogger
from os.path import exists
from os.path import join
from re import match
from time import time

# Local imports
from marc_pd_tool.core.domain.publication import Publication

logger = getLogger(__name__)


class ParallelRenewalLoader:
    """Parallel loader for renewal TSV files using multiprocessing"""

    def __init__(
        self,
        renewal_dir: str,
        min_year: int | None = None,
        max_year: int | None = None,
        num_workers: int | None = None,
    ):
        """Initialize parallel renewal loader

        Args:
            renewal_dir: Directory containing renewal TSV files
            min_year: Minimum year to load (inclusive)
            max_year: Maximum year to load (inclusive)
            num_workers: Number of parallel workers (default: cpu_count - 4)
        """
        self.renewal_dir = renewal_dir
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

        # Get list of TSV files to process
        self.tsv_files = self._get_tsv_files()

    def _get_tsv_files(self) -> list[str]:
        """Get list of TSV files to process based on year range

        Returns:
            List of TSV file paths
        """
        if not exists(self.renewal_dir):
            logger.warning(f"Renewal directory does not exist: {self.renewal_dir}")
            return []

        # Find all TSV files
        pattern = join(self.renewal_dir, "*.tsv")
        all_files = glob(pattern)

        if not self.min_year and not self.max_year:
            return all_files

        # Filter by year if specified
        filtered_files = []
        for file_path in all_files:
            # Try to extract year from filename (e.g., 1950.tsv or 1950-1.tsv)
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
            file_path: Path to TSV file

        Returns:
            Year or None if not found
        """
        # Extract filename
        filename = file_path.split("/")[-1].replace(".tsv", "")

        # Try to find 4-digit year at start of filename
        year_match = match(r"^(\d{4})", filename)
        if year_match:
            return int(year_match.group(1))

        return None

    def load_all_parallel(self) -> list[Publication]:
        """Load all renewal files in parallel

        Returns:
            List of Publication objects
        """
        if not self.tsv_files:
            logger.info("No TSV files to process")
            return []

        if self.min_year or self.max_year:
            year_filter = f" (years {self.min_year or 'earliest'}-{self.max_year or 'latest'})"
        else:
            year_filter = ""

        # Create chunks for better load balancing
        # Aim for 3-4 chunks per worker for hybrid approach
        chunks_per_worker = 3
        total_chunks = min(len(self.tsv_files), self.num_workers * chunks_per_worker)
        chunk_size = max(1, len(self.tsv_files) // total_chunks)

        # Create chunks of file paths
        file_chunks = []
        for i in range(0, len(self.tsv_files), chunk_size):
            chunk = self.tsv_files[i : i + chunk_size]
            if chunk:  # Don't add empty chunks
                file_chunks.append(chunk)

        logger.info(
            f"Parallel loading {len(self.tsv_files)} renewal TSV files{year_filter} "
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
                    _load_multiple_tsv_files_static, chunk, self.min_year, self.max_year
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
                        f"({total_files_processed}/{len(self.tsv_files)} files, "
                        f"{rate:.1f} files/sec)"
                    )

                except Exception as e:
                    files_with_errors += len(chunk)
                    logger.warning(f"Error processing chunk: {e}")

        elapsed = time() - start_time
        logger.info(
            f"Loaded {len(all_publications):,} renewal records from "
            f"{total_files_processed} files in {elapsed:.1f}s "
            f"({len(all_publications) / elapsed:.0f} records/sec)"
        )

        if files_with_errors:
            logger.warning(f"Failed to process {files_with_errors} files")

        return all_publications


def _load_multiple_tsv_files_static(
    file_paths: list[str], min_year: int | None, max_year: int | None
) -> tuple[list[Publication], int]:
    """Load multiple TSV files in a worker process

    This processes a chunk of files to reduce task submission overhead.

    Args:
        file_paths: List of TSV file paths to process
        min_year: Minimum year filter
        max_year: Maximum year filter

    Returns:
        Tuple of (list of Publication objects, number of files with errors)
    """
    all_publications = []
    files_with_errors = 0

    for file_path in file_paths:
        try:
            publications = _load_single_tsv_file_static(file_path, min_year, max_year)
            all_publications.extend(publications)
        except Exception:
            files_with_errors += 1
            # Errors are already logged in _load_single_tsv_file_static

    return all_publications, files_with_errors


def _load_single_tsv_file_static(
    file_path: str, min_year: int | None, max_year: int | None
) -> list[Publication]:
    """Static method to load a single TSV file

    This must be a module-level function for multiprocessing to pickle it.
    Replicates the logic from RenewalDataLoader._extract_from_row exactly.

    Args:
        file_path: Path to TSV file
        min_year: Minimum year filter
        max_year: Maximum year filter

    Returns:
        List of Publication objects from this file
    """
    publications = []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            reader = DictReader(f, delimiter="\t")

            for row in reader:
                try:
                    # Extract title
                    title = row.get("title", "").strip()
                    if not title:
                        continue

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

                    # Create Publication object matching RenewalDataLoader exactly
                    pub = Publication(
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

                    # Extract year from pub_date if not already set
                    # Note: pub.year is set in the Publication constructor from pub_date
                    # so we don't need to call extract_year() here

                    # Apply year filter
                    if pub.year is not None:
                        if min_year and pub.year < min_year:
                            continue
                        if max_year and pub.year > max_year:
                            continue

                    publications.append(pub)

                except (KeyError, ValueError, AttributeError) as e:
                    # KeyError: missing expected columns in row
                    # ValueError: invalid data format for year extraction
                    # AttributeError: None values in expected fields
                    logger.debug(f"Error extracting from row in {file_path}: {e}")
                    continue

    except (OSError, UnicodeDecodeError, Error) as e:
        # OSError: file access issues
        # UnicodeDecodeError: encoding problems in TSV file
        # Error: malformed CSV/TSV data
        logger.warning(f"Error parsing {file_path}: {e}")

    return publications
