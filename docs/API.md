# Python API Reference

The MARC Copyright Status Analysis Tool provides a Python API for programmatic access to its functionality. This document covers the public API for using the tool as a library.

## Installation

```python
# Install the package (once available on PyPI)
pip install marc-pd-tool

# Or install from source
pdm install
```

## Quick Start

```python
from marc_pd_tool import MarcCopyrightAnalyzer

# Create analyzer instance
analyzer = MarcCopyrightAnalyzer()

# Analyze a MARC file
results = analyzer.analyze_marc_file(
    marc_path="catalog.xml",
    copyright_dir="nypl-reg/xml/",
    renewal_dir="nypl-ren/data/"
)

# Access results
print(f"Total records: {results.statistics.total_records}")
print(f"Public domain: {len(results.get_public_domain_publications())}")

# Export results
results.export_to_csv("output.csv")
```

## Core Classes

### MarcCopyrightAnalyzer

Main analyzer class for processing MARC records against copyright data.

```python
class marc_pd_tool.MarcCopyrightAnalyzer(
    config_path: str | None = None,
    cache_dir: str | None = None,
    force_refresh: bool = False,
    log_file: str | None = None
)
```

**Parameters:**

- `config_path`: Path to custom configuration JSON file
- `cache_dir`: Directory for caching indexes (default: `.marcpd_cache`)
- `force_refresh`: Force rebuild of cached indexes
- `log_file`: Path to log file for analysis output

#### Methods

##### analyze_marc_file

```python
def analyze_marc_file(
    marc_path: str,
    copyright_dir: str | None = None,
    renewal_dir: str | None = None,
    output_path: str | None = None,
    options: AnalysisOptions | None = None
) -> AnalysisResults
```

Analyze a MARC XML file for copyright status.

**Parameters:**

- `marc_path`: Path to MARC XML file or directory
- `copyright_dir`: Directory containing copyright registration XML files
- `renewal_dir`: Directory containing renewal TSV files
- `output_path`: Path for output file (optional)
- `options`: Analysis options dictionary (see AnalysisOptions below)

**Returns:** `AnalysisResults` object containing processed publications and statistics

##### load_and_index_data

```python
def load_and_index_data(
    copyright_dir: str | None = None,
    renewal_dir: str | None = None,
    min_year: int | None = None,
    max_year: int | None = None,
    use_cache: bool = True
) -> None
```

Pre-load and index copyright/renewal data. Useful when processing multiple MARC files.

**Parameters:**

- `copyright_dir`: Directory containing copyright XML files
- `renewal_dir`: Directory containing renewal TSV files
- `min_year`: Minimum year to load (filters data)
- `max_year`: Maximum year to load (filters data)
- `use_cache`: Whether to use cached indexes

##### extract_ground_truth

```python
def extract_ground_truth(
    marc_path: str,
    options: AnalysisOptions | None = None
) -> tuple[list[GroundTruthPair], GroundTruthStats]
```

Extract LCCN-verified ground truth matches for threshold optimization.

**Parameters:**

- `marc_path`: Path to MARC XML file
- `options`: Analysis options

**Returns:** Tuple of (ground truth pairs, statistics)

### AnalysisResults

Container for analysis results with statistics and export capabilities.

```python
class marc_pd_tool.AnalysisResults
```

#### Properties

- `publications`: List of processed `Publication` objects
- `statistics`: `AnalysisStatistics` object with counts
- `ground_truth_stats`: Optional ground truth statistics

#### Methods

##### get_public_domain_publications

```python
def get_public_domain_publications() -> list[Publication]
```

Get all publications determined to be in the public domain.

##### get_in_copyright_publications

```python
def get_in_copyright_publications() -> list[Publication]
```

Get all publications determined to be under copyright.

##### get_undetermined_publications

```python
def get_undetermined_publications() -> list[Publication]
```

Get all publications with undetermined copyright status.

##### export_to_csv

```python
def export_to_csv(
    output_path: str,
    single_file: bool = False
) -> None
```

Export results to CSV format.

**Parameters:**

- `output_path`: Path for output file
- `single_file`: If True, export all results to one file; if False, separate by status

##### export_to_xlsx

```python
def export_to_xlsx(
    output_path: str
) -> None
```

Export results to Excel format with multiple worksheets.

##### export_to_json

```python
def export_to_json(
    output_path: str
) -> None
```

Export results to JSON format.

### Publication

Domain entity representing a publication with bibliographic data.

```python
class marc_pd_tool.Publication
```

#### Properties

