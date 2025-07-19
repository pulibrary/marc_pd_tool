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

- **Author Type Recognition**: Personal names (field 100), corporate names (field 110), and meeting names (field 111) are handled with appropriate parsing strategies
- **Publisher Indexing**: Multi-key indexing includes publisher information with specialized stopword filtering
- **Intelligent Indexing**: Multi-key indexing reduces search space from billions to thousands of candidates per query
- **Smart Word Filtering**: Only significant words are used for key generation, with publishing-specific stopwords removed

**Matching Process:**

1. **Candidate Finding**: Uses multiple indexing strategies to find potential matches
1. **Threshold-Based Matching**: Candidates must meet similarity thresholds to be recorded as matches:
   - Title similarity ≥ 80% (default)
   - Author similarity ≥ 70% (default, when both authors exist)
   - Publisher similarity ≥ 60% (default, when MARC has publisher data)
   - Publication year within ±2 years
1. **Strict Matching**: Only candidates that meet similarity thresholds are recorded as matches

**Matching Criteria:**

- Title similarity (weighted 60% or 70%, calculated using Levenshtein distance)
- Author similarity (weighted 25% or 30%, calculated using Levenshtein distance) - using author type-specific parsing
- Publisher similarity (weighted 15%, calculated using fuzzy matching strategies)
- Publication year (within ±2 years)
- Combined score (adaptive weighting based on available data):
  - **With publisher data**: `(title_score * 0.6) + (author_score * 0.25) + (publisher_score * 0.15)`
  - **Without publisher data**: `(title_score * 0.7) + (author_score * 0.3)` (redistributes publisher weight)

**Important: Scoring Method**

All similarity scores are calculated using fuzzy string matching on normalized text:

- **Title & Author Similarity**: Direct comparison using Levenshtein distance (`fuzz.ratio()`)
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

- **Field 008**: Country codes (positions 15-17) and publication dates
- **Fields 264/260**: Publication data (RDA and AACR2 formats)
- **Field 245$c**: Author information from statement of responsibility (more likely to match copyright data format than formal authority fields)

### 3. Copyright Status Determination

Based on the pattern of matches found, we assign one of five copyright status categories:

**For US Publications:**

- **Registration but no renewal found** → `POTENTIALLY_PD_DATE_VERIFY`: The work was registered but we found no renewal, suggesting it may be public domain (verify renewal deadline)
- **Renewal found** → `POTENTIALLY_IN_COPYRIGHT`: The work was renewed and is likely still under copyright protection
- **Both registration and renewal found** → `POTENTIALLY_IN_COPYRIGHT`: The work followed the full copyright process
- **Neither found** → `POTENTIALLY_PD_DATE_VERIFY`: No registration found, may be public domain or never registered

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

**POTENTIALLY_PD_DATE_VERIFY**: These works show patterns suggesting they may be in the public domain, but date verification is needed. For pre-1978 works, check if renewal was required and whether the 28-year deadline was met.

**POTENTIALLY_IN_COPYRIGHT**: These works show evidence of copyright renewal or other indicators suggesting they may still be under copyright protection. Assume these are copyrighted unless proven otherwise.

**RESEARCH_US_STATUS**: Foreign works with some US copyright registration. The copyright status depends on complex factors including publication date, registration timing, and international copyright treaties.

**RESEARCH_US_ONLY_PD**: Foreign works with no US copyright registration found. These may be public domain in the US due to lack of compliance with US copyright formalities, but may still be copyrighted in their country of origin.

**COUNTRY_UNKNOWN**: Records where copyright status cannot be determined due to missing or invalid country information in the MARC record. These require manual investigation to determine the country of publication before copyright analysis can proceed.

### Using the Results

The tool produces a CSV file with comprehensive analysis results:

**MARC Record Data:**

- MARC ID, MARC Title, MARC Author, MARC Year, MARC Publisher, MARC Place

**Country Classification:**

- Country Code (from MARC 008 field), Country Classification (US/Non-US/Unknown)

**Copyright Analysis Results:**

- Copyright Status (algorithmic determination)
- Registration Source ID, Renewal Entry ID (source IDs for lookup)
- Registration Similarity Score, Renewal Similarity Score (overall match quality)

**Complete CSV Column Headers:**

- MARC ID, MARC Title, MARC Author, MARC Year, MARC Publisher, MARC Place
- Country Code, Country Classification, Copyright Status
- Registration Source ID, Renewal Entry ID
- Registration Title, Registration Author, Registration Publisher, Registration Date
- Registration Similarity Score, Registration Title Score, Registration Author Score, Registration Publisher Score
- Renewal Title, Renewal Author, Renewal Publisher, Renewal Date
- Renewal Similarity Score, Renewal Title Score, Renewal Author Score, Renewal Publisher Score

**Sample Output:**

```csv
MARC ID,MARC Title,MARC Author,MARC Year,MARC Publisher,Country Code,Country Classification,Copyright Status,Registration Source ID,Renewal Entry ID,Registration Title,Registration Author,Registration Publisher,Registration Similarity Score,Registration Title Score,Registration Author Score,Registration Publisher Score,Renewal Title,Renewal Author,Renewal Publisher,Renewal Similarity Score,Renewal Title Score,Renewal Author Score,Renewal Publisher Score
99123456,The Great Novel,Smith John,1955,Great Books Inc,xxu,US,POTENTIALLY_PD_DATE_VERIFY,R456789,,The great novel,Smith John,Great Books Inc,82.5,85.0,75.0,90.0,,,,,,
99789012,Another Book,Jones Mary,1960,Academic Press,uk,Non-US,RESEARCH_US_STATUS,,b3ce7263-9e8b-5f9e-b1a0-190723af8d29,,,Academic Press snippet,75.3,78.0,70.0,,Another book,Jones Mary,Academic Press,82.1,85.0,72.0,75.0
99345678,Mystery Work,Author Unknown,1950,,,,Country Unknown,,,,,,,,,,,,,,
99111222,Popular Title,Common Author,1965,Popular Publishers,xxu,US,POTENTIALLY_IN_COPYRIGHT,R111111,d6a7cb69-27b6-5f04-9ab6-53813a4d8947,Popular title,Common Author,Popular Publishers,88.7,90.0,85.0,95.0,Popular title,Common Author,Popular Publishers,89.2,91.0,86.0,92.0
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
- **Verification**: Use the source IDs to examine the original records in the datasets
- **Country Unknown**: Records with `Copyright_Status = "Country Unknown"` will always have `Country_Classification = Unknown` and typically empty `Country_Code` fields
- **Similarity Score Calculation**: Title/author use Levenshtein distance; publisher uses dual fuzzy matching strategies
- **Threshold Enforcement**: All matches must meet similarity thresholds to be recorded, ensuring match quality
