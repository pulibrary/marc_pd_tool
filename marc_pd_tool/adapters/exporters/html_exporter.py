# marc_pd_tool/adapters/exporters/html_exporter.py

"""Static HTML export functionality with paginated stacked format"""

# Standard library imports
from pathlib import Path

# Local imports
from marc_pd_tool.adapters.exporters.base_exporter import BaseJSONExporter
from marc_pd_tool.core.types.json import JSONDict
from marc_pd_tool.core.types.json import JSONList
from marc_pd_tool.core.types.json import JSONType


class HTMLExporter(BaseJSONExporter):
    """Generate static HTML pages from JSON data

    Creates a directory structure with paginated HTML files showing
    records in a stacked comparison format for detailed analysis.
    """

    __slots__ = ("items_per_page", "country_codes")

    def __init__(self, json_path: str, output_dir: str, single_file: bool = False):
        """Initialize the HTML exporter

        Args:
            json_path: Path to the JSON file
            output_dir: Directory for HTML output
            single_file: If True, all records in one status group
        """
        super().__init__(json_path, output_dir, single_file)
        self.items_per_page = 50  # Hard-coded pagination

        # Country code mappings (MARC country codes to display names)
        self.country_codes = {
            "abc": "Alberta",
            "ae": "Algeria",
            "ag": "Argentina",
            "ai": "Anguilla",
            "at": "Australia",
            "au": "Austria",
            "be": "Belgium",
            "bl": "Brazil",
            "bu": "Bulgaria",
            "bw": "Belarus",
            "cc": "China",
            "ch": "China (Republic)",
            "ck": "Colombia",
            "cl": "Chile",
            "cs": "Czechoslovakia",
            "cu": "Cuba",
            "cy": "Cyprus",
            "dk": "Denmark",
            "enk": "United Kingdom",
            "es": "El Salvador",
            "fr": "France",
            "ge": "Germany (East)",
            "gh": "Ghana",
            "gr": "Greece",
            "gs": "Georgia (Republic)",
            "gt": "Guatemala",
            "gw": "Germany",
            "hk": "Hong Kong",
            "ht": "Haiti",
            "hu": "Hungary",
            "ie": "Ireland",
            "ii": "India",
            "iq": "Iraq",
            "ir": "Iran",
            "is": "Israel",
            "it": "Italy",
            "iv": "Ivory Coast",
            "ja": "Japan",
            "jo": "Jordan",
            "ko": "Korea (South)",
            "le": "Lebanon",
            "li": "Lithuania",
            "lu": "Luxembourg",
            "lv": "Latvia",
            "mk": "Macedonia",
            "mm": "Malta",
            "mr": "Morocco",
            "mx": "Mexico",
            "ne": "Netherlands",
            "no": "Norway",
            "nr": "Nigeria",
            "onc": "Ontario",
            "pe": "Peru",
            "pl": "Poland",
            "po": "Portugal",
            "pr": "Puerto Rico",
            "quc": "Quebec",
            "rm": "Romania",
            "ru": "Russia",
            "rur": "Russia (Federation)",
            "sa": "South Africa",
            "si": "Singapore",
            "sp": "Spain",
            "stk": "Scotland",
            "sw": "Sweden",
            "sy": "Syria",
            "sz": "Switzerland",
            "ta": "Tajikistan",
            "th": "Thailand",
            "ti": "Tunisia",
            "tu": "Turkey",
            "ua": "Egypt",
            "uik": "United Kingdom (Misc.)",
            "un": "Soviet Union",
            "unr": "Soviet Union (Regions)",
            "us": "United States",
            "uz": "Uzbekistan",
            "vc": "Vatican City",
            "ve": "Venezuela",
            "vm": "Vietnam",
            "vn": "Vietnam (North)",
            "vp": "Various places",
            "wb": "West Berlin",
            "wiu": "Wisconsin",
            "wlk": "Wales",
            "xr": "Czech Republic",
            "xx": "Unknown",
            "xxc": "Canada",
            "xxk": "United Kingdom",
            "yu": "Yugoslavia",
        }

    def export(self) -> None:
        """Generate static HTML pages from JSON data"""
        # Create output directory
        output_path = Path(self.output_path)
        output_path.mkdir(parents=True, exist_ok=True)

        # Create CSS directory and file
        css_dir = output_path / "css"
        css_dir.mkdir(exist_ok=True)
        self._write_css(css_dir / "style.css")

        # Group records by status
        if self.single_file:
            # All records together
            all_records = self.records
            sorted_records = self.sort_by_quality(all_records)
            self._generate_status_pages("all", sorted_records, output_path)

            # Generate simple index for single file mode
            self._generate_simple_index(len(sorted_records), output_path)
        else:
            # Group by status
            by_status = self.group_by_status()

            # Sort records within each status group
            for status in by_status:
                by_status[status] = self.sort_by_quality(by_status[status])

            # Group statuses by country for better organization
            grouped_data = self._group_by_country(by_status)

            # Generate index page with grouped summary
            self._generate_grouped_index(grouped_data, output_path)

            # Generate paginated pages for each status
            for status, records in by_status.items():
                if records:
                    status_dir = output_path / self._status_to_dirname(status)
                    status_dir.mkdir(exist_ok=True)
                    self._generate_status_pages(status, records, status_dir)

    def _group_by_country(self, by_status: dict[str, JSONList]) -> dict[str, dict[str, JSONList]]:
        """Group statuses by country/origin

        Returns a hierarchical structure:
        {
            "US": {"NO_MATCH": [...], "PRE_1929": [...], ...},
            "France": {"NO_MATCH": [...], "RENEWED": [...], ...},
            ...
        }
        """
        grouped: dict[str, dict[str, JSONList]] = {}

        for status, records in by_status.items():
            if not records:
                continue

            if status.startswith("US_"):
                # US publications
                country = "United States"
                status_type = status[3:]  # Remove "US_" prefix
            elif status.startswith("FOREIGN_"):
                # Foreign publications - extract country code
                # Format is FOREIGN_STATUS_TYPE_COUNTRY_CODE
                # e.g., FOREIGN_RENEWED_sp or FOREIGN_NO_MATCH_fr
                parts = status.split("_", 2)  # Split into at most 3 parts
                if len(parts) >= 3:
                    # parts[0] = "FOREIGN", parts[1] = status type, parts[2] = country code and any remaining
                    status_part = parts[1]
                    remaining = parts[2]

                    # Check if this is a multi-word status like "NO_MATCH" or "REGISTERED_NOT_RENEWED"
                    if status_part == "NO" and remaining.startswith("MATCH_"):
                        status_type = "NO_MATCH"
                        country_code = remaining[6:]  # Skip "MATCH_"
                    elif status_part == "PRE" and remaining.startswith("1929_"):
                        status_type = "PRE_1929"
                        country_code = remaining[5:]  # Skip "1929_"
                    elif status_part == "REGISTERED" and remaining.startswith("NOT_RENEWED_"):
                        status_type = "REGISTERED_NOT_RENEWED"
                        country_code = remaining[13:]  # Skip "NOT_RENEWED_"
                    else:
                        # Simple status like RENEWED, RENEWED_sp
                        status_type = status_part
                        country_code = remaining

                    country = self.country_codes.get(country_code, f"Country Code: {country_code}")
                else:
                    continue
            elif status.startswith("COUNTRY_UNKNOWN"):
                # Country unknown
                country = "Country Unknown"
                status_type = status[16:] if len(status) > 16 else "UNKNOWN"
            elif status.startswith("OUT_OF_DATA_RANGE"):
                # Out of range
                country = "Out of Data Range"
                status_type = status[18:] if len(status) > 18 else "UNKNOWN"
            else:
                # Other/unknown
                country = "Other"
                status_type = status

            # Initialize country dict if needed
            if country not in grouped:
                grouped[country] = {}

            # Add records to the appropriate status within the country
            if status_type not in grouped[country]:
                grouped[country][status_type] = []
            grouped[country][status_type].extend(records)

        return grouped

    def _generate_grouped_index(
        self, grouped_data: dict[str, dict[str, JSONList]], output_path: Path
    ) -> None:
        """Generate the main index page with grouped country sections"""
        metadata = self.metadata
        total_records = 0
        for country_statuses in grouped_data.values():
            for records in country_statuses.values():
                total_records += len(records)

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MARC PD Analysis Results</title>
    <link rel="stylesheet" href="css/style.css">
