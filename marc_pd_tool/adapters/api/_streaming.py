# marc_pd_tool/adapters/api/_streaming.py

"""Streaming component for processing very large MARC datasets"""

# Standard library imports
from logging import getLogger
from multiprocessing import Pool
from multiprocessing import cpu_count
from multiprocessing import get_start_method
from tempfile import mkdtemp
from time import time
from typing import Protocol
from typing import TYPE_CHECKING

# Third party imports
import psutil

# Local imports
from marc_pd_tool.application.models.config_models import AnalysisOptions
from marc_pd_tool.application.processing.indexer import DataIndexer
from marc_pd_tool.application.processing.matching_engine import init_worker
from marc_pd_tool.application.processing.matching_engine import process_batch
from marc_pd_tool.core.domain.publication import Publication
from marc_pd_tool.core.types.aliases import BatchProcessingInfo
from marc_pd_tool.core.types.json import JSONType
from marc_pd_tool.infrastructure import CacheManager
from marc_pd_tool.shared.utils.time_utils import format_time_duration

if TYPE_CHECKING:
    # Local imports
    from marc_pd_tool.application.models.analysis_results import AnalysisResults
    from marc_pd_tool.application.processing.text_processing import GenericTitleDetector
    from marc_pd_tool.infrastructure.config import ConfigLoader

logger = getLogger(__name__)


class StreamingAnalyzerProtocol(Protocol):
    """Protocol defining required attributes for StreamingComponent"""

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
    def export_results(
        self, output_path: str, formats: list[str] | None, single_file: bool
    ) -> None: ...


