# marc_pd_tool/shared/utils/text_utils.py

"""Text processing utilities for MARC copyright analysis tool"""

# Standard library imports
from re import Match
from re import search
from re import sub
from unicodedata import normalize as unicode_normalize

# Third party imports
from unidecode import unidecode

# Local imports
from marc_pd_tool.infrastructure.config import get_config


def ascii_fold(text: str) -> str:
    """Convert accented characters to their ASCII equivalents

    This function performs ASCII folding/transliteration to convert
    accented characters to their base ASCII forms. This helps with
    matching across different encodings and data sources.

    Uses the unidecode library for comprehensive character conversion.

    Args:
        text: Input text with potential accented characters

    Returns:
        Text with all accented characters converted to ASCII
    """
    if not text:
        return ""

    # Use unidecode for comprehensive ASCII folding
    # This handles thousands of Unicode characters from many languages
    return unidecode(text)


def normalize_unicode(text: str) -> str:
    """Normalize Unicode characters to fix encoding issues and fold to ASCII

    Handles common encoding corruptions, normalizes to NFC form,
    and then folds all accented characters to ASCII.

    Args:
        text: Input text that may have encoding issues

    Returns:
        Text with normalized Unicode characters folded to ASCII
    """
    if not text:
        return ""

    # Get encoding corruption mappings from config
    # These are specific patterns found in ground truth analysis
    config = get_config()
    replacements = config.unicode_corrections

    # Apply known corruption fixes
    fixed = text
    for corrupt, correct in replacements.items():
        fixed = fixed.replace(corrupt, correct)

    # Normalize to NFC (Canonical Decomposition, followed by Canonical Composition)
    # This ensures consistent representation of accented characters
    normalized = unicode_normalize("NFC", fixed)

    # Apply ASCII folding to convert all accented characters to ASCII
    return ascii_fold(normalized)


def normalize_word_splits(text: str) -> str:
    """Normalize split words like 'a b c' to 'abc'

    Handles common patterns where single letters are separated by spaces,
    typically from abbreviations that had periods removed.

    Args:
        text: Text that may contain split single letters

    Returns:
        Text with single letter sequences joined
    """
    if not text:
        return ""

    # Pattern to find sequences of single letters separated by spaces
    # This handles cases like "a b c" → "abc", "u s a" → "usa"
    def join_single_letters(match: Match[str]) -> str:
        letters = match.group(0).split()
        return "".join(letters)

    # Match 2 or more single letters separated by one or more spaces
    # Use word boundaries and \s+ to handle multiple spaces
    pattern = r"\b(?:[a-z]\s+)+[a-z]\b"

    return sub(pattern, join_single_letters, text)


def remove_bracketed_content(text: str) -> str:
    """Remove bracketed content from text (e.g., '[microform]', '[electronic resource]')

    This function removes cataloger-added information in square brackets that
    appears in MARC titles but is not part of the actual title.

    Args:
        text: Text that may contain bracketed content

    Returns:
        Text with bracketed content removed
    """
    if not text:
        return ""

    # Remove content in square brackets along with the brackets
    # Handle nested brackets by repeatedly removing innermost brackets first
    cleaned = text
    while "[" in cleaned and "]" in cleaned:
        new_cleaned = sub(r"\[[^\[\]]*\]", "", cleaned)
        if new_cleaned == cleaned:
            # No more changes, break to avoid infinite loop
            break
        cleaned = new_cleaned

    # Clean up any double spaces left after removal
    cleaned = sub(r"\s+", " ", cleaned)

    return cleaned.strip()


def extract_significant_words(text: str, stopwords: set[str], max_words: int = 5) -> list[str]:
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
    normalized = normalize_text_standard(text)
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


