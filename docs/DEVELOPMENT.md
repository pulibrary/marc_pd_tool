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
├── compare.py              # Main entry point
└── analyze_ground_truth_scores.py
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
pdm run python -m marc_pd_tool --marcxml data.xml [options]
# Detach: Ctrl+A, D
# Reattach: screen -r marc_processing
```

### tmux
```bash
tmux new -s marc_processing
pdm run python -m marc_pd_tool --marcxml data.xml [options]
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
2. **Year filtering**: ±tolerance (default 2 years)
3. **Threshold filtering**: Title, author, publisher minimums
4. **Scoring**: Adaptive weights based on available data
5. **Early exit**: Stop at 95%+ title and 90%+ author match

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

Uses multiprocessing for CPU-bound work:

1. Main process builds/loads indexes
2. Worker processes get index references via cache
3. Batches distributed across workers
4. Results collected and merged

Benefits:
- Linear scaling with CPU cores
- Process isolation for fault tolerance
- Efficient memory usage via shared cache

### Caching Strategy

Three-tier caching system:

1. **Indexes**: If valid, skip data loading entirely
2. **Parsed data**: If valid, skip file parsing
3. **MARC batches**: Reuse across multiple runs

Cache keys include:
- File modification times
- Configuration hash
- Year ranges
- Filter options

### Memory Optimizations

- `__slots__` on all data classes
- Lazy property evaluation
- Compact index structures
- Bounded caches (LRU, max sizes)
- None vs empty string optimization

Result: 30-50% memory reduction

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
2. Add to `DataMatcher` initialization
3. Update `Publication` model if needed
4. Add caching support in `CacheManager`
5. Write tests

### Modifying Matching Logic

1. Update `DataMatcher.find_best_match()`
2. Add new thresholds to `config.json`
3. Update CLI arguments in `cli/main.py`
4. Test with ground truth data
5. Update `PIPELINE.md` documentation

### Adding an Export Format

1. Create exporter in `exporters/`
2. Implement `BaseExporter` interface
3. Add format option to CLI
4. Update `api.py` export logic
5. Add tests

### Performance Profiling

```bash
# Profile with cProfile
pdm run python -m cProfile -o profile.stats scripts/compare.py [options]

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
pdm run python -m marc_pd_tool --debug [options]
```

### Check Cache Status

```bash
# View cache contents
ls -la .marcpd_cache/

# Force cache rebuild
pdm run python -m marc_pd_tool --force-refresh [options]

# Disable cache for testing
pdm run python -m marc_pd_tool --disable-cache [options]
```

### Common Issues

1. **Missing matches**: Lower thresholds, check year ranges
2. **Memory errors**: Reduce batch size or worker count
3. **Slow startup**: Cache may be invalid, check with `--debug`
4. **Unicode errors**: Check source file encoding

## Code Style

- One class per file (usually)
- Full imports: `from module import Class`
- Type hints on all public APIs
- Docstrings for public methods
- `__slots__` for data classes
- Early returns over nested conditions

## Contributing

1. Fork repository
2. Create feature branch
3. Write tests first
4. Ensure all tests pass
5. Run `pdm format`
6. Update documentation
7. Submit pull request

## Additional Resources

- `README.md` - User guide
- `docs/GUIDE.md` - Usage examples
- `docs/PIPELINE.md` - Processing pipeline details
- `docs/REFERENCE.md` - CLI reference
- `projects/` - Future development plans