# marc_pd_tool/adapters/exporters/csv_exporter.py

"""CSV export functionality that reads from JSON data"""

# Standard library imports
from csv import writer
from pathlib import Path

# Local imports
from marc_pd_tool.adapters.exporters.base_exporter import BaseJSONExporter
from marc_pd_tool.core.types.json import JSONType
from marc_pd_tool.core.types.protocols import CSVWriter


class CSVExporter(BaseJSONExporter):
    """Export CSV files from JSON data

    Reads from the master JSON format and generates CSV files
    with simplified columns for easy analysis.
    """

    __slots__ = ("country_codes",)

    def __init__(self, json_path: str, output_path: str, single_file: bool = False):
        """Initialize the exporter with JSON data and country code mappings"""
        super().__init__(json_path, output_path, single_file)

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
        """Export records to CSV file(s) in organized folder structure"""
        if self.single_file:
            # Export all records to a single file
            self._export_single_file()
        else:
            # Export to organized folder structure with summary
            self._export_organized_structure()

    def _export_single_file(self) -> None:
        """Export all records to a single CSV file"""
        records = self.records
        sorted_records = self.sort_by_quality(records)

        with open(self.output_path, "w", newline="", encoding="utf-8") as f:
            csv_writer = writer(f)
            self._write_header(csv_writer)

            for record in sorted_records:
                # JSON structure already validated
                if isinstance(record, dict):
                    self._write_record(csv_writer, record)

    def _export_organized_structure(self) -> None:
        """Export records to organized folder structure with summary"""
        # Create output folder
        path = Path(self.output_path)
        base_name = path.stem
        output_dir = path.parent / f"{base_name}_csv"
        output_dir.mkdir(exist_ok=True)

        # Group records by status
        by_status = self.group_by_status()

        # Group statuses by country for better organization
        grouped_by_country = self._group_by_country(by_status)

        # Create summary CSV first
        self._create_summary_csv(output_dir / "_summary.csv", by_status)

        # Export CSV files by country/status combinations
        # Start with US
        if "United States" in grouped_by_country:
            us_statuses = grouped_by_country["United States"]
            for status_type, records in us_statuses.items():
                sorted_records = self.sort_by_quality(records)
                filename = f"us_{status_type.lower()}"
                output_file = output_dir / f"{filename}.csv"

                with open(output_file, "w", newline="", encoding="utf-8") as f:
                    csv_writer = writer(f)
                    self._write_header_with_country(csv_writer)

                    for record in sorted_records:
                        if isinstance(record, dict):
                            self._write_record_with_country_name(
                                csv_writer, record, "United States"
                            )

        # Export Country Unknown
        if "Country Unknown" in grouped_by_country:
            unknown_statuses = grouped_by_country["Country Unknown"]
            for status_type, records in unknown_statuses.items():
                sorted_records = self.sort_by_quality(records)
                filename = f"country_unknown_{status_type.lower()}"
                output_file = output_dir / f"{filename}.csv"

                with open(output_file, "w", newline="", encoding="utf-8") as f:
                    csv_writer = writer(f)
                    self._write_header_with_country(csv_writer)

                    for record in sorted_records:
                        if isinstance(record, dict):
                            self._write_record_with_country_name(
                                csv_writer, record, "Country Unknown"
                            )

        # Export Out of Data Range
        if "Out of Data Range" in grouped_by_country:
            out_of_range = grouped_by_country["Out of Data Range"]
            for status_type, records in out_of_range.items():
                sorted_records = self.sort_by_quality(records)
                filename = f"out_of_data_range_{status_type.lower()}"
                output_file = output_dir / f"{filename}.csv"

                with open(output_file, "w", newline="", encoding="utf-8") as f:
                    csv_writer = writer(f)
                    self._write_header_with_country(csv_writer)

                    for record in sorted_records:
                        if isinstance(record, dict):
                            self._write_record_with_country_name(
                                csv_writer, record, "Out of Data Range"
                            )

        # Export foreign countries - combine all countries by status type
        foreign_by_status: dict[str, list[tuple[str, JSONType]]] = {}

        for country_name in sorted(grouped_by_country.keys()):
            if country_name in ["United States", "Country Unknown", "Out of Data Range"]:
                continue

            country_statuses = grouped_by_country[country_name]
            for status_type, records in country_statuses.items():
                if status_type not in foreign_by_status:
                    foreign_by_status[status_type] = []
                # Store records with their country name
                for record in records:
                    foreign_by_status[status_type].append((country_name, record))

        # Now export combined foreign files by status type
        for status_type, country_records in foreign_by_status.items():
            # Sort by quality across all countries
            sorted_records = sorted(
                country_records, key=lambda x: self._get_sort_score(x[1]), reverse=True
            )

            filename = f"foreign_{status_type.lower()}"
            output_file = output_dir / f"{filename}.csv"

            with open(output_file, "w", newline="", encoding="utf-8") as f:
                csv_writer = writer(f)
                self._write_header_with_country(csv_writer)

                for country_name, record in sorted_records:
                    if isinstance(record, dict):
                        self._write_record_with_country_name(csv_writer, record, country_name)

    def _get_sort_score(self, record: JSONType) -> float:
        """Get the sort score from a record for sorting"""
        if isinstance(record, dict):
            analysis = record.get("analysis", {})
            if isinstance(analysis, dict):
                score = analysis.get("sort_score", 0.0)
                if isinstance(score, (int, float)):
                    return float(score)
        return 0.0

    def _group_by_country(
        self, by_status: dict[str, list[JSONType]]
    ) -> dict[str, dict[str, list[JSONType]]]:
        """Group statuses by country/origin

        Returns a hierarchical structure:
        {
            "US": {"NO_MATCH": [...], "PRE_1929": [...], ...},
            "France": {"NO_MATCH": [...], "RENEWED": [...], ...},
            ...
        }
        """
        grouped: dict[str, dict[str, list[JSONType]]] = {}

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

    def _write_header_with_country(self, csv_writer: CSVWriter) -> None:
        """Write CSV header row with country name column"""
        headers = [
            "ID",
            "Title",
            "Author",
            "Year",
            "Publisher",
            "Country of Publication",
            "Country Code",
            "Status",
            "Match Summary",
            "Warning",
            "Registration Source ID",
            "Renewal Entry ID",
        ]
        csv_writer.writerow(headers)  # type: ignore[arg-type]

    def _write_record_with_country_name(
        self, csv_writer: CSVWriter, record: dict[str, JSONType], country_name: str
    ) -> None:
        """Write a single record to CSV with country name"""
        marc = record.get("marc", {})
        matches = record.get("matches", {})
        analysis = record.get("analysis", {})

        # Extract MARC data
        marc_id = ""
        original = {}
        if isinstance(marc, dict):
            id_val = marc.get("id", "")
            if isinstance(id_val, str):
                marc_id = id_val
            orig_data = marc.get("original", {})
            if isinstance(orig_data, dict):
                original = orig_data

        title = original.get("title", "")
        author = original.get("author_245c") or original.get("author_1xx", "")
        year = original.get("year", "")
        publisher = original.get("publisher", "")

        # Extract metadata
        metadata = {}
        if isinstance(marc, dict):
            meta_data = marc.get("metadata", {})
            if isinstance(meta_data, dict):
                metadata = meta_data
        country_code = metadata.get("country_code", "")

        # Extract analysis data
        status = ""
        if isinstance(analysis, dict):
            status_val = analysis.get("status", "")
            if isinstance(status_val, str):
                status = status_val

        # Format match summary
        match_summary = ""
        if isinstance(matches, dict):
            match_summary = self._format_match_summary(matches)

        # Get warnings
        warnings = ""
        if isinstance(analysis, dict):
            warnings = self._get_warnings(analysis)

        # Get source IDs
        reg_id = ""
        ren_id = ""

        if isinstance(matches, dict):
            reg_data = matches.get("registration", {})
            if isinstance(reg_data, dict) and reg_data.get("found"):
                id_val = reg_data.get("id", "")
                if isinstance(id_val, str):
                    reg_id = id_val

            ren_data = matches.get("renewal", {})
            if isinstance(ren_data, dict) and ren_data.get("found"):
                id_val = ren_data.get("id", "")
                if isinstance(id_val, str):
                    ren_id = id_val

        # Write row with country name
        row = [
            marc_id,
            title,
            author,
            year,
            publisher,
            country_name,  # Use the provided country name
            country_code,
            status,
            match_summary,
            warnings,
            reg_id,
            ren_id,
        ]
        csv_writer.writerow(row)  # type: ignore[arg-type]

    def _write_header(self, csv_writer: CSVWriter) -> None:
        """Write CSV header row"""
        headers = [
            "ID",
            "Title",
            "Author",
            "Year",
            "Publisher",
            "Country",
            "Status",
            "Match Summary",
            "Warning",
            "Registration Source ID",
            "Renewal Entry ID",
        ]
        csv_writer.writerow(headers)  # type: ignore[arg-type]

    def _write_record(self, csv_writer: CSVWriter, record: dict[str, JSONType]) -> None:
        """Write a single record to CSV"""
        marc = record.get("marc", {})
        matches = record.get("matches", {})
        analysis = record.get("analysis", {})

        # Extract MARC data
        marc_id = ""
        original = {}
        if isinstance(marc, dict):
            id_val = marc.get("id", "")
            if isinstance(id_val, str):
                marc_id = id_val
            orig_data = marc.get("original", {})
            if isinstance(orig_data, dict):
                original = orig_data

        title = original.get("title", "")
        author = original.get("author_245c") or original.get("author_1xx", "")
        year = original.get("year", "")
        publisher = original.get("publisher", "")

        # Extract metadata
        metadata = {}
        if isinstance(marc, dict):
            meta_data = marc.get("metadata", {})
            if isinstance(meta_data, dict):
                metadata = meta_data
        country = metadata.get("country_code", "")

        # Extract analysis data
        status = ""
        if isinstance(analysis, dict):
            status_val = analysis.get("status", "")
            if isinstance(status_val, str):
                status = status_val

        # Format match summary
        match_summary = ""
        if isinstance(matches, dict):
            match_summary = self._format_match_summary(matches)

        # Get warnings
        warnings = ""
        if isinstance(analysis, dict):
            warnings = self._get_warnings(analysis)

        # Get source IDs
        reg_id = ""
        ren_id = ""

        if isinstance(matches, dict):
            reg_data = matches.get("registration", {})
            if isinstance(reg_data, dict) and reg_data.get("found"):
                id_val = reg_data.get("id", "")
                if isinstance(id_val, str):
                    reg_id = id_val

            ren_data = matches.get("renewal", {})
            if isinstance(ren_data, dict) and ren_data.get("found"):
                id_val = ren_data.get("id", "")
                if isinstance(id_val, str):
                    ren_id = id_val

        # Write row
        row = [
            marc_id,
            title,
            author,
            year,
            publisher,
            country,
            status,
            match_summary,
            warnings,
            reg_id,
            ren_id,
        ]
        csv_writer.writerow(row)  # type: ignore[arg-type]

    def _format_match_summary(self, matches: JSONType) -> str:
        """Format a concise match summary"""
        parts = []

        # Registration match
        reg_added = False
        if isinstance(matches, dict):
            reg = matches.get("registration", {})
            if isinstance(reg, dict) and reg.get("found"):
                match_type = reg.get("match_type", "similarity")
                if match_type == "lccn":
                    parts.append("Reg: LCCN")
                    reg_added = True
                else:
                    scores = reg.get("scores", {})
                    if isinstance(scores, dict):
                        overall_score = scores.get("overall", 0)
                        if isinstance(overall_score, (int, float)):
                            parts.append(f"Reg: {overall_score:.0f}%")
                            reg_added = True
                        else:
                            parts.append("Reg: 0%")
                            reg_added = True
                    else:
                        parts.append("Reg: 0%")
                        reg_added = True

        if not reg_added:
            parts.append("Reg: None")

        # Renewal match
        ren_added = False
        if isinstance(matches, dict):
            ren = matches.get("renewal", {})
            if isinstance(ren, dict) and ren.get("found"):
                match_type = ren.get("match_type", "similarity")
                if match_type == "lccn":
                    parts.append("Ren: LCCN")
                    ren_added = True
                else:
                    scores = ren.get("scores", {})
                    if isinstance(scores, dict):
                        overall_score = scores.get("overall", 0)
                        if isinstance(overall_score, (int, float)):
                            parts.append(f"Ren: {overall_score:.0f}%")
                            ren_added = True
                        else:
                            parts.append("Ren: 0%")
                            ren_added = True
                    else:
                        parts.append("Ren: 0%")
                        ren_added = True

        if not ren_added:
            parts.append("Ren: None")

        return ", ".join(parts)

    def _get_warnings(self, analysis: JSONType) -> str:
        """Get warning indicators for the record"""
        warnings = []

        # Check for generic title
        if isinstance(analysis, dict):
            generic_info = analysis.get("generic_title", {})
            if isinstance(generic_info, dict) and generic_info.get("detected"):
                warnings.append("Generic title")

            # Check for data completeness issues
            data_issues = analysis.get("data_completeness", [])
            if isinstance(data_issues, list):
                warnings.extend([x for x in data_issues if isinstance(x, str)])

        return ", ".join(warnings) if warnings else ""

    def _create_summary_csv(self, summary_path: Path, by_status: dict[str, list[JSONType]]) -> None:
        """Create summary CSV with statistics and explanations"""
        # Calculate total records
        total = sum(len(records) for records in by_status.values())

        # Status explanations mapping
        explanations = {
            "US_PRE_": "Published before copyright expiration year - public domain due to age",
            "US_REGISTERED_NOT_RENEWED": (
                "Registered 1923-1977 but not renewed - entered public domain"
            ),
            "US_RENEWED": "Registered and renewed - still under copyright protection",
            "US_NO_MATCH": "No registration or renewal found - copyright status uncertain",
            "FOREIGN_PRE_": (
                "Foreign work published before copyright expiration - likely public domain"
            ),
            "FOREIGN_RENEWED": "Foreign work with US renewal - may be under copyright",
            "FOREIGN_REGISTERED_NOT_RENEWED": "Foreign work registered but not renewed in US",
            "FOREIGN_NO_MATCH": "Foreign work with no US records - copyright status uncertain",
            "COUNTRY_UNKNOWN_RENEWED": "Unknown country with renewal - likely under copyright",
            "COUNTRY_UNKNOWN_REGISTERED_NOT_RENEWED": "Unknown country registered but not renewed",
            "COUNTRY_UNKNOWN_NO_MATCH": (
                "Country of origin unknown - cannot determine copyright pathway"
            ),
            "OUT_OF_DATA_RANGE": "Published after our data coverage ends (1991)",
        }

        with open(summary_path, "w", newline="", encoding="utf-8") as f:
            csv_writer = writer(f)
            csv_writer.writerow(["Status", "Count", "Percentage", "Explanation"])

            # Sort statuses for consistent output
            sorted_statuses = sorted(by_status.keys())

            for status in sorted_statuses:
                count = len(by_status[status])
                if count == 0:
                    continue

                percentage = (count / total * 100) if total > 0 else 0

                # Find explanation by pattern matching
                explanation = ""
                status_upper = status.upper()
                for pattern, desc in explanations.items():
                    if pattern in status_upper or status_upper.startswith(pattern):
                        explanation = desc
                        # Add year/country specifics if present
                        if "_PRE_" in status_upper:
                            parts = status_upper.split("_")
                            for part in parts:
                                if part.isdigit() and len(part) == 4:
                                    explanation = explanation.replace(
                                        "copyright expiration year", part
                                    )
                        if "FOREIGN_" in status_upper:
                            # Extract country code (last 3 letters)
                            parts = status_upper.split("_")
                            if len(parts[-1]) == 3 and parts[-1].isalpha():
                                explanation = f"{explanation} ({parts[-1]})"
                        break

                if not explanation:
                    explanation = "Status requires further analysis"

                csv_writer.writerow([status, count, f"{percentage:.1f}%", explanation])

            # Add total row
            csv_writer.writerow(["Total", total, "100.0%", "Total records analyzed"])

    def _format_status_filename(self, status: str) -> str:
        """Format status as valid filename"""
        # Convert to lowercase and replace problematic characters
        filename = status.lower()
        # Remove any characters that might cause issues
        filename = filename.replace("/", "_").replace("\\", "_").replace(":", "_")
        return filename

    def _write_header_with_country_code(self, csv_writer: CSVWriter) -> None:
        """Write CSV header row with country code column"""
        headers = [
            "ID",
            "Title",
            "Author",
            "Year",
            "Publisher",
            "Country",
            "Country_Code",  # Added column
            "Status",
            "Match Summary",
            "Warning",
            "Registration Source ID",
            "Renewal Entry ID",
        ]
        csv_writer.writerow(headers)  # type: ignore[arg-type]

    def _write_record_with_country_code(
        self, csv_writer: CSVWriter, record: dict[str, JSONType]
    ) -> None:
        """Write a single record to CSV with country code extracted from status"""
        marc = record.get("marc", {})
        matches = record.get("matches", {})
        analysis = record.get("analysis", {})

        # Extract MARC data
        marc_id = ""
        original = {}
        if isinstance(marc, dict):
            id_val = marc.get("id", "")
            if isinstance(id_val, str):
                marc_id = id_val
            orig_data = marc.get("original", {})
            if isinstance(orig_data, dict):
                original = orig_data

        title = original.get("title", "")
        author = original.get("author_245c") or original.get("author_1xx", "")
        year = original.get("year", "")
        publisher = original.get("publisher", "")

        # Extract metadata
        metadata = {}
        if isinstance(marc, dict):
            meta_data = marc.get("metadata", {})
            if isinstance(meta_data, dict):
                metadata = meta_data
        country = metadata.get("country_code", "")

        # Extract analysis data and country code from status
        status = ""
        country_code = ""
        if isinstance(analysis, dict):
            status_val = analysis.get("status", "")
            if isinstance(status_val, str):
                status = status_val
                # Extract country code from status (e.g., FOREIGN_RENEWED_FRA -> FRA)
                if "FOREIGN_" in status.upper():
                    parts = status.upper().split("_")
                    if len(parts) > 0 and len(parts[-1]) == 3 and parts[-1].isalpha():
                        country_code = parts[-1]

        # Format match summary
        match_summary = ""
        if isinstance(matches, dict):
            match_summary = self._format_match_summary(matches)

        # Get warnings
        warnings = ""
        if isinstance(analysis, dict):
            warnings = self._get_warnings(analysis)

        # Get source IDs
        reg_id = ""
        ren_id = ""

        if isinstance(matches, dict):
            reg_data = matches.get("registration", {})
            if isinstance(reg_data, dict) and reg_data.get("found"):
                id_val = reg_data.get("id", "")
                if isinstance(id_val, str):
                    reg_id = id_val

            ren_data = matches.get("renewal", {})
            if isinstance(ren_data, dict) and ren_data.get("found"):
                id_val = ren_data.get("id", "")
                if isinstance(id_val, str):
                    ren_id = id_val

        # Write row with country code
        row = [
            marc_id,
            title,
            author,
            year,
            publisher,
            country,
            country_code,  # Added field
            status,
            match_summary,
            warnings,
            reg_id,
            ren_id,
        ]
        csv_writer.writerow(row)  # type: ignore[arg-type]
