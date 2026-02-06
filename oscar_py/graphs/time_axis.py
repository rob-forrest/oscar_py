"""
TimeAxisItem - Custom Time Axis for PyQtGraph

This module provides a custom axis item that formats timestamps
as human-readable time strings (HH:MM:SS or HH:MM).

Copyright (c) 2019-2025 The OSCAR Team
License: GPL v3
"""

from typing import List, Optional
from datetime import datetime

import pyqtgraph as pg


class TimeAxisItem(pg.AxisItem):
    """Custom axis item for displaying time values.

    Formats timestamps (milliseconds since epoch) as human-readable
    time strings. Automatically adjusts format based on zoom level:
    - Zoomed out: HH:MM
    - Zoomed in: HH:MM:SS
    - Very zoomed in: HH:MM:SS.mmm

    Attributes:
        use_local_time: Whether to use local timezone (True) or UTC (False)
        show_date: Whether to show the date portion when time range spans days
    """

    # Time span thresholds for format selection (in milliseconds)
    THRESHOLD_SHOW_SECONDS = 10 * 60 * 1000  # 10 minutes - show seconds
    THRESHOLD_SHOW_MILLIS = 30 * 1000  # 30 seconds - show milliseconds
    THRESHOLD_SHOW_DATE = 24 * 60 * 60 * 1000  # 24 hours - show date

    def __init__(
        self,
        orientation: str = 'bottom',
        use_local_time: bool = True,
        show_date: bool = False,
        *args,
        **kwargs
    ):
        """Initialize the TimeAxisItem.

        Args:
            orientation: Axis orientation ('bottom', 'top', 'left', 'right')
            use_local_time: Use local timezone if True, UTC if False
            show_date: Show date portion in labels
            *args, **kwargs: Additional arguments for AxisItem
        """
        super().__init__(orientation, *args, **kwargs)
        self.use_local_time = use_local_time
        self.show_date = show_date
        self._time_range: Optional[float] = None

        # Enable tick labels
        self.setStyle(showValues=True)

    def tickStrings(self, values: List[float], scale: float, spacing: float) -> List[str]:
        """Convert tick values (ms since epoch) to formatted time strings.

        Args:
            values: List of tick values in milliseconds since epoch
            scale: Not used
            spacing: Spacing between ticks in data units

        Returns:
            List of formatted time strings
        """
        if not values:
            return []

        # Calculate time range to determine format
        time_range = spacing * 10  # Approximate visible range
        if self._time_range is not None:
            time_range = self._time_range

        strings = []
        for val in values:
            strings.append(self._format_time(val, time_range))

        return strings

    def _format_time(self, timestamp_ms: float, time_range: float) -> str:
        """Format a timestamp based on the current zoom level.

        Args:
            timestamp_ms: Timestamp in milliseconds since epoch
            time_range: Current visible time range in milliseconds

        Returns:
            Formatted time string
        """
        try:
            # Convert from milliseconds to seconds
            timestamp_sec = timestamp_ms / 1000.0

            if self.use_local_time:
                dt = datetime.fromtimestamp(timestamp_sec)
            else:
                dt = datetime.utcfromtimestamp(timestamp_sec)

            # Choose format based on zoom level
            if time_range < self.THRESHOLD_SHOW_MILLIS:
                # Very zoomed in: show milliseconds
                millis = int(timestamp_ms % 1000)
                return f"{dt.hour:02d}:{dt.minute:02d}:{dt.second:02d}.{millis:03d}"
            elif time_range < self.THRESHOLD_SHOW_SECONDS:
                # Zoomed in: show seconds
                return f"{dt.hour:02d}:{dt.minute:02d}:{dt.second:02d}"
            elif time_range > self.THRESHOLD_SHOW_DATE or self.show_date:
                # Zoomed out or show_date enabled: show date
                return f"{dt.month:02d}/{dt.day:02d} {dt.hour:02d}:{dt.minute:02d}"
            else:
                # Normal: show hours and minutes
                return f"{dt.hour:02d}:{dt.minute:02d}"

        except (ValueError, OSError):
            # Handle invalid timestamps
            return ""

    def set_time_range(self, time_range_ms: float) -> None:
        """Set the current visible time range for format selection.

        Args:
            time_range_ms: Visible time range in milliseconds
        """
        self._time_range = time_range_ms

    def linkToView(self, view: pg.ViewBox) -> None:
        """Override to track view range changes.

        Args:
            view: The ViewBox to link to
        """
        super().linkToView(view)
        # Connect to range change signal
        view.sigXRangeChanged.connect(self._on_range_changed)

    def _on_range_changed(self, view: pg.ViewBox, range_tuple: tuple) -> None:
        """Handle view range changes.

        Args:
            view: The ViewBox that changed
            range_tuple: Tuple of (min, max) for the X range
        """
        if range_tuple:
            min_val, max_val = range_tuple
            self._time_range = max_val - min_val


def format_duration(duration_ms: float) -> str:
    """Format a duration in milliseconds as a human-readable string.

    Args:
        duration_ms: Duration in milliseconds

    Returns:
        Formatted duration string (e.g., "1h 30m", "45s", "1.5h")
    """
    if duration_ms < 1000:
        return f"{int(duration_ms)}ms"

    seconds = duration_ms / 1000.0

    if seconds < 60:
        return f"{seconds:.1f}s"

    minutes = seconds / 60.0

    if minutes < 60:
        if minutes == int(minutes):
            return f"{int(minutes)}m"
        return f"{minutes:.1f}m"

    hours = minutes / 60.0
    remaining_minutes = int(minutes % 60)

    if remaining_minutes == 0:
        if hours == int(hours):
            return f"{int(hours)}h"
        return f"{hours:.1f}h"

    return f"{int(hours)}h {remaining_minutes}m"
