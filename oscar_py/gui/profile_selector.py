"""
Profile Selector Widget

A widget for selecting, creating, editing, and deleting user profiles.
Ported from oscar/profileselector.h/cpp/ui

Copyright (c) 2019-2025 The OSCAR Team
Copyright (c) 2018 Mark Watkins

This file is subject to the terms and conditions of the GNU General Public
License. See the file COPYING in the main directory of the source code
for more details.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableView, QLineEdit,
    QPushButton, QLabel, QGroupBox, QFrame, QToolButton,
    QHeaderView, QMessageBox, QDialog, QSizePolicy, QSpacerItem
)
from PyQt6.QtCore import (
    Qt, pyqtSignal, QSortFilterProxyModel, QModelIndex,
    QRegularExpression
)
from PyQt6.QtGui import (
    QStandardItemModel, QStandardItem, QFont, QColor, QBrush,
    QPalette, QFontMetrics
)

# Try to import sleeplib modules, fall back to mock data for testing
try:
    from sleeplib.profile import Profile, Profiles
except ImportError:
    # Mock data for testing UI independently
    class MockProfile:
        """Mock profile for testing."""
        def __init__(self, name, brand='', model='', last_import='', user_name=''):
            self.name = name
            self.brand = brand
            self.model = model
            self.last_import = last_import
            self.user_name = user_name
            self.first_name = ''
            self.last_name = ''
            self.phone = ''
            self.email = ''
            self.address = ''

    # Mock profiles dictionary
    Profiles = {
        'Test Profile': MockProfile(
            'Test Profile',
            brand='ResMed',
            model='AirSense 10',
            last_import='2025-01-15',
            user_name='Test User'
        ),
        'Demo User': MockProfile(
            'Demo User',
            brand='Philips',
            model='DreamStation',
            last_import='2025-01-10',
            user_name='Demo'
        ),
        'Sample Data': MockProfile(
            'Sample Data',
            brand='ResMed',
            model='AirCurve 10',
            last_import='2025-01-20',
            user_name='Sample'
        ),
    }
    Profile = MockProfile


class ProfileSortFilterProxyModel(QSortFilterProxyModel):
    """
    Custom sort/filter proxy model that filters across multiple columns.
    Searches in Profile Name, Brand, Model, and User Name columns.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        """Filter rows by checking multiple columns for the filter pattern."""
        model = self.sourceModel()
        if model is None:
            return True

        # Get the filter regex
        filter_exp = self.filterRegularExpression()

        # Check columns: 0 (Profile), 1 (Brand), 2 (Model), 5 (User Name)
        columns_to_check = [0, 1, 2, 5]

        for col in columns_to_check:
            index = model.index(source_row, col, source_parent)
            data = model.data(index)
            if data and filter_exp.match(str(data)).hasMatch():
                return True

        return False


