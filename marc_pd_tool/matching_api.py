"""Abstract base classes for matching and scoring API interface"""

# Standard library imports
from abc import ABC
from abc import abstractmethod
from dataclasses import dataclass
from typing import Dict
from typing import List
from typing import Optional

# Local imports
from marc_pd_tool.generic_title_detector import GenericTitleDetector
from marc_pd_tool.publication import Publication


@dataclass
class SimilarityScores:
    """Container for similarity scores between publications"""

    title: float
    author: float
    publisher: float
    combined: float


class SimilarityCalculator(ABC):
    """Abstract base class for calculating similarity between text fields"""

    @abstractmethod
    def calculate_title_similarity(self, marc_title: str, copyright_title: str) -> float:
        """Calculate similarity score between titles (0-100)

        Args:
            marc_title: Normalized title from MARC record
            copyright_title: Title from copyright/renewal record

        Returns:
            Similarity score from 0-100
        """
        pass

    @abstractmethod
    def calculate_author_similarity(self, marc_author: str, copyright_author: str) -> float:
        """Calculate similarity score between authors (0-100)

        Args:
            marc_author: Author name from MARC record
            copyright_author: Author name from copyright/renewal record

        Returns:
            Similarity score from 0-100
        """
        pass

    @abstractmethod
    def calculate_publisher_similarity(
        self, marc_publisher: str, copyright_publisher: str, copyright_full_text: str = ""
    ) -> float:
        """Calculate similarity score between publishers (0-100)

        Args:
            marc_publisher: Publisher from MARC record
            copyright_publisher: Publisher from copyright/renewal record
            copyright_full_text: Full text from renewal record (for fuzzy matching)

        Returns:
            Similarity score from 0-100
        """
        pass


class ScoreCombiner(ABC):
    """Abstract base class for combining individual similarity scores"""

    @abstractmethod
    def combine_scores(
        self,
        title_score: float,
        author_score: float,
        publisher_score: float,
        marc_pub: Publication,
        copyright_pub: Publication,
        generic_detector: Optional[GenericTitleDetector] = None,
    ) -> float:
        """Combine individual scores into final similarity score (0-100)

        Args:
            title_score: Title similarity score (0-100)
            author_score: Author similarity score (0-100)
            publisher_score: Publisher similarity score (0-100)
            marc_pub: MARC publication record
            copyright_pub: Copyright/renewal publication record
            generic_detector: Optional generic title detector for dynamic weighting

        Returns:
            Combined similarity score from 0-100
        """
        pass


class MatchingEngine(ABC):
    """Abstract base class for the complete matching process"""

    @abstractmethod
    def find_best_match(
        self,
        marc_pub: Publication,
        copyright_pubs: List[Publication],
        title_threshold: int,
        author_threshold: int,
        year_tolerance: int,
        publisher_threshold: int,
        early_exit_title: int,
        early_exit_author: int,
        generic_detector: Optional[GenericTitleDetector] = None,
    ) -> Optional[Dict]:
        """Find the best matching copyright publication

        Args:
            marc_pub: MARC publication to match
            copyright_pubs: List of copyright/renewal publications to search
            title_threshold: Minimum title similarity score (0-100)
            author_threshold: Minimum author similarity score (0-100)
            year_tolerance: Maximum year difference for matching
            publisher_threshold: Minimum publisher similarity score (0-100)
            early_exit_title: Title score for early termination (0-100)
            early_exit_author: Author score for early termination (0-100)
            generic_detector: Optional generic title detector

        Returns:
            Dictionary with match information or None if no match found
        """
        pass
