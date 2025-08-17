# marc_pd_tool/core/types/json.py

"""JSON type definitions for type-safe JSON handling using Python 3.13 features."""

# JSON Type Usage Guide:
# - JSONDict: When you KNOW it's a dict with string keys (e.g., loaded config files, JSON records)
# - JSONList: When you KNOW it's a list (e.g., array of records, list of values)
# - JSONType: When it could be either or you're accessing nested data
# - NEVER use Any - it's not allowed in our codebase

# Modern type statements for JSON types (Python 3.13)
type JSONPrimitive = str | int | float | bool | None

# Recursive type definition - Python 3.13 handles this cleanly without quotes!
type JSONType = JSONDict | JSONList | JSONPrimitive
type JSONDict = dict[str, JSONType]
type JSONList = list[JSONType]

__all__ = ["JSONPrimitive", "JSONType", "JSONDict", "JSONList"]
