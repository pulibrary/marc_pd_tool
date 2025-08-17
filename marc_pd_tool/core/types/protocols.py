# marc_pd_tool/core/types/protocols.py

"""Protocol definitions for all interfaces using modern Python 3.13 features."""

# Standard library imports
from pathlib import Path
from typing import Iterator
from typing import Protocol
from typing import TYPE_CHECKING

# Third party imports
# Third-party imports
from pydantic import BaseModel

# Local imports
from marc_pd_tool.core.domain.match_result import MatchResult
from marc_pd_tool.core.domain.publication import Publication
from marc_pd_tool.core.types.models import CopyrightRecord

if TYPE_CHECKING:
    # Avoid circular imports for type checking
    # Local imports
    from marc_pd_tool.application.models.analysis_results import AnalysisResults
    from marc_pd_tool.application.models.config_models import AnalysisOptions
    from marc_pd_tool.application.processing.indexer import DataIndexer
    from marc_pd_tool.application.processing.text_processing import GenericTitleDetector
    from marc_pd_tool.core.types.json import JSONType
    from marc_pd_tool.infrastructure import CacheManager
    from marc_pd_tool.infrastructure.config import ConfigLoader


# Type alias for CSV row data
type CSVRow = list[str | int | float | bool | None]


# ============================================================================
# External Library Protocols
# ============================================================================


class CSVWriter(Protocol):
    """Protocol for CSV writer objects."""

    def writerow(self, row: CSVRow) -> None: ...
    def writerows(self, rows: list[CSVRow]) -> None: ...


class StemmerProtocol(Protocol):
    """Protocol for Stemmer objects from PyStemmer."""

    def stemWord(self, word: str) -> str: ...
    def stemWords(self, words: list[str]) -> list[str]: ...


# ============================================================================
# Loader Protocols
# ============================================================================


class LoaderProtocol[T: BaseModel](Protocol):
    """Generic loader protocol for data loading."""

    def load(self, path: Path) -> list[T]: ...
    def load_lazy(self, path: Path) -> Iterator[T]: ...


class MarcLoaderProtocol(Protocol):
    """Protocol for MARC record loaders."""

    def load_records(self, path: Path | str) -> list[Publication]: ...
    def stream_records(self, path: Path | str) -> Iterator[Publication]: ...
    def count_records(self, path: Path | str) -> int: ...


class CopyrightLoaderProtocol(Protocol):
    """Protocol for copyright data loaders."""

    def load(self, directory: Path | str) -> list[CopyrightRecord]: ...
    def load_filtered(
        self, directory: Path | str, min_year: int | None = None, max_year: int | None = None
    ) -> list[CopyrightRecord]: ...


# ============================================================================
# Processing Protocols
# ============================================================================


class ProcessorProtocol[T, R](Protocol):
    """Generic processor protocol."""

    def process(self, input: T) -> R: ...


class TextProcessorProtocol(Protocol):
    """Protocol for text processing operations."""

    def normalize(self, text: str) -> str: ...
    def tokenize(self, text: str) -> list[str]: ...
    def remove_stopwords(self, tokens: list[str]) -> list[str]: ...


class MatcherProtocol(Protocol):
    """Protocol for matching operations."""

    def find_matches(
        self, publication: Publication, candidates: list[CopyrightRecord]
    ) -> list[MatchResult]: ...

    def calculate_similarity(self, text1: str, text2: str) -> float: ...


# ============================================================================
# Cache Protocols
# ============================================================================


class CacheProtocol[K, V](Protocol):
    """Generic cache protocol."""

    def get(self, key: K) -> V | None: ...
    def set(self, key: K, value: V) -> None: ...
    def exists(self, key: K) -> bool: ...
    def clear(self) -> None: ...


class PersistentCacheProtocol[K, V](CacheProtocol[K, V], Protocol):
    """Protocol for persistent caches."""

    def save(self, path: Path) -> None: ...
    def load(self, path: Path) -> bool: ...
    def get_size(self) -> int: ...


# ============================================================================
# Exporter Protocols
# ============================================================================


class ExporterProtocol[T: BaseModel](Protocol):
    """Generic exporter protocol."""

    def export(self, data: list[T], output_path: Path | str) -> None: ...


class MultiFormatExporterProtocol[T: BaseModel](Protocol):
    """Protocol for exporters supporting multiple formats."""

    def export_csv(self, data: list[T], path: Path) -> None: ...
    def export_json(self, data: list[T], path: Path) -> None: ...
    def export_xlsx(self, data: list[T], path: Path) -> None: ...
    def export_html(self, data: list[T], path: Path) -> None: ...


# ============================================================================
# Index Protocols
# ============================================================================


