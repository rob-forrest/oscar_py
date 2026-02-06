"""
OSCAR-Py Main Window

Copyright (c) 2019-2025 The OSCAR Team

This file is subject to the terms and conditions of the GNU General Public
License. See the file COPYING in the main directory of the source code
for more details.

Reference: oscar/mainwindow.h, oscar/mainwindow.cpp
"""

import logging
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QMenuBar,
    QMenu,
    QStatusBar,
    QTabWidget,
    QStackedWidget,
    QVBoxLayout,
    QLabel,
    QMessageBox,
    QFileDialog,
)
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtCore import Qt, QSettings

# Try to import ProfileSelector, use placeholder if not available
try:
    from gui.profile_selector import ProfileSelector
except ImportError:
    ProfileSelector = QWidget  # Placeholder

# Try to import DailyView
try:
    from gui.daily_view import DailyView
except ImportError:
    DailyView = None

# Try to import OverviewView
try:
    from gui.overview_view import OverviewView
except ImportError:
    OverviewView = None

# Try to import StatisticsView
try:
    from gui.statistics_view import StatisticsView
except ImportError:
    StatisticsView = None

# Try to import PreferencesDialog
try:
    from gui.preferences_dialog import PreferencesDialog
except ImportError:
    PreferencesDialog = None

# Try to import sleeplib components
try:
    from sleeplib.profile import Profile
    from sleeplib.schema import MachineType
except ImportError:
    Profile = None
    MachineType = None

from gui.about_dialog import AboutDialog

logger = logging.getLogger(__name__)

# Version info (should be imported from a central location)
VERSION = "0.1.0-dev"
APP_NAME = "OSCAR-Py"


