"""
AHI Chart - Stacked Bar Chart for AHI Breakdown

This module provides a chart that displays daily AHI with a breakdown
by event type (OA, CA, H, RERA) as stacked colored bars.

Copyright (c) 2019-2025 The OSCAR Team
License: GPL v3
"""

from datetime import date
from typing import List, Optional

from PyQt6.QtGui import QColor

from .summary_chart import SummaryChart

# Try to import DaySummary
try:
    from sleeplib.statistics import DaySummary
except ImportError:
    DaySummary = None


# Event colors matching OSCAR C++ (from daily_view.py)
COLOR_OA = QColor(0x40, 0xaf, 0xbf)      # Obstructive Apnea - Teal
COLOR_CA = QColor(0xb2, 0x54, 0xcd)      # Clear Airway - Purple
COLOR_H = QColor(0x40, 0x40, 0xff)       # Hypopnea - Blue
COLOR_RERA = QColor(0xff, 0xff, 0x80)    # RERA - Yellow


class AHIChart(SummaryChart):
    """Stacked bar chart showing AHI breakdown by event type.

    Each bar shows the total AHI for a day, with colors indicating
    the proportion of each event type:
    - Obstructive Apneas (OA) - Teal
    - Central/Clear Airway (CA) - Purple
    - Hypopneas (H) - Blue
    - RERA - Yellow (optional, included in RDI)

    The chart displays events per hour (cph) for each event type,
    which when stacked gives the total AHI.
    """

    def __init__(self, include_rera: bool = False, parent=None):
        """Initialize the AHIChart.

        Args:
            include_rera: Whether to include RERA in the display (RDI mode).
            parent: Parent widget.
        """
        title = "RDI Trend" if include_rera else "AHI Trend"
        super().__init__(
            title=title,
            y_label="Events",
            y_unit="per hour",
            parent=parent
        )

        self._include_rera = include_rera
        self._summaries: List['DaySummary'] = []

        # Add severity threshold lines
        self._add_severity_lines()

    def _add_severity_lines(self) -> None:
        """Add horizontal lines indicating AHI severity thresholds."""
        # Mild: 5-15
        self.add_horizontal_line(5, QColor(0, 200, 0, 100))
        # Moderate: 15-30
        self.add_horizontal_line(15, QColor(255, 165, 0, 100))
        # Severe: >30
        self.add_horizontal_line(30, QColor(255, 0, 0, 100))

    @property
    def include_rera(self) -> bool:
        """Return whether RERA is included."""
        return self._include_rera

    @include_rera.setter
    def include_rera(self, value: bool) -> None:
        """Set whether to include RERA."""
        self._include_rera = value
        self.title = "RDI Trend" if value else "AHI Trend"
        # Refresh display if we have data
        if self._summaries:
            self.set_data(self._summaries)

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

        # Calculate events per hour for each type
        oa_cph = []
        ca_cph = []
        h_cph = []
        rera_cph = []

        for s in summaries:
            hours = s.hours if s.hours > 0 else 1.0  # Avoid division by zero
            oa_cph.append(s.oa_count / hours)
            ca_cph.append(s.ca_count / hours)
            h_cph.append(s.h_count / hours)
            if self._include_rera:
                rera_cph.append(s.rera_count / hours)

        # Build stacked bars
        # Order from bottom to top: OA, CA, H, (RERA)
        if self._include_rera:
            value_lists = [oa_cph, ca_cph, h_cph, rera_cph]
            colors = [COLOR_OA, COLOR_CA, COLOR_H, COLOR_RERA]
        else:
            value_lists = [oa_cph, ca_cph, h_cph]
            colors = [COLOR_OA, COLOR_CA, COLOR_H]

        self.add_stacked_bars(value_lists, colors)

        # Auto-range to fit data
        self.auto_range()

    def get_ahi_for_date(self, d: date) -> Optional[float]:
        """Get the AHI value for a specific date.

        Args:
            d: The date to look up.

        Returns:
            The AHI value, or None if not found.
        """
        for s in self._summaries:
            if s.date == d:
                return s.ahi
        return None

    def get_summary_for_date(self, d: date) -> Optional['DaySummary']:
        """Get the DaySummary for a specific date.

        Args:
            d: The date to look up.

        Returns:
            The DaySummary, or None if not found.
        """
        for s in self._summaries:
            if s.date == d:
                return s
        return None
