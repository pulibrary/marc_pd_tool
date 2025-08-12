# marc_pd_tool/api/_processing.py

"""Processing mixin for sequential and parallel processing"""

# Standard library imports
from logging import getLogger
from multiprocessing import Pool
from multiprocessing import get_start_method
from os import getpid
from os import makedirs
from os import unlink
from os.path import join
from pickle import HIGHEST_PROTOCOL
from pickle import dump
from pickle import load
from tempfile import TemporaryDirectory
from typing import Protocol
from typing import TYPE_CHECKING
from typing import cast

# Local imports
from marc_pd_tool.data.publication import Publication
from marc_pd_tool.processing import matching_engine as me
from marc_pd_tool.processing.indexer import DataIndexer
from marc_pd_tool.processing.matching_engine import DataMatcher
from marc_pd_tool.processing.matching_engine import init_worker
from marc_pd_tool.processing.matching_engine import process_batch
from marc_pd_tool.utils.types import BatchProcessingInfo
from marc_pd_tool.utils.types import JSONType

if TYPE_CHECKING:
    # Local imports
    from marc_pd_tool.api._results import AnalysisResults
    from marc_pd_tool.infrastructure.cache_manager import CacheManager
    from marc_pd_tool.infrastructure.config_loader import ConfigLoader
    from marc_pd_tool.processing.text_processing import GenericTitleDetector

logger = getLogger(__name__)


class AnalyzerProtocol(Protocol):
    """Protocol defining required attributes for ProcessingMixin"""

    results: "AnalysisResults"
    config: "ConfigLoader"
    cache_manager: "CacheManager"
    cache_dir: str | None
    copyright_dir: str
    renewal_dir: str
    copyright_data: list[Publication] | None
    renewal_data: list[Publication] | None
    registration_index: DataIndexer | None
    renewal_index: DataIndexer | None
    generic_detector: "GenericTitleDetector | None"

    def _compute_config_hash(self, config_dict: dict[str, JSONType]) -> str: ...
    def _load_and_index_data(self, options: dict[str, JSONType]) -> None: ...


