"""
Event Flags Rendering for OSCAR Python Port

This module provides PyQtGraph-based components for visualizing
sleep event flags (apneas, hypopneas, etc.) on a timeline.

Based on gFlagsLine.cpp/h from the C++ OSCAR codebase.

Copyright (c) 2019-2025 The OSCAR Team
License: GPL v3
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
from enum import IntEnum

from PyQt6.QtCore import Qt, QRectF, pyqtSignal, QPointF
from PyQt6.QtGui import QColor, QPainter, QPen, QBrush, QFont, QPainterPath
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QGraphicsObject,
    QStyleOptionGraphicsItem, QGraphicsSceneHoverEvent, QToolTip
)
import pyqtgraph as pg
import numpy as np

# Import schema constants if available
try:
    from sleeplib.schema import (
        CPAP_Obstructive, CPAP_ClearAirway, CPAP_Hypopnea, CPAP_RERA,
        CPAP_FlowLimit, CPAP_VSnore, CPAP_PB, CPAP_CSR, ChannelID
    )
except ImportError:
    CPAP_Obstructive = 0x1002
    CPAP_ClearAirway = 0x1001
    CPAP_Hypopnea = 0x1003
    CPAP_RERA = 0x1006
    CPAP_FlowLimit = 0x1005
    CPAP_VSnore = 0x1007
    CPAP_PB = 0x1028
    CPAP_CSR = 0x1000
    ChannelID = int


# ============================================================================
# Color Constants
# ============================================================================

EVENT_COLORS: Dict[str, str] = {
    'OA': '#FF0000',      # Red - Obstructive Apnea
    'CA': '#0000FF',      # Blue - Central Apnea (Clear Airway)
    'H': '#00FFFF',       # Cyan - Hypopnea
    'RERA': '#FFFF00',    # Yellow - RERA
    'FL': '#FFA500',      # Orange - Flow Limitation
    'VS': '#8B4513',      # Brown - Vibratory Snore
    'PB': '#800080',      # Purple - Periodic Breathing
    'CSR': '#800080',     # Purple - Cheyne-Stokes Respiration
    'LL': '#FF6347',      # Tomato - Large Leak
    'UA': '#00CED1',      # Dark Cyan - Unclassified Apnea
}

# Mapping from event type codes to display labels
EVENT_LABELS: Dict[str, str] = {
    'OA': 'Obstructive Apnea',
    'CA': 'Clear Airway',
    'H': 'Hypopnea',
    'RERA': 'RERA',
    'FL': 'Flow Limitation',
    'VS': 'Vibratory Snore',
    'PB': 'Periodic Breathing',
    'CSR': 'Cheyne-Stokes',
    'LL': 'Large Leak',
    'UA': 'Unclassified Apnea',
}

# Mapping from schema ChannelIDs to event type codes
CHANNEL_TO_EVENT_TYPE: Dict[int, str] = {
    CPAP_Obstructive: 'OA',
    CPAP_ClearAirway: 'CA',
    CPAP_Hypopnea: 'H',
    CPAP_RERA: 'RERA',
    CPAP_FlowLimit: 'FL',
    CPAP_VSnore: 'VS',
    CPAP_PB: 'PB',
    CPAP_CSR: 'CSR',
}


# ============================================================================
# EventFlag Dataclass
# ============================================================================

@dataclass
class EventFlag:
    """Represents a single sleep event flag.

    Attributes:
        time_ms: Timestamp in milliseconds since epoch
        duration_ms: Duration of the event in milliseconds (0 for instant events)
        event_type: Event type code (e.g., "OA", "CA", "H", "RERA")
        value: Optional associated value (e.g., severity, percentage)
        channel_id: Optional schema ChannelID for this event
    """
    time_ms: int
    duration_ms: int = 0
    event_type: str = "OA"
    value: float = 0.0
    channel_id: Optional[int] = None

    @property
    def end_time_ms(self) -> int:
        """Return the end time of the event."""
        return self.time_ms + self.duration_ms

    @property
    def is_span(self) -> bool:
        """Return True if this event has a duration (span event)."""
        return self.duration_ms > 0

    @property
    def color(self) -> str:
        """Return the color for this event type."""
        return EVENT_COLORS.get(self.event_type, '#808080')

    @property
    def label(self) -> str:
        """Return the full label for this event type."""
        return EVENT_LABELS.get(self.event_type, self.event_type)

    def contains_time(self, time_ms: int) -> bool:
        """Check if the given time falls within this event."""
        if self.duration_ms > 0:
            return self.time_ms <= time_ms <= self.end_time_ms
        else:
            # For instant events, check within a small tolerance
            return abs(time_ms - self.time_ms) < 1000  # 1 second tolerance

    def to_tooltip(self) -> str:
        """Generate tooltip text for this event."""
        lines = [self.label]
        if self.duration_ms > 0:
            duration_sec = self.duration_ms / 1000.0
            if duration_sec >= 60:
                minutes = int(duration_sec // 60)
                seconds = duration_sec % 60
                lines.append(f"Duration: {minutes} min, {seconds:.1f} sec")
            else:
                lines.append(f"Duration: {duration_sec:.1f} sec")
        if self.value != 0:
            lines.append(f"Value: {self.value:.1f}")
        return '\n'.join(lines)


# ============================================================================
# EventFlagItem - Single Event Graphics Item
# ============================================================================

class EventFlagItem(pg.GraphicsObject):
    """Renders a single event flag as a colored marker/region.

    This is a pyqtgraph GraphicsObject that draws either:
    - A vertical line for instant events (duration_ms == 0)
    - A horizontal bar/rectangle for span events (duration_ms > 0)

    Supports hover effects and tooltips.
    """

    # Signals
    hovered = pyqtSignal(object)  # Emits EventFlag when hovered
    clicked = pyqtSignal(object)  # Emits EventFlag when clicked

    def __init__(
        self,
        event: EventFlag,
        y_offset: float = 0.0,
        height: float = 1.0,
        parent: Optional[QGraphicsObject] = None
    ):
        """Initialize an EventFlagItem.

        Args:
            event: The EventFlag to render
            y_offset: Y position offset for this flag
            height: Height of the flag bar/marker
            parent: Optional parent graphics item
        """
        super().__init__(parent)
        self._event = event
        self._y_offset = y_offset
        self._height = height
        self._hovered = False
        self._min_width = 2.0  # Minimum pixel width for visibility

        # Colors
        self._color = QColor(event.color)
        self._hover_color = self._color.lighter(130)
        self._pen_color = self._color.darker(120)

        # Enable hover events
        self.setAcceptHoverEvents(True)

        # Cache the bounding rect
        self._bounds: Optional[QRectF] = None

    @property
    def event(self) -> EventFlag:
        """Return the associated EventFlag."""
        return self._event

    def set_event(self, event: EventFlag) -> None:
        """Update the event data."""
        self._event = event
        self._color = QColor(event.color)
        self._hover_color = self._color.lighter(130)
        self._pen_color = self._color.darker(120)
        self._bounds = None
        self.prepareGeometryChange()
        self.update()

    def set_geometry(self, y_offset: float, height: float) -> None:
        """Update the y offset and height."""
        self._y_offset = y_offset
        self._height = height
        self._bounds = None
        self.prepareGeometryChange()
        self.update()

    def boundingRect(self) -> QRectF:
        """Return the bounding rectangle for this item."""
        if self._bounds is not None:
            return self._bounds

        # X coordinates are in milliseconds
        x = float(self._event.time_ms)
        if self._event.duration_ms > 0:
            width = float(self._event.duration_ms)
        else:
            # For instant events, use a minimum width
            width = 1000.0  # 1 second default width for flags

        # Add some padding for the hover/selection highlight
        padding = 2.0
        self._bounds = QRectF(
            x - padding,
            self._y_offset - padding,
            width + 2 * padding,
            self._height + 2 * padding
        )
        return self._bounds

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: Optional[QWidget] = None
    ) -> None:
        """Paint the event flag."""
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Choose color based on hover state
        if self._hovered:
            fill_color = self._hover_color
            pen_width = 2.0
        else:
            fill_color = self._color
            pen_width = 1.0

        pen = QPen(self._pen_color, pen_width)
        brush = QBrush(fill_color)
        painter.setPen(pen)
        painter.setBrush(brush)

        x = float(self._event.time_ms)
        y = self._y_offset
        h = self._height

        if self._event.duration_ms > 0:
            # Draw as a horizontal bar/rectangle for span events
            w = float(self._event.duration_ms)
            # Ensure minimum visual width
            rect = QRectF(x, y, max(w, self._min_width), h)
            painter.drawRect(rect)
        else:
            # Draw as a vertical line for instant events
            pen.setWidth(2 if self._hovered else 1)
            painter.setPen(pen)
            painter.drawLine(QPointF(x, y), QPointF(x, y + h))

    def hoverEnterEvent(self, event: QGraphicsSceneHoverEvent) -> None:
        """Handle hover enter."""
        self._hovered = True
        self.update()
        self.hovered.emit(self._event)

        # Show tooltip
        tooltip_text = self._event.to_tooltip()
        if tooltip_text:
            pos = event.screenPos()
            QToolTip.showText(pos.toPoint(), tooltip_text)

    def hoverLeaveEvent(self, event: QGraphicsSceneHoverEvent) -> None:
        """Handle hover leave."""
        self._hovered = False
        self.update()
        QToolTip.hideText()

    def mousePressEvent(self, event) -> None:
        """Handle mouse press."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._event)
            event.accept()
        else:
            event.ignore()


