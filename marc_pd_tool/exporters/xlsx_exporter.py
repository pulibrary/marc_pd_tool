# marc_pd_tool/exporters/xlsx_exporter.py

"""XLSX export functionality for publication match results"""

# Standard library imports
from datetime import datetime

# Third party imports
from openpyxl import Workbook
from openpyxl.styles import Alignment
from openpyxl.styles import Font
from openpyxl.styles import PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

# Local imports
from marc_pd_tool.data.enums import CopyrightStatus
from marc_pd_tool.data.enums import MatchType
from marc_pd_tool.data.publication import Publication


def _calculate_confidence(pub: Publication) -> str:
    """Calculate confidence level based on match scores and type
    
    Returns:
        HIGH, MEDIUM, LOW, or WARNING
    """
    # If we have an LCCN match, it's always HIGH confidence
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
    
    # Apply confidence thresholds
    if best_score >= 85:
        return "HIGH"
    elif best_score >= 60:
        return "MEDIUM"
    elif best_score > 0:
        return "LOW"
    else:
        return "WARNING"


def _format_match_summary(pub: Publication) -> str:
    """Format a concise match summary
    
    Returns:
        String like "Reg: 95%, Ren: None" or "Reg: LCCN, Ren: 82%"
    """
    parts = []
    
    if pub.registration_match:
        if pub.registration_match.match_type == MatchType.LCCN:
            parts.append("Reg: LCCN")
        else:
            parts.append(f"Reg: {pub.registration_match.similarity_score:.0f}%")
    else:
        parts.append("Reg: None")
        
    if pub.renewal_match:
        if pub.renewal_match.match_type == MatchType.LCCN:
            parts.append("Ren: LCCN")
        else:
            parts.append(f"Ren: {pub.renewal_match.similarity_score:.0f}%")
    else:
        parts.append("Ren: None")
        
    return ", ".join(parts)


def _get_warnings(pub: Publication) -> str:
    """Get warning indicators for the record
    
    Returns:
        Comma-separated warnings or empty string
    """
    warnings = []
    
    if pub.generic_title_detected:
        warnings.append("Generic title")
        
    if not pub.year:
        warnings.append("No year")
        
    if pub.country_classification.value == "Unknown":
        warnings.append("Unknown country")
        
    return ", ".join(warnings)


