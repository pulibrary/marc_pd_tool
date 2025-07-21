# MARC Copyright Analysis: What We're Doing and How

## Overview

This tool analyzes library records to determine copyright status by comparing them against U.S. copyright registration and renewal data as digitized by the New York Public Library. The goal is to help identify works that may be in the public domain or require further copyright research.

## The Data Sources

### MARC Records

The publications we're analyzing - bibliographic records from a library catalog that contain title, author, publication date, publisher, place of publication, and country information. We focus on the country code to determine whether a work was published in the US or elsewhere, as this affects copyright analysis. Right now we only support MARC XML.

### Copyright Registration Data

Historical U.S. copyright registrations from 1923-1977,
[digitized by NYPL from the Catalog of Copyright Entries Project](https://github.com/NYPL/catalog_of_copyright_entries_project). When a work was registered for copyright, it was listed in these catalogs with title, author, publication date, publisher, and place information.

### Renewal Data

U.S. copyright renewal records from 1950-1991, also digitized by NYPL as part of the [CCE-Renewals Project](https://github.com/NYPL/cce-renewals). Under the pre-1978 copyright law, works had to be renewed after 28 years to maintain copyright protection. These records show which works were renewed and which were not.

## The Analysis Process

### 1. Data Preparation

We extract bibliographic information from MARC records and classify each publication by country of origin using the Library of Congress country codes.

**Year Filtering**: By default, we focus on works published in the current year minus 95, since earlier works are likely in the public domain regardless of registration status. Users can specify custom year ranges using `--min-year` and `--max-year` options to focus on specific time periods or analyze single years.

### 2. Matching Publications

For each MARC record, we search for similar entries in both the registration and renewal datasets. We use fuzzy string matching to account for variations in how titles and authors might be recorded across different sources.

**Enhanced Matching Features:**

- **Dual Author Extraction**: Leverages both MARC 1xx fields (normalized controlled vocabulary) and 245$c (transcribed statement of responsibility) for optimal author matching
- **Enhanced Part Support**: Extracts part numbers from MARC 245$n and part names from 245$p, plus volume information from copyright/renewal data for improved multi-part work identification
- **Author Type Recognition**: Personal names (field 100), corporate names (field 110), and meeting names (field 111) are handled with appropriate parsing strategies
- **Publisher Indexing**: Multi-key indexing includes publisher information with specialized stopword filtering
- **Edition Indexing**: Multi-key indexing includes edition information when available, with ordinal and descriptive term recognition
- **Generic Title Detection**: Dynamic scoring adjustments for generic titles like "collected works" (English-only)
- **Language-Aware Processing**: Uses MARC language codes to apply appropriate detection strategies
- **Intelligent Indexing**: Multi-key indexing reduces search space from billions to thousands of candidates per query
- **Smart Word Filtering**: Only significant words are used for key generation, with publishing and edition-specific stopwords removed

**Matching Process:**

1. **Candidate Finding**: Uses multiple indexing strategies to find potential matches
1. **Threshold-Based Matching**: Candidates must meet similarity thresholds to be recorded as matches:
   - Title similarity ≥ 80% (default)
   - Author similarity ≥ 70% (default, when both authors exist)
   - Publisher similarity ≥ 60% (default, when MARC has publisher data)
   - Publication year within ±2 years
1. **Strict Matching**: Only candidates that meet similarity thresholds are recorded as matches

**Matching Criteria:**

- Title similarity (weighted 30-70%, calculated using Levenshtein distance)
- Author similarity (weighted 25-60%, calculated using Levenshtein distance) - using author type-specific parsing
- Publisher similarity (weighted 15-25%, calculated using fuzzy matching strategies)
- Publication year (within ±2 years)
- Combined score (adaptive weighting based on available data and generic title detection):
  - **Normal titles with publisher**: `(title_score * 0.6) + (author_score * 0.25) + (publisher_score * 0.15)`
  - **Generic titles with publisher**: `(title_score * 0.3) + (author_score * 0.45) + (publisher_score * 0.25)`
  - **Normal titles without publisher**: `(title_score * 0.7) + (author_score * 0.3)`
  - **Generic titles without publisher**: `(title_score * 0.4) + (author_score * 0.6)`

**Dual Author Matching Strategy**

The system now extracts and utilizes two types of author information from MARC records:

1. **Main Author (1xx fields)**: Normalized controlled vocabulary entries

   - **100$a**: Personal names in "Last, First, dates" format (dates automatically cleaned)
   - **110$a**: Corporate names
   - **111$a**: Meeting names
   - **Priority order**: 100 → 110 → 111 (uses first available)

1. **Statement of Responsibility (245$c)**: Transcribed directly from title page

   - Natural language format as published
   - May include roles, multiple contributors, etc.

**Author Scoring Algorithm**:

- Calculates similarity scores for both author types against copyright data
- Uses `max(score_245c, score_1xx)` to leverage whichever format matches better
- Provides optimal matching for both controlled vocabulary and natural language variants

**Important: Scoring Method**

All similarity scores are calculated using fuzzy string matching on normalized text:

- **Title Similarity**: Includes part information for comprehensive multi-part work matching
- **Author Similarity**: Dual scoring as described above using Levenshtein distance (`fuzz.ratio()`)
- **Publisher Similarity**: Uses different strategies based on data source:
  - **Registration matches**: Direct comparison using `fuzz.ratio()` (MARC publisher vs registration publisher)
  - **Renewal matches**: Fuzzy matching using `fuzz.partial_ratio()` (MARC publisher vs renewal full_text)
- **Threshold Application**: All matches must meet similarity thresholds to be recorded
- **CSV Output**: Shows the actual similarity scores for recorded matches

**Single Best Match:**

Each MARC record can have at most one match in each dataset (registration and renewal). The tool:

- Finds the BEST match that meets the similarity thresholds
- Records the match with its source ID and similarity scores
- Uses this single match for copyright status determination

**MARC Fields Used for Extraction:**

- **Field 008**: Country codes (positions 15-17), language codes (positions 35-37), and publication dates
- **Field 041$a**: Language codes (fallback if not in field 008)
- **Fields 264/260**: Publication data (RDA and AACR2 formats)
- **Field 245$c**: Author information from statement of responsibility (more likely to match copyright data format than formal authority fields)
- **Field 250$a**: Edition statements (e.g., "2nd ed.", "Revised edition", "First printing")

### 3. Generic Title Detection

Before applying similarity scoring, the system detects generic titles that would provide poor discrimination between different works.

**Detection Methods:**

1. **Pattern Matching**: Recognizes common generic title patterns:

   - Collections: "collected works", "selected writings", "complete works"
   - Genre-specific: "poems", "essays", "short stories", "plays", "letters"
   - Academic: "proceedings", "transactions", "papers", "studies"

1. **Frequency Analysis**: Identifies titles appearing frequently across the dataset (configurable threshold, default: 10+ occurrences)

1. **Linguistic Patterns**: Detects short titles with high stopword ratios or single genre words

**Language Limitation**: Generic title detection currently works only for English titles (language codes 'eng', 'en'). Non-English titles bypass generic detection using a conservative approach to prevent false positives.

**Scoring Adjustment**: When generic titles are detected, the algorithm reduces title weight and increases author/publisher weights to emphasize more discriminating fields.

### 4. Copyright Status Determination

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

## Understanding the Results

### What the Status Categories Mean

**PD_NO_RENEWAL**: These works are in the public domain. This applies specifically to US works published 1930-1963 that were registered for copyright but not renewed within the required 28-year period.

**PD_DATE_VERIFY**: These works show patterns suggesting they may be in the public domain, but date verification is needed. For pre-1978 works, check if renewal was required and whether the 28-year deadline was met.

**IN_COPYRIGHT**: These works show evidence of copyright renewal or other indicators suggesting they may still be under copyright protection. Assume these are copyrighted unless proven otherwise.

**RESEARCH_US_STATUS**: Foreign works with some US copyright registration. The copyright status depends on complex factors including publication date, registration timing, and international copyright treaties.

**RESEARCH_US_ONLY_PD**: Foreign works with no US copyright registration found. These may be public domain in the US due to lack of compliance with US copyright formalities, but may still be copyrighted in their country of origin.

**COUNTRY_UNKNOWN**: Records where copyright status cannot be determined due to missing or invalid country information in the MARC record. These require manual investigation to determine the country of publication before copyright analysis can proceed.

### Using the Results

The tool produces a CSV file with comprehensive analysis results:

**MARC Record Data:**

- MARC ID, MARC Title, MARC Author, MARC Year, MARC Publisher, MARC Place, MARC Edition, Language Code

**Country Classification:**

- Country Code (from MARC 008 field), Country Classification (US/Non-US/Unknown)

**Copyright Analysis Results:**

- Copyright Status (algorithmic determination)
- Generic Title Detected, Generic Detection Reason (scoring adjustment tracking)
- Registration Generic Title, Renewal Generic Title (per-dataset detection)
- Registration Source ID, Renewal Entry ID (source IDs for lookup)
- Registration Similarity Score, Renewal Similarity Score (overall match quality)

**Complete CSV Column Headers:**

- MARC ID, MARC Title, MARC Author, MARC Year, MARC Publisher, MARC Place, MARC Edition, Language Code
- Country Code, Country Classification, Copyright Status
- Generic Title Detected, Generic Detection Reason, Registration Generic Title, Renewal Generic Title
- Registration Source ID, Renewal Entry ID
- Registration Title, Registration Author, Registration Publisher, Registration Date
- Registration Similarity Score, Registration Title Score, Registration Author Score, Registration Publisher Score
- Renewal Title, Renewal Author, Renewal Publisher, Renewal Date
- Renewal Similarity Score, Renewal Title Score, Renewal Author Score, Renewal Publisher Score

**Sample Output:**

```csv
MARC ID,MARC Title,MARC Author,MARC Year,MARC Publisher,MARC Place,MARC Edition,Language Code,Country Code,Country Classification,Copyright Status,Generic Title Detected,Generic Detection Reason,Registration Generic Title,Renewal Generic Title,Registration Source ID,Renewal Entry ID,Registration Title,Registration Author,Registration Publisher,Registration Date,Registration Similarity Score,Registration Title Score,Registration Author Score,Registration Publisher Score,Renewal Title,Renewal Author,Renewal Publisher,Renewal Date,Renewal Similarity Score,Renewal Title Score,Renewal Author Score,Renewal Publisher Score
99123456,The Great Novel,Smith John,1955,Great Books Inc,New York,First edition,eng,xxu,US,PD_DATE_VERIFY,False,none,False,False,R456789,,The great novel,Smith John,Great Books Inc,1955,82.5,85.0,75.0,90.0,,,,,,,,
99234567,American Classic,Brown Alice,1947,US Publishers,Chicago,1st ed.,eng,xxu,US,PD_NO_RENEWAL,False,none,False,False,R789123,,American classic,Brown Alice,US Publishers,1947,88.2,92.0,81.0,88.0,,,,,,,,
99789012,Complete Works,Jones Mary,1960,Academic Press,London,2nd ed.,fre,uk,Non-US,RESEARCH_US_STATUS,False,skipped_non_english_fre,False,False,,b3ce7263-9e8b-5f9e-b1a0-190723af8d29,,,Academic Press snippet,1960,75.3,78.0,70.0,,Complete works,Jones Mary,Academic Press,1960,82.1,85.0,72.0,75.0
99345678,Mystery Work,Author Unknown,1950,,,,,,,COUNTRY_UNKNOWN,False,none,False,False,,,,,,,,,,,,,,,,
99111222,Collected Poems,Common Author,1965,Popular Publishers,Boston,Rev. ed.,eng,xxu,US,IN_COPYRIGHT,True,pattern,True,True,R111111,d6a7cb69-27b6-5f04-9ab6-53813a4d8947,Collected poems,Common Author,Popular Publishers,1965,65.3,50.0,85.0,95.0,Collected poems,Common Author,Popular Publishers,1965,66.8,52.0,86.0,92.0
```

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
