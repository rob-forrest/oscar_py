"""
OSCAR-Py About Dialog

Copyright (c) 2019-2025 The OSCAR Team

This file is subject to the terms and conditions of the GNU General Public
License. See the file COPYING in the main directory of the source code
for more details.

Reference: oscar/aboutdialog.h, oscar/aboutdialog.cpp
"""

import logging
from typing import Optional

from PyQt6.QtWidgets import (
    QDialog,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QTextBrowser,
)
from PyQt6.QtGui import QFont, QDesktopServices
from PyQt6.QtCore import Qt, QUrl

logger = logging.getLogger(__name__)

# Version info (should be imported from a central location)
VERSION = "0.1.0-dev"
APP_NAME = "OSCAR-Py"

# URLs
OSCAR_PROJECT_URL = "https://www.sleepfiles.com/OSCAR/"
OSCAR_GITLAB_URL = "https://gitlab.com/pholy/OSCAR-code"
OSCAR_WIKI_URL = "http://www.apneaboard.com/wiki/index.php?title=OSCAR_Help"


class AboutDialog(QDialog):
    """About dialog showing application information.

    Displays:
    - Application name and version
    - Description of the application
    - Links to the original OSCAR project
    - Credits and license information
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the About dialog.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)

        self.setWindowTitle(f"About {APP_NAME}")
        self.setMinimumSize(500, 400)

        # Remove help button from title bar (Windows)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)

        self._setup_ui()

        logger.debug("AboutDialog initialized")

    def _setup_ui(self) -> None:
        """Set up the dialog user interface."""
        layout = QVBoxLayout(self)

        # Header with app name and version
        header_layout = QVBoxLayout()

        # App name label
        name_label = QLabel(APP_NAME)
        name_font = QFont()
        name_font.setPointSize(24)
        name_font.setBold(True)
        name_label.setFont(name_font)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(name_label)

        # Version label
        version_label = QLabel(f"Version {VERSION}")
        version_font = QFont()
        version_font.setPointSize(12)
        version_label.setFont(version_font)
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(version_label)

        # Subtitle
        subtitle_label = QLabel("Open Source CPAP Analysis Reporter")
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(subtitle_label)

        layout.addLayout(header_layout)

        # Tab widget for About, Credits, License
        tab_widget = QTabWidget()

        # About tab
        about_browser = QTextBrowser()
        about_browser.setOpenExternalLinks(True)
        about_browser.setHtml(self._get_about_html())
        tab_widget.addTab(about_browser, "About")

        # Credits tab
        credits_browser = QTextBrowser()
        credits_browser.setOpenExternalLinks(True)
        credits_browser.setHtml(self._get_credits_html())
        tab_widget.addTab(credits_browser, "Credits")

        # License tab
        license_browser = QTextBrowser()
        license_browser.setOpenExternalLinks(True)
        license_browser.setHtml(self._get_license_html())
        tab_widget.addTab(license_browser, "License")

        layout.addWidget(tab_widget)

        # Button layout
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        close_button.setDefault(True)
        button_layout.addWidget(close_button)

        layout.addLayout(button_layout)

    def _get_about_html(self) -> str:
        """Get HTML content for the About tab.

        Returns:
            HTML string with about information.
        """
        return f"""
        <html>
        <head>
            <style>
                body {{ font-family: sans-serif; margin: 10px; }}
                h2 {{ color: #333; }}
                p {{ line-height: 1.5; }}
                a {{ color: #0066cc; }}
            </style>
        </head>
        <body>
            <h2>About {APP_NAME}</h2>
            <p>
                {APP_NAME} is a Python port of OSCAR (Open Source CPAP Analysis Reporter),
                an open-source application for reviewing data from CPAP and bilevel devices
                used in the treatment of sleep apnea.
            </p>

            <h3>Original OSCAR Project</h3>
            <p>
                {APP_NAME} is based on the original OSCAR project, which was derived from
                SleepyHead, created by Mark Watkins.
            </p>
            <p>
                <b>OSCAR Website:</b><br/>
                <a href="{OSCAR_PROJECT_URL}">{OSCAR_PROJECT_URL}</a>
            </p>
            <p>
                <b>Source Code:</b><br/>
                <a href="{OSCAR_GITLAB_URL}">{OSCAR_GITLAB_URL}</a>
            </p>
            <p>
                <b>Help Wiki:</b><br/>
                <a href="{OSCAR_WIKI_URL}">{OSCAR_WIKI_URL}</a>
            </p>

            <h3>Python Port</h3>
            <p>
                This Python port uses PyQt6 and aims to provide the same functionality
                as the original C++ version while making the codebase more accessible
                for contributions and easier to extend.
            </p>
        </body>
        </html>
        """

    def _get_credits_html(self) -> str:
        """Get HTML content for the Credits tab.

        Returns:
            HTML string with credits information.
        """
        return """
        <html>
        <head>
            <style>
                body { font-family: sans-serif; margin: 10px; }
                h2 { color: #333; }
                h3 { color: #555; margin-top: 20px; }
                p { line-height: 1.5; }
                ul { line-height: 1.8; }
            </style>
        </head>
        <body>
            <h2>Credits</h2>

            <h3>Original OSCAR Team</h3>
            <p>
                OSCAR is developed and maintained by The OSCAR Team, a group of
                dedicated volunteers who have contributed countless hours to make
                this software available to the sleep apnea community.
            </p>

            <h3>SleepyHead</h3>
            <p>
                OSCAR is derived from SleepyHead, originally created by
                <b>Mark Watkins</b>. His pioneering work made it possible for
                sleep apnea patients to analyze their own therapy data.
            </p>

            <h3>Python Port Contributors</h3>
            <ul>
                <li>Python/PyQt6 port development</li>
            </ul>

            <h3>Third-Party Libraries</h3>
            <ul>
                <li><b>PyQt6</b> - Python bindings for Qt 6</li>
                <li><b>Qt</b> - Cross-platform application framework</li>
            </ul>

            <h3>Community</h3>
            <p>
                Special thanks to the Apnea Board community for their support,
                testing, and feedback that helps improve OSCAR.
            </p>
        </body>
        </html>
        """

    def _get_license_html(self) -> str:
        """Get HTML content for the License tab.

        Returns:
            HTML string with license information.
        """
        return """
        <html>
        <head>
            <style>
                body { font-family: sans-serif; margin: 10px; }
                h2 { color: #333; }
                pre {
                    background-color: #f5f5f5;
                    padding: 10px;
                    border-radius: 5px;
                    white-space: pre-wrap;
                    font-size: 11px;
                }
            </style>
        </head>
        <body>
            <h2>License</h2>

            <p>
                OSCAR-Py is free software released under the GNU General Public
                License version 3 (GPLv3).
            </p>

            <pre>
OSCAR-Py - Open Source CPAP Analysis Reporter (Python Port)

Copyright (c) 2019-2025 The OSCAR Team

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see &lt;https://www.gnu.org/licenses/&gt;.
            </pre>

            <p>
                For the full license text, see:<br/>
                <a href="https://www.gnu.org/licenses/gpl-3.0.html">
                    https://www.gnu.org/licenses/gpl-3.0.html
                </a>
            </p>
        </body>
        </html>
        """
