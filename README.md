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

2. **Run analysis:**
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

## Performance

**Expected Performance:**
Processing large datasets (190K+ MARC records vs 2.1M+ registration entries + 445K+ renewal entries) typically takes several hours, depending on system specifications and dataset size.

The tool automatically uses all available CPU cores and includes several optimization features:
- **Public domain filtering**: Excludes records older than current year - 95 by default
- **Year-based filtering**: Only compares publications within ±2 years of each other
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
# Custom settings
pdm run python compare.py \
    --marcxml data.xml \
    --copyright-dir copyright_xml/ \
    --renewal-dir cce-renewals/data/ \
    --output custom_analysis.csv \
    --title-threshold 85 \
    --author-threshold 75 \
    --year-tolerance 1 \
    --min-year 1925
```

## Command Line Options

### Required Arguments
- `--marcxml` - Path to MARC XML file or directory
- `--copyright-dir` - Path to copyright registration XML directory
- `--renewal-dir` - Path to renewal TSV directory

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

## Copyright Analysis Algorithm

The tool implements a comprehensive copyright status determination algorithm:

### Step 1: Country Classification
Records are classified by country of origin using official MARC country codes from field 008:
- **US Records**: Publications originating in the United States  
- **Non-US Records**: Publications from other countries
- **Unknown**: Records without determinable country information

### Step 2: Dual Dataset Matching
Each MARC record is compared against both datasets using fuzzy matching:
- **Registration Matching**: Against copyright registration data (1923-1977)
- **Renewal Matching**: Against renewal data (1950-1991)

**Matching Criteria:**
- **Title matching** (70% weight, 80% threshold default): Normalized publication titles
- **Author matching** (30% weight, 70% threshold default): Author names when available  
- **Year filtering**: Publications within ±2 years only

### Step 3: Copyright Status Determination
Based on match patterns and country classification:

**For US Records:**
- Registration hit + No renewal = **"Potentially PD (date verify)"**
- No registration + Renewal hit = **"Potentially In-Copyright"**  
- No hits in either = **"Potentially PD (date verify)"**
- Hits in both = **"Potentially In-Copyright"**

**For Non-US Records:**
- Hit in either dataset = **"Research for US status"**
- No hits in either = **"Research for potential US-only PD status"**

**MARC Fields Used:**
- **Field 008**: Country codes (positions 15-17) and publication dates
- **Fields 264/260**: Publication data (RDA and AACR2 formats)
- **Fields 100/110/111**: Personal, corporate, and meeting name authors

## Development

### Code Formatting
```bash
pdm run format
```

### Project Structure
```
marc_pd_tool/
├── __init__.py              # Package interface
├── enums.py                 # Copyright status and country enums
├── publication.py           # Publication data model with country classification
├── marc_extractor.py        # MARC XML data extraction with country detection
├── copyright_loader.py      # Copyright registration data loading
├── renewal_loader.py        # Renewal data loading (TSV format)
└── batch_processor.py       # Parallel dual-dataset matching
compare.py                   # Command-line application
```

## Requirements

- **Python 3.12+**
- **PDM package manager**
- **Multi-core CPU** recommended for best performance
- **4GB+ RAM** for large datasets

## Output Format

The CSV output includes comprehensive analysis results:

**MARC Record Data:**
- MARC_ID, MARC_Title, MARC_Author, MARC_Year, MARC_Publisher, MARC_Place

**Country Classification:**
- Country_Code (from MARC 008 field), Country_Classification (US/Non-US/Unknown)

**Copyright Analysis Results:**
- Copyright_Status (algorithmic determination)
- Registration_Matches_Count, Renewal_Matches_Count
- Registration_Match_Details, Renewal_Match_Details (with similarity scores)

**Sample Output:**
```csv
MARC_ID,MARC_Title,MARC_Author,Country_Code,Country_Classification,Copyright_Status,Registration_Matches_Count,Renewal_Matches_Count
99123456,The Great Novel,Smith John,xxu,US,Potentially PD (date verify),1,0
99789012,Another Book,Jones Mary,uk,Non-US,Research for US status,0,1
```


## License

AGPL-3.0-only