class StreamingComponent:
    """Component for streaming processing of very large datasets"""

    def _analyze_marc_file_streaming(
        self: StreamingAnalyzerProtocol,
        batch_paths: list[str],
        marc_path: str,
        output_path: str | None,
        options: AnalysisOptions,
    ) -> "AnalysisResults":
        """Analyze MARC file using streaming mode for very large datasets.

        This method processes pickled batch files directly without loading
        all publications into memory simultaneously.
        """
        # Clear previous results
        self.results = type(self.results)()  # Create new instance

        # Log filtering information if applicable
        if options.get("us_only"):
            logger.info("  Filter applied: US publications only")
        if options.get("min_year") or options.get("max_year"):
            year_range = (
                f"{options.get('min_year') or 'earliest'} to {options.get('max_year') or 'present'}"
            )
            logger.info(f"  Year range filter: {year_range}")

        # Process batches using existing parallel infrastructure but with pre-pickled batches
        logger.info("")
        logger.info("=" * 80)
        logger.info("=== PHASE 3: PROCESSING PUBLICATIONS ===")
        logger.info("=" * 80)

        # Extract options
        year_tolerance = options.get("year_tolerance", 1)
        title_threshold = options.get("title_threshold", 40)
        author_threshold = options.get("author_threshold", 30)
        publisher_threshold = options.get("publisher_threshold", 0)
        early_exit_title = options.get("early_exit_title", 95)
        early_exit_author = options.get("early_exit_author", 90)
        early_exit_publisher = options.get("early_exit_publisher", 85)
        score_everything_mode = options.get("score_everything_mode", False)
        minimum_combined_score_raw = options.get("minimum_combined_score")
        minimum_combined_score: int | None = (
            minimum_combined_score_raw
            if isinstance(minimum_combined_score_raw, (int, type(None)))
            else None
        )
        brute_force_missing_year = options.get("brute_force_missing_year", False)
        num_processes = options.get("num_processes", max(1, cpu_count() - 2))
        min_year = options.get("min_year")
        max_year = options.get("max_year")

        logger.info(f"Processing {len(batch_paths)} pre-pickled batches in streaming mode")
        logger.info(f"  Workers: {num_processes}")
        logger.info(f"  Total batches: {len(batch_paths)}")

        # Use the existing parallel processing infrastructure with pre-pickled batches
        self._process_streaming_parallel(
            batch_paths,
            num_processes,
            year_tolerance,
            title_threshold,
            author_threshold,
            publisher_threshold,
            early_exit_title,
            early_exit_author,
            early_exit_publisher,
            score_everything_mode,
            minimum_combined_score,
            brute_force_missing_year,
            min_year,
            max_year,
        )

        # Export results if output path provided
        if output_path:
            logger.info("")
            logger.info("=" * 80)
            logger.info("=== PHASE 5: EXPORTING RESULTS ===")
            logger.info("=" * 80)
            output_formats = options.get("formats", ["json", "csv"])
            single_file = options.get("single_file", False)
            logger.info(f"Exporting results to: {output_path}")
            logger.info(f"  Formats: {', '.join([f.upper() for f in output_formats])}")
            logger.info(
                f"  Single file: {'Yes' if single_file else 'No (separate files by status)'}"
            )
            self.export_results(output_path, formats=output_formats, single_file=single_file)
            logger.info("✓ Export complete")

        return self.results

    def _process_streaming_parallel(
        self: StreamingAnalyzerProtocol,
        batch_paths: list[str],
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
        """Process pre-pickled batches in parallel for streaming mode

        This method is similar to _process_parallel but works with pre-pickled
        batches instead of re-pickling publications.
        """
        start_time = time()

        # Create temporary directory for results
        result_temp_dir = mkdtemp(prefix="marc_results_")
        logger.info(f"Worker results will be saved to: {result_temp_dir}")

        # Get configuration hash for cache validation
        config_dict = self.config.config
        config_hash = self._compute_config_hash(config_dict)

        # Get detector config
        detector_config_raw = config_dict.get("generic_title_detection", {})
        detector_config: dict[str, int | bool] = {}
        if isinstance(detector_config_raw, dict):
            for key, value in detector_config_raw.items():
                if isinstance(value, (int, bool)):
                    detector_config[key] = value

        # Create batch info tuples with pre-pickled paths
        batch_infos = []
        total_batches = len(batch_paths)
        for i, batch_path in enumerate(batch_paths):
            batch_info: BatchProcessingInfo = (
                i + 1,  # batch_id
                batch_path,  # batch_path (already pickled)
                self.cache_dir or ".marcpd_cache",  # cache_dir (provide default if None)
                self.copyright_dir,  # copyright_dir
                self.renewal_dir,  # renewal_dir
                config_hash,  # config_hash
                detector_config,  # detector_config
                total_batches,  # total_batches
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
                result_temp_dir,  # result_temp_dir for workers to save results
            )
            batch_infos.append(batch_info)

        # Process batches in parallel using existing infrastructure
        all_stats = []
        completed_batches = 0
        total_reg_matches = 0
        total_ren_matches = 0

        # Log multiprocessing configuration
        start_method = get_start_method()
        logger.info(f"Multiprocessing start method: {start_method}")

        try:
            # Use same parallel processing logic as _process_parallel
            # Calculate optimal recycling frequency based on workload
            batches_per_worker = total_batches // num_processes

            if batches_per_worker < 20:
                tasks_per_child = None
                logger.info("Small job detected - worker recycling disabled")
            else:
                tasks_per_child = max(50, min(200, batches_per_worker // 3))
                logger.info(f"Worker recycling: every {tasks_per_child} batches")

            # Platform-specific handling for true memory sharing
            if start_method == "fork":
                logger.info("Linux detected: Loading indexes in main process for memory sharing...")

                # Load indexes once in main process
                cache_manager = CacheManager(self.cache_dir or ".marcpd_cache")
                cached_indexes = cache_manager.get_cached_indexes(
                    self.copyright_dir,
                    self.renewal_dir,
                    config_hash,
                    min_year,
                    max_year,
                    brute_force_missing_year,
                )

                if cached_indexes:
                    copyright_index, renewal_index = cached_indexes
                    logger.info("✓ Loaded cached indexes in main process")
                    logger.info("✓ Memory shared via fork - workers will inherit indexes")
                else:
                    logger.info("No cached indexes found - workers will load independently")

            with Pool(
                processes=num_processes, initializer=init_worker, maxtasksperchild=tasks_per_child
            ) as pool:
                for result in pool.imap_unordered(process_batch, batch_infos):
                    batch_id, result_file_path, batch_stats = result
                    all_stats.append(batch_stats)
                    completed_batches += 1
                    total_reg_matches += batch_stats.registration_matches_found
                    total_ren_matches += batch_stats.renewal_matches_found

                    # Progress logging
                    elapsed_time = time() - start_time
                    avg_time_per_batch = elapsed_time / completed_batches
                    remaining_batches = total_batches - completed_batches
                    eta = remaining_batches * avg_time_per_batch

                    batch_duration_str = format_time_duration(batch_stats.processing_time)
                    eta_str = format_time_duration(eta)

                    logger.info(
                        f"✓ Batch {completed_batches}/{total_batches} complete | "
                        f"Batch time: {batch_duration_str} | "
                        f"Progress: ({completed_batches/total_batches*100:.1f}%) | "
                        f"ETA: {eta_str}"
                    )

                    # Memory monitoring (check every 10 batches)
                    if completed_batches % 10 == 0:
                        try:
                            process = psutil.Process()
                            mem_info = process.memory_info()
                            mem_gb: float = mem_info.rss / (1024**3)

                            # Log memory every 50 batches or if usage is high
                            if completed_batches % 50 == 0 or mem_gb > 8.0:
                                logger.info(f"Memory usage: {mem_gb:.1f}GB")
                        except Exception:
                            pass  # Ignore memory monitoring errors

        except KeyboardInterrupt:
            logger.warning("Interrupted by user. Cleaning up...")
            return self.results.publications
        except Exception as e:
            logger.error(f"Error in parallel processing: {e}")
            return self.results.publications

        # Store result directory path for later cleanup
        self.results.result_temp_dir = result_temp_dir

        # Aggregate skipped_no_year counts from all batches
        # Local imports
        from marc_pd_tool.application.models.batch_stats import BatchStats

        total_skipped_no_year = sum(
            stats.skipped_no_year for stats in all_stats if isinstance(stats, BatchStats)
        )
        self.results.statistics.increment("skipped_no_year", total_skipped_no_year)

        # Log final performance stats
        total_time = time() - start_time
        total_records = sum(
            stats.marc_count for stats in all_stats if isinstance(stats, BatchStats)
        )
        records_per_minute = total_records / (total_time / 60) if total_time > 0 else 0

        logger.info(
            f"Streaming parallel processing complete: {total_records} records in "
            f"{format_time_duration(total_time)} ({records_per_minute:.0f} records/minute)"
        )
        logger.info(
            f"Found {total_reg_matches} registration matches, {total_ren_matches} renewal matches"
        )

        return self.results.publications
