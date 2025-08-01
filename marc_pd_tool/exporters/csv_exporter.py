# marc_pd_tool/exporters/csv_exporter.py

"""CSV export functionality that reads from JSON data"""

# Standard library imports
from csv import writer
from pathlib import Path

# Local imports
from marc_pd_tool.exporters.base_exporter import BaseJSONExporter
from marc_pd_tool.utils.types import CSVWriter
from marc_pd_tool.utils.types import JSONType


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
                if isinstance(record, dict):
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
                    if isinstance(record, dict):
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
