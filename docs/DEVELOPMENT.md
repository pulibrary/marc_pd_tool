# Development Guide: Code Architecture and Performance Optimizations

## Overview

This document explains the code architecture, design decisions, and performance optimizations in the MARC Copyright Analysis Tool for developers who need to understand, maintain, or extend the system.

## 1. Package Architecture

### Modular Design

The codebase is organized as a Python package with logical sub-packages (one class per file):

```
marc_pd_tool/
├── data/                    # Core data models
│   ├── __init__.py
│   ├── enums.py           # Copyright status and country classification enums
│   └── publication.py      # Publication data model with dual author support and match tracking
├── loaders/                 # Data loading components
│   ├── __init__.py
│   ├── copyright_loader.py # Copyright registration data loading
│   ├── renewal_loader.py   # Renewal data loading (TSV format)
│   └── marc_loader.py      # MARC XML data loading with country detection
├── processing/              # Core processing logic (word-based matching)
│   ├── __init__.py
│   ├── indexer.py                   # Publication indexing with compact data structures
│   ├── matching_engine.py           # Matching engine and batch processing
│   ├── similarity_calculator.py     # Similarity scoring for matching
│   └── text_processing.py           # Text processing utilities, language support, and generic title detection
├── exporters/               # Output generation
│   ├── __init__.py
│   ├── csv_exporter.py     # CSV export functionality for match results
│   └── xlsx_exporter.py    # Excel export functionality with multi-tab organization (optional)
├── utils/                   # Utility functions
│   ├── __init__.py
│   ├── text_utils.py       # Text processing utilities (normalize_text, extract_year, etc.)
│   ├── marc_utilities.py   # MARC data processing utilities and constants
│   ├── publisher_utils.py  # Publisher-specific text processing functions
│   └── types.py            # Type definitions and protocols
├── infrastructure/          # System support
│   ├── __init__.py
│   ├── cache_manager.py    # Persistent data cache system for performance optimization
│   ├── config_loader.py    # Configuration loading and management
│   └── run_index_manager.py # Run index tracking for logging and metrics
├── cli/                     # Command-line interface
│   ├── __init__.py
│   └── main.py             # CLI logic (extracted from compare.py)
├── analysis/                # LCCN analysis and ground truth tools
│   ├── __init__.py
│   ├── ground_truth_extractor.py # LCCN ground truth pair extraction
│   └── score_analyzer.py   # Similarity score analysis and threshold optimization
└── __init__.py             # Package interface with public API exports
scripts/
├── compare.py               # Main copyright analysis script (calls cli/main.py)
└── analyze_ground_truth_scores.py # LCCN ground truth analysis tool
```

## Getting Started

### Clone with Submodules

**Critical:** This repository includes the copyright registration and renewal data as git submodules. You must clone with submodules to get the data files:

```bash
git clone --recurse-submodules https://github.com/NYPL/marc_pd_tool.git
cd marc_pd_tool
```

If you already cloned without submodules, initialize them:

```bash
git submodule update --init --recursive
```

**Submodules included:**

