"""
OSCAR-Py Overview View Tab

This module provides the OverviewView widget for displaying summary
charts and statistics over configurable date ranges.

Reference: oscar/overview.h, oscar/overview.cpp

Copyright (c) 2019-2025 The OSCAR Team

This file is subject to the terms and conditions of the GNU General Public
License. See the file COPYING in the main directory of the source code
for more details.
"""

import logging
from datetime import date, timedelta
from typing import Optional, List

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QComboBox,
    QDateEdit,
    QLabel,
    QFrame,
    QGridLayout,
    QSplitter,
    QScrollArea,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, QDate, pyqtSignal

# Import chart components with fallback
try:
    from graphs.ahi_chart import AHIChart
    from graphs.usage_chart import UsageChart
    from graphs.pressure_chart import PressureChart
except ImportError:
    AHIChart = None
    UsageChart = None
    PressureChart = None

# Import sleeplib components with fallback
try:
    from sleeplib.profile import Profile
    from sleeplib.statistics import StatisticsCalculator, DaySummary, RangeSummary
    from sleeplib.schema import MachineType
except ImportError:
    Profile = None
    StatisticsCalculator = None
    DaySummary = None
    RangeSummary = None
    MachineType = None


logger = logging.getLogger(__name__)


# Date range presets
RANGE_PRESETS = [
    ("Last Week", 7),
    ("Last 2 Weeks", 14),
    ("Last Month", 30),
    ("Last 3 Months", 90),
    ("Last 6 Months", 180),
    ("Last Year", 365),
    ("All Data", -1),
    ("Custom", 0),
]


class StatisticsPanel(QFrame):
    """Panel displaying aggregate statistics for the selected range.

    Shows:
    - AHI: Average and median
    - Usage: Average and median hours
    - Compliance: Percentage of compliant days
    - Pressure: Average pressure
    """

    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize the StatisticsPanel.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self._setup_ui()
        self.clear()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(30)

        # AHI section
        self._create_ahi_section(layout)

        # Usage section
        self._create_usage_section(layout)

        # Compliance section
        self._create_compliance_section(layout)

        # Pressure section
        self._create_pressure_section(layout)

        layout.addStretch()

    def _create_ahi_section(self, layout: QHBoxLayout) -> None:
        """Create the AHI statistics section."""
        section = QVBoxLayout()
        section.setSpacing(2)

        title = QLabel("AHI")
        title.setStyleSheet("font-weight: bold; color: #666;")
        section.addWidget(title)

        self.ahi_avg_label = QLabel("Avg: --")
        section.addWidget(self.ahi_avg_label)

        self.ahi_median_label = QLabel("Median: --")
        section.addWidget(self.ahi_median_label)

        self.ahi_90th_label = QLabel("90th %: --")
        section.addWidget(self.ahi_90th_label)

        layout.addLayout(section)

    def _create_usage_section(self, layout: QHBoxLayout) -> None:
        """Create the usage statistics section."""
        section = QVBoxLayout()
        section.setSpacing(2)

        title = QLabel("Usage")
        title.setStyleSheet("font-weight: bold; color: #666;")
        section.addWidget(title)

        self.usage_avg_label = QLabel("Avg: -- hrs")
        section.addWidget(self.usage_avg_label)

        self.usage_median_label = QLabel("Median: -- hrs")
        section.addWidget(self.usage_median_label)

        self.usage_total_label = QLabel("Total: -- hrs")
        section.addWidget(self.usage_total_label)

        layout.addLayout(section)

    def _create_compliance_section(self, layout: QHBoxLayout) -> None:
        """Create the compliance statistics section."""
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Plain)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(10, 5, 10, 5)

        title = QLabel("Compliance")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-weight: bold; color: #666;")
        frame_layout.addWidget(title)

        self.compliance_label = QLabel("--%")
        self.compliance_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = self.compliance_label.font()
        font.setPointSize(16)
        font.setBold(True)
        self.compliance_label.setFont(font)
        frame_layout.addWidget(self.compliance_label)

        self.compliance_days_label = QLabel("-- / -- days")
        self.compliance_days_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.compliance_days_label.setStyleSheet("color: #888;")
        frame_layout.addWidget(self.compliance_days_label)

        layout.addWidget(frame)

    def _create_pressure_section(self, layout: QHBoxLayout) -> None:
        """Create the pressure statistics section."""
        section = QVBoxLayout()
        section.setSpacing(2)

        title = QLabel("Pressure")
        title.setStyleSheet("font-weight: bold; color: #666;")
        section.addWidget(title)

        self.pressure_avg_label = QLabel("Avg: -- cmH2O")
        section.addWidget(self.pressure_avg_label)

        self.leak_avg_label = QLabel("Leak: -- L/min")
        section.addWidget(self.leak_avg_label)

        layout.addLayout(section)

    def clear(self) -> None:
        """Clear all displayed statistics."""
        self.ahi_avg_label.setText("Avg: --")
        self.ahi_median_label.setText("Median: --")
        self.ahi_90th_label.setText("90th %: --")
        self.usage_avg_label.setText("Avg: -- hrs")
        self.usage_median_label.setText("Median: -- hrs")
        self.usage_total_label.setText("Total: -- hrs")
        self.compliance_label.setText("--%")
        self.compliance_label.setStyleSheet("")
        self.compliance_days_label.setText("-- / -- days")
        self.pressure_avg_label.setText("Avg: -- cmH2O")
        self.leak_avg_label.setText("Leak: -- L/min")

    def update_stats(self, stats: 'RangeSummary') -> None:
        """Update the panel with range statistics.

        Args:
            stats: RangeSummary object with calculated statistics.
        """
        if stats is None:
            self.clear()
            return

        # AHI stats
        self.ahi_avg_label.setText(f"Avg: {stats.ahi_avg:.2f}")
        self.ahi_median_label.setText(f"Median: {stats.ahi_median:.2f}")
        self.ahi_90th_label.setText(f"90th %: {stats.ahi_90th:.2f}")

        # Usage stats
        self.usage_avg_label.setText(f"Avg: {stats.avg_hours:.1f} hrs")
        self.usage_median_label.setText(f"Median: {stats.median_hours:.1f} hrs")
        self.usage_total_label.setText(f"Total: {stats.total_hours:.1f} hrs")

        # Compliance stats
        compliance = stats.compliance_percent
        self.compliance_label.setText(f"{compliance:.0f}%")

        # Color code compliance
        if compliance >= 70:
            self.compliance_label.setStyleSheet("color: green; font-weight: bold;")
        elif compliance >= 50:
            self.compliance_label.setStyleSheet("color: orange; font-weight: bold;")
        else:
            self.compliance_label.setStyleSheet("color: red; font-weight: bold;")

        self.compliance_days_label.setText(
            f"{stats.days_with_data} / {stats.total_days} days"
        )

        # Pressure stats
        self.pressure_avg_label.setText(f"Avg: {stats.pressure_avg:.1f} cmH2O")
        self.leak_avg_label.setText(f"Leak: {stats.leak_avg:.1f} L/min")


