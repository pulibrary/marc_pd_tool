# tests/test_utils/test_publisher_utils.py

"""Tests for publisher text processing utilities"""

# Third party imports
import pytest

# Local imports
from marc_pd_tool.utils.publisher_utils import clean_publisher_suffix
from marc_pd_tool.utils.publisher_utils import extract_publisher_candidates


class TestExtractPublisherCandidates:
    """Test the extract_publisher_candidates function"""
    
    def test_empty_input(self):
        """Test with empty or None input"""
        assert extract_publisher_candidates("") == []
        assert extract_publisher_candidates(None) == []
        assert extract_publisher_candidates("   ") == []
    
    def test_single_publisher_mention(self):
        """Test extraction when publisher is explicitly mentioned"""
        text = "Published by Random House in 1995"
        candidates = extract_publisher_candidates(text)
        assert len(candidates) == 1
        assert "Published by Random House in 1995" in candidates
        
        text = "New York: Oxford University Press, 2020"
        candidates = extract_publisher_candidates(text)
        assert any("Oxford University Press" in c for c in candidates)
    
    def test_multiple_publishers(self):
        """Test extraction with multiple publisher candidates"""
        text = "Published by Harper & Row; distributed by Simon & Schuster Publications"
        candidates = extract_publisher_candidates(text)
        assert len(candidates) >= 2
        assert any("Harper & Row" in c for c in candidates)
        assert any("Simon & Schuster Publications" in c for c in candidates)
    
    def test_publisher_indicators(self):
        """Test various publisher indicator words"""
        # Test cases where the function finds publisher indicators
        test_cases = [
            "McGraw-Hill Publishing Company",
            "University of Chicago Press", 
            "MIT Press imprint",
            "First edition by Wiley",
        ]
        
        for text in test_cases:
            candidates = extract_publisher_candidates(text)
            assert len(candidates) > 0, f"No candidates found for '{text}'"
            # The function should find the text with publisher indicators
            assert text in candidates
            
        # Test case with period delimiter
        candidates = extract_publisher_candidates("Penguin Books Ltd.")
        assert len(candidates) > 0
        assert "Penguin Books Ltd" in candidates  # Without trailing period
        
        # Test case with comma delimiter
        candidates = extract_publisher_candidates("Random House, publisher")
        assert len(candidates) > 0
        assert "publisher" in candidates  # After comma split
    
    def test_delimiter_splitting(self):
        """Test splitting on various delimiters"""
        text = "Author: John Doe; Publisher: Acme Press; Year: 2020"
        candidates = extract_publisher_candidates(text)
        assert any("Acme Press" in c for c in candidates)
        
        text = "New York. Random House. 1st Edition"
        candidates = extract_publisher_candidates(text)
        assert len(candidates) >= 1
    
    def test_heuristic_publisher_detection(self):
        """Test heuristic detection of publishers without explicit indicators"""
        # Capitalized phrases that might be publishers
        text = "Copyright 2020 Springer Nature Switzerland AG"
        candidates = extract_publisher_candidates(text)
        assert len(candidates) > 0
        
        # Should skip common non-publisher starts
        text = "The book was great. By John Smith. At the library"
        candidates = extract_publisher_candidates(text)
        # These shouldn't be detected as publishers
        assert not any("The book was great" in c for c in candidates)
        assert not any("By John Smith" in c for c in candidates)
    
    def test_short_segments_ignored(self):
        """Test that very short segments are ignored"""
        text = "NY; CA; Published by ABC Press; UK"
        candidates = extract_publisher_candidates(text)
        assert "NY" not in candidates
        assert "CA" not in candidates
        assert "UK" not in candidates
        assert any("ABC Press" in c for c in candidates)
    
    def test_mixed_case_indicators(self):
        """Test case-insensitive matching of indicators"""
        text = "PUBLISHED BY MACMILLAN"
        candidates = extract_publisher_candidates(text)
        assert len(candidates) == 1
        assert "PUBLISHED BY MACMILLAN" in candidates
    
    def test_complex_text(self):
        """Test with complex bibliographic text"""
        text = """First published in Great Britain by Bloomsbury Publishing Plc.
        This edition published 2020. Originally published by Scholastic Press."""
        candidates = extract_publisher_candidates(text)
        assert len(candidates) >= 2
        assert any("Bloomsbury Publishing" in c for c in candidates)
        assert any("Scholastic Press" in c for c in candidates)