# ============================================================================
# EventFlagsOverlay - Container for Multiple Event Flags
# ============================================================================

class EventFlagsOverlay(pg.PlotItem):
    """Container widget for rendering multiple event flags on a timeline.

    This is designed to be added as a layer/overlay to a LineChart,
    drawing flags at the top of the chart area.

    Features:
    - Groups events by type into separate rows
    - Supports zoom and pan with the parent chart
    - Shows labels for event types
    - Configurable flag height and appearance
    """

    # Signals
    event_hovered = pyqtSignal(object)  # EventFlag or None
    event_clicked = pyqtSignal(object)  # EventFlag

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        show_labels: bool = True,
        flag_height: int = 20,
        **kwargs
    ):
        """Initialize the EventFlagsOverlay.

        Args:
            parent: Parent widget
            show_labels: Whether to show event type labels
            flag_height: Height of each flag row in pixels
            **kwargs: Additional arguments passed to PlotItem
        """
        super().__init__(**kwargs)

        self._events: List[EventFlag] = []
        self._event_items: List[EventFlagItem] = []
        self._show_labels = show_labels
        self._flag_height = flag_height

        # Time range (milliseconds)
        self._start_ms: int = 0
        self._end_ms: int = 0

        # Event type organization
        self._event_types: List[str] = []  # Ordered list of visible event types
        self._events_by_type: Dict[str, List[EventFlag]] = {}

        # Configure the plot
        self._setup_plot()

    def _setup_plot(self) -> None:
        """Configure the plot appearance."""
        # Hide axes for overlay mode
        self.hideAxis('left')
        self.hideAxis('bottom')

        # Get the ViewBox and configure it for transparent background
        vb = self.getViewBox()
        if vb is not None:
            vb.setBackgroundColor(None)

        # Disable mouse interactions (parent handles zoom/pan)
        self.setMouseEnabled(x=False, y=False)
        self.setMenuEnabled(False)

    @property
    def show_labels(self) -> bool:
        """Return whether labels are shown."""
        return self._show_labels

    @show_labels.setter
    def show_labels(self, value: bool) -> None:
        """Set whether to show labels."""
        self._show_labels = value
        self._rebuild_display()

    @property
    def flag_height(self) -> int:
        """Return the flag row height."""
        return self._flag_height

    @flag_height.setter
    def flag_height(self, value: int) -> None:
        """Set the flag row height."""
        self._flag_height = max(10, value)
        self._rebuild_display()

    def set_events(self, events: List[EventFlag]) -> None:
        """Set all events to display.

        Args:
            events: List of EventFlag objects
        """
        self._events = list(events)
        self._organize_events()
        self._rebuild_display()

    def add_event(self, event: EventFlag) -> None:
        """Add a single event.

        Args:
            event: EventFlag to add
        """
        self._events.append(event)
        self._organize_events()
        self._rebuild_display()

    def clear(self) -> None:
        """Remove all events."""
        self._events.clear()
        self._events_by_type.clear()
        self._event_types.clear()
        self._clear_items()

    def _clear_items(self) -> None:
        """Remove all graphics items."""
        for item in self._event_items:
            self.removeItem(item)
        self._event_items.clear()

    def set_time_range(self, start_ms: int, end_ms: int) -> None:
        """Set the visible time range.

        Args:
            start_ms: Start time in milliseconds
            end_ms: End time in milliseconds
        """
        self._start_ms = start_ms
        self._end_ms = end_ms
        self.setXRange(start_ms, end_ms, padding=0)

    def _organize_events(self) -> None:
        """Organize events by type for display."""
        self._events_by_type.clear()

        for event in self._events:
            event_type = event.event_type
            if event_type not in self._events_by_type:
                self._events_by_type[event_type] = []
            self._events_by_type[event_type].append(event)

        # Sort event types by a predefined order
        type_order = ['OA', 'CA', 'H', 'RERA', 'FL', 'VS', 'PB', 'CSR', 'LL', 'UA']
        self._event_types = sorted(
            self._events_by_type.keys(),
            key=lambda t: type_order.index(t) if t in type_order else 999
        )

        # Update time range from events
        if self._events:
            self._start_ms = min(e.time_ms for e in self._events)
            self._end_ms = max(e.end_time_ms for e in self._events)

    def _rebuild_display(self) -> None:
        """Rebuild all graphics items."""
        self._clear_items()

        if not self._events:
            return

        # Calculate row positions
        num_types = len(self._event_types)
        if num_types == 0:
            return

        row_height = self._flag_height

        # Create items for each event
        for row_idx, event_type in enumerate(self._event_types):
            y_offset = row_idx * row_height

            for event in self._events_by_type.get(event_type, []):
                item = EventFlagItem(
                    event=event,
                    y_offset=y_offset,
                    height=row_height - 2  # Leave small gap between rows
                )
                item.hovered.connect(self._on_event_hovered)
                item.clicked.connect(self._on_event_clicked)
                self.addItem(item)
                self._event_items.append(item)

        # Set Y range to fit all rows
        total_height = num_types * row_height
        self.setYRange(0, total_height, padding=0.05)

        # Set X range
        if self._start_ms < self._end_ms:
            self.setXRange(self._start_ms, self._end_ms, padding=0.02)

    def _on_event_hovered(self, event: EventFlag) -> None:
        """Handle event hover signal."""
        self.event_hovered.emit(event)

    def _on_event_clicked(self, event: EventFlag) -> None:
        """Handle event click signal."""
        self.event_clicked.emit(event)

    def get_events_at_time(self, time_ms: int) -> List[EventFlag]:
        """Get all events that contain the given time.

        Args:
            time_ms: Time in milliseconds

        Returns:
            List of EventFlag objects at that time
        """
        return [e for e in self._events if e.contains_time(time_ms)]

    def get_event_counts(self) -> Dict[str, int]:
        """Get counts of each event type.

        Returns:
            Dictionary mapping event type codes to counts
        """
        return {et: len(events) for et, events in self._events_by_type.items()}


