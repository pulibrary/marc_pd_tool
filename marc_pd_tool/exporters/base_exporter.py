# marc_pd_tool/exporters/base_exporter.py

"""Base exporter class that reads from JSON data"""

# Standard library imports
from abc import ABC
from abc import abstractmethod
import gzip
import json
from pathlib import Path

# Local imports
from marc_pd_tool.utils.types import JSONDict


class BaseJSONExporter(ABC):
    """Base class for exporters that read from JSON data

    All exporters should derive from this class and read data from JSON
    rather than directly from Publication objects. This ensures consistency
    and makes JSON the single source of truth for all export formats.
    """

    __slots__ = ("json_data", "output_path", "single_file")

    def __init__(self, json_path: str, output_path: str, single_file: bool = False):
        """Initialize the exporter with JSON data

        Args:
            json_path: Path to the JSON file (can be .json or .json.gz)
            output_path: Path for the output file
            single_file: Whether to export all records to a single file
        """
        self.output_path = output_path
        self.single_file = single_file
        self.json_data = self._load_json(json_path)

    def _load_json(self, json_path: str) -> JSONDict:
        """Load JSON data from file

        Args:
            json_path: Path to JSON file (supports .gz compression)

        Returns:
            Loaded JSON data as dictionary
        """
        path = Path(json_path)

        if path.suffix == ".gz" or str(path).endswith(".json.gz"):
            with gzip.open(json_path, "rt", encoding="utf-8") as f:
                return json.load(f)
        else:
            with open(json_path, "r", encoding="utf-8") as f:
                return json.load(f)

    @abstractmethod
    def export(self) -> None:
        """Export the data in the specific format

        This method must be implemented by each exporter subclass.
        """
        pass

    def get_records(self) -> list[JSONDict]:
        """Get all records from the JSON data

        Returns:
            List of record dictionaries
        """
        records = self.json_data.get("records", [])
        if not isinstance(records, list):
            return []
        return records

    def get_metadata(self) -> JSONDict:
        """Get metadata from the JSON data

        Returns:
            Metadata dictionary
        """
        metadata = self.json_data.get("metadata", {})
        if not isinstance(metadata, dict):
            return {}
        return metadata

    def group_by_status(self) -> dict[str, list[JSONDict]]:
        """Group records by copyright status

        Returns:
            Dictionary mapping status to list of records
        """
        grouped: dict[str, list[JSONDict]] = {}

        for record in self.get_records():
            if not isinstance(record, dict):
                continue

            analysis = record.get("analysis", {})
            if not isinstance(analysis, dict):
                continue

            status = analysis.get("status", "UNKNOWN")
            if status not in grouped:
                grouped[status] = []
            grouped[status].append(record)

        return grouped

    def sort_by_quality(self, records: list[JSONDict]) -> list[JSONDict]:
        """Sort records by match quality (best first)

        Args:
            records: List of records to sort

        Returns:
            Sorted list of records
        """

        def get_sort_score(record: JSONDict) -> float:
            """Calculate sort score for a record"""
            analysis = record.get("analysis", {})
            if isinstance(analysis, dict):
                score = analysis.get("sort_score", 0.0)
                if isinstance(score, (int, float)):
                    return float(score)
            return 0.0

        return sorted(records, key=get_sort_score, reverse=True)