class MainWindow(QMainWindow):
    """Main application window for OSCAR-Py.

    This is the central window that contains:
    - Menu bar with File, Tools, and Help menus
    - Tab widget with Daily, Overview, and Statistics views
    - Profile selector (shown when no profile is open)
    - Status bar

    Attributes:
        data_dir: Path to the OSCAR data directory.
        current_profile: Name of the currently open profile, or None.
    """

    def __init__(
        self,
        data_dir: Path,
        parent: Optional[QWidget] = None
    ) -> None:
        """Initialize the MainWindow.

        Args:
            data_dir: Path to the OSCAR data directory.
            parent: Optional parent widget.
        """
        super().__init__(parent)

        self.data_dir = data_dir
        self.current_profile: Optional[str] = None
        self._profile_obj: Optional['Profile'] = None
        self._requested_profile: Optional[str] = None

        # Load settings
        self.settings = QSettings()

        # Set up the UI
        self._setup_ui()
        self._setup_menus()
        self._setup_status_bar()

        # Restore window geometry
        self._restore_geometry()

        logger.info("MainWindow initialized")

    def _setup_ui(self) -> None:
        """Set up the main user interface."""
        self.setWindowTitle(f"{APP_NAME} {VERSION}")
        self.setMinimumSize(800, 600)

        # Central widget with stacked layout
        # Stack index 0: Profile selector
        # Stack index 1: Main tab widget
        self.central_stack = QStackedWidget()
        self.setCentralWidget(self.central_stack)

        # Profile selector widget
        if ProfileSelector is QWidget:
            # Placeholder profile selector
            self.profile_selector = QWidget()
            layout = QVBoxLayout(self.profile_selector)
            placeholder_label = QLabel(
                "Profile Selector\n\n"
                "(ProfileSelector not yet implemented)\n\n"
                "Use File > Import to import data"
            )
            placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(placeholder_label)
            logger.warning("Using placeholder ProfileSelector")
        else:
            self.profile_selector = ProfileSelector(parent=self)
            self.profile_selector.profile_selected.connect(self._on_profile_selected)

        self.central_stack.addWidget(self.profile_selector)

        # Main content widget with tabs
        self.main_content = QWidget()
        main_layout = QVBoxLayout(self.main_content)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Tab widget
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # Create placeholder tabs
        self._create_placeholder_tabs()

        self.central_stack.addWidget(self.main_content)

        # Start with profile selector visible
        self.central_stack.setCurrentIndex(0)

    def _create_placeholder_tabs(self) -> None:
        """Create tabs for Daily, Overview, and Statistics."""
        # Daily tab
        if DailyView is not None:
            self.daily_view = DailyView()
            self.tab_widget.addTab(self.daily_view, "Daily")
        else:
            self.daily_view = None
            daily_widget = QWidget()
            daily_layout = QVBoxLayout(daily_widget)
            daily_label = QLabel(
                "Daily View\n\n"
                "(Daily view not yet implemented)\n\n"
                "This will show detailed sleep data for each day."
            )
            daily_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            daily_layout.addWidget(daily_label)
            self.tab_widget.addTab(daily_widget, "Daily")

        # Overview tab
        if OverviewView is not None:
            self.overview_view = OverviewView()
            # Connect navigate_to_day signal to switch to Daily view
            self.overview_view.navigate_to_day.connect(self._on_navigate_to_day)
            self.tab_widget.addTab(self.overview_view, "Overview")
        else:
            self.overview_view = None
            overview_widget = QWidget()
            overview_layout = QVBoxLayout(overview_widget)
            overview_label = QLabel(
                "Overview\n\n"
                "(Overview not yet implemented)\n\n"
                "This will show trends and summary graphs over time."
            )
            overview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            overview_layout.addWidget(overview_label)
            self.tab_widget.addTab(overview_widget, "Overview")

        # Statistics tab
        if StatisticsView is not None:
            self.statistics_view = StatisticsView()
            self.tab_widget.addTab(self.statistics_view, "Statistics")
        else:
            self.statistics_view = None
            statistics_widget = QWidget()
            statistics_layout = QVBoxLayout(statistics_widget)
            statistics_label = QLabel(
                "Statistics\n\n"
                "(Statistics not yet implemented)\n\n"
                "This will show statistical analysis of your sleep data."
            )
            statistics_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            statistics_layout.addWidget(statistics_label)
            self.tab_widget.addTab(statistics_widget, "Statistics")

    def _setup_menus(self) -> None:
        """Set up the menu bar and menus."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        # Import action
        self.import_action = QAction("&Import Data...", self)
        self.import_action.setShortcut(QKeySequence("Ctrl+I"))
        self.import_action.setStatusTip("Import CPAP data from device or folder")
        self.import_action.triggered.connect(self.import_data)
        file_menu.addAction(self.import_action)

        # Export action
        self.export_action = QAction("&Export Data...", self)
        self.export_action.setShortcut(QKeySequence("Ctrl+E"))
        self.export_action.setStatusTip("Export data to file")
        self.export_action.triggered.connect(self._on_export)
        self.export_action.setEnabled(False)  # Disabled until profile is open
        file_menu.addAction(self.export_action)

        file_menu.addSeparator()

        # Exit action
        self.exit_action = QAction("E&xit", self)
        self.exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        self.exit_action.setStatusTip("Exit the application")
        self.exit_action.triggered.connect(self.close)
        file_menu.addAction(self.exit_action)

        # Tools menu
        tools_menu = menubar.addMenu("&Tools")

        # Preferences action
        self.preferences_action = QAction("&Preferences...", self)
        self.preferences_action.setShortcut(QKeySequence.StandardKey.Preferences)
        self.preferences_action.setStatusTip("Open preferences dialog")
        self.preferences_action.triggered.connect(self._on_preferences)
        tools_menu.addAction(self.preferences_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        # About action
        self.about_action = QAction("&About OSCAR-Py...", self)
        self.about_action.setStatusTip("Show information about OSCAR-Py")
        self.about_action.triggered.connect(self._on_about)
        help_menu.addAction(self.about_action)

    def _setup_status_bar(self) -> None:
        """Set up the status bar."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

    def _restore_geometry(self) -> None:
        """Restore window geometry from settings."""
        geometry = self.settings.value("MainWindow/geometry")
        if geometry:
            self.restoreGeometry(geometry)

    def _save_geometry(self) -> None:
        """Save window geometry to settings."""
        self.settings.setValue("MainWindow/geometry", self.saveGeometry())

    def request_profile(self, profile_name: str) -> None:
        """Request to open a profile by name.

        This is called when --profile is specified on the command line.
        The profile will be opened if it exists.

        Args:
            profile_name: Name of the profile to open.
        """
        self._requested_profile = profile_name
        # Attempt to open the profile
        if not self.open_profile(profile_name):
            logger.warning(f"Profile '{profile_name}' not found or could not be opened")
            self.status_bar.showMessage(f"Profile '{profile_name}' not found")

    def open_profile(self, profile_name: str) -> bool:
        """Open a profile and switch to the main tab view.

        Args:
            profile_name: Name of the profile to open.

        Returns:
            True if the profile was opened successfully, False otherwise.
        """
        logger.info(f"Opening profile: {profile_name}")

        # Check if profile exists
        profile_path = self.data_dir / "Profiles" / profile_name
        if not profile_path.exists():
            logger.error(f"Profile path does not exist: {profile_path}")
            QMessageBox.warning(
                self,
                "Profile Not Found",
                f"Profile '{profile_name}' was not found.\n\n"
                f"Expected location: {profile_path}"
            )
            return False

        # Close current profile if one is open
        if self.current_profile:
            self.close_profile()

        # Set current profile
        self.current_profile = profile_name

        # Load the Profile object if sleeplib is available
        self._profile_obj = None
        if Profile is not None:
            try:
                self._profile_obj = Profile(str(profile_path))
                self._profile_obj.open_machines()
                # Load session summaries for all machines that support it
                for machine in self._profile_obj.m_machlist:
                    if hasattr(machine, 'load_sessions'):
                        machine.load_sessions()
                logger.info(f"Loaded Profile object with {len(self._profile_obj.daylist)} days")
            except Exception as e:
                logger.error(f"Error loading Profile object: {e}")
                self._profile_obj = None

        # Update window title
        self.setWindowTitle(f"{APP_NAME} {VERSION} - Profile: {profile_name}")

        # Switch to main content view
        self.central_stack.setCurrentIndex(1)

        # Enable export action
        self.export_action.setEnabled(True)

        # Update views with profile
        self._update_views_with_profile()

        # Update status bar
        self.status_bar.showMessage(f"Profile '{profile_name}' opened")

        logger.info(f"Profile '{profile_name}' opened successfully")
        return True

    def close_profile(self) -> None:
        """Close the current profile and return to the profile selector."""
        if not self.current_profile:
            return

        logger.info(f"Closing profile: {self.current_profile}")

        # Clear current profile
        old_profile = self.current_profile
        self.current_profile = None
        self._profile_obj = None

        # Clear views
        if self.daily_view is not None:
            self.daily_view.set_profile(None)
        if self.overview_view is not None:
            self.overview_view.set_profile(None)
        if self.statistics_view is not None:
            self.statistics_view.set_profile(None)

        # Update window title
        self.setWindowTitle(f"{APP_NAME} {VERSION}")

        # Switch back to profile selector
        self.central_stack.setCurrentIndex(0)

        # Disable export action
        self.export_action.setEnabled(False)

        # Update status bar
        self.status_bar.showMessage(f"Profile '{old_profile}' closed")

        logger.info(f"Profile '{old_profile}' closed")

    def import_data(self) -> None:
        """Open dialog to import CPAP data.

        This is a placeholder implementation. The actual import functionality
        will be implemented in the data loader modules.
        """
        logger.info("Import data requested")

        # Show file dialog to select import source
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select CPAP Data Folder",
            str(Path.home()),
            QFileDialog.Option.ShowDirsOnly
        )

        if folder:
            logger.info(f"Selected folder for import: {folder}")
            self.status_bar.showMessage(f"Import from: {folder}")

            # Placeholder: actual import logic will be implemented later
            QMessageBox.information(
                self,
                "Import Data",
                f"Import functionality is not yet implemented.\n\n"
                f"Selected folder: {folder}\n\n"
                f"Data loaders will be added in future updates."
            )
        else:
            logger.debug("Import cancelled by user")

    def _on_profile_selected(self, profile_name: str) -> None:
        """Handle profile selection from ProfileSelector.

        Args:
            profile_name: Name of the selected profile.
        """
        self.open_profile(profile_name)

    def _on_export(self) -> None:
        """Handle export action."""
        logger.info("Export requested")
        QMessageBox.information(
            self,
            "Export Data",
            "Export functionality is not yet implemented."
        )

    def _on_preferences(self) -> None:
        """Handle preferences action."""
        logger.info("Preferences requested")

        if PreferencesDialog is None:
            QMessageBox.information(
                self,
                "Preferences",
                "Preferences dialog is not yet implemented."
            )
            return

        dialog = PreferencesDialog(profile=self._profile_obj, parent=self)
        if dialog.exec():
            # Refresh views after settings change
            self._update_views_with_profile()
            self.status_bar.showMessage("Preferences saved")

    def _on_about(self) -> None:
        """Show the About dialog."""
        logger.debug("Showing About dialog")
        about_dialog = AboutDialog(self)
        about_dialog.exec()

    def _update_views_with_profile(self) -> None:
        """Update all views with the current profile."""
        if self._profile_obj is None:
            return

        # Update DailyView
        if self.daily_view is not None:
            self.daily_view.set_profile(self._profile_obj)

        # Update OverviewView
        if self.overview_view is not None:
            self.overview_view.set_profile(self._profile_obj)

        # Update StatisticsView
        if self.statistics_view is not None:
            self.statistics_view.set_profile(self._profile_obj)

    def _on_navigate_to_day(self, day_date) -> None:
        """Handle navigation to a specific day from Overview.

        Args:
            day_date: The date to navigate to.
        """
        logger.debug(f"Navigating to day: {day_date}")

        # Switch to Daily tab (index 0)
        self.tab_widget.setCurrentIndex(0)

        # Select the date in DailyView
        if self.daily_view is not None:
            self.daily_view.select_date(day_date)

    def closeEvent(self, event) -> None:
        """Handle window close event.

        Saves window geometry and closes any open profile.

        Args:
            event: The close event.
        """
        logger.info("MainWindow closing")

        # Save window geometry
        self._save_geometry()

        # Close current profile
        if self.current_profile:
            self.close_profile()

        # Accept the close event
        event.accept()