</head>
<body>
    <h1>MARC Copyright Status Analysis Results</h1>
    
    <div class="processing-info">
        <h3>Processing Information</h3>
        <div class="metadata">
            <div class="metadata-item">
                <span class="metadata-label">Processing Date:</span> {metadata.get('processing_date', 'Unknown')}
            </div>
            <div class="metadata-item">
                <span class="metadata-label">Total Records:</span> {total_records:,}
            </div>
            <div class="metadata-item">
                <span class="metadata-label">Tool Version:</span> {metadata.get('tool_version', 'Unknown')}
            </div>
        </div>
    </div>
    
    <h2>Results by Country of Publication</h2>
"""

        # Sort countries with US first, then Country Unknown, then alphabetically
        sorted_countries = []
        if "United States" in grouped_data:
            sorted_countries.append("United States")
        if "Country Unknown" in grouped_data:
            sorted_countries.append("Country Unknown")
        if "Out of Data Range" in grouped_data:
            sorted_countries.append("Out of Data Range")

        # Add other countries alphabetically
        for country in sorted(grouped_data.keys()):
            if country not in ["United States", "Country Unknown", "Out of Data Range"]:
                sorted_countries.append(country)

        # Generate country sections
        for country in sorted_countries:
            statuses = grouped_data[country]
            country_total = sum(len(records) for records in statuses.values())

            html += f"""
    <div class="country-section">
        <h3>{country} ({country_total:,} records)</h3>
        <div class="status-grid">
