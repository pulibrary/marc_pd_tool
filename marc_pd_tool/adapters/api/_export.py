# marc_pd_tool/adapters/api/_export.py

"""Export component for exporting analysis results"""

# Standard library imports
from logging import getLogger
from pathlib import Path
from typing import TYPE_CHECKING

# Local imports
from marc_pd_tool.adapters.exporters.csv_exporter import CSVExporter
from marc_pd_tool.adapters.exporters.xlsx_exporter import XLSXExporter
from marc_pd_tool.core.types.protocols import ExportAnalyzerProtocol

if TYPE_CHECKING:
    # Local imports
    pass

logger = getLogger(__name__)


class ExportComponent:
    """Component for exporting analysis results"""

    def export_results(
        self: ExportAnalyzerProtocol,
        output_path: str,
        formats: list[str] | None = None,
        single_file: bool = False,
    ) -> None:
        """Export analysis results to specified formats

        Args:
            output_path: Base path for output files
            formats: List of output formats (json, csv, xlsx, html)
            single_file: If True, create single file instead of splitting by status
        """
        if formats is None:
            formats = ["json", "csv"]

        logger.info(f"Exporting results to {output_path}")
        logger.info(f"Formats: {', '.join(formats)}")

        # Ensure all publications are loaded from result files
        self.results.load_all_publications()

        # JSON is the source of truth - ALWAYS create it first for ANY export format
        json_path = f"{output_path}.json"

        # Always create JSON first (it's the source of truth for all other formats)
        if not Path(json_path).exists():
            self.results.export_json(json_path)
            self.results.add_result_file("json", json_path)
            logger.info(f"  ✓ JSON: {json_path}")

        export_count = 0
        for fmt in formats:
            fmt = fmt.lower()
            try:
                if fmt == "json":
                    # Already created above as source of truth
                    export_count += 1

                elif fmt == "csv":
                    if single_file:
                        # Single CSV file
                        output_file = f"{output_path}.csv"
                        # Use CSV exporter with single file mode
                        # JSON was already created above - CSV reads from it
                        # Pass the full output path with .csv extension
                        csv_exporter = CSVExporter(json_path, output_file, single_file=True)
                        csv_exporter.export()

                        self.results.add_result_file("csv", output_file)
                        logger.info(f"  ✓ CSV: {output_file}")
                    else:
                        # Multiple CSV files by status
                        self.results.export_csv(output_path)
                        self.results.add_result_file("csv", output_path)
                        logger.info(f"  ✓ CSV: Multiple files at {output_path}_*.csv")
                    export_count += 1

                elif fmt == "xlsx":
                    output_file = f"{output_path}.xlsx"
                    # Use XLSX exporter that reads from JSON (source of truth)
                    # JSON was already created above - XLSX reads from it
                    xlsx_exporter = XLSXExporter(json_path, output_file, single_file=single_file)
                    xlsx_exporter.export()

                    self.results.add_result_file("xlsx", output_file)
                    logger.info(f"  ✓ XLSX: {output_file}")
                    export_count += 1

                elif fmt == "html":
                    output_dir = f"{output_path}_html"
                    self.results.export_html(output_dir)
                    self.results.add_result_file("html", output_dir)
                    logger.info(f"  ✓ HTML: {output_dir}/")
                    export_count += 1

                else:
                    logger.warning(f"Unknown export format: {fmt}")

            except Exception as e:
                logger.error(f"Failed to export {fmt}: {e}")

        if export_count > 0:
            logger.info(f"Successfully exported to {export_count} format(s)")
        else:
            logger.warning("No exports completed successfully")

    def get_statistics(self: ExportAnalyzerProtocol) -> dict[str, int]:
        """Get analysis statistics

        Returns:
            Dictionary of statistics
        """
        # Return a copy to prevent external modification
        return self.results.statistics.to_dict()
