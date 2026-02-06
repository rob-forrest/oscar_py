"""
OSCAR-Py Preferences Dialog

This module provides the PreferencesDialog for configuring application
and profile settings.

Reference: oscar/preferencesdialog.h, oscar/preferencesdialog.cpp

Copyright (c) 2019-2025 The OSCAR Team

This file is subject to the terms and conditions of the GNU General Public
License. See the file COPYING in the main directory of the source code
for more details.
"""

import logging
from datetime import time
from typing import Optional

from PyQt6.QtWidgets import (
    QDialog,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QGroupBox,
    QFormLayout,
    QLabel,
    QComboBox,
    QCheckBox,
    QSpinBox,
    QDoubleSpinBox,
    QTimeEdit,
    QPushButton,
    QDialogButtonBox,
    QScrollArea,
    QFrame,
)
from PyQt6.QtCore import Qt, QTime

# Import profile settings with fallback
try:
    from sleeplib.profile import (
        Profile,
        UnitSystem,
        MaskType,
        CPAPSettings,
        SessionSettings,
        UserSettings,
        OxiSettings,
    )
    from sleeplib.schema import CPAPMode
except ImportError:
    Profile = None
    UnitSystem = None
    MaskType = None
    CPAPSettings = None
    SessionSettings = None
    UserSettings = None
    OxiSettings = None
    CPAPMode = None

logger = logging.getLogger(__name__)


