"""
SummaryChart - Base Chart for Date-Based Summary Data

This module provides a base class for creating bar charts that display
summary data over date ranges (AHI trends, usage hours, pressure, etc.)

Copyright (c) 2019-2025 The OSCAR Team
License: GPL v3
"""

from datetime import date
from typing import List, Optional, Dict, Any

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor

from .date_axis import DateAxisItem


class SummaryChart(pg.PlotWidget):
    """Base chart widget for date-based summary data.

    This widget provides the foundation for bar charts that display
    daily summary statistics over a date range. Subclasses implement
    specific visualizations (AHI, usage hours, pressure, etc.)

    Features:
        - Date-based X-axis with intelligent formatting
        - Bar chart rendering with customizable colors
        - Support for click-to-navigate to specific days
        - Automatic Y-axis scaling

    Signals:
        dayClicked: Emitted when a bar is clicked with the date.
    """

    dayClicked = pyqtSignal(object)  # date

    # Default colors
    DEFAULT_BACKGROUND = QColor(30, 30, 30)
    DEFAULT_FOREGROUND = QColor(200, 200, 200)
    DEFAULT_BAR_COLOR = QColor(0, 119, 182)
    DEFAULT_GRID_ALPHA = 0.3

    def __init__(
        self,
        title: str = "",
        y_label: str = "",
        y_unit: str = "",
        parent=None
    ):
        """Initialize the SummaryChart.

        Args:
            title: Chart title displayed at top.
            y_label: Y-axis label.
            y_unit: Y-axis unit string (e.g., "hours", "events/hr").
            parent: Parent widget.
        """
        # Create date axis for bottom
        self._date_axis = DateAxisItem(orientation='bottom')

        super().__init__(
            parent=parent,
            axisItems={'bottom': self._date_axis},
            background=self.DEFAULT_BACKGROUND
        )

        self._title = title
        self._y_label = y_label
        self._y_unit = y_unit

        # Data storage
        self._dates: List[date] = []
        self._date_to_index: Dict[date, int] = {}
        self._bar_items: List[pg.BarGraphItem] = []

        # Configure plot
        self._setup_plot()

        # Connect click signal
        self.scene().sigMouseClicked.connect(self._on_mouse_clicked)

    def _setup_plot(self) -> None:
        """Configure the plot appearance."""
        # Set title
        if self._title:
            self.setTitle(self._title, color=self.DEFAULT_FOREGROUND)

        # Configure Y-axis
        y_axis = self.getPlotItem().getAxis('left')
        label = self._y_label
        if self._y_unit:
            label = f"{label} ({self._y_unit})" if label else self._y_unit
        if label:
            y_axis.setLabel(label, color=self.DEFAULT_FOREGROUND)

        # Configure axes style
        for axis_name in ['left', 'bottom']:
            axis = self.getPlotItem().getAxis(axis_name)
            axis.setPen(pg.mkPen(self.DEFAULT_FOREGROUND))
            axis.setTextPen(pg.mkPen(self.DEFAULT_FOREGROUND))

        # Configure grid
        self.showGrid(x=True, y=True, alpha=self.DEFAULT_GRID_ALPHA)

        # Configure interaction
        self.setMouseEnabled(x=True, y=True)

        # Set Y minimum to 0 for bar charts
        self.setYRange(0, 10, padding=0.1)

    def set_dates(self, dates: List[date]) -> None:
        """Set the date list for the X-axis.

        Args:
            dates: List of dates to display.
        """
        self._dates = sorted(dates)
        self._date_to_index = {d: i for i, d in enumerate(self._dates)}

        # Update date axis mapping
        date_map = {i: d for i, d in enumerate(self._dates)}
        self._date_axis.set_date_map(date_map)

        # Set reference date if we have dates
        if self._dates:
            self._date_axis.reference_date = self._dates[0]

    def clear_bars(self) -> None:
        """Remove all bar items from the chart."""
        for item in self._bar_items:
            self.removeItem(item)
        self._bar_items.clear()

    def add_bars(
        self,
        values: List[float],
        color: QColor = None,
        width: float = 0.6
    ) -> pg.BarGraphItem:
        """Add a set of bars to the chart.

        Args:
            values: List of values (same length as dates).
            color: Bar color (defaults to DEFAULT_BAR_COLOR).
            width: Bar width (0-1).

        Returns:
            The created BarGraphItem.
        """
        if color is None:
            color = self.DEFAULT_BAR_COLOR

        if len(values) != len(self._dates):
            raise ValueError(
                f"Values length ({len(values)}) must match dates length ({len(self._dates)})"
            )

        x = np.arange(len(values))
        y = np.array(values, dtype=np.float64)

        bar_item = pg.BarGraphItem(
            x=x,
            height=y,
            width=width,
            brush=pg.mkBrush(color),
            pen=pg.mkPen(color.darker(120))
        )

        self.addItem(bar_item)
        self._bar_items.append(bar_item)

        return bar_item

    def add_colored_bars(
        self,
        values: List[float],
        colors: List[QColor],
        width: float = 0.6
    ) -> List[pg.BarGraphItem]:
        """Add bars with individual colors.

        Args:
            values: List of values (same length as dates).
            colors: List of colors for each bar.
            width: Bar width (0-1).

        Returns:
            List of created BarGraphItems (one per bar for individual colors).
        """
        if len(values) != len(self._dates):
            raise ValueError(
                f"Values length ({len(values)}) must match dates length ({len(self._dates)})"
            )

        if len(colors) != len(values):
            raise ValueError(
                f"Colors length ({len(colors)}) must match values length ({len(values)})"
            )

        items = []
        for i, (value, color) in enumerate(zip(values, colors)):
            bar_item = pg.BarGraphItem(
                x=[i],
                height=[value],
                width=width,
                brush=pg.mkBrush(color),
                pen=pg.mkPen(color.darker(120))
            )
            self.addItem(bar_item)
            self._bar_items.append(bar_item)
            items.append(bar_item)

        return items

    def add_stacked_bars(
        self,
        value_lists: List[List[float]],
        colors: List[QColor],
        width: float = 0.6
    ) -> List[pg.BarGraphItem]:
        """Add stacked bars (multiple series stacked on each other).

        Args:
            value_lists: List of value lists (one per stack layer).
            colors: List of colors for each layer.
            width: Bar width (0-1).

        Returns:
            List of created BarGraphItems.
        """
        if not value_lists:
            return []

        n_dates = len(self._dates)
        for values in value_lists:
            if len(values) != n_dates:
                raise ValueError(
                    f"All value lists must have length {n_dates}"
                )

        if len(colors) != len(value_lists):
            raise ValueError(
                f"Colors length ({len(colors)}) must match value_lists length ({len(value_lists)})"
            )

        items = []
        x = np.arange(n_dates)
        bottoms = np.zeros(n_dates)

        for values, color in zip(value_lists, colors):
            y = np.array(values, dtype=np.float64)

            bar_item = pg.BarGraphItem(
                x=x,
                height=y,
                y0=bottoms,
                width=width,
                brush=pg.mkBrush(color),
                pen=pg.mkPen(color.darker(120))
            )

            self.addItem(bar_item)
            self._bar_items.append(bar_item)
            items.append(bar_item)

            bottoms = bottoms + y

        return items

    def add_horizontal_line(
        self,
        y_value: float,
        color: QColor = None,
        style: Qt.PenStyle = Qt.PenStyle.DashLine,
        width: float = 1.0
    ) -> pg.InfiniteLine:
        """Add a horizontal reference line.

        Args:
            y_value: Y position of the line.
            color: Line color.
            style: Pen style (solid, dashed, etc.)
            width: Line width.

        Returns:
            The created InfiniteLine.
        """
        if color is None:
            color = self.DEFAULT_FOREGROUND

        pen = pg.mkPen(color, width=width, style=style)
        line = pg.InfiniteLine(
            pos=y_value,
            angle=0,
            pen=pen,
            movable=False
        )
        self.addItem(line)
        return line

    def auto_range_y(self, padding: float = 0.1) -> None:
        """Auto-scale Y axis to fit data with padding.

        Args:
            padding: Padding factor (0.1 = 10% padding).
        """
        # Find max value across all bar items
        max_val = 0.0

        for item in self._bar_items:
            if hasattr(item, 'opts') and 'height' in item.opts:
                heights = item.opts['height']
                y0 = item.opts.get('y0', 0)
                if isinstance(y0, np.ndarray):
                    max_heights = heights + y0
                else:
                    max_heights = heights + y0
                if len(max_heights) > 0:
                    max_val = max(max_val, float(np.max(max_heights)))

        if max_val > 0:
            self.setYRange(0, max_val * (1 + padding), padding=0)
        else:
            self.setYRange(0, 10, padding=0.1)

    def auto_range_x(self, padding: float = 0.5) -> None:
        """Auto-scale X axis to show all bars.

        Args:
            padding: Padding in bar units.
        """
        if self._dates:
            n = len(self._dates)
            self.setXRange(-padding, n - 1 + padding, padding=0)

    def auto_range(self) -> None:
        """Auto-scale both axes to fit all data."""
        self.auto_range_x()
        self.auto_range_y()

    def _on_mouse_clicked(self, event) -> None:
        """Handle mouse click events.

        Args:
            event: The mouse click event.
        """
        if event.button() != Qt.MouseButton.LeftButton:
            return

        # Get click position in scene coordinates
        pos = event.scenePos()

        # Convert to data coordinates
        view_box = self.getPlotItem().getViewBox()
        mouse_point = view_box.mapSceneToView(pos)

        # Find which bar was clicked
        x = mouse_point.x()
        index = int(round(x))

        if 0 <= index < len(self._dates):
            clicked_date = self._dates[index]
            self.dayClicked.emit(clicked_date)

    def get_date_at_index(self, index: int) -> Optional[date]:
        """Get the date at the given X index.

        Args:
            index: The X-axis index.

        Returns:
            The date, or None if out of range.
        """
        if 0 <= index < len(self._dates):
            return self._dates[index]
        return None

    def get_index_for_date(self, d: date) -> Optional[int]:
        """Get the X index for a given date.

        Args:
            d: The date to look up.

        Returns:
            The X-axis index, or None if not found.
        """
        return self._date_to_index.get(d)

    @property
    def dates(self) -> List[date]:
        """Return the list of dates."""
        return self._dates.copy()

    @property
    def title(self) -> str:
        """Return the chart title."""
        return self._title

    @title.setter
    def title(self, value: str) -> None:
        """Set the chart title."""
        self._title = value
        self.setTitle(value, color=self.DEFAULT_FOREGROUND)
