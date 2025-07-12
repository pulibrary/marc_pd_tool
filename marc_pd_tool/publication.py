"""Publication data model for MARC and Copyright entries"""

# Standard library imports
import re
from typing import Dict
from typing import Optional


class Publication:
    def __init__(
        self,
        title: str,
        author: str = "",
        pub_date: str = "",
        publisher: str = "",
        place: str = "",
        source: str = "",
        source_id: str = "",
    ):
        self.title = self.normalize_text(title)
        self.author = self.normalize_text(author)
        self.pub_date = pub_date
        self.publisher = self.normalize_text(publisher)
        self.place = self.normalize_text(place)
        self.source = source
        self.source_id = source_id

        # Store original values
        self.original_title = title
        self.original_author = author
        self.original_publisher = publisher
        self.original_place = place

        # Extract year
        self.year = self.extract_year()

    @staticmethod
    def normalize_text(text: str) -> str:
        if not text:
            return ""
        text = re.sub(r"[^\w\s]", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip().lower()

    def extract_year(self) -> Optional[int]:
        if not self.pub_date:
            return None
        year_match = re.search(r"\b(19|20)\d{2}\b", self.pub_date)
        if year_match:
            return int(year_match.group())
        return None

    def to_dict(self) -> Dict:
        return {
            "title": self.original_title,
            "author": self.original_author,
            "pub_date": self.pub_date,
            "publisher": self.original_publisher,
            "place": self.original_place,
            "source": self.source,
            "source_id": self.source_id,
            "year": self.year,
        }
