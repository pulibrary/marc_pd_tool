# CLI Reference

Complete reference for the MARC Copyright Status Analysis Tool command-line interface.

## Basic Usage

```bash
pdm run marc-pd-tool --marcxml <path-to-marc-file>
```

The tool requires at least the `--marcxml` argument pointing to a MARC XML file or directory containing MARC XML files.

## Required Arguments

### `--marcxml PATH`

Path to MARC XML file or directory containing MARC XML files to analyze.

## Data Source Options

### `--copyright-dir PATH`

Path to directory containing copyright registration XML files.

- Default: `./nypl-reg/xml` (from git submodule)

### `--renewal-dir PATH`

Path to directory containing renewal TSV files.

- Default: `./nypl-ren/data` (from git submodule)

## Output Options

### `-o, --output-filename FILENAME`

Base name for output files.

- Default: Auto-generated based on timestamp and parameters
- Example: `reports/20250201_143052_matches_t50_a40_y1950-1977_us.csv`

### `--output-formats FORMAT [FORMAT ...]`

Output formats to generate. Multiple formats can be specified.

- Choices: `csv`, `xlsx`, `json`, `html`
- Default: `json csv`
- Example: `--output-formats csv xlsx json`

### `--single-file`

Save all results to a single file instead of separating by copyright status.

- Default: False (creates separate files for each status category)

## Matching Thresholds

### `--title-threshold N`

Minimum title similarity score (0-100) required for a match.

- Default: 40
- Higher values require closer title matches

### `--author-threshold N`

Minimum author similarity score (0-100) required for a match.

- Default: 30
- Only applied when author data exists

### `--publisher-threshold N`

Minimum publisher similarity score (0-100) required for a match.

- Default: 30
- Only applied when publisher data exists

### `--year-tolerance N`

Maximum difference in years allowed between MARC and copyright records.

- Default: 1
- Example: With tolerance of 1, a 1955 MARC record matches 1954-1956 copyright data

### `--early-exit-title N`

Title similarity score that triggers immediate match acceptance.

- Default: 95
- When title score exceeds this, other fields aren't checked

### `--early-exit-author N`

Author similarity score for high-confidence matching.

- Default: 90
- Combined with title score for early match determination

### `--early-exit-publisher N`

Publisher similarity score for early exit optimization.

- Default: 90

## Filtering Options

### `--min-year YEAR`

Minimum publication year to process.

- Default: None (no minimum)
- Filters both MARC records and copyright/renewal data
- Example: `--min-year 1950`

### `--max-year YEAR`

Maximum publication year to process.

- Default: None (no maximum)
- Filters both MARC records and copyright/renewal data
- Example: `--max-year 1977`

### `--us-only`

Process only U.S. publications.

- Default: False (process all countries)
- Improves performance by 50-70% when only U.S. status needed

### `--brute-force-missing-year`

Process MARC records that lack publication year data.

- Default: False (skip records without years)
- Warning: Significantly slower as these must be checked against all data

## Analysis Modes

### `--ground-truth`

Extract and analyze LCCN-verified ground truth matches.

- Finds records with Library of Congress Control Numbers
- Provides high-confidence matches for threshold tuning
- Outputs additional ground truth CSV file

### `--score-everything`

Find best match for all records regardless of thresholds.

- Default: False
- Useful for threshold optimization and analysis
- Reports best match even if below configured thresholds

### `--minimum-combined-score N`

Minimum combined score when using `--score-everything` mode.

- Default: None
- Filters out very poor matches in score-everything mode

## Performance Options

### `--batch-size N`

Number of MARC records to process per batch.

- Default: 100
- Larger batches may improve throughput but use more memory

### `--max-workers N`

Number of parallel worker processes.

- Default: CPU count - 2
- Example: On an 8-core machine, default is 6 workers

### `--streaming`

Use streaming mode for very large datasets.

- Default: False
- Processes records incrementally with constant memory usage
- Recommended for datasets over 1 million records

### `--temp-dir PATH`

Directory for temporary batch files in streaming mode.

- Default: System temp directory
- Only used with `--streaming`

## Caching Options

### `--cache-dir PATH`

Directory for cached index files.

- Default: `.marcpd_cache`
- Caches speed up subsequent runs by 85%

### `--force-refresh`

Force rebuild of all cached indexes.

- Default: False
- Use when data files have changed

### `--disable-cache`

Disable caching entirely.

- Default: False
- Useful for one-time analyses or debugging

## Logging Options

### `--log-file PATH`

Path to log file.

- Default: `logs/marc_pd_[timestamp].log`
- Automatically creates logs directory if needed

### `--log-level LEVEL`

Logging verbosity level.

- Choices: `DEBUG`, `INFO`, `WARNING`, `ERROR`
- Default: `INFO`

