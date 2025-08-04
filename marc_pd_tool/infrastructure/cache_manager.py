# marc_pd_tool/infrastructure/cache_manager.py

"""Cache management system for persistent data storage to improve startup performance"""

# Standard library imports
from json import dump as json_dump
from json import load as json_load
from logging import getLogger
from os import makedirs
from os import walk
from os.path import exists
from os.path import getmtime
from os.path import isdir
from os.path import join
from pickle import dump as pickle_dump
from pickle import load as pickle_load
from shutil import rmtree
from time import time
from typing import Mapping
from typing import Optional  # Needed for forward references
from typing import TYPE_CHECKING

# Local imports
from marc_pd_tool.utils.types import CacheMetadata
from marc_pd_tool.utils.types import JSONDict
from marc_pd_tool.utils.types import JSONType
from marc_pd_tool.utils.types import T

if TYPE_CHECKING:
    # Local imports
    from marc_pd_tool.data.publication import Publication
    from marc_pd_tool.processing.indexer import DataIndexer
    from marc_pd_tool.processing.text_processing import GenericTitleDetector

logger = getLogger(__name__)


class CacheManager:
    """Manages persistent caching of parsed data and built indexes"""

    def __init__(self, cache_dir: str = ".marcpd_cache"):
        """Initialize cache manager with specified cache directory

        Args:
            cache_dir: Base directory for cache storage
        """
        self.cache_dir = cache_dir
        self.copyright_cache_dir = join(cache_dir, "copyright_data")
        self.renewal_cache_dir = join(cache_dir, "renewal_data")
        self.marc_cache_dir = join(cache_dir, "marc_data")
        self.indexes_cache_dir = join(cache_dir, "indexes")
        self.generic_detector_cache_dir = join(cache_dir, "generic_detector")

        # Ensure cache directories exist
        for cache_subdir in [
            self.copyright_cache_dir,
            self.renewal_cache_dir,
            self.marc_cache_dir,
            self.indexes_cache_dir,
            self.generic_detector_cache_dir,
        ]:
            makedirs(cache_subdir, exist_ok=True)

    def _get_directory_modification_time(self, directory_path: str) -> float:
        """Get the latest modification time of all files in a directory

        Args:
            directory_path: Path to directory to check

        Returns:
            Latest modification time of any file in the directory
        """
        if not exists(directory_path):
            return 0.0

        max_mtime = getmtime(directory_path)
        try:
            for root, dirs, files in walk(directory_path):
                for file in files:
                    file_path = join(root, file)
                    file_mtime = getmtime(file_path)
                    max_mtime = max(max_mtime, file_mtime)
        except Exception as e:
            logger.warning(f"Error checking modification times in {directory_path}: {e}")
            return 0.0  # Force cache miss on error

        return max_mtime

    def _get_year_range_cache_filename(
        self,
        base_name: str,
        min_year: int | None = None,
        max_year: int | None = None,
        brute_force: bool = False,
    ) -> str:
        """Generate cache filename based on year range parameters

        Args:
            base_name: Base filename (e.g., "publications")
            min_year: Minimum year filter (None means no minimum)
            max_year: Maximum year filter (None means no maximum)
            brute_force: Whether brute-force mode is active (loads all years)

        Returns:
            Cache filename incorporating year range
        """
        if brute_force or (min_year is None and max_year is None):
            return f"{base_name}_all.pkl"
        elif min_year is not None and max_year is not None:
            return f"{base_name}_{min_year}_{max_year}.pkl"
        elif min_year is not None:
            return f"{base_name}_{min_year}_present.pkl"
        elif max_year is not None:
            return f"{base_name}_earliest_{max_year}.pkl"
        else:
            # This shouldn't happen but provide fallback
            return f"{base_name}_all.pkl"

    def _save_metadata(self, cache_subdir: str, metadata: CacheMetadata) -> None:
        """Save cache metadata to JSON file

        Args:
            cache_subdir: Cache subdirectory path
            metadata: Metadata dictionary to save
        """
        metadata_file = join(cache_subdir, "metadata.json")
        try:
            with open(metadata_file, "w") as f:
                json_dump(metadata, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save cache metadata to {metadata_file}: {e}")

    def _load_metadata(self, cache_subdir: str) -> CacheMetadata | None:
        """Load cache metadata from JSON file

        Args:
            cache_subdir: Cache subdirectory path

        Returns:
            Metadata dictionary or None if not found/invalid
        """
        metadata_file = join(cache_subdir, "metadata.json")
        if not exists(metadata_file):
            return None

        try:
            with open(metadata_file, "r") as f:
                data = json_load(f)
                # Cast the loaded JSON to CacheMetadata
                return CacheMetadata(
                    version=data.get("version", ""),
                    source_files=data.get("source_files", []),
                    source_mtimes=data.get("source_mtimes", []),
                    cache_time=data.get("cache_time", 0.0),
                    additional_deps=data.get("additional_deps", {}),
                )
        except Exception as e:
            logger.warning(f"Failed to load cache metadata from {metadata_file}: {e}")
            return None

    def _is_cache_valid(
        self,
        cache_subdir: str,
        source_paths: list[str],
        additional_dependencies: Mapping[str, JSONType | None] | None = None,
    ) -> bool:
        """Check if cache is valid by comparing source file modification times

        Args:
            cache_subdir: Cache subdirectory path
            source_paths: List of source file/directory paths to check
            additional_dependencies: Additional dependencies to validate

        Returns:
            True if cache is valid, False otherwise
        """
        metadata = self._load_metadata(cache_subdir)
        if not metadata:
            return False

        # Check if source paths match
        if metadata["source_files"] != source_paths:
            logger.debug(f"Cache invalid: source paths changed")
            return False

        # Check modification times for each source path
        for source_path in source_paths:
            if not exists(source_path):
                logger.debug(f"Cache invalid: source path {source_path} no longer exists")
                return False

            # Get current modification time
            if exists(source_path):
                if isdir(source_path):
                    current_mtime = self._get_directory_modification_time(source_path)
                else:
                    current_mtime = getmtime(source_path)
            else:
                logger.debug(f"Cache invalid: source path {source_path} does not exist")
                return False

            # Compare with cached modification time
            # Get the index of this source path
            try:
                idx = metadata["source_files"].index(source_path)
                cached_mtime = (
                    metadata["source_mtimes"][idx] if idx < len(metadata["source_mtimes"]) else None
                )
            except (ValueError, IndexError):
                cached_mtime = None
            if cached_mtime is None or current_mtime > cached_mtime:
                logger.debug(
                    f"Cache invalid: {source_path} modified (cached: {cached_mtime}, current: {current_mtime})"
                )
                return False

        # Check additional dependencies if provided
        if additional_dependencies:
            cached_deps = metadata["additional_deps"]
            if cached_deps != additional_dependencies:
                logger.debug(f"Cache invalid: additional dependencies changed")
                return False

        return True

    def _save_cache_data(
        self,
        cache_subdir: str,
        filename: str,
        data: T,
        source_paths: list[str],
        additional_dependencies: Mapping[str, JSONType | None] | None = None,
    ) -> bool:
        """Save data to cache with metadata

        Args:
            cache_subdir: Cache subdirectory path
            filename: Filename for cached data
            data: Data to cache
            source_paths: List of source file/directory paths
            additional_dependencies: Additional dependencies to track

        Returns:
            True if successful, False otherwise
        """
        try:
            # Save the data
            data_file = join(cache_subdir, filename)
            with open(data_file, "wb") as f:
                pickle_dump(data, f)

            # Create metadata
            modification_times: dict[str, float] = {}
            for source_path in source_paths:
                if exists(source_path):
                    if isdir(source_path):
                        modification_times[source_path] = self._get_directory_modification_time(
                            source_path
                        )
                    else:
                        modification_times[source_path] = getmtime(source_path)

            metadata: CacheMetadata = {
                "version": "1.0",
                "source_files": source_paths,
                "source_mtimes": [modification_times.get(p, 0.0) for p in source_paths],
                "cache_time": time(),
                "additional_deps": dict(additional_dependencies) if additional_dependencies else {},
            }

            self._save_metadata(cache_subdir, metadata)
            return True

        except Exception as e:
            logger.error(f"Failed to save cache data to {cache_subdir}/{filename}: {e}")
            return False

    def _load_cache_data(self, cache_subdir: str, filename: str) -> T | None:
        """Load data from cache

        Args:
            cache_subdir: Cache subdirectory path
            filename: Filename of cached data

        Returns:
            Cached data or None if not found/invalid
        """
        data_file = join(cache_subdir, filename)
        if not exists(data_file):
            return None

        try:
            with open(data_file, "rb") as f:
                return pickle_load(f)  # type: ignore[no-any-return]
        except Exception as e:
            logger.warning(f"Failed to load cache data from {data_file}: {e}")
            return None

    # Public interface methods

    def get_cached_copyright_data(
        self,
        copyright_dir: str,
        min_year: int | None = None,
        max_year: int | None = None,
        brute_force: bool = False,
    ) -> Optional[list["Publication"]]:
        """Get cached copyright publications if valid

        Args:
            copyright_dir: Path to copyright XML directory
            min_year: Minimum year filter
            max_year: Maximum year filter
            brute_force: Whether brute-force mode is active

        Returns:
            Cached publications or None if not valid
        """
        cache_filename = self._get_year_range_cache_filename(
            "publications", min_year, max_year, brute_force
        )

        # Create cache subdirectory for this year range
        cache_subdir = join(
            self.copyright_cache_dir,
            cache_filename.replace(".pkl", "").replace("publications_", ""),
        )

        if not exists(cache_subdir):
            return None

        # Include year range in validation dependencies
        additional_deps = {"min_year": min_year, "max_year": max_year, "brute_force": brute_force}

        if self._is_cache_valid(cache_subdir, [copyright_dir], additional_deps):
            # Log what cache we're using
            if brute_force or (min_year is None and max_year is None):
                logger.info("Using cached copyright data for ALL years")
            elif min_year and max_year:
                logger.info(f"Using cached copyright data for years {min_year}-{max_year}")
            else:
                logger.info(
                    f"Using cached copyright data for years {min_year or 'earliest'}-{max_year or 'present'}"
                )

            return self._load_cache_data(cache_subdir, cache_filename)
        return None

    def cache_copyright_data(
        self,
        copyright_dir: str,
        publications: list["Publication"],
        min_year: int | None = None,
        max_year: int | None = None,
        brute_force: bool = False,
    ) -> bool:
        """Cache copyright publications

        Args:
            copyright_dir: Path to copyright XML directory
            publications: Parsed publications to cache
            min_year: Minimum year filter used when loading
            max_year: Maximum year filter used when loading
            brute_force: Whether brute-force mode was active

        Returns:
            True if successful
        """
        cache_filename = self._get_year_range_cache_filename(
            "publications", min_year, max_year, brute_force
        )

        # Create cache subdirectory for this year range
        cache_subdir = join(
            self.copyright_cache_dir,
            cache_filename.replace(".pkl", "").replace("publications_", ""),
        )
        makedirs(cache_subdir, exist_ok=True)

        # Include year range in metadata
        additional_deps = {"min_year": min_year, "max_year": max_year, "brute_force": brute_force}

        # Log what we're caching
        if brute_force or (min_year is None and max_year is None):
            logger.info(
                f"Caching copyright data for ALL years ({len(publications):,} publications)..."
            )
        elif min_year and max_year:
            logger.info(
                f"Caching copyright data for years {min_year}-{max_year} ({len(publications):,} publications)..."
            )
        else:
            logger.info(
                f"Caching copyright data for years {min_year or 'earliest'}-{max_year or 'present'} ({len(publications):,} publications)..."
            )

        return self._save_cache_data(
            cache_subdir, cache_filename, publications, [copyright_dir], additional_deps
        )

    def get_cached_renewal_data(
        self,
        renewal_dir: str,
        min_year: int | None = None,
        max_year: int | None = None,
        brute_force: bool = False,
    ) -> Optional[list["Publication"]]:
        """Get cached renewal publications if valid

        Args:
            renewal_dir: Path to renewal TSV directory
            min_year: Minimum year filter
            max_year: Maximum year filter
            brute_force: Whether brute-force mode is active

        Returns:
            Cached publications or None if not valid
        """
        cache_filename = self._get_year_range_cache_filename(
            "publications", min_year, max_year, brute_force
        )

        # Create cache subdirectory for this year range
        cache_subdir = join(
            self.renewal_cache_dir, cache_filename.replace(".pkl", "").replace("publications_", "")
        )

        if not exists(cache_subdir):
            return None

        # Include year range in validation dependencies
        additional_deps = {"min_year": min_year, "max_year": max_year, "brute_force": brute_force}

        if self._is_cache_valid(cache_subdir, [renewal_dir], additional_deps):
            # Log what cache we're using
            if brute_force or (min_year is None and max_year is None):
                logger.info("Using cached renewal data for ALL years")
            elif min_year and max_year:
                logger.info(f"Using cached renewal data for years {min_year}-{max_year}")
            else:
                logger.info(
                    f"Using cached renewal data for years {min_year or 'earliest'}-{max_year or 'present'}"
                )

            return self._load_cache_data(cache_subdir, cache_filename)
        return None

    def cache_renewal_data(
        self,
        renewal_dir: str,
        publications: list["Publication"],
        min_year: int | None = None,
        max_year: int | None = None,
        brute_force: bool = False,
    ) -> bool:
        """Cache renewal publications

        Args:
            renewal_dir: Path to renewal TSV directory
            publications: Parsed publications to cache
            min_year: Minimum year filter used when loading
            max_year: Maximum year filter used when loading
            brute_force: Whether brute-force mode was active

        Returns:
            True if successful
        """
        cache_filename = self._get_year_range_cache_filename(
            "publications", min_year, max_year, brute_force
        )

        # Create cache subdirectory for this year range
        cache_subdir = join(
            self.renewal_cache_dir, cache_filename.replace(".pkl", "").replace("publications_", "")
        )
        makedirs(cache_subdir, exist_ok=True)

        # Include year range in metadata
        additional_deps = {"min_year": min_year, "max_year": max_year, "brute_force": brute_force}

        # Log what we're caching
        if brute_force or (min_year is None and max_year is None):
            logger.info(
                f"Caching renewal data for ALL years ({len(publications):,} publications)..."
            )
        elif min_year and max_year:
            logger.info(
                f"Caching renewal data for years {min_year}-{max_year} ({len(publications):,} publications)..."
            )
        else:
            logger.info(
                f"Caching renewal data for years {min_year or 'earliest'}-{max_year or 'present'} ({len(publications):,} publications)..."
            )

        return self._save_cache_data(
            cache_subdir, cache_filename, publications, [renewal_dir], additional_deps
        )

    def get_cached_marc_data(
        self,
        marc_path: str,
        year_ranges: dict[str, tuple[int | None, int | None]],
        filtering_options: dict[str, bool | int],
    ) -> list[list["Publication"]] | None:
        """Get cached MARC batches if valid

        Args:
            marc_path: Path to MARC XML file or directory
            year_ranges: Dictionary with copyright/renewal year ranges for validation
            filtering_options: Dictionary with us_only, min_year, max_year settings

        Returns:
            Cached MARC batches or None if not valid
        """
        additional_deps: JSONDict = {"year_ranges": year_ranges, "filtering_options": filtering_options}  # type: ignore[dict-item]
        if self._is_cache_valid(self.marc_cache_dir, [marc_path], additional_deps):
            logger.info("Using cached MARC data")
            return self._load_cache_data(self.marc_cache_dir, "batches.pkl")
        return None

    def cache_marc_data(
        self,
        marc_path: str,
        year_ranges: dict[str, tuple[int | None, int | None]],
        filtering_options: dict[str, bool | int],
        batches: list[list["Publication"]],
    ) -> bool:
        """Cache MARC batches

        Args:
            marc_path: Path to MARC XML file or directory
            year_ranges: Dictionary with copyright/renewal year ranges
            filtering_options: Dictionary with us_only, min_year, max_year settings
            batches: Extracted MARC batches to cache

        Returns:
            True if successful
        """
        total_records = sum(len(batch) for batch in batches)
        logger.info(f"Caching MARC data ({len(batches)} batches, {total_records:,} records)...")

        additional_deps: JSONDict = {"year_ranges": year_ranges, "filtering_options": filtering_options}  # type: ignore[dict-item]
        return self._save_cache_data(
            self.marc_cache_dir, "batches.pkl", batches, [marc_path], additional_deps
        )

    def get_cached_indexes(
        self,
        copyright_dir: str,
        renewal_dir: str,
        config_hash: str,
        min_year: int | None = None,
        max_year: int | None = None,
        brute_force: bool = False,
    ) -> tuple["DataIndexer", Optional["DataIndexer"]] | None:
        """Get cached indexes if valid

        Args:
            copyright_dir: Path to copyright XML directory
            renewal_dir: Path to renewal TSV directory
            config_hash: Hash of configuration for cache validation
            min_year: Minimum year filter used when building indexes
            max_year: Maximum year filter used when building indexes
            brute_force: Whether brute-force mode was active

        Returns:
            Tuple of (registration_index, renewal_index) or None if not valid
        """
        # Create year-specific cache subdirectory
        year_suffix = (
            self._get_year_range_cache_filename("indexes", min_year, max_year, brute_force)
            .replace(".pkl", "")
            .replace("indexes_", "")
        )
        cache_subdir = join(self.indexes_cache_dir, year_suffix)

        if not exists(cache_subdir):
            logger.warning(f"Index cache not found at: {cache_subdir}")
            return None

        additional_deps = {
            "config_hash": config_hash,
            "min_year": min_year,
            "max_year": max_year,
            "brute_force": brute_force,
        }
        if self._is_cache_valid(cache_subdir, [copyright_dir, renewal_dir], additional_deps):
            logger.debug(f"Loading indexes from cache for year range: {year_suffix}")
            reg_index = self._load_cache_data(cache_subdir, "registration.pkl")
            ren_index = self._load_cache_data(cache_subdir, "renewal.pkl")
            if reg_index is not None and ren_index is not None:  # type: ignore[unreachable]
                return (reg_index, ren_index)  # type: ignore[unreachable]
        return None

    def cache_indexes(
        self,
        copyright_dir: str,
        renewal_dir: str,
        config_hash: str,
        registration_index: "DataIndexer",
        renewal_index: "DataIndexer",
        min_year: int | None = None,
        max_year: int | None = None,
        brute_force: bool = False,
    ) -> bool:
        """Cache built indexes

        Args:
            copyright_dir: Path to copyright XML directory
            renewal_dir: Path to renewal TSV directory
            config_hash: Hash of configuration
            registration_index: Built registration index
            renewal_index: Built renewal index
            min_year: Minimum year filter used when building indexes
            max_year: Maximum year filter used when building indexes
            brute_force: Whether brute-force mode was active

        Returns:
            True if successful
        """
        # Log what we're caching
        if brute_force or (min_year is None and max_year is None):
            logger.info("Caching indexes for ALL years...")
        elif min_year and max_year:
            logger.info(f"Caching indexes for years {min_year}-{max_year}...")
        else:
            logger.info(
                f"Caching indexes for years {min_year or 'earliest'}-{max_year or 'present'}..."
            )

        # Create year-specific cache subdirectory
        year_suffix = (
            self._get_year_range_cache_filename("indexes", min_year, max_year, brute_force)
            .replace(".pkl", "")
            .replace("indexes_", "")
        )
        cache_subdir = join(self.indexes_cache_dir, year_suffix)
        makedirs(cache_subdir, exist_ok=True)

        additional_deps = {
            "config_hash": config_hash,
            "min_year": min_year,
            "max_year": max_year,
            "brute_force": brute_force,
        }

        # Cache both indexes
        reg_success = self._save_cache_data(
            cache_subdir,
            "registration.pkl",
            registration_index,
            [copyright_dir, renewal_dir],
            additional_deps,
        )

        ren_success = self._save_cache_data(
            cache_subdir,
            "renewal.pkl",
            renewal_index,
            [copyright_dir, renewal_dir],
            additional_deps,
        )

        return reg_success and ren_success

    def get_cached_generic_detector(
        self, copyright_dir: str, renewal_dir: str, detector_config: dict[str, int | bool]
    ) -> Optional["GenericTitleDetector"]:
        """Get cached generic title detector if valid

        Args:
            copyright_dir: Path to copyright XML directory
            renewal_dir: Path to renewal TSV directory
            detector_config: Generic detector configuration

        Returns:
            Cached detector or None if not valid
        """
        additional_deps: JSONDict = {"detector_config": detector_config}  # type: ignore[dict-item]
        if self._is_cache_valid(
            self.generic_detector_cache_dir, [copyright_dir, renewal_dir], additional_deps
        ):
            logger.debug(f"Loading generic title detector from cache...")
            return self._load_cache_data(self.generic_detector_cache_dir, "detector.pkl")
        return None

    def cache_generic_detector(
        self,
        copyright_dir: str,
        renewal_dir: str,
        detector_config: dict[str, int | bool],
        detector: "GenericTitleDetector",
    ) -> bool:
        """Cache populated generic title detector

        Args:
            copyright_dir: Path to copyright XML directory
            renewal_dir: Path to renewal TSV directory
            detector_config: Generic detector configuration
            detector: Populated detector to cache

        Returns:
            True if successful
        """
        logger.info(f"Caching generic title detector...")
        additional_deps: JSONDict = {"detector_config": detector_config}  # type: ignore[dict-item]
        return self._save_cache_data(
            self.generic_detector_cache_dir,
            "detector.pkl",
            detector,
            [copyright_dir, renewal_dir],
            additional_deps,
        )

    def clear_all_caches(self) -> None:
        """Clear all cached data"""
        logger.info(f"Clearing all caches in {self.cache_dir}")
        try:
            if exists(self.cache_dir):
                rmtree(self.cache_dir)
                # Recreate directory structure
                for cache_subdir in [
                    self.copyright_cache_dir,
                    self.renewal_cache_dir,
                    self.marc_cache_dir,
                    self.indexes_cache_dir,
                    self.generic_detector_cache_dir,
                ]:
                    makedirs(cache_subdir, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to clear caches: {e}")

    def get_cache_info(self) -> JSONDict:
        """Get information about current cache state

        Returns:
            Dictionary with cache status information
        """
        components_dict: dict[str, dict[str, bool | CacheMetadata | None]] = {}
        info: JSONDict = {
            "cache_dir": self.cache_dir,
            "cache_exists": exists(self.cache_dir),
            "components": components_dict,  # type: ignore[dict-item]
        }

        components = [
            ("copyright_data", self.copyright_cache_dir),
            ("renewal_data", self.renewal_cache_dir),
            ("marc_data", self.marc_cache_dir),
            ("indexes", self.indexes_cache_dir),
            ("generic_detector", self.generic_detector_cache_dir),
        ]

        for component_name, component_dir in components:
            metadata = self._load_metadata(component_dir)
            components_dict[component_name] = {"cached": metadata is not None, "metadata": metadata}

        return info