- `nypl-reg/` - Copyright registration data (1923-1977) from [NYPL Catalog of Copyright Entries Project](https://github.com/NYPL/catalog_of_copyright_entries_project)
- `nypl-ren/` - Copyright renewal data (1950-1991) from [NYPL CCE Renewals Project](https://github.com/NYPL/cce-renewals)

### Requirements

- **Python 3.13.5+**
- **PDM package manager**
- **Multi-core CPU** recommended for best performance
- **4GB+ RAM** for large datasets

### Code Design Principles

- Each module handles one major concern
- Full imports instead of relative imports
- Comprehensive type hints
- Publication objects maintain both original and normalized data

## 2. Data Model Design

### Publication Class (`data/publication.py`)

The Publication class stores both normalized and original data with dual author support:

```python
class Publication:
    def __init__(self, title, author, main_author, ...):
        # Store both normalized and original data
        self.title = self.normalize_text(title)           # For matching
        self.original_title = title                       # For output
        
        # Dual author support
        self.author = self.normalize_text(author)         # 245$c transcribed
        self.main_author = self.normalize_text(main_author)  # 1xx normalized
        self.original_author = author                     # For output
        self.original_main_author = main_author           # For output
        
        # Match tracking - single best match only
        self.registration_match: Optional[MatchResult] = None
        self.renewal_match: Optional[MatchResult] = None
        
        # Country classification for algorithmic analysis
        self.country_classification = country_classification
        self.copyright_status = CopyrightStatus.COUNTRY_UNKNOWN
```

### MatchResult Class

The MatchResult class stores match information:

```python
@dataclass
class MatchResult:
    matched_title: str
    matched_author: str
    similarity_score: float
    title_score: float
    author_score: float
    year_difference: int
    source_id: str
    source_type: str
    matched_date: str = ""
```

This design allows for:

- Normalized text for matching algorithms
- Original text preserved for output
- **Dual author support**: Both controlled vocabulary (1xx) and transcribed (245$c) authors
- **Enhanced part support**: Full title construction with part numbers and names
- Single best match stored for registration and renewal
- Built-in country classification for copyright analysis

### Country Classification

Uses official Library of Congress MARC country codes:

```python
US_COUNTRY_CODES = {
    "xxu", "cau", "nyu", "ilu", "txu", "flu", "pau", "miu", "ohu", "ncu",
    # ... 67 total codes
}
```

Implementation extracts country code from MARC 008 field positions 15-17:

```python
def extract_country_from_marc_008(field_008: str) -> tuple[str, CountryClassification]:
    if len(field_008) < 18:
        return "", CountryClassification.UNKNOWN
    
    country_code = field_008[15:17].strip()
    classification = (
        CountryClassification.US 
        if country_code.lower() in US_COUNTRY_CODES 
        else CountryClassification.NON_US
    )
    return country_code, classification
```

### Generic Title Detection System (`processing/text_processing.py`)

The system includes sophisticated generic title detection to improve matching accuracy by reducing the weight of non-discriminating titles like "collected works" or "poems":

**Architecture**:

```python
class GenericTitleDetector:
    # Predefined patterns for generic titles
    GENERIC_PATTERNS = {
        "collected works", "complete works", "selected works",
        "poems", "essays", "stories", "plays", "letters",
        "proceedings", "transactions", "papers", "studies"
    }
    
    def is_generic(self, title: str, language_code: str = "") -> bool:
        # Only apply to English titles to prevent false positives
        if not self._is_english_language(language_code):
            return False
        return self._detect_generic(normalized_title)
```

**Detection Methods**:

1. **Pattern Matching**: Recognizes known generic title patterns
1. **Frequency Analysis**: Identifies titles appearing frequently in the dataset
1. **Linguistic Patterns**: Detects short titles with high stopword ratios

**Language Support**: Currently supports English only (language codes 'eng', 'en'). Non-English titles bypass detection to prevent false positives.

**Dynamic Scoring Impact**: When generic titles are detected, scoring weights are adjusted:

- **Normal titles**: title=60%, author=25%, publisher=15%
- **Generic titles**: title=30%, author=45%, publisher=25%

### Author Extraction from MARC 245$c

The system extracts dual author information from both 1xx fields (normalized controlled vocabulary) and 245$c (transcribed statement of responsibility) to maximize matching potential:

**Dual Author Extraction Logic**:

```python
def _extract_from_record(self, record) -> Optional[Publication]:
    # Extract main author from 1xx fields (priority: 100 → 110 → 111)
    main_author = ""
    main_author_elem = record.find(".//datafield[@tag='100']/subfield[@code='a']")
    if main_author_elem is not None:
        main_author = main_author_elem.text
        # Clean dates from personal names (e.g., "Smith, John, 1945-" → "Smith, John")
    elif not main_author:
        # Try 110$a (corporate) then 111$a (meeting names)
        
    # Extract statement of responsibility from 245$c
    author_elem = record.find(".//datafield[@tag='245']/subfield[@code='c']")
    author = author_elem.text if author_elem is not None else ""
```

**Indexing Strategy**:

Since 245$c contains statement of responsibility text (which is typically personal names), the system uses personal name parsing logic for all authors:

- **Personal name parsing**: Surname/given name parsing with initials handling
- **Format handling**: "Last, First" and "First Last" name formats
- **Simplified approach**: One consistent strategy instead of type-specific parsing

### Publisher and Edition Matching

The system extracts and matches publisher and edition information to improve accuracy:

**Publisher Extraction (MARC fields 264$b/260$b)**:

```python
# Try 264 (RDA) first, then fallback to 260 (AACR2)
publisher_elem = record.find(".//datafield[@tag='264']/subfield[@code='b']")
if publisher_elem is None:
    publisher_elem = record.find(".//datafield[@tag='260']/subfield[@code='b']")
```

**Edition Extraction (MARC field 250$a)**:

```python
# Extract edition statement (e.g., "2nd ed.", "Revised edition")
edition_elem = record.find(".//datafield[@tag='250']/subfield[@code='a']")
```

**Publisher Matching Strategies**:

- **Registration matches**: Jaccard similarity with stemmed words (MARC publisher vs registration publisher)
- **Renewal matches**: Jaccard similarity with stemmed words (MARC publisher vs renewal publisher)
- **Threshold**: 30% similarity required when MARC has publisher data

**Edition Indexing**: Used for candidate filtering to distinguish between different editions of the same work, but not scored since copyright datasets lack reliable edition information.

## 3. Performance Optimizations

### 3.1 Multi-Key Indexing System (`indexer.py`)

A brute-force approach with 150K MARC records would require ~375 billion comparisons (150K × 2.5M). Multi-key indexing reduces the search space to thousands of candidates per query.

#### Key Generation Strategy

**Title Keys**:

```python
def generate_title_keys(title: str) -> Set[str]:
    words = extract_significant_words(title, max_words=4)
    keys = set()
    
    # Single word keys
    for word in words:
        if len(word) >= 3:
            keys.add(word)
    
    # Multi-word combinations
    if len(words) >= 2:
        keys.add("_".join(words[:2]))    # First two words
        keys.add("_".join(words[-2:]))   # Last two words
        if len(words) >= 3:
            keys.add("_".join(words[:3])) # First three words
    
    # Note: Metaphone keys removed to reduce false positives
    
    return keys
```

**Author Keys** use simplified personal name parsing for all authors:

```python
def generate_author_keys(author: str) -> Set[str]:
    # Use personal name parsing strategy for all authors
    # since 245$c typically contains personal names
    keys = _generate_personal_name_keys(author_lower)
    
    # Note: Metaphone keys removed to reduce false positives
    
    return keys
```

**Personal Name Keys** (from 245$c):

```python
def _generate_personal_name_keys(author_lower: str) -> Set[str]:
    keys = set()
    
    if "," in author_lower:
        # "Last, First" format
        parts = [p.strip() for p in author_lower.split(",")]
        surname = normalize_text(parts[0])
        given_names = normalize_text(parts[1]).split()
        
        keys.add(surname)                          # Surname only
        keys.add(f"{surname}_{given_names[0]}")    # Surname + First
        keys.add(f"{surname}_{given_names[0][0]}") # Surname + Initial
        keys.add(f"{given_names[0]}_{surname}")    # First + Surname
        
    else:
        # "First Last" format
        words = normalize_text(author_lower).split()
        keys.add(words[-1])                       # Last word as surname
        keys.add(f"{words[0]}_{words[-1]}")       # First + Last
        keys.add(f"{words[-1]}_{words[0]}")       # Last + First
        
    return keys
```

The indexing handles:

- **Personal name parsing**: Consistent strategy for all authors from 245$c
- **Different word orders and formats**: Handles variations in name presentation
- **Smart stopword filtering**: Only significant words used for key generation
- **Multi-level indexing**: Title, author, and year dimensions
- **False positive reduction**: Removed phonetic matching to eliminate excessive false matches

### 3.2 Candidate Filtering Strategy

```python
def find_candidates(self, query_pub: Publication, year_tolerance: int = 2) -> Set[int]:
    # Find candidates by title
    title_candidates = set()
    for key in generate_title_keys(query_pub.title):
        title_candidates.update(self.title_index.get(key, set()))
    
    # Find candidates by author
    author_candidates = set()
    if query_pub.author:
        for key in generate_author_keys(query_pub.author):
            author_candidates.update(self.author_index.get(key, set()))
    
    # Combine with priority: prefer title+author intersection
    if title_candidates and author_candidates:
        intersection = title_candidates & author_candidates
        if intersection:
            return intersection & year_candidates
    
    # Fallback to union if no intersection
    return (title_candidates | author_candidates) & year_candidates
```

This reduces the candidate set from millions to hundreds or thousands.

### 3.3 Early Termination Optimization

```python
def find_best_match(marc_pub, copyright_pubs, ..., early_exit_title=95, early_exit_author=90):
    for copyright_pub in copyright_pubs:
        title_score = calculate_title_similarity(marc_pub, copyright_pub)
        
        if title_score < title_threshold:
            continue
        
        # Author scoring with fuzzy matching
        author_score = calculate_author_similarity(marc_pub, copyright_pub)
        
        combined_score = calculate_combined_score(title_score, author_score, publisher_score)
        
        if combined_score > best_score:
            best_score = combined_score
            best_match = {...}
            
            # Early exit for high-confidence matches (considers both author types)
            has_author_data = (marc_pub.author and copyright_pub.author) or (marc_pub.main_author and copyright_pub.author)
            if (title_score >= early_exit_title and 
                has_author_data and 
                author_score >= early_exit_author):
                break
```

Early termination occurs only when:

- Title score ≥95% AND author score ≥90%
- Either author type (245$c or 1xx) is present with sufficient data
- Uses best score from dual author matching
- Thresholds are configurable

### 3.4 Parallel Processing Architecture

The system uses a sophisticated multi-process architecture with persistent cache optimization:

**Main Process (Index Building & Caching):**

```python
def main():
    # Phase 3.6: Build indexes once and cache persistently
    registration_index = build_index(registration_publications)
    renewal_index = build_index(renewal_publications)
    
    # Cache indexes persistently for worker processes
    if cache_manager:
        cache_manager.cache_indexes(
            copyright_dir, renewal_dir, config_hash,
            registration_index, renewal_index
        )
    
```

**Worker Process (Index Loading & Processing):**

```python
def process_batch(batch_info):
    cache_dir, copyright_dir, renewal_dir, config_hash = batch_info[:4]
    
    # Load pre-built indexes directly from cache
    cache_manager = CacheManager(cache_dir)
    cached_indexes = cache_manager.get_cached_indexes(
        copyright_dir, renewal_dir, config_hash
    )
    registration_index, renewal_index = cached_indexes
    
    # Process MARC records using pre-built indexes
    # No index building overhead per process
```

**Key Architectural Benefits:**

- **Persistent Cache System**: Eliminates duplicate index building across processes
- **Process Isolation**: Each process has independent memory space
- **Fault Tolerance**: Process failures don't crash the entire application
- **Linear Scaling**: Performance scales with CPU cores
- **Memory Efficiency**: Indexes built once, cached persistently for direct access
- **Startup Optimization**: Reduces worker process startup from 30-60s to \<5s

**Performance Impact:**

- **Before**: 30-60 seconds × N processes = 2-4 minutes overhead
- **After**: 30-60 seconds total + direct cache loading = **Faster startup, no temp files**
- **Worker logs**: "Loading indexes from cache"

Uses processes rather than threads because:

- Python's GIL limits thread effectiveness for CPU-bound tasks
- Each process has independent memory space
- Process failures don't crash the entire application
- Scales linearly with CPU cores

### 3.5 Cache-Based Worker Process Loading

**Problem Solved:** The original implementation had each worker process rebuilding identical indexes from the same 2.1M+ registration and 445K+ renewal records, causing massive inefficiency.

**Modern Solution:** Worker processes load indexes directly from the persistent cache system, eliminating redundant serialization and temporary file management.

**Implementation Details:**

**1. Main Process Cache Strategy:**

```python
# Build indexes once and cache persistently
logger.info("Building registration index...")
registration_index = build_index(registration_publications)
logger.info("Building renewal index...")
renewal_index = build_index(renewal_publications)

# Cache indexes persistently (not temporary files)
if cache_manager:
    cache_manager.cache_indexes(
        copyright_dir, renewal_dir, config_hash,
        registration_index, renewal_index
    )

# Pass cache configuration to worker processes
batch_info = (batch_id, marc_batch, cache_dir, copyright_dir, 
              renewal_dir, config_hash, detector_config, ...)
```

**2. Worker Process Cache Loading:**

```python
def process_batch(batch_info):
    cache_dir, copyright_dir, renewal_dir, config_hash = batch_info[2:6]
    
    # Load directly from persistent cache
    cache_manager = CacheManager(cache_dir)
    cached_indexes = cache_manager.get_cached_indexes(
        copyright_dir, renewal_dir, config_hash
    )
    registration_index, renewal_index = cached_indexes
    
    # Process with pre-built indexes (no overhead)
    for marc_pub in marc_batch:
        # ... matching logic
```

**Performance Benefits:**

- **Index building time**: 30-60 seconds for 2.5M+ records (unchanged)
- **Cache loading per worker**: ~1-3 seconds per index (same as before)
- **Eliminated overhead**: No temporary file creation/deletion/cleanup
- **Simplified architecture**: Single consistent caching approach
- **Reduced I/O**: No redundant serialization step
- **Better error handling**: Unified cache validation and recovery

**Architectural Improvements:**

- **No temporary files**: Eliminates file system cleanup complexity
- **Unified caching**: Same persistent cache used throughout application
- **Configuration validation**: Cache invalidation based on matching thresholds
- **--no-cache support**: Temporary worker cache created automatically when needed
- **Better error messages**: Clear cache loading failures with context

### 3.6 Memory Optimization Architecture (January 2025)

**Problem**: High memory usage was causing system crashes and requiring reduced worker counts and batch sizes, limiting processing efficiency and throughput.

**Solution**: Comprehensive memory optimization achieving 30-50% memory reduction through multiple strategies:

#### Phase 1: Publication Data Model Optimization

**`__slots__` Implementation**:

```python
@dataclass(slots=True)
class MatchResult:
    # Reduces per-object overhead by ~40%
    matched_title: str
    matched_author: str
    similarity_score: float
    # ... other fields

class Publication:
    __slots__ = (
        'original_title', 'original_author', 'original_main_author', 
        'pub_date', 'original_publisher', 'original_place', 
        'original_edition', 'original_part_number', 'original_part_name',
        'language_code', 'source', 'source_id', 'full_text', 'year', 
        'country_code', 'country_classification', 'registration_match', 
        'renewal_match', 'generic_title_detected', 'generic_detection_reason', 
        'registration_generic_title', 'renewal_generic_title', 
        'copyright_status', '_cached_title', '_cached_author', 
        '_cached_main_author', '_cached_publisher', '_cached_place', 
        '_cached_edition', '_cached_part_number', '_cached_part_name', 
        '_cached_full_title_normalized'
    )
```

**Lazy Property Caching**:

```python
@property
def title(self) -> str:
    """Normalized title for matching - cached after first access"""
    if self._cached_title is None:
        self._cached_title = normalize_text(self.original_title) if self.original_title else ""
    return self._cached_title
```

**None vs Empty String Optimization**:

```python
# Store None for missing data instead of empty strings (saves memory)
self.original_author = author if author else None
self.original_publisher = publisher if publisher else None
# Properties return "" for None values to maintain API compatibility
```

#### Phase 2: Index Structure Optimization

**Compact Index Entry System**:

```python
class CompactIndexEntry:
    """Memory-efficient container - stores single int or set"""
    __slots__ = ('_data',)
    
    def add(self, pub_id: int) -> None:
        if self._data is None:
            self._data = pub_id  # Single entry as int
        elif isinstance(self._data, int):
            if self._data != pub_id:
                self._data = {self._data, pub_id}  # Convert to set only when needed
        else:
            self._data.add(pub_id)  # Already a set
```

**Before vs After Memory Usage**:

```python
# Before: Always defaultdict(set) - wastes memory for single entries
title_index = defaultdict(set)  # Every entry uses set overhead
title_index["shakespeare"] = {42}  # Set with one item = ~240 bytes

# After: Compact storage based on entry count
title_index = {}  # Regular dict
title_index["shakespeare"] = CompactIndexEntry()  # Single int = ~28 bytes
title_index["hamlet"] = CompactIndexEntry()       # Set only when needed
```

#### Phase 3: Generic Title Detector Optimization

**LRU Cache Implementation**:

```python
class LRUCache:
    """Simple LRU cache with size limit"""
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.cache = OrderedDict()
    
    def get(self, key: str) -> Optional[bool]:
        if key in self.cache:
            self.cache.move_to_end(key)  # Mark as recently used
            return self.cache[key]
        return None

class GenericTitleDetector:
    def __init__(self, cache_size: int = 1000, max_title_counts: int = 50000):
        self.detection_cache = LRUCache(cache_size)  # Bounded cache
        self.max_title_counts = max_title_counts
```

**Automatic Memory Cleanup**:

```python
def add_title(self, title: str) -> None:
    normalized = normalize_text(title)
    if normalized:
        self.title_counts[normalized] += 1
        
        # Prevent unbounded growth
        if len(self.title_counts) > self.max_title_counts:
            self._cleanup_title_counts()  # Keep only most frequent titles

def _cleanup_title_counts(self) -> None:
    """Keep top 80% of limit to avoid frequent cleanups"""
    keep_count = int(self.max_title_counts * 0.8)
    most_common = self.title_counts.most_common(keep_count)
    self.title_counts = Counter(dict(most_common))
    self.detection_cache.clear()  # Invalidate cache
```

#### Performance Impact Achieved

**Memory Reduction**:

- **Publication objects**: ~40% reduction through `__slots__` and lazy caching
- **Index structures**: ~60% reduction for single-entry indexes through CompactIndexEntry
- **Generic detector**: Bounded memory growth prevents crashes
- **Overall**: 30-50% total memory reduction as measured

**Processing Improvements**:

- **Higher batch sizes**: Can process larger batches without memory crashes
- **Better cache locality**: Compact data structures improve CPU cache performance
- **Reduced garbage collection**: Less memory allocation/deallocation overhead
- **Maintained accuracy**: All optimizations preserve identical matching behavior

#### Verification and Testing

**All Tests Pass**: 338+ tests validate that optimizations maintain identical functionality:

- Title/author key generation produces same results
- Index candidate filtering returns identical publication sets
- Publication matching algorithms produce same similarity scores
- Generic title detection behavior unchanged

**Backward Compatibility**: All optimizations are internal implementation changes:

- Public APIs unchanged
- Existing code continues to work without modification
- Same output formats and matching accuracy

### 3.7 Memory Management Strategies (Legacy)

**Streaming XML Parsing**:

```python
def extract_all_batches(self):
    context = ET.iterparse(marc_file, events=("start", "end"))
    for event, elem in context:
        if event == "end" and elem.tag.endswith("record"):
            pub = self._extract_from_record(elem)
            if pub:
                current_batch.append(pub)
            
            # Clear processed elements to prevent memory leaks
            elem.clear()
            root.clear()
```

**Batch Processing**:

- Fixed batch size limits memory usage per process
- Streaming prevents loading entire dataset into memory
- Explicit element clearing prevents memory leaks

### 3.3 Persistent Data Cache System (`cache_manager.py`)

**Problem**: Every application run required parsing 151 XML files + 45 TSV files + rebuilding indexes, taking 5-10 minutes of startup time before any actual comparison work began.

**Solution**: Comprehensive caching system with intelligent invalidation based on file modification times.

#### Cache Architecture

```
.marcpd_cache/
├── copyright_data/
│   ├── metadata.json    # Source paths and modification times
│   └── publications.pkl # Cached CopyrightPublication objects
├── renewal_data/
│   ├── metadata.json
│   └── publications.pkl # Cached RenewalPublication objects  
├── indexes/
│   ├── metadata.json    # Includes configuration hash for validation
│   ├── registration.pkl # Cached registration index
│   └── renewal.pkl      # Cached renewal index
└── generic_detector/
    ├── metadata.json
    └── detector.pkl     # Cached populated GenericTitleDetector
```

#### Cache Validation Strategy

**Modification Time Tracking**: Each cache component stores modification times for all source files/directories:

```python
def _is_cache_valid(self, cache_subdir: str, source_paths: List[str]) -> bool:
    metadata = self._load_metadata(cache_subdir)
    for source_path in source_paths:
        current_mtime = self._get_directory_modification_time(source_path)
        cached_mtime = metadata.get("modification_times", {}).get(source_path)
        if current_mtime > cached_mtime:
            return False  # Cache invalid - rebuild needed
    return True
```

**Configuration-Dependent Caching**: Index cache includes configuration hash to invalidate when matching thresholds change.

**Performance Impact**:

- First run: Normal processing time while building cache
- Subsequent runs: **85% startup time reduction** (5-10 minutes → 10-30 seconds)
- Cache invalidation: Automatic detection when source data changes

#### CLI Options

- `--cache-dir /path/to/cache` - Custom cache location (default: `.marcpd_cache`)
- `--force-refresh` - Bypass cache and rebuild from scratch
- `--no-cache` - Disable caching entirely for one-off runs

## 4. Scoring and Matching Logic

### 4.1 Dynamic Similarity Scoring Strategy

The system uses adaptive scoring weights based on available data and generic title detection:

```python
title_score = calculate_title_similarity(marc_pub, copyright_pub)  # Word-based Jaccard similarity
# Author scoring with fuzzy matching
author_score = calculate_author_similarity(marc_pub, copyright_pub)
publisher_score = calculate_publisher_similarity(marc_pub, copyright_pub)

# Dynamic scoring based on generic title detection and available data
if marc_pub.publisher and (copyright_pub.publisher or copyright_pub.full_text):
    if has_generic_title:
        # Generic title: title=30%, author=45%, publisher=25%
        combined_score = (title_score * 0.3) + (author_score * 0.45) + (publisher_score * 0.25)
    else:
        # Normal title: title=60%, author=25%, publisher=15%
        combined_score = (title_score * 0.6) + (author_score * 0.25) + (publisher_score * 0.15)
else:
    # No publisher data available
    if has_generic_title:
        # Generic title: title=40%, author=60%
        combined_score = (title_score * 0.4) + (author_score * 0.6)
    else:
        # Normal title: title=70%, author=30%
        combined_score = (title_score * 0.7) + (author_score * 0.3)
```

**Scoring Philosophy**:

- **Normal titles**: Titles are most distinctive and reliable
- **Generic titles**: Authors and publishers become more important for discrimination
- **Publisher data**: Adds valuable verification when available
- **Dynamic weighting**: Adapts to data quality and availability

### 4.2 Threshold Management

**Configurable Thresholds**:

- `title_threshold`: Minimum title similarity (default: 80)
- `author_threshold`: Minimum author similarity (default: 70)
- `publisher_threshold`: Minimum publisher similarity (default: 60, when MARC has publisher data)
- `year_tolerance`: Maximum year difference (default: ±2 years)

**Filtering Order**:

1. Year filter eliminates chronologically impossible matches
1. Title filter (primary discriminator)
1. Author filter (secondary validation)
1. Publisher filter (when MARC has publisher data)
1. Combined score for final ranking with dynamic weighting

### 4.3 Year Range Filtering

**Publication Year Filtering**: The system supports flexible year-based filtering during MARC extraction to focus on specific time periods.

**Implementation**:

```python
class MarcLoader:
    def __init__(self, marc_path: str, batch_size: int = 200, min_year: int = None, max_year: int = None):
        self.min_year = min_year
        self.max_year = max_year

    def _should_include_record(self, pub: Publication) -> bool:
        """Check if record should be included based on year filters"""
        if pub.year is None:
            return True  # Include records without years to be safe
        
        # Check minimum year
        if self.min_year is not None and pub.year < self.min_year:
            return False
            
        # Check maximum year
        if self.max_year is not None and pub.year > self.max_year:
            return False
            
        return True
```

**Filtering Strategies**:

- **Min-year only**: `--min-year 1950` (everything from 1950 onwards)
- **Max-year only**: `--max-year 1970` (everything up to 1970)
- **Year range**: `--min-year 1950 --max-year 1960` (decade focus)
- **Single year**: `--min-year 1955 --max-year 1955` (specific year only)

**Design Decisions**:

- **Inclusive boundaries**: Both min_year and max_year are included in results
- **Safe handling**: Records without publication years are always included
- **Early filtering**: Applied during MARC extraction to reduce processing load
- **Performance impact**: Can significantly reduce dataset size and processing time

**Logging Enhancement**:

```python
# Shows year range being processed
logger.info("Publication year range: 1950 - 1960")

# Reports filtering results
logger.info("Filtered out 50,000 records (before 1950 or after 1960)")
```

### 4.4 Text Normalization

Text normalization is critical for accurate matching across different data sources.

**See [`docs/PROCESSING_PIPELINE.md`](PROCESSING_PIPELINE.md) Section 2 for complete details on:**

- Unicode normalization and ASCII folding
- Field-specific normalization (titles, authors, publishers)
- Abbreviation expansion
- Stopword removal

The normalization pipeline ensures consistent text representation across all data sources.

## 5. Copyright Status Algorithm

### 5.1 Decision Logic

```python
def determine_copyright_status(self) -> CopyrightStatus:
    has_reg = self.has_registration_match()
    has_ren = self.has_renewal_match()
    
    if self.country_classification == CountryClassification.US:
        if has_reg and not has_ren:
            return CopyrightStatus.POTENTIALLY_PD_DATE_VERIFY
        elif has_ren and not has_reg:
            return CopyrightStatus.POTENTIALLY_IN_COPYRIGHT
        elif not has_reg and not has_ren:
            return CopyrightStatus.POTENTIALLY_PD_DATE_VERIFY
        else:  # has both
            return CopyrightStatus.POTENTIALLY_IN_COPYRIGHT
    
    elif self.country_classification == CountryClassification.NON_US:
        if has_reg or has_ren:
            return CopyrightStatus.RESEARCH_US_STATUS
        else:
            return CopyrightStatus.RESEARCH_US_ONLY_PD
```

**Algorithm Logic**:

- US works: Analysis based on registration/renewal patterns
- Non-US works: Different research strategies based on US registration
- Conservative approach errs on side of caution

### 5.2 Four-Category System

1. **`POTENTIALLY_PD_DATE_VERIFY`**: Likely public domain, verify dates
1. **`POTENTIALLY_IN_COPYRIGHT`**: Likely copyrighted, assume protection
1. **`RESEARCH_US_STATUS`**: Non-US work with US registration, needs research
1. **`RESEARCH_US_ONLY_PD`**: Non-US work without US registration, research needed

## 6. Error Handling and Robustness

### 6.1 Graceful Degradation

```python
def _extract_from_record(self, record) -> Optional[Publication]:
    try:
        title = self._extract_title(record)
        if not title:
            return None  # Skip records without titles
        
        # Continue with optional fields
        author = self._extract_author(record) or ""
        # ... other fields with fallbacks
        
    except Exception as e:
        logger.debug(f"Error extracting record: {e}")
        return None  # Skip malformed records
```

### 6.2 Process Isolation

```python
def process_batch(batch_info):
    try:
        # Process entire batch
        return batch_id, processed_marc, stats
    except Exception as e:
        logger.error(f"Batch {batch_id} failed: {e}")
        return batch_id, [], {"error": str(e)}
```

This provides:

- Fault tolerance (one bad record doesn't crash entire batch)
- Detailed logging for troubleshooting
- Continuous processing despite individual failures

## 7. Performance Results

### 7.1 Optimization Impact

**Before optimization**: ~480 billion potential comparisons
**After optimization**: ~thousands of comparisons per query

**Processing times**:

- 4-core system: 15-20 hours
- 8-core system: 8-12 hours
- 16-core system: 6-8 hours

### 7.2 Key Metrics

- Index efficiency: Average candidates per query
- Match quality: Precision/recall of similarity matching
- Processing speed: 1,000-3,000+ records per minute
- Memory usage: Controlled through batch processing

## 8. Testing and Validation

The system includes tests for:

- Index correctness (multi-key indexing)
- Matching accuracy (similarity scoring)
- Edge cases (malformed data handling)
- Performance benchmarks

### 8.1 Property-Based Testing

In addition to traditional example-based tests, the codebase includes comprehensive property-based tests using the Hypothesis framework. These tests verify that certain mathematical properties and invariants hold across all possible inputs.

**Overview**:

- **83 property tests** across 4 test files
- **Framework**: Hypothesis for Python
- **Purpose**: Discover edge cases and ensure robustness

**Test Files**:

1. **`tests/test_utils/test_lccn_properties.py`** (18 tests)

   - LCCN normalization idempotency
   - Component extraction consistency
   - Format validation (no spaces, hyphens, or slashes in output)
   - Edge case handling

1. **`tests/test_utils/test_text_properties.py`** (29 tests)

   - Unicode normalization properties
   - ASCII folding consistency
   - Text normalization idempotency
   - Year extraction constraints

1. **`tests/test_processing/test_processing_properties.py`** (19 tests)

   - Language processor stopword removal
   - Multi-language stemming consistency
   - Abbreviation expansion properties
   - Word order preservation

1. **`tests/test_processing/test_similarity_properties.py`** (17 tests)

   - Similarity score bounds (0-100)
   - Symmetry properties (similarity(a,b) = similarity(b,a))
   - Identity properties (similarity(a,a) = 100, with exceptions)
   - Language-specific behavior

**Key Findings from Property Testing**:

1. **LCCN Edge Case**: `extract_lccn_year` can return non-digit characters for malformed input like "0:"
1. **Unicode Handling**: `normalize_lccn` only removes regular spaces (U+0020) per [LC standard](https://www.loc.gov/marc/lccn-namespace.html), not all whitespace
1. **Stopword Bug**: `extract_significant_words` filters stopwords case-sensitively
1. **Abbreviation Behavior**: `expand_abbreviations` always returns lowercase text
1. **Short Text Filtering**: Single-character text (< 2 chars) gets filtered out, affecting similarity scores

**Running Property Tests**:

```bash
# Run all property tests
pdm run pytest tests/test_*/test_*_properties.py -v

# Run with specific examples that failed
pdm run pytest tests/test_utils/test_lccn_properties.py::test_extract_year_numeric_only -v

# Increase test examples (default 100)
pdm run pytest tests/test_utils/test_text_properties.py --hypothesis-max-examples=1000
```

**Writing New Property Tests**:

```python
from hypothesis import given, strategies as st

class TestNewProperties:
    @given(st.text())
    def test_function_never_crashes(self, input_text: str) -> None:
        """Function should handle any string input without exceptions"""
        try:
            result = my_function(input_text)
            assert isinstance(result, str)
        except Exception:
            assert False, "Function raised unexpected exception"
```

## 9. Maintenance Guidelines

### 9.1 Adding New Data Sources

1. Create new loader class following existing pattern
1. Implement `load_all_*_data()` method
1. Add to batch processing pipeline
1. Update Publication class if needed

### 9.2 Modifying Scoring Logic

1. Update `find_best_match()` in `matching_engine.py`
1. Add configuration parameters to argument parser
1. Update tests to validate new behavior
1. Document threshold recommendations

### 9.3 Performance Monitoring

1. Add timing decorators to key functions
1. Monitor memory usage during processing
1. Track index effectiveness metrics
1. Profile hot paths regularly

## 10. Matching and Scoring API

### 10.1 API Overview

The system provides a pluggable matching and scoring API that allows alternative implementations without modifying the core application logic. This enables experimentation with different similarity algorithms, scoring strategies, and matching approaches.

### 10.2 Word-Based Matching Implementation

**Core Components**:

```python
from marc_pd_tool.processing.matching_engine import DataMatcher
from marc_pd_tool.processing.similarity_calculator import SimilarityCalculator
from marc_pd_tool.processing.indexer import DataIndexer

# Word-based matching with stemming and stopwords
matching_engine = DataMatcher()

# Calculate similarity scores
similarity_calculator = SimilarityCalculator()
title_score = similarity_calculator.calculate_title_similarity(
    marc_title, copyright_title, language_code
)

# Build word-based indexes for fast candidate filtering
indexer = DataIndexer()
index = indexer.build_index(publications)
```

### 10.3 Key Classes

**For complete details on the matching algorithms and processing steps, see [`docs/PROCESSING_PIPELINE.md`](PROCESSING_PIPELINE.md).**

**`SimilarityCalculator`** (`processing/similarity_calculator.py`):

- Implements similarity calculations described in the processing pipeline
- Multi-language support for 5 European languages

**`DataMatcher`** (`processing/matching_engine.py`):

- Main matching orchestration with adaptive scoring
- LCCN exact matching and early termination logic
- Batch processing support via `process_batch()`

**`DataIndexer`** (`processing/indexer.py`):

- Implements the indexing strategies detailed in the processing pipeline
- Memory-efficient compact index entries

### 10.4 Configuration

The word-based matching system is configured through `config.json` and `wordlists.json`:

**`config.json`** - Algorithm parameters:

```json
{
    "default_thresholds": {
        "title": 40,
        "author": 30,
        "publisher": 30
    },
    "matching": {
        "adaptive_weighting": {
            "title_weight": 0.5,
            "author_weight": 0.3,
            "publisher_weight": 0.2,
            "generic_title_penalty": 0.8
        },
        "minimum_combined_score": 40
    }
}
```

**`wordlists.json`** - Centralized word lists:

```json
{
    "stopwords": {
        "general": ["the", "a", "an", "and", "or", "but", ...],
        "publisher": ["inc", "co", "corp", "company", ...],
        "edition": ["edition", "ed", "edn", ...],
        "title": ["a", "an", "the", "by", "in", "on", ...],
        "author": ["by", "edited", "editor", ...]
    },
    "stopwords_by_language": {
        "eng": ["the", "a", "an", "and", "or", "but", ...],
        "fre": ["le", "la", "les", "un", "une", ...],
        "ger": ["der", "die", "das", "ein", "eine", ...],
        "spa": ["el", "la", "los", "las", "un", ...],
        "ita": ["il", "la", "i", "gli", "le", ...]
    },
    "patterns": {
        "generic_titles": ["collected works", "complete works", ...],
        "ordinals": ["1st", "2nd", "3rd", ...],
        "author_titles": ["sir", "dr", "prof", ...]
    },
    "abbreviations": {
        "bibliographic": {
            "acad": "academy", "annu": "annual", "assoc": "association",
            "bibl": "bibliography", "bull": "bulletin", "dept": "department", ...
        }
    },
    "unicode_fixes": {
        "√™": "é", "√®": "î", "√≠": "í", ...
    }
}
```

### 10.5 Usage Examples

**Basic Matching**:

```python
from marc_pd_tool.processing.matching_engine import DataMatcher
from marc_pd_tool.processing.text_processing import GenericTitleDetector

# Initialize components
matching_engine = DataMatcher()
generic_detector = GenericTitleDetector()

# Find best match
result = matching_engine.find_best_match(
    marc_pub, copyright_pubs, 
    title_threshold=80, author_threshold=70, year_tolerance=2,
    publisher_threshold=60, early_exit_title=95, early_exit_author=90,
    generic_detector=generic_detector
)
```

**Batch Processing**:

```python
from marc_pd_tool.processing.matching_engine import process_batch

# Process a batch of MARC records (runs in separate process)
batch_id, processed_records, stats = process_batch(batch_info)
```

### 10.6 Performance Characteristics

**Word-Based Indexing Benefits**:

- Reduces comparison space by 10-50x through multi-key indexing
- Generates keys from significant words after stemming/stopword removal
- Memory-efficient compact index entries
- Fast candidate retrieval with year filtering

**Processing Speed**:

- Expected: 2,000-5,000+ records/minute on modern multi-core systems
- Persistent caching reduces startup from 5-10 minutes to 10-30 seconds
- Early termination for high-confidence matches (title ≥95%, author ≥90%)
- Parallel batch processing across CPU cores

**Memory Optimization**:

- `__slots__` in Publication class reduces memory by 30-50%
- Lazy property caching for normalized text fields
- LRU cache for generic title detection results
- Bounded frequency counters prevent unbounded growth

### 10.7 Testing Custom Implementations

**Contract Testing**:

All custom implementations should pass the API contract tests:

```python
# Your custom implementation
calculator = YourCustomCalculator()

# Test basic contracts
assert isinstance(calculator.calculate_title_similarity("test", "test"), (int, float))
assert 0 <= calculator.calculate_title_similarity("test", "test") <= 100
```

**Integration Testing**:

```python
from marc_pd_tool.processing.matching_engine import DataMatcher

# Test with real data
engine = DataMatcher()

# Run against known test cases
result = engine.find_best_match(test_marc_pub, test_copyright_pubs, ...)
assert result is not None  # Should find expected matches
```

### 10.8 Performance Considerations

**Optimization Tips**:

1. **Caching**: Cache expensive similarity calculations
1. **Early Termination**: Implement early exit when scores are very low
1. **Batch Processing**: Process multiple comparisons efficiently
1. **Memory Management**: Avoid loading large models repeatedly

**Profiling Custom Implementations**:

```python
import time

class ProfilingCalculator(SimilarityCalculator):
    def __init__(self, base_calculator):
        self.base = base_calculator
        self.timings = []
    
    def calculate_title_similarity(self, marc_title: str, copyright_title: str) -> float:
        start = time.time()
        result = self.base.calculate_title_similarity(marc_title, copyright_title)
        self.timings.append(time.time() - start)
        return result
```

### 10.9 Migration Guide

**From Hardcoded Logic to API**:

1. **Identify Custom Logic**: Find where you need different behavior
1. **Choose Component**: Determine if you need custom calculator, combiner, or full engine
1. **Implement Interface**: Create class implementing appropriate abstract base class
1. **Test Thoroughly**: Ensure new implementation handles edge cases
1. **Performance Test**: Compare performance with default implementation
1. **Deploy Gradually**: Test with subset of data before full deployment

## Conclusion

The system achieves performance through multi-key indexing, parallel processing, memory management, early termination, and hierarchical filtering. This architecture processes 190K records against 2.5M reference records in 6-20 hours on modern hardware.

The new matching and scoring API provides a clean extension point for alternative algorithms while maintaining full backward compatibility and enabling experimentation with advanced techniques like machine learning and semantic similarity.
