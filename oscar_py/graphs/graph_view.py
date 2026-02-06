"""
GraphView - Main Graph Container Widget

This module provides the main graph container that manages multiple
stacked graph panels with synchronized X-axis (time) scrolling.

Ported from OSCAR C++ gGraphView class.

Copyright (c) 2019-2025 The OSCAR Team
License: GPL v3
"""

from typing import Optional, Dict, List, Tuple
import numpy as np

import pyqtgraph as pg
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QScrollArea, QSplitter,
    QFrame, QSizePolicy
)
from PyQt6.QtGui import QColor, QWheelEvent, QMouseEvent

from .line_chart import LineChart
from .time_axis import TimeAxisItem

# Configure PyQtGraph for optimal performance
pg.setConfigOptions(antialias=True, useOpenGL=True)

# Try to import EventList from sleeplib
try:
    from sleeplib.event import EventList
except ImportError:
    EventList = None


class GraphPanel(QFrame):
    """Container for a single graph within GraphView.

    This wraps a LineChart and provides resize handles and
    title display.

    Attributes:
        name: Graph name/identifier
        chart: The LineChart widget
        height: Preferred height in pixels
    """

    def __init__(
        self,
        name: str,
        height: int = 150,
        parent: Optional[QWidget] = None
    ):
        """Initialize the GraphPanel.

        Args:
            name: Graph name/identifier
            height: Preferred height in pixels
            parent: Parent widget
        """
        super().__init__(parent)
        self.name = name
        self._preferred_height = height

        # Create chart
        self.chart = LineChart(title=name, parent=self)

        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.chart)

        # Size policy
        self.setMinimumHeight(50)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def sizeHint(self):
        """Return the preferred size."""
        from PyQt6.QtCore import QSize
        return QSize(400, self._preferred_height)


