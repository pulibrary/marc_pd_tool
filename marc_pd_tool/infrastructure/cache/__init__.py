# marc_pd_tool/infrastructure/cache/__init__.py

"""Cache infrastructure for persistent data storage.

This module provides caching functionality for expensive operations
like data indexing and MARC file parsing.
"""

# Local imports
from marc_pd_tool.infrastructure.cache._manager import CacheManager

__all__ = ["CacheManager"]
