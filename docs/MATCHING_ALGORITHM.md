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

1. **Encoding Corruption Detection**: Detects and fixes UTF-8 text incorrectly interpreted as Latin-1 (mojibake)
   - Example: "RevÃ£rend's" → "Reverend's"
   - Common in older records that went through multiple encoding conversions
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

The tool uses multiple strategies to compare titles accurately:

1. **Title Containment Detection**: Recognizes when one title contains another (subtitles/series)

   - Example: "Tax Guide" vs "Tax Guide 1934" scores 85-95%
   - Requires 30% containment ratio to prevent false positives
   - Higher scores when contained at start (likely subtitle)

1. **Smarter Fuzzy Matching**: Enhanced algorithm that reduces false positives

   - Single distinctive word matches capped at 60%
   - Applies penalties for stem-only similarity (England/English)
   - Filters common words to prevent score inflation
   - Returns scores from 0 (completely different) to 100 (identical)

1. **Standard Fuzzy Matching**: Handles common variations

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

#### Derived Work Detection

The tool identifies and applies penalties for derived works that are not the original:

- **Indexes**: "Index to...", "Cumulative index"
- **Bibliographies**: "Bibliography of...", "References"
- **Supplements**: "Supplement to...", "Addendum"
- **Guides**: "Study guide", "Teacher's guide"

Multi-language support for English, French, German, Spanish, and Italian.

### Step 4: Match Determination

A match is confirmed when the similarity scores meet these thresholds:

- **Title similarity**: 25% or higher (base threshold)
- **Author similarity**: 20% or higher (if author data exists)
- **Publisher similarity**: 50% or higher (if publisher data exists)
- **Year tolerance**: Publication years must be within 1 year of each other
- **Combined minimum score**: 35% or higher (increased from 30% for better precision)

#### Score Combination and Validation

The tool combines field scores using weighted averages with several refinements:

1. **Multi-Field Validation**: Prevents single-field dominance

   - At least TWO fields must have reasonable scores (>30%)
   - Single field matches (even 100%) cap combined score at 25%
   - Author-only or publisher-only matches receive 0.5x penalty

1. **Missing Field Weight Redistribution**: When ONE field is missing but others match well

   - If title >70% and exactly one field missing: redistributes weights
   - Example: Missing publisher but strong title/author match gets fair scoring
   - Never applies when BOTH author AND publisher are missing

1. **Derived Work Penalties**: Based on confidence and type match

   - Both same type of derived work: 10% penalty
   - Different types: 30% penalty
   - One derived, one not: 50% penalty

#### Library of Congress Control Number (LCCN) Matching

When both the MARC record and copyright record have the same LCCN (a unique identifier assigned by the Library of Congress), the match receives a conditional boost:

- **Strong field agreement** (title ≥40%): Full 20-point boost
- **Moderate agreement** (title ≥20% AND author/publisher ≥60%): 15-point boost
- **Weak agreement** (author ≥80% AND publisher ≥60%): 10-point boost
- **Poor agreement**: Minimal 5-point boost (likely cataloging error)

This conditional approach guards against LCCN cataloging errors while still providing valuable signal.

**Important**: The vast majority of records do not have LCCNs, so the base thresholds are calibrated to work well without this boost.

### Step 5: Special Cases

#### Generic Titles

The tool recognizes common generic titles that appear frequently and adjusts scoring accordingly:

- "Annual Report"
- "Collected Works"
- "Complete Works"
- "Selected Poems"

For these titles, author and publisher matching becomes more important.

#### Title Containment Cases

The tool handles titles that contain subtitles or series information:

- **Subtitles**: "Main Title: A Subtitle" matches "Main Title" at 85-95%
- **Series**: "Book Title Volume 3" matches "Book Title" at high confidence
- **Year variations**: "Tax Guide 1934" matches "Tax Guide" appropriately

This prevents false negatives when cataloging practices differ between sources.

#### Derived Works

The tool identifies and appropriately handles derived works:

- **Indexes and bibliographies** of original works
- **Supplements and addenda** to main publications
- **Study guides and teacher's editions**
- **Translations and adaptations**

These receive graduated penalties to prevent false positive matches with the original work.

#### Missing Field Handling

When records have incomplete data:

- **Missing publisher**: Weight redistributed if title and author match strongly
- **Missing author**: Corporate works often lack author fields
- **Both missing**: Stricter validation required, no redistribution

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

### Performance Metrics

Based on validation against 19,594 known matches and 377 known mismatches:

- **True Positive Rate**: 99.4% at threshold 35
- **False Positive Reduction**: 99.2% (from 377 to 3)
- **Precision**: ~100% (essentially perfect)
- **F1 Score**: 0.9969 (near perfect)

### High Confidence Indicators

- LCCN matches with strong field agreement
- Very high title similarity (>90%)
- Multiple field matches (title + author + publisher all >30%)
- Title containment detection (subtitle/series match)
- Clear registration and renewal patterns

### Lower Confidence Indicators

- Single field match only
- Generic titles
- Missing author or publisher data
- Borderline similarity scores (near 35% threshold)
- Derived work detection triggered
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

### Scoring Tests

The tool includes a comprehensive scoring test system to ensure the matching algorithm maintains accuracy and catches any unintended changes. This system uses 19,594 known correct matches and 377 known mismatches as baselines.

For detailed information about the scoring test system, see [tests/scoring/README.md](../tests/scoring/README.md).

Key features:

- Baseline scoring against known matches
- Detection of algorithm improvements vs regressions
- Statistical analysis of score distributions
- Separate test suite that doesn't run with regular tests
- Validation of all seven phases of matching improvements

## Output Interpretation

The tool provides several pieces of information for each record:

- **Copyright Status**: The determined status based on the analysis
- **Match Scores**: Similarity percentages for title, author, and publisher
- **Match Type**: Whether matched by LCCN or similarity scoring
- **Country Classification**: U.S., Foreign, or Unknown
- **Rule Applied**: The specific copyright law rule used for determination

This information helps users understand not just what the copyright status is, but why that determination was made and how confident the tool is in its analysis.