class XLSXExporter:
    """Exports publication match results to Excel format"""

    __slots__ = (
        "publications",
        "output_path",
        "parameters",
        "score_everything_mode",
        "column_widths",
    )

    # Column width definitions
    COLUMN_WIDTHS = {
        "ID": 15,
        "Title": 50,
        "Author": 30,
        "Year": 8,
        "Publisher": 30,
        "Country": 12,
        "Status": 20,
        "Match Summary": 25,
        "Confidence": 12,
        "Warning": 20,
        "Registration Source ID": 20,
        "Renewal Entry ID": 20,
    }

    # Header styling
    HEADER_FONT = Font(bold=True, color="FFFFFF")
    HEADER_FILL = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
    HEADER_ALIGNMENT = Alignment(horizontal="center", vertical="center")

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
        score_everything_mode: bool = False,
    ):
        """Initialize the XLSX exporter

        Args:
            publications: List of publications to export
            output_path: Path for the output XLSX file
            parameters: Processing parameters used (for summary sheet)
            score_everything_mode: Whether score-everything mode was used
        """
        self.publications = publications
        self.output_path = output_path
        self.parameters = parameters or {}
        self.score_everything_mode = score_everything_mode
        self.column_widths = self.COLUMN_WIDTHS.copy()

    def export(self) -> None:
        """Export publications to XLSX file"""
        wb = Workbook()

        # Remove default sheet
        wb.remove(wb.active)

        # Create summary sheet
        self._create_summary_sheet(wb)

        # Group publications by status
        by_status = self._group_by_status()

        # Create sheet for each status
        for status in CopyrightStatus:
            if status in by_status and by_status[status]:
                sheet_name = self.STATUS_TAB_NAMES.get(status, status.value)
                self._create_status_sheet(wb, sheet_name, by_status[status])

        # Save workbook
        wb.save(self.output_path)

    def _group_by_status(self) -> dict[CopyrightStatus, list[Publication]]:
        """Group publications by copyright status"""
        groups: dict[CopyrightStatus, list[Publication]] = {}
        for pub in self.publications:
            status = pub.copyright_status
            if status not in groups:
                groups[status] = []
            groups[status].append(pub)
        return groups

    def _create_summary_sheet(self, wb: Workbook) -> None:
        """Create summary sheet with statistics"""
        ws = wb.create_sheet("Summary")

        # Title
        ws["A1"] = "MARC PD Tool Results Summary"
        ws["A1"].font = Font(bold=True, size=16)
        ws.merge_cells("A1:B1")

        # Processing info
        ws["A3"] = "Processing Date:"
        ws["B3"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        ws["A4"] = "Total Records:"
        ws["B4"] = len(self.publications)

        # Match statistics
        matches_found = sum(
            1 for pub in self.publications if pub.registration_match or pub.renewal_match
        )
        ws["A5"] = "Matches Found:"
        ws["B5"] = matches_found

        # Status breakdown
        ws["A7"] = "By Copyright Status:"
        ws["A7"].font = Font(bold=True)

        by_status = self._group_by_status()
        row = 8
        for status in CopyrightStatus:
            if status in by_status:
                ws[f"A{row}"] = self.STATUS_TAB_NAMES.get(status, status.value) + ":"
                ws[f"B{row}"] = len(by_status[status])
                row += 1

        # Parameters used
        row += 1
        ws[f"A{row}"] = "Parameters Used:"
        ws[f"A{row}"].font = Font(bold=True)
        row += 1

        param_mapping = {
            "title_threshold": "Title Threshold",
            "author_threshold": "Author Threshold",
            "year_tolerance": "Year Tolerance",
            "min_year": "Min Year",
            "max_year": "Max Year",
            "us_only": "US Only",
            "brute_force_missing_year": "Brute Force Missing Year",
            "score_everything_mode": "Score Everything Mode",
        }

        for key, label in param_mapping.items():
            if key in self.parameters:
                ws[f"A{row}"] = f"{label}:"
                ws[f"B{row}"] = str(self.parameters[key])
                row += 1

        # Status Definitions
        row += 2
        ws[f"A{row}"] = "Copyright Status Definitions:"
        ws[f"A{row}"].font = Font(bold=True, size=12)
        row += 1
        
        # Create status definition table
        status_definitions = [
            ("Status Code", "Meaning", "Explanation"),
            ("PD_NO_RENEWAL", "Public Domain - Not Renewed", "US work 1930-1963 that was registered but not renewed"),
            ("PD_DATE_VERIFY", "Likely Public Domain - Verify Date", "May be public domain based on publication date"),
            ("IN_COPYRIGHT", "Protected by Copyright", "Found renewal or other evidence of copyright"),
            ("RESEARCH_US_STATUS", "Foreign Work - Has US Registration", "Non-US work with US copyright activity"),
            ("RESEARCH_US_ONLY_PD", "Foreign Work - No US Registration", "Non-US work, likely PD in US only"),
            ("COUNTRY_UNKNOWN", "Unknown Country - Manual Review", "Cannot determine country of publication"),
        ]
        
        # Write header row with formatting
        for col, header in enumerate(status_definitions[0], 1):
            cell = ws.cell(row=row, column=col)
            cell.value = header
            cell.font = Font(bold=True)
            cell.fill = PatternFill(start_color="CCCCCC", end_color="CCCCCC", fill_type="solid")
        
        # Write definition rows
        for status_row in status_definitions[1:]:
            row += 1
            for col, value in enumerate(status_row, 1):
                ws.cell(row=row, column=col, value=value)
        
        # Confidence Level Explanations
        row += 2
        ws[f"A{row}"] = "Confidence Level Explanations:"
        ws[f"A{row}"].font = Font(bold=True, size=12)
        row += 1
        
        confidence_definitions = [
            ("Level", "Criteria"),
            ("HIGH", "LCCN match OR combined score ≥85%"),
            ("MEDIUM", "Combined score 60-84%"),
            ("LOW", "Combined score 1-59%"),
            ("WARNING", "No matches found or special conditions (generic title, no year)"),
        ]
        
        for conf_row in confidence_definitions:
            ws[f"A{row}"] = conf_row[0] + ":"
            ws[f"B{row}"] = conf_row[1]
            if row == row - len(confidence_definitions) + 1:  # Header row
                ws[f"A{row}"].font = Font(bold=True)
            row += 1
        
        # Adjust column widths
        ws.column_dimensions["A"].width = 25
        ws.column_dimensions["B"].width = 50
        ws.column_dimensions["C"].width = 60

    def _create_status_sheet(
        self, wb: Workbook, sheet_name: str, publications: list[Publication]
    ) -> None:
        """Create a sheet for publications with a specific status"""
        ws = wb.create_sheet(sheet_name)

        # Headers
        headers = [
            "ID",
            "Title",
            "Author",
            "Year",
            "Publisher",
            "Country",
            "Status",
            "Match Summary",
            "Confidence",
            "Warning",
            "Registration Source ID",
            "Renewal Entry ID",
        ]

        # Write headers
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col)
            cell.value = header
            cell.font = self.HEADER_FONT
            cell.fill = self.HEADER_FILL
            cell.alignment = self.HEADER_ALIGNMENT

        # Write data
        for row_num, pub in enumerate(publications, 2):
            self._write_publication_row(ws, row_num, pub)

        # Adjust column widths
        for col, header in enumerate(headers, 1):
            width = self.column_widths.get(header, 15)
            ws.column_dimensions[get_column_letter(col)].width = width

        # Freeze header row
        ws.freeze_panes = "A2"

        # Add auto filter
        ws.auto_filter.ref = ws.dimensions

    def _write_publication_row(self, ws: Worksheet, row_num: int, pub: Publication) -> None:
        """Write a single publication row with proper data types"""
        # Use 245c author if available, otherwise fall back to 1xx
        author = pub.original_author or pub.original_main_author or ""
        
        # Get source IDs for verification
        reg_source_id = pub.registration_match.source_id if pub.registration_match else ""
        ren_entry_id = pub.renewal_match.source_id if pub.renewal_match else ""

        # Write data with appropriate types
        data = [
            pub.source_id,  # Text
            pub.original_title,  # Text
            author,  # Text
            pub.year,  # Integer (might be None)
            pub.original_publisher or "",  # Text
            pub.country_classification.value,  # Text
            pub.copyright_status.value,  # Text
            _format_match_summary(pub),  # Text
            _calculate_confidence(pub),  # Text
            _get_warnings(pub),  # Text
            reg_source_id,  # Text
            ren_entry_id,  # Text
        ]

        for col, value in enumerate(data, 1):
            cell = ws.cell(row=row_num, column=col)

            # Set value with proper type
            if isinstance(value, bool):
                cell.value = value
            elif isinstance(value, (int, float)):
                cell.value = value
                if isinstance(value, float):
                    cell.number_format = "0.00"
            else:
                cell.value = str(value) if value is not None else ""