class GeneralSettingsTab(QWidget):
    """Tab for general application settings."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Display settings
        display_group = QGroupBox("Display")
        display_layout = QFormLayout(display_group)

        self.unit_system_combo = QComboBox()
        self.unit_system_combo.addItem("Metric", 0)
        self.unit_system_combo.addItem("Imperial", 1)
        display_layout.addRow("Unit System:", self.unit_system_combo)

        self.skip_empty_days_check = QCheckBox()
        self.skip_empty_days_check.setToolTip(
            "Skip days without data when navigating"
        )
        display_layout.addRow("Skip Empty Days:", self.skip_empty_days_check)

        layout.addWidget(display_group)

        # Calculations settings
        calc_group = QGroupBox("Calculations")
        calc_layout = QFormLayout(calc_group)

        self.calculate_rdi_check = QCheckBox()
        self.calculate_rdi_check.setToolTip(
            "Include RERA events in AHI calculation (shows as RDI)"
        )
        calc_layout.addRow("Calculate RDI:", self.calculate_rdi_check)

        self.event_window_spin = QDoubleSpinBox()
        self.event_window_spin.setRange(0.5, 10.0)
        self.event_window_spin.setSingleStep(0.5)
        self.event_window_spin.setSuffix(" seconds")
        self.event_window_spin.setToolTip(
            "Time window around events for detailed view"
        )
        calc_layout.addRow("Event Window:", self.event_window_spin)

        self.percentile_spin = QDoubleSpinBox()
        self.percentile_spin.setRange(50.0, 99.9)
        self.percentile_spin.setSingleStep(1.0)
        self.percentile_spin.setSuffix(" %")
        self.percentile_spin.setToolTip(
            "Percentile for pressure/leak calculations"
        )
        calc_layout.addRow("Preferred Percentile:", self.percentile_spin)

        layout.addWidget(calc_group)

        # Flags settings
        flags_group = QGroupBox("Event Flags")
        flags_layout = QFormLayout(flags_group)

        self.show_unknown_flags_check = QCheckBox()
        self.show_unknown_flags_check.setToolTip(
            "Show unrecognized event flags from device"
        )
        flags_layout.addRow("Show Unknown Flags:", self.show_unknown_flags_check)

        layout.addWidget(flags_group)

        layout.addStretch()

    def load_settings(self, profile: 'Profile') -> None:
        """Load settings from profile."""
        if profile is None or profile.general is None:
            return

        general = profile.general

        # Unit system
        idx = self.unit_system_combo.findData(int(general.unit_system))
        if idx >= 0:
            self.unit_system_combo.setCurrentIndex(idx)

        self.skip_empty_days_check.setChecked(general.skip_empty_days)
        self.calculate_rdi_check.setChecked(general.calculate_rdi)
        self.percentile_spin.setValue(general.pref_calc_percentile)

        # Event window from general settings
        event_window = profile.get("EventWindowSize")
        if event_window:
            self.event_window_spin.setValue(float(event_window))
        else:
            self.event_window_spin.setValue(3.0)

        show_unknown = profile.get("ShowUnknownFlags")
        self.show_unknown_flags_check.setChecked(bool(show_unknown))

    def save_settings(self, profile: 'Profile') -> None:
        """Save settings to profile."""
        if profile is None or profile.general is None:
            return

        general = profile.general

        unit_data = self.unit_system_combo.currentData()
        if UnitSystem is not None:
            general.unit_system = UnitSystem(unit_data)

        general.skip_empty_days = self.skip_empty_days_check.isChecked()
        general.calculate_rdi = self.calculate_rdi_check.isChecked()
        general.pref_calc_percentile = self.percentile_spin.value()

        profile.set("EventWindowSize", self.event_window_spin.value())
        profile.set("ShowUnknownFlags", self.show_unknown_flags_check.isChecked())


class CPAPSettingsTab(QWidget):
    """Tab for CPAP-specific settings."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Compliance settings
        compliance_group = QGroupBox("Compliance")
        compliance_layout = QFormLayout(compliance_group)

        self.compliance_hours_spin = QDoubleSpinBox()
        self.compliance_hours_spin.setRange(0.0, 12.0)
        self.compliance_hours_spin.setSingleStep(0.5)
        self.compliance_hours_spin.setSuffix(" hours")
        self.compliance_hours_spin.setToolTip(
            "Minimum hours for a day to be considered compliant"
        )
        compliance_layout.addRow("Compliance Threshold:", self.compliance_hours_spin)

        layout.addWidget(compliance_group)

        # AHI settings
        ahi_group = QGroupBox("AHI Calculation")
        ahi_layout = QFormLayout(ahi_group)

        self.ahi_window_spin = QDoubleSpinBox()
        self.ahi_window_spin.setRange(15.0, 120.0)
        self.ahi_window_spin.setSingleStep(15.0)
        self.ahi_window_spin.setSuffix(" minutes")
        self.ahi_window_spin.setToolTip(
            "Time window for running AHI calculation"
        )
        ahi_layout.addRow("AHI Window:", self.ahi_window_spin)

        self.ahi_reset_check = QCheckBox()
        self.ahi_reset_check.setToolTip(
            "Reset AHI calculation at midnight"
        )
        ahi_layout.addRow("Reset AHI at Midnight:", self.ahi_reset_check)

        layout.addWidget(ahi_group)

        # Leak settings
        leak_group = QGroupBox("Leak Settings")
        leak_layout = QFormLayout(leak_group)

        self.leak_redline_spin = QDoubleSpinBox()
        self.leak_redline_spin.setRange(0.0, 100.0)
        self.leak_redline_spin.setSingleStep(1.0)
        self.leak_redline_spin.setSuffix(" L/min")
        self.leak_redline_spin.setToolTip(
            "Threshold for highlighting excessive leaks"
        )
        leak_layout.addRow("Leak Redline:", self.leak_redline_spin)

        self.show_leak_redline_check = QCheckBox()
        self.show_leak_redline_check.setToolTip(
            "Show leak threshold line on graphs"
        )
        leak_layout.addRow("Show Redline:", self.show_leak_redline_check)

        self.calc_unintentional_leaks_check = QCheckBox()
        self.calc_unintentional_leaks_check.setToolTip(
            "Calculate unintentional leaks from total leak"
        )
        leak_layout.addRow("Calculate Unintentional Leaks:", self.calc_unintentional_leaks_check)

        layout.addWidget(leak_group)

        # Mask settings
        mask_group = QGroupBox("Mask")
        mask_layout = QFormLayout(mask_group)

        self.mask_type_combo = QComboBox()
        self.mask_type_combo.addItem("Unknown", 0)
        self.mask_type_combo.addItem("Nasal Pillows", 1)
        self.mask_type_combo.addItem("Hybrid", 2)
        self.mask_type_combo.addItem("Standard Nasal", 3)
        self.mask_type_combo.addItem("Full Face", 4)
        mask_layout.addRow("Mask Type:", self.mask_type_combo)

        layout.addWidget(mask_group)

        # Clinical mode
        clinical_group = QGroupBox("Clinical")
        clinical_layout = QFormLayout(clinical_group)

        self.clinical_mode_check = QCheckBox()
        self.clinical_mode_check.setToolTip(
            "Enable clinical mode for detailed analysis"
        )
        clinical_layout.addRow("Clinical Mode:", self.clinical_mode_check)

        layout.addWidget(clinical_group)

        layout.addStretch()

    def load_settings(self, profile: 'Profile') -> None:
        """Load settings from profile."""
        if profile is None or profile.cpap is None:
            return

        cpap = profile.cpap

        self.compliance_hours_spin.setValue(cpap.compliance_hours)
        self.ahi_window_spin.setValue(cpap.ahi_window)
        self.leak_redline_spin.setValue(cpap.leak_redline)
        self.clinical_mode_check.setChecked(cpap.clinical_mode)

        # AHI reset
        ahi_reset = profile.get("AHIReset")
        self.ahi_reset_check.setChecked(bool(ahi_reset))

        # Show leak redline
        show_redline = profile.get("ShowLeakRedline")
        self.show_leak_redline_check.setChecked(show_redline if show_redline is not None else True)

        # Calculate unintentional leaks
        calc_leaks = profile.get("CalculateUnintentionalLeaks")
        self.calc_unintentional_leaks_check.setChecked(calc_leaks if calc_leaks is not None else True)

        # Mask type
        idx = self.mask_type_combo.findData(int(cpap.mask_type))
        if idx >= 0:
            self.mask_type_combo.setCurrentIndex(idx)

    def save_settings(self, profile: 'Profile') -> None:
        """Save settings to profile."""
        if profile is None or profile.cpap is None:
            return

        cpap = profile.cpap

        cpap.compliance_hours = self.compliance_hours_spin.value()
        cpap.ahi_window = self.ahi_window_spin.value()
        cpap.leak_redline = self.leak_redline_spin.value()
        cpap.clinical_mode = self.clinical_mode_check.isChecked()

        profile.set("AHIReset", self.ahi_reset_check.isChecked())
        profile.set("ShowLeakRedline", self.show_leak_redline_check.isChecked())
        profile.set("CalculateUnintentionalLeaks", self.calc_unintentional_leaks_check.isChecked())

        mask_data = self.mask_type_combo.currentData()
        if MaskType is not None:
            cpap.mask_type = MaskType(mask_data)