class ProfileSelector(QWidget):
    """
    Widget for selecting and managing user profiles.

    Displays a table of available profiles with columns:
    - Profile Name
    - Ventilator Brand
    - Ventilator Model
    - Other Data
    - Last Imported
    - User Name

    Provides buttons for:
    - Open: Open selected profile
    - Edit: Edit selected profile
    - New: Create a new profile
    - Delete: Delete selected profile

    Signals:
        profile_selected(str): Emitted when a profile is selected/opened
        new_profile_requested(): Emitted when new profile creation is requested
    """

    # Signals
    profile_selected = pyqtSignal(str)
    new_profile_requested = pyqtSignal()

    # Column indices
    COL_PROFILE = 0
    COL_BRAND = 1
    COL_MODEL = 2
    COL_OTHER = 3
    COL_LAST_IMPORT = 4
    COL_USER_NAME = 5
    NUM_COLUMNS = 6

    # Highlight color for open profile
    OPEN_PROFILE_HIGHLIGHT = QColor(Qt.GlobalColor.darkGreen)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.model = None
        self.proxy = None
        self.current_profile = None  # Currently open profile name

        self._setup_ui()
        self._connect_signals()

        # Initial button states
        self.button_open.setEnabled(False)
        self.button_edit.setEnabled(False)

    def _setup_ui(self):
        """Set up the user interface."""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)

        # Horizontal layout for table and side panel
        content_layout = QHBoxLayout()

        # Left side: Filter and Table
        left_layout = QVBoxLayout()

        # Filter row
        filter_layout = QHBoxLayout()

        filter_label = QLabel("Filter:")
        filter_layout.addWidget(filter_label)

        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Search profiles...")
        filter_layout.addWidget(self.filter_edit)

        self.reset_filter_button = QToolButton()
        self.reset_filter_button.setText("...")
        self.reset_filter_button.setToolTip("Reset filter to see all profiles")
        self.reset_filter_button.setStyleSheet("""
            QToolButton {
                background: transparent;
                border-radius: 8px;
                border: 2px solid transparent;
            }
            QToolButton:hover {
                border: 2px solid #456789;
            }
            QToolButton:pressed {
                border: 2px solid #456789;
                background-color: #89abcd;
            }
        """)
        filter_layout.addWidget(self.reset_filter_button)

        left_layout.addLayout(filter_layout)

        # Profile table view
        self.profile_view = QTableView()
        self.profile_view.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.profile_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.profile_view.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.profile_view.setAlternatingRowColors(True)
        self.profile_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.profile_view.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.profile_view.setSortingEnabled(True)
        self.profile_view.verticalHeader().setVisible(False)
        self.profile_view.horizontalHeader().setCascadingSectionResizes(True)

        # Set palette for selection highlighting
        palette = self.profile_view.palette()
        palette.setColor(QPalette.ColorRole.Highlight, QColor("#3a7fc2"))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("white"))
        self.profile_view.setPalette(palette)

        self.profile_view.setStyleSheet(
            "QHeaderView::section { background-color: lightgrey }"
        )

        left_layout.addWidget(self.profile_view)
        content_layout.addLayout(left_layout, stretch=1)

        # Right side: Info panel and buttons
        right_frame = QFrame()
        right_frame.setMinimumWidth(250)
        right_frame.setFrameShape(QFrame.Shape.StyledPanel)
        right_frame.setFrameShadow(QFrame.Shadow.Raised)

        right_layout = QVBoxLayout(right_frame)

        # Logo area (centered)
        logo_layout = QHBoxLayout()
        logo_layout.addSpacerItem(
            QSpacerItem(40, 20, QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        )

        self.logo_label = QLabel()
        self.logo_label.setMaximumSize(128, 128)
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo_label.setText("OSCAR")  # Placeholder, would use pixmap
        logo_layout.addWidget(self.logo_label)

        logo_layout.addSpacerItem(
            QSpacerItem(40, 20, QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        )
        right_layout.addLayout(logo_layout)

        # OSCAR title
        oscar_label = QLabel("OSCAR")
        oscar_font = QFont()
        oscar_font.setPointSize(13)
        oscar_font.setBold(True)
        oscar_label.setFont(oscar_font)
        oscar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_layout.addWidget(oscar_label)

        # Version label
        self.version_label = QLabel("")
        self.version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_layout.addWidget(self.version_label)

        # Separator line
        line1 = QFrame()
        line1.setFrameShape(QFrame.Shape.HLine)
        line1.setFrameShadow(QFrame.Shadow.Sunken)
        right_layout.addWidget(line1)

        # Open Profile button
        self.button_open = QPushButton("Open Profile")
        right_layout.addWidget(self.button_open)

        # Edit Profile button
        self.button_edit = QPushButton("Edit Profile")
        right_layout.addWidget(self.button_edit)

        # Separator line
        line2 = QFrame()
        line2.setFrameShape(QFrame.Shape.HLine)
        line2.setFrameShadow(QFrame.Shadow.Sunken)
        right_layout.addWidget(line2)

        # New Profile button
        self.button_new = QPushButton("New Profile")
        right_layout.addWidget(self.button_new)

        # Profile info group box
        self.profile_info_group = QGroupBox("Profile: None")
        info_font = QFont()
        info_font.setBold(True)
        self.profile_info_group.setFont(info_font)

        info_layout = QVBoxLayout(self.profile_info_group)

        self.profile_info_label = QLabel("Please select or create a profile...")
        label_font = QFont()
        label_font.setBold(False)
        self.profile_info_label.setFont(label_font)
        self.profile_info_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        self.profile_info_label.setWordWrap(True)
        self.profile_info_label.setOpenExternalLinks(True)
        info_layout.addWidget(self.profile_info_label)

        self.disk_space_label = QLabel("")
        self.disk_space_label.setFont(label_font)
        self.disk_space_label.setVisible(False)
        info_layout.addWidget(self.disk_space_label)

        right_layout.addWidget(self.profile_info_group)

        # Vertical spacer
        right_layout.addSpacerItem(
            QSpacerItem(20, 339, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        )

        # Delete Profile button (at bottom)
        self.button_delete = QPushButton("Destroy Profile")
        right_layout.addWidget(self.button_delete)

        content_layout.addWidget(right_frame)
        main_layout.addLayout(content_layout)

    def _connect_signals(self):
        """Connect widget signals to slots."""
        self.filter_edit.textChanged.connect(self._on_filter_text_changed)
        self.reset_filter_button.clicked.connect(self._on_reset_filter_clicked)
        self.profile_view.doubleClicked.connect(self._on_profile_double_clicked)
        self.button_open.clicked.connect(self.on_button_open_clicked)
        self.button_edit.clicked.connect(self.on_button_edit_clicked)
        self.button_new.clicked.connect(self.on_button_new_clicked)
        self.button_delete.clicked.connect(self.on_button_delete_clicked)

    def update_profile_list(self):
        """Refresh the profile table from the Profiles dictionary."""
        # Disconnect selection model temporarily
        old_selection_model = self.profile_view.selectionModel()
        if old_selection_model:
            try:
                old_selection_model.currentRowChanged.disconnect(
                    self._on_selection_changed
                )
            except TypeError:
                pass  # Not connected

        # Create new model
        if self.proxy:
            del self.proxy
        if self.model:
            del self.model

        self.model = QStandardItemModel(0, self.NUM_COLUMNS, self)

        # Set headers
        headers = [
            self.tr("Profile"),
            self.tr("Ventilator Brand"),
            self.tr("Ventilator Model"),
            self.tr("Other Data"),
            self.tr("Last Imported"),
            self.tr("Name")
        ]
        for i, header in enumerate(headers):
            self.model.setHeaderData(i, Qt.Orientation.Horizontal, header)

        # Populate with profiles
        row = 0
        for name, profile in Profiles.items():
            self.model.insertRow(row)

            # Get user name
            user_name = ""
            if hasattr(profile, 'last_name') and hasattr(profile, 'first_name'):
                if profile.last_name:
                    user_name = f"{profile.last_name}, {profile.first_name}"
            elif hasattr(profile, 'user_name'):
                user_name = profile.user_name

            # Set data
            self.model.setData(
                self.model.index(row, self.COL_PROFILE), name
            )
            self.model.setData(
                self.model.index(row, self.COL_PROFILE), name, Qt.ItemDataRole.UserRole + 2
            )
            self.model.setData(
                self.model.index(row, self.COL_USER_NAME), user_name
            )

            # Machine info
            if hasattr(profile, 'brand'):
                self.model.setData(
                    self.model.index(row, self.COL_BRAND), profile.brand
                )
            if hasattr(profile, 'model'):
                self.model.setData(
                    self.model.index(row, self.COL_MODEL), profile.model
                )
            if hasattr(profile, 'last_import'):
                self.model.setData(
                    self.model.index(row, self.COL_LAST_IMPORT), profile.last_import
                )

            # Set text color (highlight if current profile)
            text_color = QBrush(QColor(Qt.GlobalColor.black))
            font = QFont()

            if self.current_profile and name == self.current_profile:
                text_color = QBrush(self.OPEN_PROFILE_HIGHLIGHT)
                font.setBold(True)

            for col in range(self.NUM_COLUMNS):
                self.model.setData(
                    self.model.index(row, col), text_color, Qt.ItemDataRole.ForegroundRole
                )

            row += 1

        # Show message if no profiles
        if row == 0:
            self.profile_info_label.setText(self.tr("You must create a profile"))

        # Set up proxy model
        self.proxy = ProfileSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setSortCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        self.profile_view.setModel(self.proxy)

        # Configure header
        header = self.profile_view.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        # Connect selection model
        selection_model = self.profile_view.selectionModel()
        selection_model.currentRowChanged.connect(self._on_selection_changed)

    def select_profile(self, name: str) -> bool:
        """
        Open/select the profile with the given name.

        Args:
            name: The profile name to select

        Returns:
            True if profile was found and selected, False otherwise
        """
        if name not in Profiles:
            return False

        # Update current profile
        self.current_profile = name

        # Update highlight
        self.update_profile_highlight(name)

        # Emit signal
        self.profile_selected.emit(name)

        return True

    def update_profile_highlight(self, name: str):
        """Update the visual highlighting for the currently open profile."""
        if not self.model:
            return

        # Reset all rows to default style
        default_color = QBrush(QColor(Qt.GlobalColor.black))
        default_font = QFont()
        default_font.setBold(False)

        for row in range(self.model.rowCount()):
            for col in range(self.model.columnCount()):
                idx = self.model.index(row, col)
                self.model.setData(idx, default_color, Qt.ItemDataRole.ForegroundRole)
                self.model.setData(idx, default_font, Qt.ItemDataRole.FontRole)

        # Highlight the specified profile
        highlight_color = QBrush(self.OPEN_PROFILE_HIGHLIGHT)
        highlight_font = QFont()
        highlight_font.setBold(True)

        if not self.proxy:
            return

        for row in range(self.proxy.rowCount()):
            idx = self.proxy.index(row, 0)
            if self.proxy.data(idx) == name:
                for col in range(self.proxy.columnCount()):
                    idx = self.proxy.index(row, col)
                    self.proxy.setData(idx, highlight_color, Qt.ItemDataRole.ForegroundRole)
                    self.proxy.setData(idx, highlight_font, Qt.ItemDataRole.FontRole)
                break

    def _on_filter_text_changed(self, text: str):
        """Handle filter text changes."""
        # Convert to wildcard pattern
        pattern = f".*{QRegularExpression.escape(text)}.*"
        regex = QRegularExpression(pattern, QRegularExpression.PatternOption.CaseInsensitiveOption)
        if self.proxy:
            self.proxy.setFilterRegularExpression(regex)

    def _on_reset_filter_clicked(self):
        """Clear the filter text."""
        self.filter_edit.clear()

    def _on_profile_double_clicked(self, index: QModelIndex):
        """Handle double-click on a profile row."""
        if not self.proxy:
            return

        # Get profile name from first column
        idx = self.proxy.index(index.row(), 0)
        profile_name = self.proxy.data(idx, Qt.ItemDataRole.UserRole + 2)

        if profile_name:
            self.select_profile(profile_name)

    def _on_selection_changed(self, current: QModelIndex, previous: QModelIndex):
        """Handle selection changes in the table."""
        enabled = False

        if current.isValid() and self.proxy:
            idx = self.proxy.index(current.row(), 0)
            name = self.proxy.data(idx, Qt.ItemDataRole.UserRole + 2)

            if name and name in Profiles:
                enabled = True
                profile = Profiles[name]

                # Build info HTML
                html = ""

                if hasattr(profile, 'last_name') and hasattr(profile, 'first_name'):
                    if profile.last_name and profile.first_name:
                        html += f"{self.tr('Name:')} {profile.last_name}, {profile.first_name}<br/>"

                if hasattr(profile, 'phone') and profile.phone:
                    html += f"{self.tr('Phone:')} {profile.phone}<br/>"

                if hasattr(profile, 'email') and profile.email:
                    html += f"{self.tr('Email:')} <a href='mailto:{profile.email}'>{profile.email}</a><br/>"

                if hasattr(profile, 'address') and profile.address:
                    address_html = profile.address.strip().replace('\n', '<br/>')
                    html += f"<br/>{self.tr('Address:')}<br/>{address_html}<br/>"

                if not html:
                    html = self.tr("No profile information given") + "<br/>"

                self.profile_info_group.setTitle(self.tr(f"Profile: {name}"))
                self.profile_info_label.setText(html)
                self.disk_space_label.setVisible(True)

        self.button_open.setEnabled(enabled)
        self.button_edit.setEnabled(enabled)

    def _get_selected_profile_name(self) -> str:
        """Get the name of the currently selected profile."""
        if not self.profile_view.currentIndex().isValid() or not self.proxy:
            return ""

        idx = self.proxy.index(self.profile_view.currentIndex().row(), 0)
        return self.proxy.data(idx, Qt.ItemDataRole.UserRole + 2) or ""

    def on_button_open_clicked(self):
        """Handle Open Profile button click."""
        name = self._get_selected_profile_name()
        if name:
            self.select_profile(name)

    def on_button_new_clicked(self):
        """Handle New Profile button click."""
        # Import here to avoid circular imports
        from .new_profile_dialog import NewProfileDialog

        dialog = NewProfileDialog(self)
        dialog.setModal(True)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Get the new profile name and refresh list
            new_name = dialog.get_profile_name()
            if new_name:
                self.update_profile_list()
                self.new_profile_requested.emit()
                # Optionally open the new profile
                self.select_profile(new_name)

    def on_button_edit_clicked(self):
        """Handle Edit Profile button click."""
        name = self._get_selected_profile_name()
        if not name:
            QMessageBox.information(
                self,
                self.tr("Information"),
                self.tr("Select a profile first")
            )
            return

        # Import here to avoid circular imports
        from .new_profile_dialog import NewProfileDialog

        dialog = NewProfileDialog(self, profile_name=name)
        dialog.setModal(True)
        dialog.edit_profile(name)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Refresh the list to show updated info
            self.update_profile_list()
            if self.current_profile:
                self.update_profile_highlight(self.current_profile)

    def on_button_delete_clicked(self):
        """Handle Delete Profile button click."""
        name = self._get_selected_profile_name()
        if not name:
            return

        # Confirmation dialog
        result = QMessageBox.warning(
            self,
            self.tr("Warning"),
            self.tr(f"You are about to destroy profile '<b>{name}</b>'.<br/><br/>"
                    "Think carefully, as this will irretrievably delete the profile "
                    "along with all backup data.<br/><br/>"
                    "Are you sure you want to continue?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if result != QMessageBox.StandardButton.Yes:
            return

        # Secondary confirmation - require typing DELETE
        from PyQt6.QtWidgets import QInputDialog

        text, ok = QInputDialog.getText(
            self,
            self.tr("Confirm Deletion"),
            self.tr("Enter the word DELETE (exactly as shown) to confirm:")
        )

        if not ok or text != "DELETE":
            QMessageBox.information(
                self,
                self.tr("Cancelled"),
                self.tr("You need to enter DELETE in capital letters.")
            )
            return

        # Delete the profile
        if name in Profiles:
            del Profiles[name]

            # If this was the current profile, clear it
            if self.current_profile == name:
                self.current_profile = None

            QMessageBox.information(
                self,
                self.tr("Information"),
                self.tr(f"Profile '{name}' was successfully deleted")
            )

            self.update_profile_list()


# Test code
if __name__ == '__main__':
    import sys
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    selector = ProfileSelector()
    selector.update_profile_list()
    selector.resize(900, 600)
    selector.show()

    sys.exit(app.exec())
