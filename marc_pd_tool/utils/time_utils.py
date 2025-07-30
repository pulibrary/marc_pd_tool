# marc_pd_tool/utils/time_utils.py

"""Time-related utility functions"""


def format_time_duration(seconds: float) -> str:
    """Format time duration in human-readable format

    Args:
        seconds: Duration in seconds

    Returns:
        Human-readable string (e.g., "2h 15m", "1d 3h 45m")
    """
    total_seconds = int(seconds)
    days = total_seconds // (24 * 3600)
    hours = (total_seconds % (24 * 3600)) // 3600
    minutes = (total_seconds % 3600) // 60
    remaining_seconds = total_seconds % 60

    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    elif hours > 0:
        return f"{hours}h {minutes}m"
    elif minutes > 0:
        return f"{minutes}m {remaining_seconds}s"
    else:
        return f"{remaining_seconds}s"