class ProcessingMixin:
    """Mixin for sequential and parallel processing functionality"""

    def _process_sequentially(
        self: AnalyzerProtocol,
        publications: list[Publication],
        year_tolerance: int,
        title_threshold: int,
        author_threshold: int,
        publisher_threshold: int,
        early_exit_title: int,
        early_exit_author: int,
        early_exit_publisher: int,
        score_everything_mode: bool,
        minimum_combined_score: int | None,
        brute_force_missing_year: bool,
        min_year: int | None,
        max_year: int | None,
    ) -> list[Publication]:
        """Process publications sequentially using process_batch"""
        logger.info(f"Processing {len(publications)} records sequentially")

        # Get configuration for process_batch
        config_dict = self.config.config
        config_hash = self._compute_config_hash(config_dict)

        # Get detector config
        detector_config_raw = config_dict.get("generic_title_detection", {})
        detector_config: dict[str, int | bool] = {}
        if isinstance(detector_config_raw, dict):
            for key, value in detector_config_raw.items():
                if isinstance(value, (int, bool)):
                    detector_config[key] = value

        # Create a temporary directory for the batch file
        with TemporaryDirectory() as temp_dir:
            # Save the batch to a temporary file
            batch_path = join(temp_dir, "batch_001.pkl")
            with open(batch_path, "wb") as f:
                dump(publications, f, protocol=HIGHEST_PROTOCOL)

            # Create result temp dir
            result_temp_dir = join(temp_dir, "results")
            makedirs(result_temp_dir, exist_ok=True)

            # Create a single batch with all publications
            batch_info: BatchProcessingInfo = (
                1,  # batch_id
                batch_path,  # batch_path (path to pickled publications)
                self.cache_dir or ".marcpd_cache",  # cache_dir (provide default if None)
                self.copyright_dir,  # copyright_dir
                self.renewal_dir,  # renewal_dir
                config_hash,  # config_hash
                detector_config,  # detector_config
                1,  # total_batches
                title_threshold,
                author_threshold,
                publisher_threshold,
                year_tolerance,
                early_exit_title,
                early_exit_author,
                early_exit_publisher,
                score_everything_mode,
                minimum_combined_score,
                brute_force_missing_year,
                min_year,
                max_year,
                result_temp_dir,  # result_temp_dir
            )

            # Process using the same logic as parallel processing
            batch_id, result_file_path, stats = process_batch(batch_info)

            # Load the results from the pickle file
            with open(result_file_path, "rb") as f:
                processed_publications = cast(list[Publication], load(f))

        # Update results
        for pub in processed_publications:
            if isinstance(pub, Publication):
                self.results.add_publication(pub)

        # Update skipped count
        if "skipped_no_year" in stats:
            self.results.statistics["skipped_no_year"] = stats["skipped_no_year"]

        logger.info(
            f"Sequential processing complete: {stats['registration_matches_found']} registration, "
            f"{stats['renewal_matches_found']} renewal matches"
        )

        return self.results.publications

    def _process_parallel(
        self: AnalyzerProtocol,
        publications: list[Publication],
        batch_size: int,
        num_processes: int,
        year_tolerance: int,
        title_threshold: int,
        author_threshold: int,
        publisher_threshold: int,
        early_exit_title: int,
        early_exit_author: int,
        early_exit_publisher: int,
        score_everything_mode: bool,
        minimum_combined_score: int | None,
        brute_force_missing_year: bool,
        min_year: int | None,
        max_year: int | None,
    ) -> list[Publication]:
        """Process publications in parallel using multiprocessing Pool"""
        logger.info(
            f"Processing {len(publications)} records in parallel with {num_processes} workers"
        )

        # Get configuration
        config_dict = self.config.config
        config_hash = self._compute_config_hash(config_dict)

        # Get detector config
        detector_config_raw = config_dict.get("generic_title_detection", {})
        detector_config: dict[str, int | bool] = {}
        if isinstance(detector_config_raw, dict):
            for key, value in detector_config_raw.items():
                if isinstance(value, (int, bool)):
                    detector_config[key] = value

        # Create temporary directory for batch files
        with TemporaryDirectory() as temp_dir:
            # Save batches to disk
            batches = [
                publications[i : i + batch_size] for i in range(0, len(publications), batch_size)
            ]
            total_batches = len(batches)

            batch_infos: list[BatchProcessingInfo] = []
            for batch_id, batch in enumerate(batches, 1):
                batch_path = join(temp_dir, f"batch_{batch_id:04d}.pkl")
                with open(batch_path, "wb") as f:
                    dump(batch, f, protocol=HIGHEST_PROTOCOL)

                batch_info: BatchProcessingInfo = (
                    batch_id,
                    batch_path,
                    self.cache_dir or ".marcpd_cache",
                    self.copyright_dir,
                    self.renewal_dir,
                    config_hash,
                    detector_config,
                    total_batches,
                    title_threshold,
                    author_threshold,
                    publisher_threshold,
                    year_tolerance,
                    early_exit_title,
                    early_exit_author,
                    early_exit_publisher,
                    score_everything_mode,
                    minimum_combined_score,
                    brute_force_missing_year,
                    min_year,
                    max_year,
                    temp_dir,  # result_temp_dir
                )
                batch_infos.append(batch_info)

            # Determine worker recycling strategy
            total_records = len(publications)
            if total_records < 10000:
                tasks_per_child = None  # No recycling for small datasets
            elif total_records < 50000:
                tasks_per_child = max(5, total_batches // (num_processes * 2))
            else:
                tasks_per_child = max(3, total_batches // (num_processes * 4))

            # Platform-specific worker initialization
            start_method = get_start_method()
            if start_method == "fork":
                # Linux: Load data once in main process
                logger.info(
                    "Fork mode detected: Loading indexes in main process for memory sharing"
                )

                if not self.registration_index or not self.renewal_index:
                    self._load_and_index_data(
                        {
                            "min_year": min_year,
                            "max_year": max_year,
                            "brute_force_missing_year": brute_force_missing_year,
                        }
                    )

                registration_index = self.registration_index
                renewal_index = self.renewal_index
                generic_detector = self.generic_detector

                # Store in global for fork to inherit
                me._shared_data = {
                    "registration_index": registration_index,
                    "renewal_index": renewal_index,
                    "generic_detector": generic_detector,
                    "matching_engine": DataMatcher(),
                }

                # Use minimal initializer that just sets up worker data from shared
                def init_worker_fork() -> None:
                    """Initialize worker on Linux - use pre-loaded shared data"""
                    me._worker_data = me._shared_data
                    logger.info(f"Worker {getpid()} using shared memory indexes")

                pool_args = {
                    "processes": num_processes,
                    "initializer": init_worker_fork,
                    "maxtasksperchild": tasks_per_child,
                }
            else:
                # macOS/Windows: Each worker loads independently
                logger.info("Spawn mode detected: Workers will load indexes independently")
                init_args = (
                    self.cache_dir,
                    self.copyright_dir,
                    self.renewal_dir,
                    config_hash,
                    detector_config,
                    min_year,
                    max_year,
                    brute_force_missing_year,
                )

                pool_args = {
                    "processes": num_processes,
                    "initializer": init_worker,
                    "initargs": init_args,
                    "maxtasksperchild": tasks_per_child,
                }

            # Create pool with platform-specific arguments
            with Pool(**pool_args) as pool:  # type: ignore[arg-type]
                logger.info(f"Processing {total_batches} batches with {num_processes} workers")

                # Process batches as they complete (unordered for efficiency)
                for batch_id_result, result_file_path, batch_stats in pool.imap_unordered(
                    process_batch, batch_infos, chunksize=1
                ):
                    try:
                        batch_id = batch_id_result

                        # Load only statistics file - not the full publications
                        try:
                            # Construct stats file path from result file path
                            stats_file_path = result_file_path.replace("result_", "stats_")

                            # Load just the statistics (small data)
                            with open(stats_file_path, "rb") as stats_file:
                                detailed_stats: JSONType = load(stats_file)

                            # Update statistics directly
                            if isinstance(detailed_stats, dict):
                                for key, value in detailed_stats.items():
                                    if isinstance(key, str) and isinstance(value, int):
                                        if key in self.results.statistics:
                                            self.results.statistics[key] += value
                                        else:
                                            # For copyright status counts
                                            self.results.statistics[key] = (
                                                self.results.statistics.get(key, 0) + value
                                            )

                            # Track the result file path for later loading
                            self.results.add_result_file(result_file_path)

                            # Delete the stats file - we don't need it anymore
                            unlink(stats_file_path)

                            # Log tracking info
                            total_records = 0
                            if (
                                isinstance(detailed_stats, dict)
                                and "total_records" in detailed_stats
                            ):
                                tr = detailed_stats["total_records"]
                                if isinstance(tr, int):
                                    total_records = tr
                            logger.debug(
                                f"Tracked result file: {result_file_path} ({total_records} publications)"
                            )

                        except Exception as e:
                            logger.error(f"Failed to load statistics for batch {batch_id}: {e}")
                            # Still track the result file even if stats failed
                            self.results.add_result_file(result_file_path)

                        # Update high-level statistics from batch_stats
                        self.results.statistics["registration_matches"] += batch_stats.get(
                            "registration_matches_found", 0
                        )
                        self.results.statistics["renewal_matches"] += batch_stats.get(
                            "renewal_matches_found", 0
                        )
                        self.results.statistics["skipped_no_year"] += batch_stats.get(
                            "skipped_no_year", 0
                        )

                        # Report progress
                        processing_time = batch_stats.get("processing_time", 0.0)
                        records_processed_raw = batch_stats.get("records_processed", 0)
                        records_processed = (
                            int(cast(int, records_processed_raw)) if records_processed_raw else 0
                        )
                        records_per_second = (
                            float(records_processed) / processing_time
                            if processing_time > 0
                            else 0.0
                        )
                        logger.info(
                            f"Batch {batch_id}/{total_batches} complete: "
                            f"{batch_stats.get('registration_matches_found', 0)} reg, "
                            f"{batch_stats.get('renewal_matches_found', 0)} ren matches "
                            f"({records_per_second:.1f} rec/s)"
                        )

                    except Exception as e:
                        logger.error(f"Error processing batch {batch_id_result}: {e}")
                        raise

        # Store the temp directory path for later loading
        self.results.result_temp_dir = temp_dir

        # Note: We don't load all publications here for memory efficiency
        # They will be loaded on-demand when needed (e.g., for export)
        logger.info(
            f"Parallel processing complete: "
            f"{self.results.statistics['registration_matches']} registration, "
            f"{self.results.statistics['renewal_matches']} renewal matches"
        )

        return []  # Publications are stored in result files, not in memory
