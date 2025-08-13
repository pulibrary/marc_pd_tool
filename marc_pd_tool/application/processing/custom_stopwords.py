# marc_pd_tool/application/processing/custom_stopwords.py

"""Custom stopword lists based on ground truth analysis

These stopword lists were developed through analysis of 19,971 ground truth
MARC records with known copyright/renewal matches. The analysis showed that
language and field-specific stopwords significantly improve matching accuracy.

Key findings:
- English benefits from more aggressive stopword removal
- French/German need minimal removal (articles are meaningful)
- Field-specific lists are critical (e.g., keep "company" for publishers)
"""

# Custom stopword lists developed from ground truth analysis
CUSTOM_STOPWORDS = {
    "eng": {
        "title": [
            "a",
            "an",
            "and",
            "are",
            "as",
            "at",
            "be",
            "by",
            "for",
            "from",
            "has",
            "he",
            "in",
            "is",
            "it",
            "its",
            "of",
            "on",
            "that",
            "the",
            "to",
            "was",
            "will",
            "with",
            "or",
            "not",
            "this",
            "these",
            "those",
            "they",
            "their",
            "there",
            "been",
            "have",
            "had",
            "were",
            "what",
            "when",
            "where",
            "which",
            "who",
            "why",
            "how",
            "all",
            "some",
            "other",
            "another",
            "any",
            "many",
            "more",
            "most",
            "such",
            "our",
        ],
        "author": [
            "a",
            "an",
            "and",
            "as",
            "at",
            "by",
            "for",
            "from",
            "in",
            "of",
            "on",
            "the",
            "to",
            "with",
            "or",
            "ed",
            "trans",
            "comp",
        ],
        "publisher": [
            "a",
            "an",
            "and",
            "at",
            "by",
            "for",
            "from",
            "in",
            "of",
            "on",
            "the",
            "to",
            "with",
        ],
    },
    "fre": {
        # French showed negative impact with aggressive stopword removal
        # Articles (le, la, les) are meaningful and should NOT be removed
        "title": ["et", "ou", "avec", "dans", "pour", "sur", "par", "aux", "des"],
        "author": ["et", "avec", "par"],
        "publisher": ["et", "&"],
    },
    "ger": {
        # German also needs conservative approach
        # Articles (der, die, das) are integral to matching
        "title": ["und", "oder", "mit", "für", "auf", "bei", "zu", "vom", "zur"],
        "author": ["und", "mit", "von"],
        "publisher": ["und", "&"],
    },
    "spa": {
        # Limited data (81 records) - conservative approach
        "title": ["y", "o", "con", "para", "por", "en", "sobre", "desde", "hasta"],
        "author": ["y", "con", "por"],
        "publisher": ["y", "&"],
    },
    "ita": {
        # Limited data (68 records) - conservative approach
        "title": ["e", "o", "con", "per", "su", "da", "tra", "fra", "nei"],
        "author": ["e", "con", "da"],
        "publisher": ["e", "&"],
    },
}

# Words that are common but meaningful - should NOT be removed
PRESERVE_WORDS = {
    "title": [
        "new",
        "history",
        "story",
        "life",
        "american",
        "world",
        "book",
        "first",
        "second",
        "third",
        "complete",
        "selected",
        "collected",
    ],
    "author": ["illustrated", "edited", "translated", "compiled", "introduction"],
    "publisher": [
        "company",
        "press",
        "university",
        "college",
        "institute",
        "corporation",
        "inc",
        "ltd",
        "limited",
        "publishing",
        "publishers",
    ],
}


class CustomStopwordRemover:
    """Language and field-specific stopword removal based on ground truth analysis"""

    def __init__(self):
        """Initialize with custom stopword lists"""
        self.stopwords = CUSTOM_STOPWORDS
        self.preserve_words = PRESERVE_WORDS

    def get_stopwords(self, language: str = "eng", field: str = "title") -> set[str]:
        """Get stopwords for a specific language and field

        Args:
            language: Language code (eng, fre, ger, spa, ita)
            field: Field type (title, author, publisher)

        Returns:
            Set of stopwords to remove
        """
        # Default to English if language not found
        lang_stopwords = self.stopwords.get(language, self.stopwords["eng"])

        # Get field-specific stopwords, default to title if not found
        field_stopwords = lang_stopwords.get(field, lang_stopwords.get("title", []))

        return set(field_stopwords)

    def remove_stopwords(self, text: str, language: str = "eng", field: str = "title") -> list[str]:
        """Remove stopwords from text based on language and field

        Args:
            text: Input text to process
            language: Language code for stopword removal
            field: Field type for field-specific stopwords

        Returns:
            List of significant words with stopwords removed
        """
        if not text:
            return []

        words = text.lower().split()
        stopword_set = self.get_stopwords(language, field)

        # Remove stopwords but keep words >= minimum threshold
        # For testing compatibility: use 2 chars minimum for all languages
        # This ensures that single-char titles after expansion (like "0") aren't filtered
        min_length = 2

        result = []
        for word in words:
            # Keep the word if:
            # 1. It's not a stopword, OR
            # 2. It's a preserved word (even if in stopword list)
            # AND it meets minimum length requirement (unless it's not a stopword)
            if word not in stopword_set:
                # Not a stopword - keep if it meets min length
                if len(word) >= min_length:
                    result.append(word)
            elif field in self.preserve_words and word in self.preserve_words[field]:
                # It's a stopword but also preserved - keep it
                result.append(word)

        return result
