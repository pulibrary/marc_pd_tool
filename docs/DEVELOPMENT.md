# Development Guide

## Overview

This guide covers the architecture and key concepts for developers working with the MARC Copyright Analysis Tool.

## Package Architecture

```
marc_pd_tool/
├── api.py                   # Public API interface
├── data/                    # Core data models
│   ├── enums.py            # Copyright status and country enums
│   ├── publication.py      # Publication model with match tracking
│   └── ground_truth.py     # Ground truth analysis structures
├── loaders/                 # Data loading
│   ├── copyright_loader.py # Copyright XML parsing
│   ├── renewal_loader.py   # Renewal TSV parsing
│   └── marc_loader.py      # MARC XML parsing with filtering
├── processing/              # Matching logic
│   ├── indexer.py          # Multi-key index building
│   ├── matching_engine.py  # Core matching and batch processing
│   ├── similarity_calculator.py     # Similarity scoring
│   ├── text_processing.py  # Text normalization and language support
│   ├── ground_truth_extractor.py   # LCCN-based ground truth
│   └── score_analyzer.py   # Threshold optimization
├── exporters/               # Output formats
│   ├── csv_exporter.py
│   ├── xlsx_exporter.py
│   └── json_exporter.py
├── utils/                   # Utilities
│   ├── types.py            # Type definitions
│   ├── text_utils.py       # Text processing helpers
│   ├── marc_utilities.py   # MARC-specific utilities
│   └── publisher_utils.py  # Publisher normalization
├── infrastructure/          # System support
│   ├── cache_manager.py    # Persistent caching
│   ├── config_loader.py    # Configuration management
│   └── run_index_manager.py # Run tracking
└── cli/
    └── main.py             # Command-line interface

scripts/
└── analyze_ground_truth_scores.py  # Ground truth analysis tool
```

## Getting Started

### Prerequisites

- Python 3.13.5+
- PDM package manager
- 4GB+ RAM
- Multi-core CPU recommended

### Clone with Submodules

The repository includes copyright data as submodules:

```bash
git clone --recurse-submodules https://github.com/NYPL/marc_pd_tool.git
cd marc_pd_tool

# Or if already cloned:
git submodule update --init --recursive
```

Submodules:

- `nypl-reg/` - Copyright registrations (1923-1977)
- `nypl-ren/` - Copyright renewals (1950-1991)

### Development Setup

```bash
pdm install
pdm run pytest  # Run tests
pdm format      # Format code
```

## Running on Servers

For long-running processes (3-10 hours), use screen or tmux:

### GNU Screen

```bash
screen -S marc_processing
pdm run marc-pd-tool --marcxml data.xml [options]
# Detach: Ctrl+A, D
# Reattach: screen -r marc_processing
```

### tmux

```bash
tmux new -s marc_processing
pdm run marc-pd-tool --marcxml data.xml [options]
# Detach: Ctrl+B, D
# Reattach: tmux attach -t marc_processing
```

## Core Classes

### Publication (`data/publication.py`)

Central data model storing both original and normalized text:

```python
class Publication:
    # Original data (preserved for output)
    original_title: str
    original_author: str         # 245$c transcribed
    original_main_author: str    # 1xx controlled
    
    # Normalized data (for matching) - lazy properties
    @property
    def title(self) -> str
    @property
    def author(self) -> str
    
    # Match results
    registration_match: Optional[MatchResult]
    renewal_match: Optional[MatchResult]
    
    # Status
    country_classification: CountryClassification
    copyright_status: CopyrightStatus
```

Key features:

- Dual author support (245$c and 1xx fields)
- Lazy normalization for memory efficiency
- Single best match stored per type
- `__slots__` for memory optimization

### MatchResult (`data/publication.py`)

Stores match details:

```python
@dataclass(slots=True)
class MatchResult:
    matched_title: str
    matched_author: str
    similarity_score: float
    title_score: float
    author_score: float
    publisher_score: float
    year_difference: int
    source_id: str
    match_type: str  # "lccn" or "similarity"
```

### CacheManager (`infrastructure/cache_manager.py`)

Manages persistent caches to avoid re-parsing data:

```
.marcpd_cache/
├── copyright_data_[year_range]/   # Parsed copyright records
├── renewal_data_[year_range]/     # Parsed renewal records
├── marc_data/                     # Parsed MARC records
├── indexes/                       # Built search indexes
└── generic_detector/              # Title frequency data
```

Features:

- Automatic invalidation on file changes
- Configuration-aware (rebuilds on threshold changes)
- Year-range specific caching
- 85% startup time reduction

### DataMatcher (`processing/matching_engine.py`)

Core matching engine with multi-stage filtering:

1. **Index lookup**: Find candidates using title/author keys
1. **Year filtering**: ±tolerance (default 2 years)
1. **Threshold filtering**: Title, author, publisher minimums
1. **Scoring**: Adaptive weights based on available data
1. **Early exit**: Stop at 95%+ title and 90%+ author match

Key methods:

- `find_best_match()`: Single record matching
- `process_batch()`: Parallel batch processing

## Key Concepts

### Country Classification

