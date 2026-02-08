"""
OSCAR-Py Daily View Tab

This module provides the DailyView widget for displaying detailed daily
sleep data, including session graphs, statistics, and event information.

Reference: oscar/daily.h, oscar/daily.cpp, oscar/daily.ui

Copyright (c) 2019-2025 The OSCAR Team

This file is subject to the terms and conditions of the GNU General Public
License. See the file COPYING in the main directory of the source code
for more details.
"""

import logging
import math
from datetime import datetime, date, time, timedelta
from typing import Optional, List, Dict, Any, Tuple

import numpy as np

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QCalendarWidget,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QFrame,
    QScrollArea,
    QGroupBox,
    QGridLayout,
    QPushButton,
    QToolButton,
    QSizePolicy,
    QTextBrowser,
    QApplication,
)
from PyQt6.QtCore import Qt, QDate, pyqtSignal, QSize
from PyQt6.QtGui import (
    QTextCharFormat,
    QBrush,
    QColor,
    QFont,
    QPalette,
)

# Import with fallbacks for sleeplib components
try:
    from sleeplib.profile import Profile
    from sleeplib.session import Session
    from sleeplib.machine import Day
    from sleeplib.schema import (
        CPAP_FlowRate, CPAP_MaskPressure, CPAP_MaskPressureHi, CPAP_Leak, CPAP_RespRate,
        CPAP_Obstructive, CPAP_ClearAirway, CPAP_Hypopnea, CPAP_RERA,
        CPAP_Pressure, CPAP_AHI, CPAP_TidalVolume, CPAP_Snore, CPAP_MinuteVent,
        CPAP_Ti, CPAP_Te, CPAP_IPAP, CPAP_EPAP, CPAP_FLG, CPAP_IE,
        MachineType, ChannelID,
        channel as schema_channel,
    )
except ImportError:
    Profile = Session = Day = None
    CPAP_FlowRate = 0x1100
    CPAP_MaskPressure = 0x1101
    CPAP_MaskPressureHi = 0x1102
    CPAP_TidalVolume = 0x1103
    CPAP_Snore = 0x1104
    CPAP_MinuteVent = 0x1105
    CPAP_RespRate = 0x1106
    CPAP_Leak = 0x1108
    CPAP_IE = 0x1109
    CPAP_Te = 0x110A
    CPAP_Ti = 0x110B
    CPAP_Pressure = 0x110C
    CPAP_IPAP = 0x110D
    CPAP_EPAP = 0x110E
    CPAP_FLG = 0x1113
    CPAP_AHI = 0x1116
    CPAP_Obstructive = 0x1002
    CPAP_ClearAirway = 0x1001
    CPAP_Hypopnea = 0x1003
    CPAP_RERA = 0x1006
    MachineType = None
    ChannelID = int
    schema_channel = None

# Import with fallbacks for graph components
try:
    from graphs.graph_view import GraphView
    from graphs.line_chart import LineChart
except ImportError:
    GraphView = None
    LineChart = None

logger = logging.getLogger(__name__)


# ============================================================================
# Color Constants (matching OSCAR C++ colors)
# ============================================================================
COLOR_CPAP_DAY = QColor(0, 0, 255)           # Blue - CPAP data available
COLOR_CPAP_JOURNAL = QColor(0, 0, 200)       # Dark Blue - CPAP + Journal
COLOR_OXI_DAY = QColor(255, 0, 0)            # Red - Oximeter data
COLOR_OXI_CPAP = QColor(200, 0, 0)           # Dark Red - Oxi + CPAP
COLOR_JOURNAL_DAY = QColor(200, 200, 0)      # Yellow - Journal only
COLOR_NO_DATA = QColor(0, 0, 0)              # Black - No data

# Graph colors
COLOR_FLOW_RATE = QColor(0, 0, 180)          # Blue
COLOR_MASK_PRESSURE = QColor(0, 150, 0)      # Green
COLOR_LEAK = QColor(180, 0, 0)               # Red
COLOR_RESP_RATE = QColor(0, 180, 180)        # Cyan
COLOR_PRESSURE = QColor(150, 0, 150)         # Purple
COLOR_TIDAL_VOLUME = QColor(200, 100, 0)     # Orange
COLOR_SNORE = QColor(128, 128, 0)            # Olive
COLOR_MINUTE_VENT = QColor(100, 100, 200)    # Light blue
COLOR_TI = QColor(0, 200, 100)               # Sea green
COLOR_TE = QColor(200, 0, 100)               # Magenta
COLOR_IPAP = QColor(255, 100, 100)           # Light red
COLOR_EPAP = QColor(100, 200, 100)           # Light green
COLOR_FLG = QColor(255, 200, 0)              # Gold
COLOR_IE = QColor(150, 100, 50)              # Brown

# Event colors
COLOR_OA = QColor(0x40, 0xaf, 0xbf)          # Obstructive Apnea
COLOR_CA = QColor(0xb2, 0x54, 0xcd)          # Clear Airway
COLOR_H = QColor(0x40, 0x40, 0xff)           # Hypopnea
COLOR_RERA = QColor(0xff, 0xff, 0x80)        # RERA