### `--disable-file-logging`

Disable writing logs to file.

- Default: False
- Console output still appears

### `--silent`

Suppress all console output.

- Default: False
- Log file still written unless disabled

### `--debug`

Enable debug mode with verbose output.

- Default: False
- Equivalent to `--log-level DEBUG`

## Memory Monitoring

### `--monitor-memory`

Log memory usage statistics during processing.

- Default: False
- Helps identify memory issues

### `--memory-log-interval N`

Seconds between memory usage logs.

- Default: 60
- Only used with `--monitor-memory`

## Output Files

The tool generates output files in the `reports/` directory with automatic timestamping:

### File Naming Convention

```
reports/[timestamp]_[base_name]_[parameters].[format]
```

Example:

```
reports/20250201_143052_matches_t50_a40_y1950-1977_us.csv
```

Components:

- `timestamp`: YYYYMMDD_HHMMSS format
- `base_name`: From `--output-filename` or "matches"
- `parameters`: Encoded threshold and filter settings
- `format`: File extension based on output format

### Multiple File Output (default)

When `--single-file` is not used, creates separate files by status:

- `*_public_domain.csv`: Works determined to be in public domain
- `*_in_copyright.csv`: Works still under copyright
- `*_undetermined.csv`: Works needing further research
- `*_no_match.csv`: Works with no copyright data found

### Excel Output Structure

XLSX files contain multiple worksheets:

- **Summary**: Overview statistics and parameters
- **Public Domain**: Records determined to be public domain
- **In Copyright**: Records still protected
- **Needs Review**: Records requiring manual review
- **No Match**: Records without copyright data
- **All Records**: Complete dataset

## Copyright Status Codes

The tool assigns specific status codes based on its analysis. For a complete reference of all status codes, what they mean, and their copyright implications, see [Copyright Status Codes Reference](COPYRIGHT_STATUS_CODES.md).

### Quick Reference

- **Public Domain**: `US_PRE_[YEAR]`, `US_REGISTERED_NOT_RENEWED`
- **In Copyright**: `US_RENEWED`, `FOREIGN_RENEWED_[COUNTRY]`
- **Undetermined**: `US_NO_MATCH`, `FOREIGN_NO_MATCH_[COUNTRY]`
- **Special Cases**: `OUT_OF_DATA_RANGE_[YEAR]`, `COUNTRY_UNKNOWN_*`

## Examples

### Basic Analysis

```bash
pdm run marc-pd-tool --marcxml catalog.xml
```

### U.S. Books from 1950s

```bash
pdm run marc-pd-tool \
    --marcxml catalog.xml \
    --us-only \
    --min-year 1950 \
    --max-year 1959
```

### High-Precision Matching

```bash
pdm run marc-pd-tool \
    --marcxml catalog.xml \
    --title-threshold 60 \
    --author-threshold 50 \
    --year-tolerance 0
```

### Performance Optimized

```bash
pdm run marc-pd-tool \
    --marcxml large_catalog.xml \
    --batch-size 500 \
    --max-workers 8 \
    --us-only \
    --min-year 1940 \
    --max-year 1970
```

### Ground Truth Analysis

```bash
pdm run marc-pd-tool \
    --marcxml catalog.xml \
    --ground-truth \
    --score-everything \
    --output-formats csv xlsx json
```

### Streaming Large Dataset

```bash
pdm run marc-pd-tool \
    --marcxml huge_catalog.xml \
    --streaming \
    --temp-dir /data/temp \
    --batch-size 1000
```

## Performance Tips

1. **Use year filters**: Restricting date ranges significantly improves performance
1. **Enable US-only mode**: If only analyzing U.S. publications, use `--us-only`
1. **Skip year-less records**: Default behavior; avoid `--brute-force-missing-year` unless necessary
1. **Tune batch size**: Larger batches (200-500) can improve throughput on systems with adequate memory
1. **Adjust worker count**: Set `--max-workers` to number of CPU cores for CPU-bound processing
1. **Use caching**: First run builds cache; subsequent runs are much faster
1. **Enable streaming**: For datasets over 1M records, use `--streaming` mode

## Troubleshooting

### Out of Memory

- Reduce `--batch-size`
- Reduce `--max-workers`
- Enable `--streaming` mode
- Use `--monitor-memory` to identify issues

### Slow Performance

- Enable `--us-only` if appropriate
- Add year filters with `--min-year` and `--max-year`
- Increase `--max-workers` if CPU cores available
- Ensure cache is enabled (avoid `--disable-cache`)

### Poor Match Quality

- Adjust thresholds based on ground truth analysis
- Review records with `--score-everything` to understand matching
- Check for data quality issues in MARC records
- Consider manual review for borderline matches
