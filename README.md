# MARC/Public Domain Publication Comparison Tool

A tool for comparing MARC bibliographic records against copyright registry data to identify potentially copyrighted works using fuzzy string matching and parallel processing.

## Overview

This tool aims to identify which publications from MARC XML files appear in historical copyright data by comparing titles, authors, and publication years. It automatically filters out likely public domain works and uses parallel processing to efficiently handle large datasets.

**Data Sources:**
- **MARC records**: Library catalog data in MARCXML format
- **Copyright data**: Historical copyright registry entries (1923-1977) from the [NYPL Catalog of Copyright Entries Project](https://github.com/NYPL/catalog_of_copyright_entries_project)

## Quick Start

1. **Install dependencies:**
   ```bash
   pdm install
   ```

2. **Run comparison:**
   ```bash
   pdm run python compare.py --marcxml path/to/marc_file.xml --copyright-dir path/to/copyright_xml/
   ```

3. **Results:**
   - `matches.csv` - Publication matches with similarity scores
   - Completion time: Several hours for large datasets

## Performance

**Expected Performance:**
Processing large datasets (190K+ MARC records vs 2.1M+ copyright entries) typically takes several hours, depending on system specifications and dataset size.

The tool automatically uses all available CPU cores and includes several optimization features:
- **Public domain filtering**: Excludes records older than current year - 95 by default
- **Year-based filtering**: Only compares publications within ±2 years of each other
- **Parallel processing**: Efficient multi-core utilization
- **Smart memory management**: Streaming XML parsing

Here is the result of a analyzing ~160K MARC XML records the defaults on a laptop with eight cores:

```bash
============================================================
COMPARISON COMPLETE
============================================================
MARC records processed: 159,736
Matches found: 10,760
Match rate: 6.74%
Total comparisons: 297,986,042,312
Workers used: 8
Total time: 904.0 minutes
Speed: 177 records/minute
Output: matches.csv
============================================================
```

## Usage

### Basic Usage
```bash
# Compare MARC records with copyright data
pdm run python compare.py --marcxml data.xml --copyright-dir copyright_xml/
```

### Advanced Configuration
```bash
# Custom settings
pdm run python compare.py \
    --marcxml data.xml \
    --copyright-dir copyright_xml/ \
    --output custom_matches.csv \
    --title-threshold 85 \
    --author-threshold 75 \
    --year-tolerance 1 \
    --min-year 1925
```

## Command Line Options

### Required Arguments
- `--marcxml` - Path to MARC XML file or directory
- `--copyright-dir` - Path to copyright XML directory

### Output Options
- `--output` - CSV output filename (default: `matches.csv`)

### Matching Parameters
- `--title-threshold` - Title similarity threshold 0-100 (default: 80)
- `--author-threshold` - Author similarity threshold 0-100 (default: 70)
- `--year-tolerance` - Maximum year difference for matching (default: 2)
- `--min-year` - Minimum publication year to include (default: current year - 95)

### Performance Options
- `--max-workers` - Number of CPU cores to use (default: auto-detect)
- `--batch-size` - Records per batch (default: 500)

## Public Domain Filtering

By default, the tool focuses on potentially copyrighted works by filtering out records published before `current year - 95` (e.g., before 1930 in 2025). This significantly improves performance by excluding likely public domain works.

Use `--min-year` to override (e.g., `--min-year 1900`).

## Matching Algorithm

The tool performs sophisticated fuzzy matching with:

- **Title matching** (70% weight, 80% threshold default): Compares normalized publication titles
- **Author matching** (30% weight, 70% threshold default): Compares author names when available  
- **Year filtering**: Only compares publications within ±2 years
- **Optimizations**: Parallel processing for speed

**MARC Fields Used:**
- **Fields 264/260**: Publication data (RDA and AACR2 formats)
- **Fields 100/110/111**: Personal, corporate, and meeting name authors
- **Field 008**: Fallback publication dates

## Development

### Code Formatting
```bash
pdm run format
```

### Project Structure
```
marc_pd_tool/
├── __init__.py              # Package interface
├── publication.py           # Publication data model
├── marc_extractor.py        # MARC XML data extraction
├── copyright_loader.py      # Copyright data loading
└── batch_processor.py       # Parallel processing and matching
compare.py                   # Command-line application
```

## Requirements

- **Python 3.12+**
- **PDM package manager**
- **Multi-core CPU** recommended for best performance
- **4GB+ RAM** for large datasets

## Output Format

The CSV output includes:

**MARC Record Data:**
- MARC_ID, MARC_Title, MARC_Author, MARC_Year, MARC_Publisher

**Copyright Record Data:**  
- Copyright_ID, Copyright_Title, Copyright_Author, Copyright_Year, Copyright_Publisher

**Similarity Scores:**
- Title_Score, Author_Score, Combined_Score


## License

AGPL-3.0-only