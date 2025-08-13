# tests/test_infrastructure/test_run_index_manager.py

"""Tests for the run index manager functionality"""

# Standard library imports
from os.path import exists
from os.path import join
from tempfile import TemporaryDirectory

# Local imports
from marc_pd_tool.infrastructure import RunIndexManager


class TestRunIndexManager:
    """Test the RunIndexManager functionality"""

    def test_initialization(self):
        """Test that RunIndexManager initializes correctly"""
        with TemporaryDirectory() as temp_dir:
            log_dir = join(temp_dir, "logs")
            manager = RunIndexManager(log_dir)

            assert manager.index_path == join(log_dir, "_run_index.csv")
            assert exists(log_dir)
            assert len(manager.fieldnames) == 15
            assert "timestamp" in manager.fieldnames
            assert "log_file" in manager.fieldnames

    def test_initialize_index_creates_file(self):
        """Test that _initialize_index creates the CSV file with headers"""
        with TemporaryDirectory() as temp_dir:
            manager = RunIndexManager(temp_dir)

            # Initially file doesn't exist
            assert not exists(manager.index_path)

            # Initialize index
            manager._initialize_index()

            # File should now exist with headers
            assert exists(manager.index_path)

            with open(manager.index_path, "r") as f:
                content = f.read()
                assert "timestamp,log_file,marcxml" in content
                assert all(field in content for field in manager.fieldnames)

    def test_initialize_index_doesnt_overwrite(self):
        """Test that _initialize_index doesn't overwrite existing file"""
        with TemporaryDirectory() as temp_dir:
            manager = RunIndexManager(temp_dir)

            # Create file with content
            with open(manager.index_path, "w") as f:
                f.write("existing,content\n")

            # Initialize should not overwrite
            manager._initialize_index()

            with open(manager.index_path, "r") as f:
                content = f.read()
                assert content == "existing,content\n"

    def test_add_run_basic(self):
        """Test adding a basic run entry"""
        with TemporaryDirectory() as temp_dir:
            manager = RunIndexManager(temp_dir)

            run_info = {
                "timestamp": "2025-01-31T10:00:00",
                "log_file": "test_run.log",
                "marcxml": "test.xml",
                "output_file": "output.csv",
                "us_only": "True",
                "min_year": "1950",
                "max_year": "1977",
                "brute_force": "False",
                "score_everything_mode": "False",
                "title_threshold": "40",
                "author_threshold": "30",
                "marc_count": "100",
                "duration_seconds": "120.5",
                "matches_found": "75",
                "status": "completed",
            }

            manager.add_run(run_info)

            # Verify file was created and contains the entry
            assert exists(manager.index_path)

            with open(manager.index_path, "r") as f:
                content = f.read()
                assert "test_run.log" in content
                assert "test.xml" in content
                assert "100" in content

    def test_add_run_missing_fields(self):
        """Test adding run with missing fields fills them with empty strings"""
        with TemporaryDirectory() as temp_dir:
            manager = RunIndexManager(temp_dir)

            # Minimal run info
            run_info = {"timestamp": "2025-01-31T10:00:00", "log_file": "minimal.log"}

            manager.add_run(run_info)

            # Read back and verify empty fields
            run = manager.get_run_by_log_file("minimal.log")
            assert run is not None
            assert run["log_file"] == "minimal.log"
            assert run["marcxml"] == ""
            assert run["output_file"] == ""

    def test_update_run_success(self):
        """Test updating an existing run entry"""
        with TemporaryDirectory() as temp_dir:
            manager = RunIndexManager(temp_dir)

            # Add initial run
            run_info = {
                "timestamp": "2025-01-31T10:00:00",
                "log_file": "update_test.log",
                "status": "running",
                "matches_found": "0",
            }
            manager.add_run(run_info)

            # Update the run
            updates = {"status": "completed", "matches_found": "50", "duration_seconds": "180.2"}

            result = manager.update_run("update_test.log", updates)
            assert result is True

            # Verify updates
            run = manager.get_run_by_log_file("update_test.log")
            assert run["status"] == "completed"
            assert run["matches_found"] == "50"
            assert run["duration_seconds"] == "180.2"

    def test_update_run_not_found(self):
        """Test updating a non-existent run returns False"""
        with TemporaryDirectory() as temp_dir:
            manager = RunIndexManager(temp_dir)

            # Add a run
            manager.add_run({"log_file": "exists.log"})

            # Try to update non-existent run
            result = manager.update_run("doesnt_exist.log", {"status": "completed"})
            assert result is False

    def test_update_run_no_index(self):
        """Test updating when index doesn't exist returns False"""
        with TemporaryDirectory() as temp_dir:
            manager = RunIndexManager(temp_dir)

            # Don't create any runs
            result = manager.update_run("any.log", {"status": "completed"})
            assert result is False

    def test_get_recent_runs_empty(self):
        """Test getting recent runs when index is empty"""
        with TemporaryDirectory() as temp_dir:
            manager = RunIndexManager(temp_dir)

            runs = manager.get_recent_runs()
            assert runs == []

    def test_get_recent_runs_limit(self):
        """Test getting recent runs with limit"""
        with TemporaryDirectory() as temp_dir:
            manager = RunIndexManager(temp_dir)

            # Add multiple runs
            for i in range(15):
                run_info = {"timestamp": f"2025-01-31T10:{i:02d}:00", "log_file": f"run_{i}.log"}
                manager.add_run(run_info)

            # Get recent runs with default limit
            runs = manager.get_recent_runs()
            assert len(runs) == 10

            # Get recent runs with custom limit
            runs = manager.get_recent_runs(limit=5)
            assert len(runs) == 5

            # Verify they're sorted by timestamp descending
            assert runs[0]["log_file"] == "run_14.log"
            assert runs[1]["log_file"] == "run_13.log"

    def test_get_recent_runs_sorting(self):
        """Test that recent runs are sorted by timestamp descending"""
        with TemporaryDirectory() as temp_dir:
            manager = RunIndexManager(temp_dir)

            # Add runs in non-chronological order
            manager.add_run({"timestamp": "2025-01-31T12:00:00", "log_file": "middle.log"})
            manager.add_run({"timestamp": "2025-01-31T10:00:00", "log_file": "first.log"})
            manager.add_run({"timestamp": "2025-01-31T14:00:00", "log_file": "last.log"})

            runs = manager.get_recent_runs()
            assert len(runs) == 3
            assert runs[0]["log_file"] == "last.log"
            assert runs[1]["log_file"] == "middle.log"
            assert runs[2]["log_file"] == "first.log"

    def test_get_run_by_log_file_found(self):
        """Test getting a specific run by log file"""
        with TemporaryDirectory() as temp_dir:
            manager = RunIndexManager(temp_dir)

            # Add runs
            manager.add_run(
                {
                    "timestamp": "2025-01-31T10:00:00",
                    "log_file": "target.log",
                    "marcxml": "target.xml",
                }
            )
            manager.add_run(
                {
                    "timestamp": "2025-01-31T11:00:00",
                    "log_file": "other.log",
                    "marcxml": "other.xml",
                }
            )

            # Get specific run
            run = manager.get_run_by_log_file("target.log")
            assert run is not None
            assert run["log_file"] == "target.log"
            assert run["marcxml"] == "target.xml"

    def test_get_run_by_log_file_not_found(self):
        """Test getting a non-existent run returns None"""
        with TemporaryDirectory() as temp_dir:
            manager = RunIndexManager(temp_dir)

            # Add a run
            manager.add_run({"log_file": "exists.log"})

            # Try to get non-existent run
            run = manager.get_run_by_log_file("doesnt_exist.log")
            assert run is None

    def test_get_run_by_log_file_no_index(self):
        """Test getting run when index doesn't exist returns None"""
        with TemporaryDirectory() as temp_dir:
            manager = RunIndexManager(temp_dir)

            # Don't create any runs
            run = manager.get_run_by_log_file("any.log")
            assert run is None

    def test_concurrent_writes(self):
        """Test that file locking works for concurrent writes"""
        with TemporaryDirectory() as temp_dir:
            manager = RunIndexManager(temp_dir)

            # Add multiple runs in quick succession
            for i in range(10):
                run_info = {
                    "timestamp": f"2025-01-31T10:00:{i:02d}",
                    "log_file": f"concurrent_{i}.log",
                }
                manager.add_run(run_info)

            # Verify all runs were added
            runs = manager.get_recent_runs(limit=20)
            assert len(runs) == 10
            log_files = {run["log_file"] for run in runs}
            expected = {f"concurrent_{i}.log" for i in range(10)}
            assert log_files == expected

    def test_fieldnames_order_preserved(self):
        """Test that CSV fields are written in the correct order"""
        with TemporaryDirectory() as temp_dir:
            manager = RunIndexManager(temp_dir)

            run_info = {
                "timestamp": "2025-01-31T10:00:00",
                "log_file": "order_test.log",
                "marcxml": "test.xml",
                "output_file": "output.csv",
                "us_only": "True",
                "min_year": "1950",
                "max_year": "1977",
                "brute_force": "False",
                "score_everything_mode": "False",
                "title_threshold": "40",
                "author_threshold": "30",
                "marc_count": "100",
                "duration_seconds": "120.5",
                "matches_found": "75",
                "status": "completed",
            }

            manager.add_run(run_info)

            # Read back and verify field order
            with open(manager.index_path, "r") as f:
                lines = f.readlines()
                header = lines[0].strip()
                expected_header = ",".join(manager.fieldnames)
                assert header == expected_header

    def test_empty_string_handling(self):
        """Test that empty strings are handled correctly"""
        with TemporaryDirectory() as temp_dir:
            manager = RunIndexManager(temp_dir)

            run_info = {
                "timestamp": "",
                "log_file": "empty_test.log",
                "marcxml": "",
                "output_file": "",
                "status": "",
            }

            manager.add_run(run_info)

            run = manager.get_run_by_log_file("empty_test.log")
            assert run is not None
            assert run["timestamp"] == ""
            assert run["marcxml"] == ""
            assert run["status"] == ""

    def test_special_characters_in_values(self):
        """Test handling of special characters in CSV values"""
        with TemporaryDirectory() as temp_dir:
            manager = RunIndexManager(temp_dir)

            run_info = {
                "log_file": "special.log",
                "marcxml": "file,with,commas.xml",
                "output_file": 'file"with"quotes.csv',
                "status": "completed\nwith newline",
            }

            manager.add_run(run_info)

            run = manager.get_run_by_log_file("special.log")
            assert run is not None
            assert run["marcxml"] == "file,with,commas.xml"
            assert "quotes" in run["output_file"]