# ============================================================================
# Graph Configuration
# ============================================================================
GRAPH_CONFIGS = [
    {
        'name': 'Flow Rate',
        'channel_id': CPAP_FlowRate,
        'color': COLOR_FLOW_RATE,
        'unit': 'L/min',
        'height': 120,
    },
    {
        'name': 'Mask Pressure',
        'channel_id': CPAP_MaskPressure,
        'color': COLOR_MASK_PRESSURE,
        'unit': 'cmH2O',
        'height': 100,
    },
    {
        'name': 'Leak Rate',
        'channel_id': CPAP_Leak,
        'color': COLOR_LEAK,
        'unit': 'L/min',
        'height': 80,
    },
    {
        'name': 'Respiratory Rate',
        'channel_id': CPAP_RespRate,
        'color': COLOR_RESP_RATE,
        'unit': 'br/min',
        'height': 80,
    },
]


# ============================================================================
# SessionInfoPanel - Displays session statistics
# ============================================================================
class SessionInfoPanel(QFrame):
    """Panel displaying session information and statistics.

    Shows:
    - Date and time range
    - Total hours
    - AHI (events per hour)
    - Event counts (OA, CA, H, RERA)
    - Average leak, 95th percentile leak
    - Average pressure
    """

    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize the SessionInfoPanel.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Sunken)
        self._setup_ui()
        self.clear()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(20)

        # Create info sections
        self._create_time_section(layout)
        self._create_ahi_section(layout)
        self._create_events_section(layout)
        self._create_leak_section(layout)
        self._create_pressure_section(layout)

        layout.addStretch()

    def _create_time_section(self, layout: QHBoxLayout) -> None:
        """Create the time/duration info section."""
        section = QVBoxLayout()
        section.setSpacing(2)

        self.date_label = QLabel("Date: --")
        self.date_label.setStyleSheet("font-weight: bold;")
        section.addWidget(self.date_label)

        self.time_range_label = QLabel("Time: -- to --")
        section.addWidget(self.time_range_label)

        self.duration_label = QLabel("Duration: --:--")
        section.addWidget(self.duration_label)

        layout.addLayout(section)

    def _create_ahi_section(self, layout: QHBoxLayout) -> None:
        """Create the AHI info section."""
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Plain)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(10, 5, 10, 5)

        title = QLabel("AHI")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-weight: bold; color: #666;")
        frame_layout.addWidget(title)

        self.ahi_label = QLabel("--")
        self.ahi_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = self.ahi_label.font()
        font.setPointSize(18)
        font.setBold(True)
        self.ahi_label.setFont(font)
        frame_layout.addWidget(self.ahi_label)

        layout.addWidget(frame)

    def _create_events_section(self, layout: QHBoxLayout) -> None:
        """Create the events count section."""
        section = QGridLayout()
        section.setSpacing(5)

        # Event type labels and counts
        self.oa_label = QLabel("OA: --")
        self.oa_label.setStyleSheet(f"color: {COLOR_OA.name()};")
        section.addWidget(self.oa_label, 0, 0)

        self.ca_label = QLabel("CA: --")
        self.ca_label.setStyleSheet(f"color: {COLOR_CA.name()};")
        section.addWidget(self.ca_label, 0, 1)

        self.h_label = QLabel("H: --")
        self.h_label.setStyleSheet(f"color: {COLOR_H.name()};")
        section.addWidget(self.h_label, 1, 0)

        self.rera_label = QLabel("RERA: --")
        self.rera_label.setStyleSheet(f"color: {COLOR_RERA.name()};")
        section.addWidget(self.rera_label, 1, 1)

        layout.addLayout(section)

    def _create_leak_section(self, layout: QHBoxLayout) -> None:
        """Create the leak info section."""
        section = QVBoxLayout()
        section.setSpacing(2)

        title = QLabel("Leak")
        title.setStyleSheet("font-weight: bold; color: #666;")
        section.addWidget(title)

        self.leak_avg_label = QLabel("Avg: -- L/min")
        section.addWidget(self.leak_avg_label)

        self.leak_95_label = QLabel("95%: -- L/min")
        section.addWidget(self.leak_95_label)

        layout.addLayout(section)

    def _create_pressure_section(self, layout: QHBoxLayout) -> None:
        """Create the pressure info section."""
        section = QVBoxLayout()
        section.setSpacing(2)

        title = QLabel("Pressure")
        title.setStyleSheet("font-weight: bold; color: #666;")
        section.addWidget(title)

        self.pressure_avg_label = QLabel("Avg: -- cmH2O")
        section.addWidget(self.pressure_avg_label)

        self.pressure_range_label = QLabel("Min-Max: -- - --")
        section.addWidget(self.pressure_range_label)

        layout.addLayout(section)

    def clear(self) -> None:
        """Clear all displayed information."""
        self.date_label.setText("Date: --")
        self.time_range_label.setText("Time: -- to --")
        self.duration_label.setText("Duration: --:--")
        self.ahi_label.setText("--")
        self.oa_label.setText("OA: --")
        self.ca_label.setText("CA: --")
        self.h_label.setText("H: --")
        self.rera_label.setText("RERA: --")
        self.leak_avg_label.setText("Avg: -- L/min")
        self.leak_95_label.setText("95%: -- L/min")
        self.pressure_avg_label.setText("Avg: -- cmH2O")
        self.pressure_range_label.setText("Min-Max: -- - --")

    def update_info(
        self,
        session_date: Optional[date] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        duration_hours: float = 0.0,
        ahi: float = 0.0,
        oa_count: int = 0,
        ca_count: int = 0,
        h_count: int = 0,
        rera_count: int = 0,
        leak_avg: float = 0.0,
        leak_95: float = 0.0,
        pressure_avg: float = 0.0,
        pressure_min: float = 0.0,
        pressure_max: float = 0.0,
    ) -> None:
        """Update the panel with session information.

        Args:
            session_date: The date of the session.
            start_time: Session start time.
            end_time: Session end time.
            duration_hours: Duration in decimal hours.
            ahi: Apnea-Hypopnea Index.
            oa_count: Obstructive apnea count.
            ca_count: Clear airway count.
            h_count: Hypopnea count.
            rera_count: RERA count.
            leak_avg: Average leak rate.
            leak_95: 95th percentile leak rate.
            pressure_avg: Average pressure.
            pressure_min: Minimum pressure.
            pressure_max: Maximum pressure.
        """
        if session_date:
            self.date_label.setText(f"Date: {session_date.strftime('%Y-%m-%d')}")
        else:
            self.date_label.setText("Date: --")

        if start_time and end_time:
            self.time_range_label.setText(
                f"Time: {start_time.strftime('%H:%M')} to {end_time.strftime('%H:%M')}"
            )
        else:
            self.time_range_label.setText("Time: -- to --")

        hours = int(duration_hours)
        minutes = int((duration_hours - hours) * 60)
        self.duration_label.setText(f"Duration: {hours}:{minutes:02d}")

        # AHI with color coding
        self.ahi_label.setText(f"{ahi:.2f}")
        if ahi < 5:
            self.ahi_label.setStyleSheet("color: green; font-weight: bold;")
        elif ahi < 15:
            self.ahi_label.setStyleSheet("color: orange; font-weight: bold;")
        elif ahi < 30:
            self.ahi_label.setStyleSheet("color: #ff6600; font-weight: bold;")
        else:
            self.ahi_label.setStyleSheet("color: red; font-weight: bold;")

        # Event counts
        self.oa_label.setText(f"OA: {oa_count}")
        self.ca_label.setText(f"CA: {ca_count}")
        self.h_label.setText(f"H: {h_count}")
        self.rera_label.setText(f"RERA: {rera_count}")

        # Leak info
        self.leak_avg_label.setText(f"Avg: {leak_avg:.1f} L/min")
        self.leak_95_label.setText(f"95%: {leak_95:.1f} L/min")

        # Pressure info
        self.pressure_avg_label.setText(f"Avg: {pressure_avg:.1f} cmH2O")
        self.pressure_range_label.setText(
            f"Min-Max: {pressure_min:.1f} - {pressure_max:.1f}"
        )


