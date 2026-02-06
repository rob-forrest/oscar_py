"""
DateAxisItem - Date-based X-axis for PyQtGraph

This module provides a custom axis item that displays dates
for bar charts and summary graphs.

Copyright (c) 2019-2025 The OSCAR Team
License: GPL v3
"""

from datetime import date, datetime
from typing import List, Tuple, Optional

import pyqtgraph as pg


class DateAxisItem(pg.AxisItem):
    """Custom axis item that displays dates.

    This axis converts numeric X values (representing days since a reference
    date or day indices) into human-readable date strings.

    The axis automatically adjusts the display format based on the zoom level:
    - Wide view: Shows month/day (Jan 5, Feb 12)
    - Medium view: Shows day names (Mon, Tue, Wed)
    - Narrow view: Shows full dates (2024-01-05)
    """

    def __init__(
        self,
        orientation: str = 'bottom',
        reference_date: Optional[date] = None,
        **kwargs
    ):
        """Initialize the DateAxisItem.

        Args:
            orientation: Axis orientation ('bottom', 'top', etc.)
            reference_date: Optional reference date for index 0.
                           If None, dates are stored directly as day indices.
            **kwargs: Additional arguments passed to AxisItem.
        """
        super().__init__(orientation, **kwargs)
        self._reference_date = reference_date
        self._date_map: dict = {}  # Maps index to date

    @property
    def reference_date(self) -> Optional[date]:
        """Return the reference date."""
        return self._reference_date

    @reference_date.setter
    def reference_date(self, value: Optional[date]) -> None:
        """Set the reference date."""
        self._reference_date = value

    def set_date_map(self, date_map: dict) -> None:
        """Set a mapping from X indices to dates.

        Args:
            date_map: Dictionary mapping integer indices to date objects.
        """
        self._date_map = date_map

    def tickStrings(self, values: List[float], scale: float, spacing: float) -> List[str]:
        """Generate tick label strings for the given values.

        Args:
            values: List of tick values (X positions).
            scale: Current view scale.
            spacing: Spacing between ticks.

        Returns:
            List of formatted date strings.
        """
        strings = []

        # Determine format based on number of visible days
        num_values = len(values)

        for value in values:
            idx = int(round(value))
            date_str = self._format_date(idx, num_values)
            strings.append(date_str)

        return strings

    def _format_date(self, index: int, num_visible: int) -> str:
        """Format a date for display.

        Args:
            index: The X-axis index.
            num_visible: Approximate number of visible ticks.

        Returns:
            Formatted date string.
        """
        # Try to get date from map first
        if index in self._date_map:
            d = self._date_map[index]
        elif self._reference_date is not None:
            # Calculate date from reference
            from datetime import timedelta
            d = self._reference_date + timedelta(days=index)
        else:
            # Fallback: just show the index
            return str(index)

        # Format based on zoom level
        if num_visible <= 7:
            # Narrow view: show day name and date
            return d.strftime("%a\n%m/%d")
        elif num_visible <= 14:
            # Medium view: show short date
            return d.strftime("%m/%d")
        elif num_visible <= 31:
            # Month view: show day number and short month
            return d.strftime("%d\n%b")
        else:
            # Wide view: show month and day
            return d.strftime("%b %d")

    def tickValues(self, minVal: float, maxVal: float, size: int) -> List[Tuple[float, List[float]]]:
        """Generate tick values for the given range.

        This method determines where to place tick marks on the axis.

        Args:
            minVal: Minimum visible value.
            maxVal: Maximum visible value.
            size: Size of the axis in pixels.

        Returns:
            List of (spacing, [tick_values]) tuples.
        """
        # Calculate the range
        range_val = maxVal - minVal

        if range_val <= 0:
            return []

        # Determine appropriate tick spacing
        if range_val <= 7:
            # Show every day
            spacing = 1.0
        elif range_val <= 14:
            # Show every 2 days
            spacing = 2.0
        elif range_val <= 31:
            # Show every 7 days (weekly)
            spacing = 7.0
        elif range_val <= 90:
            # Show every 14 days
            spacing = 14.0
        elif range_val <= 180:
            # Show monthly (approximately)
            spacing = 30.0
        else:
            # Show every 2 months
            spacing = 60.0

        # Generate tick values
        start = int(minVal // spacing) * spacing
        ticks = []
        val = start
        while val <= maxVal:
            if val >= minVal:
                ticks.append(val)
            val += spacing

        return [(spacing, ticks)]
