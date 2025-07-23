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
