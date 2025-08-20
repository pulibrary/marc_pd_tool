# Matching Algorithm and Copyright Status Determination

This document explains how the MARC Copyright Status Analysis Tool matches library records against copyright data and determines copyright status. It is written for people who understand library cataloging and copyright concepts but may not be programmers.

## Overview

The tool performs three main tasks:

1. Matches library catalog records against historical U.S. copyright registration and renewal data
1. Applies U.S. copyright law rules based on the matches found
1. Classifies each work into a specific copyright status category

## Data Sources

### Library Records (MARC)

Library catalog records contain bibliographic information about books and other publications. The tool extracts:

- **Title**: The main title and any subtitles or part information
- **Authors**: Both the controlled heading form and the transcribed statement of responsibility
- **Publication Information**: Publisher name, place of publication, and year
- **Country of Publication**: A three-letter code indicating where the work was published

### Copyright Registration Data (1923-1977)

Historical records of works registered for U.S. copyright protection. Each entry includes the title, author, publisher, and registration date as recorded when the copyright was registered.

### Copyright Renewal Data (1950-1991)

Records of copyright renewals. Under pre-1978 U.S. copyright law, copyrights had to be renewed after 28 years to maintain protection. These records show which works were renewed and which were not.

## The Matching Process

### Step 1: Country Classification

The tool first determines where a work was published using the MARC country code:

- **U.S. Publications**: Works published in the United States
- **Foreign Publications**: Works published outside the U.S.
- **Unknown**: Records without clear country information

This classification is crucial because U.S. and foreign works follow different copyright rules.

### Step 2: Text Normalization

Before comparing records, the tool normalizes text to handle variations in cataloging:

1. **Unicode to ASCII Conversion**: Converts accented characters (é→e, ñ→n)
1. **Case Normalization**: Converts everything to lowercase for comparison
1. **Abbreviation Expansion**: Expands common abbreviations (Co.→Company, Inc.→Incorporated)
1. **Number Normalization**: Standardizes numbers in various formats:
   - Roman numerals: XIV→14
   - Ordinal numbers: 1st→1, third→3
   - Written numbers: twenty-five→25
1. **Punctuation Removal**: Removes commas, periods, and other punctuation
1. **Stopword Removal**: Filters out common words that don't help with matching:
   - General stopwords: the, a, an, of, and
   - Title-specific: collected, complete, works, edition
   - Publisher-specific: company, press, publishers, incorporated
1. **Word Stemming**: Reduces words to their root form (publishing→publish, edited→edit)

### Step 3: Similarity Scoring

#### Title Matching

The tool compares normalized titles using a fuzzy matching algorithm that calculates how similar two strings are, returning a score from 0 (completely different) to 100 (identical).

The algorithm handles:

- Word order variations ("Adventures of Tom Sawyer" vs "Tom Sawyer Adventures")
- Minor spelling differences
- Missing or extra words

#### Author Matching

Author names use a different matching approach that's more sensitive to:

- Name order (last name, first name vs first name last name)
- Initials vs full names
- Common variations in name recording

#### Publisher Matching

Publisher comparison accounts for:

- Company name variations
- Location information
- Imprint relationships

### Step 4: Match Determination

A match is confirmed when the similarity scores meet these thresholds:

- **Title similarity**: 40% or higher
- **Author similarity**: 30% or higher (if author data exists)
- **Publisher similarity**: 30% or higher (if publisher data exists)
- **Year tolerance**: Publication years must be within 1 year of each other

The tool uses an "early exit" optimization: if the title score is extremely high (95% or above), it may accept the match without checking other fields.

### Step 5: Special Cases

#### LCCN (Library of Congress Control Number) Matching

When both the MARC record and copyright data contain an LCCN, the tool uses this for direct matching. This provides high-confidence matches without relying on text similarity.

#### Generic Titles

The tool recognizes common generic titles that appear frequently and adjusts scoring accordingly:

- "Annual Report"
- "Collected Works"
- "Complete Works"
- "Selected Poems"

For these titles, author and publisher matching becomes more important.

#### Records Without Years

