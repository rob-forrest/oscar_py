"""
New Profile Dialog

A dialog for creating and editing user profiles.
Ported from oscar/newprofile.h/cpp/ui

Copyright (c) 2019-2025 The OSCAR Team
Copyright (c) 2011-2018 Mark Watkins

This file is subject to the terms and conditions of the GNU General Public
License. See the file COPYING in the main directory of the source code
for more details.
"""

from datetime import date
from enum import IntEnum
from typing import Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout,
    QStackedWidget, QWidget, QLabel, QLineEdit, QPushButton,
    QGroupBox, QCheckBox, QComboBox, QDateEdit, QDoubleSpinBox,
    QTextEdit, QPlainTextEdit, QTextBrowser, QSpacerItem,
    QSizePolicy, QFrame, QMessageBox
)
from PyQt6.QtCore import Qt, QDate, QLocale
from PyQt6.QtGui import QFont

# Try to import sleeplib modules, fall back to mock data for testing
try:
    from sleeplib.profile import Profile, Profiles
except ImportError:
    # Mock data for testing UI independently
    class MockProfile:
        """Mock profile for testing."""
        def __init__(self, name='', brand='', model='', last_import='', user_name=''):
            self.name = name
            self.brand = brand
            self.model = model
            self.last_import = last_import
            self.user_name = name
            self.first_name = ''
            self.last_name = ''
            self.dob = date(1990, 1, 1)
            self.gender = 0
            self.height = 170.0
            self.phone = ''
            self.email = ''
            self.address = ''
            self.password = ''
            self.country = ''
            self.timezone = ''
            self.dst = False
            # CPAP info
            self.date_diagnosed = date(2020, 1, 1)
            self.untreated_ahi = 0.0
            self.cpap_mode = 0
            self.min_pressure = 4.0
            self.max_pressure = 20.0
            self.cpap_notes = ''
            # Doctor info
            self.doctor_name = ''
            self.doctor_practice = ''
            self.doctor_patient_id = ''
            self.doctor_address = ''
            self.doctor_phone = ''
            self.doctor_email = ''

    # Reference to the shared Profiles dict from profile_selector
    try:
        from .profile_selector import Profiles
    except ImportError:
        Profiles = {}

    Profile = MockProfile


class Gender(IntEnum):
    """Gender enumeration."""
    UNSPECIFIED = 0
    MALE = 1
    FEMALE = 2


class CPAPMode(IntEnum):
    """CPAP mode enumeration."""
    CPAP = 0
    APAP = 1
    BILEVEL = 2
    ASV = 3


