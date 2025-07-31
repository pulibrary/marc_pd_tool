# marc_pd_tool/exporters/xlsx_stacked_exporter.py

"""Stacked XLSX export functionality for detailed match analysis"""

# Standard library imports
from datetime import datetime

# Third party imports
from openpyxl import Workbook
from openpyxl.styles import Alignment
from openpyxl.styles import Border
from openpyxl.styles import Font
from openpyxl.styles import PatternFill
from openpyxl.styles import Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

# Local imports
from marc_pd_tool.data.enums import CopyrightStatus
from marc_pd_tool.data.enums import MatchType
from marc_pd_tool.data.publication import Publication


class StackedXLSXExporter:
    """Exports publication match results in stacked format for detailed comparison"""

    __slots__ = ("publications", "output_path", "parameters")

    # Header styling
    HEADER_FONT = Font(bold=True, color="FFFFFF")
    HEADER_FILL = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
    HEADER_ALIGNMENT = Alignment(horizontal="center", vertical="center")

    # Sub-header styling
    SUBHEADER_FONT = Font(bold=True)
    SUBHEADER_FILL = PatternFill(start_color="E0E0E0", end_color="E0E0E0", fill_type="solid")

    # Score coloring
    HIGH_SCORE_FILL = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
    MEDIUM_SCORE_FILL = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")
    LOW_SCORE_FILL = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")

    # Borders
    THIN_BORDER = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )

    # Tab name mapping
    STATUS_TAB_NAMES = {
        CopyrightStatus.PD_DATE_VERIFY: "PD Date Verify",
        CopyrightStatus.PD_NO_RENEWAL: "PD No Renewal",
        CopyrightStatus.IN_COPYRIGHT: "In Copyright",
        CopyrightStatus.RESEARCH_US_STATUS: "Research US Status",
        CopyrightStatus.RESEARCH_US_ONLY_PD: "Research US Only PD",
        CopyrightStatus.COUNTRY_UNKNOWN: "Country Unknown",
    }

    def __init__(
        self,
        publications: list[Publication],
        output_path: str,
        parameters: dict[str, str | None] | None = None,
    ):
        """Initialize the stacked XLSX exporter

        Args:
            publications: List of publications to export
            output_path: Path for the output XLSX file
            parameters: Processing parameters used (for summary sheet)
        """
        self.publications = publications
        self.output_path = output_path
        self.parameters = parameters or {}

    def export(self) -> None:
        """Export publications to stacked XLSX file"""
        wb = Workbook()

        # Remove default sheet
        wb.remove(wb.active)

        # Create summary sheet
        self._create_summary_sheet(wb)

        # Group publications by status
        by_status = self._group_by_status()

        # Create a sheet for each status
        for status in CopyrightStatus:
            if status in by_status:
                sheet_name = self.STATUS_TAB_NAMES.get(status, status.value)
                self._create_status_sheet(wb, sheet_name, by_status[status])

        # Save the workbook
        wb.save(self.output_path)

    def _group_by_status(self) -> dict[CopyrightStatus, list[Publication]]:
        """Group publications by copyright status"""
        groups: dict[CopyrightStatus, list[Publication]] = {}
        for pub in self.publications:
            if pub.copyright_status not in groups:
                groups[pub.copyright_status] = []
            groups[pub.copyright_status].append(pub)
        return groups

    def _create_summary_sheet(self, wb: Workbook) -> None:
        """Create summary sheet with statistics and definitions"""
        ws = wb.create_sheet("Summary")

        # Title
        ws["A1"] = "MARC PD Tool Stacked Results"
        ws["A1"].font = Font(bold=True, size=16)
        ws.merge_cells("A1:B1")

        # Processing info
        ws["A3"] = "Processing Date:"
        ws["B3"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        ws["A4"] = "Total Records:"
        ws["B4"] = len(self.publications)

        # Format description
        ws["A6"] = "Format Description:"
        ws["A6"].font = Font(bold=True)
        ws["A7"] = "This stacked format shows original and normalized text side-by-side"
        ws["A8"] = "for easy comparison. Scores appear next to the matched data."
        ws.merge_cells("A7:D7")
        ws.merge_cells("A8:D8")

        # Status breakdown
        ws["A10"] = "By Copyright Status:"
        ws["A10"].font = Font(bold=True)

        by_status = self._group_by_status()
        row = 11
        for status in CopyrightStatus:
            if status in by_status:
                ws[f"A{row}"] = self.STATUS_TAB_NAMES.get(status, status.value) + ":"
                ws[f"B{row}"] = len(by_status[status])
                row += 1

        # Adjust column widths
        ws.column_dimensions["A"].width = 25
        ws.column_dimensions["B"].width = 20

    def _create_status_sheet(
        self, wb: Workbook, sheet_name: str, publications: list[Publication]
    ) -> None:
        """Create a sheet for publications with a specific status"""
        ws = wb.create_sheet(sheet_name)

        # Start row for first record
        current_row = 1

        # Process each publication
        for i, pub in enumerate(publications):
            current_row = self._write_stacked_record(ws, current_row, pub, i + 1)
            current_row += 2  # Add blank rows between records

        # Set column widths
        ws.column_dimensions["A"].width = 12
        ws.column_dimensions["B"].width = 12
        ws.column_dimensions["C"].width = 50
        ws.column_dimensions["D"].width = 8
        ws.column_dimensions["E"].width = 30
        ws.column_dimensions["F"].width = 8
        ws.column_dimensions["G"].width = 30
        ws.column_dimensions["H"].width = 8
        ws.column_dimensions["I"].width = 6

    def _write_stacked_record(
        self, ws: Worksheet, start_row: int, pub: Publication, record_num: int
    ) -> int:
        """Write a single record in stacked format

        Returns:
            The next available row number
        """
        row = start_row

        # Record header
        ws.cell(row=row, column=1, value=f"Record {record_num}")
        ws.cell(row=row, column=1).font = Font(bold=True, size=12)
        ws.merge_cells(f"A{row}:I{row}")

        # Record summary
        row += 1
        ws.cell(row=row, column=1, value="ID:")
        ws.cell(row=row, column=2, value=pub.source_id)
        ws.cell(row=row, column=3, value="Status:")
        ws.cell(row=row, column=4, value=pub.copyright_status.value)
        ws.cell(row=row, column=5, value="Country:")
        ws.cell(row=row, column=6, value=pub.country_classification.value)

        # Overall match summary
        row += 1
        overall_confidence = self._calculate_overall_confidence(pub)
        ws.cell(row=row, column=1, value="Overall:")
        ws.cell(row=row, column=2, value=overall_confidence)
        self._apply_confidence_formatting(ws.cell(row=row, column=2), overall_confidence)

        if pub.generic_title_detected:
            ws.cell(row=row, column=3, value="⚠️ Generic title detected")
            ws.cell(row=row, column=3).font = Font(color="FF6600")

        # Comparison table headers
        row += 2
        headers = [
            "Source",
            "Version",
            "Title",
            "Score",
            "Author",
            "Score",
            "Publisher",
            "Score",
            "Year",
        ]
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=row, column=col, value=header)
            cell.font = self.HEADER_FONT
            cell.fill = self.HEADER_FILL
            cell.alignment = self.HEADER_ALIGNMENT
            cell.border = self.THIN_BORDER

        # MARC Original
        row += 1
        self._write_data_row(
            ws,
            row,
            "MARC",
            "Original",
            pub.original_title,
            None,
            self._get_display_author(pub),
            None,
            pub.original_publisher,
            None,
            pub.year,
        )

        # MARC Normalized
        row += 1
        self._write_data_row(
            ws,
            row,
            "MARC",
            "Normalized",
            pub.title,
            None,
            pub.author,
            None,
            pub.publisher,
            None,
            None,
        )

        # Registration data
        row += 1
        if pub.registration_match:
            match = pub.registration_match
            self._write_data_row(
                ws,
                row,
                "Registration",
                "Original",
                match.matched_title,
                match.title_score,
                match.matched_author,
                match.author_score,
                match.matched_publisher,
                match.publisher_score,
                match.matched_date,
            )

            # Add LCCN indicator if applicable
            if match.match_type == MatchType.LCCN:
                ws.cell(row=row, column=10, value="LCCN Match")
                ws.cell(row=row, column=10).font = Font(bold=True, color="006600")
        else:
            self._write_no_match_row(ws, row, "Registration")

        # Registration normalized (skipped for brevity - would be same as original in current implementation)

        # Renewal data
        row += 1
        if pub.renewal_match:
            match = pub.renewal_match
            self._write_data_row(
                ws,
                row,
                "Renewal",
                "Original",
                match.matched_title,
                match.title_score,
                match.matched_author,
                match.author_score,
                match.matched_publisher,
                match.publisher_score,
                match.matched_date,
            )

            # Add LCCN indicator if applicable
            if match.match_type == MatchType.LCCN:
                ws.cell(row=row, column=10, value="LCCN Match")
                ws.cell(row=row, column=10).font = Font(bold=True, color="006600")
        else:
            self._write_no_match_row(ws, row, "Renewal")

        return row + 1

    def _write_data_row(
        self,
        ws: Worksheet,
        row: int,
        source: str,
        version: str,
        title: str | None,
        title_score: float | None,
        author: str | None,
        author_score: float | None,
        publisher: str | None,
        publisher_score: float | None,
        year: str | int | None,
    ) -> None:
        """Write a single data row with formatting"""
        # Source and version
        ws.cell(row=row, column=1, value=source).border = self.THIN_BORDER
        ws.cell(row=row, column=2, value=version).border = self.THIN_BORDER

        # Title
        ws.cell(row=row, column=3, value=title or "").border = self.THIN_BORDER
        if title_score is not None:
            cell = ws.cell(row=row, column=4, value=f"{title_score:.1f}%")
            cell.border = self.THIN_BORDER
            self._apply_score_formatting(cell, title_score)
        else:
            ws.cell(row=row, column=4, value="").border = self.THIN_BORDER

        # Author
        ws.cell(row=row, column=5, value=author or "").border = self.THIN_BORDER
        if author_score is not None:
            cell = ws.cell(row=row, column=6, value=f"{author_score:.1f}%")
            cell.border = self.THIN_BORDER
            self._apply_score_formatting(cell, author_score)
        else:
            ws.cell(row=row, column=6, value="").border = self.THIN_BORDER

        # Publisher
        ws.cell(row=row, column=7, value=publisher or "").border = self.THIN_BORDER
        if publisher_score is not None:
            cell = ws.cell(row=row, column=8, value=f"{publisher_score:.1f}%")
            cell.border = self.THIN_BORDER
            self._apply_score_formatting(cell, publisher_score)
        else:
            ws.cell(row=row, column=8, value="").border = self.THIN_BORDER

        # Year
        ws.cell(row=row, column=9, value=str(year) if year else "").border = self.THIN_BORDER

    def _write_no_match_row(self, ws: Worksheet, row: int, source: str) -> None:
        """Write a row indicating no match found"""
        ws.cell(row=row, column=1, value=source).border = self.THIN_BORDER
        ws.cell(row=row, column=2, value="No match").border = self.THIN_BORDER
        for col in range(3, 10):
            ws.cell(row=row, column=col, value="-").border = self.THIN_BORDER

    def _get_display_author(self, pub: Publication) -> str:
        """Get the best author for display (245c preferred)"""
        return pub.original_author or pub.original_main_author or ""

    def _calculate_overall_confidence(self, pub: Publication) -> str:
        """Calculate overall confidence level"""
        # If we have an LCCN match, it's always HIGH
        if pub.registration_match and pub.registration_match.match_type == MatchType.LCCN:
            return "HIGH"
        if pub.renewal_match and pub.renewal_match.match_type == MatchType.LCCN:
            return "HIGH"

        # Calculate best combined score
        best_score = 0.0
        if pub.registration_match:
            best_score = max(best_score, pub.registration_match.similarity_score)
        if pub.renewal_match:
            best_score = max(best_score, pub.renewal_match.similarity_score)

        # Apply thresholds
        if best_score >= 85:
            return "HIGH"
        elif best_score >= 60:
            return "MEDIUM"
        elif best_score > 0:
            return "LOW"
        else:
            return "NO MATCH"

    def _apply_score_formatting(self, cell, score: float) -> None:
        """Apply color formatting based on score value"""
        if score >= 85:
            cell.fill = self.HIGH_SCORE_FILL
        elif score >= 60:
            cell.fill = self.MEDIUM_SCORE_FILL
        else:
            cell.fill = self.LOW_SCORE_FILL

    def _apply_confidence_formatting(self, cell, confidence: str) -> None:
        """Apply formatting based on confidence level"""
        if confidence == "HIGH":
            cell.fill = self.HIGH_SCORE_FILL
            cell.font = Font(bold=True, color="006600")
        elif confidence == "MEDIUM":
            cell.fill = self.MEDIUM_SCORE_FILL
            cell.font = Font(bold=True, color="996600")
        elif confidence == "LOW":
            cell.fill = self.LOW_SCORE_FILL
            cell.font = Font(bold=True, color="990000")
        else:
            cell.font = Font(bold=True, color="666666")
