"""
SleepLib Preferences - Base Preferences Class

This module provides the Preferences class for storing and managing
application and profile settings, ported from the C++ OSCAR codebase.

Copyright (c) 2019-2025 The OSCAR Team
License: GPL v3
"""

from __future__ import annotations
import os
import xml.etree.ElementTree as ET
from xml.dom import minidom
from pathlib import Path
from datetime import datetime, date, time
from typing import Any, Dict, Optional, Iterator, Union
import getpass


# Constants
STR_EXT_XML = ".xml"
STR_APP_NAME = "OSCAR"


def get_user_name() -> str:
    """Get the current username from the operating system."""
    try:
        return getpass.getuser()
    except Exception:
        return os.environ.get("USER", "User")


def get_app_data() -> Path:
    """Get the application data directory path.

    Returns the path to the OSCAR data directory, typically in the user's
    Documents folder.
    """
    # Check for custom path in environment or settings
    custom_path = os.environ.get("OSCAR_DATA_PATH")
    if custom_path:
        return Path(custom_path)

    # Default to Documents/OSCAR-Data
    documents = Path.home() / "Documents"
    return documents / "OSCAR-Data"


def pref_macro(s: str) -> str:
    """Create a preference macro string."""
    return "{" + s + "}"


class Preferences:
    """Holds a group of preference variables with XML persistence.

    This class provides dict-like storage for settings with type-aware
    serialization to XML format compatible with the C++ OSCAR application.

    Attributes:
        p_name: Name of this preferences group
        p_filename: Full path to the XML file
        p_path: Directory containing the preferences file
        p_comment: Optional comment stored in the XML
        p_preferences: Dictionary of preference key-value pairs
    """

    def __init__(self, name: str = "Preferences", filename: str = ""):
        """Initialize a Preferences object.

        Args:
            name: Name of the preferences group
            filename: Optional full path to the XML file
        """
        # Strip .xml extension from name if present
        if name.endswith(STR_EXT_XML):
            self.p_name = name.rsplit(".", 1)[0]
        else:
            self.p_name = name

        self.p_path = str(get_app_data())
        self.p_comment = ""
        self.p_preferences: Dict[str, Any] = {}

        if filename:
            if "/" not in filename and "\\" not in filename:
                self.p_filename = str(get_app_data() / filename)
            else:
                self.p_filename = filename

            if not self.p_filename.endswith(STR_EXT_XML):
                self.p_filename += STR_EXT_XML
        else:
            self.p_filename = str(get_app_data() / (self.p_name + STR_EXT_XML))

    @property
    def name(self) -> str:
        """Return the preferences name."""
        return self.p_name

    def get(self, name: str) -> str:
        """Get a preference value, expanding any macros.

        Macros are enclosed in braces like {Home}, {User}, {Sep}.

        Args:
            name: The preference key or a string containing macros

        Returns:
            The expanded preference value as a string
        """
        if name in self.p_preferences:
            value = self.p_preferences[name]
            if not isinstance(value, str):
                return str(value)
            t = value
        else:
            t = name

        result = ""
        while "{" in t:
            # Get text before the macro
            result += t.split("{", 1)[0]
            after = t.split("{", 1)[1]

            # Handle escaped braces {{
            if after.startswith("{"):
                result += "{"
                t = after[1:]
                continue

            # Get the macro name and remaining text
            ref = after.split("}", 1)[0]
            t = after.split("}", 1)[1] if "}" in after else ""

            # Expand known macros
            ref_lower = ref.lower()
            if ref_lower == "home":
                result += str(get_app_data())
            elif ref_lower == "user":
                result += get_user_name()
            elif ref_lower == "sep":
                result += os.sep
            else:
                # Recursive expansion
                result += self.get(ref)

        result += t
        result = result.replace("}}", "}")
        return result

    def __getitem__(self, name: str) -> Any:
        """Get a preference value directly without macro expansion."""
        return self.p_preferences.get(name)

    def __setitem__(self, name: str, value: Any) -> None:
        """Set a preference value."""
        self.p_preferences[name] = value

    def set(self, name: str, value: Any) -> None:
        """Set a preference value."""
        self.p_preferences[name] = value

    def contains(self, name: str) -> bool:
        """Check if a preference exists."""
        return name in self.p_preferences

    def init(self, name: str, value: Any) -> Any:
        """Initialize a preference with a default value if not present.

        Args:
            name: Preference key
            value: Default value to use if preference doesn't exist

        Returns:
            The existing or newly set value
        """
        if name not in self.p_preferences:
            self.p_preferences[name] = value
        return self.p_preferences[name]

    def exists_and_true(self, name: str) -> bool:
        """Check if a preference exists and is truthy."""
        if name not in self.p_preferences:
            return False
        value = self.p_preferences[name]
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            return value.lower() in ("true", "on", "yes", "1")
        return bool(value)

    def erase(self, name: str) -> None:
        """Remove a preference."""
        self.p_preferences.pop(name, None)

    def rename(self, old_name: str, new_name: str) -> None:
        """Rename a preference key."""
        if old_name in self.p_preferences:
            self.p_preferences[new_name] = self.p_preferences.pop(old_name)

    def find(self, key: str) -> Optional[Any]:
        """Find a preference by key."""
        return self.p_preferences.get(key)

    def __iter__(self) -> Iterator[str]:
        """Iterate over preference keys."""
        return iter(self.p_preferences)

    def items(self):
        """Return preference items."""
        return self.p_preferences.items()

    def set_path(self, path: str) -> None:
        """Set the preferences directory path."""
        self.p_path = path

    def set_filename(self, filename: str) -> None:
        """Set the preferences filename."""
        self.p_filename = filename

    def set_comment(self, comment: str) -> None:
        """Set the XML comment string."""
        self.p_comment = comment

    def open(self, filename: str = "") -> bool:
        """Load preferences from an XML file.

        Args:
            filename: Optional override filename

        Returns:
            True if successful, False otherwise
        """
        if filename:
            self.p_filename = filename

        try:
            tree = ET.parse(self.p_filename)
            root = tree.getroot()

            # Check for OSCAR root element
            if root.tag != STR_APP_NAME:
                # Check for old SleepyHead format
                if root.tag == "SleepyHead":
                    print(f"Found SleepyHead format in {self.p_filename}")
                    return False
                return False

            # Find the preferences section
            pref_elem = root.find(self.p_name)
            if pref_elem is None:
                return False

            self.p_preferences.clear()

            for elem in pref_elem:
                name = elem.tag
                type_attr = elem.get("type", "").lower()
                value_text = elem.text or ""

                try:
                    if type_attr == "double":
                        self.p_preferences[name] = float(value_text)
                    elif type_attr == "qlonglong":
                        self.p_preferences[name] = int(value_text)
                    elif type_attr == "int":
                        self.p_preferences[name] = int(value_text)
                    elif type_attr == "bool":
                        v = value_text.lower()
                        if v in ("true", "on", "yes"):
                            self.p_preferences[name] = True
                        elif v in ("false", "off", "no"):
                            self.p_preferences[name] = False
                        else:
                            self.p_preferences[name] = int(value_text) != 0
                    elif type_attr == "qdatetime":
                        self.p_preferences[name] = datetime.strptime(
                            value_text, "%Y-%m-%d %H:%M:%S"
                        )
                    elif type_attr == "qtime":
                        self.p_preferences[name] = datetime.strptime(
                            value_text, "%H:%M:%S"
                        ).time()
                    elif type_attr == "qdate":
                        self.p_preferences[name] = datetime.strptime(
                            value_text, "%Y-%m-%d"
                        ).date()
                    else:
                        # Default to string
                        self.p_preferences[name] = value_text
                except (ValueError, TypeError) as e:
                    print(f"Error parsing preference {name}: {e}")
                    self.p_preferences[name] = value_text

            return True

        except FileNotFoundError:
            print(f"Preferences file not found: {self.p_filename}")
            return False
        except ET.ParseError as e:
            print(f"XML parse error in {self.p_filename}: {e}")
            return False
        except Exception as e:
            print(f"Error opening preferences: {e}")
            return False

    def save(self, filename: str = "") -> bool:
        """Save preferences to an XML file.

        Args:
            filename: Optional override filename

        Returns:
            True if successful, False otherwise
        """
        if filename:
            self.p_filename = filename

        try:
            # Create root OSCAR element
            root = ET.Element(STR_APP_NAME)

            # Create preferences section
            pref_elem = ET.SubElement(root, self.p_name)

            for key, value in self.p_preferences.items():
                if value is None:
                    continue

                elem = ET.SubElement(pref_elem, key)

                # Set type attribute and text value
                if isinstance(value, bool):
                    elem.set("type", "bool")
                    elem.text = "true" if value else "false"
                elif isinstance(value, int):
                    if value > 2**31 or value < -(2**31):
                        elem.set("type", "qlonglong")
                    else:
                        elem.set("type", "int")
                    elem.text = str(value)
                elif isinstance(value, float):
                    elem.set("type", "double")
                    elem.text = str(value)
                elif isinstance(value, datetime):
                    elem.set("type", "QDateTime")
                    elem.text = value.strftime("%Y-%m-%d %H:%M:%S")
                elif isinstance(value, date):
                    elem.set("type", "QDate")
                    elem.text = value.strftime("%Y-%m-%d")
                elif isinstance(value, time):
                    elem.set("type", "QTime")
                    elem.text = value.strftime("%H:%M:%S")
                else:
                    elem.set("type", "QString")
                    elem.text = str(value)

            # Create the XML string with proper formatting
            rough_string = ET.tostring(root, encoding="unicode")
            reparsed = minidom.parseString(rough_string)

            # Add XML declaration
            xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>\n'

            # Ensure directory exists
            Path(self.p_filename).parent.mkdir(parents=True, exist_ok=True)

            with open(self.p_filename, "w", encoding="utf-8") as f:
                # Write BOM for UTF-8
                f.write("\ufeff")
                f.write(xml_declaration)
                # Write pretty-printed XML (skip the declaration from minidom)
                for line in reparsed.toprettyxml(indent="  ").split("\n")[1:]:
                    if line.strip():
                        f.write(line + "\n")

            return True

        except Exception as e:
            print(f"Error saving preferences to {self.p_filename}: {e}")
            return False


class PrefSettings:
    """Parent class for subclasses that manipulate profile preferences.

    This provides a convenience interface for accessing and modifying
    preferences through a Preferences object.
    """

    def __init__(self, pref: Preferences):
        """Initialize with a Preferences object.

        Args:
            pref: The Preferences object to wrap
        """
        self.m_pref = pref

    def set_pref(self, name: str, value: Any) -> None:
        """Set a preference value."""
        self.m_pref[name] = value

    def init_pref(self, name: str, value: Any) -> Any:
        """Initialize a preference with a default value."""
        return self.m_pref.init(name, value)

    def get_pref(self, name: str) -> Any:
        """Get a preference value."""
        return self.m_pref[name]

    def set_pref_object(self, pref: Preferences) -> None:
        """Set a new Preferences object."""
        self.m_pref = pref