def normalize_lccn(lccn: str) -> str:
    """Normalize LCCN according to Library of Congress standard algorithm

    Follows the normalization rules from:
    https://www.loc.gov/marc/lccn-namespace.html

    Algorithm:
    1. Remove all blanks (Note: only regular spaces U+0020, not all Unicode whitespace)
    2. If there is a forward slash (/) in the string, remove it and all characters to the right
    3. If there is a hyphen in the string:
       - Remove it
       - Inspect the substring following (to the right of) the removed hyphen
       - All characters should be digits, and there should be six or less
       - If the length of the substring is less than 6, left-fill with zeros until length is six

    Args:
        lccn: Raw LCCN string from MARC or copyright data

    Returns:
        Normalized LCCN string

    Examples:
        >>> normalize_lccn("n78-890351")
        'n78890351'
        >>> normalize_lccn("n78-89035")
        'n78089035'
        >>> normalize_lccn("n 78890351 ")
        'n78890351'
        >>> normalize_lccn(" 85000002 ")
        '85000002'
        >>> normalize_lccn("85-2 ")
        '85000002'
        >>> normalize_lccn("2001-000002")
        '2001000002'
        >>> normalize_lccn("75-425165//r75")
        '75425165'
        >>> normalize_lccn(" 79139101 /AC/r932")
        '79139101'
    """
    if not lccn:
        return ""

    # Step 1: Remove all blanks (spaces)
    normalized = lccn.replace(" ", "")

    # Step 2: Handle forward slash - remove it and everything to the right
    if "/" in normalized:
        normalized = normalized.split("/")[0]

    # Step 3: Handle hyphen - special processing for standard LCCN format
    if "-" in normalized:
        # Split on the first hyphen only
        parts = normalized.split("-", 1)
        prefix = parts[0]
        suffix = parts[1] if len(parts) > 1 else ""

        # Check if this follows standard LCCN format (suffix is all digits and <= 6 chars)
        if suffix.isdigit() and len(suffix) <= 6:
            # Left-pad with zeros to make it 6 digits
            suffix = suffix.zfill(6)

        # Reassemble without the hyphen
        normalized = prefix + suffix

        # Remove any remaining hyphens
        normalized = normalized.replace("-", "")

    return normalized


def extract_lccn_prefix(normalized_lccn: str) -> str:
    """Extract the alphabetic prefix from a normalized LCCN

    Args:
        normalized_lccn: Normalized LCCN string

    Returns:
        Alphabetic prefix (e.g., 'n' from 'n78890351')
    """
    if not normalized_lccn:
        return ""

    # Find the first digit position
    for i, char in enumerate(normalized_lccn):
        if char.isdigit():
            return normalized_lccn[:i]

    # If no digits found, return the whole string
    return normalized_lccn


def extract_lccn_year(normalized_lccn: str) -> str:
    """Extract the year portion from a normalized LCCN

    Args:
        normalized_lccn: Normalized LCCN string

    Returns:
        Year portion (e.g., '78' from 'n78890351')
    """
    if not normalized_lccn:
        return ""

    # Find the first digit position
    digit_start = 0
    for i, char in enumerate(normalized_lccn):
        if char.isdigit():
            digit_start = i
            break
    else:
        return ""  # No digits found

    # Extract the numeric portion
    numeric_part = normalized_lccn[digit_start:]

    # For most LCCNs, the year is the first 2-4 digits
    # Handle different year formats:
    if len(numeric_part) >= 4 and numeric_part[:4].isdigit():
        # Full 4-digit year (e.g., "2001000002" -> "2001")
        year_candidate = numeric_part[:4]
        if year_candidate.startswith("19") or year_candidate.startswith("20"):
            return year_candidate

    if len(numeric_part) >= 2:
        # 2-digit year (e.g., "78890351" -> "78")
        return numeric_part[:2]
    elif len(numeric_part) == 1:
        # Single digit - return as-is for edge cases
        return numeric_part

    return ""


def extract_lccn_serial(normalized_lccn: str) -> str:
    """Extract the serial number portion from a normalized LCCN

    Args:
        normalized_lccn: Normalized LCCN string

    Returns:
        Serial number portion (e.g., '890351' from 'n78890351')
    """
    if not normalized_lccn:
        return ""

    # Find the first digit position
    digit_start = 0
    for i, char in enumerate(normalized_lccn):
        if char.isdigit():
            digit_start = i
            break
    else:
        return ""  # No digits found

    numeric_part = normalized_lccn[digit_start:]

    # Handle different year formats to extract serial
    if len(numeric_part) >= 4 and numeric_part[:4].isdigit():
        year_candidate = numeric_part[:4]
        if year_candidate.startswith("19") or year_candidate.startswith("20"):
            # 4-digit year, serial is remainder
            return numeric_part[4:]

    # 2-digit year, serial is remainder (only if we have more than 2 digits)
    if len(numeric_part) > 2:
        return numeric_part[2:]

    # For very short cases (1-2 digits), there's no serial
    return ""