class IndexProtocol[K, V](Protocol):
    """Protocol for index structures."""

    def add(self, key: K, value: V) -> None: ...
    def get(self, key: K) -> list[V]: ...
    def get_all_keys(self) -> list[K]: ...
    def size(self) -> int: ...


class InvertedIndexProtocol(Protocol):
    """Protocol for inverted index structures."""

    def add_document(self, doc_id: str, terms: list[str]) -> None: ...
    def search(self, term: str) -> list[str]: ...
    def search_multiple(self, terms: list[str]) -> dict[str, list[str]]: ...


# ============================================================================
# Configuration Protocols
# ============================================================================


class ConfigProtocol(Protocol):
    """Protocol for configuration objects."""

    def get[T](self, key: str, default: T | None = None) -> T | None: ...
    def to_dict(self) -> dict[str, object]: ...
    def validate(self) -> bool: ...


class ThresholdConfigProtocol(Protocol):
    """Protocol for threshold configuration."""

    @property
    def title_threshold(self) -> float: ...

    @property
    def author_threshold(self) -> float: ...

    @property
    def publisher_threshold(self) -> float: ...

    def should_match(self, score: float, field: str) -> bool: ...


# ============================================================================
# API Component Protocols
# ============================================================================


class ExportAnalyzerProtocol(Protocol):
    """Protocol defining required attributes for ExportComponent"""

    results: "AnalysisResults"


class GroundTruthAnalyzerProtocol(Protocol):
    """Protocol defining required attributes for GroundTruthComponent"""

    results: "AnalysisResults"
    copyright_dir: str
    renewal_dir: str
    copyright_data: list[Publication] | None
    renewal_data: list[Publication] | None
    config: "ConfigLoader"
    registration_index: "DataIndexer | None"
    renewal_index: "DataIndexer | None"

    def _load_and_index_data(self, options: "AnalysisOptions") -> None: ...
    def _export_ground_truth_json(self, output_path: str) -> None: ...
    def _export_ground_truth_csv(self, output_path: str) -> None: ...


class AnalyzerProtocol(Protocol):
    """Protocol defining required attributes for ProcessingComponent"""

    results: "AnalysisResults"
    config: "ConfigLoader"
    cache_manager: "CacheManager"
    cache_dir: str | None
    copyright_dir: str
    renewal_dir: str
    copyright_data: list[Publication] | None
    renewal_data: list[Publication] | None
    registration_index: "DataIndexer | None"
    renewal_index: "DataIndexer | None"
    generic_detector: "GenericTitleDetector | None"

    def _compute_config_hash(self, config_dict: dict[str, "JSONType"]) -> str: ...
    def _load_and_index_data(self, options: "AnalysisOptions") -> None: ...
    def _cleanup_on_exit(self) -> None: ...
    def export_results(
        self, output_path: str, formats: list[str] | None, single_file: bool
    ) -> None: ...


class StreamingAnalyzerProtocol(Protocol):
    """Protocol defining required attributes for StreamingComponent"""

    results: "AnalysisResults"
    config: "ConfigLoader"
    cache_manager: "CacheManager"
    cache_dir: str | None
    copyright_dir: str
    renewal_dir: str
    copyright_data: list[Publication]
    renewal_data: list[Publication]
    registration_index: "DataIndexer | None"
    renewal_index: "DataIndexer | None"
    generic_detector: "GenericTitleDetector | None"

    def _compute_config_hash(self, config_dict: dict[str, "JSONType"]) -> str: ...
    def _load_and_index_data(self, options: "AnalysisOptions") -> None: ...
    def export_results(
        self, output_path: str, formats: list[str] | None, single_file: bool
    ) -> None: ...
    def _process_streaming_parallel(
        self,
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
    ) -> list[Publication]: ...


__all__ = [
    # External
    "CSVRow",
    "CSVWriter",
    "StemmerProtocol",
    # Loaders
    "LoaderProtocol",
    "MarcLoaderProtocol",
    "CopyrightLoaderProtocol",
    # Processing
    "ProcessorProtocol",
    "TextProcessorProtocol",
    "MatcherProtocol",
    # Cache
    "CacheProtocol",
    "PersistentCacheProtocol",
    # Exporters
    "ExporterProtocol",
    "MultiFormatExporterProtocol",
    # Indexes
    "IndexProtocol",
    "InvertedIndexProtocol",
    # Configuration
    "ConfigProtocol",
    "ThresholdConfigProtocol",
    # API Components
    "ExportAnalyzerProtocol",
    "GroundTruthAnalyzerProtocol",
    "AnalyzerProtocol",
    "StreamingAnalyzerProtocol",
]