By default, the tool skips records without publication years to improve performance. The `--brute-force-missing-year` option enables checking these records against all copyright data, though this is much slower.

## Copyright Status Determination

Once matching is complete, the tool applies U.S. copyright law rules to determine status:

### For U.S. Publications

#### Published Before Copyright Expiration (current year - 96)

- **Status**: `US_PRE_[YEAR]` (e.g., `US_PRE_1929`)
- **Meaning**: In the public domain due to copyright expiration

#### Published Between Copyright Expiration and 1977

If registered and renewed:

- **Status**: `US_RENEWED`
- **Meaning**: Still under copyright protection

If registered but not renewed:

- **Status**: `US_REGISTERED_NOT_RENEWED`
- **Meaning**: In the public domain due to non-renewal

If no registration found:

- **Status**: `US_NO_MATCH`
- **Meaning**: Possibly never copyrighted or records not digitized

#### Published After 1977

- **Status**: `US_RENEWED` (if renewal found)
- **Meaning**: Different copyright rules apply (1978 Copyright Act)

### For Foreign Publications

Foreign works have different copyright rules and the tool provides informational matching:

If renewed in the U.S.:

- **Status**: `FOREIGN_RENEWED_[COUNTRY]` (e.g., `FOREIGN_RENEWED_GBR`)
- **Meaning**: Had U.S. copyright protection through renewal

If registered but not renewed:

- **Status**: `FOREIGN_REGISTERED_NOT_RENEWED_[COUNTRY]`
- **Meaning**: Had U.S. registration but was not renewed

If no U.S. copyright records:

- **Status**: `FOREIGN_NO_MATCH_[COUNTRY]`
- **Meaning**: No U.S. copyright activity found

### For Unknown Country

When the country cannot be determined, the tool provides limited analysis:

- `COUNTRY_UNKNOWN_RENEWED`: Renewal found
- `COUNTRY_UNKNOWN_REGISTERED_NOT_RENEWED`: Registration only
- `COUNTRY_UNKNOWN_NO_MATCH`: No matches found

### Special Statuses

#### Beyond Data Coverage

- **Status**: `OUT_OF_DATA_RANGE_[YEAR]`
- **Meaning**: Published after our renewal data ends (1991)

## Confidence and Accuracy

### High Confidence Indicators

- LCCN matches (direct identifier match)
- Very high title similarity (>90%)
- Multiple field matches (title + author + publisher)
- Clear registration and renewal patterns

### Lower Confidence Indicators

- Generic titles
- Missing author or publisher data
- Borderline similarity scores
- Records from the edges of our data coverage

### Limitations

1. **Data Coverage**: Registration data covers 1923-1977, renewal data 1950-1991
1. **Digitization Gaps**: Not all copyright records have been digitized
1. **Cataloging Variations**: Different cataloging standards over time
1. **Foreign Works**: Limited ability to determine foreign copyright status
1. **Post-1978 Works**: Different copyright law makes determination complex

## Improving Results

To get the best results:

1. Ensure MARC records have complete bibliographic data
1. Include publication years whenever possible
1. Review matches with borderline scores manually
1. Consider the copyright status as guidance requiring legal review for important decisions
1. Use the `--score-everything` option to see best matches even below thresholds

## Quality Assurance and Testing

### Regression Testing

The tool includes a comprehensive regression testing system to ensure the matching algorithm maintains accuracy and catches any unintended changes. This system uses approximately 20,000 known correct matches as a baseline.

For detailed information about the regression testing system, see [tests/regression/README.md](../tests/regression/README.md).

Key features:

- Baseline scoring against known matches
- Detection of algorithm improvements vs regressions
- Statistical analysis of score distributions
- Separate test suite that doesn't run with regular tests

## Output Interpretation

The tool provides several pieces of information for each record:

- **Copyright Status**: The determined status based on the analysis
- **Match Scores**: Similarity percentages for title, author, and publisher
- **Match Type**: Whether matched by LCCN or similarity scoring
- **Country Classification**: U.S., Foreign, or Unknown
- **Rule Applied**: The specific copyright law rule used for determination

This information helps users understand not just what the copyright status is, but why that determination was made and how confident the tool is in its analysis.
