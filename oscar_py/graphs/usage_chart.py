"""
Usage Chart - Daily Usage Hours with Compliance Tracking

This module provides a chart that displays daily usage hours with
color coding to indicate compliance status.

Copyright (c) 2019-2025 The OSCAR Team
License: GPL v3
"""

from datetime import date
from typing import List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from .summary_chart import SummaryChart

# Try to import DaySummary
try:
    from sleeplib.statistics import DaySummary
except ImportError:
    DaySummary = None


# Compliance colors
COLOR_COMPLIANT = QColor(0, 150, 200)      # Blue - meets compliance
COLOR_NON_COMPLIANT = QColor(200, 50, 50)  # Red - below compliance
COLOR_COMPLIANCE_LINE = QColor(150, 150, 150)  # Gray dashed line


class UsageChart(SummaryChart):
    """Bar chart showing daily usage hours with compliance tracking.

    Each bar represents the total usage hours for a day. Bars are
    color-coded based on whether they meet the compliance threshold:
    - Blue: >= compliance hours
    - Red: < compliance hours

    A dashed horizontal line indicates the compliance threshold.
    """

    def __init__(
        self,
        compliance_hours: float = 4.0,
        parent=None
    ):
        """Initialize the UsageChart.

        Args:
            compliance_hours: Hours required for compliance (default 4.0).
            parent: Parent widget.
        """
        super().__init__(
            title="Usage Hours",
            y_label="Hours",
            y_unit="",
            parent=parent
        )

        self._compliance_hours = compliance_hours
        self._summaries: List['DaySummary'] = []
        self._compliance_line = None

        # Set Y-axis range suitable for hours (0-12)
        self.setYRange(0, 12, padding=0.05)

    @property
    def compliance_hours(self) -> float:
        """Return the compliance hours threshold."""
        return self._compliance_hours

    @compliance_hours.setter
    def compliance_hours(self, value: float) -> None:
        """Set the compliance hours threshold."""
        self._compliance_hours = value
        self._update_compliance_line()
        # Refresh colors if we have data
        if self._summaries:
            self.set_data(self._summaries)

    def _update_compliance_line(self) -> None:
        """Update or create the compliance threshold line."""
        # Remove existing line
        if self._compliance_line is not None:
            self.removeItem(self._compliance_line)
            self._compliance_line = None

        # Add new line
        self._compliance_line = self.add_horizontal_line(
            self._compliance_hours,
            color=COLOR_COMPLIANCE_LINE,
            style=Qt.PenStyle.DashLine,
            width=2.0
        )

    def set_data(self, summaries: List['DaySummary']) -> None:
        """Set the data to display.

        Args:
            summaries: List of DaySummary objects to display.
        """
        self._summaries = summaries

        if not summaries:
            self.clear_bars()
            return

        # Extract dates and set up X-axis
        dates = [s.date for s in summaries]
        self.set_dates(dates)

        # Clear existing bars
        self.clear_bars()

        # Extract hours and determine colors
        hours = []
        colors = []

        for s in summaries:
            hours.append(s.hours)
            if s.hours >= self._compliance_hours:
                colors.append(COLOR_COMPLIANT)
            else:
                colors.append(COLOR_NON_COMPLIANT)

        # Add bars with individual colors
        self.add_colored_bars(hours, colors)

        # Update compliance line
        self._update_compliance_line()

        # Auto-range X axis
        self.auto_range_x()

        # Set Y-axis based on max hours
        max_hours = max(hours) if hours else 8
        self.setYRange(0, max(max_hours * 1.1, 10), padding=0.05)

    def get_hours_for_date(self, d: date) -> Optional[float]:
        """Get the usage hours for a specific date.

        Args:
            d: The date to look up.

        Returns:
            The hours value, or None if not found.
        """
        for s in self._summaries:
            if s.date == d:
                return s.hours
        return None

    def is_compliant_date(self, d: date) -> Optional[bool]:
        """Check if a specific date is compliant.

        Args:
            d: The date to check.

        Returns:
            True if compliant, False if not, None if not found.
        """
        hours = self.get_hours_for_date(d)
        if hours is not None:
            return hours >= self._compliance_hours
        return None

    def get_compliance_stats(self) -> dict:
        """Get compliance statistics for the displayed data.

        Returns:
            Dictionary with compliance statistics:
            - compliant_days: Number of compliant days
            - total_days: Total number of days with data
            - compliance_percent: Percentage of compliant days
        """
        if not self._summaries:
            return {
                'compliant_days': 0,
                'total_days': 0,
                'compliance_percent': 0.0
            }

        compliant = sum(1 for s in self._summaries if s.hours >= self._compliance_hours)
        total = len(self._summaries)

        return {
            'compliant_days': compliant,
            'total_days': total,
            'compliance_percent': (compliant / total * 100) if total > 0 else 0.0
        }