"""

            # Sort status types for consistent display
            status_order = ["NO_MATCH", "PRE_1929", "REGISTERED_NOT_RENEWED", "RENEWED"]
            # Add any other statuses not in the standard order
            for status_type in sorted(statuses.keys()):
                if status_type not in status_order:
                    status_order.append(status_type)

            for status_type in status_order:
                if status_type in statuses:
                    records = statuses[status_type]
                    # Reconstruct the full status name for directory creation
                    if country == "United States":
                        full_status = f"US_{status_type}"
                    elif country == "Country Unknown":
                        full_status = f"COUNTRY_UNKNOWN_{status_type}"
                    elif country == "Out of Data Range":
                        full_status = f"OUT_OF_DATA_RANGE_{status_type}"
                    else:
                        # Find the country code for foreign countries
                        country_code = None
                        for code, name in self.country_codes.items():
                            if name == country:
                                country_code = code
                                break
                        if country_code:
                            full_status = f"FOREIGN_{status_type}_{country_code}"
                        else:
                            # Fallback for unknown codes
                            full_status = f"FOREIGN_{status_type}_unknown"

                    status_dir = self._status_to_dirname(full_status)
                    display_name = self._format_status_type(status_type)

                    html += f"""
            <div class="status-card">
                <h4>{display_name}</h4>
                <div class="count">{len(records):,}</div>
                <a href="{status_dir}/page_1.html">View Records →</a>
            </div>
"""

            html += """
        </div>
    </div>
"""

        html += """
    <footer>
        <p>Generated by MARC Copyright Status Analysis Tool</p>
    </footer>
