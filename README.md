# MARC Copyright Status Analysis Tool

A tool for analyzing MARC bibliographic records to determine copyright status by comparing against both registration and renewal data using country classification and parallel processing.

## Overview

This tool implements a comprehensive algorithm to classify publications by copyright status. It compares MARC records against two distinct datasets and uses country of origin to determine appropriate copyright analysis pathways.

**Data Sources:**

- **MARC records**: Library catalog data in MARCXML format with country classification
- **Registration data**: Historical copyright registry entries (1923-1977) from the [NYPL Catalog of Copyright Entries Project](https://github.com/NYPL/catalog_of_copyright_entries_project)
- **Renewal data**: Copyright renewal records (1950-1991) from the [NYPL CCE Renewals Project](https://github.com/NYPL/cce-renewals)

## Quick Start

1. **Clone the repository with submodules:**

   ```bash
   git clone --recurse-submodules https://github.com/NYPL/marc_pd_tool.git
   cd marc_pd_tool
   ```

   **Important:** This repository includes the copyright registration and renewal data as git submodules. The `--recurse-submodules` flag is required to download the data files needed for analysis.

   If you already cloned without submodules, initialize them:

   ```bash
   git submodule update --init --recursive
   ```

2. **Install dependencies:**

   ```bash
   pdm install
   ```

3. **Run analysis:**

   ```bash
   pdm run python compare.py \
       --marcxml path/to/marc_file.xml \
       --copyright-dir path/to/copyright_xml/ \
       --renewal-dir path/to/cce-renewals/data/
   ```

3. **Results:**

   - `matches.csv` - CSV with copyright status classifications
   - Country classification (US/Non-US/Unknown)
   - Registration and renewal match analysis
   - Completion time: Several hours for large datasets

## How It Works

The tool compares MARC bibliographic records against U.S. copyright registration and renewal data to determine likely copyright status. It uses:

1. **Country Classification**: Identifies US vs. non-US publications using MARC country codes
2. **Fuzzy Matching**: Compares titles and authors against both registration (1923-1977) and renewal (1950-1991) datasets
3. **Status Determination**: Assigns one of five copyright status categories based on match patterns

For detailed information about the analysis algorithm, matching criteria, and copyright law logic, see [`docs/ALGORITHM.md`](docs/ALGORITHM.md).

## Basic Usage Examples

### Analyze All Records

```bash
# Basic analysis with all available CPU cores
pdm run python compare.py \
    --marcxml data.xml \
    --copyright-dir copyright_xml/ \
    --renewal-dir cce-renewals/data/
```

### Focus on US Publications (Faster)

```bash
# Process only US publications (50-70% faster)
pdm run python compare.py \
    --marcxml data.xml \
    --copyright-dir copyright_xml/ \
    --renewal-dir cce-renewals/data/ \
    --us-only
```

### Focus on Specific Time Period

```bash
# Focus on 1950s decade
pdm run python compare.py \
    --marcxml data.xml \
    --copyright-dir copyright_xml/ \
    --renewal-dir cce-renewals/data/ \
    --min-year 1950 \
    --max-year 1959
```

## Key Command Line Options

### Required Arguments

- `--marcxml` - Path to MARC XML file or directory
- `--copyright-dir` - Path to copyright registration XML directory
- `--renewal-dir` - Path to renewal TSV directory

### Common Options

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
- `--us-only` - Only process US publications (significantly faster for US-focused research)
- `--min-year` - Minimum publication year to include (default: current year - 95)
- `--max-year` - Maximum publication year to include (default: no limit)
- `--log-file` - Write logs to specified file (default: console only)
- `--debug` - Enable DEBUG level logging for verbose details

For complete command line options and advanced configuration, see the detailed usage examples below.

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

## Output

The tool generates a CSV file with copyright analysis results for each MARC record, including:

- Original bibliographic data (title, author, year, publisher, place)
- Country classification (US/Non-US/Unknown)
- Copyright status determination
- Match details and confidence scores for the best match found

For complete output format details and sample data, see [`docs/ALGORITHM.md`](docs/ALGORITHM.md).

## Advanced Usage

### Custom Thresholds

```bash
# Adjust matching sensitivity
pdm run python compare.py \
    --marcxml data.xml \
    --copyright-dir copyright_xml/ \
    --renewal-dir cce-renewals/data/ \
    --title-threshold 85 \
    --author-threshold 75 \
    --year-tolerance 1
```

### Performance Tuning

```bash
# Custom worker count and batch size
pdm run python compare.py \
    --marcxml data.xml \
    --copyright-dir copyright_xml/ \
    --renewal-dir cce-renewals/data/ \
    --max-workers 16 \
    --batch-size 1000
```

### Logging

```bash
# Save logs to file for analysis
pdm run python compare.py \
    --marcxml data.xml \
    --copyright-dir copyright_xml/ \
    --renewal-dir cce-renewals/data/ \
    --log-file copyright_analysis.log \
    --debug
```

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

## Development

For technical details about code architecture, design patterns, performance optimizations, and system requirements, see [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md).

### Code Formatting

```bash
pdm run format
```

### Testing

```bash
pdm run test
```

## License

AGPL-3.0-only