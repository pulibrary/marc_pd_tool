# tests/adapters/exporters/test_csv_exporter.py

"""Comprehensive tests for CSV exporter functionality"""

# Standard library imports
from csv import reader
from csv import writer
from json import dump
from pathlib import Path
from tempfile import TemporaryDirectory

# Third party imports
from pytest import fixture

# Local imports
from marc_pd_tool.adapters.exporters.csv_exporter import CSVExporter


class TestCSVExporter:
    """Test CSV export functionality"""

    @fixture
    def sample_json_data(self):
        """Create sample JSON data structure"""
        return {
            "metadata": {"version": "1.0", "created_at": "2025-01-01", "total_records": 4},
            "records": [
                {
                    "marc": {
                        "id": "001",
                        "original": {
                            "title": "Test Book 1",
                            "author_245c": "Author One",
                            "publisher": "Publisher A",
                            "year": "1950",
                            "lccn": "50001234",
                        },
                        "metadata": {"country_code": "usa"},
                    },
                    "analysis": {
                        "status": "US_REGISTERED_NOT_RENEWED",
                        "reason": "US_REGISTERED_NO_RENEWAL",
                    },
                    "matches": {
                        "registrations": [
                            {
                                "matched_title": "Test Book 1",
                                "matched_author": "Author One",
                                "similarity_score": 95.0,
                                "source_id": "A123456",
                            }
                        ]
                    },
                },
                {
                    "marc": {
                        "id": "002",
                        "original": {
                            "title": "Test Book 2",
                            "author_245c": "Author Two",
                            "publisher": "Publisher B",
                            "year": "1960",
                        },
                        "metadata": {"country_code": "usa"},
                    },
                    "analysis": {"status": "US_NO_MATCH", "reason": "US_NO_MATCH"},
                },
                {
                    "marc": {
                        "id": "003",
                        "original": {
                            "title": "Foreign Book",
                            "author_245c": "Foreign Author",
                            "publisher": "Foreign Publisher",
                            "year": "1955",
                        },
                        "metadata": {"country_code": "gbr"},
                    },
                    "analysis": {"status": "FOREIGN_RENEWED_gbr", "reason": "FOREIGN_RENEWED"},
                    "matches": {
                        "renewals": [
                            {
                                "matched_title": "Foreign Book",
                                "matched_author": "Foreign Author",
                                "similarity_score": 88.0,
                                "source_id": "R789012",
                            }
                        ]
                    },
                },
                {
                    "marc": {
                        "id": "004",
                        "original": {
                            "title": "Unknown Country Book",
                            "author_245c": "Unknown Author",
                            "year": "1945",
                        },
                        "metadata": {"country_code": ""},
                    },
                    "analysis": {
                        "status": "COUNTRY_UNKNOWN_NO_MATCH",
                        "reason": "COUNTRY_UNKNOWN_NO_MATCH",
                    },
                },
            ],
        }

    def test_export_single_file(self, sample_json_data):
        """Test exporting all records to a single CSV file"""
        with TemporaryDirectory() as temp_dir:
            # Create JSON file
            json_path = Path(temp_dir) / "test_data.json"
            with open(json_path, "w", encoding="utf-8") as f:
                dump(sample_json_data, f)

            output_path = Path(temp_dir) / "output.csv"

            exporter = CSVExporter(
                json_path=str(json_path), output_path=str(output_path), single_file=True
            )

            exporter.export()

            # Check file was created
            assert output_path.exists()

            # Read and verify CSV content
            with open(output_path, "r", encoding="utf-8") as f:
                csv_reader = list(reader(f))

                # Check header
                assert csv_reader[0][0] == "ID"
                assert "Title" in csv_reader[0]
                assert "Author" in csv_reader[0]
                assert "Status" in csv_reader[0]

                # Check we have all records (header + 4 records)
                assert len(csv_reader) == 5

                # Check first record content
                assert csv_reader[1][0] == "001"  # ID
                assert "Test Book 1" in csv_reader[1]
                assert "US_REGISTERED_NOT_RENEWED" in csv_reader[1]

    def test_export_organized_structure(self, sample_json_data):
        """Test exporting records to organized folder structure"""
        with TemporaryDirectory() as temp_dir:
            # Create JSON file
            json_path = Path(temp_dir) / "test_data.json"
            with open(json_path, "w", encoding="utf-8") as f:
                dump(sample_json_data, f)

            output_path = Path(temp_dir) / "output.csv"

            exporter = CSVExporter(
                json_path=str(json_path), output_path=str(output_path), single_file=False
            )

            exporter.export()

            # Check output directory was created
            output_dir = Path(temp_dir) / "output_csv"
            assert output_dir.exists()
            assert output_dir.is_dir()

            # Check summary file exists
            summary_file = output_dir / "_summary.csv"
            assert summary_file.exists()

            # Check status-specific files were created
            expected_files = [
                "us_registered_not_renewed.csv",
                "us_no_match.csv",
                "foreign_renewed.csv",  # Should be grouped without country code
                "country_unknown_no_match.csv",
            ]

            created_files = [f.name for f in output_dir.glob("*.csv")]
            for expected in expected_files:
                assert expected in created_files, f"Missing {expected} in {created_files}"

    def test_summary_csv_creation(self, sample_json_data):
        """Test summary CSV creation with counts by status"""
        with TemporaryDirectory() as temp_dir:
            # Create JSON file
            json_path = Path(temp_dir) / "test_data.json"
            with open(json_path, "w", encoding="utf-8") as f:
                dump(sample_json_data, f)

            output_path = Path(temp_dir) / "output.csv"

            exporter = CSVExporter(
                json_path=str(json_path), output_path=str(output_path), single_file=False
            )

            exporter.export()

            # Read summary file
            summary_file = Path(temp_dir) / "output_csv" / "_summary.csv"
            with open(summary_file, "r", encoding="utf-8") as f:
                csv_reader = list(reader(f))

                # Check header
                assert csv_reader[0] == ["Status", "Count", "Percentage", "Explanation"]

                # Check we have entries for each status
                assert len(csv_reader) > 1

                # Check total row exists
                total_row = csv_reader[-1]
                assert total_row[0] == "Total"
                assert total_row[1] == "4"  # Total count
                assert total_row[2] == "100.0%"

    def test_foreign_status_grouping(self):
        """Test that foreign statuses are grouped by type, not country"""
        json_data = {
            "metadata": {"version": "1.0"},
            "records": [
                {
                    "marc": {
                        "id": "001",
                        "original": {"title": "French Book", "year": "1950"},
                        "metadata": {"country_code": "fra"},
                    },
                    "analysis": {"status": "FOREIGN_RENEWED_fra", "reason": "FOREIGN_RENEWED"},
                },
                {
                    "marc": {
                        "id": "002",
                        "original": {"title": "German Book", "year": "1951"},
                        "metadata": {"country_code": "deu"},
                    },
                    "analysis": {"status": "FOREIGN_RENEWED_deu", "reason": "FOREIGN_RENEWED"},
                },
                {
                    "marc": {
                        "id": "003",
                        "original": {"title": "British Book", "year": "1920"},
                        "metadata": {"country_code": "gbr"},
                    },
                    "analysis": {
                        "status": "FOREIGN_PRE_1929_gbr",
                        "reason": "FOREIGN_PRE_COPYRIGHT_EXPIRATION",
                    },
                },
            ],
        }

        with TemporaryDirectory() as temp_dir:
            # Create JSON file
            json_path = Path(temp_dir) / "test_data.json"
            with open(json_path, "w", encoding="utf-8") as f:
                dump(json_data, f)

            output_path = Path(temp_dir) / "output.csv"

            exporter = CSVExporter(
                json_path=str(json_path), output_path=str(output_path), single_file=False
            )

            exporter.export()

            output_dir = Path(temp_dir) / "output_csv"

            # Should have grouped files by status type
            assert (output_dir / "foreign_renewed.csv").exists()
            assert (output_dir / "foreign_pre_1929.csv").exists()

            # Check that foreign_renewed has both French and German books
            with open(output_dir / "foreign_renewed.csv", "r", encoding="utf-8") as f:
                csv_reader = list(reader(f))
                # Header + 2 records
                assert len(csv_reader) == 3

    def test_write_header(self):
        """Test CSV header writing"""
        with TemporaryDirectory() as temp_dir:
            # Create empty JSON file
            json_path = Path(temp_dir) / "empty.json"
            with open(json_path, "w", encoding="utf-8") as f:
                dump({"metadata": {}, "records": []}, f)

            output_path = Path(temp_dir) / "test.csv"

            exporter = CSVExporter(
                json_path=str(json_path), output_path=str(output_path), single_file=True
            )

            # Test header writing
            with open(output_path, "w", newline="", encoding="utf-8") as f:
                csv_writer = writer(f)
                exporter._write_header(csv_writer)

            # Read and verify header
            with open(output_path, "r", encoding="utf-8") as f:
                csv_reader = list(reader(f))
                header = csv_reader[0]

                expected_columns = [
                    "ID",
                    "Title",
                    "Author",
                    "Year",
                    "Publisher",
                    "Country",
                    "Status",
                    "Match Summary",
                    "Warning",
                ]

                for col in expected_columns:
                    assert col in header

    def test_write_record(self):
        """Test writing individual record to CSV"""
        json_data = {
            "metadata": {},
            "records": [
                {
                    "marc": {
                        "id": "TEST001",
                        "original": {
                            "title": "Test Title",
                            "author_245c": "Test Author",
                            "publisher": "Test Publisher",
                            "year": "1950",
                            "lccn": "50123456",
                        },
                        "metadata": {"country_code": "usa"},
                    },
                    "analysis": {
                        "status": "US_REGISTERED_NOT_RENEWED",
                        "reason": "US_REGISTERED_NO_RENEWAL",
                    },
                    "matches": {
                        "registrations": [
                            {
                                "matched_title": "Test Title",
                                "matched_author": "Test Author",
                                "similarity_score": 95.0,
                                "title_score": 98.0,
                                "author_score": 92.0,
                                "source_id": "A123456",
                            }
                        ]
                    },
                }
            ],
        }

        with TemporaryDirectory() as temp_dir:
            # Create JSON file
            json_path = Path(temp_dir) / "test_data.json"
            with open(json_path, "w", encoding="utf-8") as f:
                dump(json_data, f)

            output_path = Path(temp_dir) / "test.csv"

            exporter = CSVExporter(
                json_path=str(json_path), output_path=str(output_path), single_file=True
            )

            with open(output_path, "w", newline="", encoding="utf-8") as f:
                csv_writer = writer(f)
                exporter._write_header(csv_writer)
                exporter._write_record(csv_writer, exporter.records[0])

            # Read and verify
            with open(output_path, "r", encoding="utf-8") as f:
                csv_reader = list(reader(f))

                # Check record data
                data_row = csv_reader[1]
                assert "TEST001" in data_row
                assert "Test Title" in data_row
                assert "Test Author" in data_row
                assert "US_REGISTERED_NOT_RENEWED" in data_row
                # Check that US_REGISTERED_NOT_RENEWED status is present
                assert "US_REGISTERED_NOT_RENEWED" in data_row

    def test_format_status_filename(self):
        """Test status filename formatting"""
        with TemporaryDirectory() as temp_dir:
            # Create empty JSON file
            json_path = Path(temp_dir) / "empty.json"
            with open(json_path, "w", encoding="utf-8") as f:
                dump({"metadata": {}, "records": []}, f)

            exporter = CSVExporter(
                json_path=str(json_path), output_path="test.csv", single_file=False
            )

        # Test various status formats (they are converted to lowercase)
        assert exporter._format_status_filename("US_NO_MATCH") == "us_no_match"
        assert exporter._format_status_filename("FOREIGN_RENEWED_gbr") == "foreign_renewed_gbr"
        assert (
            exporter._format_status_filename("COUNTRY_UNKNOWN_NO_MATCH")
            == "country_unknown_no_match"
        )

    def test_empty_records(self):
        """Test handling of empty record list"""
        with TemporaryDirectory() as temp_dir:
            # Create empty JSON file
            json_path = Path(temp_dir) / "empty.json"
            with open(json_path, "w", encoding="utf-8") as f:
                dump({"metadata": {}, "records": []}, f)

            output_path = Path(temp_dir) / "empty.csv"

            exporter = CSVExporter(
                json_path=str(json_path), output_path=str(output_path), single_file=True
            )

            exporter.export()

            # File should be created with just header
            assert output_path.exists()

            with open(output_path, "r", encoding="utf-8") as f:
                csv_reader = list(reader(f))
                assert len(csv_reader) == 1  # Just header

    def test_record_with_missing_fields(self):
        """Test handling records with missing optional fields"""
        json_data = {
            "metadata": {},
            "records": [
                {
                    "marc": {
                        "id": "MIN001",
                        "original": {
                            "title": "Minimal Record"
                            # Missing author, publisher, year, etc.
                        },
                        "metadata": {},
                    },
                    "analysis": {"status": "US_NO_MATCH", "reason": "US_NO_MATCH"},
                }
            ],
        }

        with TemporaryDirectory() as temp_dir:
            # Create JSON file
            json_path = Path(temp_dir) / "test_data.json"
            with open(json_path, "w", encoding="utf-8") as f:
                dump(json_data, f)

            output_path = Path(temp_dir) / "minimal.csv"

            exporter = CSVExporter(
                json_path=str(json_path), output_path=str(output_path), single_file=True
            )

            # Should not raise an error
            exporter.export()

            assert output_path.exists()

            with open(output_path, "r", encoding="utf-8") as f:
                csv_reader = list(reader(f))
                assert len(csv_reader) == 2  # Header + 1 record

    def test_sort_by_quality(self):
        """Test record sorting by quality metrics"""
        json_data = {
            "metadata": {},
            "records": [
                {
                    "marc": {"id": "001", "original": {"title": "Book 1"}, "metadata": {}},
                    "analysis": {"status": "US_NO_MATCH", "sort_score": 50.0},
                    "matches": {"registrations": [{"similarity_score": 50.0}]},
                },
                {
                    "marc": {"id": "002", "original": {"title": "Book 2"}, "metadata": {}},
                    "analysis": {"status": "US_REGISTERED_NOT_RENEWED", "sort_score": 95.0},
                    "matches": {
                        "registrations": [{"similarity_score": 95.0, "is_lccn_match": True}]
                    },
                },
                {
                    "marc": {"id": "003", "original": {"title": "Book 3"}, "metadata": {}},
                    "analysis": {"status": "US_RENEWED", "sort_score": 80.0},
                    "matches": {"renewals": [{"similarity_score": 80.0}]},
                },
            ],
        }

        with TemporaryDirectory() as temp_dir:
            # Create JSON file
            json_path = Path(temp_dir) / "test_data.json"
            with open(json_path, "w", encoding="utf-8") as f:
                dump(json_data, f)

            exporter = CSVExporter(
                json_path=str(json_path), output_path="test.csv", single_file=True
            )

        sorted_records = exporter.sort_by_quality(exporter.records)

        # LCCN match should be first
        assert sorted_records[0]["marc"]["id"] == "002"
        # Higher score should be second
        assert sorted_records[1]["marc"]["id"] == "003"
        # Lower score should be last
        assert sorted_records[2]["marc"]["id"] == "001"

    def test_group_by_status(self):
        """Test grouping records by copyright status"""
        json_data = {
            "metadata": {},
            "records": [
                {
                    "marc": {"id": "001", "original": {"title": "Book 1"}, "metadata": {}},
                    "analysis": {"status": "US_NO_MATCH"},
                },
                {
                    "marc": {"id": "002", "original": {"title": "Book 2"}, "metadata": {}},
                    "analysis": {"status": "US_NO_MATCH"},
                },
                {
                    "marc": {"id": "003", "original": {"title": "Book 3"}, "metadata": {}},
                    "analysis": {"status": "US_RENEWED"},
                },
            ],
        }

        with TemporaryDirectory() as temp_dir:
            # Create JSON file
            json_path = Path(temp_dir) / "test_data.json"
            with open(json_path, "w", encoding="utf-8") as f:
                dump(json_data, f)

            exporter = CSVExporter(
                json_path=str(json_path), output_path="test.csv", single_file=False
            )

        grouped = exporter.group_by_status()

        assert "US_NO_MATCH" in grouped
        assert len(grouped["US_NO_MATCH"]) == 2
        assert "US_RENEWED" in grouped
        assert len(grouped["US_RENEWED"]) == 1

    def test_percentage_calculation_in_summary(self):
        """Test percentage calculation in summary CSV"""
        json_data = {
            "metadata": {},
            "records": [
                {
                    "marc": {"id": f"{i:03d}", "original": {}, "metadata": {}},
                    "analysis": {"status": status},
                }
                for i, status in enumerate(["US_NO_MATCH"] * 3 + ["US_RENEWED"] * 1)
            ],
        }

        with TemporaryDirectory() as temp_dir:
            # Create JSON file
            json_path = Path(temp_dir) / "test_data.json"
            with open(json_path, "w", encoding="utf-8") as f:
                dump(json_data, f)

            output_path = Path(temp_dir) / "test.csv"

            exporter = CSVExporter(
                json_path=str(json_path), output_path=str(output_path), single_file=False
            )

            exporter.export()

            summary_file = Path(temp_dir) / "test_csv" / "_summary.csv"
            with open(summary_file, "r", encoding="utf-8") as f:
                csv_reader = list(reader(f))

                # Find US_NO_MATCH row
                for row in csv_reader[1:]:
                    if row[0] == "US_NO_MATCH":
                        assert row[1] == "3"  # Count
                        assert row[2] == "75.0%"  # Percentage
                        break

    def test_format_match_summary_with_registration_scores(self):
        """Test formatting match summary with registration scores"""
        with TemporaryDirectory() as temp_dir:
            # Create JSON file
            json_path = Path(temp_dir) / "empty.json"
            with open(json_path, "w", encoding="utf-8") as f:
                dump({"metadata": {}, "records": []}, f)

            exporter = CSVExporter(
                json_path=str(json_path), output_path="test.csv", single_file=True
            )

            # Test registration with similarity scores
            matches = {
                "registration": {
                    "found": True,
                    "match_type": "similarity",
                    "scores": {"overall": 85.5},
                }
            }
            summary = exporter._format_match_summary(matches)
            assert summary == "Reg: 86%, Ren: None"

            # Test registration with invalid score type
            matches = {
                "registration": {
                    "found": True,
                    "match_type": "similarity",
                    "scores": {"overall": "invalid"},
                }
            }
            summary = exporter._format_match_summary(matches)
            assert summary == "Reg: 0%, Ren: None"

            # Test registration with missing scores dict
            matches = {"registration": {"found": True, "match_type": "similarity"}}
            summary = exporter._format_match_summary(matches)
            assert summary == "Reg: 0%, Ren: None"

    def test_format_match_summary_with_renewal_scores(self):
        """Test formatting match summary with renewal scores"""
        with TemporaryDirectory() as temp_dir:
            # Create JSON file
            json_path = Path(temp_dir) / "empty.json"
            with open(json_path, "w", encoding="utf-8") as f:
                dump({"metadata": {}, "records": []}, f)

            exporter = CSVExporter(
                json_path=str(json_path), output_path="test.csv", single_file=True
            )

            # Test renewal with similarity scores
            matches = {
                "renewal": {"found": True, "match_type": "similarity", "scores": {"overall": 92.3}}
            }
            summary = exporter._format_match_summary(matches)
            assert summary == "Reg: None, Ren: 92%"

            # Test renewal with invalid score type
            matches = {
                "renewal": {
                    "found": True,
                    "match_type": "similarity",
                    "scores": {"overall": "invalid"},
                }
            }
            summary = exporter._format_match_summary(matches)
            assert summary == "Reg: None, Ren: 0%"

            # Test renewal with missing scores dict
            matches = {"renewal": {"found": True, "match_type": "similarity"}}
            summary = exporter._format_match_summary(matches)
            assert summary == "Reg: None, Ren: 0%"

    def test_format_match_summary_with_lccn_matches(self):
        """Test formatting match summary with LCCN matches"""
        with TemporaryDirectory() as temp_dir:
            # Create JSON file
            json_path = Path(temp_dir) / "empty.json"
            with open(json_path, "w", encoding="utf-8") as f:
                dump({"metadata": {}, "records": []}, f)

            exporter = CSVExporter(
                json_path=str(json_path), output_path="test.csv", single_file=True
            )

            # Test LCCN match for registration
            matches = {"registration": {"found": True, "match_type": "lccn"}}
            summary = exporter._format_match_summary(matches)
            assert summary == "Reg: LCCN, Ren: None"

            # Test LCCN match for renewal
            matches = {"renewal": {"found": True, "match_type": "lccn"}}
            summary = exporter._format_match_summary(matches)
            assert summary == "Reg: None, Ren: LCCN"

            # Test both LCCN matches
            matches = {
                "registration": {"found": True, "match_type": "lccn"},
                "renewal": {"found": True, "match_type": "lccn"},
            }
            summary = exporter._format_match_summary(matches)
            assert summary == "Reg: LCCN, Ren: LCCN"

    def test_get_warnings_with_generic_title(self):
        """Test extracting warnings including generic title detection"""
        with TemporaryDirectory() as temp_dir:
            # Create JSON file
            json_path = Path(temp_dir) / "empty.json"
            with open(json_path, "w", encoding="utf-8") as f:
                dump({"metadata": {}, "records": []}, f)

            exporter = CSVExporter(
                json_path=str(json_path), output_path="test.csv", single_file=True
            )

            # Test with generic title detected
            analysis = {"generic_title": {"detected": True}}
            warnings = exporter._get_warnings(analysis)
            assert warnings == "Generic title"

            # Test with data completeness issues
            analysis = {"data_completeness": ["Missing author", "Missing year"]}
            warnings = exporter._get_warnings(analysis)
            assert warnings == "Missing author, Missing year"

            # Test with both generic title and data issues
            analysis = {
                "generic_title": {"detected": True},
                "data_completeness": ["Missing author"],
            }
            warnings = exporter._get_warnings(analysis)
            assert warnings == "Generic title, Missing author"

            # Test with no warnings
            analysis = {"generic_title": {"detected": False}, "data_completeness": []}
            warnings = exporter._get_warnings(analysis)
            assert warnings == ""

    def test_get_warnings_with_non_string_items(self):
        """Test warnings extraction filters out non-string items"""
        with TemporaryDirectory() as temp_dir:
            # Create JSON file
            json_path = Path(temp_dir) / "empty.json"
            with open(json_path, "w", encoding="utf-8") as f:
                dump({"metadata": {}, "records": []}, f)

            exporter = CSVExporter(
                json_path=str(json_path), output_path="test.csv", single_file=True
            )

            # Test with mixed types in data_completeness
            analysis = {"data_completeness": ["Missing author", 123, None, "Missing year"]}
            warnings = exporter._get_warnings(analysis)
            assert warnings == "Missing author, Missing year"

    def test_write_header_with_country_code(self):
        """Test CSV header writing with country code column"""
        with TemporaryDirectory() as temp_dir:
            # Create empty JSON file
            json_path = Path(temp_dir) / "empty.json"
            with open(json_path, "w", encoding="utf-8") as f:
                dump({"metadata": {}, "records": []}, f)

            output_path = Path(temp_dir) / "test.csv"

            exporter = CSVExporter(
                json_path=str(json_path), output_path=str(output_path), single_file=True
            )

            # Test header writing with country code
            with open(output_path, "w", newline="", encoding="utf-8") as f:
                csv_writer = writer(f)
                exporter._write_header_with_country_code(csv_writer)

            # Read and verify header
            with open(output_path, "r", encoding="utf-8") as f:
                csv_reader = list(reader(f))
                header = csv_reader[0]

                assert "Country_Code" in header
                assert header.index("Country_Code") == header.index("Country") + 1

    def test_write_record_with_country_code(self):
        """Test writing record with country code extracted from status"""
        json_data = {
            "metadata": {},
            "records": [
                {
                    "marc": {
                        "id": "TEST001",
                        "original": {
                            "title": "Foreign Test",
                            "author_245c": "Foreign Author",
                            "year": "1950",
                        },
                        "metadata": {"country_code": "fra"},
                    },
                    "analysis": {"status": "FOREIGN_RENEWED_FRA"},
                    "matches": {
                        "registration": {"found": True, "id": "REG123"},
                        "renewal": {"found": True, "id": "REN456"},
                    },
                }
            ],
        }

        with TemporaryDirectory() as temp_dir:
            # Create JSON file
            json_path = Path(temp_dir) / "test_data.json"
            with open(json_path, "w", encoding="utf-8") as f:
                dump(json_data, f)

            output_path = Path(temp_dir) / "test.csv"

            exporter = CSVExporter(
                json_path=str(json_path), output_path=str(output_path), single_file=True
            )

            with open(output_path, "w", newline="", encoding="utf-8") as f:
                csv_writer = writer(f)
                exporter._write_header_with_country_code(csv_writer)
                exporter._write_record_with_country_code(csv_writer, exporter.records[0])

            # Read and verify
            with open(output_path, "r", encoding="utf-8") as f:
                csv_reader = list(reader(f))

                # Find Country_Code column index
                header = csv_reader[0]
                country_code_idx = header.index("Country_Code")

                # Check record data
                data_row = csv_reader[1]
                assert data_row[country_code_idx] == "FRA"
                assert "REG123" in data_row
                assert "REN456" in data_row

    def test_summary_csv_with_year_in_status(self):
        """Test summary CSV with year information in status"""
        json_data = {
            "metadata": {},
            "records": [
                {
                    "marc": {"id": "001", "original": {}, "metadata": {}},
                    "analysis": {"status": "US_PRE_1929"},
                },
                {
                    "marc": {"id": "002", "original": {}, "metadata": {}},
                    "analysis": {"status": "FOREIGN_PRE_1950_GBR"},
                },
            ],
        }

        with TemporaryDirectory() as temp_dir:
            # Create JSON file
            json_path = Path(temp_dir) / "test_data.json"
            with open(json_path, "w", encoding="utf-8") as f:
                dump(json_data, f)

            output_path = Path(temp_dir) / "test.csv"

            exporter = CSVExporter(
                json_path=str(json_path), output_path=str(output_path), single_file=False
            )

            exporter.export()

            summary_file = Path(temp_dir) / "test_csv" / "_summary.csv"
            with open(summary_file, "r", encoding="utf-8") as f:
                csv_reader = list(reader(f))

                # Check that year was substituted in explanation
                for row in csv_reader[1:]:
                    if "US_PRE_1929" in row[0]:
                        assert "1929" in row[3]  # Year should be in explanation
                    elif "FOREIGN_PRE_1950" in row[0]:
                        assert "1950" in row[3] or "GBR" in row[3]

    def test_summary_csv_unknown_status(self):
        """Test summary CSV with unrecognized status"""
        json_data = {
            "metadata": {},
            "records": [
                {
                    "marc": {"id": "001", "original": {}, "metadata": {}},
                    "analysis": {"status": "CUSTOM_UNRECOGNIZED_STATUS"},
                }
            ],
        }

        with TemporaryDirectory() as temp_dir:
            # Create JSON file
            json_path = Path(temp_dir) / "test_data.json"
            with open(json_path, "w", encoding="utf-8") as f:
                dump(json_data, f)

            output_path = Path(temp_dir) / "test.csv"

            exporter = CSVExporter(
                json_path=str(json_path), output_path=str(output_path), single_file=False
            )

            exporter.export()

            summary_file = Path(temp_dir) / "test_csv" / "_summary.csv"
            with open(summary_file, "r", encoding="utf-8") as f:
                csv_reader = list(reader(f))

                # Check for default explanation
                for row in csv_reader[1:]:
                    if "CUSTOM_UNRECOGNIZED_STATUS" in row[0]:
                        assert row[3] == "Status requires further analysis"

    def test_foreign_status_without_country_code(self):
        """Test foreign status handling when country code is not at end"""
        json_data = {
            "metadata": {},
            "records": [
                {
                    "marc": {"id": "001", "original": {}, "metadata": {}},
                    "analysis": {"status": "FOREIGN_SPECIAL_CASE"},
                }
            ],
        }

        with TemporaryDirectory() as temp_dir:
            # Create JSON file
            json_path = Path(temp_dir) / "test_data.json"
            with open(json_path, "w", encoding="utf-8") as f:
                dump(json_data, f)

            output_path = Path(temp_dir) / "test.csv"

            exporter = CSVExporter(
                json_path=str(json_path), output_path=str(output_path), single_file=False
            )

            exporter.export()

            # Should create a file with the full status name
            output_dir = Path(temp_dir) / "test_csv"
            assert (output_dir / "foreign_special_case.csv").exists()

    def test_us_status_edge_cases(self):
        """Test US status classification edge cases"""
        json_data = {
            "metadata": {},
            "records": [
                {
                    "marc": {"id": "001", "original": {}, "metadata": {}},
                    "analysis": {"status": "STATUS_WITH_US_IN_MIDDLE"},
                },
                {
                    "marc": {"id": "002", "original": {}, "metadata": {}},
                    "analysis": {"status": "UNRECOGNIZED_STATUS"},
                },
            ],
        }

        with TemporaryDirectory() as temp_dir:
            # Create JSON file
            json_path = Path(temp_dir) / "test_data.json"
            with open(json_path, "w", encoding="utf-8") as f:
                dump(json_data, f)

            output_path = Path(temp_dir) / "test.csv"

            exporter = CSVExporter(
                json_path=str(json_path), output_path=str(output_path), single_file=False
            )

            exporter.export()

            output_dir = Path(temp_dir) / "test_csv"

            # Both should be classified as US (default)
            assert (output_dir / "status_with_us_in_middle.csv").exists()
            assert (output_dir / "unrecognized_status.csv").exists()

    def test_empty_status_records(self):
        """Test handling records with empty status"""
        json_data = {
            "metadata": {},
            "records": [
                {"marc": {"id": "001", "original": {}, "metadata": {}}, "analysis": {"status": ""}}
            ],
        }

        with TemporaryDirectory() as temp_dir:
            # Create JSON file
            json_path = Path(temp_dir) / "test_data.json"
            with open(json_path, "w", encoding="utf-8") as f:
                dump(json_data, f)

            output_path = Path(temp_dir) / "test.csv"

            exporter = CSVExporter(
                json_path=str(json_path), output_path=str(output_path), single_file=False
            )

            exporter.export()

            # Empty status should still be processed
            output_dir = Path(temp_dir) / "test_csv"
            assert output_dir.exists()

    def test_foreign_status_grouping_edge_cases(self):
        """Test foreign status grouping with edge cases"""
        json_data = {
            "metadata": {},
            "records": [
                {
                    "marc": {"id": "001", "original": {}, "metadata": {}},
                    "analysis": {"status": "FOREIGN_RENEWED_12X"},  # Non-alpha country code
                },
                {
                    "marc": {"id": "002", "original": {}, "metadata": {}},
                    "analysis": {"status": "FOREIGN_AB"},  # Two parts only
                },
            ],
        }

        with TemporaryDirectory() as temp_dir:
            # Create JSON file
            json_path = Path(temp_dir) / "test_data.json"
            with open(json_path, "w", encoding="utf-8") as f:
                dump(json_data, f)

            output_path = Path(temp_dir) / "test.csv"

            exporter = CSVExporter(
                json_path=str(json_path), output_path=str(output_path), single_file=False
            )

            exporter.export()

            output_dir = Path(temp_dir) / "test_csv"

            # Non-alpha code not treated as country code
            assert (output_dir / "foreign_renewed_12x.csv").exists()
            # Two parts only
            assert (output_dir / "foreign_ab.csv").exists()

    def test_write_record_with_missing_ids(self):
        """Test writing record with missing registration/renewal IDs"""
        json_data = {
            "metadata": {},
            "records": [
                {
                    "marc": {
                        "id": "TEST001",
                        "original": {
                            "title": "Test",
                            "author_1xx": "Author",  # Testing author_1xx fallback
                            "year": "1950",
                        },
                        "metadata": {},
                    },
                    "analysis": {"status": "US_NO_MATCH"},
                    "matches": {
                        "registration": {
                            "found": True
                            # Missing 'id' field
                        },
                        "renewal": {"found": True, "id": 123},  # Non-string ID
                    },
                }
            ],
        }

        with TemporaryDirectory() as temp_dir:
            # Create JSON file
            json_path = Path(temp_dir) / "test_data.json"
            with open(json_path, "w", encoding="utf-8") as f:
                dump(json_data, f)

            output_path = Path(temp_dir) / "test.csv"

            exporter = CSVExporter(
                json_path=str(json_path), output_path=str(output_path), single_file=True
            )

            exporter.export()

            # Should not crash
            assert output_path.exists()

            with open(output_path, "r", encoding="utf-8") as f:
                csv_reader = list(reader(f))
                # Should have header + 1 row
                assert len(csv_reader) == 2
                # Check author from author_1xx was used
                assert "Author" in csv_reader[1]

    def test_write_record_with_country_code_edge_cases(self):
        """Test writing record with country code extraction edge cases"""
        json_data = {
            "metadata": {},
            "records": [
                {
                    "marc": {"id": "TEST001", "original": {}, "metadata": {}},
                    "analysis": {"status": "FOREIGN_RENEWED_12"},  # Not 3 chars
                    "matches": {},
                }
            ],
        }

        with TemporaryDirectory() as temp_dir:
            # Create JSON file
            json_path = Path(temp_dir) / "test_data.json"
            with open(json_path, "w", encoding="utf-8") as f:
                dump(json_data, f)

            output_path = Path(temp_dir) / "test.csv"

            exporter = CSVExporter(
                json_path=str(json_path), output_path=str(output_path), single_file=True
            )

            with open(output_path, "w", newline="", encoding="utf-8") as f:
                csv_writer = writer(f)
                exporter._write_header_with_country_code(csv_writer)
                exporter._write_record_with_country_code(csv_writer, exporter.records[0])

            # Read and verify
            with open(output_path, "r", encoding="utf-8") as f:
                csv_reader = list(reader(f))

                # Find Country_Code column index
                header = csv_reader[0]
                country_code_idx = header.index("Country_Code")

                # Check record data - country code should be empty
                data_row = csv_reader[1]
                assert data_row[country_code_idx] == ""

    def test_summary_csv_country_code_extraction(self):
        """Test summary CSV with foreign country code extraction"""
        json_data = {
            "metadata": {},
            "records": [
                {
                    "marc": {"id": "001", "original": {}, "metadata": {}},
                    "analysis": {"status": "FOREIGN_RENEWED_FRA"},
                }
            ],
        }

        with TemporaryDirectory() as temp_dir:
            # Create JSON file
            json_path = Path(temp_dir) / "test_data.json"
            with open(json_path, "w", encoding="utf-8") as f:
                dump(json_data, f)

            output_path = Path(temp_dir) / "test.csv"

            exporter = CSVExporter(
                json_path=str(json_path), output_path=str(output_path), single_file=False
            )

            exporter.export()

            summary_file = Path(temp_dir) / "test_csv" / "_summary.csv"
            with open(summary_file, "r", encoding="utf-8") as f:
                csv_reader = list(reader(f))

                # Check that country code was appended to explanation
                for row in csv_reader[1:]:
                    if "FOREIGN_RENEWED" in row[0]:
                        assert "(FRA)" in row[3]  # Country code in explanation
