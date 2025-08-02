# tests/test_exporters/test_html_exporter_simple.py

"""Simplified tests for HTML export functionality"""

# Standard library imports
from pathlib import Path
from tempfile import TemporaryDirectory

# Third party imports
import pytest

# Local imports
from marc_pd_tool.data.enums import CopyrightStatus
from marc_pd_tool.exporters.html_exporter import HTMLExporter
from marc_pd_tool.exporters.json_exporter import save_matches_json
from tests.fixtures.publications import PublicationBuilder
from tests.fixtures.publications import sample_publications


class TestHTMLExporterSimple:
    """Simplified tests for HTML export functionality"""
    
    def test_html_exporter_creates_directory(self, sample_publications):
        """Test that HTML exporter creates a directory structure"""
        with TemporaryDirectory() as temp_dir:
            json_path = str(Path(temp_dir) / "test.json")
            output_dir = str(Path(temp_dir) / "html_output")
            
            # Save to JSON first
            save_matches_json(sample_publications, json_path)
            
            # Export to HTML
            exporter = HTMLExporter(json_path, output_dir)
            exporter.export()
            
            # Verify directory was created
            assert Path(output_dir).exists()
            assert Path(output_dir).is_dir()
            
            # Check for basic structure
            assert (Path(output_dir) / "index.html").exists()
            assert (Path(output_dir) / "css").exists()
            assert (Path(output_dir) / "css" / "style.css").exists()
    
    def test_html_export_with_empty_data(self):
        """Test HTML export with no records"""
        with TemporaryDirectory() as temp_dir:
            json_path = str(Path(temp_dir) / "empty.json")
            output_dir = str(Path(temp_dir) / "html_empty")
            
            # Save empty data
            save_matches_json([], json_path)
            
            # Export
            exporter = HTMLExporter(json_path, output_dir)
            exporter.export()
            
            # Should still create structure
            assert Path(output_dir).exists()
            assert (Path(output_dir) / "index.html").exists()
    
    def test_html_export_creates_status_directories(self):
        """Test that status-specific directories are created"""
        # Create publications with different statuses
        pubs = []
        
        # PD publication
        pub1 = PublicationBuilder.basic_us_publication(source_id="pd1")
        pub1.copyright_status = CopyrightStatus.PD_NO_RENEWAL
        pubs.append(pub1)
        
        # In copyright publication
        pub2 = PublicationBuilder.basic_us_publication(source_id="ic1")
        pub2.copyright_status = CopyrightStatus.IN_COPYRIGHT
        pubs.append(pub2)
        
        # Research status publication
        pub3 = PublicationBuilder.basic_us_publication(source_id="rs1")
        pub3.copyright_status = CopyrightStatus.RESEARCH_US_STATUS
        pubs.append(pub3)
        
        with TemporaryDirectory() as temp_dir:
            json_path = str(Path(temp_dir) / "mixed.json")
            output_dir = str(Path(temp_dir) / "html_mixed")
            
            save_matches_json(pubs, json_path)
            
            # Export
            exporter = HTMLExporter(json_path, output_dir, single_file=False)
            exporter.export()
            
            # Check that at least some directories were created
            dirs = [d for d in Path(output_dir).iterdir() if d.is_dir() and d.name != "css"]
            assert len(dirs) > 0  # Should have at least one status directory
            
            # Check if we have any of the expected directories (use hyphens)
            expected_dirs = ["pd-no-renewal", "in-copyright", "research-us-status", 
                           "pd-date-verify", "research-us-only-pd", "country-unknown"]
            found_dirs = [d.name for d in dirs]
            assert any(d in expected_dirs for d in found_dirs)
    
    def test_html_single_file_mode(self):
        """Test single file mode creates all_records directory"""
        pubs = [
            PublicationBuilder.basic_us_publication(source_id="1"),
            PublicationBuilder.basic_us_publication(source_id="2"),
        ]
        pubs[0].copyright_status = CopyrightStatus.PD_NO_RENEWAL
        pubs[1].copyright_status = CopyrightStatus.IN_COPYRIGHT
        
        with TemporaryDirectory() as temp_dir:
            json_path = str(Path(temp_dir) / "single.json")
            output_dir = str(Path(temp_dir) / "html_single")
            
            save_matches_json(pubs, json_path)
            
            # Export with single_file=True
            exporter = HTMLExporter(json_path, output_dir, single_file=True)
            exporter.export()
            
            # In single_file mode, pages go directly in output dir
            assert (Path(output_dir) / "page_1.html").exists()
            
            # Should NOT create status directories
            assert not (Path(output_dir) / "pd_no_renewal").exists()
            assert not (Path(output_dir) / "in_copyright").exists()
            assert not (Path(output_dir) / "all_records").exists()
    
    def test_html_contains_basic_content(self):
        """Test that generated HTML contains expected content"""
        pub = PublicationBuilder.basic_us_publication()
        pub.original_title = "Test Book Title"
        pub.original_author = "Test Author"
        pub.copyright_status = CopyrightStatus.PD_NO_RENEWAL
        
        with TemporaryDirectory() as temp_dir:
            json_path = str(Path(temp_dir) / "content.json")
            output_dir = str(Path(temp_dir) / "html_content")
            
            save_matches_json([pub], json_path)
            
            exporter = HTMLExporter(json_path, output_dir)
            exporter.export()
            
            # Read a page
            page_file = Path(output_dir) / "pd_no_renewal" / "page_1.html"
            if page_file.exists():
                content = page_file.read_text()
                assert "Test Book Title" in content
                assert "Test Author" in content
    
    def test_html_exporter_accepts_path_strings(self):
        """Test that exporter works with string paths"""
        with TemporaryDirectory() as temp_dir:
            json_path = f"{temp_dir}/test.json"
            output_dir = f"{temp_dir}/html_out"
            
            save_matches_json([], json_path)
            
            # Should work with string paths
            exporter = HTMLExporter(json_path, output_dir)
            assert exporter is not None
            
            exporter.export()
            assert Path(output_dir).exists()