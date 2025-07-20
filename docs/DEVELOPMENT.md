# Development Guide: Code Architecture and Performance Optimizations

## Overview

This document explains the code architecture, design decisions, and performance optimizations in the MARC Copyright Analysis Tool for developers who need to understand, maintain, or extend the system.

## 1. Package Architecture

### Modular Design

The codebase is organized as a Python package with one class per file:

```
marc_pd_tool/
├── __init__.py              # Package interface with explicit imports
├── enums.py                 # Copyright status and country classification enums
├── publication.py           # Publication data model with country and match tracking
├── marc_extractor.py        # MARC XML extraction with country detection
├── copyright_loader.py      # Copyright registration data loading
├── renewal_loader.py        # Renewal data loading (TSV format)
├── indexer.py               # Multi-key indexing system
└── generic_title_detector.py # Language-aware generic title detection
compare.py                   # Command-line application
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

- **Python 3.12+**
- **PDM package manager**
- **Multi-core CPU** recommended for best performance
- **4GB+ RAM** for large datasets

### Code Design Principles

- Each module handles one major concern
- Full imports instead of relative imports
- Comprehensive type hints
- Publication objects maintain both original and normalized data

## 2. Data Model Design

### Publication Class (`publication.py`)

The Publication class stores both normalized and original data:

```python
class Publication:
    def __init__(self, title, author, ...):
        # Store both normalized and original data
        self.title = self.normalize_text(title)           # For matching
        self.original_title = title                       # For output
        
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

### Generic Title Detection System (`generic_title_detector.py`)

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

The system extracts author information from MARC field 245$c (statement of responsibility), which is more likely to match copyright registration data than the traditional 1xx author fields:

**MARC Extraction Logic**:

```python
def _extract_from_record(self, record) -> Optional[Publication]:
    # Extract author from 245$c (statement of responsibility)
    # This format is more likely to match copyright registration data
    author_elem = record.find(".//datafield[@tag='245']/subfield[@code='c']")
    if author_elem is not None:
        author = author_elem.text
    else:
        author = ""
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

- **Registration matches**: Direct comparison using `fuzz.ratio()` (MARC publisher vs registration publisher)
- **Renewal matches**: Fuzzy matching using `fuzz.partial_ratio()` (MARC publisher vs renewal full_text)
- **Threshold**: 60% similarity required when MARC has publisher data

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
        title_score = fuzz.ratio(marc_pub.title, copyright_pub.title)
        
        if title_score < title_threshold:
            continue
        
        author_score = fuzz.ratio(marc_pub.author, copyright_pub.author)
        combined_score = (title_score * 0.7) + (author_score * 0.3)
        
        if combined_score > best_score:
            best_score = combined_score
            best_match = {...}
            
            # Early exit for high-confidence matches
            if (title_score >= early_exit_title and 
                marc_pub.author and copyright_pub.author and 
                author_score >= early_exit_author):
                break
```

Early termination occurs only when:

- Title score ≥95% AND author score ≥90%
- Both title and author are present
- Thresholds are configurable

### 3.4 Parallel Processing Architecture

The system uses a sophisticated multi-process architecture with index serialization optimization:

**Main Process (Index Building & Serialization):**

```python
def main():
    # Phase 3.5: Build indexes once and serialize to temp files
    registration_index = build_index(registration_publications)
    renewal_index = build_index(renewal_publications)
    
    # Create temporary files for serialized indexes
    temp_dir = tempfile.mkdtemp(prefix="marc_indexes_")
    registration_index_file = os.path.join(temp_dir, "registration_index.pkl")
    renewal_index_file = os.path.join(temp_dir, "renewal_index.pkl")
    
    # Serialize indexes to pickle files
    with open(registration_index_file, "wb") as f:
        pickle.dump(registration_index, f)
    with open(renewal_index_file, "wb") as f:
        pickle.dump(renewal_index, f)
```

**Worker Process (Index Loading & Processing):**

```python
def process_batch(batch_info):
    # Load pre-built indexes from pickle files
    with open(registration_index_file, "rb") as f:
        registration_index = pickle.load(f)
    with open(renewal_index_file, "rb") as f:
        renewal_index = pickle.load(f)
    
    # Process MARC records using pre-built indexes
    # No index building overhead per process
```

**Key Architectural Benefits:**