</body>
</html>
"""

        (output_path / "index.html").write_text(html)

    def _format_status_type(self, status_type: str) -> str:
        """Format status type for display"""
        status_formats = {
            "NO_MATCH": "No Match",
            "PRE_1929": "Pre-1929",
            "REGISTERED_NOT_RENEWED": "Registered, Not Renewed",
            "RENEWED": "Renewed",
            "NO MATCH": "No Match",
            "PRE 1929": "Pre-1929",
            "_NO_MATCH": "No Match",
            "_PRE_1929": "Pre-1929",
            "_REGISTERED_NOT_RENEWED": "Registered, Not Renewed",
            "_RENEWED": "Renewed",
        }
        return status_formats.get(status_type, status_type.replace("_", " ").title())

    def _status_to_dirname(self, status: str) -> str:
        """Convert status to directory name"""
        return status.lower().replace("_", "-")

    def _status_to_display_name(self, status: str) -> str:
        """Convert status to human-readable display name"""
        status_names = {
            "PD_PRE_MIN_YEAR": "PD Pre Min Year",
            "PD_US_NOT_RENEWED": "PD US Not Renewed",
            "PD_US_REG_NO_RENEWAL": "PD US Reg No Renewal",
            "PD_US_NO_REG_DATA": "PD US No Reg Data",
            "UNKNOWN_US_NO_DATA": "Unknown US No Data",
            "IN_COPYRIGHT": "In Copyright",
            "IN_COPYRIGHT_US_RENEWED": "In Copyright US Renewed",
            "RESEARCH_US_STATUS": "Research US Status",
            "RESEARCH_US_ONLY_PD": "Research US Only PD",
            "COUNTRY_UNKNOWN": "Country Unknown",
        }
        return status_names.get(status, status.replace("_", " ").title())

    def _write_css(self, css_path: Path) -> None:
        """Write the CSS file"""
        css_content = """/* MARC PD Analysis Styles */

body {
    font-family: Arial, sans-serif;
    max-width: 1400px;
    margin: 0 auto;
    padding: 20px;
    background-color: #f5f5f5;
}

h1, h2 {
    color: #333;
}

h1 {
    border-bottom: 3px solid #366092;
    padding-bottom: 10px;
}

/* Navigation */
nav {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 15px 0;
    border-bottom: 1px solid #ddd;
    margin-bottom: 20px;
    background-color: white;
    padding-left: 15px;
    padding-right: 15px;
    border-radius: 5px;
}

nav a {
    color: #366092;
    text-decoration: none;
    padding: 5px 10px;
    border: 1px solid #366092;
    border-radius: 3px;
    transition: all 0.3s;
}

nav a:hover {
    background-color: #366092;
    color: white;
}

/* Index page styles */
/* Country sections */
.country-section {
    margin: 30px 0;
    padding: 20px;
    background: #f9f9f9;
    border-radius: 8px;
    border: 1px solid #e0e0e0;
}

.country-section h3 {
    color: #2c5282;
    margin-top: 0;
    margin-bottom: 20px;
    font-size: 1.4em;
    border-bottom: 2px solid #366092;
    padding-bottom: 10px;
}

/* Status grid within country */
.status-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 15px;
    margin: 15px 0;
}

.summary-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 20px;
    margin: 30px 0;
}

.status-card {
    background: white;
    border: 1px solid #ddd;
    border-radius: 8px;
    padding: 20px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    transition: transform 0.2s;
}

.status-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 8px rgba(0,0,0,0.15);
}

.status-card h2,
.status-card h4 {
    margin-top: 0;
    color: #366092;
}

.status-card h4 {
    font-size: 1.1em;
}

.status-card .count {
    font-size: 2em;
    font-weight: bold;
    color: #666;
    margin: 10px 0;
}

.status-card a {
    display: inline-block;
    margin-top: 10px;
    color: #366092;
    text-decoration: none;
}

/* Record styles */
.record {
    background: white;
    border: 1px solid #ddd;
    margin: 20px 0;
    padding: 20px;
    border-radius: 5px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}

.record h2 {
    margin-top: 0;
    color: #366092;
    font-size: 1.2em;
}

.status-rule {
    font-style: italic;
    color: #666;
    margin: 10px 0;
}

.metadata {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 10px;
    margin: 15px 0;
    padding: 10px;
    background-color: #f9f9f9;
    border-radius: 3px;
}

.metadata-item {
    font-size: 0.9em;
}