class NewProfileDialog(QDialog):
    """
    Dialog for creating new profiles or editing existing ones.

    This is a multi-page wizard-style dialog with the following pages:
    0. Welcome/Agreement page
    1. User Information (username, password, locale)
    2. Personal Information (name, DOB, gender, contact)
    3. CPAP Treatment Information
    4. Doctor/Clinic Information
    """

    # Page indices
    PAGE_WELCOME = 0
    PAGE_USER = 1
    PAGE_PERSONAL = 2
    PAGE_CPAP = 3
    PAGE_DOCTOR = 4

    def __init__(self, parent=None, profile_name: Optional[str] = None):
        super().__init__(parent, Qt.WindowType.WindowTitleHint | Qt.WindowType.WindowCloseButtonHint)

        self.original_profile_name = profile_name or ""
        self.new_profile_name = ""
        self.edit_mode = False
        self.first_page = 0
        self.password_hashed = False
        self.height_modified = False
        self.tmp_height_cm = 170.0

        self._setup_ui()
        self._connect_signals()
        self._load_locale_data()

        # Initial state
        self.back_button.setEnabled(False)
        self.next_button.setEnabled(False)
        self.stacked_widget.setCurrentIndex(0)

        if profile_name:
            self.user_name_edit.setText(profile_name)

    def _setup_ui(self):
        """Set up the user interface."""
        self.setWindowTitle(self.tr("Edit User Profile"))
        self.resize(667, 450)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)

        # Content area with stacked widget and logo
        content_layout = QHBoxLayout()

        # Left side: Stacked widget with pages
        left_layout = QVBoxLayout()
        left_layout.setSpacing(0)

        self.stacked_widget = QStackedWidget()

        # Create all pages
        self._create_welcome_page()
        self._create_user_page()
        self._create_personal_page()
        self._create_cpap_page()
        self._create_doctor_page()

        left_layout.addWidget(self.stacked_widget)
        content_layout.addLayout(left_layout, stretch=1)

        # Right side: Logo
        right_layout = QVBoxLayout()

        self.logo_label = QLabel()
        self.logo_label.setMaximumSize(128, 128)
        self.logo_label.setScaledContents(True)
        self.logo_label.setText("OSCAR")  # Placeholder
        right_layout.addWidget(self.logo_label)

        app_title = QLabel("OSCAR")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        app_title.setFont(title_font)
        app_title.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        right_layout.addWidget(app_title)

        self.version_label = QLabel("")
        version_font = QFont()
        version_font.setItalic(True)
        self.version_label.setFont(version_font)
        self.version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_layout.addWidget(self.version_label)

        right_layout.addSpacerItem(
            QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        )

        content_layout.addLayout(right_layout)
        main_layout.addLayout(content_layout)

        # Button row
        button_layout = QHBoxLayout()
        button_layout.setSpacing(16)
        button_layout.setContentsMargins(8, 8, 8, 8)

        button_layout.addSpacerItem(
            QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        )

        self.cancel_button = QPushButton(self.tr("Cancel"))
        self.cancel_button.setAutoDefault(False)
        button_layout.addWidget(self.cancel_button)

        self.back_button = QPushButton(self.tr("Back"))
        self.back_button.setAutoDefault(False)
        button_layout.addWidget(self.back_button)

        self.next_button = QPushButton(self.tr("Next"))
        self.next_button.setAutoDefault(False)
        self.next_button.setDefault(False)
        button_layout.addWidget(self.next_button)

        main_layout.addLayout(button_layout)

    def _create_welcome_page(self):
        """Create the welcome/agreement page."""
        page = QWidget()
        layout = QVBoxLayout(page)

        self.text_browser = QTextBrowser()
        self.text_browser.setOpenExternalLinks(False)
        self.text_browser.setOpenLinks(False)
        self.text_browser.setHtml(self._get_intro_html())
        layout.addWidget(self.text_browser)

        agree_layout = QHBoxLayout()
        self.agree_checkbox = QCheckBox(self.tr("I agree to all the conditions above."))
        agree_layout.addWidget(self.agree_checkbox)
        agree_layout.addSpacerItem(
            QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        )
        layout.addLayout(agree_layout)

        self.stacked_widget.addWidget(page)

    def _create_user_page(self):
        """Create the user information page."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(6)
        layout.setContentsMargins(8, 8, 8, 8)

        # User Information group
        user_group = QGroupBox(self.tr("User Information"))
        user_layout = QHBoxLayout(user_group)

        user_layout.addWidget(QLabel(self.tr("User Name")))
        self.user_name_edit = QLineEdit()
        user_layout.addWidget(self.user_name_edit)

        layout.addWidget(user_group)

        # Password group
        self.password_group = QGroupBox(self.tr("Password Protect Profile"))
        self.password_group.setToolTip(
            self.tr("Very weak password protection and not recommended if security is required.")
        )
        self.password_group.setCheckable(True)
        self.password_group.setChecked(False)

        pass_layout = QGridLayout(self.password_group)
        pass_layout.setContentsMargins(8, 8, 8, 8)

        pass_layout.addWidget(QLabel(self.tr("Password")), 0, 0)
        self.password_edit1 = QLineEdit()
        self.password_edit1.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        pass_layout.addWidget(self.password_edit1, 0, 1)

        pass_layout.addWidget(QLabel(self.tr("...twice...")), 1, 0)
        self.password_edit2 = QLineEdit()
        self.password_edit2.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        pass_layout.addWidget(self.password_edit2, 1, 1)

        layout.addWidget(self.password_group)

        # Locale Settings group
        locale_group = QGroupBox(self.tr("Locale Settings"))
        locale_layout = QGridLayout(locale_group)
        locale_layout.setContentsMargins(8, 8, 8, 8)
        locale_layout.setSpacing(6)

        locale_layout.addWidget(QLabel(self.tr("Country")), 0, 0)
        self.country_combo = QComboBox()
        locale_layout.addWidget(self.country_combo, 0, 1, 1, 2)

        locale_layout.addWidget(QLabel(self.tr("TimeZone")), 1, 0)
        self.timezone_combo = QComboBox()
        locale_layout.addWidget(self.timezone_combo, 1, 1, 1, 2)

        self.dst_checkbox = QCheckBox(self.tr("DST Zone"))
        locale_layout.addWidget(self.dst_checkbox, 2, 0)

        locale_layout.addItem(
            QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding),
            3, 0
        )

        layout.addWidget(locale_group)

        self.stacked_widget.addWidget(page)

    def _create_personal_page(self):
        """Create the personal information page."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(6)
        layout.setContentsMargins(8, 8, 8, 8)

        # Personal Information group
        personal_group = QGroupBox(self.tr("Personal Information (for reports)"))
        personal_layout = QFormLayout(personal_group)
        personal_layout.setHorizontalSpacing(6)
        personal_layout.setVerticalSpacing(6)
        personal_layout.setContentsMargins(8, 8, 8, 8)

        self.first_name_edit = QLineEdit()
        personal_layout.addRow(self.tr("First Name"), self.first_name_edit)

        self.last_name_edit = QLineEdit()
        personal_layout.addRow(self.tr("Last Name"), self.last_name_edit)

        # DOB and Gender row
        dob_gender_layout = QHBoxLayout()

        self.dob_edit = QDateEdit()
        self.dob_edit.setCalendarPopup(True)
        dob_gender_layout.addWidget(self.dob_edit)

        dob_gender_layout.addWidget(QLabel(self.tr("Gender")))

        self.gender_combo = QComboBox()
        self.gender_combo.addItems(["", self.tr("Male"), self.tr("Female")])
        dob_gender_layout.addWidget(self.gender_combo)

        personal_layout.addRow(self.tr("D.O.B."), dob_gender_layout)

        # Height row
        height_layout = QHBoxLayout()

        self.height_edit = QDoubleSpinBox()
        self.height_edit.setDecimals(1)
        self.height_edit.setMaximum(350.0)
        self.height_edit.setSuffix(" cm")
        height_layout.addWidget(self.height_edit)

        self.height_edit2 = QDoubleSpinBox()
        self.height_edit2.setDecimals(1)
        self.height_edit2.setMaximum(11.9)
        self.height_edit2.setVisible(False)
        height_layout.addWidget(self.height_edit2)

        self.height_combo = QComboBox()
        self.height_combo.addItems([self.tr("Metric"), self.tr("English")])
        height_layout.addWidget(self.height_combo)

        personal_layout.addRow(self.tr("Height"), height_layout)

        layout.addWidget(personal_group)

        # Contact Information group
        contact_group = QGroupBox(self.tr("Contact Information"))
        contact_layout = QFormLayout(contact_group)
        contact_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        contact_layout.setHorizontalSpacing(6)
        contact_layout.setVerticalSpacing(6)
        contact_layout.setContentsMargins(8, 8, 8, 8)

        self.address_edit = QTextEdit()
        self.address_edit.setTabChangesFocus(True)
        self.address_edit.setMaximumHeight(60)
        contact_layout.addRow(self.tr("Address"), self.address_edit)

        self.email_edit = QLineEdit()
        contact_layout.addRow(self.tr("Email"), self.email_edit)

        self.phone_edit = QLineEdit()
        contact_layout.addRow(self.tr("Phone"), self.phone_edit)

        layout.addWidget(contact_group)

        self.stacked_widget.addWidget(page)

    def _create_cpap_page(self):
        """Create the CPAP treatment information page."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(6)
        layout.setContentsMargins(8, 8, 8, 8)

        cpap_group = QGroupBox(self.tr("CPAP Treatment Information"))
        cpap_layout = QFormLayout(cpap_group)
        cpap_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        cpap_layout.setHorizontalSpacing(6)
        cpap_layout.setVerticalSpacing(6)
        cpap_layout.setContentsMargins(8, 8, 8, 8)

        self.date_diagnosed_edit = QDateEdit()
        self.date_diagnosed_edit.setCalendarPopup(True)
        cpap_layout.addRow(self.tr("Date Diagnosed"), self.date_diagnosed_edit)

        self.untreated_ahi_edit = QDoubleSpinBox()
        self.untreated_ahi_edit.setMaximum(999.99)
        cpap_layout.addRow(self.tr("Untreated AHI"), self.untreated_ahi_edit)

        self.cpap_mode_combo = QComboBox()
        self.cpap_mode_combo.addItems([
            self.tr("CPAP"),
            self.tr("APAP"),
            self.tr("Bi-Level"),
            self.tr("ASV")
        ])
        cpap_layout.addRow(self.tr("CPAP Mode"), self.cpap_mode_combo)

        # Pressure row
        pressure_layout = QHBoxLayout()
        self.min_pressure_edit = QDoubleSpinBox()
        self.min_pressure_edit.setRange(4.0, 25.0)
        pressure_layout.addWidget(self.min_pressure_edit)

        self.max_pressure_edit = QDoubleSpinBox()
        self.max_pressure_edit.setRange(4.0, 25.0)
        pressure_layout.addWidget(self.max_pressure_edit)

        cpap_layout.addRow(self.tr("RX Pressure"), pressure_layout)

        self.cpap_notes_edit = QPlainTextEdit()
        self.cpap_notes_edit.setTabChangesFocus(True)
        cpap_layout.addRow(self.cpap_notes_edit)

        layout.addWidget(cpap_group)

        self.stacked_widget.addWidget(page)

    def _create_doctor_page(self):
        """Create the doctor/clinic information page."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(6)
        layout.setContentsMargins(8, 8, 8, 8)

        doctor_group = QGroupBox(self.tr("Doctors / Clinic Information"))
        doctor_layout = QFormLayout(doctor_group)
        doctor_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        doctor_layout.setHorizontalSpacing(6)
        doctor_layout.setVerticalSpacing(6)
        doctor_layout.setContentsMargins(8, 8, 8, 8)

        self.doctor_name_edit = QLineEdit()
        doctor_layout.addRow(self.tr("Doctors Name"), self.doctor_name_edit)

        # Separator
        line1 = QFrame()
        line1.setFrameShape(QFrame.Shape.HLine)
        line1.setFrameShadow(QFrame.Shadow.Sunken)
        doctor_layout.addRow(line1)

        self.doctor_practice_edit = QLineEdit()
        doctor_layout.addRow(self.tr("Practice Name"), self.doctor_practice_edit)

        self.doctor_patient_id_edit = QLineEdit()
        doctor_layout.addRow(self.tr("Patient ID"), self.doctor_patient_id_edit)

        # Separator
        line2 = QFrame()
        line2.setFrameShape(QFrame.Shape.HLine)
        line2.setFrameShadow(QFrame.Shadow.Sunken)
        doctor_layout.addRow(line2)

        self.doctor_address_edit = QTextEdit()
        self.doctor_address_edit.setTabChangesFocus(True)
        self.doctor_address_edit.setMaximumHeight(60)
        doctor_layout.addRow(self.tr("Address"), self.doctor_address_edit)

        # Separator
        line3 = QFrame()
        line3.setFrameShape(QFrame.Shape.HLine)
        line3.setFrameShadow(QFrame.Shadow.Sunken)
        doctor_layout.addRow(line3)

        self.doctor_phone_edit = QLineEdit()
        doctor_layout.addRow(self.tr("Phone"), self.doctor_phone_edit)

        self.doctor_email_edit = QLineEdit()
        doctor_layout.addRow(self.tr("Email"), self.doctor_email_edit)

        layout.addWidget(doctor_group)

        # Add spacer
        layout.addSpacerItem(
            QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        )

        self.stacked_widget.addWidget(page)

    def _connect_signals(self):
        """Connect widget signals to slots."""
        self.cancel_button.clicked.connect(self.reject)
        self.back_button.clicked.connect(self._on_back_clicked)
        self.next_button.clicked.connect(self._on_next_clicked)
        self.agree_checkbox.clicked.connect(self._on_agree_clicked)
        self.cpap_mode_combo.activated.connect(self._on_cpap_mode_changed)
        self.height_combo.currentIndexChanged.connect(self._on_height_unit_changed)
        self.height_edit.valueChanged.connect(self._on_height_changed)
        self.height_edit2.valueChanged.connect(self._on_height_changed)
        self.password_edit1.editingFinished.connect(self._on_password_edited)
        self.password_edit2.editingFinished.connect(self._on_password_edited)

    def _load_locale_data(self):
        """Load country and timezone data."""
        # Add placeholder country
        self.country_combo.clear()
        self.country_combo.addItem(self.tr("Select Country"))

        # Sample countries (in production, load from file)
        countries = [
            "Australia", "Canada", "France", "Germany", "Japan",
            "New Zealand", "United Kingdom", "United States"
        ]
        for country in countries:
            self.country_combo.addItem(country)

        # Sample timezones (in production, load from file)
        self.timezone_combo.clear()
        timezones = [
            ("UTC-12:00", "UTC-12:00"),
            ("UTC-08:00", "Pacific Time (US & Canada)"),
            ("UTC-07:00", "Mountain Time (US & Canada)"),
            ("UTC-06:00", "Central Time (US & Canada)"),
            ("UTC-05:00", "Eastern Time (US & Canada)"),
            ("UTC+00:00", "London, Dublin"),
            ("UTC+01:00", "Paris, Berlin"),
            ("UTC+10:00", "Sydney, Melbourne"),
            ("UTC+12:00", "Auckland"),
        ]
        for tz_id, tz_name in timezones:
            self.timezone_combo.addItem(tz_name, tz_id)

        # Set date format from locale
        locale = QLocale.system()
        short_format = locale.dateFormat(QLocale.FormatType.ShortFormat)
        self.dob_edit.setDisplayFormat(short_format)
        self.date_diagnosed_edit.setDisplayFormat(short_format)

    def _get_intro_html(self) -> str:
        """Get the welcome/intro HTML content."""
        return """<html>
<body>
<div align=center><h1>Welcome to the Open Source CPAP Analysis Reporter</h1></div>

<p>This software is being designed to assist you in reviewing the data produced by your CPAP Devices and related equipment.</p>

<p>OSCAR has been released freely under the <a href='qrc:/COPYING'>GNU Public License v3</a>, and comes with no warranty, and without ANY claims to fitness for any purpose.</p>

<div align=center><font color="red"><h2>PLEASE READ CAREFULLY</h2></font></div>

<p>OSCAR is intended merely as a data viewer, and definitely not a substitute for competent medical guidance from your Doctor.</p>

<p>Accuracy of any data displayed is not and can not be guaranteed.</p>

<p>Any reports generated are for PERSONAL USE ONLY, and NOT IN ANY WAY fit for compliance or medical diagnostic purposes.</p>

<p>The authors will not be held liable for <u>anything</u> related to the use or misuse of this software.</p>

<div align=center>
<p><b><font size=+1>Use of this software is entirely at your own risk.</font></b></p>

<p><i>OSCAR is copyright &copy;2011-2018 Mark Watkins and portions &copy;2019-2025 The OSCAR Team</i></p>
</div>
</body>
</html>"""

    def skip_welcome_screen(self):
        """Skip the welcome screen (for edit mode)."""
        self.agree_checkbox.setChecked(True)
        self.first_page = self.PAGE_USER
        self.stacked_widget.setCurrentIndex(self.first_page)
        self.back_button.setEnabled(False)
        self.next_button.setEnabled(True)

    def edit_profile(self, name: str):
        """
        Load an existing profile for editing.

        Args:
            name: The profile name to edit
        """
        self.edit_mode = True
        self.skip_welcome_screen()

        if name not in Profiles:
            return

        profile = Profiles[name]

        # User page
        self.user_name_edit.setText(name)

        # Check for password
        if hasattr(profile, 'password') and profile.password:
            self.password_edit1.setText("******")
            self.password_edit2.setText("******")
            self.password_group.setChecked(True)
            self.password_hashed = True

        # Personal page
        if hasattr(profile, 'first_name'):
            self.first_name_edit.setText(profile.first_name)
        if hasattr(profile, 'last_name'):
            self.last_name_edit.setText(profile.last_name)
        if hasattr(profile, 'dob'):
            self.dob_edit.setDate(QDate(profile.dob.year, profile.dob.month, profile.dob.day))
        if hasattr(profile, 'gender'):
            self.gender_combo.setCurrentIndex(profile.gender)
        if hasattr(profile, 'height'):
            self.height_edit.setValue(profile.height)
            self.tmp_height_cm = profile.height
        if hasattr(profile, 'address'):
            self.address_edit.setText(profile.address)
        if hasattr(profile, 'email'):
            self.email_edit.setText(profile.email)
        if hasattr(profile, 'phone'):
            self.phone_edit.setText(profile.phone)

        # Locale
        if hasattr(profile, 'country'):
            idx = self.country_combo.findText(profile.country)
            if idx >= 0:
                self.country_combo.setCurrentIndex(idx)
        if hasattr(profile, 'timezone'):
            idx = self.timezone_combo.findData(profile.timezone)
            if idx >= 0:
                self.timezone_combo.setCurrentIndex(idx)
        if hasattr(profile, 'dst'):
            self.dst_checkbox.setChecked(profile.dst)

        # CPAP page
        if hasattr(profile, 'date_diagnosed'):
            self.date_diagnosed_edit.setDate(
                QDate(profile.date_diagnosed.year, profile.date_diagnosed.month, profile.date_diagnosed.day)
            )
        if hasattr(profile, 'untreated_ahi'):
            self.untreated_ahi_edit.setValue(profile.untreated_ahi)
        if hasattr(profile, 'cpap_mode'):
            self.cpap_mode_combo.setCurrentIndex(profile.cpap_mode)
            self._on_cpap_mode_changed(profile.cpap_mode)
        if hasattr(profile, 'min_pressure'):
            self.min_pressure_edit.setValue(profile.min_pressure)
        if hasattr(profile, 'max_pressure'):
            self.max_pressure_edit.setValue(profile.max_pressure)
        if hasattr(profile, 'cpap_notes'):
            self.cpap_notes_edit.setPlainText(profile.cpap_notes)

        # Doctor page
        if hasattr(profile, 'doctor_name'):
            self.doctor_name_edit.setText(profile.doctor_name)
        if hasattr(profile, 'doctor_practice'):
            self.doctor_practice_edit.setText(profile.doctor_practice)
        if hasattr(profile, 'doctor_patient_id'):
            self.doctor_patient_id_edit.setText(profile.doctor_patient_id)
        if hasattr(profile, 'doctor_address'):
            self.doctor_address_edit.setText(profile.doctor_address)
        if hasattr(profile, 'doctor_phone'):
            self.doctor_phone_edit.setText(profile.doctor_phone)
        if hasattr(profile, 'doctor_email'):
            self.doctor_email_edit.setText(profile.doctor_email)

        self.height_modified = False

    def get_profile_name(self) -> str:
        """Get the profile name from the dialog."""
        return self.user_name_edit.text().strip()

    def _validate_current_page(self) -> bool:
        """Validate the current page before proceeding."""
        index = self.stacked_widget.currentIndex()

        if index == self.PAGE_WELCOME:
            if not self.agree_checkbox.isChecked():
                return False

        elif index == self.PAGE_USER:
            if not self.user_name_edit.text().strip():
                QMessageBox.information(
                    self,
                    self.tr("Error"),
                    self.tr("Please provide a username for this profile")
                )
                return False

            if self.password_group.isChecked():
                if self.password_edit1.text() != self.password_edit2.text():
                    QMessageBox.information(
                        self,
                        self.tr("Error"),
                        self.tr("Passwords don't match")
                    )
                    return False

                if not self.password_edit1.text():
                    self.password_group.setChecked(False)

        return True

    def _save_profile(self) -> bool:
        """Save the profile data."""
        self.new_profile_name = self.user_name_edit.text().strip()
        profile_name = self.original_profile_name if self.original_profile_name else self.new_profile_name

        result = QMessageBox.question(
            self,
            self.tr("Profile Changes"),
            self.tr("Accept and save this information?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if result != QMessageBox.StandardButton.Yes:
            return False

        # Get or create profile
        if profile_name in Profiles:
            profile = Profiles[profile_name]
        else:
            # Create new mock profile
            profile = MockProfile(profile_name)
            Profiles[profile_name] = profile

        # Save user info
        profile.name = self.new_profile_name
        profile.user_name = self.new_profile_name
        profile.first_name = self.first_name_edit.text()
        profile.last_name = self.last_name_edit.text()

        dob_qdate = self.dob_edit.date()
        profile.dob = date(dob_qdate.year(), dob_qdate.month(), dob_qdate.day())

        profile.gender = self.gender_combo.currentIndex()
        profile.email = self.email_edit.text()
        profile.phone = self.phone_edit.text()
        profile.address = self.address_edit.toPlainText()

        if self.password_group.isChecked() and not self.password_hashed:
            profile.password = self.password_edit1.text()
        elif not self.password_group.isChecked():
            profile.password = ''

        # Locale
        profile.country = self.country_combo.currentText()
        profile.timezone = self.timezone_combo.currentData() or ''
        profile.dst = self.dst_checkbox.isChecked()

        if self.height_modified:
            profile.height = self.tmp_height_cm

        # CPAP info
        diag_qdate = self.date_diagnosed_edit.date()
        profile.date_diagnosed = date(diag_qdate.year(), diag_qdate.month(), diag_qdate.day())
        profile.untreated_ahi = self.untreated_ahi_edit.value()
        profile.cpap_mode = self.cpap_mode_combo.currentIndex()
        profile.min_pressure = self.min_pressure_edit.value()
        profile.max_pressure = self.max_pressure_edit.value()
        profile.cpap_notes = self.cpap_notes_edit.toPlainText()

        # Doctor info
        profile.doctor_name = self.doctor_name_edit.text()
        profile.doctor_practice = self.doctor_practice_edit.text()
        profile.doctor_patient_id = self.doctor_patient_id_edit.text()
        profile.doctor_address = self.doctor_address_edit.toPlainText()
        profile.doctor_phone = self.doctor_phone_edit.text()
        profile.doctor_email = self.doctor_email_edit.text()

        # Handle profile rename
        if self.original_profile_name and self.original_profile_name != self.new_profile_name:
            if self.new_profile_name in Profiles:
                QMessageBox.warning(
                    self,
                    self.tr("Duplicate or Invalid User Name"),
                    self.tr("Please Change User Name")
                )
                return False

            # Move profile to new name
            del Profiles[self.original_profile_name]
            Profiles[self.new_profile_name] = profile

        return True

    def _on_agree_clicked(self, checked: bool):
        """Handle agreement checkbox click."""
        self.next_button.setEnabled(checked)

    def _on_back_clicked(self):
        """Handle Back button click."""
        self.next_button.setText(self.tr("Next"))

        current = self.stacked_widget.currentIndex()
        if current > self.first_page:
            self.stacked_widget.setCurrentIndex(current - 1)

        if self.stacked_widget.currentIndex() == self.first_page:
            self.back_button.setEnabled(False)
        else:
            self.back_button.setEnabled(True)

    def _on_next_clicked(self):
        """Handle Next button click."""
        if not self._validate_current_page():
            return

        current = self.stacked_widget.currentIndex()
        max_pages = self.stacked_widget.count() - 1

        if current < max_pages:
            self.stacked_widget.setCurrentIndex(current + 1)
        else:
            # Finish button clicked - save profile
            if self._save_profile():
                self.accept()

        # Update button text
        if self.stacked_widget.currentIndex() >= max_pages:
            self.next_button.setText(self.tr("Finish"))
        else:
            self.next_button.setText(self.tr("Next"))

        self.back_button.setEnabled(True)

    def _on_cpap_mode_changed(self, index: int):
        """Handle CPAP mode selection change."""
        # Hide max pressure for fixed CPAP mode
        self.max_pressure_edit.setVisible(index != CPAPMode.CPAP)

    def _on_height_unit_changed(self, index: int):
        """Handle height unit selection change."""
        self.height_edit.blockSignals(True)
        self.height_edit2.blockSignals(True)

        if index == 0:
            # Metric (cm)
            self.height_edit.setDecimals(1)
            self.height_edit.setSuffix(" cm")
            self.height_edit.setValue(self.tmp_height_cm)
            self.height_edit2.setVisible(False)
        else:
            # English (feet/inches)
            self.height_edit.setDecimals(0)
            self.height_edit.setSuffix(" ft")
            self.height_edit2.setVisible(True)
            self.height_edit2.setSuffix(" in")

            # Convert cm to feet and inches
            total_inches = self.tmp_height_cm / 2.54
            feet = int(total_inches // 12)
            inches = total_inches % 12

            self.height_edit.setValue(feet)
            self.height_edit2.setValue(inches)

        self.height_edit.blockSignals(False)
        self.height_edit2.blockSignals(False)

    def _on_height_changed(self, value: float):
        """Handle height value change."""
        self.height_modified = True

        if self.height_combo.currentIndex() == 0:
            # Metric
            self.tmp_height_cm = self.height_edit.value()
        else:
            # English - convert to cm
            feet = self.height_edit.value()
            inches = self.height_edit2.value()
            self.tmp_height_cm = (feet * 12 + inches) * 2.54

    def _on_password_edited(self):
        """Handle password field editing."""
        self.password_hashed = False


# Test code
if __name__ == '__main__':
    import sys
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    dialog = NewProfileDialog()
    result = dialog.exec()

    if result == QDialog.DialogCode.Accepted:
        print(f"Profile created/edited: {dialog.get_profile_name()}")
    else:
        print("Cancelled")

    sys.exit(0)
