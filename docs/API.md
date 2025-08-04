# MARC Copyright Analysis Tool - API Documentation

## Overview

The marc_pd_tool package provides a Python API for analyzing MARC bibliographic records against US copyright registration and renewal data. The API is designed to be simple for basic use cases while allowing advanced users to access lower-level components.

## Installation

```bash
# Install with PDM (recommended)
pdm install

# Or with pip (once published to PyPI)
pip install marc-pd-comparison-tool
```

## Quick Start

### Basic Usage

```python
from marc_pd_tool import MarcCopyrightAnalyzer

# Create analyzer
analyzer = MarcCopyrightAnalyzer()

# Analyze a MARC file
analyzer.analyze_marc_file(
    'data.marcxml',
    copyright_dir='nypl-reg/xml/',
    renewal_dir='nypl-ren/data/',
    output_path='results.csv'
)
```

### Library Usage with Results

```python
from marc_pd_tool import MarcCopyrightAnalyzer, CopyrightStatus

# Create analyzer
analyzer = MarcCopyrightAnalyzer()

# Analyze without automatic export
results = analyzer.analyze_marc_file('data.marcxml')

# Access results programmatically
for pub in results.publications:
    if pub.copyright_status == CopyrightStatus.PD_NO_RENEWAL:
        print(f"Public domain: {pub.title} ({pub.year})")

# Get statistics
stats = results.statistics
print(f"Total records: {stats['total_records']}")
print(f"Public domain (no renewal): {stats['pd_no_renewal']}")

# Export in different formats
analyzer.export_results('results.csv', format='csv')
analyzer.export_results('results.xlsx', format='xlsx')
analyzer.export_results('results.json', format='json')
```

## Main API Class

### MarcCopyrightAnalyzer

The primary interface for copyright analysis.

```python
class MarcCopyrightAnalyzer:
    def __init__(
        self,
        config_path: Optional[str] = None,
        cache_dir: Optional[str] = None,
        force_refresh: bool = False,
        log_file: Optional[str] = None,
    )
```

**Parameters:**

- `config_path`: Path to custom configuration JSON file
- `cache_dir`: Directory for caching indexes (default: `.marcpd_cache`)
- `force_refresh`: Force rebuild of all cached data
- `log_file`: Path to log file (optional)

### Key Methods

#### analyze_marc_file()

```python
def analyze_marc_file(
    self,
    marc_path: str,
    copyright_dir: Optional[str] = None,
    renewal_dir: Optional[str] = None,
    output_path: Optional[str] = None,
    **options: Any
) -> AnalysisResults
```

Analyze a MARC XML file for copyright status.

**Parameters:**

- `marc_path`: Path to MARC XML file
- `copyright_dir`: Directory with copyright XML files (default: `nypl-reg/xml/`)
- `renewal_dir`: Directory with renewal TSV files (default: `nypl-ren/data/`)
- `output_path`: Path for output file (optional)
- `**options`: Analysis options (see below)

**Analysis Options:**

- `us_only`: Only analyze US publications (bool)
- `min_year`: Minimum publication year (int)
- `max_year`: Maximum publication year (int)
- `year_tolerance`: Year matching tolerance (int, default: 1)
- `title_threshold`: Title similarity threshold (int, default: 40)
- `author_threshold`: Author similarity threshold (int, default: 30)
- `early_exit_title`: Early exit title threshold (int, default: 95)
- `early_exit_author`: Early exit author threshold (int, default: 90)
- `score_everything`: Find best match regardless of thresholds (bool)
- `minimum_combined_score`: Minimum score for score_everything mode (int)
- `brute_force_missing_year`: Process records without years (bool)
- `format`: Output format ('csv', 'xlsx', 'json')
- `single_file`: Export all results to single file (bool)

#### analyze_marc_records()

```python
def analyze_marc_records(
    self,
    publications: List[Publication],
    **options: Any
) -> List[Publication]
```

Analyze a list of already-loaded Publication objects.

#### export_results()

```python
def export_results(
    self,
    output_path: str,
    format: str = "csv",
    single_file: bool = False
) -> None
```

Export results in the specified format.