class GraphView(QWidget):
    """Main graph container with multiple stacked graph panels.

    This widget manages multiple LineChart panels arranged vertically
    with synchronized X-axis (time) scrolling and zooming.

    Features:
        - Multiple stacked graph panels
        - Synchronized X-axis across all graphs
        - Mouse wheel zoom
        - Click and drag to pan
        - Time range selection

    Signals:
        timeRangeChanged: Emitted when visible time range changes
            Args: (start_ms: float, end_ms: float)
        graphAdded: Emitted when a graph is added
            Args: (name: str)
        graphRemoved: Emitted when a graph is removed
            Args: (name: str)

    Attributes:
        graphs: Dictionary of graph name to GraphPanel
    """

    timeRangeChanged = pyqtSignal(float, float)
    graphAdded = pyqtSignal(str)
    graphRemoved = pyqtSignal(str)

    # Zoom configuration
    ZOOM_FACTOR = 0.1  # 10% zoom per wheel step
    MIN_TIME_RANGE_MS = 1000  # Minimum 1 second visible
    MAX_ZOOM_FACTOR = 100  # Maximum zoom level

    # Colors
    BACKGROUND_COLOR = QColor(30, 30, 30)
    SPLITTER_COLOR = QColor(60, 60, 60)

    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize the GraphView.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)

        # Graph storage
        self._graphs: Dict[str, GraphPanel] = {}
        self._graph_order: List[str] = []

        # Time range
        self._time_start: float = 0  # Start of visible range (ms)
        self._time_end: float = 0  # End of visible range (ms)
        self._data_start: float = 0  # Start of all data (ms)
        self._data_end: float = 0  # End of all data (ms)

        # Interaction state
        self._is_panning = False
        self._pan_start_x = 0
        self._pan_start_time = 0.0

        # Sync timer for batching range updates
        self._sync_timer = QTimer()
        self._sync_timer.setSingleShot(True)
        self._sync_timer.setInterval(16)  # ~60fps
        self._sync_timer.timeout.connect(self._do_sync_x_axis)
        self._pending_range: Optional[Tuple[float, float]] = None

        # Setup UI
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup the user interface."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Scroll area to allow scrolling through many graphs
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        # Container widget for the splitter
        self._scroll_container = QWidget()
        self._scroll_container_layout = QVBoxLayout(self._scroll_container)
        self._scroll_container_layout.setContentsMargins(0, 0, 0, 0)
        self._scroll_container_layout.setSpacing(0)

        # Splitter for resizable graph panels
        self._splitter = QSplitter(Qt.Orientation.Vertical)
        self._splitter.setHandleWidth(4)
        self._splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background-color: {self.SPLITTER_COLOR.name()};
            }}
            QSplitter::handle:hover {{
                background-color: #888888;
            }}
        """)

        self._scroll_container_layout.addWidget(self._splitter)
        self._scroll_area.setWidget(self._scroll_container)
        layout.addWidget(self._scroll_area)

        # Background color
        self.setStyleSheet(f"background-color: {self.BACKGROUND_COLOR.name()};")

        # Accept mouse events
        self.setMouseTracking(True)

    def add_graph(
        self,
        name: str,
        height: int = 150,
        y_label: str = "",
        y_unit: str = "",
        color: Optional[QColor] = None
    ) -> LineChart:
        """Add a new graph panel.

        Args:
            name: Unique name for the graph
            height: Preferred height in pixels
            y_label: Y-axis label
            y_unit: Y-axis unit string
            color: Line color

        Returns:
            The created LineChart widget

        Raises:
            ValueError: If a graph with the same name already exists
        """
        if name in self._graphs:
            raise ValueError(f"Graph '{name}' already exists")

        # Create panel
        panel = GraphPanel(name, height, parent=self._splitter)

        # Ensure minimum readable height
        panel.setMinimumHeight(max(height, 60))
        panel.setFixedHeight(height)

        # Configure chart
        if y_label:
            panel.chart.y_label = y_label
        if y_unit:
            panel.chart.y_unit = y_unit
        if color:
            panel.chart.color = color

        # Connect chart signals
        panel.chart.timeRangeChanged.connect(self._on_chart_range_changed)

        # Add to splitter
        self._splitter.addWidget(panel)

        # Store reference
        self._graphs[name] = panel
        self._graph_order.append(name)

        # Link X-axis
        self._link_x_axes()

        # Update container size to fit all graphs
        self._update_container_size()

        # Emit signal
        self.graphAdded.emit(name)

        return panel.chart

    def _update_container_size(self) -> None:
        """Update the scroll container size to fit all graphs."""
        total_height = 0
        for panel in self._graphs.values():
            total_height += panel._preferred_height + 4  # 4 for splitter handle

        # Set minimum height for the scroll container
        self._scroll_container.setMinimumHeight(total_height)

    def remove_graph(self, name: str) -> bool:
        """Remove a graph panel.

        Args:
            name: Name of the graph to remove

        Returns:
            True if graph was removed, False if not found
        """
        if name not in self._graphs:
            return False

        panel = self._graphs.pop(name)
        self._graph_order.remove(name)

        # Remove from splitter and delete
        panel.setParent(None)
        panel.deleteLater()

        # Re-link axes
        self._link_x_axes()

        # Update container size
        self._update_container_size()

        # Emit signal
        self.graphRemoved.emit(name)

        return True

    def get_graph(self, name: str) -> Optional[LineChart]:
        """Get a graph by name.

        Args:
            name: Graph name

        Returns:
            LineChart widget or None if not found
        """
        panel = self._graphs.get(name)
        return panel.chart if panel else None

    def set_time_range(self, start_ms: float, end_ms: float) -> None:
        """Set the visible time range for all graphs.

        Args:
            start_ms: Start time in milliseconds since epoch
            end_ms: End time in milliseconds since epoch
        """
        if start_ms >= end_ms:
            return

        # Clamp to data range
        if self._data_start > 0 and self._data_end > 0:
            if start_ms < self._data_start:
                start_ms = self._data_start
            if end_ms > self._data_end:
                end_ms = self._data_end

        # Enforce minimum range
        if end_ms - start_ms < self.MIN_TIME_RANGE_MS:
            end_ms = start_ms + self.MIN_TIME_RANGE_MS

        self._time_start = start_ms
        self._time_end = end_ms

        # Apply to all charts
        self._apply_time_range()

        # Emit signal
        self.timeRangeChanged.emit(start_ms, end_ms)

    def _apply_time_range(self) -> None:
        """Apply the current time range to all charts."""
        for panel in self._graphs.values():
            view_box = panel.chart.getPlotItem().getViewBox()
            view_box.blockSignals(True)
            view_box.setXRange(self._time_start, self._time_end, padding=0)
            view_box.blockSignals(False)

    def sync_x_axis(self) -> None:
        """Synchronize all graphs to the same time range.

        This method ensures all graphs display the same X-axis range.
        It uses the current time range or calculates from data if needed.
        """
        if self._time_start == 0 and self._time_end == 0:
            # Calculate range from data
            self._calculate_data_range()

            if self._data_start > 0 and self._data_end > 0:
                self._time_start = self._data_start
                self._time_end = self._data_end

        self._apply_time_range()

    def _calculate_data_range(self) -> None:
        """Calculate the full data range across all graphs."""
        min_time = float('inf')
        max_time = float('-inf')

        for panel in self._graphs.values():
            data_range = panel.chart.data_range
            if data_range:
                x_min, x_max, _, _ = data_range
                if x_min < min_time:
                    min_time = x_min
                if x_max > max_time:
                    max_time = x_max

        if min_time < float('inf') and max_time > float('-inf'):
            self._data_start = min_time
            self._data_end = max_time

    def _link_x_axes(self) -> None:
        """Link X-axes of all graphs for synchronized scrolling."""
        if len(self._graphs) < 2:
            return

        # Get first chart's view box as reference
        panels = list(self._graphs.values())
        reference_view = panels[0].chart.getPlotItem().getViewBox()

        # Link all other charts to the reference
        for panel in panels[1:]:
            view_box = panel.chart.getPlotItem().getViewBox()
            view_box.setXLink(reference_view)

    def _on_chart_range_changed(self, start_ms: float, end_ms: float) -> None:
        """Handle time range change from a chart.

        Args:
            start_ms: New start time
            end_ms: New end time
        """
        # Batch updates using timer
        self._pending_range = (start_ms, end_ms)
        if not self._sync_timer.isActive():
            self._sync_timer.start()

    def _do_sync_x_axis(self) -> None:
        """Actually perform the X-axis sync (called by timer)."""
        if self._pending_range:
            start_ms, end_ms = self._pending_range
            self._pending_range = None

            self._time_start = start_ms
            self._time_end = end_ms

            # Emit signal
            self.timeRangeChanged.emit(start_ms, end_ms)

    def clear(self) -> None:
        """Remove all graphs."""
        for name in list(self._graphs.keys()):
            self.remove_graph(name)

        self._time_start = 0
        self._time_end = 0
        self._data_start = 0
        self._data_end = 0

    def zoom(self, factor: float, center_ms: Optional[float] = None) -> None:
        """Zoom in or out.

        Args:
            factor: Zoom factor (>1 = zoom in, <1 = zoom out)
            center_ms: Center point for zoom (None = center of view)
        """
        if factor <= 0:
            return

        current_range = self._time_end - self._time_start
        if current_range <= 0:
            return

        # Calculate new range
        new_range = current_range / factor

        # Enforce limits
        if new_range < self.MIN_TIME_RANGE_MS:
            new_range = self.MIN_TIME_RANGE_MS

        max_range = (self._data_end - self._data_start) if self._data_end > self._data_start else current_range * self.MAX_ZOOM_FACTOR
        if new_range > max_range:
            new_range = max_range

        # Calculate center
        if center_ms is None:
            center_ms = (self._time_start + self._time_end) / 2

        # Apply zoom centered on center_ms
        half_range = new_range / 2
        new_start = center_ms - half_range
        new_end = center_ms + half_range

        # Clamp to data range
        if self._data_start > 0 and self._data_end > 0:
            if new_start < self._data_start:
                shift = self._data_start - new_start
                new_start = self._data_start
                new_end = min(new_end + shift, self._data_end)
            if new_end > self._data_end:
                shift = new_end - self._data_end
                new_end = self._data_end
                new_start = max(new_start - shift, self._data_start)

        self.set_time_range(new_start, new_end)

    def zoom_in(self, center_ms: Optional[float] = None) -> None:
        """Zoom in by one step.

        Args:
            center_ms: Center point for zoom
        """
        self.zoom(1.0 + self.ZOOM_FACTOR, center_ms)

    def zoom_out(self, center_ms: Optional[float] = None) -> None:
        """Zoom out by one step.

        Args:
            center_ms: Center point for zoom
        """
        self.zoom(1.0 - self.ZOOM_FACTOR, center_ms)

    def reset_zoom(self) -> None:
        """Reset zoom to show all data."""
        self._calculate_data_range()
        if self._data_start > 0 and self._data_end > 0:
            self.set_time_range(self._data_start, self._data_end)

    def pan(self, delta_ms: float) -> None:
        """Pan the view by a time delta.

        Args:
            delta_ms: Amount to pan in milliseconds (positive = right)
        """
        new_start = self._time_start + delta_ms
        new_end = self._time_end + delta_ms

        # Clamp to data range
        if self._data_start > 0 and self._data_end > 0:
            if new_start < self._data_start:
                shift = self._data_start - new_start
                new_start = self._data_start
                new_end += shift
            if new_end > self._data_end:
                shift = new_end - self._data_end
                new_end = self._data_end
                new_start -= shift

        self.set_time_range(new_start, new_end)

    # Event handlers

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Handle mouse wheel for zooming.

        Args:
            event: Wheel event
        """
        # Get wheel delta
        delta = event.angleDelta().y()
        if delta == 0:
            return

        # Calculate center point from mouse position
        mouse_x = event.position().x()
        widget_width = self.width()
        if widget_width > 0:
            fraction = mouse_x / widget_width
            current_range = self._time_end - self._time_start
            center_ms = self._time_start + fraction * current_range
        else:
            center_ms = None

        # Zoom based on wheel direction
        if delta > 0:
            self.zoom_in(center_ms)
        else:
            self.zoom_out(center_ms)

        event.accept()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press for panning.

        Args:
            event: Mouse event
        """
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_panning = True
            self._pan_start_x = event.position().x()
            self._pan_start_time = self._time_start
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handle mouse move for panning.

        Args:
            event: Mouse event
        """
        if self._is_panning:
            dx = event.position().x() - self._pan_start_x
            widget_width = self.width()
            if widget_width > 0:
                current_range = self._time_end - self._time_start
                delta_ms = -dx * current_range / widget_width
                new_start = self._pan_start_time + delta_ms
                new_end = new_start + current_range
                self.set_time_range(new_start, new_end)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Handle mouse release.

        Args:
            event: Mouse event
        """
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_panning = False
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """Handle double click to reset zoom.

        Args:
            event: Mouse event
        """
        if event.button() == Qt.MouseButton.LeftButton:
            self.reset_zoom()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    # Properties

    @property
    def graphs(self) -> Dict[str, GraphPanel]:
        """Return dictionary of graph panels."""
        return self._graphs.copy()

    @property
    def graph_names(self) -> List[str]:
        """Return list of graph names in order."""
        return self._graph_order.copy()

    @property
    def time_range(self) -> Tuple[float, float]:
        """Return current visible time range (start_ms, end_ms)."""
        return (self._time_start, self._time_end)

    @property
    def data_range(self) -> Tuple[float, float]:
        """Return full data time range (start_ms, end_ms)."""
        self._calculate_data_range()
        return (self._data_start, self._data_end)


# Test code
if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication, QMainWindow

    # Create application
    app = QApplication(sys.argv)

    # Create main window
    window = QMainWindow()
    window.setWindowTitle("GraphView Test")
    window.setGeometry(100, 100, 1000, 600)

    # Create GraphView
    graph_view = GraphView()
    window.setCentralWidget(graph_view)

    # Generate sample data
    np.random.seed(42)

    # Timestamps: 8 hours of data at 1 sample per second
    start_time = 1704067200000  # 2024-01-01 00:00:00 UTC in ms
    duration_ms = 8 * 60 * 60 * 1000  # 8 hours
    num_samples = 8 * 60 * 60  # 1 sample per second
    times = np.linspace(start_time, start_time + duration_ms, num_samples)

    # Flow rate: breathing pattern
    t = np.linspace(0, 8 * 60, num_samples)
    flow = 30 * np.sin(2 * np.pi * t / 4)  # 4 second breath cycle
    flow += np.random.normal(0, 2, num_samples)  # Add noise

    # Pressure: CPAP pressure with variations
    pressure = 10 + 0.5 * np.sin(2 * np.pi * t / 60)  # Slow variation
    pressure += np.random.normal(0, 0.2, num_samples)

    # SpO2: stable with occasional dips
    spo2 = 96 + np.random.normal(0, 0.5, num_samples)
    # Add some dips
    for i in range(20):
        dip_start = np.random.randint(0, num_samples - 100)
        spo2[dip_start:dip_start + 50] -= np.random.uniform(2, 5)

    # Add graphs
    flow_chart = graph_view.add_graph(
        "Flow Rate", height=200, y_label="Flow", y_unit="L/min",
        color=QColor(0, 150, 255)
    )
    flow_chart.set_data(times, flow)

    pressure_chart = graph_view.add_graph(
        "Pressure", height=150, y_label="Pressure", y_unit="cmH2O",
        color=QColor(255, 100, 0)
    )
    pressure_chart.set_data(times, pressure)

    spo2_chart = graph_view.add_graph(
        "SpO2", height=150, y_label="SpO2", y_unit="%",
        color=QColor(255, 50, 50)
    )
    spo2_chart.set_data(times, spo2)

    # Synchronize X-axes
    graph_view.sync_x_axis()

    # Show window
    window.show()

    # Run application
    sys.exit(app.exec())
