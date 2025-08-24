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
            return 0.0  # Both empty - should not match
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

        # Check for title containment first
        containment_score = self._check_title_containment(
            marc_normalized, copyright_normalized, marc_title, copyright_title
        )
        if containment_score > 0:
            return containment_score

        # Phase 4B: Smarter Fuzzy Matching
        # Apply stricter matching to reduce false positives
        score = self._smart_fuzzy_match(
            marc_normalized,
            copyright_normalized,
            marc_stemmed,
            copyright_stemmed,
            marc_title,
            copyright_title,
        )

        return float(score)

    def _check_title_containment(
        self,
        marc_normalized: str,
        copyright_normalized: str,
        marc_original: str,
        copyright_original: str,
    ) -> float:
        """Check if one title contains the other (subtitle/series detection)

        This handles cases like:
        - "Tax Guide" vs "Tax Guide 1934"
        - "Annual Report" vs "Annual Report of the Commissioner"
        - Series with subtitles

        Args:
            marc_normalized: Normalized MARC title
            copyright_normalized: Normalized copyright title
            marc_original: Original MARC title (for length checking)
            copyright_original: Original copyright title

        Returns:
            Score (0 if no containment, 85-95 if contained)
        """
        # Don't apply containment boost for very short titles (prone to false positives)
        min_orig_len = min(len(marc_original), len(copyright_original))
        if min_orig_len < 8:  # Lowered from 10 to handle "Tax Guide" type cases
            return 0.0

        # Check both directions for containment
        marc_in_copyright = marc_normalized in copyright_normalized
        copyright_in_marc = copyright_normalized in marc_normalized

        if not (marc_in_copyright or copyright_in_marc):
            return 0.0

        # Calculate how much of the shorter string is contained
        if marc_in_copyright:
            shorter = marc_normalized
            longer = copyright_normalized
        else:
            shorter = copyright_normalized
            longer = marc_normalized

        # Require the contained portion to be significant
        # Both absolute length and word count matter
        shorter_words = shorter.split()
        if len(shorter) < 5 or len(shorter_words) < 2:  # Too short after normalization
            return 0.0

        # Calculate containment ratio
        containment_ratio = len(shorter) / len(longer)

        # Full containment (one is substring of other)
        if containment_ratio > 0.3:  # At least 30% of the longer title
            # Check if it's at the beginning (likely a base title + subtitle)
            if longer.startswith(shorter):
                # Strong match - likely base title with additional info
                # Scale score based on containment ratio: 85-95
                # Use a minimum of 85 for significant containment at start
                return max(85.0, 80.0 + (containment_ratio * 20.0))
            else:
                # Contained but not at start - be more conservative
                return 75.0 + (containment_ratio * 15.0)

        return 0.0

    def _smart_fuzzy_match(
        self,
        marc_normalized: str,
        copyright_normalized: str,
        marc_words: list[str],
        copyright_words: list[str],
        marc_original: str,
        copyright_original: str,
    ) -> float:
        """Smarter fuzzy matching that reduces false positives

        Phase 4B implementation to handle issues like:
        - "War over England" matching "English literature" at 55%
        - Common words inflating scores
        - Similar word stems creating false matches

        Args:
            marc_normalized: Normalized MARC title string
            copyright_normalized: Normalized copyright title string
            marc_words: List of words after stopword removal and stemming
            copyright_words: List of words after stopword removal and stemming
            marc_original: Original MARC title
            copyright_original: Original copyright title

        Returns:
            Similarity score (0-100)
        """
        # Count distinctive words (after stopword removal)
        marc_distinctive = set(marc_words)
        copyright_distinctive = set(copyright_words)

        # If either has very few distinctive words, be stricter
        min_distinctive = min(len(marc_distinctive), len(copyright_distinctive))

        if min_distinctive == 0:
            # No distinctive words after filtering - likely all stopwords
            # Check if originals are identical
            if marc_original.strip().lower() == copyright_original.strip().lower():
                return 100.0
            return 0.0

        # Check for identical normalized strings first
        if marc_normalized == copyright_normalized:
            # Identical after normalization
            return 100.0

        # Calculate word overlap
        word_overlap = marc_distinctive.intersection(copyright_distinctive)
        overlap_count = len(word_overlap)

        # Check for perfect word set match (handles reordering)
        if marc_distinctive == copyright_distinctive and len(marc_distinctive) > 0:
            # Same words, possibly different order
            return float(fuzz.token_sort_ratio(marc_normalized, copyright_normalized))

        # Minimum distinctive word requirement
        # If only one word overlaps regardless of total words, be more careful
        if overlap_count <= 1:
            if overlap_count == 1:
                # Only one distinctive word matches
                # But check if titles are very short (might be legitimate)
                if min_distinctive <= 2:
                    # Very short titles - single word overlap might be significant
                    # Like "Othello" vs "Othello illustrated"
                    base = fuzz.token_sort_ratio(marc_normalized, copyright_normalized)
                    return float(min(60.0, base * 0.8))  # Allow up to 60 for short titles
                else:
                    # Longer titles with only one word overlap - more suspicious
                    # This handles cases like "Annual Report" vs "Annual Review"
                    return float(
                        min(
                            40.0, fuzz.token_sort_ratio(marc_normalized, copyright_normalized) * 0.6
                        )
                    )
            else:
                # No overlap at all
                return 0.0

        # Calculate overlap ratio
        max_possible = max(len(marc_distinctive), len(copyright_distinctive))
        overlap_ratio = overlap_count / max_possible if max_possible > 0 else 0

        # Get base fuzzy score
        base_score = fuzz.token_sort_ratio(marc_normalized, copyright_normalized)

        # Apply penalties based on word overlap
        if overlap_ratio < 0.6:
            # Less than 60% words overlap - apply penalty
            # Stricter than before (was 0.5)
            adjusted_score = base_score * (0.4 + overlap_ratio)
        else:
            # Good word overlap
            adjusted_score = base_score

        # Additional penalty for very short titles after normalization
        # Short titles are prone to false positives
        total_words = len(marc_words) + len(copyright_words)
        if total_words <= 4:  # Very short
            adjusted_score *= 0.8

        # Check for stem-only matches (helps with England/English problem)
        # If the original words are quite different but stems match,
        # apply a penalty
        if adjusted_score > 60:
            # Do a quick check on original (non-stemmed) similarity
            original_score = fuzz.token_sort_ratio(
                marc_original.lower(), copyright_original.lower()
            )
            if original_score < adjusted_score * 0.7:
                # Stems match better than originals - likely false positive
                adjusted_score *= 0.7

        return float(min(100.0, max(0.0, adjusted_score)))

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

        # Use token_set_ratio instead of ratio for better name matching
        # This handles "Smith, John" vs "John Smith" and similar variations
        score = fuzz.token_set_ratio(marc_processed, copyright_processed)

        # Apply noise floor - scores below 60% are likely false matches
        # Testing showed unrelated names score 25-50% with token_set_ratio
        if score < 60:
            return 0.0

        # Optional: Penalize when word counts differ significantly
        # This helps distinguish corporate vs personal names
        marc_words = len(marc_processed.split())
        copyright_words = len(copyright_processed.split())
        if abs(marc_words - copyright_words) > 3:
            score = score * 0.7

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
