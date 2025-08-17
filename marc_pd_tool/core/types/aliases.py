# marc_pd_tool/core/types/aliases.py

"""Type aliases for domain-specific dictionaries using Python 3.13 type statements."""

# Standard library imports
from typing import TypeVar

# Local imports
# Local imports - import protocol directly to avoid forward reference
from marc_pd_tool.core.types.protocols import StemmerProtocol

# Modern type statements (Python 3.13)
type StopwordDict = dict[str, list[str]]  # Category -> stopwords
type PatternDict = dict[str, list[str]]  # Pattern type -> patterns
type AbbreviationDict = dict[str, str]  # Abbreviation -> expansion
type StemmerDict = dict[str, StemmerProtocol]  # Language -> Stemmer object (no quotes needed!)

# Batch processing info type - using type statement for clarity
type BatchProcessingInfo = tuple[
    int,  # batch_id (i + 1)
    str,  # batch_path (path to pickled batch file)
    str,  # worker_cache_dir
    str,  # copyright_dir
    str,  # renewal_dir
    str,  # config_hash
    dict[str, int | bool],  # detector_config
    int,  # total_batches
    int,  # title_threshold
    int,  # author_threshold
    int,  # publisher_threshold
    int,  # year_tolerance
    int,  # early_exit_title
    int,  # early_exit_author
    int,  # early_exit_publisher
    bool,  # score_everything
    int | None,  # minimum_combined_score
    bool,  # brute_force_missing_year
    int | None,  # min_year
    int | None,  # max_year
    str,  # result_temp_dir (path to directory for result pickle files)
]

# Generic type variables
T = TypeVar("T")

__all__ = [
    "StopwordDict",
    "PatternDict",
    "AbbreviationDict",
    "StemmerDict",
    "BatchProcessingInfo",
    "T",
]
