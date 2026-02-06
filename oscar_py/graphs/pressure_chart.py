"""
Pressure Chart - Min/Avg/Max Pressure Display

This module provides a chart that displays daily pressure statistics
with range bars showing min/max and markers for average.

Copyright (c) 2019-2025 The OSCAR Team
License: GPL v3
"""

from datetime import date
from typing import List, Optional

import numpy as np
import pyqtgraph as pg
from PyQt6.QtGui import QColor

from .summary_chart import SummaryChart

# Try to import DaySummary
try:
    from sleeplib.statistics import DaySummary
except ImportError:
    DaySummary = None


# Pressure chart colors
COLOR_PRESSURE_RANGE = QColor(100, 100, 200, 180)  # Blue with transparency
COLOR_PRESSURE_AVG = QColor(200, 50, 50)  # Red for average marker


class PressureChart(SummaryChart):
    """Chart showing daily pressure statistics.

    Each day displays:
    - A vertical bar from min to max pressure
    - A marker showing the average pressure

    This gives a quick view of the pressure range and typical
    pressure for each day.
    """

    def __init__(self, parent=None):
        """Initialize the PressureChart.

        Args:
            parent: Parent widget.
        """
        super().__init__(
            title="Pressure",
            y_label="Pressure",
            y_unit="cmH2O",
            parent=parent
        )

        self._summaries: List['DaySummary'] = []
        self._range_items: List[pg.ErrorBarItem] = []
        self._avg_scatter = None

        # Set Y-axis range suitable for pressure (typically 4-20 cmH2O)
        self.setYRange(0, 20, padding=0.05)

    def set_data(self, summaries: List['DaySummary']) -> None:
        """Set the data to display.

        Args:
            summaries: List of DaySummary objects to display.
        """
        self._summaries = summaries

        # Clear existing items
        self.clear_bars()
        self._clear_pressure_items()

        if not summaries:
            return

        # Extract dates and set up X-axis
        dates = [s.date for s in summaries]
        self.set_dates(dates)

        # Extract pressure data
        x_vals = []
        y_min = []
        y_max = []
        y_avg = []

        for i, s in enumerate(summaries):
            # Only include if we have valid pressure data
            if s.pressure_avg > 0:
                x_vals.append(i)
                y_min.append(s.pressure_min)
                y_max.append(s.pressure_max)
                y_avg.append(s.pressure_avg)

        if not x_vals:
            return

        # Convert to numpy arrays
        x = np.array(x_vals, dtype=np.float64)
        mins = np.array(y_min, dtype=np.float64)
        maxs = np.array(y_max, dtype=np.float64)
        avgs = np.array(y_avg, dtype=np.float64)

        # Add range bars (using ErrorBarItem for vertical ranges)
        # ErrorBarItem expects: x, y (center), height
        centers = (mins + maxs) / 2
        heights = (maxs - mins) / 2  # Half-height for error bar

        error_bar = pg.ErrorBarItem(
            x=x,
            y=centers,
            height=heights,
            beam=0.3,
            pen=pg.mkPen(COLOR_PRESSURE_RANGE, width=2)
        )
        self.addItem(error_bar)
        self._range_items.append(error_bar)

        # Add average markers
        self._avg_scatter = pg.ScatterPlotItem(
            x=x,
            y=avgs,
            size=8,
            pen=pg.mkPen(COLOR_PRESSURE_AVG.darker(120)),
            brush=pg.mkBrush(COLOR_PRESSURE_AVG),
            symbol='o'
        )
        self.addItem(self._avg_scatter)

        # Auto-range
        self.auto_range_x()
        self._auto_range_pressure(mins, maxs)

    def _clear_pressure_items(self) -> None:
        """Remove pressure-specific items."""
        for item in self._range_items:
            self.removeItem(item)
        self._range_items.clear()

        if self._avg_scatter is not None:
            self.removeItem(self._avg_scatter)
            self._avg_scatter = None

    def _auto_range_pressure(
        self,
        mins: np.ndarray,
        maxs: np.ndarray,
        padding: float = 0.1
    ) -> None:
        """Set Y-axis range based on pressure data.

        Args:
            mins: Array of minimum pressures.
            maxs: Array of maximum pressures.
            padding: Padding factor.
        """
        if len(mins) == 0 or len(maxs) == 0:
            self.setYRange(0, 20, padding=0.05)
            return

        min_val = float(np.min(mins))
        max_val = float(np.max(maxs))

        # Ensure reasonable range
        min_val = max(0, min_val - 1)
        max_val = max_val + 1

        # Add padding
        range_val = max_val - min_val
        padding_val = range_val * padding

        self.setYRange(min_val - padding_val, max_val + padding_val, padding=0)

    def get_pressure_for_date(self, d: date) -> Optional[dict]:
        """Get pressure statistics for a specific date.

        Args:
            d: The date to look up.

        Returns:
            Dictionary with min, avg, max pressure, or None if not found.
        """
        for s in self._summaries:
            if s.date == d:
                return {
                    'min': s.pressure_min,
                    'avg': s.pressure_avg,
                    'max': s.pressure_max
                }
        return None