- **Index Serialization**: Eliminates duplicate index building across processes
- **Process Isolation**: Each process has independent memory space
- **Fault Tolerance**: Process failures don't crash the entire application
- **Linear Scaling**: Performance scales with CPU cores
- **Memory Efficiency**: Indexes built once, shared via serialized files
- **Startup Optimization**: Reduces worker process startup from 30-60s to \<5s

**Performance Impact:**

- **Before**: 30-60 seconds × N processes = 2-4 minutes overhead
- **After**: 30-60 seconds total = **1.5-3 minutes saved per run**
- **Worker logs**: "Loading registration index from /tmp/marc_indexes_xyz/registration_index.pkl"

Uses processes rather than threads because:

- Python's GIL limits thread effectiveness for CPU-bound tasks
- Each process has independent memory space
- Process failures don't crash the entire application
- Scales linearly with CPU cores

### 3.5 Index Serialization Optimization

**Problem Solved:** The original implementation had each worker process rebuilding identical indexes from the same 2.1M+ registration and 445K+ renewal records, causing massive inefficiency.

**Implementation Details:**

**1. Temporary File Management:**

```python
# Create secure temporary directory
temp_dir = tempfile.mkdtemp(prefix="marc_indexes_")
registration_index_file = os.path.join(temp_dir, "registration_index.pkl")
renewal_index_file = os.path.join(temp_dir, "renewal_index.pkl")

# Robust cleanup with try/finally
try:
    # Process batches with pre-built indexes
    with ProcessPoolExecutor(max_workers=args.max_workers) as executor:
        # ... processing logic
finally:
    # Clean up temporary files even if processing fails
    try:
        os.unlink(registration_index_file)
        os.unlink(renewal_index_file)
        os.rmdir(temp_dir)
    except Exception as e:
        logger.warning(f"Failed to clean up temporary files: {e}")
```

**2. Index Serialization:**

```python
# Build indexes once in main process
logger.info("Building registration index...")
registration_index = build_index(registration_publications)
logger.info("Building renewal index...")
renewal_index = build_index(renewal_publications)

# Serialize to pickle files for worker processes
with open(registration_index_file, "wb") as f:
    pickle.dump(registration_index, f)
with open(renewal_index_file, "wb") as f:
    pickle.dump(renewal_index, f)
```

**3. Worker Process Loading:**

```python
def process_batch(batch_info):
    # Extract file paths from batch_info tuple
    registration_index_file, renewal_index_file = batch_info[2], batch_info[3]
    
    # Load pre-built indexes (fast operation)
    with open(registration_index_file, "rb") as f:
        registration_index = pickle.load(f)
    with open(renewal_index_file, "rb") as f:
        renewal_index = pickle.load(f)
    
    # Immediate processing with no build overhead
```

**Performance Measurements:**

- **Index building time**: 30-60 seconds for 2.5M+ records
- **Pickle serialization**: ~2-5 seconds for both indexes
- **Pickle loading per worker**: ~1-3 seconds per index
- **Total overhead reduction**: From 2-4 minutes to 30-60 seconds
- **Efficiency gain**: 75-85% reduction in startup overhead

**Error Handling:**

- Graceful handling of pickle file creation/loading failures
- Automatic cleanup of temporary files even if process crashes
- Worker process isolation prevents cascading failures
- Detailed logging for troubleshooting serialization issues

### 3.6 Memory Management Strategies

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

## 4. Scoring and Matching Logic

### 4.1 Dynamic Similarity Scoring Strategy

The system uses adaptive scoring weights based on available data and generic title detection:

```python
title_score = fuzz.ratio(marc_pub.title, copyright_pub.title)
author_score = fuzz.ratio(marc_pub.author, copyright_pub.author)
publisher_score = calculate_publisher_score(marc_pub, copyright_pub)

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
class ParallelMarcExtractor:
    def __init__(self, marc_path: str, batch_size: int = 1000, min_year: int = None, max_year: int = None):
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

```python
def normalize_text(text: str) -> str:
    # Remove punctuation except spaces and hyphens
    normalized = re.sub(r"[^\w\s\-]", " ", text.lower())
    # Normalize whitespace and hyphens
    normalized = re.sub(r"[\s\-]+", " ", normalized)
    return normalized.strip()
```

This approach:

- Eliminates formatting variations
- Keeps word boundaries intact
- Removes punctuation noise while preserving meaning

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

## Conclusion

The system achieves performance through multi-key indexing, parallel processing, memory management, early termination, and hierarchical filtering. This architecture processes 190K records against 2.5M reference records in 6-20 hours on modern hardware.
