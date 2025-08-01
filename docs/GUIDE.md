# Usage Guide

## How the Tool Works

The tool analyzes library catalog records (MARC) to determine copyright status by comparing them against historical U.S. copyright data.

### Data Flow Overview

```
Input Files → Loading → Indexing → Matching → Analysis → Output Files
```

### Data Sources

1. **Your MARC Records** (MARCXML files)

   - **Extracted by**: `MarcLoader` class
   - **Data used**:
     - Title (245 field with subfields $a, $b, $n, $p)
     - Authors (100/110/111 fields and 245$c)
     - Publication info (260/264 fields)
     - Country code (008 field, positions 15-17)
     - LCCN when available (010 field)
     - Language and edition information

1. **Copyright Registration Data** (XML files, 1923-1977)

   - **Extracted by**: `CopyrightDataLoader` class
   - **Data used**: Title, author, publisher, registration date/number
   - **Storage**: Both normalized and original versions kept

1. **Copyright Renewal Data** (TSV files, 1950-1991)

   - **Extracted by**: `RenewalDataLoader` class
   - **Data used**: Title, author, renewal date, full text entry
   - **Storage**: Both normalized and original versions kept

### The Matching Process

1. **Loading Phase**

   - MARC records are loaded and filtered by year (if specified)
   - Copyright and renewal data are loaded into memory
   - All text is stored in both original and normalized forms

1. **Indexing Phase**

   - Creates searchable indexes for fast lookup:
     - Title words and combinations
     - Author surnames and full names
     - Publisher keywords
     - Publication years
     - LCCNs for instant matching
   - Reduces millions of comparisons to hundreds

1. **Matching Phase**

   - For each MARC record:
     - Generate index keys from title/author/year
     - Find candidate matches using indexes
     - Calculate similarity scores for each candidate
     - Select best match above thresholds
   - Special handling:
     - LCCN matches get 100% score immediately
     - High scores (>95%) trigger early exit
     - Generic titles get adjusted scoring

1. **Analysis Phase**

   - Copyright status determined by country and match pattern
   - Results include match details and similarity scores
   - Single best match per dataset (registration and renewal)

1. **Export Phase**

   - Results formatted as CSV or XLSX
   - Organized by copyright status
   - Includes all match details for verification

## Understanding Results

### Copyright Status Categories

**PD_NO_RENEWAL** - Public domain due to non-renewal

- US works published 1930-1963 that were registered but not renewed
- These are definitively in the public domain

**PD_DATE_VERIFY** - Potentially public domain, needs date verification

- Works that may be public domain based on publication date
- Verify the specific copyright requirements for the publication year

**IN_COPYRIGHT** - Likely still under copyright

- Works that show evidence of renewal or other copyright protection
- Assume copyrighted unless proven otherwise

**RESEARCH_US_STATUS** - Foreign work with US copyright activity

- Non-US works that have some US copyright registration
- Complex cases requiring additional research

**RESEARCH_US_ONLY_PD** - Foreign work possibly public domain in US only

- Non-US works with no US copyright registration found
- May be public domain in US but copyrighted elsewhere

**COUNTRY_UNKNOWN** - Cannot determine without country information

- MARC record lacks valid country code
- Manual investigation needed

### Understanding Output

The simplified output format focuses on what matters:

**Match Summary Column**

Shows match results in a clear format:

- `Reg: 95%, Ren: 82%` - Similarity scores for registration and renewal matches
- `Reg: LCCN, Ren: None` - LCCN match for registration, no renewal found
- `Reg: None, Ren: None` - No matches found

**Status Column**

Copyright status codes:

- `PD_NO_RENEWAL` - Public domain, not renewed (1930-1963 US works)
- `PD_DATE_VERIFY` - Likely public domain based on date
- `IN_COPYRIGHT` - Still protected by copyright
- `RESEARCH_US_STATUS` - Foreign work with US registration
- `RESEARCH_US_ONLY_PD` - Foreign work, likely PD in US only
- `COUNTRY_UNKNOWN` - Cannot determine country of publication

**Warning Column**

Data quality flags:

