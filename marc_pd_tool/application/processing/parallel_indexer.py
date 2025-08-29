# marc_pd_tool/application/processing/parallel_indexer.py

"""Parallel index building for faster startup times"""

# Standard library imports
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures import as_completed
from logging import getLogger
from pickle import dumps
from pickle import loads
from time import time
from typing import Optional

# Third party imports
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

# Local imports
from marc_pd_tool.application.processing.indexer import (
    generate_wordbased_publisher_keys,
)
from marc_pd_tool.application.processing.indexer import DataIndexer
from marc_pd_tool.application.processing.indexer import generate_wordbased_author_keys
from marc_pd_tool.application.processing.indexer import generate_wordbased_title_keys
from marc_pd_tool.application.processing.text_processing import LanguageProcessor
from marc_pd_tool.application.processing.text_processing import MultiLanguageStemmer
from marc_pd_tool.core.domain.index_entry import IndexEntry
from marc_pd_tool.core.domain.publication import Publication
from marc_pd_tool.infrastructure.config import ConfigLoader
from marc_pd_tool.infrastructure.config import get_config

logger = getLogger(__name__)


class PartialIndexResult(BaseModel):
    """Partial index results from worker processes"""

    model_config = ConfigDict()

    title_index: dict[str, set[int]] = Field(
        default_factory=dict, description="Title word to publication ID mappings"
    )
    author_index: dict[str, set[int]] = Field(
        default_factory=dict, description="Author word to publication ID mappings"
    )
    publisher_index: dict[str, set[int]] = Field(
        default_factory=dict, description="Publisher word to publication ID mappings"
    )
    year_index: dict[int, set[int]] = Field(
        default_factory=dict, description="Year to publication ID mappings"
    )
    lccn_index: dict[str, set[int]] = Field(
        default_factory=dict, description="LCCN to publication ID mappings"
    )


