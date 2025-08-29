# marc_pd_tool/infrastructure/logging/_progress.py

"""Progress bar management for CLI output"""

# Standard library imports
from contextlib import contextmanager
from logging import getLogger
from typing import Any
from typing import Iterator

try:
    # Third party imports
    from rich.console import Console
    from rich.progress import BarColumn
    from rich.progress import MofNCompleteColumn
    from rich.progress import Progress
    from rich.progress import SpinnerColumn
    from rich.progress import TaskID
    from rich.progress import TextColumn
    from rich.progress import TimeElapsedColumn
    from rich.progress import TimeRemainingColumn

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    Progress = Any  # type: ignore
    TaskID = int  # type: ignore
    Console = Any  # type: ignore

logger = getLogger(__name__)


def log_phase_header(phase_name: str, enabled: bool = False) -> None:
    """Log a phase header, printing to console if progress bars are enabled.

    Args:
        phase_name: The name of the phase (e.g., "PHASE 1: LOADING COPYRIGHT/RENEWAL DATA")
        enabled: Whether progress bars are enabled (if True, also print to console)
    """
    separator = "=" * 80
    header = f"=== {phase_name} ==="

    # Print to console if progress bars are enabled
    if enabled:
        print("")
        print(separator)
        print(header)
        print(separator)

    # Always log for file output
    logger.info("")
    logger.info(separator)
    logger.info(header)
    logger.info(separator)


def log_phase_info(message: str, enabled: bool = False) -> None:
    """Log phase information, printing to console if progress bars are enabled.

    Args:
        message: The information message to log
        enabled: Whether progress bars are enabled (if True, also print to console)
    """
    if enabled:
        print(message)
    logger.info(message)


class ProgressBarManager:
    """Manages progress bars for different phases of processing"""

    def __init__(self, enabled: bool = True) -> None:
        """Initialize progress bar manager

        Args:
            enabled: Whether to show progress bars (requires rich library)
        """
        self.enabled = enabled and RICH_AVAILABLE
        self.progress: Progress | None = None
        self.console: Console | None = None
        self.tasks: dict[str, TaskID] = {}

        if self.enabled:
            self.console = Console()
            self.progress = Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                BarColumn(),
                MofNCompleteColumn(),
                TimeElapsedColumn(),
                TimeRemainingColumn(),
                console=self.console,
                expand=False,
            )

    def start(self) -> None:
        """Start the progress display"""
        if self.enabled and self.progress:
            self.progress.start()

    def stop(self) -> None:
        """Stop the progress display"""
        if self.enabled and self.progress:
            self.progress.stop()

    def create_phase_task(
        self, phase_name: str, total: int | None = None, description: str | None = None
    ) -> TaskID | None:
        """Create a new progress task for a processing phase

        Args:
            phase_name: Name of the phase (used as key)
            total: Total number of items to process (None for indeterminate)
            description: Description to display

        Returns:
            Task ID if progress bars are enabled, None otherwise
        """
        if not self.enabled or not self.progress:
            # Log to console if progress bars disabled
            if description:
                logger.info(description)
            return None

        # Create the task
        task_id = self.progress.add_task(
            description or phase_name,
            total=total or 100,  # Default to 100 for percentage-based updates
        )
        self.tasks[phase_name] = task_id
        return task_id

    def update_task(
        self,
        phase_name: str,
        advance: int = 1,
        completed: int | None = None,
        total: int | None = None,
        description: str | None = None,
    ) -> None:
        """Update progress for a task

        Args:
            phase_name: Name of the phase to update
            advance: Number of items to advance by
            completed: Set absolute completed count
            total: Update the total if it changed
            description: Update the description
        """
        if not self.enabled or not self.progress or phase_name not in self.tasks:
            return

        task_id = self.tasks[phase_name]

        # Build update kwargs
        update_kwargs: dict[str, Any] = {}
        if completed is not None:
            update_kwargs["completed"] = completed
        if total is not None:
            update_kwargs["total"] = total
        if description is not None:
            update_kwargs["description"] = description

        if update_kwargs:
            self.progress.update(task_id, **update_kwargs)

        if advance > 0:
            self.progress.advance(task_id, advance)

    def complete_task(self, phase_name: str, message: str | None = None) -> None:
        """Mark a task as complete

        Args:
            phase_name: Name of the phase to complete
            message: Optional completion message
        """
        if not self.enabled or not self.progress or phase_name not in self.tasks:
            if message:
                logger.info(message)
            return

        task_id = self.tasks[phase_name]
        task = self.progress.tasks[task_id]

        # Set to 100% complete
        self.progress.update(task_id, completed=task.total)

        if message and self.console:
            self.console.print(f"[green]✓[/green] {message}")

    def log_message(self, message: str, style: str | None = None) -> None:
        """Log a message outside the progress display

        Args:
            message: Message to display
            style: Rich style string (e.g., "bold red")
        """
        if self.enabled and self.console:
            if style:
                self.console.print(f"[{style}]{message}[/{style}]")
            else:
                self.console.print(message)
        else:
            logger.info(message)

    @contextmanager
    def phase_context(
        self, phase_name: str, total: int | None = None, description: str | None = None
    ) -> Iterator[None]:
        """Context manager for a processing phase

        Args:
            phase_name: Name of the phase
            total: Total items to process
            description: Phase description
        """
        # Create the task
        self.create_phase_task(phase_name, total, description)

        try:
            yield
        finally:
            # Mark as complete
            self.complete_task(phase_name)


# Global progress manager instance
_progress_manager: ProgressBarManager | None = None


def get_progress_manager() -> ProgressBarManager:
    """Get the global progress manager instance"""
    global _progress_manager
    if _progress_manager is None:
        _progress_manager = ProgressBarManager(enabled=False)
    return _progress_manager


def initialize_progress_manager(enabled: bool = True) -> ProgressBarManager:
    """Initialize and return the global progress manager

    Args:
        enabled: Whether to enable progress bars

    Returns:
        The initialized progress manager
    """
    global _progress_manager
    _progress_manager = ProgressBarManager(enabled=enabled)
    if enabled:
        _progress_manager.start()
    return _progress_manager


def shutdown_progress_manager() -> None:
    """Shut down the global progress manager"""
    global _progress_manager
    if _progress_manager:
        _progress_manager.stop()
        _progress_manager = None