Uses Library of Congress MARC country codes (008 field positions 15-17):

- **US codes**: 67 codes including state codes (xxu, nyu, cau, etc.)
- **Classification**: US, NON_US, or UNKNOWN
- **Impact**: Determines copyright analysis algorithm

### Generic Title Detection

Identifies non-distinctive titles to adjust scoring weights:

- **Patterns**: "collected works", "complete works", "poems", etc.
- **Frequency**: Titles appearing frequently in dataset
- **Language**: Currently English-only to avoid false positives
- **Effect**: Reduces title weight from 60% to 30%

### Multi-Key Indexing

Reduces search space from millions to thousands:

- **Title keys**: Single words, 2-word, 3-word combinations
- **Author keys**: Surname, surname+first, full name variants
- **Year keys**: Exact year ± tolerance
- **CompactIndexEntry**: Memory-efficient storage

### Text Normalization

See `docs/PIPELINE.md` for complete normalization details:

- Unicode normalization (é → e)
- Abbreviation expansion (dept → department)
- Stopword removal (language-specific)
- Field-specific rules (title, author, publisher)

## Performance Architecture

### Parallel Processing

Uses multiprocessing with platform-specific optimizations:

#### Linux (fork-based)

1. Main process loads indexes into memory BEFORE creating worker pool
1. Workers inherit shared memory via copy-on-write (fork)
1. No duplicate loading - true memory sharing
1. Batches are pickled to disk to reduce memory footprint
1. Workers load only active batch from pickle file

#### macOS/Windows (spawn-based)

1. Each worker loads indexes independently during initialization
1. Indexes loaded once per worker, not per batch
1. Batches are pickled to disk to reduce memory footprint
1. Workers load only active batch from pickle file

Benefits:

- Linear scaling with CPU cores
- Process isolation for fault tolerance
- **Memory efficient**:
  - Linux: True memory sharing via fork
  - macOS/Windows: Load-once-per-worker pattern
  - All platforms: Only active batch in RAM
- **Dynamic worker recycling**: Prevents memory leaks
- **Platform optimized**: Leverages OS-specific features

### Caching Strategy

Multi-tier caching system:

1. **Indexes**: If valid, skip data loading entirely
1. **Parsed data**: If valid, skip file parsing
1. **MARC batches**: Pickled to temporary files during processing
1. **Year-filtered data**: Separate caches for different year ranges

Cache keys include:

- File modification times
- Configuration hash
- Year ranges (enables loading only relevant data)
- Filter options

**Year Filtering Optimization**:

- When `--min-year`/`--max-year` are used, only relevant copyright/renewal data is loaded
- Dramatically reduces memory usage and startup time
- Separate caches maintained for different year ranges

### Memory Optimizations

- `__slots__` on all data classes
- Lazy property evaluation
- Compact index structures
- Bounded caches (LRU, max sizes)
- None vs empty string optimization
- **Batch pickling**: Only active batch in RAM
- **Platform-specific sharing**:
  - Linux: Copy-on-write via fork
  - macOS/Windows: Load-once pattern
- **Year filtering**: Load only needed data

Result: 50-70% memory reduction

## Configuration

### config.json

Controls matching behavior:

```json
{
  "default_thresholds": {
    "title": 40,
    "author": 30,
    "publisher": 30,
    "year_tolerance": 1,
    "early_exit_title": 95,
    "early_exit_author": 90
  },
  "processing": {
    "batch_size": 200,
    "brute_force_missing_year": false
  },
  "generic_title_detection": {
    "frequency_threshold": 10,
    "disabled": false
  }
}
```

### wordlists.json

Centralized text processing data:

```json
{
  "stopwords": {
    "general": ["the", "a", "an"],
    "publisher": ["inc", "corp"],
    "title": ["by", "in", "on"]
  },
  "stopwords_by_language": {
    "eng": [...],
    "fre": [...],
    "ger": [...]
  },
  "abbreviations": {
    "bibliographic": {
      "dept": "department",
      "univ": "university"
    }
  },
  "patterns": {
    "generic_titles": ["collected works"]
  }
}
```

## API Usage

### Basic Example

```python
from marc_pd_tool import MarcCopyrightAnalyzer

# Initialize analyzer
analyzer = MarcCopyrightAnalyzer(
    config_path="config.json",
    cache_dir=".marcpd_cache"
)

# Process MARC file
results = analyzer.analyze_marc_file(
    "data.xml",
    copyright_dir="nypl-reg/xml",
    renewal_dir="nypl-ren/data",
    output_path="results.csv",
    options={
        "us_only": True,
        "min_year": 1950,
        "max_year": 1960
    }
)

# Access results
print(f"Total: {results.statistics['total_records']}")
print(f"Matches: {results.statistics['registration_matches']}")
```

### Ground Truth Analysis

```python
# Extract LCCN-verified matches
pairs, stats = analyzer.extract_ground_truth(
    "marc_file.xml",
    min_year=1950,
    max_year=1960
)

# Analyze similarity scores
analyzer.analyze_ground_truth_scores(pairs)
```

## Common Development Tasks

### Adding a New Data Source

