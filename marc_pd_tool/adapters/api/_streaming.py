# marc_pd_tool/adapters/api/_streaming.py

"""Streaming component for processing very large MARC datasets"""

# Standard library imports
from logging import getLogger
from multiprocessing import Pool
from multiprocessing import get_start_method
from tempfile import mkdtemp
from time import time
from typing import TYPE_CHECKING

# Local imports
from marc_pd_tool.application.models.config_models import AnalysisOptions
from marc_pd_tool.application.processing.matching_engine import init_worker
from marc_pd_tool.application.processing.matching_engine import process_batch
from marc_pd_tool.core.domain.publication import Publication
from marc_pd_tool.core.types.aliases import BatchProcessingInfo
from marc_pd_tool.core.types.protocols import StreamingAnalyzerProtocol
from marc_pd_tool.infrastructure import CacheManager
from marc_pd_tool.shared.utils.time_utils import format_time_duration

# Third party imports removed - psutil not needed (memory monitoring handled by CLI)


if TYPE_CHECKING:
    # Local imports
    from marc_pd_tool.application.models.analysis_results import AnalysisResults

logger = getLogger(__name__)


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
        if options.us_only:
            logger.info("  Filter applied: US publications only")
        if options.min_year or options.max_year:
            year_range = f"{options.min_year or 'earliest'} to {options.max_year or 'present'}"
            logger.info(f"  Year range filter: {year_range}")

        # Process batches using existing parallel infrastructure but with pre-pickled batches
        logger.info("")
        logger.info("=" * 80)
        logger.info("=== PHASE 3: PROCESSING PUBLICATIONS ===")
        logger.info("=" * 80)

        # Extract options
        year_tolerance = options.year_tolerance
        title_threshold = options.title_threshold
        author_threshold = options.author_threshold
        publisher_threshold = options.publisher_threshold if options.publisher_threshold else 0
        early_exit_title = options.early_exit_title
        early_exit_author = options.early_exit_author
        early_exit_publisher = options.early_exit_publisher if options.early_exit_publisher else 85
        score_everything_mode = options.score_everything_mode
        minimum_combined_score_raw = options.minimum_combined_score
        minimum_combined_score: int | None = (
            minimum_combined_score_raw
            if isinstance(minimum_combined_score_raw, (int, type(None)))
            else None
        )
        brute_force_missing_year = options.brute_force_missing_year
        # num_processes should be set by CLI, but provide a fallback
        num_processes = options.num_processes
        if num_processes is None:
            # Standard library imports
            from multiprocessing import cpu_count

            num_processes = max(1, cpu_count() - 4)
        min_year = options.min_year
        max_year = options.max_year

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
            output_formats = options.formats if options.formats else ["json", "csv"]
            single_file = options.single_file
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

            # Platform-specific worker initialization
            if start_method == "fork" and self.registration_index and self.renewal_index:
                # Linux with pre-loaded indexes: Use fork memory sharing
                logger.info("Fork mode: Using pre-loaded indexes via memory sharing")
                
                # Store indexes in module for fork to inherit
                import marc_pd_tool.application.processing.matching_engine as me
                me._shared_data = {  # type: ignore[attr-defined]
                    "registration_index": self.registration_index,
                    "renewal_index": self.renewal_index, 
                    "generic_detector": self.generic_detector,
                    "matching_engine": None,
                }
                
                def init_worker_fork() -> None:
                    """Initialize worker on Linux - use pre-loaded shared data"""
                    import signal
                    signal.signal(signal.SIGINT, signal.SIG_IGN)
                    
                    import marc_pd_tool.application.processing.matching_engine as me
                    from os import getpid
                    from logging import getLogger
                    
                    # Set up worker globals from shared data
                    me._worker_registration_index = me._shared_data["registration_index"]  # type: ignore
                    me._worker_renewal_index = me._shared_data["renewal_index"]  # type: ignore
                    me._worker_generic_detector = me._shared_data["generic_detector"]  # type: ignore
                    
                    # Load config
                    from marc_pd_tool.infrastructure.config import get_config
                    me._worker_config = get_config()
                    me._worker_options = {}
                    
                    logger = getLogger(__name__)
                    logger.info(f"Worker {getpid()} using shared memory indexes")
                
                pool_args = {
                    "processes": num_processes,
                    "initializer": init_worker_fork,
                    "maxtasksperchild": tasks_per_child,
                }
            else:
                # No pre-loaded indexes or not fork: Workers load independently
                if start_method == "fork":
                    logger.info("Fork mode: Indexes not pre-loaded, workers will load from cache")
                else:
                    logger.info(f"{start_method.capitalize()} mode: Workers will load indexes independently")
                
                # Prepare init_worker arguments
                init_args = (
                    self.cache_dir or ".marcpd_cache",
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

            with Pool(**pool_args) as pool:  # type: ignore[arg-type]
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
                        f"✓ Batch {batch_id} complete ({completed_batches}/{total_batches}) | "
                        f"Batch time: {batch_duration_str} | "
                        f"Matches so far: {total_reg_matches} reg, {total_ren_matches} ren | "
                        f"Progress: ({completed_batches/total_batches*100:.1f}%) | "
                        f"ETA: {eta_str}"
                    )

                    # Memory monitoring removed - handled by CLI's MemoryMonitor when --monitor-memory is used

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