.metadata-label {
    font-weight: bold;
    color: #666;
}

/* General table styles */
table {
    width: 100%;
    border-collapse: collapse;
    margin: 15px 0;
    font-family: Arial, sans-serif;
    border: 1px solid #ddd;
}

table th,
table td {
    border: 1px solid #ddd !important;
    padding: 8px;
    text-align: left;
}

table th {
    background: #366092;
    color: white;
    font-weight: bold;
}

table tr:nth-child(even) {
    background-color: #f9f9f9;
}

/* Stacked comparison table */
.stacked-comparison {
    width: 100%;
    border-collapse: collapse;
    margin-top: 15px;
    font-size: 0.9em;
    border: 1px solid #ddd;
}

.stacked-comparison th,
.stacked-comparison td {
    border: 1px solid #ddd !important;
    padding: 8px;
    text-align: left;
}

.stacked-comparison th {
    background: #366092;
    color: white;
    font-weight: bold;
    position: sticky;
    top: 0;
}

.stacked-comparison tr:nth-child(even) {
    background-color: #f9f9f9;
}

/* Row type styling */
.marc-original {
    background-color: #ffffff;
}

.marc-normalized {
    background-color: #f8f8f8;
}

.marc-normalized td {
    font-family: monospace;
    font-size: 0.95em;
}

.registration {
    background-color: #e8f4f8;
}

.renewal {
    background-color: #f8e8f4;
}

.no-match {
    background-color: #f4f4f4;
    color: #999;
}

/* Score styling */
.score {
    font-weight: bold;
}

.score-high {
    color: #008000;
}

.score-medium {
    color: #ff8c00;
}

.score-low {
    color: #dc143c;
}

.lccn-match {
    color: #008000;
    font-weight: bold;
}

/* Normalized text */
.normalized {
    font-family: monospace;
    background-color: #f0f0f0;
    padding: 2px 4px;
    border-radius: 2px;
}

/* Processing info */
.processing-info {
    background-color: #e8f4f8;
    border: 1px solid #b8d4e8;
    padding: 15px;
    margin: 20px 0;
    border-radius: 5px;
}

.processing-info h3 {
    margin-top: 0;
    color: #366092;
}

/* Warnings */
.warning {
    background-color: #fff3cd;
    border: 1px solid #ffecb5;
    color: #856404;
    padding: 10px;
    margin: 10px 0;
    border-radius: 3px;
}

/* Footer */
footer {
    margin-top: 50px;
    padding-top: 20px;
    border-top: 1px solid #ddd;
    text-align: center;
    color: #666;
    font-size: 0.9em;
}
"""
        css_path.write_text(css_content)

    def _generate_index(self, by_status: dict[str, JSONList], output_path: Path) -> None:
        """Generate the main index page"""
        metadata = self.metadata
        total_records = sum(len(records) for records in by_status.values())

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MARC PD Analysis Results</title>
    <link rel="stylesheet" href="css/style.css">
</head>
<body>
    <h1>MARC Copyright Status Analysis Results</h1>
    
    <div class="processing-info">
        <h3>Processing Information</h3>
        <div class="metadata">
            <div class="metadata-item">
                <span class="metadata-label">Processing Date:</span> {metadata.get('processing_date', 'Unknown')}
            </div>
            <div class="metadata-item">
                <span class="metadata-label">Total Records:</span> {total_records:,}
            </div>
            <div class="metadata-item">
                <span class="metadata-label">Tool Version:</span> {metadata.get('tool_version', 'Unknown')}
            </div>
        </div>
    </div>
    
    <h2>Results by Copyright Status</h2>
    
    <div class="summary-grid">
"""

        # Add status cards - use all statuses found in the data
        # Sort statuses for consistent display, prioritizing US statuses
        all_statuses = sorted(by_status.keys())

        # Group and order statuses for better organization
        us_statuses = [s for s in all_statuses if s.startswith("US_")]
        foreign_statuses = [s for s in all_statuses if s.startswith("FOREIGN_")]
        country_unknown = [s for s in all_statuses if s.startswith("COUNTRY_UNKNOWN")]
        other_statuses = [
            s
            for s in all_statuses
            if not any(s.startswith(p) for p in ["US_", "FOREIGN_", "COUNTRY_UNKNOWN"])
        ]

        # Combine in priority order
        status_order = us_statuses + country_unknown + foreign_statuses + other_statuses

        for status in status_order:
            if status in by_status:
                records = by_status[status]
                if records:
                    status_dir = self._status_to_dirname(status)
                    display_name = self._status_to_display_name(status)

                    html += f"""
        <div class="status-card">
            <h2>{display_name}</h2>
            <div class="count">{len(records):,}</div>
            <div>records</div>
            <a href="{status_dir}/page_1.html">View Records →</a>
        </div>
"""

        html += """
    </div>
    
    <footer>
        <p>Generated by MARC Copyright Status Analysis Tool</p>
    </footer>
</body>
</html>
"""

        (output_path / "index.html").write_text(html)

    def _generate_simple_index(self, total_records: int, output_path: Path) -> None:
        """Generate simple index for single file mode"""
        metadata = self.metadata

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MARC PD Analysis Results</title>
    <link rel="stylesheet" href="css/style.css">