- `title`: Cleaned title text
- `author`: Author statement (may include multiple authors)
- `main_author`: Main entry author (controlled form)
- `year`: Publication year as integer
- `publisher`: Publisher name
- `place`: Place of publication
- `lccn`: Library of Congress Control Number
- `normalized_lccn`: Normalized LCCN for matching
- `country_code`: Three-letter country code
- `country_classification`: `CountryClassification` enum value
- `copyright_status`: Determined copyright status string
- `status_rule`: `CopyrightStatusRule` enum explaining the determination

#### Methods

##### has_registration_match

```python
def has_registration_match() -> bool
```

Check if publication has a copyright registration match.

##### has_renewal_match

```python
def has_renewal_match() -> bool
```

Check if publication has a copyright renewal match.

##### get_best_match

```python
def get_best_match() -> MatchResult | None
```

Get the highest-scoring match result.

### MatchResult

Represents a match between a MARC record and copyright/renewal data.

```python
class marc_pd_tool.MatchResult
```

#### Properties

- `matched_title`: Title from copyright/renewal record
- `matched_author`: Author from copyright/renewal record
- `similarity_score`: Overall similarity score (0-100)
- `title_score`: Title similarity score (0-100)
- `author_score`: Author similarity score (0-100)
- `publisher_score`: Publisher similarity score (0-100)
- `year_difference`: Difference in publication years
- `source_type`: "registration" or "renewal"
- `source_id`: Identifier from source record
- `match_type`: `MatchType` enum (LCCN, SIMILARITY, or BRUTE_FORCE_WITHOUT_YEAR)

## Analysis Options

The `AnalysisOptions` dictionary supports the following keys:

```python
options = {
    # Filtering
    "us_only": False,              # Only process US publications
    "min_year": 1923,              # Minimum publication year
    "max_year": 1977,              # Maximum publication year
    "brute_force_missing_year": False,  # Process records without years
    
    # Matching thresholds
    "title_threshold": 40,         # Title similarity threshold (0-100)
    "author_threshold": 30,        # Author similarity threshold (0-100)
    "publisher_threshold": 30,     # Publisher similarity threshold (0-100)
    "year_tolerance": 1,           # Year difference tolerance
    "early_exit_title": 95,        # High-confidence title threshold
    "early_exit_author": 90,       # High-confidence author threshold
    "early_exit_publisher": 85,    # High-confidence publisher threshold
    
    # Analysis modes
    "score_everything_mode": False,     # Find best match regardless of thresholds
    "minimum_combined_score": None,     # Minimum score for score_everything mode
    
    # Performance
    "batch_size": 100,             # Records per batch
    "num_processes": None,         # Worker processes (None = auto)
    
    # Output
    "formats": ["csv", "json"],    # Output formats
    "single_file": False,          # Single vs multiple output files
}
```

## Enumerations

### CountryClassification

```python
class marc_pd_tool.CountryClassification(Enum):
    US = "US"
    NON_US = "Non-US"
    UNKNOWN = "Unknown"
```

### CopyrightStatus

```python
class marc_pd_tool.CopyrightStatus(Enum):
    US_RENEWED = "US_RENEWED"
    US_REGISTERED_NOT_RENEWED = "US_REGISTERED_NOT_RENEWED"
    US_NO_MATCH = "US_NO_MATCH"
    # ... additional statuses
```

Note: Some statuses are dynamically generated (e.g., `US_PRE_1929`, `FOREIGN_RENEWED_GBR`)

### MatchType

```python
class marc_pd_tool.MatchType(Enum):
    LCCN = "lccn"
    SIMILARITY = "similarity"
    BRUTE_FORCE_WITHOUT_YEAR = "brute_force_without_year"
```

## Advanced Usage

### Custom Configuration

```python
from marc_pd_tool import MarcCopyrightAnalyzer, ConfigLoader

# Load custom configuration
config = ConfigLoader("custom_config.json")

# Create analyzer with custom config
analyzer = MarcCopyrightAnalyzer(config_path="custom_config.json")
```

### Direct Data Loading

```python
from marc_pd_tool import (
    MarcLoader,
    CopyrightDataLoader,
    RenewalDataLoader,
    DataMatcher
)

# Load data directly
marc_loader = MarcLoader()
publications = marc_loader.load_marc_file("catalog.xml")

copyright_loader = CopyrightDataLoader("nypl-reg/xml/")
copyright_data = copyright_loader.load_all_copyright_data(min_year=1950)

renewal_loader = RenewalDataLoader("nypl-ren/data/")
renewal_data = renewal_loader.load_all_renewal_data(min_year=1950)

# Create matcher and process
matcher = DataMatcher()
for pub in publications:
    matches = matcher.find_matches(pub, copyright_data, renewal_data)
```

### Cache Management

