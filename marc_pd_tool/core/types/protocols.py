# marc_pd_tool/core/types/protocols.py

"""Protocol definitions for external interfaces"""

# Standard library imports
from typing import Protocol


class CSVWriter(Protocol):
    """Protocol for CSV writer objects"""

    def writerow(self, row: list[str | int | float | bool | None]) -> None: ...
    def writerows(self, rows: list[list[str | int | float | bool | None]]) -> None: ...


class StemmerProtocol(Protocol):
    """Protocol for Stemmer objects from PyStemmer"""

    def stemWord(self, word: str) -> str: ...
    def stemWords(self, words: list[str]) -> list[str]: ...


__all__ = ["CSVWriter", "StemmerProtocol"]
