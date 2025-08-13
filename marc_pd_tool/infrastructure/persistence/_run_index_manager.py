# marc_pd_tool/infrastructure/persistence/_run_index_manager.py

"""Manager for tracking all tool runs in a master index"""

# Standard library imports
from csv import DictReader
from csv import DictWriter
from fcntl import LOCK_EX
from fcntl import LOCK_UN
from fcntl import flock
from logging import getLogger
from os import makedirs
from os.path import exists
from os.path import join

logger = getLogger(__name__)


class RunIndexManager:
    """Manages the master run index that tracks all tool executions"""

    __slots__ = ("index_path", "fieldnames")

    def __init__(self, log_dir: str = "logs"):
        """Initialize the run index manager

        Args:
            log_dir: Directory where logs and index are stored
        """
        makedirs(log_dir, exist_ok=True)
        self.index_path = join(log_dir, "_run_index.csv")
        self.fieldnames = [
            "timestamp",
            "log_file",
            "marcxml",
            "output_file",
            "us_only",
            "min_year",
            "max_year",
            "brute_force",
            "score_everything_mode",
            "title_threshold",
            "author_threshold",
            "marc_count",
            "duration_seconds",
            "matches_found",
            "status",
        ]

    def _initialize_index(self) -> None:
        """Create the index file with headers if it doesn't exist"""
        if not exists(self.index_path):
            with open(self.index_path, "w", newline="") as f:
                writer = DictWriter(f, fieldnames=self.fieldnames)
                writer.writeheader()

    def add_run(self, run_info: dict[str, str]) -> None:
        """Add a new run entry to the index

        Args:
            run_info: Dictionary containing run information
        """
        self._initialize_index()

        # Ensure all required fields have values
        for field in self.fieldnames:
            if field not in run_info:
                run_info[field] = ""

        # Use file locking to handle concurrent writes
        with open(self.index_path, "a", newline="") as f:
            try:
                # Acquire exclusive lock
                flock(f.fileno(), LOCK_EX)

                writer = DictWriter(f, fieldnames=self.fieldnames)
                writer.writerow(run_info)

                logger.info(f"Added run entry to index: {run_info.get('log_file', 'unknown')}")

            finally:
                # Release lock
                flock(f.fileno(), LOCK_UN)

    def update_run(self, log_file: str, updates: dict[str, str]) -> bool:
        """Update an existing run entry

        Args:
            log_file: Log file name to identify the run
            updates: Dictionary of fields to update

        Returns:
            True if updated successfully
        """
        if not exists(self.index_path):
            logger.warning(f"Run index does not exist: {self.index_path}")
            return False

        # Read all entries
        rows = []
        updated = False

        with open(self.index_path, "r", newline="") as f:
            reader = DictReader(f)
            for row in reader:
                if row.get("log_file") == log_file:
                    row.update(updates)
                    updated = True
                rows.append(row)

        if updated:
            # Write back all entries
            with open(self.index_path, "w", newline="") as f:
                try:
                    flock(f.fileno(), LOCK_EX)

                    writer = DictWriter(f, fieldnames=self.fieldnames)
                    writer.writeheader()
                    writer.writerows(rows)

                    logger.info(f"Updated run entry: {log_file}")

                finally:
                    flock(f.fileno(), LOCK_UN)

        return updated

    def get_next_run_index(self) -> int:
        """Get the next run index number

        Returns:
            The next sequential run index number
        """
        if not exists(self.index_path):
            return 1

        max_index = 0
        with open(self.index_path, "r", newline="") as f:
            reader = DictReader(f)
            for row in reader:
                # Extract run index from log_file if it contains one
                log_file = row.get("log_file", "")
                if "_run" in log_file:
                    try:
                        # Extract run number from filename like "marc_pd_20250101_120000_run001.log"
                        run_part = log_file.split("_run")[1].split(".")[0]
                        run_num = int(run_part)
                        max_index = max(max_index, run_num)
                    except (IndexError, ValueError):
                        pass

        return max_index + 1

    def get_recent_runs(self, limit: int = 10) -> list[dict[str, str]]:
        """Get the most recent run entries

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of run dictionaries, most recent first
        """
        if not exists(self.index_path):
            return []

        runs = []
        with open(self.index_path, "r", newline="") as f:
            reader = DictReader(f)
            runs = list(reader)

        # Sort by timestamp descending
        runs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        return runs[:limit]

    def get_run_by_log_file(self, log_file: str) -> dict[str, str | None] | None:
        """Get a specific run entry by log file name

        Args:
            log_file: Log file name to search for

        Returns:
            Run dictionary or None if not found
        """
        if not exists(self.index_path):
            return None

        with open(self.index_path, "r", newline="") as f:
            reader = DictReader(f)
            for row in reader:
                if row.get("log_file") == log_file:
                    return row

        return None
