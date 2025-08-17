# marc_pd_tool/application/processing/similarity_calculator.py

"""Similarity calculator for matching titles, authors, and publishers using appropriate algorithms"""

# Standard library imports

# Third party imports
from fuzzywuzzy import fuzz

# Local imports
from marc_pd_tool.application.processing.text_processing import LanguageProcessor
from marc_pd_tool.application.processing.text_processing import MultiLanguageStemmer
from marc_pd_tool.application.processing.text_processing import expand_abbreviations
from marc_pd_tool.infrastructure.config import ConfigLoader
from marc_pd_tool.shared.mixins.mixins import ConfigurableMixin


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

        # Initialize number normalizer (restored functionality)
        # Local imports
        from marc_pd_tool.application.processing.number_normalizer import (
            NumberNormalizer,
        )

        self.number_normalizer = NumberNormalizer(config)

        # Initialize custom stopword remover based on ground truth analysis
        # Local imports
        from marc_pd_tool.application.processing.custom_stopwords import (
            CustomStopwordRemover,
        )

        self.stopword_remover = CustomStopwordRemover()

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
        """Calculate title similarity using full normalization pipeline + fuzzy matching

        Pipeline:
        1. Unicode → ASCII (è → e)
        2. Lowercase
        3. Expand abbreviations (Co. → Company)
        4. Normalize numbers (XIV → 14, first → 1)
        5. Remove stopwords (language/field-specific)
        6. Stem words
        7. Apply fuzzy matching

        Args:
            marc_title: Title from MARC record (now minimally processed)
            copyright_title: Title from copyright/renewal record
            language: Language code for processing (eng, fre, ger, spa, ita)

        Returns:
            Similarity score from 0-100
        """
        if not marc_title and not copyright_title:
            return 100.0  # Both empty
        elif not marc_title or not copyright_title:
            return 0.0  # One empty, one not

        # Apply full normalization pipeline
        # Step 1: Unicode normalization and ASCII folding
        # Local imports
        from marc_pd_tool.shared.utils.text_utils import normalize_unicode

        marc_normalized = normalize_unicode(marc_title)
        copyright_normalized = normalize_unicode(copyright_title)

        # Step 2: Convert to lowercase
        marc_normalized = marc_normalized.lower()
        copyright_normalized = copyright_normalized.lower()

        # Step 3: Expand abbreviations if enabled
        if self.enable_abbreviation_expansion:
            marc_normalized = expand_abbreviations(marc_normalized)
            copyright_normalized = expand_abbreviations(copyright_normalized)

        # Step 4: Normalize numbers (Roman numerals, ordinals, word numbers)
        marc_normalized = self.number_normalizer.normalize_numbers(marc_normalized, language)
        copyright_normalized = self.number_normalizer.normalize_numbers(
            copyright_normalized, language
        )

        # Step 5: Use custom stopwords based on ground truth analysis
        # The analysis showed field and language-specific stopwords are critical
        marc_words = self.stopword_remover.remove_stopwords(marc_normalized, language, "title")
        copyright_words = self.stopword_remover.remove_stopwords(
            copyright_normalized, language, "title"
        )

        # Handle edge case: if both texts become empty after processing
        # (e.g., single character titles that get filtered out)
        if not marc_words and not copyright_words:
            # Both normalized to nothing - they're effectively identical
            # Check if original strings were identical to decide score
            if marc_title.strip().lower() == copyright_title.strip().lower():
                return 100.0
            else:
                return 0.0  # Different originals that both normalized to nothing
        elif not marc_words or not copyright_words:
            # One normalized to nothing, the other didn't
            return 0.0

        # Stem words if enabled
        if self.enable_stemming:
            marc_stemmed = self.stemmer.stem_words(marc_words, language)
            copyright_stemmed = self.stemmer.stem_words(copyright_words, language)
        else:
            marc_stemmed = marc_words
            copyright_stemmed = copyright_words

        # Reconstruct normalized text strings for fuzzy matching
        marc_normalized = " ".join(marc_stemmed)
        copyright_normalized = " ".join(copyright_stemmed)

        # Apply fuzzy matching on the fully normalized text
        # This is the correct approach based on the original implementation
        # The full normalization pipeline followed by fuzzy matching provides
        # the best balance of accuracy and consistency

        # Use token_sort_ratio as it handles word order variations well
        # This sorts the tokens alphabetically before comparison
        score = fuzz.token_sort_ratio(marc_normalized, copyright_normalized)

        return float(score)

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
        """Preprocess author name with full normalization pipeline

        Args:
            author: Raw author name (now minimally processed)
            language: Language code for processing (eng, fre, ger, spa, ita)

        Returns:
            Preprocessed author name ready for fuzzy matching
        """
        if not author:
            return ""

        # Apply full normalization pipeline
        # Unicode normalization and ASCII folding
        # Local imports
        from marc_pd_tool.shared.utils.text_utils import normalize_unicode

        normalized = normalize_unicode(author)

        # Convert to lowercase
        normalized = normalized.lower()

        # Expand abbreviations if enabled
        if self.enable_abbreviation_expansion:
            normalized = expand_abbreviations(normalized)

        # Normalize numbers (for cases like "John Smith III" → "John Smith 3")
        normalized = self.number_normalizer.normalize_numbers(normalized, language)

        # Use custom field-specific stopwords from ground truth analysis
        # The analysis showed minimal stopwords work best for authors
        words = self.stopword_remover.remove_stopwords(normalized, language, "author")

        return " ".join(words)

    def calculate_similarity(
        self, text1: str, text2: str, field_type: str, language: str = "eng"
    ) -> float:
        """Calculate similarity based on field type

        This is a generic method that delegates to field-specific methods.

        Args:
            text1: First text to compare
            text2: Second text to compare
            field_type: Type of field (title, author, or publisher)
            language: Language code for processing

        Returns:
            Similarity score from 0-100
        """
        if field_type == "title":
            return self.calculate_title_similarity(text1, text2, language)
        elif field_type == "author":
            return self.calculate_author_similarity(text1, text2, language)
        elif field_type == "publisher":
            # For publisher, text2 might be the full text for renewals
            return self.calculate_publisher_similarity(text1, text2, "", language)
        else:
            # Fallback to fuzzy matching
            if not text1 or not text2:
                return 0.0
            score = fuzz.ratio(text1.lower(), text2.lower())
            return float(score)

    def _preprocess_publisher(self, publisher: str, language: str = "eng") -> str:
        """Preprocess publisher name with full normalization pipeline

        Args:
            publisher: Raw publisher name (now minimally processed)
            language: Language code for processing (eng, fre, ger, spa, ita)

        Returns:
            Preprocessed publisher name ready for fuzzy matching
        """
        if not publisher:
            return ""

        # Apply full normalization pipeline
        # Unicode normalization and ASCII folding
        # Local imports
        from marc_pd_tool.shared.utils.text_utils import normalize_unicode

        normalized = normalize_unicode(publisher)

        # Convert to lowercase
        normalized = normalized.lower()

        # Expand abbreviations if enabled
        if self.enable_abbreviation_expansion:
            normalized = expand_abbreviations(normalized)

        # Normalize numbers (for edition numbers, years in publisher names)
        normalized = self.number_normalizer.normalize_numbers(normalized, language)

        # Use custom field-specific stopwords from ground truth analysis
        # The analysis showed very minimal stopwords for publishers
        words = self.stopword_remover.remove_stopwords(normalized, language, "publisher")

        return " ".join(words)