def extract_year(date_string: str) -> int | None:
    """Extract a 4-digit year from a date string

    Searches for the first occurrence of a 4-digit year (1800-2099) in the string.
    This centralizes year extraction logic used across the codebase.

    Args:
        date_string: String that may contain a year

    Returns:
        Extracted year as integer, or None if no valid year found

    Examples:
        >>> extract_year("1984")
        1984
        >>> extract_year("Published in 1925")
        1925
        >>> extract_year("1984-05-15")
        1984
        >>> extract_year("May 15, 1984")
        1984
        >>> extract_year("c1955")
        1955
        >>> extract_year("[c1923]")
        1923
        >>> extract_year("18th century")
        None
        >>> extract_year("")
        None
    """
    if not date_string:
        return None

    # Search for 4-digit year from 1800s to 2000s
    # This pattern handles:
    # - Standard years with word boundaries: 1955, "1955", etc.
    # - Copyright notation: c1955, [c1955], etc.
    year_match = search(r"(?:\b|c)(18|19|20)\d{2}\b", date_string)
    if year_match:
        # Extract just the year digits
        year_str = search(r"(18|19|20)\d{2}", year_match.group())
        if year_str:
            return int(year_str.group())
    return None


def normalize_text_comprehensive(
    text: str,
    remove_brackets: bool = True,
    remove_punctuation: bool = True,
    join_split_letters: bool = True,
    lowercase: bool = True,
    normalize_whitespace: bool = True,
    apply_unicode_fixes: bool = True,
    ascii_fold_chars: bool = True,
    stopwords: set[str] | None = None,
    remove_suffixes: str | None = None,
) -> str:
    """Comprehensive text normalization with configurable options

    This function provides all text normalization capabilities in one place,
    replacing the need for TextNormalizerMixin. It applies transformations
    in a logical order to ensure consistent results.

    Args:
        text: Input text to normalize
        remove_brackets: Remove [bracketed] content
        remove_punctuation: Remove punctuation (except hyphens)
        join_split_letters: Join "a b c" -> "abc"
        lowercase: Convert to lowercase
        normalize_whitespace: Normalize spaces and hyphens
        apply_unicode_fixes: Apply Unicode corruption fixes
        ascii_fold_chars: Convert accented chars to ASCII
        stopwords: Optional set of stopwords to remove
        remove_suffixes: Optional regex pattern of suffixes to remove

    Returns:
        Normalized text according to configured options
    """
    if not text:
        return ""

    # Apply steps in logical order
    if remove_brackets:
        text = remove_bracketed_content(text)

    if apply_unicode_fixes or ascii_fold_chars:
        # normalize_unicode does both unicode fixes and ASCII folding
        text = normalize_unicode(text)

    if lowercase:
        text = text.lower()

    if remove_punctuation:
        # Keep hyphens as they can be meaningful
        text = sub(r"[^\w\s\-]", " ", text)

    if normalize_whitespace:
        # Normalize spaces and hyphens
        text = sub(r"[\s\-]+", " ", text)

    if join_split_letters:
        text = normalize_word_splits(text)

    # Apply stopwords filtering if provided
    if stopwords:
        words = [w for w in text.split() if w not in stopwords]
        text = " ".join(words)

    # Remove suffixes if pattern provided
    if remove_suffixes:
        text = sub(remove_suffixes, "", text)
        # Clean up any double spaces after suffix removal
        text = sub(r"\s+", " ", text)

    return text.strip()


def normalize_text_standard(text: str) -> str:
    """Standard text normalization for backward compatibility

    This provides a simple function interface for standard text normalization
    using all default options.

    Args:
        text: Input text to normalize

    Returns:
        Normalized text with all standard transformations applied
    """
    return normalize_text_comprehensive(text)
