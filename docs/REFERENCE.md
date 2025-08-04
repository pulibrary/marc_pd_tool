# Command Line Reference

## Synopsis

```bash
pdm run python -m marc_pd_tool [OPTIONS]
```

## Required Arguments

- `--marcxml PATH` - Path to MARC XML file or directory
- `--copyright-dir PATH` - Path to copyright registration XML directory
- `--renewal-dir PATH` - Path to renewal TSV directory

## Options

### Output Options

- `--output-filename PATH` - Output base filename without extension (default: reports/[auto-generated based on filters])
- `--output-formats FORMAT [FORMAT ...]` - Output formats to generate (choices: csv, xlsx, xlsx-stacked, json, html; default: json csv)
- `--single-file` - Export all results to single file instead of separating by status

**Automatic Filename Generation:**
When using the default output, filenames are automatically generated based on applied filters and saved to the `reports/` directory:

- `reports/matches.csv` - No filters applied
- `reports/matches_us-only.csv` - US-only filtering enabled
- `reports/matches_1950-1960.csv` - Year range filtering
- `reports/matches_us-only_1950-1960.csv` - Combined filters
- `reports/matches_1955-only.csv` - Single year (min_year = max_year)
- `reports/matches_after-1945.csv` - Minimum year only
- `reports/matches_before-1970.csv` - Maximum year only

### Filtering Options

- `--us-only` - Only process US publications (significantly faster for US-focused research)
- `--min-year YEAR` - Minimum publication year to include (default: current year - 95)
- `--max-year YEAR` - Maximum publication year to include (default: no limit)
- `--brute-force-missing-year` - Process MARC records without year data (default: skip for performance)

**Note on year filtering**: When using `--min-year`/`--max-year`, the tool optimizes by loading only the relevant subset of copyright/renewal data (with ±1 year tolerance). This conflicts with `--brute-force-missing-year` which requires all data - if both are specified, a warning is logged and all data is loaded.

### Matching Thresholds

- `--title-threshold PERCENT` - Minimum title similarity score (default: 40)
- `--author-threshold PERCENT` - Minimum author similarity score (default: 30)
- `--publisher-threshold PERCENT` - Minimum publisher similarity score (default: 30)
- `--year-tolerance YEARS` - Maximum year difference for matching (default: 1)
- `--early-exit-title PERCENT` - Title score for early termination (default: 95)
- `--early-exit-author PERCENT` - Author score for early termination (default: 90)
- `--minimum-combined-score PERCENT` - Minimum combined score in score-everything mode (default: 40)

### Performance Options

- `--max-workers NUMBER` - Number of parallel processes (default: CPU count - 2)
- `--batch-size NUMBER` - Records per batch (default: 200)

### Threshold Analysis Modes

These special modes help analyze and tune similarity thresholds:

- `--score-everything-mode` - Find best match for every record regardless of thresholds
- `--ground-truth-mode` - Extract LCCN-verified matches and analyze their similarity scores

Both modes are useful for understanding how the matching algorithm performs and determining appropriate thresholds for your data.

### Cache Management

- `--cache-dir PATH` - Directory for cached data (default: `.marcpd_cache`)
- `--force-refresh` - Force rebuild of all cached data
- `--disable-cache` - Disable caching entirely for this run

### Logging Options

- `--log-file PATH` - Write logs to specified file (default: auto-generated in logs/ directory)
- `--no-log-file` - Disable file logging (console output only)
- `--debug` - Enable DEBUG level logging for verbose output

### Configuration

- `--config PATH` - Path to configuration JSON file (default: config.json in current directory)

### Boolean Flag Behavior

Boolean options support both positive and negative forms:

- Use `--flag` to enable a feature
- Use `--no-flag` to disable a feature

This is especially useful when your config file sets a default:

```bash
# Config has "us_only": true, but you want to process all countries
pdm run python -m marc_pd_tool --marcxml data.xml --no-us-only

# Config has "debug": false, but you want debug logging
pdm run python -m marc_pd_tool --marcxml data.xml --debug

# Config has "force_refresh": true, but you want to use cache
pdm run python -m marc_pd_tool --marcxml data.xml --no-force-refresh
```

## Configuration File Format

The tool supports a JSON configuration file (`config.json`) that allows you to set default values for all command-line options.

