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

        # Create summary CSV first
        self._create_summary_csv(output_dir / "_summary.csv", by_status)

        # Separate US, foreign, and unknown records
        us_statuses: dict[str, list[JSONType]] = {}
        foreign_by_status_type: dict[str, list[JSONType]] = {}  # Group by status type, not country
        unknown_statuses: dict[str, list[JSONType]] = {}

        for status, records in by_status.items():
            if not records:
                continue

            status_upper = status.upper()
            if status_upper.startswith("US_") or "US_" in status_upper:
                us_statuses[status] = records
            elif status_upper.startswith("FOREIGN_"):
                # Extract status type without country code
                # FOREIGN_RENEWED_FRA -> FOREIGN_RENEWED
                # FOREIGN_PRE_1929_GBR -> FOREIGN_PRE_1929
                parts = status_upper.split("_")
                if len(parts) >= 3:
                    # Remove the last part if it looks like a country code (3 chars, all letters)
                    if len(parts[-1]) == 3 and parts[-1].isalpha():
                        status_type = "_".join(parts[:-1])
                    else:
                        status_type = status_upper
                else:
                    status_type = status_upper

                if status_type not in foreign_by_status_type:
                    foreign_by_status_type[status_type] = []
                foreign_by_status_type[status_type].extend(records)
            elif "UNKNOWN" in status_upper:
                unknown_statuses[status] = records
            else:
                # Default to US for unrecognized patterns
                us_statuses[status] = records

        # Export US statuses to separate files
        for status, records in us_statuses.items():
            sorted_records = self.sort_by_quality(records)
            filename = self._format_status_filename(status)
            output_file = output_dir / f"{filename}.csv"

            with open(output_file, "w", newline="", encoding="utf-8") as f:
                csv_writer = writer(f)
                self._write_header(csv_writer)

                for record in sorted_records:
                    # JSON structure already validated
                    self._write_record(csv_writer, record)

        # Export foreign records grouped by status type (all countries together)
        for status_type, records in foreign_by_status_type.items():
            sorted_records = self.sort_by_quality(records)
            filename = self._format_status_filename(status_type)
            output_file = output_dir / f"{filename}.csv"

            with open(output_file, "w", newline="", encoding="utf-8") as f:
                csv_writer = writer(f)
                self._write_header_with_country_code(csv_writer)

                for record in sorted_records:
                    # JSON structure already validated
                    self._write_record_with_country_code(csv_writer, record)

        # Export unknown country statuses to separate files
        for status, records in unknown_statuses.items():
            sorted_records = self.sort_by_quality(records)
            filename = self._format_status_filename(status)
            output_file = output_dir / f"{filename}.csv"

            with open(output_file, "w", newline="", encoding="utf-8") as f:
                csv_writer = writer(f)
                self._write_header(csv_writer)

                for record in sorted_records:
                    # JSON structure already validated
                    self._write_record(csv_writer, record)

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