def build_wordbased_index_parallel(
    publications: list[Publication],
    config_loader: Optional[ConfigLoader] = None,
    num_workers: int | None = None,
) -> DataIndexer:
    """Build an index from publications using parallel processing

    Args:
        publications: List of publications to index
        config_loader: Optional configuration loader
        num_workers: Number of parallel workers (default: cpu_count - 1, max 8)

    Returns:
        DataIndexer with all publications indexed
    """
    if not publications:
        return DataIndexer(config_loader)

    # Use specified number of workers, with fallback
    if num_workers is None:
        # Standard library imports
        from multiprocessing import cpu_count

        num_workers = max(1, cpu_count() - 4)
        logger.debug(f"No worker count specified for indexing, using default: {num_workers}")
    else:
        logger.debug(f"Using specified worker count for indexing: {num_workers}")

    # For small datasets, use sequential processing
    if len(publications) < 1000 or num_workers == 1:
        logger.debug("Using sequential indexing for small dataset")
        indexer = DataIndexer(config_loader)
        for pub in publications:
            indexer.add_publication(pub)
        return indexer

    logger.info(
        f"Parallel building indexes for {len(publications):,} publications using {num_workers} worker{'s' if num_workers != 1 else ''}"
    )
    start_time = time()

    # Split publications into chunks for parallel processing
    chunk_size = max(
        100, len(publications) // (num_workers * 4)
    )  # More chunks than workers for better load balancing
    chunks = []
    for i in range(0, len(publications), chunk_size):
        chunk = publications[i : i + chunk_size]
        # Include the starting index so we can reconstruct proper pub_ids
        chunks.append((i, chunk))

    logger.debug(
        f"Split {len(publications)} publications into {len(chunks)} chunks of ~{chunk_size} each"
    )

    # Get config for workers (serialize it once)
    config = config_loader if config_loader else get_config()
    config_data = dumps(config)

    # Process chunks in parallel
    partial_indexes = []
    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        # Submit all chunks for processing
        future_to_chunk = {
            executor.submit(_index_chunk, start_idx, chunk, config_data): (start_idx, chunk)
            for start_idx, chunk in chunks
        }

        # Collect results as they complete
        completed = 0
        total_pubs_indexed = 0
        for future in as_completed(future_to_chunk):
            start_idx, chunk = future_to_chunk[future]
            try:
                partial_index = future.result()
                partial_indexes.append((start_idx, partial_index))

                completed += 1
                total_pubs_indexed += len(chunk)
                
                # Log progress every 10 chunks or 30 seconds, whichever comes first
                elapsed = time() - start_time
                if completed % 10 == 0 or elapsed > (completed // 10 + 1) * 30 or completed == len(chunks):
                    rate = total_pubs_indexed / elapsed if elapsed > 0 else 0
                    percent = (completed / len(chunks)) * 100
                    logger.info(
                        f"  Indexing progress: {percent:.1f}% ({total_pubs_indexed:,}/{len(publications):,} publications, "
                        f"{rate:.0f} pubs/sec)"
                    )

            except Exception as e:
                logger.error(f"Error indexing chunk starting at {start_idx}: {e}")
                # Continue with other chunks

    # Merge partial indexes into final index
    logger.debug("Merging partial indexes...")
    final_indexer = _merge_indexes(partial_indexes, publications, config_loader)

    elapsed = time() - start_time
    logger.info(
        f"Built indexes for {len(publications):,} publications in {elapsed:.1f}s "
        f"({len(publications) / elapsed:.0f} pubs/sec)"
    )

    return final_indexer


def _index_chunk(
    start_idx: int, publications: list[Publication], config_data: bytes
) -> PartialIndexResult:
    """Index a chunk of publications (runs in worker process)

    Args:
        start_idx: Starting index for this chunk
        publications: Publications to index
        config_data: Serialized config

    Returns:
        Dictionary with partial indexes
    """
    # Deserialize config
    config = loads(config_data)

    # Get abbreviation expansion setting
    config_dict = config.config
    enable_abbreviation_expansion = (
        config_dict.get("matching", {})
        .get("word_based", {})
        .get("enable_abbreviation_expansion", True)
    )

    # Initialize language processors (these will be created fresh in each worker)
    lang_processor = LanguageProcessor()  # No config needed
    stemmer = MultiLanguageStemmer()

    # Build partial indexes
    title_index: dict[str, set[int]] = {}
    author_index: dict[str, set[int]] = {}
    publisher_index: dict[str, set[int]] = {}
    year_index: dict[int, set[int]] = {}
    lccn_index: dict[str, set[int]] = {}

    for i, pub in enumerate(publications):
        pub_id = start_idx + i

        # Index by title
        title_keys = generate_wordbased_title_keys(
            pub.title, pub.language_code, lang_processor, stemmer, enable_abbreviation_expansion
        )
        for key in title_keys:
            if key not in title_index:
                title_index[key] = set()
            title_index[key].add(pub_id)

        # Index by author
        if pub.author:
            author_keys = generate_wordbased_author_keys(
                pub.author, pub.language_code, enable_abbreviation_expansion
            )
            for key in author_keys:
                if key not in author_index:
                    author_index[key] = set()
                author_index[key].add(pub_id)

        # Index by main author
        if pub.main_author:
            main_author_keys = generate_wordbased_author_keys(
                pub.main_author, pub.language_code, enable_abbreviation_expansion
            )
            for key in main_author_keys:
                if key not in author_index:
                    author_index[key] = set()
                author_index[key].add(pub_id)

        # Index by publisher
        if pub.publisher:
            publisher_keys = generate_wordbased_publisher_keys(
                pub.publisher, pub.language_code, enable_abbreviation_expansion
            )
            for key in publisher_keys:
                if key not in publisher_index:
                    publisher_index[key] = set()
                publisher_index[key].add(pub_id)

        # Index by year
        if pub.year:
            if pub.year not in year_index:
                year_index[pub.year] = set()
            year_index[pub.year].add(pub_id)

        # Index by LCCN
        if pub.normalized_lccn:
            if pub.normalized_lccn not in lccn_index:
                lccn_index[pub.normalized_lccn] = set()
            lccn_index[pub.normalized_lccn].add(pub_id)

    return PartialIndexResult(
        title_index=title_index,
        author_index=author_index,
        publisher_index=publisher_index,
        year_index=year_index,
        lccn_index=lccn_index,
    )


def _merge_indexes(
    partial_indexes: list[tuple[int, PartialIndexResult]],
    publications: list[Publication],
    config_loader: Optional[ConfigLoader],
) -> DataIndexer:
    """Merge partial indexes into a final DataIndexer

    Args:
        partial_indexes: List of (start_idx, partial_index_dict) tuples
        publications: Complete list of publications
        config_loader: Configuration loader

    Returns:
        Merged DataIndexer
    """
    # Create final indexer
    final_indexer = DataIndexer(config_loader)
    final_indexer.publications = publications

    # Sort partial indexes by start index to ensure correct order
    partial_indexes.sort(key=lambda x: x[0])

    # Merge each partial index
    for start_idx, partial in partial_indexes:
        # Merge title index
        for key, pub_ids in partial.title_index.items():
            if key not in final_indexer.title_index:
                final_indexer.title_index[key] = IndexEntry()
            for pub_id in pub_ids:
                final_indexer.title_index[key].add(pub_id)

        # Merge author index
        for key, pub_ids in partial.author_index.items():
            if key not in final_indexer.author_index:
                final_indexer.author_index[key] = IndexEntry()
            for pub_id in pub_ids:
                final_indexer.author_index[key].add(pub_id)

        # Merge publisher index
        for key, pub_ids in partial.publisher_index.items():
            if key not in final_indexer.publisher_index:
                final_indexer.publisher_index[key] = IndexEntry()
            for pub_id in pub_ids:
                final_indexer.publisher_index[key].add(pub_id)

        # Merge year index
        for year, pub_ids in partial.year_index.items():
            if year not in final_indexer.year_index:
                final_indexer.year_index[year] = IndexEntry()
            for pub_id in pub_ids:
                final_indexer.year_index[year].add(pub_id)

        # Merge LCCN index
        for lccn, pub_ids in partial.lccn_index.items():
            if lccn not in final_indexer.lccn_index:
                final_indexer.lccn_index[lccn] = IndexEntry()
            for pub_id in pub_ids:
                final_indexer.lccn_index[lccn].add(pub_id)

    return final_indexer