# ============================================================================
# EventSummaryWidget - Compact Event Summary Table
# ============================================================================

class EventSummaryWidget(QWidget):
    """Widget showing event counts in a compact table format.

    Displays:
    - Event Type
    - Count
    - Events Per Hour (if total hours provided)

    Rows are color-coded to match event flag colors.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize the EventSummaryWidget.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)

        self._events: List[EventFlag] = []
        self._total_hours: float = 0.0

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Title label
        self._title_label = QLabel("Event Summary")
        self._title_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self._title_label)

        # Table widget
        self._table = QTableWidget()
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels(["Event", "Count", "/Hour"])
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._table.setMaximumHeight(200)
        layout.addWidget(self._table)

        # AHI label
        self._ahi_label = QLabel("AHI: --")
        self._ahi_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(self._ahi_label)

    def set_events(self, events: List[EventFlag], total_hours: float = 0.0) -> None:
        """Set the events to summarize.

        Args:
            events: List of EventFlag objects
            total_hours: Total recording time in hours (for per-hour calculations)
        """
        self._events = list(events)
        self._total_hours = max(0.01, total_hours)  # Avoid division by zero
        self._update_table()

    def set_total_hours(self, hours: float) -> None:
        """Set the total recording time.

        Args:
            hours: Total hours
        """
        self._total_hours = max(0.01, hours)
        self._update_table()

    def _update_table(self) -> None:
        """Update the table contents."""
        # Count events by type
        counts: Dict[str, int] = {}
        for event in self._events:
            et = event.event_type
            counts[et] = counts.get(et, 0) + 1

        # Define display order
        display_order = ['OA', 'CA', 'H', 'RERA', 'FL', 'VS', 'PB']

        # Filter to types that exist in data or are in display order
        visible_types = [t for t in display_order if t in counts]

        # Add any other types not in the predefined order
        for t in counts:
            if t not in visible_types:
                visible_types.append(t)

        # Update table
        self._table.setRowCount(len(visible_types) + 1)  # +1 for total

        total_ahi_events = 0

        for row, event_type in enumerate(visible_types):
            count = counts.get(event_type, 0)
            per_hour = count / self._total_hours if self._total_hours > 0 else 0

            # Event type cell with color
            type_item = QTableWidgetItem(event_type)
            color = QColor(EVENT_COLORS.get(event_type, '#808080'))
            type_item.setBackground(QBrush(color))
            # Set text color for contrast
            if color.lightness() < 128:
                type_item.setForeground(QBrush(QColor('white')))
            self._table.setItem(row, 0, type_item)

            # Count cell
            count_item = QTableWidgetItem(str(count))
            count_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 1, count_item)

            # Per hour cell
            per_hour_item = QTableWidgetItem(f"{per_hour:.1f}")
            per_hour_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 2, per_hour_item)

            # Count AHI contributing events
            if event_type in ['OA', 'CA', 'H', 'UA']:
                total_ahi_events += count

        # Add total row
        total_row = len(visible_types)
        total_type_item = QTableWidgetItem("Total")
        total_type_item.setBackground(QBrush(QColor('#E0E0E0')))
        font = total_type_item.font()
        font.setBold(True)
        total_type_item.setFont(font)
        self._table.setItem(total_row, 0, total_type_item)

        total_count = sum(counts.values())
        total_count_item = QTableWidgetItem(str(total_count))
        total_count_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        total_count_item.setFont(font)
        self._table.setItem(total_row, 1, total_count_item)

        total_per_hour = total_count / self._total_hours if self._total_hours > 0 else 0
        total_per_hour_item = QTableWidgetItem(f"{total_per_hour:.1f}")
        total_per_hour_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        total_per_hour_item.setFont(font)
        self._table.setItem(total_row, 2, total_per_hour_item)

        # Update AHI label
        ahi = total_ahi_events / self._total_hours if self._total_hours > 0 else 0
        self._ahi_label.setText(f"AHI: {ahi:.2f}")

    def clear(self) -> None:
        """Clear all data."""
        self._events.clear()
        self._total_hours = 0.0
        self._table.setRowCount(0)
        self._ahi_label.setText("AHI: --")


# ============================================================================
# Integration with LineChart
# ============================================================================

class EventFlagsLayer:
    """Helper class for integrating event flags as a layer on a LineChart.

    This class manages an EventFlagsOverlay as a layer that draws on top of
    a LineChart widget, synchronizing the time axis between them.

    Usage:
        chart = LineChart(title="Flow Rate")
        flags_layer = EventFlagsLayer(chart)
        flags_layer.set_events(events)

    The flags will be drawn at the top of the chart, overlaying the waveform data.
    """

    def __init__(
        self,
        chart: 'pg.PlotWidget',
        flag_height: int = 20,
        show_labels: bool = True
    ):
        """Initialize the EventFlagsLayer.

        Args:
            chart: The LineChart (or any PlotWidget) to overlay
            flag_height: Height of each event flag row in pixels
            show_labels: Whether to show event type labels
        """
        self._chart = chart
        self._flag_height = flag_height
        self._show_labels = show_labels
        self._events: List[EventFlag] = []

        # Create a ViewBox for the flags overlay
        self._overlay_viewbox = pg.ViewBox()
        self._overlay_viewbox.setMouseEnabled(x=False, y=False)

        # Add the overlay viewbox to the chart's scene
        self._chart.scene().addItem(self._overlay_viewbox)

        # Create event flag items directly in the overlay
        self._flag_items: List[EventFlagItem] = []

        # Connect to the chart's resize and range change signals
        self._chart.sigRangeChanged.connect(self._on_range_changed)

        # Initial update
        self._update_overlay_geometry()

    def set_events(self, events: List[EventFlag]) -> None:
        """Set the events to display.

        Args:
            events: List of EventFlag objects
        """
        self._events = list(events)
        self._rebuild_flags()

    def add_event(self, event: EventFlag) -> None:
        """Add a single event.

        Args:
            event: EventFlag to add
        """
        self._events.append(event)
        self._rebuild_flags()

    def clear(self) -> None:
        """Remove all events."""
        self._events.clear()
        self._clear_flags()

    def _clear_flags(self) -> None:
        """Remove all flag items from the overlay."""
        for item in self._flag_items:
            self._overlay_viewbox.removeItem(item)
        self._flag_items.clear()

    def _rebuild_flags(self) -> None:
        """Rebuild all flag items."""
        self._clear_flags()

        if not self._events:
            return

        # Organize events by type
        events_by_type: Dict[str, List[EventFlag]] = {}
        for event in self._events:
            et = event.event_type
            if et not in events_by_type:
                events_by_type[et] = []
            events_by_type[et].append(event)

        # Sort event types
        type_order = ['OA', 'CA', 'H', 'RERA', 'FL', 'VS', 'PB', 'CSR', 'LL', 'UA']
        event_types = sorted(
            events_by_type.keys(),
            key=lambda t: type_order.index(t) if t in type_order else 999
        )

        # Create items for each event
        for row_idx, event_type in enumerate(event_types):
            y_offset = row_idx * self._flag_height

            for event in events_by_type.get(event_type, []):
                item = EventFlagItem(
                    event=event,
                    y_offset=y_offset,
                    height=self._flag_height - 2
                )
                self._overlay_viewbox.addItem(item)
                self._flag_items.append(item)

        self._update_overlay_geometry()

    def _update_overlay_geometry(self) -> None:
        """Update the overlay geometry to match the chart."""
        # Get the chart's view box
        chart_vb = self._chart.getPlotItem().getViewBox()
        chart_rect = chart_vb.sceneBoundingRect()

        # Position the overlay at the top of the chart
        num_types = len(set(e.event_type for e in self._events))
        overlay_height = max(num_types * self._flag_height, self._flag_height)

        self._overlay_viewbox.setGeometry(
            chart_rect.x(),
            chart_rect.y(),
            chart_rect.width(),
            overlay_height
        )

        # Sync the X range
        x_range = chart_vb.viewRange()[0]
        self._overlay_viewbox.setXRange(x_range[0], x_range[1], padding=0)

        # Set Y range for the overlay
        self._overlay_viewbox.setYRange(0, overlay_height, padding=0)

    def _on_range_changed(self) -> None:
        """Handle chart range changes."""
        self._update_overlay_geometry()

    @property
    def flag_height(self) -> int:
        """Return the flag row height."""
        return self._flag_height

    @flag_height.setter
    def flag_height(self, value: int) -> None:
        """Set the flag row height."""
        self._flag_height = max(10, value)
        self._rebuild_flags()

    @property
    def events(self) -> List[EventFlag]:
        """Return the list of events."""
        return list(self._events)


def add_event_flags_to_chart(
    chart: 'pg.PlotWidget',
    events: List[EventFlag],
    flag_height: int = 20,
    show_labels: bool = True
) -> EventFlagsLayer:
    """Helper function to add event flags overlay to a chart.

    This is a convenience function that creates an EventFlagsLayer
    and configures it with the given events.

    Args:
        chart: The LineChart or PlotWidget to overlay
        events: List of EventFlag objects to display
        flag_height: Height of each event flag row
        show_labels: Whether to show event type labels

    Returns:
        The created EventFlagsLayer instance

    Example:
        chart = LineChart(title="Flow Rate")
        chart.set_data(times, values)
        flags_layer = add_event_flags_to_chart(chart, events)
    """
    layer = EventFlagsLayer(chart, flag_height, show_labels)
    layer.set_events(events)
    return layer


# ============================================================================
# Utility Functions
# ============================================================================

def create_sample_events(
    start_time_ms: int = 0,
    duration_hours: float = 8.0,
    num_events: int = 50
) -> List[EventFlag]:
    """Create sample event data for testing.

    Args:
        start_time_ms: Start time in milliseconds
        duration_hours: Duration of the recording in hours
        num_events: Approximate number of events to generate

    Returns:
        List of randomly generated EventFlag objects
    """
    import random

    events = []
    duration_ms = int(duration_hours * 3600 * 1000)
    end_time_ms = start_time_ms + duration_ms

    # Event types with relative probabilities
    event_types = [
        ('OA', 0.25),  # Obstructive Apnea
        ('CA', 0.15),  # Clear Airway
        ('H', 0.35),   # Hypopnea
        ('RERA', 0.15),  # RERA
        ('FL', 0.05),  # Flow Limitation
        ('VS', 0.05),  # Vibratory Snore
    ]

    # Generate events
    for _ in range(num_events):
        # Choose event type based on probabilities
        r = random.random()
        cumulative = 0
        event_type = 'OA'
        for et, prob in event_types:
            cumulative += prob
            if r < cumulative:
                event_type = et
                break

        # Generate random time
        time_ms = random.randint(start_time_ms, end_time_ms)

        # Generate duration (0 for flags, positive for spans)
        if event_type in ['PB', 'CSR']:
            # Spans are longer
            duration_ms_event = random.randint(30000, 120000)  # 30 sec to 2 min
        elif event_type in ['FL']:
            duration_ms_event = random.randint(5000, 30000)  # 5-30 sec
        else:
            # Most events are flag-like with short or zero duration
            if random.random() < 0.7:
                duration_ms_event = random.randint(10000, 60000)  # 10-60 sec
            else:
                duration_ms_event = 0  # Instant flag

        # Generate optional value
        value = random.uniform(0, 10) if random.random() < 0.3 else 0.0

        event = EventFlag(
            time_ms=time_ms,
            duration_ms=duration_ms_event,
            event_type=event_type,
            value=value
        )
        events.append(event)

    # Sort by time
    events.sort(key=lambda e: e.time_ms)
    return events


# ============================================================================
# Demo/Test Code
# ============================================================================

def _demo():
    """Run a demo of the event flags rendering."""
    import sys
    from PyQt6.QtWidgets import QApplication, QMainWindow, QSplitter

    app = QApplication(sys.argv)

    # Create main window
    window = QMainWindow()
    window.setWindowTitle("Event Flags Demo")
    window.resize(1200, 600)

    # Create splitter for layout
    splitter = QSplitter(Qt.Orientation.Horizontal)
    window.setCentralWidget(splitter)

    # Create graphics layout widget for the flags overlay
    graphics_widget = pg.GraphicsLayoutWidget()
    splitter.addWidget(graphics_widget)

    # Create the flags overlay
    flags_overlay = EventFlagsOverlay(show_labels=True, flag_height=25)
    graphics_widget.addItem(flags_overlay, row=0, col=0)

    # Create sample events
    import time
    start_time = int(time.time() * 1000) - (8 * 3600 * 1000)  # 8 hours ago
    sample_events = create_sample_events(
        start_time_ms=start_time,
        duration_hours=8.0,
        num_events=100
    )

    # Set events on overlay
    flags_overlay.set_events(sample_events)

    # Create summary widget
    summary_widget = EventSummaryWidget()
    summary_widget.set_events(sample_events, total_hours=8.0)
    summary_widget.setMaximumWidth(300)
    splitter.addWidget(summary_widget)

    # Connect signals
    def on_event_hovered(event: EventFlag):
        if event:
            print(f"Hovered: {event.label} at {event.time_ms}")

    def on_event_clicked(event: EventFlag):
        print(f"Clicked: {event.label} at {event.time_ms}")

    flags_overlay.event_hovered.connect(on_event_hovered)
    flags_overlay.event_clicked.connect(on_event_clicked)

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    _demo()
