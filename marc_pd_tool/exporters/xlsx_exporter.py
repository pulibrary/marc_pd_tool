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
from marc_pd_tool.data.publication import Publication


class XLSXExporter:
    """Exports publication match results to Excel format"""

    __slots__ = ("publications", "output_path", "parameters", "score_everything", "column_widths")

    # Column width definitions
    COLUMN_WIDTHS = {
        "MARC ID": 15,
        "MARC Title": 50,
        "Registration Title": 50,
        "Renewal Title": 50,
        "Registration Title Score": 12,
        "Renewal Title Score": 12,
        "MARC Author (245c)": 30,
        "MARC Main Author (1xx)": 30,
        "Registration Author": 30,
        "Renewal Author": 30,
        "Registration Author Score": 12,
        "Renewal Author Score": 12,
        "MARC Year": 8,
        "Registration Date": 12,
        "Renewal Date": 12,
        "MARC Publisher": 30,
        "Registration Publisher": 30,
        "Renewal Publisher": 30,
        "Registration Publisher Score": 12,
        "Renewal Publisher Score": 12,
        "Registration Similarity Score": 12,
        "Renewal Similarity Score": 12,
        "MARC Place": 20,
        "MARC Edition": 20,
        "MARC LCCN": 15,
        "MARC Normalized LCCN": 15,
        "Language Code": 10,
        "Language Detection Status": 20,
        "Country Code": 10,
        "Country Classification": 12,
        "Copyright Status": 20,
        "Generic Title Detected": 12,
        "Generic Detection Reason": 30,
        "Registration Generic Title": 12,
        "Renewal Generic Title": 12,
        "Registration Source ID": 20,
        "Renewal Entry ID": 20,
        "Registration Match Type": 15,
        "Renewal Match Type": 15,
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
        score_everything: bool = False,
    ):
        """Initialize the XLSX exporter

        Args:
            publications: List of publications to export
            output_path: Path for the output XLSX file
            parameters: Processing parameters used (for summary sheet)
            score_everything: Whether score-everything mode was used
        """
        self.publications = publications
        self.output_path = output_path
        self.parameters = parameters or {}
        self.score_everything = score_everything
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
            "score_everything": "Score Everything",
        }

        for key, label in param_mapping.items():
            if key in self.parameters:
                ws[f"A{row}"] = f"{label}:"
                ws[f"B{row}"] = str(self.parameters[key])
                row += 1

        # Adjust column widths
        ws.column_dimensions["A"].width = 25
        ws.column_dimensions["B"].width = 20

    def _create_status_sheet(
        self, wb: Workbook, sheet_name: str, publications: list[Publication]
    ) -> None:
        """Create a sheet for publications with a specific status"""
        ws = wb.create_sheet(sheet_name)

        # Headers
        headers = [
            "MARC ID",
            "MARC Title",
            "Registration Title",
            "Renewal Title",
            "Registration Title Score",
            "Renewal Title Score",
            "MARC Author (245c)",
            "MARC Main Author (1xx)",
            "Registration Author",
            "Renewal Author",
            "Registration Author Score",
            "Renewal Author Score",
            "MARC Year",
            "Registration Date",
            "Renewal Date",
            "MARC Publisher",
            "Registration Publisher",
            "Renewal Publisher",
            "Registration Publisher Score",
            "Renewal Publisher Score",
            "Registration Similarity Score",
            "Renewal Similarity Score",
            "MARC Place",
            "MARC Edition",
            "MARC LCCN",
            "MARC Normalized LCCN",
            "Language Code",
            "Language Detection Status",
            "Country Code",
            "Country Classification",
            "Copyright Status",
            "Generic Title Detected",
            "Generic Detection Reason",
            "Registration Generic Title",
            "Renewal Generic Title",
            "Registration Source ID",
            "Renewal Entry ID",
            "Registration Match Type",
            "Renewal Match Type",
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
        # Registration match data
        reg_source_id = pub.registration_match.source_id if pub.registration_match else ""
        reg_title = pub.registration_match.matched_title if pub.registration_match else ""
        reg_author = pub.registration_match.matched_author if pub.registration_match else ""
        reg_date = pub.registration_match.matched_date if pub.registration_match else ""
        reg_similarity_score = (
            pub.registration_match.similarity_score if pub.registration_match else None
        )
        reg_title_score = pub.registration_match.title_score if pub.registration_match else None
        reg_author_score = pub.registration_match.author_score if pub.registration_match else None
        reg_publisher = (
            pub.registration_match.matched_publisher or "" if pub.registration_match else ""
        )
        reg_publisher_score = (
            pub.registration_match.publisher_score if pub.registration_match else None
        )
        reg_match_type = pub.registration_match.match_type if pub.registration_match else ""

        # Renewal match data
        ren_entry_id = pub.renewal_match.source_id if pub.renewal_match else ""
        ren_title = pub.renewal_match.matched_title if pub.renewal_match else ""
        ren_author = pub.renewal_match.matched_author if pub.renewal_match else ""
        ren_date = pub.renewal_match.matched_date if pub.renewal_match else ""
        ren_similarity_score = pub.renewal_match.similarity_score if pub.renewal_match else None
        ren_title_score = pub.renewal_match.title_score if pub.renewal_match else None
        ren_author_score = pub.renewal_match.author_score if pub.renewal_match else None
        ren_publisher = pub.renewal_match.matched_publisher or "" if pub.renewal_match else ""
        ren_publisher_score = pub.renewal_match.publisher_score if pub.renewal_match else None
        ren_match_type = pub.renewal_match.match_type if pub.renewal_match else ""

        # Write data with appropriate types
        data = [
            pub.source_id,  # Text
            pub.original_title,  # Text
            reg_title,  # Text
            ren_title,  # Text
            reg_title_score,  # Float (None if no match)
            ren_title_score,  # Float
            pub.original_author,  # Text
            pub.original_main_author,  # Text
            reg_author,  # Text
            ren_author,  # Text
            reg_author_score,  # Float
            ren_author_score,  # Float
            pub.year,  # Integer (might be None)
            reg_date,  # Text
            ren_date,  # Text
            pub.original_publisher,  # Text
            reg_publisher,  # Text
            ren_publisher,  # Text
            reg_publisher_score,  # Float
            ren_publisher_score,  # Float
            reg_similarity_score,  # Float
            ren_similarity_score,  # Float
            pub.original_place,  # Text
            pub.original_edition,  # Text
            pub.lccn or "",  # Text
            pub.normalized_lccn or "",  # Text
            pub.language_code,  # Text
            pub.language_detection_status,  # Text
            pub.country_code,  # Text
            pub.country_classification.value,  # Text
            pub.copyright_status.value,  # Text
            pub.generic_title_detected,  # Boolean
            pub.generic_detection_reason,  # Text
            pub.registration_generic_title,  # Boolean
            pub.renewal_generic_title,  # Boolean
            reg_source_id,  # Text
            ren_entry_id,  # Text
            reg_match_type,  # Text
            ren_match_type,  # Text
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