1. Create loader in `loaders/` following existing patterns
1. Add to `DataMatcher` initialization
1. Update `Publication` model if needed
1. Add caching support in `CacheManager`
1. Update worker initialization in `matching_engine.py`
1. Write tests

### Debugging Multiprocessing Issues

1. **Check platform**: `multiprocessing.get_start_method()`
1. **Linux memory issues**: Verify indexes loaded before fork
1. **Worker crashes**: Check pickle file creation/cleanup
1. **Memory leaks**: Adjust `maxtasksperchild` dynamically
1. **Use debug logging**: Shows worker initialization details

### Performance Monitoring

#### Batch Processing Metrics

The system tracks and reports per-batch performance metrics:

- **Records per second (rec/s)**: Calculated using actual batch processing time
- **Match counts**: Registration and renewal matches found per batch
- **Processing time**: Each batch tracks its own processing duration

Example log output:

```
Batch 1/10 complete: 5 reg, 3 ren matches (152.3 rec/s)
Batch 2/10 complete: 2 reg, 0 ren matches (143.7 rec/s)
```

The `processing_time` is tracked within each worker process and included in the batch statistics, ensuring accurate per-batch performance metrics regardless of parallel execution order.

### Modifying Matching Logic

1. Update `DataMatcher.find_best_match()`
1. Add new thresholds to `config.json`
1. Update CLI arguments in `cli.py`
1. Test with ground truth data
1. Update `PIPELINE.md` documentation
1. Ensure changes work with batch pickling
1. Test on both Linux (fork) and macOS (spawn)

### Adding an Export Format

1. Create exporter in `exporters/`
1. Implement `BaseExporter` interface
1. Add format option to CLI
1. Update `api.py` export logic
1. Add tests

### Performance Profiling

```bash
# Profile with cProfile
pdm run python -m cProfile -o profile.stats -m marc_pd_tool [options]

# Analyze results
pdm run python -c "import pstats; p = pstats.Stats('profile.stats'); p.sort_stats('cumulative').print_stats(20)"
```

## Testing

### Test Structure

```
tests/
├── fixtures/           # Test data files
├── test_data/         # Data model tests
├── test_loaders/      # Loader tests
├── test_processing/   # Matching logic tests
├── test_exporters/    # Export format tests
├── test_utils/        # Utility tests
└── test_integration/  # End-to-end tests
```

### Running Tests

```bash
pdm test                    # All tests
pdm run pytest -k "lccn"   # Pattern match
pdm run pytest -x          # Stop on first failure
pdm run pytest --lf        # Last failed only
```

### Key Test Categories

- **Unit tests**: Individual functions/methods
- **Integration tests**: Component interaction
- **Property tests**: Mathematical properties (Hypothesis)
- **Performance tests**: Speed and memory usage

## Debugging Tips

### Enable Debug Logging

```bash
pdm run marc-pd-tool --debug [options]
```

### Check Cache Status

```bash
# View cache contents
ls -la .marcpd_cache/

# Force cache rebuild
pdm run marc-pd-tool --force-refresh [options]

# Disable cache for testing
pdm run marc-pd-tool --disable-cache [options]
```

### Common Issues

1. **Missing matches**: Lower thresholds, check year ranges
1. **Memory errors**: Reduce batch size or worker count
1. **Slow startup**: Cache may be invalid, check with `--debug`
1. **Unicode errors**: Check source file encoding

## Code Style

- One class per file (usually)
- Full imports: `from module import Class`
- Type hints on all public APIs
- Docstrings for public methods
- `__slots__` for data classes
- Early returns over nested conditions

## Contributing

1. Fork repository
1. Create feature branch
1. Write tests first
1. Ensure all tests pass
1. Run `pdm format`
1. Update documentation
1. Submit pull request

## Recent Architecture Improvements (2025)

### Linux Stability Fix

Resolved worker process instability on Linux by implementing platform-specific memory sharing:

- **Problem**: Workers dying with "broken pipe" errors due to memory pressure
- **Solution**: Load indexes in main process before fork() on Linux
- **Result**: True memory sharing via copy-on-write, stable processing

### Batch Pickling Implementation

Reduced memory footprint by pickling MARC batches to disk:

- **Problem**: Entire dataset (130K+ records) held in RAM
- **Solution**: Pickle batches to temp files, load on demand
- **Result**: Only active batch in memory, 70%+ RAM reduction

### Dynamic Worker Recycling

Implemented intelligent worker lifecycle management:

- **Calculation**: `max(50, min(200, batches_per_worker // 3))`
- **Range**: 50-200 tasks per worker based on workload
- **Purpose**: Prevents memory leaks while maintaining efficiency

### Year Filtering Enhancement

Optimized data loading based on year ranges:

- **Smart loading**: Only loads copyright/renewal data for requested years
- **Logging**: Tracks why records are filtered (no year, out of range, non-US)
- **Copyright notation**: Now handles "c1955" format correctly

## Additional Resources

- `README.md` - User guide
- `docs/GUIDE.md` - Usage examples
- `docs/PIPELINE.md` - Processing pipeline details
- `docs/REFERENCE.md` - CLI reference
- `projects/` - Future development plans
