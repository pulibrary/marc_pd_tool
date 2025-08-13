# marc_pd_tool/core/domain/match_result.py

"""Match result domain model"""

# Third party imports
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

# Local imports
from marc_pd_tool.core.domain.enums import MatchType


class MatchResult(BaseModel):
    """Represents a match between MARC record and copyright/renewal data"""

    # Note: Pydantic v2 doesn't support __slots__ directly
    # We'll use regular Pydantic which is still efficient
    model_config = ConfigDict()

    matched_title: str
    matched_author: str
    similarity_score: float
    title_score: float
    author_score: float
    year_difference: int
    source_id: str
    source_type: str
    matched_date: str = Field(default="", description="Source publication/registration date")
    matched_publisher: str | None = Field(default=None, description="Source publisher")
    publisher_score: float = Field(default=0.0, description="Publisher similarity score")
    match_type: MatchType = Field(
        default=MatchType.SIMILARITY,
        description="Type of match (LCCN, SIMILARITY, or BRUTE_FORCE_WITHOUT_YEAR)",
    )

    # Normalized versions for comparison visibility
    normalized_title: str = Field(default="", description="Normalized version of matched title")
    normalized_author: str = Field(default="", description="Normalized version of matched author")
    normalized_publisher: str = Field(
        default="", description="Normalized version of matched publisher"
    )
