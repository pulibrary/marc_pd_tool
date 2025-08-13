# marc_pd_tool/core/domain/index_entry.py

"""Index-related data structures"""


class IndexEntry:
    """Memory-efficient container for index entries - stores single int or set"""

    __slots__ = ("_data",)

    def __init__(self) -> None:
        self._data: int | set[int] | None = None  # None, int, or set

    def add(self, pub_id: int) -> None:
        """Add a publication ID to this entry"""
        if self._data is None:
            # First entry - store as single int
            self._data = pub_id
        elif isinstance(self._data, int):
            # Second entry - convert to set
            if self._data != pub_id:  # Only convert if different
                self._data = {self._data, pub_id}
        else:
            # Already a set - add to it
            self._data.add(pub_id)

    @property
    def ids(self) -> set[int]:
        """Get all publication IDs as a set"""
        if self._data is None:
            return set()
        elif isinstance(self._data, int):
            return {self._data}
        else:
            # self._data is guaranteed to be a set here by the type system
            return self._data.copy()

    def is_empty(self) -> bool:
        """Check if entry is empty"""
        return self._data is None