# ============================================================================
# PlaceholderGraphArea - Placeholder for graph display
# ============================================================================
class PlaceholderGraphArea(QScrollArea):
    """Placeholder widget for the graph display area.

    This will be replaced with actual GraphView when available.
    Shows placeholder graphs with labels.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize the PlaceholderGraphArea.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        container = QWidget()
        self.layout = QVBoxLayout(container)
        self.layout.setSpacing(5)
        self.layout.setContentsMargins(5, 5, 5, 5)

        self.graph_frames: List[QFrame] = []

        # Create placeholder frames for each graph type
        for config in GRAPH_CONFIGS:
            frame = self._create_graph_frame(config)
            self.graph_frames.append(frame)
            self.layout.addWidget(frame)

        # Add events panel
        events_frame = self._create_events_frame()
        self.graph_frames.append(events_frame)
        self.layout.addWidget(events_frame)

        self.layout.addStretch()
        self.setWidget(container)

    def _create_graph_frame(self, config: Dict[str, Any]) -> QFrame:
        """Create a placeholder frame for a graph.

        Args:
            config: Graph configuration dictionary.

        Returns:
            The created QFrame.
        """
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        frame.setMinimumHeight(config['height'])
        frame.setMaximumHeight(config['height'])

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(5, 2, 5, 2)

        # Title label
        title = QLabel(f"{config['name']} ({config['unit']})")
        title.setStyleSheet(
            f"font-weight: bold; color: {config['color'].name()};"
        )
        layout.addWidget(title)

        # Placeholder content
        placeholder = QLabel("No data - Select a session to view graph")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet("color: #888;")
        layout.addWidget(placeholder, 1)

        return frame

    def _create_events_frame(self) -> QFrame:
        """Create the events panel frame.

        Returns:
            The created QFrame.
        """
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        frame.setMinimumHeight(60)
        frame.setMaximumHeight(80)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(5, 2, 5, 2)

        title = QLabel("Events (Apneas/Hypopneas)")
        title.setStyleSheet("font-weight: bold; color: #666;")
        layout.addWidget(title)

        placeholder = QLabel("Event flags will be displayed here")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet("color: #888;")
        layout.addWidget(placeholder, 1)

        return frame

    def clear_graphs(self) -> None:
        """Clear all graphs and show placeholder text."""
        # Reset placeholder content
        for frame in self.graph_frames:
            labels = frame.findChildren(QLabel)
            for label in labels:
                if "No data" in label.text() or "flags will be" in label.text():
                    label.setText(label.text())


# ============================================================================
# DailyView - Main Daily View Tab
# ============================================================================
class DailyView(QWidget):
    """Main daily view tab widget.

    Layout:
    - Left panel: Calendar widget + session list
    - Right panel: Stacked graphs for selected session
    - Bottom: Session info summary

    Signals:
        date_changed: Emitted when the selected date changes.
        session_changed: Emitted when a session is selected.
    """

    date_changed = pyqtSignal(QDate)
    session_changed = pyqtSignal(object)  # Session or None

    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize the DailyView.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)

        self._profile: Optional[Profile] = None
        self._current_date: Optional[date] = None
        self._current_session: Optional[Session] = None
        self._sessions: List[Session] = []

        self._setup_ui()
        self._setup_styling()
        self._connect_signals()

        logger.info("DailyView initialized")

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Main splitter divides left panel and graph area
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel (calendar and session list)
        self._create_left_panel()

        # Right panel (graphs)
        self._create_right_panel()

        # Set up splitter sizes
        self.main_splitter.setSizes([250, 700])
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)

        main_layout.addWidget(self.main_splitter, 1)

        # Bottom info panel
        self.info_panel = SessionInfoPanel()
        main_layout.addWidget(self.info_panel)

    def _create_left_panel(self) -> None:
        """Create the left panel with calendar and session list."""
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(5, 5, 5, 5)
        left_layout.setSpacing(5)

        # Navigation buttons
        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(2)

        self.prev_day_btn = QToolButton()
        self.prev_day_btn.setText("<")
        self.prev_day_btn.setToolTip("Go to previous day")
        self.prev_day_btn.setMinimumSize(QSize(30, 25))
        nav_layout.addWidget(self.prev_day_btn)

        self.date_display_btn = QToolButton()
        self.date_display_btn.setText("Select Date")
        self.date_display_btn.setCheckable(True)
        self.date_display_btn.setChecked(True)
        self.date_display_btn.setToolTip("Show/hide calendar")
        self.date_display_btn.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        nav_layout.addWidget(self.date_display_btn)

        self.next_day_btn = QToolButton()
        self.next_day_btn.setText(">")
        self.next_day_btn.setToolTip("Go to next day")
        self.next_day_btn.setMinimumSize(QSize(30, 25))
        nav_layout.addWidget(self.next_day_btn)

        self.today_btn = QToolButton()
        self.today_btn.setText(">>")
        self.today_btn.setToolTip("Go to most recent day with data")
        self.today_btn.setMinimumSize(QSize(30, 25))
        nav_layout.addWidget(self.today_btn)

        left_layout.addLayout(nav_layout)

        # Calendar widget
        self.calendar_frame = QFrame()
        self.calendar_frame.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        calendar_layout = QVBoxLayout(self.calendar_frame)
        calendar_layout.setContentsMargins(0, 0, 0, 0)

        self.calendar = QCalendarWidget()
        self.calendar.setMinimumHeight(200)
        self.calendar.setGridVisible(False)
        self.calendar.setVerticalHeaderFormat(
            QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader
        )
        self.calendar.setHorizontalHeaderFormat(
            QCalendarWidget.HorizontalHeaderFormat.ShortDayNames
        )
        self.calendar.setFirstDayOfWeek(Qt.DayOfWeek.Monday)
        calendar_layout.addWidget(self.calendar)

        left_layout.addWidget(self.calendar_frame)

        # Session list
        session_group = QGroupBox("Sessions")
        session_layout = QVBoxLayout(session_group)
        session_layout.setContentsMargins(5, 5, 5, 5)

        self.session_list = QListWidget()
        self.session_list.setMinimumHeight(100)
        session_layout.addWidget(self.session_list)

        left_layout.addWidget(session_group, 1)

        # Details browser
        details_group = QGroupBox("Details")
        details_layout = QVBoxLayout(details_group)
        details_layout.setContentsMargins(5, 5, 5, 5)

        self.details_browser = QTextBrowser()
        self.details_browser.setOpenLinks(False)
        self.details_browser.setMinimumHeight(100)
        details_layout.addWidget(self.details_browser)

        left_layout.addWidget(details_group, 1)

        self.main_splitter.addWidget(left_panel)

    def _create_right_panel(self) -> None:
        """Create the right panel with graph area."""
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(5, 5, 5, 5)
        right_layout.setSpacing(5)

        # Use GraphView if available, otherwise placeholder
        if GraphView is not None:
            self.graph_area = GraphView()
        else:
            self.graph_area = PlaceholderGraphArea()

        right_layout.addWidget(self.graph_area)

        self.main_splitter.addWidget(right_panel)

    def _setup_styling(self) -> None:
        """Set up the visual styling."""
        # Navigation button styling
        button_style = """
            QToolButton {
                background: transparent;
                border-radius: 4px;
                border: 1px solid #aaa;
            }
            QToolButton:hover {
                border: 2px solid #456789;
            }
            QToolButton:pressed {
                border: 2px solid #456789;
                background-color: #89abcd;
            }
        """
        self.prev_day_btn.setStyleSheet(button_style)
        self.next_day_btn.setStyleSheet(button_style)
        self.today_btn.setStyleSheet(button_style)

        # Date display button styling
        date_button_style = """
            QToolButton {
                border: 2px solid #aaaaaa;
                border-radius: 5px;
                background: white;
                padding: 3px;
            }
            QToolButton:hover {
                border: 2px solid #456789;
            }
            QToolButton:checked {
                border: 2px solid #456789;
            }
        """
        self.date_display_btn.setStyleSheet(date_button_style)

    def _connect_signals(self) -> None:
        """Connect widget signals to slots."""
        self.calendar.selectionChanged.connect(self._on_calendar_selection_changed)
        self.calendar.currentPageChanged.connect(self._on_calendar_page_changed)
        self.session_list.currentRowChanged.connect(self._on_session_row_changed)
        self.prev_day_btn.clicked.connect(self._on_prev_day_clicked)
        self.next_day_btn.clicked.connect(self._on_next_day_clicked)
        self.today_btn.clicked.connect(self._on_today_clicked)
        self.date_display_btn.toggled.connect(self._on_calendar_toggle)

    # ========================================================================
    # Public API
    # ========================================================================

    def set_profile(self, profile: Optional[Profile]) -> None:
        """Set the active profile.

        Args:
            profile: The profile to use, or None to clear.
        """
        self._profile = profile
        self._sessions = []
        self._current_session = None
        self._current_date = None

        self.session_list.clear()
        self.info_panel.clear()

        if profile is not None:
            # Update calendar date range highlighting
            self._update_calendar_all()

            # Select the most recent day with data
            last_day = None
            if hasattr(profile, 'last_day'):
                last_day = profile.last_day()

            if last_day:
                self.select_date(last_day)
            else:
                # Select today if no data
                self.select_date(date.today())

        logger.debug(f"Profile set: {profile}")

    def select_date(self, selected_date: date) -> None:
        """Select a date and load sessions.

        Args:
            selected_date: The date to select.
        """
        if selected_date == self._current_date:
            return

        self._current_date = selected_date
        self._sessions = []
        self._current_session = None

        # Update calendar selection
        qdate = QDate(selected_date.year, selected_date.month, selected_date.day)
        self.calendar.blockSignals(True)
        self.calendar.setSelectedDate(qdate)
        self.calendar.blockSignals(False)

        # Update date display button
        self.date_display_btn.setText(selected_date.strftime("%Y-%m-%d"))

        # Load sessions for this date
        self._load_sessions_for_date(selected_date)

        # Update UI
        self._update_session_list()

        # Select first session if available
        if self._sessions:
            self.select_session(self._sessions[0])
        else:
            self.info_panel.clear()
            self._update_details_browser()

        # Emit signal
        self.date_changed.emit(qdate)

        logger.debug(f"Date selected: {selected_date}")

    def select_session(self, session: Optional[Session]) -> None:
        """Display session in graphs.

        Args:
            session: The session to display, or None.
        """
        self._current_session = session

        if session is None:
            self.info_panel.clear()
            if hasattr(self.graph_area, 'clear_graphs'):
                self.graph_area.clear_graphs()
            self._update_details_browser()
            return

        # Update info panel with session data
        self._update_info_panel(session)

        # Update graphs
        self.update_graphs()

        # Update details
        self._update_details_browser()

        # Emit signal
        self.session_changed.emit(session)

        logger.debug(f"Session selected: {session}")

    def update_graphs(self) -> None:
        """Refresh graph display with waveform data."""
        if self._current_session is None:
            if hasattr(self.graph_area, 'clear'):
                self.graph_area.clear()
            return

        # If using real GraphView, load and display waveforms
        if GraphView is not None and isinstance(self.graph_area, GraphView):
            self._load_and_display_waveforms()
        else:
            # Placeholder - no waveform display available
            pass

    def _load_and_display_waveforms(self) -> None:
        """Load event data and display waveforms in GraphView.

        Iterates over ALL sessions for the current day (not just one),
        concatenating data with NaN gaps between sessions so PyQtGraph
        breaks the line at session boundaries.
        """
        if not self._sessions:
            return

        # Load events for all sessions
        for session in self._sessions:
            if hasattr(session, 'load_events'):
                try:
                    session.load_events()
                except Exception as e:
                    logger.warning(f"Failed to load events for session: {e}")
            if not hasattr(session, 'get_events'):
                return

        # Clear existing graphs
        self.graph_area.clear()

        # Channel configurations: (channel_id, name, y_label, y_unit, color, height)
        # All available CPAP waveform channels
        waveform_channels = [
            # Primary waveforms (larger graphs)
            (CPAP_FlowRate, "Flow Rate", "Flow", "L/min", COLOR_FLOW_RATE, 180),
            (CPAP_MaskPressureHi, "Mask Pressure", "Pressure", "cmH2O", COLOR_MASK_PRESSURE, 120),
            (CPAP_MaskPressure, "Mask Pressure Lo", "Pressure", "cmH2O", QColor(0, 120, 0), 100),
            (CPAP_Leak, "Leak Rate", "Leak", "L/min", COLOR_LEAK, 100),
            # Respiratory parameters
            (CPAP_RespRate, "Resp Rate", "RR", "br/min", COLOR_RESP_RATE, 80),
            (CPAP_TidalVolume, "Tidal Volume", "TV", "ml", COLOR_TIDAL_VOLUME, 80),
            (CPAP_MinuteVent, "Minute Vent", "MV", "L/min", COLOR_MINUTE_VENT, 80),
            # Timing parameters
            (CPAP_Ti, "Insp Time (Ti)", "Ti", "s", COLOR_TI, 70),
            (CPAP_Te, "Exp Time (Te)", "Te", "s", COLOR_TE, 70),
            (CPAP_IE, "I:E Ratio", "I:E", "", COLOR_IE, 70),
            # Pressure channels
            (CPAP_Pressure, "Pressure", "P", "cmH2O", COLOR_PRESSURE, 100),
            (CPAP_IPAP, "IPAP", "IPAP", "cmH2O", COLOR_IPAP, 80),
            (CPAP_EPAP, "EPAP", "EPAP", "cmH2O", COLOR_EPAP, 80),
            # Other channels
            (CPAP_Snore, "Snore", "Snore", "", COLOR_SNORE, 60),
            (CPAP_FLG, "Flow Limitation", "FLG", "", COLOR_FLG, 70),
            (CPAP_AHI, "AHI Graph", "AHI", "events/hr", QColor(200, 0, 0), 80),
        ]

        graphs_added = 0

        for channel_id, name, y_label, y_unit, color, height in waveform_channels:
            # Collect data from ALL sessions for this channel
            all_times = []
            all_values = []

            for session in self._sessions:
                events = session.get_events(channel_id)
                if not events:
                    continue

                evlist = events[0]
                if evlist.count == 0:
                    continue

                times = evlist.get_times_ms()  # ms relative to evlist.first
                values = evlist.get_values()    # Actual values with gain/offset

                # Convert to absolute epoch ms for TimeAxisItem
                times = times + evlist.first

                # Insert NaN gap between sessions to break the line
                if all_times:
                    all_times.append(np.array([np.nan]))
                    all_values.append(np.array([np.nan]))

                all_times.append(times)
                all_values.append(values)

            if not all_times:
                continue

            try:
                # Add graph panel
                chart = self.graph_area.add_graph(
                    name=name,
                    height=height,
                    y_label=y_label,
                    y_unit=y_unit,
                    color=color
                )

                # Concatenate all sessions' data
                concat_times = np.concatenate(all_times)
                concat_values = np.concatenate(all_values)

                # Set data on chart — auto_range=False to avoid per-chart
                # autoRange fighting with X-linked viewboxes.  reset_zoom()
                # below sets the range once for all charts together.
                chart.set_data(concat_times, concat_values, auto_range=False)
                graphs_added += 1

            except Exception as e:
                logger.warning(f"Failed to display {name}: {e}")

        logger.info(f"Displayed {graphs_added} waveform channels from {len(self._sessions)} sessions")

        # Add event flags overlay
        self._add_event_flags()

        # Set initial time range to show all data
        if hasattr(self.graph_area, 'reset_zoom'):
            self.graph_area.reset_zoom()

    def _add_event_flags(self) -> None:
        """Add respiratory event flags to the graphs.

        Iterates over ALL sessions for the current day.
        """
        if not self._sessions:
            return

        # Event channels to display as flags
        event_channels = [
            (0x1002, "OA", QColor(0, 180, 180, 76)),    # Obstructive - Teal
            (0x1001, "CA", QColor(180, 80, 200, 76)),    # Central - Purple
            (0x1003, "H", QColor(80, 80, 255, 76)),      # Hypopnea - Blue
            (0x1006, "RERA", QColor(255, 255, 80, 76)),   # RERA - Yellow
        ]

        # Get the first graph to add regions to (usually Flow Rate)
        flow_chart = self.graph_area.get_graph("Flow Rate")
        if flow_chart is None:
            return

        for channel_id, label, color in event_channels:
            for session in self._sessions:
                if not hasattr(session, 'get_events'):
                    continue

                events = session.get_events(channel_id)
                if not events:
                    continue

                evlist = events[0]
                if evlist.count == 0:
                    continue

                # Convert to absolute epoch ms for TimeAxisItem
                times = evlist.get_times_ms() + evlist.first

                for t in times[:100]:  # Limit to first 100 events per session
                    try:
                        flow_chart.add_region(
                            start_ms=t - 2000,  # 2 seconds before
                            end_ms=t + 2000,     # 2 seconds after
                            color=color,
                        )
                    except Exception:
                        pass  # Region adding may fail

    def on_date_changed(self, selected_date: date) -> None:
        """Handle calendar selection (public slot).

        Args:
            selected_date: The selected date.
        """
        self.select_date(selected_date)

    def on_session_changed(self, index: int) -> None:
        """Handle session list selection (public slot).

        Args:
            index: The selected index in the session list.
        """
        if 0 <= index < len(self._sessions):
            self.select_session(self._sessions[index])
        else:
            self.select_session(None)

    # ========================================================================
    # Private Methods
    # ========================================================================

    def _load_sessions_for_date(self, selected_date: date) -> None:
        """Load sessions for the given date.

        Args:
            selected_date: The date to load sessions for.
        """
        self._sessions = []

        if self._profile is None:
            return

        # Get day from profile
        if not hasattr(self._profile, 'get_day'):
            return

        day = self._profile.get_day(selected_date)
        if day is None:
            return

        # Get sessions from the day
        if hasattr(day, 'sessions'):
            self._sessions = list(day.sessions)
        elif hasattr(day, '__iter__'):
            self._sessions = list(day)

    def _update_session_list(self) -> None:
        """Update the session list widget."""
        self.session_list.clear()

        for i, session in enumerate(self._sessions):
            # Get session time range
            start_time = "--:--"
            end_time = "--:--"
            duration = 0.0

            if hasattr(session, 'first') and session.first:
                start_time = session.first.strftime("%H:%M")
            elif hasattr(session, 'first_time') and session.first_time:
                dt = datetime.fromtimestamp(session.first_time / 1000.0)
                start_time = dt.strftime("%H:%M")

            if hasattr(session, 'last') and session.last:
                end_time = session.last.strftime("%H:%M")
            elif hasattr(session, 'last_time') and session.last_time:
                dt = datetime.fromtimestamp(session.last_time / 1000.0)
                end_time = dt.strftime("%H:%M")

            if hasattr(session, 'hours'):
                duration = session.hours()
            elif hasattr(session, 'duration'):
                duration = session.duration()

            # Format duration
            hours = int(duration)
            mins = int((duration - hours) * 60)
            duration_str = f"{hours}h {mins}m"

            # Create list item
            item_text = f"Session {i + 1}: {start_time} - {end_time} ({duration_str})"
            item = QListWidgetItem(item_text)
            self.session_list.addItem(item)

        # Select first item
        if self.session_list.count() > 0:
            self.session_list.setCurrentRow(0)

    def _update_info_panel(self, session: Session) -> None:
        """Update the info panel with session data.

        Args:
            session: The session to display info for.
        """
        # Extract session info
        session_date = self._current_date
        start_time = None
        end_time = None
        duration_hours = 0.0

        if hasattr(session, 'first') and session.first:
            start_time = session.first
        elif hasattr(session, 'first_time') and session.first_time:
            start_time = datetime.fromtimestamp(session.first_time / 1000.0)

        if hasattr(session, 'last') and session.last:
            end_time = session.last
        elif hasattr(session, 'last_time') and session.last_time:
            end_time = datetime.fromtimestamp(session.last_time / 1000.0)

        if hasattr(session, 'hours'):
            duration_hours = session.hours()
        elif hasattr(session, 'duration'):
            duration_hours = session.duration()

        # Get event counts
        oa_count = 0
        ca_count = 0
        h_count = 0
        rera_count = 0

        if hasattr(session, 'count'):
            oa_count = int(session.count(CPAP_Obstructive))
            ca_count = int(session.count(CPAP_ClearAirway))
            h_count = int(session.count(CPAP_Hypopnea))
            rera_count = int(session.count(CPAP_RERA))

        # Calculate AHI
        total_events = oa_count + ca_count + h_count
        ahi = total_events / duration_hours if duration_hours > 0 else 0.0

        # Get leak stats
        leak_avg = 0.0
        leak_95 = 0.0
        if hasattr(session, 'avg'):
            leak_avg = session.avg(CPAP_Leak)
        # 95th percentile would require more data

        # Get pressure stats
        pressure_avg = 0.0
        pressure_min = 0.0
        pressure_max = 0.0
        if hasattr(session, 'avg'):
            pressure_avg = session.avg(CPAP_Pressure)
        if hasattr(session, 'min_value'):
            pressure_min = session.min_value(CPAP_Pressure)
        if hasattr(session, 'max_value'):
            pressure_max = session.max_value(CPAP_Pressure)

        # Update the panel
        self.info_panel.update_info(
            session_date=session_date,
            start_time=start_time,
            end_time=end_time,
            duration_hours=duration_hours,
            ahi=ahi,
            oa_count=oa_count,
            ca_count=ca_count,
            h_count=h_count,
            rera_count=rera_count,
            leak_avg=leak_avg,
            leak_95=leak_95,
            pressure_avg=pressure_avg,
            pressure_min=pressure_min,
            pressure_max=pressure_max,
        )

    def _update_details_browser(self) -> None:
        """Update the details browser with session information."""
        if self._current_session is None:
            self.details_browser.setHtml("<p>No session selected</p>")
            return

        session = self._current_session

        # Build HTML content
        html = "<style>"
        html += "body { font-family: sans-serif; font-size: 10pt; }"
        html += "table { border-collapse: collapse; width: 100%; }"
        html += "td { padding: 2px 5px; }"
        html += ".label { color: #666; }"
        html += ".value { font-weight: bold; }"
        html += "</style>"
        html += "<body>"

        html += "<h4>Session Information</h4>"
        html += "<table>"

        # Session ID
        if hasattr(session, 'session_id'):
            html += f"<tr><td class='label'>Session ID:</td><td class='value'>{session.session_id}</td></tr>"

        # Machine type
        if hasattr(session, 'type'):
            html += f"<tr><td class='label'>Machine Type:</td><td class='value'>{session.type}</td></tr>"

        # Duration
        if hasattr(session, 'hours'):
            hours = session.hours()
            h = int(hours)
            m = int((hours - h) * 60)
            html += f"<tr><td class='label'>Duration:</td><td class='value'>{h}h {m}m</td></tr>"

        html += "</table>"
        html += "</body>"

        self.details_browser.setHtml(html)

    def _update_calendar_all(self) -> None:
        """Update calendar highlighting for all visible dates."""
        if self._profile is None:
            return

        # Get current month/year from calendar
        current = self.calendar.selectedDate()
        year = current.year()
        month = current.month()

        self._update_calendar_month(year, month)

    def _update_calendar_month(self, year: int, month: int) -> None:
        """Update calendar highlighting for a specific month.

        Args:
            year: The year.
            month: The month (1-12).
        """
        if self._profile is None:
            return

        # Define text formats
        cpap_format = QTextCharFormat()
        cpap_format.setForeground(QBrush(COLOR_CPAP_DAY))
        cpap_format.setFontWeight(QFont.Weight.Normal)

        oxi_format = QTextCharFormat()
        oxi_format.setForeground(QBrush(COLOR_OXI_DAY))
        oxi_format.setFontWeight(QFont.Weight.Bold)

        journal_format = QTextCharFormat()
        journal_format.setForeground(QBrush(COLOR_JOURNAL_DAY))
        journal_format.setFontWeight(QFont.Weight.Bold)

        no_data_format = QTextCharFormat()
        no_data_format.setForeground(QBrush(COLOR_NO_DATA))
        no_data_format.setFontWeight(QFont.Weight.Normal)

        # Get days in month
        first_of_month = QDate(year, month, 1)
        days_in_month = first_of_month.daysInMonth()

        # Update each day
        for day in range(1, days_in_month + 1):
            qdate = QDate(year, month, day)
            py_date = date(year, month, day)

            # Check what data is available
            has_cpap = False
            has_oxi = False
            has_journal = False

            if hasattr(self._profile, 'find_day'):
                if MachineType is not None:
                    cpap_day = self._profile.find_day(py_date, MachineType.MT_CPAP)
                    has_cpap = cpap_day is not None

                    oxi_day = self._profile.find_day(py_date, MachineType.MT_OXIMETER)
                    has_oxi = oxi_day is not None

                    journal_day = self._profile.find_day(py_date, MachineType.MT_JOURNAL)
                    has_journal = journal_day is not None

            # Apply appropriate format
            if has_cpap and has_oxi:
                self.calendar.setDateTextFormat(qdate, oxi_format)
            elif has_cpap:
                self.calendar.setDateTextFormat(qdate, cpap_format)
            elif has_oxi:
                self.calendar.setDateTextFormat(qdate, oxi_format)
            elif has_journal:
                self.calendar.setDateTextFormat(qdate, journal_format)
            else:
                self.calendar.setDateTextFormat(qdate, no_data_format)

    # ========================================================================
    # Signal Handlers
    # ========================================================================

    def _on_calendar_selection_changed(self) -> None:
        """Handle calendar selection change."""
        qdate = self.calendar.selectedDate()
        py_date = date(qdate.year(), qdate.month(), qdate.day())
        self.select_date(py_date)

    def _on_calendar_page_changed(self, year: int, month: int) -> None:
        """Handle calendar page (month/year) change.

        Args:
            year: The new year.
            month: The new month.
        """
        self._update_calendar_month(year, month)

    def _on_session_row_changed(self, row: int) -> None:
        """Handle session list row change.

        Args:
            row: The new selected row.
        """
        self.on_session_changed(row)

    def _on_prev_day_clicked(self) -> None:
        """Handle previous day button click."""
        if self._current_date is None:
            return

        new_date = self._current_date - timedelta(days=1)
        self.select_date(new_date)

    def _on_next_day_clicked(self) -> None:
        """Handle next day button click."""
        if self._current_date is None:
            return

        new_date = self._current_date + timedelta(days=1)
        self.select_date(new_date)

    def _on_today_clicked(self) -> None:
        """Handle today button click."""
        if self._profile is not None and hasattr(self._profile, 'last_day'):
            last_day = self._profile.last_day()
            if last_day:
                self.select_date(last_day)
                return

        self.select_date(date.today())

    def _on_calendar_toggle(self, checked: bool) -> None:
        """Handle calendar toggle button.

        Args:
            checked: Whether the calendar should be visible.
        """
        self.calendar_frame.setVisible(checked)


# ============================================================================
# Standalone Test
# ============================================================================
def main():
    """Test the DailyView with mock data."""
    import sys

    app = QApplication(sys.argv)
    app.setApplicationName("OSCAR-Py DailyView Test")

    # Create main window
    window = QWidget()
    window.setWindowTitle("Daily View Test")
    window.resize(1200, 800)

    layout = QVBoxLayout(window)

    # Create daily view
    daily_view = DailyView()
    layout.addWidget(daily_view)

    # Create some mock session data for testing
    class MockSession:
        """Mock session for testing."""

        def __init__(self, session_id, start_ms, end_ms):
            self.session_id = session_id
            self._first = start_ms
            self._last = end_ms
            self._enabled = True
            self._counts = {
                CPAP_Obstructive: 5,
                CPAP_ClearAirway: 2,
                CPAP_Hypopnea: 8,
                CPAP_RERA: 3,
            }
            self._avgs = {
                CPAP_Leak: 12.5,
                CPAP_Pressure: 10.2,
            }
            self._mins = {CPAP_Pressure: 8.0}
            self._maxs = {CPAP_Pressure: 14.0}

        @property
        def first_time(self):
            return self._first

        @property
        def last_time(self):
            return self._last

        @property
        def first(self):
            return datetime.fromtimestamp(self._first / 1000.0)

        @property
        def last(self):
            return datetime.fromtimestamp(self._last / 1000.0)

        def hours(self):
            return (self._last - self._first) / 3600000.0

        def count(self, channel_id):
            return self._counts.get(channel_id, 0)

        def avg(self, channel_id):
            return self._avgs.get(channel_id, 0.0)

        def min_value(self, channel_id):
            return self._mins.get(channel_id, 0.0)

        def max_value(self, channel_id):
            return self._maxs.get(channel_id, 0.0)

        @property
        def type(self):
            return "CPAP"

    class MockDay:
        """Mock day for testing."""

        def __init__(self, sessions):
            self._sessions = sessions

        @property
        def sessions(self):
            return self._sessions

    class MockProfile:
        """Mock profile for testing."""

        def __init__(self):
            self._days = {}

            # Create mock data for today
            today = date.today()
            now = datetime.now()
            start_ms = int((now - timedelta(hours=7)).timestamp() * 1000)
            end_ms = int(now.timestamp() * 1000)

            session1 = MockSession(1, start_ms, start_ms + 4 * 3600000)
            session2 = MockSession(2, start_ms + 5 * 3600000, end_ms)

            self._days[today] = MockDay([session1, session2])

            # Add yesterday
            yesterday = today - timedelta(days=1)
            y_start = int((now - timedelta(days=1, hours=8)).timestamp() * 1000)
            y_end = int((now - timedelta(days=1, hours=1)).timestamp() * 1000)
            session3 = MockSession(3, y_start, y_end)
            self._days[yesterday] = MockDay([session3])

        def get_day(self, d, mtype=None):
            return self._days.get(d)

        def find_day(self, d, mtype=None):
            return self._days.get(d)

        def last_day(self, mtype=None):
            if self._days:
                return max(self._days.keys())
            return None

    # Set up mock profile
    mock_profile = MockProfile()
    daily_view.set_profile(mock_profile)

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
