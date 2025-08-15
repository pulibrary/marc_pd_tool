# Technical Architecture

This document describes the software architecture, design patterns, and performance optimizations used in the MARC Copyright Status Analysis Tool.

## Architecture Pattern: Hexagonal (Ports & Adapters)

The codebase follows the hexagonal architecture pattern, also known as ports and adapters. This pattern separates business logic from external concerns, making the system more maintainable, testable, and adaptable to change.

### Layer Organization

#### Core (Domain)

Pure business logic and entities with no external dependencies.

- `core/domain/`: Domain entities (Publication, MatchResult, copyright logic, enums)
- `core/types/`: Type definitions, protocols, type aliases

#### Application

Use cases and application services that orchestrate domain logic.

- `application/services/`: High-level services (analysis, indexing, matching)
- `application/processing/`: Core algorithms (matching engine, similarity calculator, indexer)
- `application/models/`: Data transfer objects and application-specific models

#### Adapters (Ports)

External interfaces that adapt the application to the outside world.

- `adapters/api/`: Public Python API for library usage
- `adapters/cli/`: Command-line interface
- `adapters/exporters/`: Output format adapters (CSV, XLSX, JSON, HTML)

#### Infrastructure

Technical implementations of external concerns.

- `infrastructure/persistence/`: Data loaders for MARC, copyright, and renewal data
- `infrastructure/cache/`: Caching implementation using pickle serialization
- `infrastructure/config/`: Configuration management with Pydantic models
- `infrastructure/logging/`: Centralized logging setup

#### Shared

Cross-cutting utilities and mixins used across layers.

- `shared/utils/`: Text processing, MARC utilities, helper functions
- `shared/mixins/`: Reusable mixins for common functionality

### Dependency Flow

Dependencies flow inward: adapters depend on application, application depends on core, but core depends on nothing external. This ensures business logic remains pure and testable.

```
Adapters → Application → Core
    ↓           ↓         ↑
Infrastructure  Shared ───┘
```

## Text Normalization Pipeline

The text normalization process is critical for accurate matching. Based on analysis of the actual code implementation:

### Full Normalization Pipeline (for matching)

1. **Unicode Normalization** (`marc_pd_tool.shared.utils.text_utils.normalize_unicode`):

   - Fixes known UTF-8/Latin-1 encoding corruptions
   - Normalizes to NFC form (canonical composition)
   - Converts accented characters to ASCII using unidecode
   - Also uses: `marc_pd_tool.shared.utils.text_utils.ascii_fold`

1. **Case Folding**:

   - Converts all text to lowercase for comparison
   - Performed inline in `marc_pd_tool.application.processing.similarity_calculator.SimilarityCalculator`

1. **Abbreviation Expansion** (`marc_pd_tool.application.processing.text_processing.expand_abbreviations`):

   - Expands common bibliographic abbreviations
   - Uses wordlists.json for comprehensive abbreviation dictionary
   - Examples: "Co." → "Company", "Inc." → "Incorporated"

1. **Number Normalization** (`marc_pd_tool.application.processing.number_normalizer.NumberNormalizer`):

   - Roman numerals to Arabic: "XIV" → "14"
   - Ordinals to numbers: "1st" → "1", "third" → "3"
   - Word numbers to digits: "twenty-five" → "25"
   - Language-specific number words supported

1. **Stopword Removal** (`marc_pd_tool.application.processing.custom_stopwords.CustomStopwordRemover`):

   - Field-specific stopwords (title, author, publisher)
   - Language-specific stopwords (English, French, German, Spanish, Italian)
   - Based on ground truth analysis of actual copyright data

1. **Word Stemming** (`marc_pd_tool.application.processing.text_processing.MultiLanguageStemmer`):

   - Reduces words to root form using Snowball stemmer
   - Language-aware stemming for supported languages
   - Example: "publishing" → "publish", "edited" → "edit"

1. **Fuzzy Matching** (`fuzzywuzzy.fuzz`):

   - Token sort ratio for order-independent comparison
   - Handles minor spelling variations and word order differences
   - Called within `marc_pd_tool.application.processing.similarity_calculator.SimilarityCalculator`

### Minimal Cleanup (for storage)

The `marc_pd_tool.core.domain.publication.Publication` domain entity performs only minimal cleanup:

- Whitespace normalization
- Bracketed content removal for titles using `marc_pd_tool.shared.utils.text_utils.remove_bracketed_content`

This separation ensures the domain layer stores data close to its original form while the application layer handles full normalization for matching.

## Performance Optimizations

### Multiprocessing Strategy

The tool uses Python's multiprocessing module for parallel processing, with platform-specific optimizations:

#### Linux (fork-based)

- Indexes loaded once in main process
- Shared memory through fork() system call
- Zero-copy access to read-only indexes
- Most memory-efficient approach

