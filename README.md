# MARC Copyright Status Analysis Tool

A tool for determining the copyright status of library catalog records by comparing them against historical U.S. copyright registration and renewal data.

## Overview

This tool analyzes MARC bibliographic records to determine their likely copyright status. It compares library catalog records against digitized U.S. copyright registration data (1923-1977) and renewal data (1950-1991) to identify works that may be in the public domain.

The analysis uses sophisticated text matching algorithms to handle variations in how titles, authors, and publishers are recorded across different sources. It applies U.S. copyright law rules based on publication date, country of origin, and renewal status to classify each work.

## Installation

### Prerequisites

- Python 3.13.5 or later
- PDM (Python Dependency Manager)
- Git with submodule support

### Setup

1. Clone the repository with copyright/renewal data submodules:

```bash
git clone --recurse-submodules https://github.com/NYPL/marc_pd_tool.git
cd marc_pd_tool
```

2. Install dependencies:

```bash
pdm install
```

## Basic Usage

Analyze a MARC XML file:

```bash
pdm run marc-pd-tool --marcxml data.xml
```

The tool will use the included copyright and renewal data from the submodules and output results to the `reports/` directory.

## Data Sources

- **MARC Records**: Library catalog records in MARCXML format containing bibliographic information
- **Copyright Registration Data**: U.S. copyright registrations from 1923-1977, digitized by the [NYPL Catalog of Copyright Entries Project](https://github.com/NYPL/catalog_of_copyright_entries_project)
- **Renewal Data**: U.S. copyright renewals from 1950-1991, from the [NYPL CCE Renewals Project](https://github.com/NYPL/cce-renewals)

## Documentation

- [Matching Algorithm](docs/MATCHING_ALGORITHM.md) - How the tool matches records and determines copyright status
- [Copyright Status Codes](docs/COPYRIGHT_STATUS_CODES.md) - Complete reference for all status codes in reports
- [Technical Architecture](docs/TECHNICAL_ARCHITECTURE.md) - Software architecture and implementation details
- [CLI Reference](docs/CLI_REFERENCE.md) - Complete command-line options and usage examples
- [Python API](docs/API.md) - Using the tool as a Python library

## Performance

The tool processes records in parallel across available CPU cores. Typical performance:

- Small datasets (< 1,000 records): 1-2 minutes
- Medium datasets (10,000 records): 15-30 minutes
- Large datasets (100,000+ records): 2-4 hours

Performance can be improved by:

- Limiting analysis to U.S. publications only (`--us-only`)
- Restricting to specific date ranges (`--min-year`, `--max-year`)
- Skipping records without publication years (default behavior)

## Output

Results are saved to the `reports/` directory with automatic timestamping. Available formats:

- **CSV**: Spreadsheet-compatible format with all fields
- **XLSX**: Excel workbook with separate tabs by copyright status
- **JSON**: Structured data for programmatic processing

## License

AGPL-3.0 - See LICENSE file for details.