class ImportSettingsTab(QWidget):
    """Tab for import/session settings."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Day boundary settings
        day_group = QGroupBox("Day Boundary")
        day_layout = QFormLayout(day_group)

        self.day_split_time_edit = QTimeEdit()
        self.day_split_time_edit.setDisplayFormat("HH:mm")
        self.day_split_time_edit.setToolTip(
            "Time at which a new 'day' starts (usually noon)"
        )
        day_layout.addRow("Day Split Time:", self.day_split_time_edit)

        layout.addWidget(day_group)

        # Session handling
        session_group = QGroupBox("Session Handling")
        session_layout = QFormLayout(session_group)

        self.combine_sessions_spin = QDoubleSpinBox()
        self.combine_sessions_spin.setRange(0.0, 480.0)
        self.combine_sessions_spin.setSingleStep(30.0)
        self.combine_sessions_spin.setSuffix(" minutes")
        self.combine_sessions_spin.setToolTip(
            "Combine sessions that are closer than this interval"
        )
        session_layout.addRow("Combine Close Sessions:", self.combine_sessions_spin)

        self.ignore_short_sessions_spin = QDoubleSpinBox()
        self.ignore_short_sessions_spin.setRange(0.0, 60.0)
        self.ignore_short_sessions_spin.setSingleStep(1.0)
        self.ignore_short_sessions_spin.setSuffix(" minutes")
        self.ignore_short_sessions_spin.setToolTip(
            "Ignore sessions shorter than this duration"
        )
        session_layout.addRow("Ignore Sessions Shorter Than:", self.ignore_short_sessions_spin)

        layout.addWidget(session_group)

        # Backup settings
        backup_group = QGroupBox("Backup")
        backup_layout = QFormLayout(backup_group)

        self.backup_card_data_check = QCheckBox()
        self.backup_card_data_check.setToolTip(
            "Create backup of SD card data during import"
        )
        backup_layout.addRow("Backup Card Data:", self.backup_card_data_check)

        self.compress_backup_check = QCheckBox()
        self.compress_backup_check.setToolTip(
            "Compress backup data to save disk space"
        )
        backup_layout.addRow("Compress Backup:", self.compress_backup_check)

        layout.addWidget(backup_group)

        # Warning settings
        warnings_group = QGroupBox("Warnings")
        warnings_layout = QFormLayout(warnings_group)

        self.warn_untested_check = QCheckBox()
        self.warn_untested_check.setToolTip(
            "Show warning when importing from untested machine"
        )
        warnings_layout.addRow("Warn on Untested Machine:", self.warn_untested_check)

        self.warn_unexpected_check = QCheckBox()
        self.warn_unexpected_check.setToolTip(
            "Show warning when encountering unexpected data"
        )
        warnings_layout.addRow("Warn on Unexpected Data:", self.warn_unexpected_check)

        layout.addWidget(warnings_group)

        layout.addStretch()

    def load_settings(self, profile: 'Profile') -> None:
        """Load settings from profile."""
        if profile is None or profile.session is None:
            return

        session = profile.session

        # Day split time
        split_time = session.day_split_time
        self.day_split_time_edit.setTime(QTime(split_time.hour, split_time.minute))

        self.combine_sessions_spin.setValue(session.combine_close_sessions)
        self.ignore_short_sessions_spin.setValue(session.ignore_short_sessions)
        self.backup_card_data_check.setChecked(session.backup_card_data)
        self.warn_untested_check.setChecked(session.warn_on_untested_machine)

        # Compress backup
        compress = profile.get("CompressBackupData")
        self.compress_backup_check.setChecked(bool(compress))

        # Warn unexpected
        warn_unexpected = profile.get("WarnOnUnexpectedData")
        self.warn_unexpected_check.setChecked(warn_unexpected if warn_unexpected is not None else True)

    def save_settings(self, profile: 'Profile') -> None:
        """Save settings to profile."""
        if profile is None or profile.session is None:
            return

        session = profile.session

        qtime = self.day_split_time_edit.time()
        session.day_split_time = time(qtime.hour(), qtime.minute())

        session.combine_close_sessions = self.combine_sessions_spin.value()
        session.ignore_short_sessions = self.ignore_short_sessions_spin.value()
        session.backup_card_data = self.backup_card_data_check.isChecked()
        session.warn_on_untested_machine = self.warn_untested_check.isChecked()

        profile.set("CompressBackupData", self.compress_backup_check.isChecked())
        profile.set("WarnOnUnexpectedData", self.warn_unexpected_check.isChecked())


class OximetrySettingsTab(QWidget):
    """Tab for oximetry settings."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Enable oximetry
        enable_group = QGroupBox("General")
        enable_layout = QFormLayout(enable_group)

        self.enable_oximetry_check = QCheckBox()
        self.enable_oximetry_check.setToolTip(
            "Enable oximetry data analysis"
        )
        enable_layout.addRow("Enable Oximetry:", self.enable_oximetry_check)

        layout.addWidget(enable_group)

        # SpO2 drop settings
        spo2_group = QGroupBox("SpO2 Drop Detection")
        spo2_layout = QFormLayout(spo2_group)

        self.spo2_drop_duration_spin = QDoubleSpinBox()
        self.spo2_drop_duration_spin.setRange(1.0, 30.0)
        self.spo2_drop_duration_spin.setSingleStep(1.0)
        self.spo2_drop_duration_spin.setSuffix(" seconds")
        self.spo2_drop_duration_spin.setToolTip(
            "Minimum duration for SpO2 drop event"
        )
        spo2_layout.addRow("Drop Duration:", self.spo2_drop_duration_spin)

        self.spo2_drop_percentage_spin = QDoubleSpinBox()
        self.spo2_drop_percentage_spin.setRange(1.0, 10.0)
        self.spo2_drop_percentage_spin.setSingleStep(0.5)
        self.spo2_drop_percentage_spin.setSuffix(" %")
        self.spo2_drop_percentage_spin.setToolTip(
            "Minimum SpO2 drop percentage to flag"
        )
        spo2_layout.addRow("Drop Percentage:", self.spo2_drop_percentage_spin)

        self.desat_threshold_spin = QDoubleSpinBox()
        self.desat_threshold_spin.setRange(70.0, 95.0)
        self.desat_threshold_spin.setSingleStep(1.0)
        self.desat_threshold_spin.setSuffix(" %")
        self.desat_threshold_spin.setToolTip(
            "SpO2 level considered desaturation"
        )
        spo2_layout.addRow("Desaturation Threshold:", self.desat_threshold_spin)

        layout.addWidget(spo2_group)

        # Pulse settings
        pulse_group = QGroupBox("Pulse Rate")
        pulse_layout = QFormLayout(pulse_group)

        self.pulse_change_duration_spin = QDoubleSpinBox()
        self.pulse_change_duration_spin.setRange(1.0, 30.0)
        self.pulse_change_duration_spin.setSingleStep(1.0)
        self.pulse_change_duration_spin.setSuffix(" seconds")
        self.pulse_change_duration_spin.setToolTip(
            "Minimum duration for pulse change event"
        )
        pulse_layout.addRow("Change Duration:", self.pulse_change_duration_spin)

        self.pulse_change_bpm_spin = QDoubleSpinBox()
        self.pulse_change_bpm_spin.setRange(1.0, 30.0)
        self.pulse_change_bpm_spin.setSingleStep(1.0)
        self.pulse_change_bpm_spin.setSuffix(" bpm")
        self.pulse_change_bpm_spin.setToolTip(
            "Minimum pulse change to flag"
        )
        pulse_layout.addRow("Change Threshold:", self.pulse_change_bpm_spin)

        self.pulse_above_spin = QDoubleSpinBox()
        self.pulse_above_spin.setRange(60.0, 200.0)
        self.pulse_above_spin.setSingleStep(5.0)
        self.pulse_above_spin.setSuffix(" bpm")
        self.pulse_above_spin.setToolTip(
            "Flag pulse rates above this value"
        )
        pulse_layout.addRow("Flag Pulse Above:", self.pulse_above_spin)

        self.pulse_below_spin = QDoubleSpinBox()
        self.pulse_below_spin.setRange(20.0, 80.0)
        self.pulse_below_spin.setSingleStep(5.0)
        self.pulse_below_spin.setSuffix(" bpm")
        self.pulse_below_spin.setToolTip(
            "Flag pulse rates below this value"
        )
        pulse_layout.addRow("Flag Pulse Below:", self.pulse_below_spin)

        layout.addWidget(pulse_group)

        layout.addStretch()

    def load_settings(self, profile: 'Profile') -> None:
        """Load settings from profile."""
        if profile is None or profile.oxi is None:
            return

        oxi = profile.oxi

        self.enable_oximetry_check.setChecked(oxi.oximetry_enabled)
        self.spo2_drop_duration_spin.setValue(oxi.spo2_drop_duration)
        self.spo2_drop_percentage_spin.setValue(oxi.spo2_drop_percentage)

        # Get additional settings from profile
        desat = profile.get("oxiDesaturationThreshold")
        self.desat_threshold_spin.setValue(float(desat) if desat else 88.0)

        pulse_duration = profile.get("PulseChangeDuration")
        self.pulse_change_duration_spin.setValue(float(pulse_duration) if pulse_duration else 8.0)

        pulse_bpm = profile.get("PulseChangeBPM")
        self.pulse_change_bpm_spin.setValue(float(pulse_bpm) if pulse_bpm else 5.0)

        pulse_above = profile.get("flagPulseAbove")
        self.pulse_above_spin.setValue(float(pulse_above) if pulse_above else 99.0)

        pulse_below = profile.get("flagPulseBelow")
        self.pulse_below_spin.setValue(float(pulse_below) if pulse_below else 40.0)

    def save_settings(self, profile: 'Profile') -> None:
        """Save settings to profile."""
        if profile is None or profile.oxi is None:
            return

        oxi = profile.oxi

        oxi.oximetry_enabled = self.enable_oximetry_check.isChecked()
        oxi.spo2_drop_duration = self.spo2_drop_duration_spin.value()
        oxi.spo2_drop_percentage = self.spo2_drop_percentage_spin.value()

        profile.set("oxiDesaturationThreshold", self.desat_threshold_spin.value())
        profile.set("PulseChangeDuration", self.pulse_change_duration_spin.value())
        profile.set("PulseChangeBPM", self.pulse_change_bpm_spin.value())
        profile.set("flagPulseAbove", self.pulse_above_spin.value())
        profile.set("flagPulseBelow", self.pulse_below_spin.value())


