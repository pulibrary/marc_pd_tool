# MARC Copyright Analysis Pipeline

## Overview

This tool analyzes library records to determine copyright status by comparing them against U.S. copyright registration and renewal data as digitized by the New York Public Library. The goal is to help identify works that may be in the public domain or require further copyright research.

## Data Sources

### MARC Records

The publications we're analyzing - bibliographic records from a library catalog that contain title, author, publication date, publisher, place of publication, and country information. We focus on the country code to determine whether a work was published in the US or elsewhere, as this affects copyright analysis. Right now we only support MARC XML.

### Copyright Registration Data

Historical U.S. copyright registrations from 1923-1977,
[digitized by NYPL from the Catalog of Copyright Entries Project](https://github.com/NYPL/catalog_of_copyright_entries_project). When a work was registered for copyright, it was listed in these catalogs with title, author, publication date, publisher, and place information.

### Renewal Data

U.S. copyright renewal records from 1950-1991, also digitized by NYPL as part of the [CCE-Renewals Project](https://github.com/NYPL/cce-renewals). Under the pre-1978 copyright law, works had to be renewed after 28 years to maintain copyright protection. These records show which works were renewed and which were not.

## Processing Pipeline

### 1. Data Loading and Extraction

#### 1.1 MARC Record Extraction (`MarcLoader`)

**Input**: MARCXML files containing bibliographic records

**Processing Steps**:

1. Parse MARCXML and extract:

   - **Title**: Field 245 subfields $a, $b, $n, and $p (in original order)
     - $a: Main title
     - $b: Subtitle/other title information
     - $n: Number of part/section
     - $p: Name of part/section
   - **Authors**:
     - Field 100/110/111 (main entry - controlled form)
     - Field 245 subfield $c (statement of responsibility - transcribed form, more likely to match copyright data format)
   - **Publication Info**:
     - Field 264 (RDA) or 260 (AACR2) for place, publisher, date
     - Prefer 264 when both exist
   - **Country Code**: Field 008 positions 15-17
   - **Language Code**: Field 008 positions 35-37 (fallback: Field 041$a)
   - **LCCN**: Field 010 subfield $a
   - **Edition**: Field 250$a (e.g., "2nd ed.", "Revised edition", "First printing")

1. **Country Classification**:

   - Extract 3-letter code from MARC 008/15-17
   - Map to classification:
     - US codes: xxu, nyu, mau, cau, etc. → "US"
     - Known non-US codes → "Non-US"
     - Unknown/missing → "Unknown" (when field 008 is too short, positions 15-17 are empty/blank, or record lacks reliable country information)

1. **Year Filtering**:

   - Apply `--min-year` and `--max-year` filters during extraction
   - When year filtering is active, records without publication years are excluded by default
   - Use `--brute-force-missing-year` to include records without years (searches entire dataset)
   - Year extraction handles standard formats plus copyright notation (e.g., "c1955")
   - Filtered records are logged with breakdown (no year, out of range, non-US)

#### 1.2 Copyright Registration Data (`CopyrightDataLoader`)

**Input**: XML files from NYPL registration dataset (1923-1977)

**Processing Steps**:

1. Parse XML and extract:
   - Title, author, publisher, registration date, registration number
   - Store both normalized and original versions

#### 1.3 Renewal Data (`RenewalDataLoader`)

**Input**: Tab-delimited files from NYPL renewal dataset (1950-1991)

**Processing Steps**:

1. Parse TSV and extract:
   - Title, author, original registration info, renewal date
   - Full text field containing complete renewal entry
   - Store both normalized and original versions

### 2. Text Normalization

All text fields undergo normalization before indexing and matching. The normalization pipeline is applied consistently across all data sources.

#### 2.1 Unicode Normalization (`normalize_unicode`)

**Purpose**: Handle encoding issues and ensure consistent character representation

**Steps**:

1. **UTF-8 Decoding with Fallback**:

   ```
   If text is bytes: decode as UTF-8
   If UTF-8 fails: decode as Latin-1
   ```

1. **Unicode Normalization Form C (NFC)**:

   - Combine decomposed characters (é = e + ´ → é)
   - Ensures consistent representation

1. **Fix Common Encoding Corruptions**:

   - Patterns loaded from `wordlists.json` under `text_fixes.unicode_corrections`
   - √© → é, √® → î, √† → à, etc.
   - Handles UTF-8/Latin-1 mojibake
   - Easily extensible by updating the JSON file

1. **ASCII Folding**:

   - Uses the `unidecode` library for comprehensive character conversion
   - Convert accented characters to ASCII base forms
   - é→e, ñ→n, ü→u, etc.
   - Handles thousands of Unicode characters from many languages

**Important Notes** (from property testing):

- Some Unicode strings may normalize to empty (e.g., certain control characters)
- For LCCN normalization specifically, only regular spaces (U+0020) are removed per the [Library of Congress standard](https://www.loc.gov/marc/lccn-namespace.html), not all Unicode whitespace (e.g., \\r, \\n, \\t are preserved)

#### 2.2 Basic Text Normalization (`TextNormalizerMixin`)

**Applied to all text fields via the `TextNormalizerMixin` class**:

1. Apply Unicode normalization (above)
1. Convert to lowercase
1. Remove extra whitespace
1. Strip leading/trailing whitespace
1. Join split letters (fixes OCR issues like "N E W" → "NEW")
1. Remove punctuation (configurable)
1. Apply ASCII folding for character variants

**Note**: The old `normalize_text` function is deprecated in favor of `TextNormalizerMixin._normalize_text()` or `normalize_text_standard()` for backward compatibility.

**Important Edge Cases** (from property testing):

- Single-character text (< 2 chars) may be filtered out entirely during processing
- This affects similarity scoring, which returns 0% for text that gets completely filtered
- The `extract_significant_words` function filters stopwords case-sensitively (known bug)

#### 2.3 Title-Specific Normalization

**Additional steps for titles**:

1. **Part Integration**:

   - **TODO:** confirm that these are just taken in the order in which they appear, and not resorted somehow
   - If MARC 245 has $n or $p, append to main title
   - Format: "Main Title Part Name" or "Main Title Part Number"

1. **Abbreviation Expansion** (always applied):

   - Expand bibliographic abbreviations: vol→volume, pt→part, ed→edition
   - Only expand if abbreviation has period or is \<5 characters
   - Uses 130+ AACR2 standard abbreviations from wordlists.json
   - Applied during word-based indexing and similarity calculation

1. **Bracketed Data Removal**:

   - Remove cataloger additions in square brackets
   - "Title [microform]" → "Title"
   - "Title [electronic resource]" → "Title"
   - Applied during MARC extraction before any other normalization

#### 2.4 Author-Specific Normalization

1. **Format Standardization**:

   - **TODO:** confirm from registration data that we should be removing dates
   - Handle "Last, First" and "First Last" formats
   - Remove dates: "Smith, John (1923-1995)" → "Smith, John"
   - Remove titles: "Dr.", "Prof.", "Sir", etc.

1. **Abbreviation Expansion**:

   - Same as title normalization

**Known Issue** (from property testing):

- The `extract_significant_words` function used in author processing filters stopwords case-sensitively, which may cause inconsistent behavior

#### 2.5 Publisher-Specific Normalization (`normalize_publisher_text`)

1. **Abbreviation Expansion**:

   - corp→corporation, inc→incorporated, ltd→limited, etc.
   - Uses the same bibliographic abbreviations from wordlists.json
   - **Note**: `expand_abbreviations` always returns lowercase text

1. **Stopword Removal**:

   - Remove generic terms from wordlists.json publisher stopwords
   - Language-specific stopwords for multilingual publishers

1. **Suffix Pattern Removal**:

   - Remove common publisher suffixes defined in wordlists.json
   - Pattern: inc, incorporated, llc, ltd, limited, corp, corporation, company, co, publishers, publishing, press, books
   - Applied via configurable regex pattern from `ConfigLoader.get_publisher_suffix_regex()`

### 3. Indexing

#### 3.1 Word-Based Indexing (`DataIndexer`)

The indexer creates inverted indexes to dramatically reduce the number of comparisons needed during matching.

##### 3.1.1 Title Indexing

**Key Generation Process**:

1. **Preprocessing**:

   - Normalize text (as above)
   - Expand abbreviations
   - Remove stopwords based on language

1. **Word Extraction**:

   - Split on whitespace
   - Keep words ≥2 characters

1. **Stemming** (if enabled):

   - Apply language-specific stemming
   - English: plays→play, playing→play
   - Supports 5 languages: eng, fre, ger, spa, ita

1. **Key Creation**:

   - **Single word keys**: Each stemmed word becomes an index key
   - **Multi-word combination keys**: Adjacent words joined with underscore for better precision
     - First two words: Captures common title patterns
     - Last two words: Useful for titles with similar beginnings
     - First three words: Maximum precision for longer titles
   - **Purpose**: Keys enable fast candidate lookup in the inverted index

**Example**:

```
"The Great Adventure, vol. 2" 
→ Normalized: "great adventure volume 2"
→ After stopwords: ["great", "adventure", "volume", "2"]
→ After stemming: ["great", "adventur", "volum", "2"]
→ Keys: [
    "great",              # Single word keys
    "adventur", 
    "volum", 
    "2",
    "great_adventur",     # First two words
    "volum_2",           # Last two words  
    "great_adventur_volum" # First three words
]
```

**How Keys Work**:

- Each key maps to a set of publication IDs in the index
- When searching, we generate keys for the query and look up matching IDs
- Multi-word keys reduce false positives by requiring word proximity

##### 3.1.2 Author Indexing

**Key Generation Process**:

1. **Preprocessing**:

   - Remove titles (Dr., Prof., etc.)
   - Remove dates and qualifiers
   - Handle comma-separated names

1. **Name Parsing**:

   - For "Last, First": extract surname words
   - For "First Last": use last word as surname
   - Filter stopwords (by, von, de, etc.)

1. **Key Creation**:

   - Each significant surname word becomes a key
   - Also create full normalized name as key

**Example**:

```
"Smith, Dr. John Jr. (1923-1995)"
→ Normalized: "smith, john"
→ Keys: ["smith", "smith, john"]
```

##### 3.1.3 Year Indexing

- Direct year as key: 1950 → ["1950"]
- Enables fast year-based filtering

##### 3.1.4 LCCN Indexing

- Direct normalized LCCN as key: "n78890351" → ["n78890351"]
- Enables O(1) lookup for exact LCCN matches
- Highest priority - bypasses all other indexing when found

#### 3.2 Index Structure

Each index entry maps a key to a set of publication IDs:

```
{
  "adventure": {1, 5, 42, 156, ...},
  "smith": {3, 7, 23, 89, ...},
  "1950": {1, 3, 5, 7, ...},
  "n78890351": {42},  # LCCN index for instant lookup
}
```

### 4. Matching Process

For each MARC record, we search for similar entries in both the registration and renewal datasets using sophisticated text processing and matching algorithms.

**Key Points:**

- Word-based title matching with language-aware stemming
- Fuzzy string matching for authors and publishers
- Adaptive scoring based on available fields
- Default thresholds: Title ≥40%, Author ≥30%, Publisher ≥30%
- LCCN exact matches get 100% priority as ground truth

**Single Best Match:**

Each MARC record can have at most one match in each dataset (registration and renewal). The tool:

- Finds the BEST match that meets the similarity thresholds
- Records the match with its source ID and similarity scores
- Uses this single match for copyright status determination

#### 4.1 Candidate Selection

For each MARC record, find potential matches:

1. **LCCN Lookup** (highest priority, O(1) performance):

   - If MARC record has normalized LCCN, check LCCN index first
   - Direct match returns immediately - no other indexes checked
   - Bypasses year filtering for guaranteed matches

1. **Year Filtering** (applied first for non-LCCN matches):

   - Only consider records within ±`year_tolerance` (default: 1)
   - Dramatically reduces candidate pool

1. **Index Lookup**:

   - Generate keys for MARC record (same process as indexing)
   - Look up each key in the index
   - Union all matching publication IDs

1. **Candidate Retrieval**:

   - Fetch full records for candidate IDs
   - Typically reduces millions of comparisons to hundreds

#### 4.2 Similarity Calculation

For each candidate, calculate field-specific similarities:

##### 4.2.1 Title Similarity (Word-Based Jaccard)

**Algorithm**: Jaccard similarity on stemmed words

1. **Text Processing**:

   - Normalize both titles
   - Remove stopwords
   - Stem remaining words

1. **Jaccard Calculation**:

   ```
   similarity = |intersection| / |union| × 100
   ```

1. **Empty Handling**:

   - If both empty after processing: 0% (not 100%)
   - If one empty: 0%

**Edge Case** (from property testing):

- Identical single-character titles (e.g., "A" vs "A") return 0% instead of 100% because they are filtered out as too short (< 2 chars) during processing

**Example**:

```
MARC: "The Great Adventure"
Copyright: "Great Adventures" 
→ Words: {"great", "adventur"} vs {"great", "adventur"}
→ Similarity: 2/2 × 100 = 100%
```

##### 4.2.2 Author Similarity (Fuzzy String)

**Algorithm**: Token sort ratio (order-independent fuzzy matching)

1. Normalize both authors
1. Apply fuzzy string matching (Levenshtein-based)
1. Handle missing authors: 0% if only one side has author

**Dual Author Scoring**:

- Compare both MARC fields (100 and 245$c) against copyright author
- Take the maximum score

##### 4.2.3 Publisher Similarity (Fuzzy String)

**Algorithm**: Token sort ratio with extraction

1. For renewals: extract best matching publisher from full_text field
1. Apply fuzzy string matching
1. Handle missing publishers: 0% if only one side has publisher

#### 4.3 Special Cases

##### 4.3.1 LCCN Matching (Ground Truth)

- **TODO:** Are we trying to match even if we don't have a year? If not, we should probably document that in the report in the same place as the rationale for why we matched on LCCN

If both records have normalized LCCN and they match:

- Immediate 100% match on all fields
- Bypass all other similarity calculations
- Highest priority match
- Match type set to "lccn" (vs "similarity" for other matches)
- Reported in CSV output with match type indicator

##### 4.3.2 Early Termination

If title ≥ `early_exit_title` (95%) AND author ≥ `early_exit_author` (90%):

- Stop searching for better matches
- Return immediately (performance optimization)

##### 4.3.3 Brute-Force Mode for Yearless Records

**Purpose**: Handle MARC records that lack publication year information

**Default Behavior** (Performance Mode):

- MARC records without a year are skipped entirely
- Significantly improves performance by reducing comparisons
- Most appropriate for large-scale processing

**Brute-Force Mode** (`--brute-force-missing-year`):

- Processes MARC records even when year is missing
- Compares against ALL copyright/renewal data (no year filtering)
- Match type set to "brute_force_without_year" in output
- Performance impact: 10-100x slower for yearless records

**Implementation Details**:

1. Year filtering is bypassed for yearless MARC records
1. All copyright/renewal records become potential candidates
1. Only title, author, and publisher similarities are used
1. Standard thresholds still apply
1. Cache must contain full dataset (not year-filtered)

**When to Use**:

- Small datasets where completeness matters more than speed
- Research projects requiring exhaustive matching
- When many MARC records lack year information

**Important Notes**:

- Cannot be used effectively with `--min-year`/`--max-year` filters
- Requires loading entire copyright dataset into memory
- Consider using `--score-everything` mode for better yearless matches

#### 4.4 Generic Title Detection

Before applying similarity scoring, the system detects generic titles that would provide poor discrimination between different works.

**Detection Methods**:

1. **Pattern Matching**: Recognizes common generic title patterns:

   - Collections: "collected works", "selected writings", "complete works"
   - Genre-specific: "poems", "essays", "short stories", "plays", "letters"
   - Academic: "proceedings", "transactions", "papers", "studies"

1. **Frequency Analysis**: Identifies titles appearing frequently across the dataset (configurable threshold, default: 10+ occurrences)

1. **Linguistic Patterns**: Detects short titles with high stopword ratios or single genre words

**Language Limitation**: Generic title detection currently works only for English titles (language codes 'eng', 'en'). Non-English titles bypass generic detection using a conservative approach to prevent false positives.

**Scoring Adjustment**: When generic titles are detected, the algorithm reduces title weight and increases author/publisher weights to emphasize more discriminating fields.

### 5. Scoring and Thresholds

#### 5.1 Individual Field Thresholds

**Default Thresholds**:

- Title: 40% (must meet to consider match)
- Author: 30% (only applied if author data exists)
- Publisher: 30% (only applied if publisher data exists)
- Year tolerance: ±1 year

#### 5.2 Combined Score Calculation

**Adaptive Weighting** based on available fields:

1. **All fields present**:

   - Title: 60%, Author: 25%, Publisher: 15%

1. **No publisher**:

   - Title: 70%, Author: 30%

1. **No author**:

   - Title: 80%, Publisher: 20%

1. **Title only**:

   - Title: 100%

#### 5.3 Score Modifiers

1. **Generic Title Penalty**:

   - If title matches generic pattern ("Collected Works", "Poems", etc.)
   - Or appears ≥10 times in dataset
   - Multiply final score by 0.8 (20% penalty)

1. **Minimum Combined Score** (score-everything mode):

   - Default: 40%
   - Rejects matches below threshold even in "find best match" mode

#### 5.4 Match Selection

1. **Normal Mode**:

   - Must meet all applicable thresholds
   - Return highest scoring match above thresholds

1. **Score-Everything Mode** (`--score-everything`):

   - Ignore individual thresholds
   - Return best match regardless of score
   - Apply minimum combined score if configured

### 6. Copyright Status Determination

Based on the pattern of matches found, we assign one of six copyright status categories:

**For US Publications:**

**Special Rule for US Works Published 1930-1963:**

- **Registration but no renewal found** → `PD_NO_RENEWAL`: Public domain (renewal was required but not done)
- **Renewal found** → `IN_COPYRIGHT`: The work was renewed and is likely still under copyright protection
- **Neither registration nor renewal found** → `PD_DATE_VERIFY`: No registration found, may be public domain or never registered

**For US Works from Other Years:**

- **Registration but no renewal found** → `PD_DATE_VERIFY`: The work was registered but we found no renewal, suggesting it may be public domain (verify renewal deadline)
- **Renewal found** → `IN_COPYRIGHT`: The work was renewed and is likely still under copyright protection
- **Both registration and renewal found** → `IN_COPYRIGHT`: The work followed the full copyright process
- **Neither found** → `PD_DATE_VERIFY`: No registration found, may be public domain or never registered

**For Non-US Publications:**

- **Any US registration/renewal found** → `RESEARCH_US_STATUS`: The foreign work has some US copyright history requiring research
- **No US registration/renewal found** → `RESEARCH_US_ONLY_PD`: The foreign work may be public domain in the US only

**For Publications with Unknown Country:**

- **Any match pattern** → `COUNTRY_UNKNOWN`: Cannot determine copyright status without knowing country of publication. This occurs when:
  - MARC field 008 is too short (less than 18 characters)
  - Country code positions 15-17 are empty or blank
  - Record lacks reliable country information

**Legal Interpretation**:

The tool provides data matches only. Legal interpretation of copyright status requires:

- Understanding publication dates and copyright terms
- Checking renewal requirements for the publication year
- Considering special cases (government docs, etc.)

## Understanding the Results

### What the Status Categories Mean

**PD_NO_RENEWAL**: These works are in the public domain. This applies specifically to US works published 1930-1963 that were registered for copyright but not renewed within the required 28-year period.

**PD_DATE_VERIFY**: These works show patterns suggesting they may be in the public domain, but date verification is needed. For pre-1978 works, check if renewal was required and whether the 28-year deadline was met.

**IN_COPYRIGHT**: These works show evidence of copyright renewal or other indicators suggesting they may still be under copyright protection. Assume these are copyrighted unless proven otherwise.

**RESEARCH_US_STATUS**: Foreign works with some US copyright registration. The copyright status depends on complex factors including publication date, registration timing, and international copyright treaties.

**RESEARCH_US_ONLY_PD**: Foreign works with no US copyright registration found. These may be public domain in the US due to lack of compliance with US copyright formalities, but may still be copyrighted in their country of origin.

**COUNTRY_UNKNOWN**: Records where copyright status cannot be determined due to missing or invalid country information in the MARC record. These require manual investigation to determine the country of publication before copyright analysis can proceed.

### Using the Results

The tool produces output files with analysis results. The default CSV format has been simplified for clarity:

**CSV Column Headers:**

- **ID** - MARC record identifier
- **Title** - Original title from MARC record
- **Author** - Author from MARC record (245c or 1xx)
- **Year** - Publication year
- **Publisher** - Publisher name
- **Country** - Country classification (US/Non-US/Unknown)
- **Status** - Copyright status determination
- **Match Summary** - Shows match scores (e.g., "Reg: 95%, Ren: None" or "Reg: LCCN")
- **Warning** - Flags for data issues (generic title, no year, etc.)
- **Registration Source ID** - ID of matched registration record
- **Renewal Entry ID** - ID of matched renewal record

**Sample Output:**

```csv
ID,Title,Author,Year,Publisher,Country,Status,Match Summary,Warning,Registration Source ID,Renewal Entry ID
99123456,The Great Novel,Smith John,1955,Great Books Inc,US,PD_DATE_VERIFY,"Reg: 83%, Ren: None",,R456789,
99234567,American Classic,Brown Alice,1947,US Publishers,US,PD_NO_RENEWAL,"Reg: 88%, Ren: None",,R789123,
99789012,Complete Works,Jones Mary,1960,Academic Press,Non-US,RESEARCH_US_STATUS,"Reg: None, Ren: 82%",,b3ce7263-9e8b-5f9e-b1a0-190723af8d29
99345678,Mystery Work,Author Unknown,1950,,Unknown,COUNTRY_UNKNOWN,"Reg: None, Ren: None","No publisher, Unknown country",,
99111222,Collected Poems,Common Author,1965,Popular Publishers,US,IN_COPYRIGHT,"Reg: 65%, Ren: 67%",Generic title,R111111,d6a7cb69-27b6-5f04-9ab6-53813a4d8947
```

**For detailed analysis**, use the JSON or XLSX_ANALYSIS formats which include:

- All individual field scores (title, author, publisher)
- Normalized text versions showing how matching was performed
- Complete match metadata including year differences
- Status rule codes explaining copyright determinations

**Important Notes:**

- **Single Best Match**: Each MARC record has at most one match per dataset (registration and renewal)
- **Source ID Fields**: Clean source IDs for direct lookup in the original datasets
  - **Registration Source ID**: Direct lookup in copyright registration XML files
  - **Renewal Entry ID**: UUID for direct lookup in renewal TSV files (finds exact row)
- **Score Fields**: All score fields show values from the single best match found
- **Publisher Matching**:
  - **Registration Publisher**: Direct text comparison of MARC publisher vs registration publisher
  - **Renewal Publisher**: Extracted snippet from renewal full_text that best matches MARC publisher
  - **Publisher Score**: Reflects quality of publisher match (60% threshold when MARC has publisher data)
- **Edition Handling**:
  - **MARC Edition**: Extracted from field 250$a when present (empty when missing)
  - **Edition Indexing**: Used for candidate filtering when available, improves precision for multi-edition works
  - **No Edition Scoring**: Copyright datasets lack reliable edition information, so edition similarity is not calculated
  - **Candidate Enhancement**: Edition data helps distinguish between different editions of the same work when multiple candidates exist
- **Generic Title Detection**:
  - **Language Limitation**: Only applied to English titles (language codes 'eng', 'en')
  - **Detection Reason**: Shows why generic detection was applied (pattern/frequency/linguistic) or skipped (non-English)
  - **Scoring Impact**: Generic titles receive reduced title weight and increased author/publisher weight
  - **Conservative Approach**: Non-English titles bypass detection to prevent false positives
- **Verification**: Use the source IDs to examine the original records in the datasets
- **Country Unknown**: Records with `Copyright_Status = "Country Unknown"` will always have `Country_Classification = Unknown` and typically empty `Country_Code` fields
- **Similarity Score Calculation**: Title/author use Levenshtein distance; publisher uses dual fuzzy matching strategies
- **Threshold Enforcement**: All matches must meet similarity thresholds to be recorded, ensuring match quality

## Configuration Files

### wordlists.json

Contains all word lists and patterns for text processing:

- **Abbreviations**: 130+ bibliographic abbreviations (AACR2 standard + NCBI additions)
- **Stopwords**: By category (general, publisher, author, title, edition) and language
- **Patterns**:
  - Generic titles (collected works, poems, etc.)
  - Ordinals (1st, first, 2nd, second, etc.)
  - Author titles (dr, prof, sir, etc.)
  - Publisher suffixes (inc, ltd, corp, etc.)
- **Text fixes**: Unicode corruption mappings for common encoding issues

**Note**: All text normalization now requires wordlists.json to be present. Hardcoded fallbacks have been removed to ensure consistency.

### config.json

Contains matching configuration:

- Scoring weights by scenario
- Default thresholds
- Feature flags (stemming, abbreviation expansion)

## Performance Optimizations

1. **LCCN Direct Lookup**: O(1) lookup for records with LCCNs

   - Instant match for ground truth data
   - Bypasses all other processing
   - 10-20x faster for LCCN matches

1. **Multi-key Indexing**: Reduces comparisons from O(n×m) to O(k×c)

   - n,m = dataset sizes (millions)
   - k = keys per record (~10)
   - c = candidates per key (~100)

1. **Year Filtering First**: Eliminates 90%+ candidates immediately

1. **Early Termination**: Stops on high-confidence matches

1. **Persistent Caching**:

   - Indexes cached to disk (~2GB)
   - 85% reduction in startup time
   - Shared across worker processes

1. **Parallel Processing**:

   - Batches distributed across CPU cores
   - Platform-specific optimizations:
     - Linux: Indexes loaded once in main process, shared via fork()
     - macOS/Windows: Each worker loads indexes independently
   - Worker recycling based on workload (prevents memory leaks)
   - Batch pickling reduces memory usage (only active batch in RAM)
   - Linear scaling with core count
