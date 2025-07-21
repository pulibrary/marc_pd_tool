"""Text processing utilities for MARC copyright analysis tool"""

# Standard library imports
from re import sub


def normalize_text(text: str) -> str:
    """Normalize text for consistent processing across the application

    This function provides unified text normalization for both indexing and matching.
    It preserves hyphens as they can be meaningful in titles and names.

    Args:
        text: Input text to normalize

    Returns:
        Normalized text: lowercase, punctuation removed (except hyphens),
        whitespace normalized
    """
    if not text:
        return ""

    # Convert to lowercase and remove punctuation except spaces and hyphens
    normalized = sub(r"[^\w\s\-]", " ", text.lower())

    # Normalize whitespace and hyphens
    normalized = sub(r"[\s\-]+", " ", normalized)

    return normalized.strip()


def extract_significant_words(text: str, stopwords: set, max_words: int = 5) -> list:
    """Extract significant words from text, filtering stopwords

    Args:
        text: Input text to process
        stopwords: Set of stopwords to filter out
        max_words: Maximum number of words to return

    Returns:
        List of significant words
    """
    if not text:
        return []

    # Normalize and split into words
    normalized = normalize_text(text)
    words = normalized.split()

    # Filter stopwords and short words (length >= 3)
    significant = [w for w in words if w not in stopwords and len(w) >= 3]
    if not significant and words:
        # If all words were filtered, keep the first word with length >= 2
        significant = [w for w in words if len(w) >= 2][:1]

    # Return up to max_words
    return significant[:max_words]


def clean_personal_name_dates(name: str) -> str:
    """Clean dates from personal names in MARC 1xx fields

    MARC personal names often include dates like "Smith, John, 1945-2020"
    This function removes the trailing date portion.

    Args:
        name: Personal name that may include dates

    Returns:
        Name with dates removed
    """
    if not name or "," not in name:
        return name

    parts = name.split(",")
    if len(parts) >= 3:
        # Check if last part looks like a date
        last_part = parts[-1].strip()
        if last_part and (last_part[0].isdigit() or last_part.endswith("-")):
            # Remove the date part
            return ",".join(parts[:-1]).strip()

    return name
