"""
OSCAR GUI Package

This package contains the graphical user interface components for OSCAR.
Ported from C++ Qt to Python/PyQt6.

Copyright (c) 2019-2025 The OSCAR Team
This file is subject to the terms and conditions of the GNU General Public
License. See the file COPYING in the main directory of the source code
for more details.
"""

from .main_window import MainWindow
from .about_dialog import AboutDialog

# Optional imports - may not be implemented yet
try:
    from .profile_selector import ProfileSelector
except ImportError:
    ProfileSelector = None

try:
    from .new_profile_dialog import NewProfileDialog
except ImportError:
    NewProfileDialog = None

try:
    from .daily_view import DailyView
except ImportError:
    DailyView = None

__all__ = ['MainWindow', 'AboutDialog', 'ProfileSelector', 'NewProfileDialog', 'DailyView']