class TestCleanPublisherSuffix:
    """Test the clean_publisher_suffix function"""
    
    def test_empty_input(self):
        """Test with empty or None input"""
        assert clean_publisher_suffix("") == ""
        assert clean_publisher_suffix(None) == ""
        assert clean_publisher_suffix("   ") == ""
    
    def test_remove_trailing_punctuation(self):
        """Test removal of trailing punctuation"""
        assert clean_publisher_suffix("Random House,") == "Random House"
        assert clean_publisher_suffix("Penguin Books.") == "Penguin Books"
        assert clean_publisher_suffix("HarperCollins;") == "HarperCollins"
        assert clean_publisher_suffix("MIT Press:") == "MIT Press"
        assert clean_publisher_suffix("Wiley & Sons...") == "Wiley & Sons"
    
    def test_remove_parenthetical_content(self):
        """Test removal of trailing parenthetical content"""
        assert clean_publisher_suffix("Random House (NY)") == "Random House"
        assert clean_publisher_suffix("Oxford University Press (2020)") == "Oxford University Press"
        assert clean_publisher_suffix("Springer (Berlin/Heidelberg)") == "Springer"
        assert clean_publisher_suffix("Academic Press (Elsevier)") == "Academic Press"
    
    def test_remove_subsidiary_phrases(self):
        """Test removal of subsidiary/successor phrases"""
        assert clean_publisher_suffix("Harper, successor to Harper & Row") == "Harper"
        assert clean_publisher_suffix("Penguin, formerly Viking") == "Penguin"
        assert clean_publisher_suffix("Crown, division of Random House") == "Crown"
        assert clean_publisher_suffix("Tor, imprint of Macmillan") == "Tor"
        assert clean_publisher_suffix("Knopf, subsidiary of PRH") == "Knopf"
    
    def test_case_insensitive_removal(self):
        """Test case-insensitive removal of phrases"""
        assert clean_publisher_suffix("Harper, SUCCESSOR TO old company") == "Harper"
        assert clean_publisher_suffix("Penguin, Formerly Viking") == "Penguin"
        assert clean_publisher_suffix("Crown, Division Of Random House") == "Crown"
    
    def test_combined_cleaning(self):
        """Test multiple cleaning operations"""
        assert clean_publisher_suffix("Random House, Inc. (New York)") == "Random House, Inc."
        assert clean_publisher_suffix("McGraw-Hill, division of S&P Global.") == "McGraw-Hill"
        assert clean_publisher_suffix("Wiley & Sons, formerly John Wiley (USA);") == "Wiley & Sons"
    
    def test_preserve_internal_elements(self):
        """Test that internal punctuation and parentheses are preserved"""
        assert clean_publisher_suffix("O'Reilly Media") == "O'Reilly Media"
        assert clean_publisher_suffix("McGraw-Hill") == "McGraw-Hill"
        assert clean_publisher_suffix("Simon & Schuster") == "Simon & Schuster"
        assert clean_publisher_suffix("St. Martin's Press") == "St. Martin's Press"
    
    def test_no_changes_needed(self):
        """Test with clean publisher names that need no changes"""
        assert clean_publisher_suffix("Random House") == "Random House"
        assert clean_publisher_suffix("Penguin Books") == "Penguin Books"
        assert clean_publisher_suffix("Oxford University Press") == "Oxford University Press"