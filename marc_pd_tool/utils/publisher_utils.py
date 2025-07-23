# marc_pd_tool/utils/publisher_utils.py

"""Publisher text processing utilities"""

# Standard library imports
from re import sub


def extract_publisher_candidates(text: str) -> list[str]:
    """Extract potential publisher strings from unstructured text

    Args:
        text: Full text that may contain publisher information

    Returns:
        List of potential publisher strings
    """
    if not text:
        return []

    candidates = []

    # Split on common delimiters
    segments = []
    for delimiter in [";", ".", ",", "\n"]:
        if delimiter in text:
            segments.extend(text.split(delimiter))

    if not segments:
        segments = [text]

    for segment in segments:
        segment_clean = segment.strip()

        # Skip if too short
        if len(segment_clean) < 3:
            continue

        # Look for publisher indicators
        lower_segment = segment_clean.lower()
        publisher_indicators = [
            "publisher",
            "published by",
            "press",
            "publications",
            "books",
            "pub.",
            "publishing",
            "imprint",
            "edition",
        ]

        if any(ind in lower_segment for ind in publisher_indicators):
            candidates.append(segment_clean)
        # Also consider segments that might be publisher names (heuristic)
        elif 3 <= len(segment_clean.split()) <= 6 and segment_clean[0].isupper():
            # Check if it doesn't start with common non-publisher words
            non_publisher_starts = ["the", "a", "an", "by", "in", "at", "on", "for"]
            first_word = segment_clean.split()[0].lower()
            if first_word not in non_publisher_starts:
                candidates.append(segment_clean)

    return candidates


def clean_publisher_suffix(publisher: str) -> str:
    """Remove common suffixes and trailing elements from publisher names

    Args:
        publisher: Publisher text to clean

    Returns:
        Cleaned publisher text
    """
    if not publisher:
        return ""

    # Remove trailing punctuation
    cleaned = sub(r"[.,;:]+$", "", publisher)

    # Remove trailing parenthetical content (often codes or locations)
    cleaned = sub(r"\s*\([^)]*\)\s*$", "", cleaned)

    # Remove "successor to" and similar phrases
    cleaned = sub(
        r",?\s*(successor to|formerly|division of|imprint of|subsidiary of).*$",
        "",
        cleaned,
        flags=2,
    )

    return cleaned.strip()