#### macOS/Windows (spawn-based)

- Indexes pickled and passed to workers
- Higher memory overhead but necessary for spawn
- Worker process recycling to manage memory

### Memory Management

#### Batch Processing with Pickling

```python
# Batches are pickled to disk to reduce memory footprint
batch_file = f"{temp_dir}/batch_{batch_num}.pkl"
with open(batch_file, 'wb') as f:
    pickle.dump(batch, f)

# Workers load only their assigned batch
with open(batch_file, 'rb') as f:
    batch = pickle.load(f)
```

This approach keeps only the active batch in memory rather than the entire dataset.

#### Index Caching

- Copyright and renewal indexes cached to disk (~2GB)
- 85% reduction in startup time (10 minutes → 30 seconds)
- Cache key includes year range for filtered loading
- Automatic cache invalidation on data structure changes

#### Worker Process Management

- Dynamic `maxtasksperchild` based on batch size
- Prevents memory leaks from long-running workers
- Automatic process recycling after N tasks

### Data Structure Optimizations

#### Memory-Efficient Classes

```python
class Publication:
    __slots__ = ['_title', '_author', '_year', '_publisher', ...]
```

Using `__slots__` reduces memory overhead by ~50% for frequently instantiated classes.

#### Static Methods

Methods that don't need instance state are marked `@staticmethod` to avoid instance overhead.

#### Dataclasses

Using `@dataclass` for data containers provides efficient initialization and reduces boilerplate.

### Indexing Strategy

#### Multi-Key Word Indexing

Instead of comparing every record against every other record (O(n²)), the tool uses word-based indexing:

1. Build inverted index: word → list of publications
1. For each MARC record, look up its words in index
1. Score only publications that share words
1. Reduces comparisons by 10-50x

#### Year-Filtered Loading

- Load only copyright/renewal data within specified year range
- Reduces memory usage and processing time
- Separate caches for different year ranges

### Parallel Processing Pipeline

```python
# Main process
analyzer = MarcCopyrightAnalyzer(args)
analyzer.load_and_index_data()  # Load once

# Parallel batch processing
with Pool(max_workers) as pool:
    for batch_file in batch_files:
        pool.apply_async(process_batch, (batch_file, shared_data))
```

Each worker processes an independent batch, eliminating inter-process communication overhead.

## Configuration System

### Pydantic Models

Configuration uses Pydantic for validation and type safety:

```python
class ThresholdConfig(BaseModel):
    title: int = Field(40, ge=0, le=100)
    author: int = Field(30, ge=0, le=100)
    year_tolerance: int = Field(1, ge=0, le=5)
```

### Hierarchical Configuration

- Default values in Pydantic models
- Override via config.json
- Override via command-line arguments (highest priority)

### Wordlists Integration

The `wordlists.json` file centralizes:

- Stopwords by language and field
- Abbreviation mappings
- Generic title patterns
- Unicode corruption fixes

## Testing Strategy

### Test Organization

Tests mirror the hexagonal architecture:

- `tests/test_core/`: Domain logic tests
- `tests/test_application/`: Service and processing tests
- `tests/test_adapters/`: CLI and API tests
- `tests/test_infrastructure/`: Loader and cache tests

### Test Coverage

- 86% overall coverage
- 1059 tests passing
- Property-based testing for data access
- Integration tests for end-to-end workflows

### Mocking Strategy

Tests use dependency injection and mocking to isolate layers:

```python
mock_config = Mock(spec=ConfigLoader)
calculator = SimilarityCalculator(config=mock_config)
```

## Error Handling

### Graceful Degradation

- Missing data fields don't crash processing
- Malformed records logged and skipped
- Partial matches still reported

### Comprehensive Logging

- Structured logging with levels
- Performance metrics per batch
- Detailed error diagnostics
- Run summary statistics

## Scalability Considerations

### Streaming Mode

For very large datasets (>1M records):

- Incremental MARC parsing
- Batch serialization to disk
- Constant memory usage regardless of input size

### Cache Management

- Automatic cache invalidation
- Year-range specific caches
- Configurable cache directory
- Force refresh option

### Resource Limits

- Configurable worker count
- Batch size tuning
- Memory monitoring
- Graceful handling of resource exhaustion

## Future Architecture Considerations

### Potential Improvements

1. **Async I/O**: Could improve I/O-bound operations
1. **Database Backend**: For persistent storage of results
1. **Distributed Processing**: Support for cluster computing
1. **Plugin Architecture**: Extensible matching algorithms

### Maintaining Architecture Integrity

- Keep domain logic pure and free of I/O
- Maintain clear layer boundaries
- Use dependency injection for testability
- Document architectural decisions
- Regular refactoring to prevent architectural drift