</head>
<body>
    <h1>MARC Copyright Status Analysis Results</h1>
    
    <div class="processing-info">
        <h3>Processing Information</h3>
        <div class="metadata">
            <div class="metadata-item">
                <span class="metadata-label">Processing Date:</span> {metadata.get('processing_date', 'Unknown')}
            </div>
            <div class="metadata-item">
                <span class="metadata-label">Total Records:</span> {total_records:,}
            </div>
        </div>
    </div>
    
    <div class="status-card" style="max-width: 300px; margin: 30px auto;">
        <h2>All Records</h2>
        <div class="count">{total_records:,}</div>
        <div>records</div>
        <a href="all/page_1.html">View Records →</a>
    </div>
    
    <footer>
        <p>Generated by MARC Copyright Status Analysis Tool</p>
    </footer>
</body>
</html>
"""

        (output_path / "index.html").write_text(html)

    def _generate_status_pages(self, status: str, records: JSONList, output_dir: Path) -> None:
        """Generate paginated HTML pages for a status group"""
        total_pages = (len(records) + self.items_per_page - 1) // self.items_per_page

        for page_num in range(1, total_pages + 1):
            start_idx = (page_num - 1) * self.items_per_page
            end_idx = min(start_idx + self.items_per_page, len(records))
            page_records = records[start_idx:end_idx]

            self._generate_page(
                status, page_num, total_pages, page_records, start_idx + 1, output_dir
            )

    def _generate_page(
        self,
        status: str,
        page_num: int,
        total_pages: int,
        records: JSONList,
        start_record: int,
        output_dir: Path,
    ) -> None:
        """Generate a single HTML page"""
        display_name = self._status_to_display_name(status)

        # Calculate relative path to root
        if self.single_file and status == "all":
            css_path = "../css/style.css"
            index_path = "../index.html"
        else:
            css_path = "../../css/style.css"
            index_path = "../../index.html"

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{display_name} - Page {page_num} of {total_pages}</title>
    <link rel="stylesheet" href="{css_path}">
</head>
<body>
    <h1>{display_name} - Page {page_num} of {total_pages}</h1>
    
    <nav>
        <a href="{index_path}">← Back to Index</a>
        <span>Page {page_num} of {total_pages}</span>
"""

        if page_num < total_pages:
            html += f'        <a href="page_{page_num + 1}.html">Next →</a>\n'
        else:
            html += '        <span style="visibility: hidden;">Next →</span>\n'

        html += """    </nav>
    
    <div class="records">
"""

        # Add each record
        for i, record in enumerate(records):
            if isinstance(record, dict):
                record_num = start_record + i
                html += self._format_record(record_num, record)

        html += """    </div>
    
    <nav>
"""

        if page_num > 1:
            html += f'        <a href="page_{page_num - 1}.html">← Previous</a>\n'
        else:
            html += '        <a href="{index_path}">← Back to Index</a>\n'

        html += f"        <span>Page {page_num} of {total_pages}</span>\n"

        if page_num < total_pages:
            html += f'        <a href="page_{page_num + 1}.html">Next →</a>\n'
        else:
            html += '        <span style="visibility: hidden;">Next →</span>\n'

        html += """    </nav>
    
    <footer>
        <p>Generated by MARC Copyright Status Analysis Tool</p>
    </footer>
</body>
</html>
"""

        (output_dir / f"page_{page_num}.html").write_text(html)

    def _format_record(self, record_num: int, record: dict[str, JSONType]) -> str:
        """Format a single record as HTML"""
        marc = record.get("marc", {})
        matches = record.get("matches", {})
        analysis = record.get("analysis", {})

        marc_id = "Unknown"
        metadata: dict[str, JSONType] = {}
        if isinstance(marc, dict):
            id_val = marc.get("id", "Unknown")
            if isinstance(id_val, str):
                marc_id = id_val
            meta_data = marc.get("metadata", {})
            if isinstance(meta_data, dict):
                metadata = meta_data

        status = "UNKNOWN"
        status_rule = ""
        data_completeness = []
        if isinstance(analysis, dict):
            status_val = analysis.get("status", "UNKNOWN")
            if isinstance(status_val, str):
                status = status_val
            rule_val = analysis.get("status_rule", "")
            if isinstance(rule_val, str):
                status_rule = rule_val
            data_comp = analysis.get("data_completeness", [])
            if isinstance(data_comp, list):
                data_completeness = [x for x in data_comp if isinstance(x, str)]

        # Start record HTML
        html = f"""
        <div class="record">
            <h2>Record {record_num}: ID {marc_id} - Status: {status}</h2>
"""

        if status_rule:
            html += f'            <p class="status-rule">Rule: {status_rule}</p>\n'

        # Add metadata
        if metadata:
            html += '            <div class="metadata">\n'

            if metadata.get("country_code"):
                html += f"""                <div class="metadata-item">
                    <span class="metadata-label">Country:</span> {metadata.get("country_code")}
                </div>\n"""

            if metadata.get("language_code"):
                html += f"""                <div class="metadata-item">
                    <span class="metadata-label">Language:</span> {metadata.get("language_code")}
                </div>\n"""

            html += "            </div>\n"

        # Add warnings for data issues
        if data_completeness:
            html += f'            <div class="warning">Data issues: {", ".join(data_completeness)}</div>\n'

        # Add stacked comparison table
        if isinstance(marc, dict) and isinstance(matches, dict):
            html += self._format_stacked_table(marc, matches)

        html += "        </div>\n"

        return html

    def _format_stacked_table(self, marc: JSONType, matches: JSONType) -> str:
        """Format the stacked comparison table"""
        html = """
            <table class="stacked-comparison">
                <thead>
                    <tr>
                        <th>Source</th>
                        <th>ID</th>
                        <th>Version</th>
                        <th>Title</th>
                        <th>Score</th>
                        <th>Author</th>
                        <th>Score</th>
                        <th>Publisher</th>
                        <th>Score</th>
                        <th>Year</th>
                    </tr>
                </thead>
                <tbody>
"""

        # MARC original row
        original = {}
        normalized = {}
        marc_id = ""

        if isinstance(marc, dict):
            id_val = marc.get("id", "")
            if isinstance(id_val, str):
                marc_id = id_val
            orig_data = marc.get("original", {})
            if isinstance(orig_data, dict):
                original = orig_data
            norm_data = marc.get("normalized", {})
            if isinstance(norm_data, dict):
                normalized = norm_data

        html += f"""                    <tr class="marc-original">
                        <td>MARC</td>
                        <td>{marc_id}</td>
                        <td>Original</td>
                        <td>{self._escape_html(str(original.get("title", "")))}</td>
                        <td>-</td>
                        <td>{self._escape_html(str(original.get("author_245c", "") or original.get("author_1xx", "")))}</td>
                        <td>-</td>
                        <td>{self._escape_html(str(original.get("publisher", "")))}</td>
                        <td>-</td>
                        <td>{original.get("year", "")}</td>
                    </tr>
"""

        # MARC normalized row
        html += f"""                    <tr class="marc-normalized">
                        <td>MARC</td>
                        <td>{marc_id}</td>
                        <td>Normalized</td>
                        <td class="normalized">{self._escape_html(str(normalized.get("title", "")))}</td>
                        <td>-</td>
                        <td class="normalized">{self._escape_html(str(normalized.get("author", "")))}</td>
                        <td>-</td>
                        <td class="normalized">{self._escape_html(str(normalized.get("publisher", "")))}</td>
                        <td>-</td>
                        <td>-</td>
                    </tr>
"""

        # Registration match
        if isinstance(matches, dict):
            reg = matches.get("registration", {})
            if isinstance(reg, dict) and reg.get("found"):
                match_type_val = reg.get("match_type", "similarity")
                match_type = match_type_val if isinstance(match_type_val, str) else "similarity"
                html += self._format_match_row("Registration", reg, match_type)
            else:
                html += """                    <tr class="no-match">
                        <td>Registration</td>
                        <td>-</td>
                        <td>No match</td>
                        <td>-</td>
                        <td>-</td>
                        <td>-</td>
                        <td>-</td>
                        <td>-</td>
                        <td>-</td>
                        <td>-</td>
                    </tr>
"""
            # Renewal match
            ren = matches.get("renewal", {})
            if isinstance(ren, dict) and ren.get("found"):
                match_type_val = ren.get("match_type", "similarity")
                match_type = match_type_val if isinstance(match_type_val, str) else "similarity"
                html += self._format_match_row("Renewal", ren, match_type)
            else:
                html += """                    <tr class="no-match">
                        <td>Renewal</td>
                        <td>-</td>
                        <td>No match</td>
                        <td>-</td>
                        <td>-</td>
                        <td>-</td>
                        <td>-</td>
                        <td>-</td>
                        <td>-</td>
                        <td>-</td>
                    </tr>
"""

        html += """                </tbody>
            </table>
"""

        return html

    def _format_match_row(self, source: str, match_data: JSONDict, match_type: str) -> str:
        """Format a match row for registration or renewal"""
        original = {}
        scores = {}

        if isinstance(match_data, dict):
            orig_data = match_data.get("original", {})
            if isinstance(orig_data, dict):
                original = orig_data
            score_data = match_data.get("scores", {})
            if isinstance(score_data, dict):
                scores = score_data

        # Format scores
        def format_score(score: JSONType) -> str:
            if match_type == "lccn":
                return '<span class="lccn-match">LCCN</span>'
            if score is None:
                return "-"
            if isinstance(score, (int, float)):
                score_val = float(score)
                if score_val >= 90:
                    css_class = "score-high"
                elif score_val >= 70:
                    css_class = "score-medium"
                else:
                    css_class = "score-low"
                return f'<span class="score {css_class}">{score_val:.0f}%</span>'
            return str(score)

        row_class = "registration" if source == "Registration" else "renewal"

        return f"""                    <tr class="{row_class}">
                        <td>{source}</td>
                        <td>{match_data.get("id", "") if isinstance(match_data, dict) else ""}</td>
                        <td>Original</td>
                        <td>{self._escape_html(str(original.get("title", "")))}</td>
                        <td>{format_score(scores.get("title"))}</td>
                        <td>{self._escape_html(str(original.get("author", "")))}</td>
                        <td>{format_score(scores.get("author"))}</td>
                        <td>{self._escape_html(str(original.get("publisher", "")))}</td>
                        <td>{format_score(scores.get("publisher"))}</td>
                        <td>{original.get("date", "")}</td>
                    </tr>
"""

    def _escape_html(self, text: str | None) -> str:
        """Escape HTML special characters"""
        if not text:
            return ""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
        )