class OverviewView(QWidget):
    """Main overview view tab widget.

    Layout:
    - Top: Date range selector (presets + custom date pickers)
    - Middle: Stacked charts (AHI, Usage, Pressure)
    - Bottom: Statistics panel

    Signals:
        navigate_to_day: Emitted when user clicks a day to navigate there.
        range_changed: Emitted when the date range changes.
    """

    navigate_to_day = pyqtSignal(object)  # date
    range_changed = pyqtSignal(object, object)  # start_date, end_date

    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize the OverviewView.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)

        self._profile: Optional['Profile'] = None
        self._calculator: Optional['StatisticsCalculator'] = None
        self._summaries: List['DaySummary'] = []
        self._start_date: Optional[date] = None
        self._end_date: Optional[date] = None

        self._setup_ui()
        self._connect_signals()

        logger.info("OverviewView initialized")

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        # Date range selector
        self._create_date_selector(main_layout)

        # Charts area (scrollable)
        self._create_charts_area(main_layout)

        # Statistics panel
        self.stats_panel = StatisticsPanel()
        main_layout.addWidget(self.stats_panel)

    def _create_date_selector(self, layout: QVBoxLayout) -> None:
        """Create the date range selector controls."""
        selector_frame = QFrame()
        selector_frame.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        selector_layout = QHBoxLayout(selector_frame)
        selector_layout.setContentsMargins(10, 5, 10, 5)

        # Preset dropdown
        selector_layout.addWidget(QLabel("Range:"))
        self.range_combo = QComboBox()
        for name, _ in RANGE_PRESETS:
            self.range_combo.addItem(name)
        self.range_combo.setCurrentIndex(2)  # Default to "Last Month"
        selector_layout.addWidget(self.range_combo)

        selector_layout.addSpacing(20)

        # From date
        selector_layout.addWidget(QLabel("From:"))
        self.from_date_edit = QDateEdit()
        self.from_date_edit.setCalendarPopup(True)
        self.from_date_edit.setEnabled(False)  # Enabled only for "Custom"
        selector_layout.addWidget(self.from_date_edit)

        # To date
        selector_layout.addWidget(QLabel("To:"))
        self.to_date_edit = QDateEdit()
        self.to_date_edit.setCalendarPopup(True)
        self.to_date_edit.setEnabled(False)  # Enabled only for "Custom"
        selector_layout.addWidget(self.to_date_edit)

        selector_layout.addStretch()

        layout.addWidget(selector_frame)

    def _create_charts_area(self, layout: QVBoxLayout) -> None:
        """Create the charts display area."""
        # Create scroll area for charts
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Container for charts
        charts_container = QWidget()
        charts_layout = QVBoxLayout(charts_container)
        charts_layout.setSpacing(5)
        charts_layout.setContentsMargins(0, 0, 0, 0)

        # Create charts if available
        if AHIChart is not None:
            self.ahi_chart = AHIChart()
            self.ahi_chart.setMinimumHeight(150)
            self.ahi_chart.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
            )
            charts_layout.addWidget(self.ahi_chart)
        else:
            self.ahi_chart = None
            charts_layout.addWidget(self._create_placeholder("AHI Chart"))

        if UsageChart is not None:
            self.usage_chart = UsageChart()
            self.usage_chart.setMinimumHeight(150)
            self.usage_chart.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
            )
            charts_layout.addWidget(self.usage_chart)
        else:
            self.usage_chart = None
            charts_layout.addWidget(self._create_placeholder("Usage Chart"))

        if PressureChart is not None:
            self.pressure_chart = PressureChart()
            self.pressure_chart.setMinimumHeight(150)
            self.pressure_chart.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
            )
            charts_layout.addWidget(self.pressure_chart)
        else:
            self.pressure_chart = None
            charts_layout.addWidget(self._create_placeholder("Pressure Chart"))

        charts_layout.addStretch()
        scroll_area.setWidget(charts_container)
        layout.addWidget(scroll_area, 1)  # Stretch factor 1

    def _create_placeholder(self, name: str) -> QFrame:
        """Create a placeholder widget for a chart.

        Args:
            name: Name of the chart.

        Returns:
            Placeholder QFrame.
        """
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        frame.setMinimumHeight(150)
        layout = QVBoxLayout(frame)
        label = QLabel(f"{name}\n(Not available)")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("color: #888;")
        layout.addWidget(label)
        return frame

    def _connect_signals(self) -> None:
        """Connect widget signals to slots."""
        self.range_combo.currentIndexChanged.connect(self._on_range_preset_changed)
        self.from_date_edit.dateChanged.connect(self._on_custom_date_changed)
        self.to_date_edit.dateChanged.connect(self._on_custom_date_changed)

        # Connect chart click signals
        if self.ahi_chart is not None:
            self.ahi_chart.dayClicked.connect(self._on_day_clicked)
        if self.usage_chart is not None:
            self.usage_chart.dayClicked.connect(self._on_day_clicked)
        if self.pressure_chart is not None:
            self.pressure_chart.dayClicked.connect(self._on_day_clicked)

    # ========================================================================
    # Public API
    # ========================================================================

    def set_profile(self, profile: Optional['Profile']) -> None:
        """Set the active profile.

        Args:
            profile: The profile to use, or None to clear.
        """
        self._profile = profile
        self._summaries = []

        if profile is None:
            self._calculator = None
            self._clear_charts()
            self.stats_panel.clear()
            return

        # Create statistics calculator
        if StatisticsCalculator is not None:
            # Get compliance hours from profile settings
            compliance_hours = 4.0
            if hasattr(profile, 'cpap') and profile.cpap is not None:
                compliance_hours = profile.cpap.compliance_hours

            self._calculator = StatisticsCalculator(profile, compliance_hours)

            # Update usage chart compliance threshold
            if self.usage_chart is not None:
                self.usage_chart.compliance_hours = compliance_hours

            # Get data range
            date_range = self._calculator.get_available_date_range()
            if date_range:
                first, last = date_range
                self.from_date_edit.setDateRange(
                    QDate(first.year, first.month, first.day),
                    QDate(last.year, last.month, last.day)
                )
                self.to_date_edit.setDateRange(
                    QDate(first.year, first.month, first.day),
                    QDate(last.year, last.month, last.day)
                )

        # Load data for current range selection
        self._on_range_preset_changed(self.range_combo.currentIndex())

        logger.debug(f"Profile set: {profile}")

    def set_date_range(self, start: date, end: date) -> None:
        """Set the date range to display.

        Args:
            start: Start date.
            end: End date.
        """
        self._start_date = start
        self._end_date = end
        self._load_data()

    def refresh(self) -> None:
        """Refresh the display with current data."""
        self._load_data()

    # ========================================================================
    # Private Methods
    # ========================================================================

    def _clear_charts(self) -> None:
        """Clear all chart displays."""
        if self.ahi_chart is not None:
            self.ahi_chart.clear_bars()
        if self.usage_chart is not None:
            self.usage_chart.clear_bars()
        if self.pressure_chart is not None:
            self.pressure_chart.clear_bars()

    def _load_data(self) -> None:
        """Load and display data for the current date range."""
        if self._calculator is None:
            self._clear_charts()
            self.stats_panel.clear()
            return

        if self._start_date is None or self._end_date is None:
            self._clear_charts()
            self.stats_panel.clear()
            return

        # Get summaries
        self._summaries = self._calculator.get_range_summaries(
            self._start_date, self._end_date
        )

        # Update charts
        if self.ahi_chart is not None:
            self.ahi_chart.set_data(self._summaries)

        if self.usage_chart is not None:
            self.usage_chart.set_data(self._summaries)

        if self.pressure_chart is not None:
            self.pressure_chart.set_data(self._summaries)

        # Update statistics panel
        stats = self._calculator.get_range_statistics(
            self._start_date, self._end_date
        )
        self.stats_panel.update_stats(stats)

        # Emit range changed signal
        self.range_changed.emit(self._start_date, self._end_date)

        logger.debug(
            f"Loaded {len(self._summaries)} days from "
            f"{self._start_date} to {self._end_date}"
        )

    def _calculate_date_range(self, preset_days: int) -> tuple:
        """Calculate start and end dates based on preset.

        Args:
            preset_days: Number of days for preset, or -1 for all data.

        Returns:
            Tuple of (start_date, end_date).
        """
        if self._calculator is None:
            return None, None

        data_range = self._calculator.get_available_date_range()
        if data_range is None:
            return None, None

        first_data, last_data = data_range

        if preset_days == -1:
            # All data
            return first_data, last_data
        elif preset_days == 0:
            # Custom - use current from/to dates
            from_qdate = self.from_date_edit.date()
            to_qdate = self.to_date_edit.date()
            return (
                date(from_qdate.year(), from_qdate.month(), from_qdate.day()),
                date(to_qdate.year(), to_qdate.month(), to_qdate.day())
            )
        else:
            # Preset number of days from last data date
            end = last_data
            start = end - timedelta(days=preset_days - 1)
            # Don't go before first data
            if start < first_data:
                start = first_data
            return start, end

    # ========================================================================
    # Signal Handlers
    # ========================================================================

    def _on_range_preset_changed(self, index: int) -> None:
        """Handle range preset selection change.

        Args:
            index: Index of selected preset.
        """
        if index < 0 or index >= len(RANGE_PRESETS):
            return

        preset_name, preset_days = RANGE_PRESETS[index]

        # Enable/disable custom date pickers
        is_custom = (preset_days == 0)
        self.from_date_edit.setEnabled(is_custom)
        self.to_date_edit.setEnabled(is_custom)

        # Calculate date range
        start, end = self._calculate_date_range(preset_days)

        if start is not None and end is not None:
            # Update date pickers (without triggering signals)
            self.from_date_edit.blockSignals(True)
            self.to_date_edit.blockSignals(True)
            self.from_date_edit.setDate(QDate(start.year, start.month, start.day))
            self.to_date_edit.setDate(QDate(end.year, end.month, end.day))
            self.from_date_edit.blockSignals(False)
            self.to_date_edit.blockSignals(False)

            # Set range and load data
            self._start_date = start
            self._end_date = end
            self._load_data()

    def _on_custom_date_changed(self) -> None:
        """Handle custom date change."""
        # Only respond if we're in custom mode
        preset_name, preset_days = RANGE_PRESETS[self.range_combo.currentIndex()]
        if preset_days != 0:
            return

        from_qdate = self.from_date_edit.date()
        to_qdate = self.to_date_edit.date()

        self._start_date = date(
            from_qdate.year(), from_qdate.month(), from_qdate.day()
        )
        self._end_date = date(
            to_qdate.year(), to_qdate.month(), to_qdate.day()
        )

        # Ensure start <= end
        if self._start_date > self._end_date:
            self._start_date, self._end_date = self._end_date, self._start_date

        self._load_data()

    def _on_day_clicked(self, clicked_date: date) -> None:
        """Handle day click on a chart.

        Args:
            clicked_date: The date that was clicked.
        """
        logger.debug(f"Day clicked: {clicked_date}")
        self.navigate_to_day.emit(clicked_date)


# ============================================================================
# Standalone Test
# ============================================================================
def main():
    """Test the OverviewView with mock data."""
    import sys
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setApplicationName("OSCAR-Py OverviewView Test")

    # Create main window
    window = QWidget()
    window.setWindowTitle("Overview View Test")
    window.resize(1000, 700)

    layout = QVBoxLayout(window)

    # Create overview view
    overview = OverviewView()
    layout.addWidget(overview)

    # Note: Without a real profile, the charts will be empty
    # To test with real data, load a profile and call set_profile()

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