```python
from marc_pd_tool import CacheManager

# Create cache manager
cache = CacheManager(".marcpd_cache")

# Clear specific cache
cache.clear_cache("registration_index")

# Clear all caches
cache.clear_all_caches()

# Check cache status
if cache.is_cached("registration_index"):
    print("Registration index is cached")
```

### Ground Truth Analysis

```python
from marc_pd_tool import MarcCopyrightAnalyzer

analyzer = MarcCopyrightAnalyzer()

# Extract ground truth for threshold optimization
ground_truth_pairs, stats = analyzer.extract_ground_truth(
    marc_path="catalog.xml",
    options={"score_everything_mode": True}
)

print(f"MARC records with LCCN: {stats.marc_with_lccn}")
print(f"Registration matches: {stats.registration_matches}")
print(f"Renewal matches: {stats.renewal_matches}")

# Export ground truth for analysis
analyzer.export_ground_truth_analysis(
    ground_truth_pairs,
    output_path="ground_truth.csv"
)
```

### Streaming Large Datasets

```python
from marc_pd_tool import MarcCopyrightAnalyzer

analyzer = MarcCopyrightAnalyzer()

# Process large dataset with streaming
results = analyzer.analyze_marc_file_streaming(
    marc_path="huge_catalog.xml",
    batch_size=1000,
    temp_dir="/data/temp",
    options={"us_only": True}
)
```

## Examples

### Batch Processing Multiple Files

```python
from pathlib import Path
from marc_pd_tool import MarcCopyrightAnalyzer

analyzer = MarcCopyrightAnalyzer()

# Pre-load indexes once
analyzer.load_and_index_data(
    copyright_dir="nypl-reg/xml/",
    renewal_dir="nypl-ren/data/",
    min_year=1950,
    max_year=1970
)

# Process multiple files
marc_files = Path("marc_data").glob("*.xml")
for marc_file in marc_files:
    results = analyzer.analyze_marc_file(str(marc_file))
    output_name = marc_file.stem + "_results.csv"
    results.export_to_csv(output_name)
```

### Custom Threshold Analysis

```python
from marc_pd_tool import MarcCopyrightAnalyzer

# Test different threshold combinations
thresholds = [
    {"title": 30, "author": 20},
    {"title": 40, "author": 30},
    {"title": 50, "author": 40},
]

analyzer = MarcCopyrightAnalyzer()

for threshold_set in thresholds:
    options = {
        "title_threshold": threshold_set["title"],
        "author_threshold": threshold_set["author"],
        "score_everything_mode": True
    }
    
    results = analyzer.analyze_marc_file(
        "test_data.xml",
        options=options
    )
    
    print(f"Thresholds {threshold_set}: "
          f"{results.statistics.registration_matches} matches")
```

### Filtering and Analysis

```python
from marc_pd_tool import MarcCopyrightAnalyzer

analyzer = MarcCopyrightAnalyzer()

# Analyze only US books from 1950s
results = analyzer.analyze_marc_file(
    "catalog.xml",
    options={
        "us_only": True,
        "min_year": 1950,
        "max_year": 1959,
        "formats": ["csv", "xlsx", "json"]
    }
)

# Get specific categories
pd_books = results.get_public_domain_publications()
for book in pd_books[:10]:
    print(f"{book.title} ({book.year}): {book.copyright_status}")
```

## Error Handling

```python
from marc_pd_tool import MarcCopyrightAnalyzer
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)

try:
    analyzer = MarcCopyrightAnalyzer()
    results = analyzer.analyze_marc_file("catalog.xml")
except FileNotFoundError as e:
    print(f"File not found: {e}")
except Exception as e:
    print(f"Analysis failed: {e}")
```

## Performance Considerations

1. **Use caching**: First run builds indexes; subsequent runs are much faster
1. **Filter by year**: Reduces data loading and processing time
1. **Adjust batch size**: Larger batches can improve throughput
1. **Set worker count**: Use `num_processes` based on available cores
1. **Enable streaming**: For datasets over 1M records

## Thread Safety

The `MarcCopyrightAnalyzer` class is not thread-safe. Create separate instances for concurrent processing or use multiprocessing instead of threading.

## Memory Management

For large datasets:

- Use streaming mode with `analyze_marc_file_streaming()`
- Set appropriate `batch_size` (100-500 records)
- Clear caches between runs if processing different year ranges
- Monitor memory with system tools

## Compatibility

- Python 3.13.5 or later required
- No backward compatibility guarantees

## Testing and Quality Assurance

When modifying the matching algorithm:

1. Run the standard test suite: `pdm test`
1. Run scoring tests: `pdm run test-regression`
1. Update baselines if changes are intentional: `pdm run python scripts/generate_baseline_scores.py`

See [tests/scoring/README.md](../tests/scoring/README.md) for details on the scoring test system.
