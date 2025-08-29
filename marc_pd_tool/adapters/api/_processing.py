# marc_pd_tool/adapters/api/_processing.py

"""Processing component - currently unused but kept for potential future use"""

# Standard library imports
from typing import TYPE_CHECKING

# Local imports
from marc_pd_tool.core.types.protocols import AnalyzerProtocol

if TYPE_CHECKING:
    pass


class ProcessingComponent:
    """Component for processing functionality

    Note: The processing methods in this component have been superseded
    by the StreamingComponent which handles all processing more efficiently.
    This component is kept as a mixin to satisfy protocol requirements
    but its methods are not actively used.
    """

    def _cleanup_on_exit(self: AnalyzerProtocol) -> None:
        """Clean up temporary files on exit

        Required by AnalyzerProtocol but not actively used since
        StreamingComponent handles its own cleanup.
        """
        if hasattr(self.results, "result_temp_dir") and self.results.result_temp_dir:
            self.results.cleanup_temp_files()