- `Generic title` - Common title like "Collected Works"
- `No year` - Missing publication year
- `Unknown country` - Cannot determine publication country

**Source ID Columns**

- **Registration Source ID** - Identifier from copyright registration data
- **Renewal Entry ID** - UUID from renewal database

### Choosing an Output Format

**CSV (Default)**

- Best for: Quick analysis, importing to other tools
- Use when: You need simple, tabular data
- Creates: Separate files by copyright status (or single file with `--single-file`)

**XLSX**

- Best for: Manual review with better formatting
- Use when: You want all results in one file with multiple tabs
- Creates: Single Excel file with tabs for each copyright status

**JSON**

- Best for: Custom tools, programmatic processing
- Use when: You need complete data for further analysis
- Includes: All fields, normalized versions, comprehensive metadata
- Creates: Single JSON file (or one per status without `--single-file`)

## Common Workflows

### Basic Analysis

```bash
# Analyze all records
pdm run python -m marc_pd_tool \
    --marcxml data.xml \
    --copyright-dir copyright_xml/ \
    --renewal-dir cce-renewals/data/
```

### Focus on Specific Years

```bash
# Analyze 1950s publications only
pdm run python -m marc_pd_tool \
    --marcxml data.xml \
    --copyright-dir copyright_xml/ \
    --renewal-dir cce-renewals/data/ \
    --min-year 1950 \
    --max-year 1959
```

### US Publications Only

```bash
# Much faster when focusing on US works
pdm run python -m marc_pd_tool \
    --marcxml data.xml \
    --copyright-dir copyright_xml/ \
    --renewal-dir cce-renewals/data/ \
    --us-only
```

### Adjusting Match Sensitivity

```bash
# Lower thresholds for older/OCR'd data
pdm run python -m marc_pd_tool \
    --marcxml data.xml \
    --copyright-dir copyright_xml/ \
    --renewal-dir cce-renewals/data/ \
    --title-threshold 35 \
    --author-threshold 25
```

### Performance Optimization

```bash
# Use more CPU cores and larger batches
pdm run python -m marc_pd_tool \
    --marcxml data.xml \
    --copyright-dir copyright_xml/ \
    --renewal-dir cce-renewals/data/ \
    --max-workers 16 \
    --batch-size 500
```

## Troubleshooting

### No Matches Found

- Try lowering thresholds: `--title-threshold 30 --author-threshold 20`
- Check year ranges aren't too restrictive
- Use `--score-everything` to see all scores regardless of thresholds
- Verify data directories are correct

### Tool Runs Slowly

- Use year filtering: `--min-year 1950 --max-year 1970`
- Enable US-only mode if applicable: `--us-only`
- Ensure cache is enabled (no `--disable-cache`)
- Check available CPU cores and adjust `--max-workers`

### Out of Memory

- Reduce batch size: `--batch-size 50`
- Use fewer workers: `--max-workers 4`
- Apply year filtering to reduce dataset size
- Process MARC file in smaller chunks

### Cache Issues

- Force rebuild: `--force-refresh`
- Delete cache: `rm -rf .marcpd_cache`
- Check disk space and permissions
- Use different cache location: `--cache-dir /path/to/cache`

### Understanding Low Scores

Low similarity scores can indicate:

- Different editions of the same work
- Spelling variations or typos
- Different citation formats
- OCR errors in historical data
- Abbreviated vs. full forms

### Verifying Results

Always verify important determinations by:

1. Checking the source IDs in the original datasets
1. Comparing matched titles/authors with MARC data
1. Consulting copyright law for the specific time period
1. Considering international copyright treaties for foreign works

## Performance Tips

### Expected Performance

- **Loading**: 10,000-50,000 records/second from files
- **Indexing**: 5,000-20,000 records/second into memory
- **Matching**: 2,000-5,000 records/minute (the bottleneck)
- **Cache benefit**: Reduces startup from 5-10 minutes to 10-30 seconds

### How Performance Features Work

1. **Persistent Cache** (~2GB)

   - Stores pre-built indexes on disk
   - Location: `.marcpd_cache/` directory
   - Rebuilds automatically when data changes
   - Use `--force-refresh` to manually rebuild

