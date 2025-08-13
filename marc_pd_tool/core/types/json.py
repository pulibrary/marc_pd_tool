# marc_pd_tool/core/types/json.py

"""JSON type definitions for type-safe JSON handling"""

# JSON Type Usage Guide:
# - JSONDict: When you KNOW it's a dict with string keys (e.g., loaded config files, JSON records)
# - JSONList: When you KNOW it's a list (e.g., array of records, list of values)
# - JSONType: When it could be either or you're accessing nested data
# - NEVER use Any - it's not allowed in our codebase

# Define a generic type for JSON data
JSONPrimitive = str | int | float | bool | None
JSONType = dict[str, "JSONType"] | list["JSONType"] | JSONPrimitive

# "Wrapper" types that at least give a hint at the outermost structure
JSONDict = dict[str, JSONType]
JSONList = list[JSONType]

__all__ = ["JSONPrimitive", "JSONType", "JSONDict", "JSONList"]
