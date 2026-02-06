"""
OSCAR-Py Statistics View Tab

This module provides the StatisticsView widget for displaying detailed
statistical reports and tables.

Reference: oscar/statistics.h, oscar/statistics.cpp

Copyright (c) 2019-2025 The OSCAR Team

This file is subject to the terms and conditions of the GNU General Public
License. See the file COPYING in the main directory of the source code
for more details.
"""

import logging
from datetime import date, timedelta
from typing import Optional, List, Dict, Any
from calendar import monthrange

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QComboBox,
    QDateEdit,
    QLabel,
    QFrame,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QTabWidget,
    QTextBrowser,
    QPushButton,
    QFileDialog,
    QMessageBox,
    QScrollArea,
    QGroupBox,
    QGridLayout,
    QApplication,
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QFont, QColor

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


# Date range presets (same as overview)
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


class SummaryStatsWidget(QFrame):
    """Widget displaying summary statistics for a date range."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QGridLayout(self)
        layout.setSpacing(20)

        # Create labeled value displays
        row = 0

        # Usage section
        usage_label = QLabel("Usage")
        usage_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(usage_label, row, 0, 1, 2)
        row += 1

        self.days_used_label = self._create_stat_row(layout, row, "Days Used:")
        row += 1
        self.total_days_label = self._create_stat_row(layout, row, "Total Days:")
        row += 1
        self.total_hours_label = self._create_stat_row(layout, row, "Total Hours:")
        row += 1
        self.avg_hours_label = self._create_stat_row(layout, row, "Average Hours:")
        row += 1
        self.median_hours_label = self._create_stat_row(layout, row, "Median Hours:")
        row += 1
        self.compliance_label = self._create_stat_row(layout, row, "Compliance:")
        row += 1

        # Add separator
        row += 1

        # AHI section
        ahi_label = QLabel("AHI / Events")
        ahi_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(ahi_label, row, 0, 1, 2)
        row += 1

        self.ahi_avg_label = self._create_stat_row(layout, row, "AHI Average:")
        row += 1
        self.ahi_median_label = self._create_stat_row(layout, row, "AHI Median:")
        row += 1
        self.ahi_90th_label = self._create_stat_row(layout, row, "AHI 90th %ile:")
        row += 1

        # Spacer column for right side stats
        layout.setColumnStretch(2, 1)

        # Right column - Pressure/Leak
        row = 0

        pressure_label = QLabel("Pressure / Leak")
        pressure_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(pressure_label, row, 3, 1, 2)
        row += 1

        self.pressure_avg_label = self._create_stat_row(layout, row, "Avg Pressure:", col=3)
        row += 1
        self.leak_avg_label = self._create_stat_row(layout, row, "Avg Leak:", col=3)
        row += 1

    def _create_stat_row(
        self,
        layout: QGridLayout,
        row: int,
        label_text: str,
        col: int = 0
    ) -> QLabel:
        """Create a label/value row."""
        label = QLabel(label_text)
        label.setStyleSheet("color: #666;")
        layout.addWidget(label, row, col)

        value = QLabel("--")
        value.setStyleSheet("font-weight: bold;")
        layout.addWidget(value, row, col + 1)

        return value

    def clear(self) -> None:
        """Clear all displayed values."""
        self.days_used_label.setText("--")
        self.total_days_label.setText("--")
        self.total_hours_label.setText("--")
        self.avg_hours_label.setText("--")
        self.median_hours_label.setText("--")
        self.compliance_label.setText("--")
        self.ahi_avg_label.setText("--")
        self.ahi_median_label.setText("--")
        self.ahi_90th_label.setText("--")
        self.pressure_avg_label.setText("--")
        self.leak_avg_label.setText("--")

    def update_stats(self, stats: 'RangeSummary') -> None:
        """Update display with statistics."""
        if stats is None:
            self.clear()
            return

        self.days_used_label.setText(str(stats.days_with_data))
        self.total_days_label.setText(str(stats.total_days))
        self.total_hours_label.setText(f"{stats.total_hours:.1f}")
        self.avg_hours_label.setText(f"{stats.avg_hours:.2f}")
        self.median_hours_label.setText(f"{stats.median_hours:.2f}")

        # Compliance with color
        compliance = stats.compliance_percent
        self.compliance_label.setText(f"{compliance:.1f}%")
        if compliance >= 70:
            self.compliance_label.setStyleSheet("font-weight: bold; color: green;")
        elif compliance >= 50:
            self.compliance_label.setStyleSheet("font-weight: bold; color: orange;")
        else:
            self.compliance_label.setStyleSheet("font-weight: bold; color: red;")

        # AHI with color
        self.ahi_avg_label.setText(f"{stats.ahi_avg:.2f}")
        self._color_ahi_label(self.ahi_avg_label, stats.ahi_avg)

        self.ahi_median_label.setText(f"{stats.ahi_median:.2f}")
        self._color_ahi_label(self.ahi_median_label, stats.ahi_median)

        self.ahi_90th_label.setText(f"{stats.ahi_90th:.2f}")
        self._color_ahi_label(self.ahi_90th_label, stats.ahi_90th)

        self.pressure_avg_label.setText(f"{stats.pressure_avg:.1f} cmH2O")
        self.leak_avg_label.setText(f"{stats.leak_avg:.1f} L/min")

    def _color_ahi_label(self, label: QLabel, ahi: float) -> None:
        """Apply color to AHI label based on severity."""
        if ahi < 5:
            label.setStyleSheet("font-weight: bold; color: green;")
        elif ahi < 15:
            label.setStyleSheet("font-weight: bold; color: orange;")
        elif ahi < 30:
            label.setStyleSheet("font-weight: bold; color: #ff6600;")
        else:
            label.setStyleSheet("font-weight: bold; color: red;")


class MonthlyBreakdownTable(QTableWidget):
    """Table showing monthly breakdown of statistics."""

    COLUMNS = [
        ("Month", 100),
        ("Days", 50),
        ("Hours", 70),
        ("Avg Hrs", 70),
        ("AHI Avg", 70),
        ("AHI Med", 70),
        ("Compliance", 80),
        ("Pressure", 70),
        ("Leak", 60),
    ]

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_table()

    def _setup_table(self) -> None:
        """Configure table columns and appearance."""
        self.setColumnCount(len(self.COLUMNS))
        self.setHorizontalHeaderLabels([col[0] for col in self.COLUMNS])

        # Set column widths
        header = self.horizontalHeader()
        for i, (_, width) in enumerate(self.COLUMNS):
            self.setColumnWidth(i, width)

        header.setStretchLastSection(True)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

    def clear_data(self) -> None:
        """Clear all table data."""
        self.setRowCount(0)

    def set_monthly_data(
        self,
        summaries: List['DaySummary'],
        compliance_hours: float = 4.0
    ) -> None:
        """Populate table with monthly breakdown.

        Args:
            summaries: List of daily summaries.
            compliance_hours: Hours threshold for compliance.
        """
        self.clear_data()

        if not summaries:
            return

        # Group by month
        monthly_data: Dict[str, List['DaySummary']] = {}
        for s in summaries:
            key = s.date.strftime("%Y-%m")
            if key not in monthly_data:
                monthly_data[key] = []
            monthly_data[key].append(s)

        # Sort by month
        sorted_months = sorted(monthly_data.keys(), reverse=True)

        self.setRowCount(len(sorted_months))

        for row, month_key in enumerate(sorted_months):
            month_summaries = monthly_data[month_key]

            # Calculate monthly stats
            days = len(month_summaries)
            total_hours = sum(s.hours for s in month_summaries)
            avg_hours = total_hours / days if days > 0 else 0

            ahi_values = [s.ahi for s in month_summaries if s.hours > 0]
            ahi_avg = sum(ahi_values) / len(ahi_values) if ahi_values else 0
            ahi_med = self._median(ahi_values)

            compliant = sum(1 for s in month_summaries if s.hours >= compliance_hours)
            compliance = (compliant / days * 100) if days > 0 else 0

            pressure_values = [s.pressure_avg for s in month_summaries if s.pressure_avg > 0]
            pressure_avg = sum(pressure_values) / len(pressure_values) if pressure_values else 0

            leak_values = [s.leak_avg for s in month_summaries if s.leak_avg >= 0]
            leak_avg = sum(leak_values) / len(leak_values) if leak_values else 0

            # Format month label
            year, month = month_key.split("-")
            month_label = date(int(year), int(month), 1).strftime("%B %Y")

            # Populate row
            self.setItem(row, 0, QTableWidgetItem(month_label))
            self.setItem(row, 1, QTableWidgetItem(str(days)))
            self.setItem(row, 2, QTableWidgetItem(f"{total_hours:.1f}"))
            self.setItem(row, 3, QTableWidgetItem(f"{avg_hours:.2f}"))
            self.setItem(row, 4, self._create_ahi_item(ahi_avg))
            self.setItem(row, 5, self._create_ahi_item(ahi_med))
            self.setItem(row, 6, self._create_compliance_item(compliance))
            self.setItem(row, 7, QTableWidgetItem(f"{pressure_avg:.1f}"))
            self.setItem(row, 8, QTableWidgetItem(f"{leak_avg:.1f}"))

    def _median(self, values: List[float]) -> float:
        """Calculate median of a list."""
        if not values:
            return 0.0
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        if n % 2 == 0:
            return (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2
        return sorted_vals[n // 2]

    def _create_ahi_item(self, ahi: float) -> QTableWidgetItem:
        """Create table item with AHI coloring."""
        item = QTableWidgetItem(f"{ahi:.2f}")
        if ahi < 5:
            item.setForeground(QColor(0, 150, 0))
        elif ahi < 15:
            item.setForeground(QColor(200, 150, 0))
        elif ahi < 30:
            item.setForeground(QColor(255, 100, 0))
        else:
            item.setForeground(QColor(200, 0, 0))
        return item

    def _create_compliance_item(self, compliance: float) -> QTableWidgetItem:
        """Create table item with compliance coloring."""
        item = QTableWidgetItem(f"{compliance:.1f}%")
        if compliance >= 70:
            item.setForeground(QColor(0, 150, 0))
        elif compliance >= 50:
            item.setForeground(QColor(200, 150, 0))
        else:
            item.setForeground(QColor(200, 0, 0))
        return item


class DailyBreakdownTable(QTableWidget):
    """Table showing daily breakdown of statistics."""

    COLUMNS = [
        ("Date", 100),
        ("Hours", 60),
        ("AHI", 60),
        ("OA", 50),
        ("CA", 50),
        ("H", 50),
        ("RERA", 50),
        ("Pressure", 70),
        ("Leak", 60),
    ]

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_table()

    def _setup_table(self) -> None:
        """Configure table columns and appearance."""
        self.setColumnCount(len(self.COLUMNS))
        self.setHorizontalHeaderLabels([col[0] for col in self.COLUMNS])

        header = self.horizontalHeader()
        for i, (_, width) in enumerate(self.COLUMNS):
            self.setColumnWidth(i, width)

        header.setStretchLastSection(True)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setSortingEnabled(True)

    def clear_data(self) -> None:
        """Clear all table data."""
        self.setRowCount(0)

    def set_daily_data(
        self,
        summaries: List['DaySummary'],
        compliance_hours: float = 4.0
    ) -> None:
        """Populate table with daily data.

        Args:
            summaries: List of daily summaries.
            compliance_hours: Hours threshold for compliance.
        """
        self.clear_data()

        if not summaries:
            return

        # Sort by date descending
        sorted_summaries = sorted(summaries, key=lambda s: s.date, reverse=True)

        self.setRowCount(len(sorted_summaries))

        for row, s in enumerate(sorted_summaries):
            # Date
            date_item = QTableWidgetItem(s.date.strftime("%Y-%m-%d"))
            self.setItem(row, 0, date_item)

            # Hours with compliance coloring
            hours_item = QTableWidgetItem(f"{s.hours:.2f}")
            if s.hours >= compliance_hours:
                hours_item.setForeground(QColor(0, 150, 0))
            else:
                hours_item.setForeground(QColor(200, 0, 0))
            self.setItem(row, 1, hours_item)

            # AHI with severity coloring
            ahi_item = QTableWidgetItem(f"{s.ahi:.2f}")
            if s.ahi < 5:
                ahi_item.setForeground(QColor(0, 150, 0))
            elif s.ahi < 15:
                ahi_item.setForeground(QColor(200, 150, 0))
            elif s.ahi < 30:
                ahi_item.setForeground(QColor(255, 100, 0))
            else:
                ahi_item.setForeground(QColor(200, 0, 0))
            self.setItem(row, 2, ahi_item)

            # Event counts
            self.setItem(row, 3, QTableWidgetItem(str(s.oa_count)))
            self.setItem(row, 4, QTableWidgetItem(str(s.ca_count)))
            self.setItem(row, 5, QTableWidgetItem(str(s.h_count)))
            self.setItem(row, 6, QTableWidgetItem(str(s.rera_count)))

            # Pressure and leak
            self.setItem(row, 7, QTableWidgetItem(f"{s.pressure_avg:.1f}"))
            self.setItem(row, 8, QTableWidgetItem(f"{s.leak_avg:.1f}"))


class StatisticsView(QWidget):
    """Main statistics view tab widget.

    Provides detailed statistical reports including:
    - Summary statistics for selected date range
    - Monthly breakdown table
    - Daily breakdown table
    - Export functionality
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._profile: Optional['Profile'] = None
        self._calculator: Optional['StatisticsCalculator'] = None
        self._summaries: List['DaySummary'] = []
        self._start_date: Optional[date] = None
        self._end_date: Optional[date] = None
        self._compliance_hours: float = 4.0

        self._setup_ui()
        self._connect_signals()

        logger.info("StatisticsView initialized")

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        # Date range selector
        self._create_date_selector(main_layout)

        # Summary stats
        self.summary_widget = SummaryStatsWidget()
        main_layout.addWidget(self.summary_widget)

        # Tab widget for tables
        self.tab_widget = QTabWidget()

        # Monthly breakdown tab
        self.monthly_table = MonthlyBreakdownTable()
        self.tab_widget.addTab(self.monthly_table, "Monthly Breakdown")

        # Daily breakdown tab
        self.daily_table = DailyBreakdownTable()
        self.tab_widget.addTab(self.daily_table, "Daily Breakdown")

        # Machine info tab
        self.machine_browser = QTextBrowser()
        self.tab_widget.addTab(self.machine_browser, "Machine Info")

        main_layout.addWidget(self.tab_widget, 1)

        # Export buttons
        self._create_export_buttons(main_layout)

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
        self.from_date_edit.setEnabled(False)
        selector_layout.addWidget(self.from_date_edit)

        # To date
        selector_layout.addWidget(QLabel("To:"))
        self.to_date_edit = QDateEdit()
        self.to_date_edit.setCalendarPopup(True)
        self.to_date_edit.setEnabled(False)
        selector_layout.addWidget(self.to_date_edit)

        selector_layout.addStretch()

        # Refresh button
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self._load_data)
        selector_layout.addWidget(self.refresh_button)

        layout.addWidget(selector_frame)

    def _create_export_buttons(self, layout: QVBoxLayout) -> None:
        """Create export buttons."""
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.copy_button = QPushButton("Copy to Clipboard")
        self.copy_button.clicked.connect(self._on_copy_to_clipboard)
        button_layout.addWidget(self.copy_button)

        self.export_button = QPushButton("Export to CSV")
        self.export_button.clicked.connect(self._on_export_csv)
        button_layout.addWidget(self.export_button)

        layout.addLayout(button_layout)

    def _connect_signals(self) -> None:
        """Connect widget signals to slots."""
        self.range_combo.currentIndexChanged.connect(self._on_range_preset_changed)
        self.from_date_edit.dateChanged.connect(self._on_custom_date_changed)
        self.to_date_edit.dateChanged.connect(self._on_custom_date_changed)

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
            self._clear_display()
            return

        # Create statistics calculator
        if StatisticsCalculator is not None:
            self._compliance_hours = 4.0
            if hasattr(profile, 'cpap') and profile.cpap is not None:
                self._compliance_hours = profile.cpap.compliance_hours

            self._calculator = StatisticsCalculator(profile, self._compliance_hours)

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

        # Update machine info
        self._update_machine_info()

        # Load data for current range selection
        self._on_range_preset_changed(self.range_combo.currentIndex())

        logger.debug(f"Profile set: {profile}")

    def refresh(self) -> None:
        """Refresh the display."""
        self._load_data()

    # ========================================================================
    # Private Methods
    # ========================================================================

    def _clear_display(self) -> None:
        """Clear all displays."""
        self.summary_widget.clear()
        self.monthly_table.clear_data()
        self.daily_table.clear_data()
        self.machine_browser.clear()

    def _load_data(self) -> None:
        """Load and display data for the current date range."""
        if self._calculator is None:
            self._clear_display()
            return

        if self._start_date is None or self._end_date is None:
            self._clear_display()
            return

        # Get summaries
        self._summaries = self._calculator.get_range_summaries(
            self._start_date, self._end_date
        )

        # Update summary stats
        stats = self._calculator.get_range_statistics(
            self._start_date, self._end_date
        )
        self.summary_widget.update_stats(stats)

        # Update monthly table
        self.monthly_table.set_monthly_data(self._summaries, self._compliance_hours)

        # Update daily table
        self.daily_table.set_daily_data(self._summaries, self._compliance_hours)

        logger.debug(
            f"Loaded {len(self._summaries)} days from "
            f"{self._start_date} to {self._end_date}"
        )

    def _update_machine_info(self) -> None:
        """Update machine info display."""
        if self._profile is None:
            self.machine_browser.setHtml("<p>No profile loaded</p>")
            return

        html = "<html><head><style>"
        html += "body { font-family: sans-serif; margin: 10px; }"
        html += "h3 { color: #333; margin-top: 15px; }"
        html += "table { border-collapse: collapse; width: 100%; }"
        html += "td { padding: 3px 8px; border-bottom: 1px solid #eee; }"
        html += ".label { color: #666; width: 40%; }"
        html += ".value { font-weight: bold; }"
        html += "</style></head><body>"

        html += "<h3>Profile Information</h3>"
        html += "<table>"

        # Profile path
        if hasattr(self._profile, 'path'):
            html += f"<tr><td class='label'>Profile Path:</td><td class='value'>{self._profile.path}</td></tr>"

        # Date range
        if self._calculator:
            date_range = self._calculator.get_available_date_range()
            if date_range:
                first, last = date_range
                days = (last - first).days + 1
                html += f"<tr><td class='label'>First Day:</td><td class='value'>{first}</td></tr>"
                html += f"<tr><td class='label'>Last Day:</td><td class='value'>{last}</td></tr>"
                html += f"<tr><td class='label'>Total Days:</td><td class='value'>{days}</td></tr>"

        html += "</table>"

        # Machine information
        if hasattr(self._profile, 'm_machlist') and self._profile.m_machlist:
            for machine in self._profile.m_machlist:
                html += f"<h3>Machine: {getattr(machine, 'brand', 'Unknown')} {getattr(machine, 'model', '')}</h3>"
                html += "<table>"

                if hasattr(machine, 'serial'):
                    html += f"<tr><td class='label'>Serial:</td><td class='value'>{machine.serial}</td></tr>"
                if hasattr(machine, 'type'):
                    html += f"<tr><td class='label'>Type:</td><td class='value'>{machine.type}</td></tr>"
                if hasattr(machine, 'first_day'):
                    html += f"<tr><td class='label'>First Session:</td><td class='value'>{machine.first_day}</td></tr>"
                if hasattr(machine, 'last_day'):
                    html += f"<tr><td class='label'>Last Session:</td><td class='value'>{machine.last_day}</td></tr>"

                html += "</table>"

        html += "</body></html>"
        self.machine_browser.setHtml(html)

    def _calculate_date_range(self, preset_days: int) -> tuple:
        """Calculate start and end dates based on preset."""
        if self._calculator is None:
            return None, None

        data_range = self._calculator.get_available_date_range()
        if data_range is None:
            return None, None

        first_data, last_data = data_range

        if preset_days == -1:
            return first_data, last_data
        elif preset_days == 0:
            from_qdate = self.from_date_edit.date()
            to_qdate = self.to_date_edit.date()
            return (
                date(from_qdate.year(), from_qdate.month(), from_qdate.day()),
                date(to_qdate.year(), to_qdate.month(), to_qdate.day())
            )
        else:
            end = last_data
            start = end - timedelta(days=preset_days - 1)
            if start < first_data:
                start = first_data
            return start, end

    # ========================================================================
    # Signal Handlers
    # ========================================================================

    def _on_range_preset_changed(self, index: int) -> None:
        """Handle range preset selection change."""
        if index < 0 or index >= len(RANGE_PRESETS):
            return

        preset_name, preset_days = RANGE_PRESETS[index]

        is_custom = (preset_days == 0)
        self.from_date_edit.setEnabled(is_custom)
        self.to_date_edit.setEnabled(is_custom)

        start, end = self._calculate_date_range(preset_days)

        if start is not None and end is not None:
            self.from_date_edit.blockSignals(True)
            self.to_date_edit.blockSignals(True)
            self.from_date_edit.setDate(QDate(start.year, start.month, start.day))
            self.to_date_edit.setDate(QDate(end.year, end.month, end.day))
            self.from_date_edit.blockSignals(False)
            self.to_date_edit.blockSignals(False)

            self._start_date = start
            self._end_date = end
            self._load_data()

    def _on_custom_date_changed(self) -> None:
        """Handle custom date change."""
        preset_name, preset_days = RANGE_PRESETS[self.range_combo.currentIndex()]
        if preset_days != 0:
            return

        from_qdate = self.from_date_edit.date()
        to_qdate = self.to_date_edit.date()

        self._start_date = date(from_qdate.year(), from_qdate.month(), from_qdate.day())
        self._end_date = date(to_qdate.year(), to_qdate.month(), to_qdate.day())

        if self._start_date > self._end_date:
            self._start_date, self._end_date = self._end_date, self._start_date

        self._load_data()

    def _on_copy_to_clipboard(self) -> None:
        """Copy current data to clipboard."""
        current_tab = self.tab_widget.currentIndex()

        if current_tab == 0:  # Monthly
            text = self._table_to_text(self.monthly_table)
        elif current_tab == 1:  # Daily
            text = self._table_to_text(self.daily_table)
        else:  # Machine info
            text = self.machine_browser.toPlainText()

        clipboard = QApplication.clipboard()
        clipboard.setText(text)

        logger.info("Statistics copied to clipboard")

    def _on_export_csv(self) -> None:
        """Export current data to CSV file."""
        current_tab = self.tab_widget.currentIndex()

        if current_tab == 0:
            default_name = "monthly_statistics.csv"
            table = self.monthly_table
        elif current_tab == 1:
            default_name = "daily_statistics.csv"
            table = self.daily_table
        else:
            QMessageBox.information(
                self, "Export",
                "Machine info cannot be exported to CSV."
            )
            return

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export to CSV",
            default_name,
            "CSV Files (*.csv)"
        )

        if filename:
            text = self._table_to_csv(table)
            try:
                with open(filename, 'w') as f:
                    f.write(text)
                logger.info(f"Statistics exported to {filename}")
            except Exception as e:
                QMessageBox.critical(
                    self, "Export Error",
                    f"Failed to export: {e}"
                )

    def _table_to_text(self, table: QTableWidget) -> str:
        """Convert table to tab-separated text."""
        lines = []

        # Headers
        headers = []
        for col in range(table.columnCount()):
            item = table.horizontalHeaderItem(col)
            headers.append(item.text() if item else "")
        lines.append("\t".join(headers))

        # Data
        for row in range(table.rowCount()):
            cells = []
            for col in range(table.columnCount()):
                item = table.item(row, col)
                cells.append(item.text() if item else "")
            lines.append("\t".join(cells))

        return "\n".join(lines)

    def _table_to_csv(self, table: QTableWidget) -> str:
        """Convert table to CSV format."""
        lines = []

        # Headers
        headers = []
        for col in range(table.columnCount()):
            item = table.horizontalHeaderItem(col)
            text = item.text() if item else ""
            headers.append(f'"{text}"')
        lines.append(",".join(headers))

        # Data
        for row in range(table.rowCount()):
            cells = []
            for col in range(table.columnCount()):
                item = table.item(row, col)
                text = item.text() if item else ""
                cells.append(f'"{text}"')
            lines.append(",".join(cells))

        return "\n".join(lines)