1. **Parallel Processing**

   - Splits MARC records into batches
   - Each CPU core processes a batch independently
   - Default: CPU count - 2 workers
   - Results combined at the end

1. **Smart Indexing**

   - Multi-key indexing reduces comparisons by 10-50x
   - Year filtering eliminates 90%+ candidates
   - LCCN lookup provides instant O(1) matching

### Optimization Strategies

1. **Year Filtering** - Most effective optimization
   - `--min-year 1950 --max-year 1960` reduces data by 90%+
1. **US-Only Mode** - 50-70% faster for US works
   - `--us-only` skips all non-US publications
1. **Adequate Hardware** - More CPU cores = faster processing
   - 16 cores can be 4x faster than 4 cores
1. **SSD Storage** - Improves cache performance
   - Cache on SSD loads 3-5x faster than HDD
1. **Appropriate Batch Size** - Balance memory vs. overhead
   - Larger batches = better performance but more memory

### Large Dataset Recommendations

For datasets over 100,000 records:

- Use year filtering to process in chunks
- Allocate sufficient memory (8GB+)
- Use fast storage for cache
- Consider running overnight
- Monitor progress with log files

### Memory Usage

- Base usage: ~500MB for application
- Registration data: ~1-2GB in memory
- Renewal data: ~500MB in memory
- MARC records: ~1KB per record
- Cache files: ~2GB on disk

## Data Quality Considerations

### Common Data Issues

- **OCR Errors** - Historical data may have transcription errors
- **Cataloging Variations** - Standards changed over time
- **Missing Data** - Not all fields present in all records
- **Name Variations** - Authors cited differently
- **Edition Differences** - Same work, different editions

### When to Trust Results

**High Confidence**:

- LCCN matches (match_type = "lccn")
- High similarity scores (>90%)
- Exact year matches
- US works with clear registration/renewal patterns

**Lower Confidence**:

- Low similarity scores (40-60%)
- Generic titles
- Foreign works
- Missing or ambiguous data
- Year mismatches

### Manual Verification

Consider manual verification for:

- High-value digitization projects
- Legal compliance requirements
- Borderline similarity scores
- Complex publication histories
- International works

## Threshold Analysis and Tuning

The tool provides two special modes to help analyze matching performance and determine appropriate thresholds for your data.

### Score Everything Mode

The `--score-everything-mode` finds the best match for every MARC record regardless of configured thresholds:

```bash
pdm run python -m marc_pd_tool \
    --marcxml data.marcxml \
    --score-everything-mode \
    --minimum-combined-score 20 \
    --output-filename all_scores.csv
```

This mode:

- Ignores title/author thresholds
- Finds the highest scoring match for each record
- Includes a combined similarity score column
- Useful for analyzing score distributions across your entire dataset

### Ground Truth Mode

The `--ground-truth-mode` extracts LCCN-verified matches and analyzes their similarity scores:

```bash
pdm run python -m marc_pd_tool \
    --marcxml data.marcxml \
    --ground-truth-mode \
    --min-year 1950 \
    --max-year 1960 \
    --output-filename ground_truth_analysis.csv
```

This mode:

1. Finds all MARC records with LCCNs
1. Matches them against copyright/renewal data using LCCN
1. Calculates similarity scores WITHOUT using LCCN matching
1. Generates statistical analysis of the score distributions

### Using the Analysis Results

Both modes export data that helps you understand matching performance:

**Score Everything Mode** provides:

- All records with their best matches
- Similarity scores for each field (title, author, publisher)
- Combined scores to see overall match quality
- Useful for identifying edge cases and outliers

**Ground Truth Mode** provides:

- Statistical analysis of verified matches
- Score distributions showing mean, median, percentiles
- Helps determine what thresholds would capture known good matches

Example workflow:

1. Run ground truth mode to analyze verified matches
1. Review the score distributions (e.g., if 5th percentile for title is 42)
1. Test thresholds using score everything mode
1. Apply chosen thresholds to production runs