**Formats:**

- `csv`: CSV file(s) organized by copyright status
- `xlsx`: Excel workbook with multiple sheets
- `json`: JSON format

#### extract_ground_truth()

```python
def extract_ground_truth(
    self,
    marc_path: str,
    copyright_dir: Optional[str] = None,
    renewal_dir: Optional[str] = None,
    min_year: Optional[int] = None,
    max_year: Optional[int] = None,
    lccn_prefix: Optional[str] = None,
) -> Tuple[List[GroundTruthPair], GroundTruthStats]
```

Extract LCCN-verified ground truth pairs for algorithm validation.

**Parameters:**

- `marc_path`: Path to MARC XML file
- `copyright_dir`: Directory containing copyright XML files
- `renewal_dir`: Directory containing renewal TSV files
- `min_year`: Minimum publication year filter
- `max_year`: Maximum publication year filter

**Returns:** Tuple of (ground_truth_pairs, statistics)

#### analyze_ground_truth_scores()

```python
def analyze_ground_truth_scores(
    self,
    ground_truth_pairs: Optional[List[GroundTruthPair]] = None
) -> GroundTruthAnalysis
```

Analyze similarity scores for ground truth pairs without LCCN matching.

#### export_ground_truth_analysis()

```python
def export_ground_truth_analysis(
    self,
    output_path: str,
    output_format: str = "csv",
) -> None
```

Export ground truth analysis results including score distributions.

## Data Models

### Publication

Represents a bibliographic record (MARC, copyright, or renewal).

```python
from marc_pd_tool import Publication

pub = Publication(
    title="The Great Novel",
    author="Smith, John",
    year=1950,
    publisher="Big Publishing Co.",
    place="New York"
)
```

### MatchResult

Contains information about a match between records.

```python
from marc_pd_tool import MatchResult

# Access match results
if pub.has_registration_match():
    match = pub.get_registration_match()
    print(f"Matched with {match.similarity_score}% confidence")
```

### CopyrightStatus

Enum representing copyright status determinations.

```python
from marc_pd_tool import CopyrightStatus

# Available statuses
CopyrightStatus.PD_NO_RENEWAL      # Public domain - no renewal
CopyrightStatus.PD_DATE_VERIFY     # Possibly public domain - verify dates
CopyrightStatus.IN_COPYRIGHT       # Likely in copyright
CopyrightStatus.RESEARCH_US_STATUS # Foreign work - research needed
CopyrightStatus.RESEARCH_US_ONLY_PD # Foreign work - may be PD in US only
CopyrightStatus.COUNTRY_UNKNOWN    # Cannot determine - country unknown
```

### AnalysisResults

Container for analysis results with comprehensive statistics.

```python
# Access results after analysis
results = analyzer.analyze()

# Get statistics dictionary
stats = results.statistics

# Available statistics:
print(f"Total records processed: {stats['total_records']}")
print(f"Records skipped (no year): {stats['skipped_no_year']}")  # When not using --brute-force-missing-year
print(f"US records: {stats['us_records']}")
print(f"Non-US records: {stats['non_us_records']}")
print(f"Unknown country: {stats['unknown_country']}")
print(f"Registration matches: {stats['registration_matches']}")
print(f"Renewal matches: {stats['renewal_matches']}")
print(f"No matches found: {stats['no_matches']}")

# Copyright status breakdown
print(f"Public domain (pre-1928): {stats.get('pd_pre_1928', 0)}")
print(f"Public domain (no renewal): {stats['pd_no_renewal']}")
print(f"In copyright: {stats['in_copyright']}")
# ... other status counts
```

**Note**: The `skipped_no_year` statistic tracks MARC records that were skipped because they lack publication year data when not using the `--brute-force-missing-year` option. This helps identify potentially incomplete analysis coverage.

## Advanced Usage

### Custom Configuration

```python
from marc_pd_tool import MarcCopyrightAnalyzer

# Use custom configuration
analyzer = MarcCopyrightAnalyzer(config_path='my_config.json')
```

### Direct Component Access

For advanced use cases, you can access individual components:

```python
from marc_pd_tool import (
    MarcLoader,
    CopyrightDataLoader,
    RenewalDataLoader,
    DataMatcher,
    ConfigLoader
)

# Load data manually
marc_loader = MarcLoader()
publications = marc_loader.load_marc_xml('data.xml')

# Create custom matching engine
config = ConfigLoader('config.json')
engine = DataMatcher(config=config)

# Process individual records
for pub in publications:
    match = engine.find_best_match(pub, copyright_pubs, 
                                  title_threshold=40,
                                  author_threshold=30,
                                  year_tolerance=1)
```

### Progress Monitoring

The API logs progress information. Configure logging to monitor:

```python
import logging

# Set up logging before creating analyzer
logging.basicConfig(level=logging.INFO)

analyzer = MarcCopyrightAnalyzer()
# Progress will be logged during analysis
```

## Examples

### Filter by Year Range

```python
analyzer = MarcCopyrightAnalyzer()

results = analyzer.analyze_marc_file(
    'data.marcxml',
    min_year=1950,
    max_year=1960,
    us_only=True
)

print(f"Analyzed {results.statistics['total_records']} US records from 1950-1960")
```

### Threshold Optimization Mode

```python
# Find best match for every record regardless of thresholds
results = analyzer.analyze_marc_file(
    'data.marcxml',
    score_everything=True,
    minimum_combined_score=40  # Still require 40% minimum
)

# Analyze score distribution
scores = []
for pub in results.publications:
    if pub.has_registration_match():
        match = pub.get_registration_match()
        scores.append(match.similarity_score)

print(f"Average match score: {sum(scores)/len(scores):.1f}%")
```

### Batch Processing Multiple Files

```python
import glob

analyzer = MarcCopyrightAnalyzer()

# Process multiple MARC files
for marc_file in glob.glob('marc_files/*.xml'):
    output_file = marc_file.replace('.xml', '_results.csv')
    
    results = analyzer.analyze_marc_file(
        marc_file,
        output_path=output_file
    )
    
    print(f"{marc_file}: {results.statistics['total_records']} records")
```

### Threshold Analysis Modes

The API provides two approaches for analyzing and tuning similarity thresholds:

#### Score Everything Mode

Find the best match for every record regardless of thresholds:

```python
results = analyzer.analyze_marc_file(
    'data.marcxml',
    score_everything=True,
    minimum_combined_score=20  # Still require some minimum
)

# Analyze score distribution
for pub in results.publications:
    if pub.has_registration_match():
        match = pub.get_registration_match()
        print(f"{pub.title}: {match.similarity_score}%")
```

#### Ground Truth Analysis

Extract LCCN-verified matches and analyze their similarity scores:

```python
# Extract ground truth pairs based on LCCN matching
ground_truth_pairs, stats = analyzer.extract_ground_truth(
    'data.marcxml',
    min_year=1950,
    max_year=1960
)

print(f"Found {len(ground_truth_pairs)} verified matches")
print(f"MARC records with LCCN: {stats.marc_lccn_coverage:.1f}%")

# Analyze similarity scores (without LCCN matching)
analysis = analyzer.analyze_ground_truth_scores(ground_truth_pairs)

# Export analysis results with score distributions
analyzer.export_ground_truth_analysis(
    'ground_truth_analysis.csv',
    output_format='csv'
)
```

## Performance Considerations

- **Caching**: The analyzer caches parsed data and indexes. First run will be slower.
- **Memory**: Large datasets require significant memory. Use year filtering to reduce memory usage.
- **Parallel Processing**: The analyzer uses multiple CPU cores automatically.
- **Year Filtering**: Always specify `min_year`/`max_year` when possible for better performance.

## Error Handling

The API raises standard Python exceptions:

```python
try:
    results = analyzer.analyze_marc_file('data.marcxml')
except FileNotFoundError:
    print("MARC file not found")
except ValueError as e:
    print(f"Invalid configuration: {e}")
```

## See Also

- [CLI Documentation](../README.md) - Using the command-line interface
- [Processing Pipeline](PIPELINE.md) - Detailed algorithm documentation
- [Development Guide](DEVELOPMENT.md) - Contributing to the project
