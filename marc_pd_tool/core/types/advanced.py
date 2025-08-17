# marc_pd_tool/core/types/advanced.py

"""Advanced type definitions using Python 3.13 features."""

# Standard library imports
from typing import Annotated
from typing import Callable
from typing import Literal
from typing import ParamSpec
from typing import Self
from typing import TypeIs
from typing import TypeVar
from typing import assert_never

# Third party imports
# Third-party imports
from pydantic import BaseModel
from pydantic import Field

# Type parameters
P = ParamSpec("P")
R = TypeVar("R")
T = TypeVar("T")

# ============================================================================
# Discriminated Union Types
# ============================================================================


class TextMatch(BaseModel):
    """Text-based match result."""

    type: Literal["text"] = "text"
    score: float = Field(ge=0.0, le=100.0)
    matched_title: str
    matched_author: str
    matched_publisher: str | None = None


class LCCNMatch(BaseModel):
    """LCCN-based match result."""

    type: Literal["lccn"] = "lccn"
    lccn: str
    exact: bool = True
    normalized_lccn: str


class NoMatch(BaseModel):
    """No match found."""

    type: Literal["none"] = "none"
    reason: str
    highest_score: float | None = None


# Discriminated union for match results
type MatchResultType = TextMatch | LCCNMatch | NoMatch


def process_match_result(result: MatchResultType) -> str:
    """Example of exhaustive matching with discriminated unions."""
    match result.type:
        case "text":
            return f"Text match with score {result.score}"
        case "lccn":
            return f"LCCN match: {result.lccn}"
        case "none":
            return f"No match: {result.reason}"
        case _:
            assert_never(result.type)


# ============================================================================
# Function Decorators with ParamSpec
# ============================================================================


def with_logging[**P, R](level: str = "INFO") -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator that adds logging to any function."""

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            print(f"[{level}] Calling {func.__name__}")
            result = func(*args, **kwargs)
            print(f"[{level}] Completed {func.__name__}")
            return result

        return wrapper

    return decorator


def with_retry[**P, R](max_attempts: int = 3) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator that adds retry logic."""

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts - 1:
                        raise
                    print(f"Attempt {attempt + 1} failed: {e}")
            raise RuntimeError("Should not reach here")

        return wrapper

    return decorator


# ============================================================================
# Builder Pattern with Self
# ============================================================================


class QueryBuilder(BaseModel):
    """Fluent query builder using Self type."""

    model_config = {"frozen": False}

    select_fields: list[str] = Field(default_factory=list)
    where_clauses: list[str] = Field(default_factory=list)
    order_by_field: str | None = None
    limit_value: int | None = None

    def select(self, *fields: str) -> Self:
        """Add fields to select."""
        self.select_fields.extend(fields)
        return self

    def where(self, clause: str) -> Self:
        """Add where clause."""
        self.where_clauses.append(clause)
        return self

    def order_by(self, field: str) -> Self:
        """Set order by field."""
        self.order_by_field = field
        return self

    def limit(self, n: int) -> Self:
        """Set limit."""
        self.limit_value = n
        return self

    def build(self) -> str:
        """Build the query string."""
        parts = []
        if self.select_fields:
            parts.append(f"SELECT {', '.join(self.select_fields)}")
        if self.where_clauses:
            parts.append(f"WHERE {' AND '.join(self.where_clauses)}")
        if self.order_by_field:
            parts.append(f"ORDER BY {self.order_by_field}")
        if self.limit_value:
            parts.append(f"LIMIT {self.limit_value}")
        return " ".join(parts)


# ============================================================================
# Generic Pipeline
# ============================================================================


class Pipeline[T, R](BaseModel):
    """Pipeline that processes data through stages."""

    model_config = {"arbitrary_types_allowed": True}

    stages: list[Callable[[object], object]] = Field(default_factory=list)

    def add_stage(self, processor: Callable[[object], object]) -> Self:
        """Add a processing stage."""
        self.stages.append(processor)
        return self

    def execute(self, input_data: T) -> R:
        """Execute pipeline on input."""
        result: object = input_data
        for stage in self.stages:
            result = stage(result)
        return result  # type: ignore[return-value]


# ============================================================================
# Type Guards
# ============================================================================


def is_text_match(result: MatchResultType) -> TypeIs[TextMatch]:
    """Type guard for text matches."""
    return result.type == "text"


def is_lccn_match(result: MatchResultType) -> TypeIs[LCCNMatch]:
    """Type guard for LCCN matches."""
    return result.type == "lccn"


def is_no_match(result: MatchResultType) -> TypeIs[NoMatch]:
    """Type guard for no matches."""
    return result.type == "none"


# ============================================================================
# Constrained Type Aliases
# ============================================================================

# Score types with semantic meaning
type HighConfidenceScore = Annotated[float, Field(ge=90.0, le=100.0)]
type MediumConfidenceScore = Annotated[float, Field(ge=60.0, lt=90.0)]
type LowConfidenceScore = Annotated[float, Field(ge=0.0, lt=60.0)]

# Year ranges for different eras
type PreModernYear = Annotated[int, Field(ge=1450, lt=1900)]
type ModernYear = Annotated[int, Field(ge=1900, lt=2000)]
type ContemporaryYear = Annotated[int, Field(ge=2000, le=2100)]

# String constraints with business meaning
type ISBNString = Annotated[str, Field(pattern=r"^(\d{10}|\d{13})$")]
type ISSNString = Annotated[str, Field(pattern=r"^\d{4}-\d{3}[\dX]$")]
type LCCNString = Annotated[str, Field(pattern=r"^[a-z]{0,3}\d{2,4}\d{6}$")]
type DOIString = Annotated[str, Field(pattern=r"^10\.\d{4,}/[-._;()/:a-zA-Z0-9]+$")]


# ============================================================================
# Result Monad Pattern
# ============================================================================


class Ok[T](BaseModel):
    """Success result."""

    value: T

    def map[U](self, func: Callable[[T], U]) -> "Ok[U]":
        """Map function over success value."""
        return Ok(value=func(self.value))

    def flat_map[U](self, func: Callable[[T], "Result[U]"]) -> "Result[U]":
        """Flat map for chaining operations."""
        return func(self.value)


class Err(BaseModel):
    """Error result."""

    error: str
    code: int | None = None

    def map[U](self, func: Callable[[object], U]) -> "Err":
        """Map has no effect on errors."""
        return self

    def flat_map[U](self, func: Callable[[object], "Result[U]"]) -> "Err":
        """Flat map has no effect on errors."""
        return self


type Result[T] = Ok[T] | Err


def divide(a: float, b: float) -> Result[float]:
    """Example function using Result type."""
    if b == 0:
        return Err(error="Division by zero", code=1001)
    return Ok(value=a / b)


__all__ = [
    # Discriminated unions
    "TextMatch",
    "LCCNMatch",
    "NoMatch",
    "MatchResultType",
    "process_match_result",
    # Decorators
    "with_logging",
    "with_retry",
    # Builder
    "QueryBuilder",
    # Pipeline
    "Pipeline",
    # Type guards
    "is_text_match",
    "is_lccn_match",
    "is_no_match",
    # Constrained types
    "HighConfidenceScore",
    "MediumConfidenceScore",
    "LowConfidenceScore",
    "PreModernYear",
    "ModernYear",
    "ContemporaryYear",
    "ISBNString",
    "ISSNString",
    "LCCNString",
    "DOIString",
    # Result monad
    "Ok",
    "Err",
    "Result",
    "divide",
]
