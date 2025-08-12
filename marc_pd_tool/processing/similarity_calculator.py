# marc_pd_tool/processing/similarity_calculator.py

"""Similarity calculator for matching titles, authors, and publishers using appropriate algorithms"""

# Standard library imports

# Third party imports
from fuzzywuzzy import fuzz

# Local imports
from marc_pd_tool.infrastructure.config_loader import ConfigLoader
from marc_pd_tool.processing.text_processing import LanguageProcessor
from marc_pd_tool.processing.text_processing import MultiLanguageStemmer
from marc_pd_tool.processing.text_processing import expand_abbreviations
from marc_pd_tool.utils.mixins import ConfigurableMixin


class SimilarityCalculator(ConfigurableMixin):
    """Calculates similarity between MARC and copyright/renewal records using field-specific algorithms"""

    def __init__(self, config: ConfigLoader | None = None) -> None:
        """Initialize with language processing components

        Args:
            config: Optional configuration loader
        """
        self.config = self._init_config(config)

        # Initialize language processing components
        self.lang_processor = LanguageProcessor()
        self.stemmer = MultiLanguageStemmer()

        # Get default language from config
        config_dict = self.config.config

        # Get configuration values using safe navigation
        self.default_language = str(
            self._get_config_value(config_dict, "matching.word_based.default_language", "eng")
        )
        self.enable_stemming = bool(
            self._get_config_value(config_dict, "matching.word_based.enable_stemming", True)
        )
        self.enable_abbreviation_expansion = bool(
            self._get_config_value(
                config_dict, "matching.word_based.enable_abbreviation_expansion", True
            )
        )

    def calculate_title_similarity(
        self, marc_title: str, copyright_title: str, language: str = "eng"
    ) -> float:
        """Calculate title similarity using word-based matching with stemming and stopwords

        Args:
            marc_title: Normalized title from MARC record
            copyright_title: Title from copyright/renewal record
            language: Language code for processing (eng, fre, ger, spa, ita)

        Returns:
            Similarity score from 0-100
        """
        if not marc_title and not copyright_title:
            return 100.0  # Both empty
        elif not marc_title or not copyright_title:
            return 0.0  # One empty, one not

        # Expand abbreviations if enabled
        if self.enable_abbreviation_expansion:
            marc_expanded = expand_abbreviations(marc_title)
            copyright_expanded = expand_abbreviations(copyright_title)
        else:
            marc_expanded = marc_title
            copyright_expanded = copyright_title

        # Check if we should skip stopword removal for short titles
        # Count words in both titles
        marc_word_count = len(marc_expanded.split())
        copyright_word_count = len(copyright_expanded.split())
        shorter_title_word_count = min(marc_word_count, copyright_word_count)

        # If the shorter title has 6 or fewer words, keep stopwords for both
        if shorter_title_word_count <= 6:
            # Just split into words without removing stopwords, but filter very short words
            marc_words = [word for word in marc_expanded.lower().split() if len(word) >= 2]
            copyright_words = [
                word for word in copyright_expanded.lower().split() if len(word) >= 2
            ]
        else:
            # Remove stopwords using publication language
            marc_words = self.lang_processor.remove_stopwords(marc_expanded, language)
            copyright_words = self.lang_processor.remove_stopwords(copyright_expanded, language)

        # Stem words if enabled
        if self.enable_stemming:
            marc_stems = set(self.stemmer.stem_words(marc_words, language))
            copyright_stems = set(self.stemmer.stem_words(copyright_words, language))
        else:
            marc_stems = set(marc_words)
            copyright_stems = set(copyright_words)

        # Calculate word overlap similarity using Jaccard index
        if not marc_stems and not copyright_stems:
            return 0.0  # Both empty after processing - no meaningful comparison possible
        elif not marc_stems or not copyright_stems:
            return 0.0  # One empty, one not

        intersection = marc_stems & copyright_stems
        union = marc_stems | copyright_stems

        # Standard Jaccard similarity
        jaccard_score = (len(intersection) / len(union)) * 100.0

        # Check for partial title matching
        # If one title is significantly shorter and all its words are in the longer title,
        # it's likely a truncated version
        if len(marc_stems) != len(copyright_stems):
            shorter_set = marc_stems if len(marc_stems) < len(copyright_stems) else copyright_stems
            longer_set = copyright_stems if len(marc_stems) < len(copyright_stems) else marc_stems

            # If the shorter title has at least 2 words and all are contained in the longer
            if len(shorter_set) >= 2 and shorter_set.issubset(longer_set):
                # When all words from the shorter title are in the longer one,
                # it's likely a truncated version or the longer has additional info
                # Give a bonus based on how complete the match is

                # Base score: How much of the shorter title is matched (always 100% here)
                # But scale it by how significant the shorter title is (at least 2 words)
                if len(shorter_set) >= 3:
                    # 3+ word matches are very likely the same work
                    containment_bonus = 75.0
                else:
                    # 2 word matches get a smaller bonus
                    containment_bonus = 60.0

                # Return the better of Jaccard or the containment bonus
                return max(jaccard_score, containment_bonus)

        return jaccard_score

    def calculate_author_similarity(
        self, marc_author: str, copyright_author: str, language: str = "eng"
    ) -> float:
        """Calculate author similarity using enhanced fuzzy matching with preprocessing

        Args:
            marc_author: Author name from MARC record
            copyright_author: Author name from copyright/renewal record
            language: Language code for processing (eng, fre, ger, spa, ita)

        Returns:
            Similarity score from 0-100
        """
        if not marc_author or not copyright_author:
            return 0.0

        # Preprocess both author strings
        marc_processed = self._preprocess_author(marc_author, language)
        copyright_processed = self._preprocess_author(copyright_author, language)

        # Use fuzzy matching on preprocessed text
        score = fuzz.ratio(marc_processed, copyright_processed)
        return float(score)

    def calculate_publisher_similarity(
        self,
        marc_publisher: str,
        copyright_publisher: str,
        copyright_full_text: str = "",
        language: str = "eng",
    ) -> float:
        """Calculate publisher similarity using enhanced fuzzy matching with preprocessing

        Args:
            marc_publisher: Publisher from MARC record
            copyright_publisher: Publisher from copyright/renewal record
            copyright_full_text: Full text from renewal record (for fuzzy matching)
            language: Language code for processing (eng, fre, ger, spa, ita)

        Returns:
            Similarity score from 0-100
        """
        if not marc_publisher:
            return 0.0

        # Preprocess MARC publisher
        marc_processed = self._preprocess_publisher(marc_publisher, language)

        if copyright_full_text:
            # For renewals: fuzzy match against full text
            score = fuzz.partial_ratio(marc_processed, copyright_full_text)
            return float(score)
        elif copyright_publisher:
            # For registrations: direct publisher comparison with preprocessing
            copyright_processed = self._preprocess_publisher(copyright_publisher, language)
            score = fuzz.ratio(marc_processed, copyright_processed)
            return float(score)
        else:
            return 0.0

    def _preprocess_author(self, author: str, language: str = "eng") -> str:
        """Preprocess author name for improved matching

        Args:
            author: Raw author name
            language: Language code for processing (eng, fre, ger, spa, ita)

        Returns:
            Preprocessed author name
        """
        if not author:
            return ""

        # Expand abbreviations if enabled
        if self.enable_abbreviation_expansion:
            expanded = expand_abbreviations(author)
        else:
            expanded = author

        # Remove common author stopwords and qualifiers
        author_stopwords = self.config.author_stopwords
        words = [word for word in expanded.lower().split() if word not in author_stopwords]

        return " ".join(words)

    def _preprocess_publisher(self, publisher: str, language: str = "eng") -> str:
        """Preprocess publisher name for improved matching

        Args:
            publisher: Raw publisher name
            language: Language code for processing (eng, fre, ger, spa, ita)

        Returns:
            Preprocessed publisher name
        """
        if not publisher:
            return ""

        # Expand abbreviations if enabled
        if self.enable_abbreviation_expansion:
            expanded = expand_abbreviations(publisher)
        else:
            expanded = publisher

        # Remove common publisher stopwords
        publisher_stopwords = self.config.publisher_stopwords
        words = [word for word in expanded.lower().split() if word not in publisher_stopwords]

        return " ".join(words)
