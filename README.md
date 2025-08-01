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

1. **Install dependencies:**

   ```bash
   pdm install
   ```

1. **Run analysis:**

   ```bash
   pdm run python -m marc_pd_tool \
       --marcxml path/to/marc_file.xml \
       --copyright-dir path/to/copyright_xml/ \
       --renewal-dir path/to/cce-renewals/data/
   ```

1. **Results:**

   - `matches.csv` - CSV with copyright status classifications
   - Country classification (US/Non-US/Unknown)
   - Registration and renewal match analysis
   - Completion time: Several hours for large datasets

## How It Works

The tool compares MARC bibliographic records against U.S. copyright registration and renewal data to determine likely copyright status. It uses:

1. **Country Classification**: Identifies US vs. non-US publications using MARC country codes
1. **Enhanced Word-Based Matching**: Compares titles using word overlap with stemming, authors/publishers using fuzzy matching, against both registration (1923-1977) and renewal (1950-1991) datasets
1. **Generic Title Detection**: Adjusts scoring for generic titles like "collected works" to improve accuracy (English titles only)
1. **Dynamic Scoring**: Adapts match weighting based on available data and title genericness
1. **Status Determination**: Assigns one of six copyright status categories based on match patterns, including definitive public domain determination for US works published 1930-1963

For detailed information about the analysis algorithm, matching criteria, and copyright law logic, see [`docs/ALGORITHM.md`](docs/ALGORITHM.md). For technical details on the complete processing pipeline, see [`docs/PROCESSING_PIPELINE.md`](docs/PROCESSING_PIPELINE.md).

## Basic Usage Examples

### Analyze All Records

```bash
# Basic analysis with all available CPU cores
pdm run python -m marc_pd_tool \
    --marcxml data.xml \
    --copyright-dir copyright_xml/ \
    --renewal-dir cce-renewals/data/
```

### Focus on US Publications (Faster)

```bash
# Process only US publications (50-70% faster)
pdm run python -m marc_pd_tool \
    --marcxml data.xml \
    --copyright-dir copyright_xml/ \
    --renewal-dir cce-renewals/data/ \
    --us-only
```

### Focus on Specific Time Period

```bash
# Focus on 1950s decade
pdm run python -m marc_pd_tool \
    --marcxml data.xml \
    --copyright-dir copyright_xml/ \
    --renewal-dir cce-renewals/data/ \
    --min-year 1950 \
    --max-year 1959
```

### Process Records Without Year Data

```bash
# Include MARC records that lack year information (slower)
pdm run python -m marc_pd_tool \
    --marcxml data.xml \
    --copyright-dir copyright_xml/ \
    --renewal-dir cce-renewals/data/ \
    --brute-force-missing-year
```

**Note**: By default, MARC records without year data are skipped for performance. Use `--brute-force-missing-year` to process them, but this significantly increases processing time as they must be compared against all copyright/renewal records.

## Key Options

- `--us-only` - Process only US publications (50-70% faster)
- `--min-year`, `--max-year` - Filter by publication year
- `--output-formats` - Choose output formats: `csv`, `xlsx`, `xlsx-stacked`, `json`, `html` (space-separated, default: json csv)
- `--debug` - Enable verbose logging

For complete command line reference, see [`docs/REFERENCE.md`](docs/REFERENCE.md).

## Performance

The tool processes large datasets efficiently using parallel processing and caching. Expected performance: 2,000-5,000 records/minute on modern hardware.

Key optimizations:

- Persistent cache reduces startup time by 85%
- Year filtering dramatically reduces comparison space
- US-only mode processes 50-70% faster
- Automatic parallel processing across CPU cores
- Linux systems benefit from shared memory (fork) optimization
- Dynamic worker recycling prevents memory leaks
- Batch pickling reduces memory footprint for large datasets

## Output

The tool supports multiple output formats that can be generated in a single run. JSON is always generated first as the master format, then other formats are derived from it.

