# marc_pd_tool/exporters/csv_exporter.py

"""CSV export functionality that reads from JSON data"""

# Standard library imports
from csv import writer
from pathlib import Path

# Local imports
from marc_pd_tool.exporters.base_exporter import BaseJSONExporter
from marc_pd_tool.utils.types import CSVWriter
from marc_pd_tool.utils.types import JSONDict


class CSVExporter(BaseJSONExporter):
    """Export CSV files from JSON data

    Reads from the master JSON format and generates CSV files
    with simplified columns for easy analysis.
    """

    def export(self) -> None:
        """Export records to CSV file(s)"""
        if self.single_file:
            # Export all records to a single file
            self._export_single_file()
        else:
            # Export to separate files by status
            self._export_by_status()

    def _export_single_file(self) -> None:
        """Export all records to a single CSV file"""
        records = self.get_records()
        sorted_records = self.sort_by_quality(records)

        with open(self.output_path, "w", newline="", encoding="utf-8") as f:
            csv_writer = writer(f)
            self._write_header(csv_writer)

            for record in sorted_records:
                self._write_record(csv_writer, record)

    def _export_by_status(self) -> None:
        """Export records to separate files by copyright status"""
        by_status = self.group_by_status()

        # Get base path without extension
        path = Path(self.output_path)
        base_name = path.stem
        parent = path.parent

        for status, records in by_status.items():
            if not records:
                continue

            # Sort records by quality
            sorted_records = self.sort_by_quality(records)

            # Create filename for this status
            status_filename = status.lower()
            output_file = parent / f"{base_name}_{status_filename}.csv"

            with open(output_file, "w", newline="", encoding="utf-8") as f:
                csv_writer = writer(f)
                self._write_header(csv_writer)

                for record in sorted_records:
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
        csv_writer.writerow(headers)

    def _write_record(self, csv_writer: CSVWriter, record: JSONDict) -> None:
        """Write a single record to CSV"""
        marc = record.get("marc", {})
        matches = record.get("matches", {})
        analysis = record.get("analysis", {})

        # Extract MARC data
        marc_id = marc.get("id", "")
        original = marc.get("original", {})
        title = original.get("title", "")
        author = original.get("author_245c") or original.get("author_1xx", "")
        year = original.get("year", "")
        publisher = original.get("publisher", "")

        # Extract metadata
        metadata = marc.get("metadata", {})
        country = metadata.get("country_code", "")

        # Extract analysis data
        status = analysis.get("status", "")

        # Format match summary
        match_summary = self._format_match_summary(matches)

        # Get warnings
        warnings = self._get_warnings(analysis)

        # Get source IDs
        reg_id = ""
        ren_id = ""

        reg_match = matches.get("registration", {})
        if reg_match.get("found"):
            reg_id = reg_match.get("id", "")

        ren_match = matches.get("renewal", {})
        if ren_match.get("found"):
            ren_id = ren_match.get("id", "")

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
        csv_writer.writerow(row)

    def _format_match_summary(self, matches: JSONDict) -> str:
        """Format a concise match summary"""
        parts = []

        # Registration match
        reg = matches.get("registration", {})
        if reg.get("found"):
            match_type = reg.get("match_type", "similarity")
            if match_type == "lccn":
                parts.append("Reg: LCCN")
            else:
                scores = reg.get("scores", {})
                overall_score = scores.get("overall", 0)
                parts.append(f"Reg: {overall_score:.0f}%")
        else:
            parts.append("Reg: None")

        # Renewal match
        ren = matches.get("renewal", {})
        if ren.get("found"):
            match_type = ren.get("match_type", "similarity")
            if match_type == "lccn":
                parts.append("Ren: LCCN")
            else:
                scores = ren.get("scores", {})
                overall_score = scores.get("overall", 0)
                parts.append(f"Ren: {overall_score:.0f}%")
        else:
            parts.append("Ren: None")

        return ", ".join(parts)

    def _get_warnings(self, analysis: JSONDict) -> str:
        """Get warning indicators for the record"""
        warnings = []

        # Check for generic title
        generic_info = analysis.get("generic_title", {})
        if generic_info.get("detected"):
            warnings.append("Generic title")

        # Check for data completeness issues
        data_issues = analysis.get("data_completeness", [])
        if isinstance(data_issues, list):
            warnings.extend(data_issues)

        return ", ".join(warnings) if warnings else ""
