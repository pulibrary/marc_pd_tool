# MARC Copyright Status Analysis Tool

A tool for analyzing MARC bibliographic records to determine copyright status by comparing against both registration and renewal data using country classification and parallel processing.

## Overview

This tool implements a comprehensive algorithm to classify publications by copyright status. It compares MARC records against two distinct datasets and uses country of origin to determine appropriate copyright analysis pathways.

**Data Sources:**

- **MARC records**: Library catalog data in MARCXML format with country classification
- **Registration data**: Historical copyright registry entries (1923-1977) from the [NYPL Catalog of Copyright Entries Project](https://github.com/NYPL/catalog_of_copyright_entries_project)
- **Renewal data**: Copyright renewal records (1950-1991) from the [NYPL CCE Renewals Project](https://github.com/NYPL/cce-renewals)

## Quick Start

1. **Install dependencies:**

   ```bash
   pdm install
   ```

1. **Run analysis:**

   ```bash
   pdm run python compare.py \
       --marcxml path/to/marc_file.xml \
       --copyright-dir path/to/copyright_xml/ \
       --renewal-dir path/to/cce-renewals/data/
   ```

1. **Results:**

   - `matches.csv` - CSV with copyright status classifications
   - Country classification (US/Non-US/Unknown)
   - Registration and renewal match analysis
   - Completion time: Several hours for large datasets

## Performance

**Expected Performance:**
Processing large datasets (190K+ MARC records vs 2.1M+ registration entries + 445K+ renewal entries) typically takes several hours, depending on system specifications and dataset size.

The tool automatically uses all available CPU cores and includes several optimization features:

- **Public domain filtering**: Excludes records older than current year - 95 by default
- **Year-based filtering**: Only compares publications within ±2 years of each other
- **US-only filtering**: Optional `--us-only` flag to process only US publications (50-70% faster)
- **Parallel processing**: Efficient multi-core utilization with dual dataset matching
- **Smart memory management**: Streaming XML parsing and batch processing
- **Country classification**: Official MARC country codes for accurate geographic analysis

Example output analyzing ~160K MARC XML records on an 8-core system:

```bash
================================================================================
PUBLICATION COMPARISON COMPLETE
================================================================================
MARC records processed: 159,736
Registration matches found: 8,542
Renewal matches found: 2,218
Total comparisons made: 445,678,432,156

Country Classification:
  US records: 95,841 (60.0%)
  Non-US records: 52,103 (32.6%)
  Unknown country: 11,792 (7.4%)

Copyright Status Results:
  Potentially PD (date verify): 89,234 (55.9%)
  Research for US status: 31,872 (20.0%)
  Potentially In-Copyright: 23,456 (14.7%)
  Research for potential US-only PD status: 15,174 (9.5%)

Performance:
  Workers used: 8
  Total time: 15h 4m
  Speed: 177 records/minute
  Output: matches.csv
================================================================================
```

## Usage

### Basic Usage

```bash
# Analyze MARC records against registration and renewal data
pdm run python compare.py \
    --marcxml data.xml \
    --copyright-dir copyright_xml/ \
    --renewal-dir cce-renewals/data/
```

### Advanced Configuration

```bash
# Custom settings with performance tuning
pdm run python compare.py \
    --marcxml data.xml \
    --copyright-dir copyright_xml/ \
    --renewal-dir cce-renewals/data/ \
    --output custom_analysis.csv \
    --title-threshold 85 \
    --author-threshold 75 \
    --year-tolerance 1 \
    --min-year 1925 \
    --early-exit-title 98 \
    --early-exit-author 95 \
    --max-workers 16
```

### Logging Examples

```bash
# Save logs to file for analysis
pdm run python compare.py \
    --marcxml data.xml \
    --copyright-dir copyright_xml/ \
    --renewal-dir cce-renewals/data/ \
    --log-file copyright_analysis.log

# Enable verbose DEBUG logging
pdm run python compare.py \
    --marcxml data.xml \
    --copyright-dir copyright_xml/ \
    --renewal-dir cce-renewals/data/ \
    --debug

# Both file logging and debug mode
pdm run python compare.py \
    --marcxml data.xml \
    --copyright-dir copyright_xml/ \
    --renewal-dir cce-renewals/data/ \
    --log-file copyright_analysis.log \
    --debug
```

### US-Focused Research

```bash
# Process only US publications (significantly faster)
pdm run python compare.py \
    --marcxml data.xml \
    --copyright-dir copyright_xml/ \
    --renewal-dir cce-renewals/data/ \
    --us-only
```

## Command Line Options

### Required Arguments

- `--marcxml` - Path to MARC XML file or directory
- `--copyright-dir` - Path to copyright registration XML directory
- `--renewal-dir` - Path to renewal TSV directory

### Output Options

- `--output` - CSV output filename (default: auto-generated based on filters)

**Automatic Filename Generation:**
When using the default output, filenames are automatically generated based on applied filters:

- `matches.csv` - No filters applied
- `matches_us-only.csv` - US-only filtering enabled
- `matches_1950-1960.csv` - Year range filtering
- `matches_us-only_1950-1960.csv` - Combined filters
- `matches_1955-only.csv` - Single year (min_year = max_year)
- `matches_after-1945.csv` - Minimum year only
- `matches_before-1970.csv` - Maximum year only

To override automatic naming, specify a custom filename with `--output`.

### Logging Options

- `--log-file` - Write logs to specified file (default: console only)
- `--debug` - Enable DEBUG level logging for verbose details

### Matching Parameters

- `--title-threshold` - Title similarity threshold 0-100 (default: 80)
- `--author-threshold` - Author similarity threshold 0-100 (default: 70)
- `--year-tolerance` - Maximum year difference for matching (default: 2)
- `--min-year` - Minimum publication year to include (default: current year - 95)
- `--max-year` - Maximum publication year to include (default: no limit)
- `--us-only` - Only process US publications (significantly faster for US-focused research)

### Performance Options

- `--max-workers` - Number of CPU cores to use (default: auto-detect)
- `--batch-size` - Records per batch (default: 500)
- `--early-exit-title` - Title score for early termination (default: 95)
- `--early-exit-author` - Author score for early termination (default: 90)

**Note:** Early termination stops searching when both title AND author scores exceed their thresholds, significantly speeding up matching for high-confidence matches.

## Public Domain Filtering

By default, the tool focuses on potentially copyrighted works by filtering out records published before `current year - 95` (e.g., before 1930 in 2025). This significantly improves performance by excluding likely public domain works.

Use `--min-year` to override (e.g., `--min-year 1900`).

## Year Range Filtering

You can focus analysis on specific time periods using:

```bash
# Focus on 1950s decade
pdm run python compare.py --marcxml data.xml --copyright-dir reg/ --renewal-dir ren/ --min-year 1950 --max-year 1959

# Only 1955 publications  
pdm run python compare.py --marcxml data.xml --copyright-dir reg/ --renewal-dir ren/ --min-year 1955 --max-year 1955

# Everything up to 1970
pdm run python compare.py --marcxml data.xml --copyright-dir reg/ --renewal-dir ren/ --max-year 1970
```

## How It Works

The tool compares MARC bibliographic records against U.S. copyright registration and renewal data to determine likely copyright status. It uses:

1. **Country Classification**: Identifies US vs. non-US publications using MARC country codes
1. **Fuzzy Matching**: Compares titles and authors against both registration (1923-1977) and renewal (1950-1991) datasets
1. **Status Determination**: Assigns one of four copyright status categories based on match patterns

For detailed information about the analysis algorithm, matching criteria, and copyright law logic, see [`docs/ALGORITHM.md`](docs/ALGORITHM.md).

## Development

For technical details about code architecture, design patterns, performance optimizations, and system requirements, see [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md).

### Code Formatting

```bash
pdm run format
```

## Output

The tool generates a CSV file with copyright analysis results for each MARC record, including:

- Original bibliographic data (title, author, year, publisher, place)
- Country classification (US/Non-US/Unknown)
- Copyright status determination
- Match details and confidence scores for the best match found

For complete output format details and sample data, see [`docs/ALGORITHM.md`](docs/ALGORITHM.md).

## Documentation

- **[ALGORITHM.md](docs/ALGORITHM.md)** - Domain logic and copyright analysis details
- **[DEVELOPMENT.md](docs/DEVELOPMENT.md)** - Code architecture and technical implementation

## Limitations and Considerations

**This is not legal advice** - the results provide research starting points, not definitive copyright determinations. The analysis has several limitations:

- **Matching accuracy**: Fuzzy matching may miss some matches due to spelling variations, transcription errors, or different citation formats
- **Data completeness**: Not all copyright registrations or renewals may be present in the digitized records
- **Complex copyright law**: Copyright status depends on many factors beyond registration/renewal patterns
- **International considerations**: Copyright law varies by country and has changed over time

**Use this information as a starting point for copyright research, not as a final determination. All works including those marked as "potentially public domain" require verification of actual copyright status through additional research.**

## License

AGPL-3.0-only