```json
{
  "processing": {
    "batch_size": 500,
    "max_workers": 8,
    "score_everything": false,
    "brute_force_missing_year": false
  },
  "filtering": {
    "us_only": true,
    "min_year": 1950,
    "max_year": 1970
  },
  "output": {
    "single_file": false
  },
  "caching": {
    "cache_dir": ".marcpd_cache",
    "force_refresh": false,
    "no_cache": false
  },
  "logging": {
    "debug": false,
    "log_file": null
  },
  "default_thresholds": {
    "title": 40,
    "author": 30,
    "publisher": 30,
    "early_exit_title": 95,
    "early_exit_author": 90,
    "year_tolerance": 1,
    "minimum_combined_score": 40
  }
}
```

### Configuration Priority

Settings are applied in this order (highest priority first):

1. Command-line arguments
1. Configuration file (`config.json`)
1. Built-in defaults

### Specifying a Custom Config File

```bash
pdm run python -m marc_pd_tool \
    --marcxml data.xml \
    --config /path/to/custom-config.json
```

## Output Format

### CSV Output (Default)

The tool generates CSV files with copyright analysis results. By default, separate files are created for each copyright status in the `reports/` directory:

- `reports/matches_pd_no_renewal.csv` - Works in public domain due to non-renewal
- `reports/matches_pd_date_verify.csv` - Potentially public domain (needs date verification)
- `reports/matches_in_copyright.csv` - Works still under copyright
- `reports/matches_research_us_status.csv` - Requires additional research
- `reports/matches_research_us_only_pd.csv` - US public domain status unclear
- `reports/matches_country_unknown.csv` - Country classification unknown

Each CSV includes:

- Original bibliographic data (title, author, year, publisher, place, edition, language)
- LCCN (both original and normalized forms)
- Country classification (US/Non-US/Unknown)
- Copyright status determination
- Generic title detection information and scoring adjustments
- Match details and confidence scores for the best match found
- Source data from matched registration and renewal records
- Match type indicator ("lccn" for LCCN matches, "similarity" for text-based matches)

### XLSX Output (Optional)

For a more organized output, use Excel format:

```bash
# First install the optional dependency
pdm add -dG xlsx openpyxl

# Then use --output-format xlsx
pdm run python -m marc_pd_tool \
    --marcxml data.xml \
    --copyright-dir nypl-reg/xml/ \
    --renewal-dir nypl-ren/data/ \
    --output-formats xlsx
```

The XLSX format provides:

- **Single file output** with multiple tabs organized by copyright status
- **Summary tab** with processing statistics and parameters used
- **Proper data types** - numbers, percentages, and booleans (not just text)
- **Professional formatting** - colored headers, appropriate column widths
- **Better readability** - no need to open multiple CSV files

### Complete CSV Column Headers

- MARC ID, MARC Title, MARC Author, MARC Year, MARC Publisher, MARC Place, MARC Edition, Language Code
- Country Code, Country Classification, Copyright Status
- Generic Title Detected, Generic Detection Reason, Registration Generic Title, Renewal Generic Title
- Registration Source ID, Renewal Entry ID
- Registration Title, Registration Author, Registration Publisher, Registration Date
- Registration Similarity Score, Registration Title Score, Registration Author Score, Registration Publisher Score
- Renewal Title, Renewal Author, Renewal Publisher, Renewal Date
- Renewal Similarity Score, Renewal Title Score, Renewal Author Score, Renewal Publisher Score

### Processing Summary Output

At the end of processing, the tool displays a comprehensive summary:

```
================================================================================
PROCESSING COMPLETE
================================================================================
Total records processed: 12,345
Records skipped (no year): 234     # Only shown when records were skipped
Registration matches: 8,901
Renewal matches: 5,678
Processing time: 123.45 seconds
Processing rate: 6,000 records/minute
Output written to: reports/matches_2024-01-15_123456.csv
================================================================================
Copyright Status Breakdown:
  PD_PRE_1928: 1,234 (10.0%)
  PD_US_1930_1963_NOT_RENEWED: 3,456 (28.0%)
  PD_US_NO_REG_DATA: 2,345 (19.0%)
  IN_COPYRIGHT: 4,567 (37.0%)
  RESEARCH_US_STATUS: 789 (6.4%)
  Other: 10 (0.1%)
================================================================================
```

**Note**: The "Records skipped (no year)" line only appears when records lacking publication year data were excluded from processing (the default behavior when not using `--brute-force-missing-year`).