### CSV Output (Default)

The tool generates CSV files with copyright analysis results for each MARC record. By default, separate files are created for each copyright status:

- `matches_pd_no_renewal.csv` - Works in public domain due to non-renewal
- `matches_pd_date_verify.csv` - Potentially public domain (needs date verification)
- `matches_in_copyright.csv` - Works still under copyright
- `matches_research_us_status.csv` - Requires additional research
- `matches_research_us_only_pd.csv` - US public domain status unclear
- `matches_country_unknown.csv` - Country classification unknown

Each CSV includes these columns:

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

### XLSX Output

For more advanced analysis, use Excel format:

```bash
pdm run python -m marc_pd_tool \
    --marcxml data.xml \
    --copyright-dir nypl-reg/xml/ \
    --renewal-dir nypl-ren/data/ \
    --output-formats xlsx
```

The XLSX format provides:

- **Single file output** with multiple tabs organized by copyright status
- **Summary tab** with processing statistics and parameters used
- **Same simplified columns** as CSV format
- **Professional formatting** - colored headers, auto-filters, frozen headers
- **Better for manual review** than multiple CSV files

### JSON Output

For programmatic processing or creating custom reports:

```bash
pdm run python -m marc_pd_tool \
    --marcxml data.xml \
    --copyright-dir nypl-reg/xml/ \
    --renewal-dir nypl-ren/data/ \
    --output-formats json
```

The JSON format provides:

- **Complete data structure** - all fields and scores
- **Normalized text versions** - see exactly what was matched
- **Comprehensive metadata** - processing date, version, statistics
- **Machine-readable** - easily parsed for custom analysis
- **Gzip compression** supported with `.json.gz` extension

### Multiple Formats in One Run

Generate multiple output formats simultaneously:

```bash
pdm run python -m marc_pd_tool \
    --marcxml data.xml \
    --copyright-dir nypl-reg/xml/ \
    --renewal-dir nypl-ren/data/ \
    --output-formats json csv xlsx html
```

This will generate:

- `matches.json` - Master data file with all information
- `matches_*.csv` - CSV files by copyright status
- `matches.xlsx` - Tabbed Excel file
- `matches_html/` - Static HTML pages with visual comparison

### HTML Output

For visual inspection without Excel:

```bash
pdm run python -m marc_pd_tool \
    --marcxml data.xml \
    --copyright-dir nypl-reg/xml/ \
    --renewal-dir nypl-ren/data/ \
    --output-formats html
```

The HTML format provides:

- **Static paginated pages** - 50 records per page
- **Stacked comparison tables** - Original vs normalized text
- **Visual score indicators** - Color-coded match quality
- **No JavaScript required** - Works in any browser
- **Easy navigation** - Index page with status summaries

For understanding results and match types, see [`docs/GUIDE.md`](docs/GUIDE.md).

## Configuration

The tool supports JSON configuration files for setting defaults. Create a `config.json` file to avoid repeating command-line options.

For configuration details, see [`docs/REFERENCE.md`](docs/REFERENCE.md#configuration-file-format).

## Advanced Usage

For advanced usage including:

- Custom threshold tuning
- Performance optimization
- Cache management
- Troubleshooting

See [`docs/GUIDE.md`](docs/GUIDE.md#common-workflows).

## Documentation

- **[Usage Guide](docs/GUIDE.md)** - Understanding the tool and interpreting results
- **[Command Reference](docs/REFERENCE.md)** - Complete CLI options and configuration
- **[API Guide](docs/API.md)** - Using as a Python library
- **[Development Guide](docs/DEVELOPMENT.md)** - Architecture and contributing

## Limitations and Considerations

**This is not legal advice** - the results provide research starting points, not definitive copyright determinations. The analysis has several limitations:

- **Matching accuracy**: Word-based title matching and fuzzy author/publisher matching may miss some matches due to spelling variations, transcription errors, or different citation formats
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
