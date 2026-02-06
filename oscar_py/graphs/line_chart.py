"""
LineChart - Line Chart Widget for Waveform Data

This module provides a PyQtGraph-based line chart widget optimized
for displaying large waveform datasets with efficient downsampling.

Ported from OSCAR C++ gLineChart class.

Copyright (c) 2019-2025 The OSCAR Team
License: GPL v3
"""

from typing import Optional, Tuple, List
import numpy as np

import pyqtgraph as pg
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPen, QBrush

from .time_axis import TimeAxisItem

# Try to import EventList from sleeplib
try:
    from sleeplib.event import EventList
except ImportError:
    EventList = None


class LineChart(pg.PlotWidget):
    """Line chart widget for displaying waveform data.

    This widget efficiently renders large datasets using automatic
    downsampling and GPU acceleration when available.

    Features:
        - Automatic downsampling for large datasets
        - GPU-accelerated rendering with OpenGL
        - Customizable line color and style
        - Support for highlighted regions
        - Linked X-axis for synchronized scrolling

    Signals:
        timeRangeChanged: Emitted when the visible time range changes
            Args: (start_ms: float, end_ms: float)
        dataClicked: Emitted when data is clicked
            Args: (time_ms: float, value: float)

    Attributes:
        title: Chart title
        y_label: Y-axis label
        y_unit: Y-axis unit string
        color: Line color
    """

    timeRangeChanged = pyqtSignal(float, float)
    dataClicked = pyqtSignal(float, float)

    # Default colors
    DEFAULT_LINE_COLOR = QColor(0, 119, 182)  # Blue
    DEFAULT_REGION_COLOR = QColor(255, 255, 0, 50)  # Semi-transparent yellow
    DEFAULT_BACKGROUND = QColor(30, 30, 30)  # Dark background
    DEFAULT_FOREGROUND = QColor(200, 200, 200)  # Light foreground

    # Downsampling thresholds
    DOWNSAMPLE_THRESHOLD = 5000  # Start downsampling above this many points
    TARGET_POINTS = 2000  # Target number of points after downsampling

    def __init__(
        self,
        title: str = "",
        y_label: str = "",
        y_unit: str = "",
        color: Optional[QColor] = None,
        parent=None
    ):
        """Initialize the LineChart.

        Args:
            title: Chart title displayed at top
            y_label: Y-axis label
            y_unit: Y-axis unit string (e.g., "cmH2O", "L/min")
            color: Line color (defaults to blue)
            parent: Parent widget
        """
        # Create custom time axis for bottom
        time_axis = TimeAxisItem(orientation='bottom')

        super().__init__(
            parent=parent,
            axisItems={'bottom': time_axis},
            background=self.DEFAULT_BACKGROUND
        )

        # Store properties
        self._title = title
        self._y_label = y_label
        self._y_unit = y_unit
        self._color = color or self.DEFAULT_LINE_COLOR

        # Data storage
        self._times: Optional[np.ndarray] = None  # Timestamps in ms
        self._values: Optional[np.ndarray] = None  # Data values
        self._raw_times: Optional[np.ndarray] = None  # Original times (for lookup)
        self._raw_values: Optional[np.ndarray] = None  # Original values

        # Plot items
        self._line_item: Optional[pg.PlotDataItem] = None
        self._regions: List[pg.LinearRegionItem] = []

        # Configure plot
        self._setup_plot()

    def _setup_plot(self) -> None:
        """Configure the plot appearance and behavior."""
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
        self.showGrid(x=True, y=True, alpha=0.3)

        # Configure interaction
        self.setMouseEnabled(x=True, y=True)

        # Enable auto-range initially
        self.enableAutoRange()

        # Connect range change signal
        self.sigXRangeChanged.connect(self._on_x_range_changed)

        # Configure view for efficient rendering
        view_box = self.getPlotItem().getViewBox()
        view_box.setDefaultPadding(0.02)

    def set_data(
        self,
        times: np.ndarray,
        values: np.ndarray,
        auto_range: bool = True
    ) -> None:
        """Set waveform data for display.

        Args:
            times: Array of timestamps in milliseconds since epoch
            values: Array of data values (same length as times)
            auto_range: Whether to automatically adjust view to show all data
        """
        if len(times) != len(values):
            raise ValueError(f"times ({len(times)}) and values ({len(values)}) must have same length")

        # Store original data
        self._raw_times = np.asarray(times, dtype=np.float64)
        self._raw_values = np.asarray(values, dtype=np.float64)

        # Apply downsampling if needed
        if len(self._raw_times) > self.DOWNSAMPLE_THRESHOLD:
            self._times, self._values = self._downsample(
                self._raw_times, self._raw_values
            )
        else:
            self._times = self._raw_times
            self._values = self._raw_values

        # Update or create plot item
        self._update_plot_item()

        # Auto-range if requested
        if auto_range:
            self.autoRange()

    def set_event_list(self, event_list: 'EventList', auto_range: bool = True) -> None:
        """Set data from an EventList object.

        Args:
            event_list: EventList containing waveform or event data
            auto_range: Whether to automatically adjust view to show all data

        Raises:
            ImportError: If EventList is not available
            ValueError: If event_list is empty
        """
        if EventList is None:
            raise ImportError("EventList not available - sleeplib.event not found")

        if event_list.count == 0:
            raise ValueError("EventList is empty")

        # Extract data from EventList
        times = event_list.timestamps()
        values = event_list.physical_data()

        # Set data
        self.set_data(times, values, auto_range)

    def _downsample(
        self,
        times: np.ndarray,
        values: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Downsample data for efficient display.

        Uses a min-max preserving algorithm that maintains the visual
        appearance of the waveform while reducing the number of points.

        Args:
            times: Original timestamps
            values: Original values

        Returns:
            Tuple of (downsampled_times, downsampled_values)
        """
        n_points = len(times)
        if n_points <= self.TARGET_POINTS:
            return times, values

        # Calculate bin size
        bin_size = n_points // self.TARGET_POINTS

        # Number of bins
        n_bins = n_points // bin_size

        # Reshape for binning (may truncate some points)
        truncated_len = n_bins * bin_size
        times_binned = times[:truncated_len].reshape(n_bins, bin_size)
        values_binned = values[:truncated_len].reshape(n_bins, bin_size)

        # For each bin, keep min and max values to preserve peaks
        mins = values_binned.min(axis=1)
        maxs = values_binned.max(axis=1)
        min_times = times_binned[:, 0]  # Use start of bin for min
        max_times = times_binned[:, 0]  # Use start of bin for max

        # Interleave min and max values
        result_times = np.empty(n_bins * 2, dtype=np.float64)
        result_values = np.empty(n_bins * 2, dtype=np.float64)

        result_times[0::2] = min_times
        result_times[1::2] = max_times
        result_values[0::2] = mins
        result_values[1::2] = maxs

        return result_times, result_values

    def _update_plot_item(self) -> None:
        """Update or create the plot item with current data."""
        if self._times is None or self._values is None:
            return

        pen = pg.mkPen(color=self._color, width=1)

        if self._line_item is None:
            # Create new plot item
            # Note: clipToView and downsample options removed for PyQtGraph 0.14 compatibility
            self._line_item = self.plot(
                self._times,
                self._values,
                pen=pen,
                antialias=True
            )
        else:
            # Update existing plot item
            self._line_item.setData(self._times, self._values)
            self._line_item.setPen(pen)

    def set_color(self, color: QColor) -> None:
        """Set the line color.

        Args:
            color: New line color
        """
        self._color = color
        if self._line_item is not None:
            self._line_item.setPen(pg.mkPen(color=color, width=1))

    def add_region(
        self,
        start_ms: float,
        end_ms: float,
        color: Optional[QColor] = None,
        movable: bool = False
    ) -> pg.LinearRegionItem:
        """Add a highlighted region to the chart.

        Args:
            start_ms: Start time in milliseconds
            end_ms: End time in milliseconds
            color: Region color (defaults to semi-transparent yellow)
            movable: Whether the region can be moved by the user

        Returns:
            The created LinearRegionItem
        """
        if color is None:
            color = self.DEFAULT_REGION_COLOR

        region = pg.LinearRegionItem(
            values=[start_ms, end_ms],
            brush=pg.mkBrush(color),
            pen=pg.mkPen(color.darker()),
            movable=movable
        )

        self.addItem(region)
        self._regions.append(region)

        return region

    def clear_regions(self) -> None:
        """Remove all highlighted regions."""
        for region in self._regions:
            self.removeItem(region)
        self._regions.clear()

    def clear(self) -> None:
        """Clear all data and regions from the chart."""
        # Clear data
        self._times = None
        self._values = None
        self._raw_times = None
        self._raw_values = None

        # Remove line item
        if self._line_item is not None:
            self.removeItem(self._line_item)
            self._line_item = None

        # Clear regions
        self.clear_regions()

    def get_value_at_time(self, time_ms: float) -> Optional[float]:
        """Get the interpolated value at a specific time.

        Args:
            time_ms: Timestamp in milliseconds

        Returns:
            Interpolated value, or None if outside data range
        """
        if self._raw_times is None or self._raw_values is None:
            return None

        if len(self._raw_times) == 0:
            return None

        if time_ms < self._raw_times[0] or time_ms > self._raw_times[-1]:
            return None

        # Find nearest index
        idx = np.searchsorted(self._raw_times, time_ms)

        if idx == 0:
            return float(self._raw_values[0])
        if idx >= len(self._raw_times):
            return float(self._raw_values[-1])

        # Linear interpolation
        t0 = self._raw_times[idx - 1]
        t1 = self._raw_times[idx]
        v0 = self._raw_values[idx - 1]
        v1 = self._raw_values[idx]

        if t1 == t0:
            return float(v0)

        fraction = (time_ms - t0) / (t1 - t0)
        return float(v0 + fraction * (v1 - v0))

    def _on_x_range_changed(self, view_box, range_tuple) -> None:
        """Handle X-axis range changes.

        Args:
            view_box: The ViewBox that changed
            range_tuple: Tuple of (x_min, x_max) or [[x_min, x_max], [y_min, y_max]]
        """
        try:
            if range_tuple is None:
                return

            # Handle different range tuple formats from PyQtGraph
            if isinstance(range_tuple, (list, tuple)):
                if len(range_tuple) >= 2:
                    # Check if first element is a list/tuple (nested format)
                    if isinstance(range_tuple[0], (list, tuple)):
                        x_range = range_tuple[0]
                        if len(x_range) >= 2:
                            self.timeRangeChanged.emit(float(x_range[0]), float(x_range[1]))
                    else:
                        # Simple (x_min, x_max) format
                        self.timeRangeChanged.emit(float(range_tuple[0]), float(range_tuple[1]))
        except (TypeError, IndexError, ValueError):
            # Silently ignore invalid range tuples
            pass

    # Properties

    @property
    def title(self) -> str:
        """Return the chart title."""
        return self._title

    @title.setter
    def title(self, value: str) -> None:
        """Set the chart title."""
        self._title = value
        self.setTitle(value, color=self.DEFAULT_FOREGROUND)

    @property
    def y_label(self) -> str:
        """Return the Y-axis label."""
        return self._y_label

    @y_label.setter
    def y_label(self, value: str) -> None:
        """Set the Y-axis label."""
        self._y_label = value
        self._update_y_axis_label()

    @property
    def y_unit(self) -> str:
        """Return the Y-axis unit."""
        return self._y_unit

    @y_unit.setter
    def y_unit(self, value: str) -> None:
        """Set the Y-axis unit."""
        self._y_unit = value
        self._update_y_axis_label()

    def _update_y_axis_label(self) -> None:
        """Update the Y-axis label text."""
        y_axis = self.getPlotItem().getAxis('left')
        label = self._y_label
        if self._y_unit:
            label = f"{label} ({self._y_unit})" if label else self._y_unit
        if label:
            y_axis.setLabel(label, color=self.DEFAULT_FOREGROUND)

    @property
    def color(self) -> QColor:
        """Return the line color."""
        return self._color

    @color.setter
    def color(self, value: QColor) -> None:
        """Set the line color."""
        self.set_color(value)

    @property
    def data_range(self) -> Optional[Tuple[float, float, float, float]]:
        """Return the data range as (x_min, x_max, y_min, y_max)."""
        if self._raw_times is None or self._raw_values is None:
            return None

        return (
            float(self._raw_times.min()),
            float(self._raw_times.max()),
            float(self._raw_values.min()),
            float(self._raw_values.max())
        )