class PreferencesDialog(QDialog):
    """Dialog for editing application and profile preferences.

    Provides tabs for:
    - General settings (units, display options)
    - CPAP settings (compliance, AHI, leaks)
    - Import settings (session handling, backup)
    - Oximetry settings (SpO2, pulse rate)
    """

    def __init__(
        self,
        profile: Optional['Profile'] = None,
        parent: Optional[QWidget] = None
    ) -> None:
        """Initialize the PreferencesDialog.

        Args:
            profile: Optional profile to edit settings for.
            parent: Optional parent widget.
        """
        super().__init__(parent)

        self._profile = profile

        self.setWindowTitle("Preferences")
        self.setMinimumSize(500, 500)
        self.resize(550, 600)

        # Remove help button from title bar
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)

        self._setup_ui()
        self._load_settings()

        logger.debug("PreferencesDialog initialized")

    def _setup_ui(self) -> None:
        """Set up the dialog user interface."""
        layout = QVBoxLayout(self)

        # Tab widget
        self.tab_widget = QTabWidget()

        # Create tabs
        self.general_tab = GeneralSettingsTab()
        self.tab_widget.addTab(self.general_tab, "General")

        self.cpap_tab = CPAPSettingsTab()
        self.tab_widget.addTab(self.cpap_tab, "CPAP")

        self.import_tab = ImportSettingsTab()
        self.tab_widget.addTab(self.import_tab, "Import")

        self.oxi_tab = OximetrySettingsTab()
        self.tab_widget.addTab(self.oxi_tab, "Oximetry")

        layout.addWidget(self.tab_widget)

        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel |
            QDialogButtonBox.StandardButton.Apply
        )
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)

        apply_button = button_box.button(QDialogButtonBox.StandardButton.Apply)
        if apply_button:
            apply_button.clicked.connect(self._on_apply)

        layout.addWidget(button_box)

    def _load_settings(self) -> None:
        """Load settings from profile into all tabs."""
        if self._profile is None:
            return

        self.general_tab.load_settings(self._profile)
        self.cpap_tab.load_settings(self._profile)
        self.import_tab.load_settings(self._profile)
        self.oxi_tab.load_settings(self._profile)

    def _save_settings(self) -> None:
        """Save settings from all tabs to profile."""
        if self._profile is None:
            return

        self.general_tab.save_settings(self._profile)
        self.cpap_tab.save_settings(self._profile)
        self.import_tab.save_settings(self._profile)
        self.oxi_tab.save_settings(self._profile)

        # Save profile to disk
        self._profile.save()

        logger.info("Preferences saved")

    def _on_accept(self) -> None:
        """Handle OK button click."""
        self._save_settings()
        self.accept()

    def _on_apply(self) -> None:
        """Handle Apply button click."""
        self._save_settings()

    def set_profile(self, profile: Optional['Profile']) -> None:
        """Set the profile to edit.

        Args:
            profile: The profile, or None.
        """
        self._profile = profile
        self._load_settings()
