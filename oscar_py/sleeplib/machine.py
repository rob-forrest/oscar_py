"""
SleepLib Machine - Device Class Implementation

This module provides the Machine class representing a single device
and its data, ported from the C++ OSCAR codebase.

Copyright (c) 2019-2025 The OSCAR Team
License: GPL v3
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, date
from pathlib import Path
from typing import Dict, Optional, List, Set, Any, TYPE_CHECKING
import random
import logging
import xml.etree.ElementTree as ET

from .preferences import Preferences
from .schema import (
    MachineType, MachineID, SessionID, ChannelID, ChanType
)

# Import the full Session implementation
from .session import Session

if TYPE_CHECKING:
    from .profile import Profile

logger = logging.getLogger(__name__)


def to_hexid(machine_id: MachineID) -> str:
    """Convert a machine ID to lowercase hexadecimal string."""
    return f"{machine_id:08x}"


def generate_machine_id() -> MachineID:
    """Generate a new random machine ID."""
    return random.randint(1, 0xFFFFFFFF)


@dataclass
class MachineInfo:
    """Information about a device.

    Attributes:
        type: Type of machine (CPAP, Oximeter, etc.)
        cap: Device capabilities flags
        loadername: Name of the loader that handles this device
        brand: Device brand/manufacturer
        model: Device model name
        modelnumber: Device model number
        serial: Device serial number
        series: Device series name
        lastimported: Last import timestamp
        version: Loader version
        purgeDate: Date before which data should be purged
        properties: Additional text properties
    """
    type: MachineType = MachineType.MT_UNKNOWN
    cap: int = 0
    loadername: str = ""
    brand: str = ""
    model: str = ""
    modelnumber: str = ""
    serial: str = ""
    series: str = ""
    lastimported: Optional[datetime] = None
    version: int = 0
    purgeDate: Optional[date] = None
    properties: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        """Ensure properties dict exists."""
        if self.properties is None:
            self.properties = {}


# Note: Session class is now imported from session.py module
# The full implementation is in sleeplib/session.py


class Day:
    """Represents a single day's worth of data.

    This is a placeholder class - the full implementation would include
    aggregation of sessions, statistics calculations, etc.
    """

    def __init__(self, date_val: date):
        """Initialize a Day.

        Args:
            date_val: The date this day represents
        """
        self.date = date_val
        self.sessions: List[Session] = []
        self.machines: List['Machine'] = []

    def add_session(self, session: Session) -> None:
        """Add a session to this day."""
        self.sessions.append(session)
        if session.machine not in self.machines:
            self.machines.append(session.machine)

    def has_data(self, machine_type: MachineType = MachineType.MT_UNKNOWN) -> bool:
        """Check if this day has data for the given machine type."""
        if machine_type == MachineType.MT_UNKNOWN:
            return len(self.sessions) > 0

        for session in self.sessions:
            if session.machine.type == machine_type:
                return True
        return False


class Machine:
    """Device class representing a single device and its data.

    This is the heart of SleepLib, managing device information and
    associated session data.
    """

    def __init__(self, profile: 'Profile', machine_id: MachineID = 0):
        """Initialize a Machine.

        Args:
            profile: The profile this machine belongs to
            machine_id: Unique machine identifier (generated if 0)
        """
        self.profile = profile
        self._id = machine_id if machine_id else generate_machine_id()
        self.info = MachineInfo()

        # Session management
        self.sessionlist: Dict[SessionID, Session] = {}
        self.day: Dict[date, Day] = {}
        self.highest_sessionid: SessionID = 0
        self.firstday: Optional[date] = None
        self.lastday: Optional[date] = None

        # State flags
        self.changed = False
        self.firstsession = True
        self._suppress_untested_warning = False
        self._previous_unexpected: Set[str] = set()

        # Channel tracking
        self._available_channels: Dict[ChannelID, bool] = {}
        self._available_settings: Dict[ChannelID, bool] = {}

        # Paths
        self._path = ""
        self._data_path = ""
        self._summary_path = ""
        self._events_path = ""

    @property
    def id(self) -> MachineID:
        """Return the machine ID."""
        return self._id

    def set_id(self, machine_id: MachineID) -> None:
        """Set the machine ID."""
        self._id = machine_id

    def hexid(self) -> str:
        """Return machine ID as lowercase hex string."""
        return to_hexid(self._id)

    # Property accessors for MachineInfo fields
    @property
    def type(self) -> MachineType:
        return self.info.type

    @type.setter
    def type(self, value: MachineType) -> None:
        self.info.type = value

    @property
    def brand(self) -> str:
        return self.info.brand

    @brand.setter
    def brand(self, value: str) -> None:
        self.info.brand = value

    @property
    def model(self) -> str:
        return self.info.model

    @model.setter
    def model(self, value: str) -> None:
        self.info.model = value

    @property
    def serial(self) -> str:
        return self.info.serial

    @serial.setter
    def serial(self, value: str) -> None:
        self.info.serial = value

    @property
    def series(self) -> str:
        return self.info.series

    @property
    def modelnumber(self) -> str:
        return self.info.modelnumber

    @property
    def loader_name(self) -> str:
        return self.info.loadername

    @loader_name.setter
    def loader_name(self, value: str) -> None:
        self.info.loadername = value

    @property
    def cap(self) -> int:
        return self.info.cap

    @cap.setter
    def cap(self, value: int) -> None:
        self.info.cap = value

    @property
    def version(self) -> int:
        return self.info.version

    @property
    def last_imported(self) -> Optional[datetime]:
        return self.info.lastimported

    @property
    def purge_date(self) -> Optional[date]:
        return self.info.purgeDate

    @purge_date.setter
    def purge_date(self, value: Optional[date]) -> None:
        self.info.purgeDate = value

    def clear_purge_date(self) -> None:
        """Clear the purge date."""
        self.info.purgeDate = None

    def set_info(self, info: MachineInfo) -> None:
        """Set the machine info."""
        self.info = info

    def get_info(self) -> MachineInfo:
        """Get the machine info."""
        return self.info

    def warn_on_untested(self) -> bool:
        """Check if warnings should be shown for untested devices."""
        return not self._suppress_untested_warning

    def suppress_warn_on_untested(self) -> None:
        """Suppress warnings for untested devices."""
        self._suppress_untested_warning = True

    def previously_seen_unexpected_data(self) -> Set[str]:
        """Return set of previously seen unexpected data keys."""
        return self._previous_unexpected

    # Path management
    def get_data_path(self) -> str:
        """Get the data directory path for this machine.

        The path is {profile}/{loader}_{serial} format, e.g.:
        /path/to/profile/ResMed_23254434021/
        """
        if not self._data_path:
            # OSCAR uses {loader}_{serial} format for machine data folders
            folder_name = f"{self.info.loadername}_{self.info.serial}"
            self._data_path = str(Path(self.profile.path()) / folder_name)
        return self._data_path

    def get_events_path(self) -> str:
        """Get the events directory path."""
        if not self._events_path:
            self._events_path = str(Path(self.get_data_path()) / "Events")
        return self._events_path

    def get_summaries_path(self) -> str:
        """Get the summaries directory path."""
        if not self._summary_path:
            self._summary_path = str(Path(self.get_data_path()) / "Summaries")
        return self._summary_path

    def get_backup_path(self) -> str:
        """Get the backup directory path."""
        return str(Path(self.get_data_path()) / "Backup")

    # Channel management
    def has_channel(self, code: ChannelID) -> bool:
        """Check if this machine has data for the given channel."""
        return code in self._available_channels

    def has_setting(self, code: ChannelID) -> bool:
        """Check if this machine has the given setting."""
        return code in self._available_settings

    def available_channels(self, chantype: int) -> List[ChannelID]:
        """Get list of available channels matching the given type mask."""
        # This would filter by ChanType flags
        return list(self._available_channels.keys())

    def update_channels(self, session: Session) -> None:
        """Update available channels from a session."""
        for code in session.events.keys():
            self._available_channels[code] = True
        for code in session.settings.keys():
            self._available_settings[code] = True

    # Session management
    def session_exists(self, session_id: SessionID) -> Optional[Session]:
        """Check if a session exists and return it."""
        return self.sessionlist.get(session_id)

    def create_session_id(self) -> SessionID:
        """Create a new session ID."""
        return self.highest_sessionid + 1

    def add_session(self, session: Session, allow_old: bool = False) -> bool:
        """Add a session to this machine.

        Args:
            session: The session to add
            allow_old: Allow sessions older than existing data

        Returns:
            True if session was added successfully
        """
        if session.id in self.sessionlist:
            return False

        self.sessionlist[session.id] = session

        if session.id > self.highest_sessionid:
            self.highest_sessionid = session.id

        # Update date range
        if session.first:
            session_date = session.first.date()
            if self.firstday is None or session_date < self.firstday:
                self.firstday = session_date
            if self.lastday is None or session_date > self.lastday:
                self.lastday = session_date

            # Add to day
            if session_date not in self.day:
                self.day[session_date] = Day(session_date)
            self.day[session_date].add_session(session)

        self.update_channels(session)
        self.changed = True
        return True

    def unlink_session(self, session: Session) -> bool:
        """Remove a session from machine indexes."""
        if session.id not in self.sessionlist:
            return False

        del self.sessionlist[session.id]
        self.changed = True
        return True

    def has_modified_sessions(self) -> bool:
        """Check if any sessions have been modified."""
        for session in self.sessionlist.values():
            if session.changed:
                return True
        return self.changed

    # Placeholder methods for load/save
    def load(self, progress=None) -> bool:
        """Load all device summary data."""
        # Placeholder - would load from disk
        return True

    def load_summary(self, progress=None) -> bool:
        """Load summary data only."""
        # Placeholder - would load summaries
        return True

    def save(self) -> bool:
        """Save all modified sessions."""
        # Placeholder - would save to disk
        return True

    def save_session(self, session: Session) -> bool:
        """Save an individual session."""
        # Placeholder - would save session data
        return True

    def purge(self, secret: int) -> bool:
        """Delete all device data."""
        # Placeholder - would delete data files
        return False


class CPAP(Machine):
    """A CPAP-classed device object."""

    def __init__(self, profile: 'Profile', machine_id: MachineID = 0):
        """Initialize a CPAP machine."""
        super().__init__(profile, machine_id)
        self.info.type = MachineType.MT_CPAP
        self._sessions_loaded = False

    def load_sessions(self, progress=None) -> bool:
        """Load session summaries from disk.

        This loads the session index from Summaries.xml.gz and binary
        summary data from .000 files, populating the profile's daylist.

        Args:
            progress: Optional progress callback.

        Returns:
            True if sessions were loaded successfully.
        """
        if self._sessions_loaded:
            return True

        # Import here to avoid circular import
        from .summary_loader import SummaryLoader

        machine_path = Path(self.get_data_path())
        if not machine_path.exists():
            logger.warning(f"Machine path does not exist: {machine_path}")
            return False

        try:
            loader = SummaryLoader(machine_path)

            # Load session index from Summaries.xml.gz
            count = loader.load_session_index()
            if count == 0:
                logger.warning(f"No sessions found in index for {machine_path}")
                return False

            logger.info(f"Loaded index with {count} sessions")

            # Get day split hour from profile settings
            day_split_hour = 12
            if self.profile.session:
                split_time = self.profile.session.day_split_time
                day_split_hour = split_time.hour

            # Load binary summaries and create Session/Day objects
            loaded = loader.load_session_summaries(self.profile, day_split_hour)
            logger.info(f"Loaded {loaded} session summaries for {self.info.brand} {self.info.model}")

            self._sessions_loaded = True
            return True

        except Exception as e:
            logger.error(f"Error loading sessions: {e}")
            import traceback
            traceback.print_exc()
            return False


class Oximeter(Machine):
    """An Oximeter-classed device object."""

    def __init__(self, profile: 'Profile', machine_id: MachineID = 0):
        """Initialize an Oximeter machine."""
        super().__init__(profile, machine_id)
        self.info.type = MachineType.MT_OXIMETER


class SleepStage(Machine):
    """A SleepStage-classed device object."""

    def __init__(self, profile: 'Profile', machine_id: MachineID = 0):
        """Initialize a SleepStage machine."""
        super().__init__(profile, machine_id)
        self.info.type = MachineType.MT_SLEEPSTAGE


class PositionSensor(Machine):
    """A PositionSensor-classed device object."""

    def __init__(self, profile: 'Profile', machine_id: MachineID = 0):
        """Initialize a PositionSensor machine."""
        super().__init__(profile, machine_id)
        self.info.type = MachineType.MT_POSITION
