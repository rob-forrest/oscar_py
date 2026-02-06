"""
SleepLib Session - Session Data Class Implementation

This module provides the Session class for storing a single sleep session's
worth of device event/waveform information, ported from the C++ OSCAR codebase.

Copyright (c) 2019-2025 The OSCAR Team
License: GPL v3
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List, Any, BinaryIO, TYPE_CHECKING, Union
from enum import IntEnum
import struct
import os

from .schema import (
    MachineType, ChannelID, SessionID, EventDataType
)
from .event import EventList, EventListType

if TYPE_CHECKING:
    from .machine import Machine


# Binary format constants (matching C++ OSCAR format)
SESSION_MAGIC = 0x4F534341  # 'OSCA' in little-endian
SUMMARY_VERSION = 18
EVENTS_VERSION = 10
FILETYPE_SUMMARY = 0
FILETYPE_DATA = 1


class SliceStatus(IntEnum):
    """Status of a session slice."""
    UnknownStatus = 0
    EquipmentOff = 1
    MaskOn = 2
    MaskOff = 3


@dataclass
class SessionSlice:
    """Represents a time slice within a session (e.g., mask on/off periods)."""
    start: int = 0  # milliseconds since epoch
    end: int = 0    # milliseconds since epoch
    status: SliceStatus = SliceStatus.UnknownStatus


class Session:
    """Contains a single session's worth of device event/waveform information.

    This class also contains the primary database logic for SleepLib, managing
    event data, settings, and summary statistics.

    Attributes:
        machine: The machine this session belongs to
        session_id: Unique session identifier (typically Unix timestamp)
        enabled: Whether this session is enabled for statistics
        changed: Whether this session has been modified
        events: Dictionary mapping ChannelID to list of EventList objects
        settings: Dictionary mapping ChannelID to setting values
    """

    def __init__(self, machine: 'Machine', session_id: SessionID = 0):
        """Initialize a Session.

        Args:
            machine: The machine this session belongs to
            session_id: Unique session identifier (generated if 0)
        """
        self._machine = machine
        self._session_id = session_id if session_id else machine.create_session_id()

        # Time boundaries (milliseconds since epoch)
        self._first: int = 0  # Session start time
        self._last: int = 0   # Session end time

        # State flags
        self._changed: bool = False
        self._enabled: int = 1  # Using int like C++ (quint8)
        self._lone_session: bool = False
        self._summary_only: bool = False
        self._no_settings: bool = False
        self._summary_loaded: bool = False
        self._events_loaded: bool = False
        self._evchecksum_checked: bool = False

        # Event data: ChannelID -> list of EventList
        self._eventlist: Dict[ChannelID, List[EventList]] = {}

        # Session settings: ChannelID -> value
        self._settings: Dict[ChannelID, Any] = {}

        # Session summary caches
        self._cnt: Dict[ChannelID, EventDataType] = {}
        self._sum: Dict[ChannelID, float] = {}
        self._avg: Dict[ChannelID, EventDataType] = {}
        self._wavg: Dict[ChannelID, EventDataType] = {}
        self._min: Dict[ChannelID, EventDataType] = {}
        self._max: Dict[ChannelID, EventDataType] = {}
        self._physmin: Dict[ChannelID, EventDataType] = {}
        self._physmax: Dict[ChannelID, EventDataType] = {}
        self._cph: Dict[ChannelID, EventDataType] = {}
        self._sph: Dict[ChannelID, EventDataType] = {}
        self._firstchan: Dict[ChannelID, int] = {}
        self._lastchan: Dict[ChannelID, int] = {}
        self._gain: Dict[ChannelID, EventDataType] = {}

        # Value/time summaries for discrete values
        self._valuesummary: Dict[ChannelID, Dict[int, int]] = {}
        self._timesummary: Dict[ChannelID, Dict[int, int]] = {}

        # Threshold tracking
        self._lower_threshold: Dict[ChannelID, EventDataType] = {}
        self._time_below_threshold: Dict[ChannelID, EventDataType] = {}
        self._upper_threshold: Dict[ChannelID, EventDataType] = {}
        self._time_above_threshold: Dict[ChannelID, EventDataType] = {}

        # Available channels list
        self._available_channels: List[ChannelID] = []
        self._available_settings: List[ChannelID] = []

        # Session slices (mask on/off periods)
        self._slices: List[SessionSlice] = []

    # Properties

    @property
    def session_id(self) -> SessionID:
        """Return the session ID."""
        return self._session_id

    @property
    def id(self) -> SessionID:
        """Return the session ID (alias for session_id)."""
        return self._session_id

    @id.setter
    def id(self, value: SessionID) -> None:
        """Set the session ID."""
        self._session_id = value

    @property
    def machine(self) -> 'Machine':
        """Return the machine this session belongs to."""
        return self._machine

    @property
    def type(self) -> MachineType:
        """Return the machine type for this session."""
        return self._machine.type

    @property
    def enabled(self) -> bool:
        """Return whether this session is enabled."""
        return bool(self._enabled)

    @enabled.setter
    def enabled(self, value: bool) -> None:
        """Set whether this session is enabled."""
        self._enabled = 1 if value else 0

    @property
    def changed(self) -> bool:
        """Return whether this session has been modified."""
        return self._changed

    @changed.setter
    def changed(self, value: bool) -> None:
        """Set whether this session has been modified."""
        self._changed = value
        if value:
            self._events_loaded = value

    @property
    def summary_only(self) -> bool:
        """Return whether this session contains only summary data."""
        return self._summary_only

    @summary_only.setter
    def summary_only(self, value: bool) -> None:
        """Set whether this session contains only summary data."""
        self._summary_only = value

    @property
    def no_settings(self) -> bool:
        """Return whether this session has no settings."""
        return self._no_settings

    @no_settings.setter
    def no_settings(self, value: bool) -> None:
        """Set whether this session has no settings."""
        self._no_settings = value

    @property
    def events_loaded(self) -> bool:
        """Return whether event data is loaded."""
        return self._events_loaded

    @property
    def summary_loaded(self) -> bool:
        """Return whether summary data is loaded."""
        return self._summary_loaded

    @property
    def events(self) -> Dict[ChannelID, List[EventList]]:
        """Return the events dictionary."""
        return self._eventlist

    @property
    def settings(self) -> Dict[ChannelID, Any]:
        """Return the settings dictionary."""
        return self._settings

    @property
    def slices(self) -> List[SessionSlice]:
        """Return the session slices."""
        return self._slices

    # Time properties

    @property
    def first_time(self) -> int:
        """Return the session start time (ms since epoch)."""
        return self._first

    @first_time.setter
    def first_time(self, value: int) -> None:
        """Set the session start time."""
        self._first = value

    @property
    def last_time(self) -> int:
        """Return the session end time (ms since epoch)."""
        return self._last

    @last_time.setter
    def last_time(self, value: int) -> None:
        """Set the session end time."""
        self._last = value

    @property
    def first(self) -> Optional[datetime]:
        """Return the session start time as datetime."""
        if self._first:
            return datetime.fromtimestamp(self._first / 1000.0)
        return None

    @first.setter
    def first(self, value: Optional[datetime]) -> None:
        """Set the session start time from datetime."""
        if value:
            self._first = int(value.timestamp() * 1000)
        else:
            self._first = 0

    @property
    def last(self) -> Optional[datetime]:
        """Return the session end time as datetime."""
        if self._last:
            return datetime.fromtimestamp(self._last / 1000.0)
        return None

    @last.setter
    def last(self, value: Optional[datetime]) -> None:
        """Set the session end time from datetime."""
        if value:
            self._last = int(value.timestamp() * 1000)
        else:
            self._last = 0

    def real_first(self) -> int:
        """Return the raw first time (ms since epoch)."""
        return self._first

    def real_last(self) -> int:
        """Return the raw last time (ms since epoch)."""
        return self._last

    def set_first(self, time_ms: int) -> None:
        """Set first time to lower of time_ms and existing first."""
        if not self._first:
            self._first = time_ms
        elif time_ms < self._first:
            self._first = time_ms

    def set_last(self, time_ms: int) -> None:
        """Set last time to higher of time_ms and existing last."""
        if time_ms <= self._first:
            print(f"Warning: Session.set_last() time_ms <= first: {time_ms} <= {self._first}")
            return

        if not self._last:
            self._last = time_ms
        elif self._last < time_ms:
            self._last = time_ms

    def really_set_first(self, time_ms: int) -> None:
        """Set first time without comparison."""
        self._first = time_ms

    def really_set_last(self, time_ms: int) -> None:
        """Set last time without comparison."""
        self._last = time_ms

    def update_first(self, time_ms: int) -> None:
        """Update first time if less than current."""
        if not self._first:
            self._first = time_ms
        elif self._first > time_ms:
            self._first = time_ms

    def update_last(self, time_ms: int) -> None:
        """Update last time if greater than current."""
        if not self._last:
            self._last = time_ms
        elif self._last < time_ms:
            self._last = time_ms

    # Duration methods

    def length(self) -> int:
        """Return session length in milliseconds."""
        duration = self._last - self._first
        return duration if duration > 0 else 0

    def hours(self) -> float:
        """Return session duration in decimal hours.

        If slices are defined, only counts time where mask is on.
        """
        if len(self._slices) == 0:
            return (self._last - self._first) / 3600000.0
        else:
            total = 0
            for slice in self._slices:
                if slice.status == SliceStatus.MaskOn:
                    total += slice.end - slice.start
            return total / 3600000.0

    def duration(self) -> float:
        """Return session duration in hours (alias for hours())."""
        return self.hours()

    def is_empty(self) -> bool:
        """Return True if session contains an empty duration."""
        return self._first == self._last

    def check_inside(self, time_ms: int) -> bool:
        """Check if time is within session bounds."""
        return self._first <= time_ms <= self._last

    # Event list management

    def add_event_list(
        self,
        channel_id: ChannelID,
        event_type: EventListType = EventListType.EVL_Event,
        gain: EventDataType = 1.0,
        offset: EventDataType = 0.0,
        min_val: EventDataType = 0.0,
        max_val: EventDataType = 0.0,
        rate: EventDataType = 0.0,
        second_field: bool = False
    ) -> EventList:
        """Create and add a new EventList for the given channel.

        Args:
            channel_id: Channel ID for this event list
            event_type: EVL_Waveform or EVL_Event
            gain: Gain multiplier
            offset: Offset value
            min_val: Minimum value (0 for auto)
            max_val: Maximum value (0 for auto)
            rate: Sample rate for waveforms
            second_field: Whether to use second data field

        Returns:
            The newly created EventList
        """
        evlist = EventList(
            event_type=event_type,
            gain=gain,
            offset=offset,
            min_val=min_val,
            max_val=max_val,
            rate=rate,
            second_field=second_field
        )

        if channel_id not in self._eventlist:
            self._eventlist[channel_id] = []
        self._eventlist[channel_id].append(evlist)

        return evlist

    def get_event_list(self, channel_id: ChannelID) -> Optional[List[EventList]]:
        """Get the list of EventLists for a channel.

        Args:
            channel_id: Channel ID to look up

        Returns:
            List of EventList objects, or None if channel not found
        """
        return self._eventlist.get(channel_id)

    def get_first_event_list(self, channel_id: ChannelID) -> Optional[EventList]:
        """Get the first EventList for a channel.

        Args:
            channel_id: Channel ID to look up

        Returns:
            First EventList for channel, or None if not found
        """
        evlists = self._eventlist.get(channel_id)
        if evlists and len(evlists) > 0:
            return evlists[0]
        return None

    def destroy_event(self, channel_id: ChannelID) -> None:
        """Destroy all EventLists for a channel and remove from caches."""
        if channel_id in self._eventlist:
            del self._eventlist[channel_id]

        # Remove from caches
        for cache in [self._gain, self._firstchan, self._lastchan, self._sph,
                      self._cph, self._min, self._max, self._avg, self._wavg,
                      self._sum, self._cnt]:
            cache.pop(channel_id, None)

        if channel_id in self._valuesummary:
            del self._valuesummary[channel_id]
        if channel_id in self._timesummary:
            del self._timesummary[channel_id]

    def trash_events(self) -> None:
        """Release all event data from memory."""
        if self._changed:
            # Should save first
            pass

        self._eventlist.clear()
        self._events_loaded = False

    # Settings management

    def set_setting(self, channel_id: ChannelID, value: Any) -> None:
        """Set a session setting.

        Args:
            channel_id: Channel ID for the setting
            value: Setting value
        """
        self._settings[channel_id] = value

    def get_setting(self, channel_id: ChannelID, default: Any = None) -> Any:
        """Get a session setting.

        Args:
            channel_id: Channel ID for the setting
            default: Default value if not found

        Returns:
            Setting value or default
        """
        return self._settings.get(channel_id, default)

    def has_setting(self, channel_id: ChannelID) -> bool:
        """Check if a setting exists."""
        return channel_id in self._settings

    # Channel existence checks

    def channel_exists(self, channel_id: ChannelID) -> bool:
        """Check if channel has events or a count record."""
        if not self._enabled:
            return False

        if self._events_loaded:
            return channel_id in self._eventlist
        else:
            cnt = self._cnt.get(channel_id)
            return cnt is not None and cnt > 0

    def channel_data_exists(self, channel_id: ChannelID) -> bool:
        """Check if channel has event data loaded."""
        if self._events_loaded:
            return channel_id in self._eventlist
        else:
            print("Warning: Calling channel_data_exists without open event data!")
            return False

    # Summary cache setters

    def set_count(self, channel_id: ChannelID, val: EventDataType) -> None:
        """Set count for a channel."""
        self._cnt[channel_id] = val

    def set_sum(self, channel_id: ChannelID, val: float) -> None:
        """Set sum for a channel."""
        self._sum[channel_id] = val

    def set_min(self, channel_id: ChannelID, val: EventDataType) -> None:
        """Set minimum for a channel."""
        self._min[channel_id] = val

    def set_max(self, channel_id: ChannelID, val: EventDataType) -> None:
        """Set maximum for a channel."""
        self._max[channel_id] = val

    def set_phys_min(self, channel_id: ChannelID, val: EventDataType) -> None:
        """Set physical minimum for a channel."""
        self._physmin[channel_id] = val

    def set_phys_max(self, channel_id: ChannelID, val: EventDataType) -> None:
        """Set physical maximum for a channel."""
        self._physmax[channel_id] = val

    def update_min(self, channel_id: ChannelID, val: EventDataType) -> None:
        """Update minimum if val is lower."""
        if channel_id not in self._min:
            self._min[channel_id] = val
        elif self._min[channel_id] > val:
            self._min[channel_id] = val

    def update_max(self, channel_id: ChannelID, val: EventDataType) -> None:
        """Update maximum if val is higher."""
        if channel_id not in self._max:
            self._max[channel_id] = val
        elif self._max[channel_id] < val:
            self._max[channel_id] = val

    def set_avg(self, channel_id: ChannelID, val: EventDataType) -> None:
        """Set average for a channel."""
        self._avg[channel_id] = val

    def set_wavg(self, channel_id: ChannelID, val: EventDataType) -> None:
        """Set weighted average for a channel."""
        self._wavg[channel_id] = val

    def set_cph(self, channel_id: ChannelID, val: EventDataType) -> None:
        """Set counts per hour for a channel."""
        self._cph[channel_id] = val

    def set_sph(self, channel_id: ChannelID, val: EventDataType) -> None:
        """Set sum per hour for a channel."""
        self._sph[channel_id] = val

    def set_first_chan(self, channel_id: ChannelID, val: int) -> None:
        """Set first time for a channel."""
        self._firstchan[channel_id] = val

    def set_last_chan(self, channel_id: ChannelID, val: int) -> None:
        """Set last time for a channel."""
        self._lastchan[channel_id] = val

    # Summary cache getters (with calculation if needed)

    def count(self, channel_id: ChannelID) -> EventDataType:
        """Return the count of events for a channel."""
        if channel_id in self._cnt:
            return self._cnt[channel_id]

        if channel_id not in self._eventlist:
            return 0

        total = sum(evlist.count for evlist in self._eventlist[channel_id])
        self._cnt[channel_id] = total
        return total

    def sum_values(self, channel_id: ChannelID) -> float:
        """Return the sum of all event values for a channel."""
        if channel_id in self._sum:
            return self._sum[channel_id]

        if channel_id not in self._eventlist:
            self._sum[channel_id] = 0.0
            return 0.0

        total = 0.0
        for evlist in self._eventlist[channel_id]:
            gain = evlist.gain
            for i in range(evlist.count):
                total += float(evlist.raw(i)) * gain

        self._sum[channel_id] = total
        return total

    def avg(self, channel_id: ChannelID) -> EventDataType:
        """Return the average of all event values for a channel."""
        if channel_id in self._avg:
            return self._avg[channel_id]

        if channel_id not in self._eventlist:
            self._avg[channel_id] = 0.0
            return 0.0

        total = 0.0
        cnt = 0
        for evlist in self._eventlist[channel_id]:
            gain = evlist.gain
            for i in range(evlist.count):
                total += float(evlist.raw(i)) * gain
            cnt += evlist.count

        val = total / cnt if cnt > 0 else 0.0
        self._avg[channel_id] = val
        return val

    def min_value(self, channel_id: ChannelID) -> EventDataType:
        """Return the minimum value for a channel."""
        if channel_id in self._min:
            return self._min[channel_id]

        if channel_id not in self._eventlist:
            self._min[channel_id] = 0.0
            return 0.0

        first = True
        min_val = 0.0
        for evlist in self._eventlist[channel_id]:
            if evlist.count > 0:
                t1 = evlist.min
                if t1 == 0 and t1 == evlist.max:
                    continue
                if first:
                    min_val = t1
                    first = False
                elif min_val > t1:
                    min_val = t1

        self._min[channel_id] = min_val
        return min_val

    def max_value(self, channel_id: ChannelID) -> EventDataType:
        """Return the maximum value for a channel."""
        if channel_id in self._max:
            return self._max[channel_id]

        if channel_id not in self._eventlist:
            self._max[channel_id] = 0.0
            return 0.0

        first = True
        max_val = 0.0
        for evlist in self._eventlist[channel_id]:
            if evlist.count > 0:
                t1 = evlist.max
                if t1 == 0 and t1 == evlist.min:
                    continue
                if first:
                    max_val = t1
                    first = False
                elif max_val < t1:
                    max_val = t1

        self._max[channel_id] = max_val
        return max_val

    def cph(self, channel_id: ChannelID) -> EventDataType:
        """Return count per hour for a channel."""
        if channel_id in self._cph:
            return self._cph[channel_id]

        val = self.count(channel_id) / self.hours() if self.hours() > 0 else 0.0
        self._cph[channel_id] = val
        return val

    def sph(self, channel_id: ChannelID) -> EventDataType:
        """Return sum per hour for a channel."""
        if channel_id in self._sph:
            return self._sph[channel_id]

        h = self.hours()
        val = (self.sum_values(channel_id) / 3600.0) * (100.0 / h) if h > 0 else 0.0
        self._sph[channel_id] = val
        return val

    def first_chan(self, channel_id: ChannelID) -> int:
        """Return first timestamp for a channel."""
        if channel_id in self._firstchan:
            return self._firstchan[channel_id]

        if channel_id not in self._eventlist:
            return 0

        first = True
        min_time = 0
        for evlist in self._eventlist[channel_id]:
            t1 = evlist.first
            if first:
                min_time = t1
                first = False
            elif min_time > t1:
                min_time = t1

        self._firstchan[channel_id] = min_time
        return min_time

    def last_chan(self, channel_id: ChannelID) -> int:
        """Return last timestamp for a channel."""
        if channel_id in self._lastchan:
            return self._lastchan[channel_id]

        if channel_id not in self._eventlist:
            return 0

        first = True
        max_time = 0
        for evlist in self._eventlist[channel_id]:
            t1 = evlist.last
            if first:
                max_time = t1
                first = False
            elif max_time < t1:
                max_time = t1

        self._lastchan[channel_id] = max_time
        return max_time

    # File I/O

    def event_file(self) -> str:
        """Return the event file path for this session."""
        return os.path.join(
            self._machine.get_events_path(),
            f"{self._session_id:08x}.001"
        )

    def summary_file(self) -> str:
        """Return the summary file path for this session."""
        return os.path.join(
            self._machine.get_summaries_path(),
            f"{self._session_id:08x}.000"
        )

    def store(self, path: str) -> bool:
        """Store the session to disk.

        Args:
            path: Directory path for storage

        Returns:
            True on success
        """
        os.makedirs(path, exist_ok=True)

        # Store summary
        if not self.store_summary():
            return False

        # Store events if we have any
        if len(self._eventlist) > 0:
            self.store_events()

        self._changed = False
        self._events_loaded = True
        return True

    def store_summary(self) -> bool:
        """Store the session summary to disk.

        Returns:
            True on success
        """
        if self._first == 0:
            print(f"Warning: Discarding session {self._session_id} with first=0")
            return False

        summary_path = self._machine.get_summaries_path()
        os.makedirs(summary_path, exist_ok=True)

        filename = os.path.join(summary_path, f"{self._session_id:08x}.000")

        try:
            with open(filename, 'wb') as f:
                self._write_summary(f)
            return True
        except Exception as e:
            print(f"Error storing summary: {e}")
            return False

    def _write_summary(self, f: BinaryIO) -> None:
        """Write summary data to file."""
        # Header
        f.write(struct.pack('<I', SESSION_MAGIC))
        f.write(struct.pack('<H', SUMMARY_VERSION))
        f.write(struct.pack('<H', FILETYPE_SUMMARY))
        f.write(struct.pack('<I', self._machine.id))
        f.write(struct.pack('<I', self._session_id))
        f.write(struct.pack('<q', self._first))
        f.write(struct.pack('<q', self._last))

        # Settings (simplified - just write count and key-value pairs)
        self._write_dict_any(f, self._settings)

        # Cached values
        self._write_dict_float(f, self._cnt)
        self._write_dict_double(f, self._sum)
        self._write_dict_float(f, self._avg)
        self._write_dict_float(f, self._wavg)
        self._write_dict_float(f, self._min)
        self._write_dict_float(f, self._max)
        self._write_dict_float(f, self._physmin)
        self._write_dict_float(f, self._physmax)
        self._write_dict_float(f, self._cph)
        self._write_dict_float(f, self._sph)
        self._write_dict_int64(f, self._firstchan)
        self._write_dict_int64(f, self._lastchan)

        # Value and time summaries (nested dicts)
        self._write_value_summary(f, self._valuesummary)
        self._write_time_summary(f, self._timesummary)

        # Gain
        self._write_dict_float(f, self._gain)

        # Available channels
        f.write(struct.pack('<I', len(self._available_channels)))
        for ch in self._available_channels:
            f.write(struct.pack('<I', ch))

        # Threshold data
        self._write_dict_float(f, self._time_above_threshold)
        self._write_dict_float(f, self._upper_threshold)
        self._write_dict_float(f, self._time_below_threshold)
        self._write_dict_float(f, self._lower_threshold)

        # Flags
        f.write(struct.pack('<B', 1 if self._summary_only else 0))
        f.write(struct.pack('<B', 1 if self._no_settings else 0))

        # Slices
        f.write(struct.pack('<I', len(self._slices)))
        for slice in self._slices:
            f.write(struct.pack('<q', slice.start))
            f.write(struct.pack('<I', slice.end - slice.start))
            f.write(struct.pack('<H', int(slice.status)))

    def _write_dict_float(self, f: BinaryIO, d: Dict[int, float]) -> None:
        """Write a dict of int->float."""
        f.write(struct.pack('<I', len(d)))
        for k, v in d.items():
            f.write(struct.pack('<I', k))
            f.write(struct.pack('<f', float(v)))

    def _write_dict_double(self, f: BinaryIO, d: Dict[int, float]) -> None:
        """Write a dict of int->double."""
        f.write(struct.pack('<I', len(d)))
        for k, v in d.items():
            f.write(struct.pack('<I', k))
            f.write(struct.pack('<d', float(v)))

    def _write_dict_int64(self, f: BinaryIO, d: Dict[int, int]) -> None:
        """Write a dict of int->int64."""
        f.write(struct.pack('<I', len(d)))
        for k, v in d.items():
            f.write(struct.pack('<I', k))
            f.write(struct.pack('<Q', v))

    def _write_dict_any(self, f: BinaryIO, d: Dict[int, Any]) -> None:
        """Write a dict of int->any (using pickle-like encoding)."""
        f.write(struct.pack('<I', len(d)))
        for k, v in d.items():
            f.write(struct.pack('<I', k))
            # Type tag + value
            if isinstance(v, bool):
                f.write(struct.pack('<B', 1))  # bool type
                f.write(struct.pack('<B', 1 if v else 0))
            elif isinstance(v, int):
                f.write(struct.pack('<B', 2))  # int type
                f.write(struct.pack('<q', v))
            elif isinstance(v, float):
                f.write(struct.pack('<B', 3))  # float type
                f.write(struct.pack('<d', v))
            elif isinstance(v, str):
                f.write(struct.pack('<B', 4))  # string type
                encoded = v.encode('utf-8')
                f.write(struct.pack('<I', len(encoded)))
                f.write(encoded)
            else:
                # Skip unknown types
                f.write(struct.pack('<B', 0))

    def _write_value_summary(self, f: BinaryIO, d: Dict[int, Dict[int, int]]) -> None:
        """Write value summary (nested dict)."""
        f.write(struct.pack('<I', len(d)))
        for k, inner in d.items():
            f.write(struct.pack('<I', k))
            f.write(struct.pack('<I', len(inner)))
            for ik, iv in inner.items():
                f.write(struct.pack('<h', ik))  # EventStoreType is int16
                f.write(struct.pack('<h', iv))

    def _write_time_summary(self, f: BinaryIO, d: Dict[int, Dict[int, int]]) -> None:
        """Write time summary (nested dict)."""
        f.write(struct.pack('<I', len(d)))
        for k, inner in d.items():
            f.write(struct.pack('<I', k))
            f.write(struct.pack('<I', len(inner)))
            for ik, iv in inner.items():
                f.write(struct.pack('<h', ik))
                f.write(struct.pack('<I', iv))

    def store_events(self) -> bool:
        """Store event data to disk.

        Returns:
            True on success
        """
        events_path = self._machine.get_events_path()
        os.makedirs(events_path, exist_ok=True)

        filename = os.path.join(events_path, f"{self._session_id:08x}.001")

        try:
            with open(filename, 'wb') as f:
                self._write_events(f)
            return True
        except Exception as e:
            print(f"Error storing events: {e}")
            return False

    def _write_events(self, f: BinaryIO) -> None:
        """Write event data to file."""
        # Header
        f.write(struct.pack('<I', SESSION_MAGIC))
        f.write(struct.pack('<H', EVENTS_VERSION))
        f.write(struct.pack('<H', FILETYPE_DATA))
        f.write(struct.pack('<I', self._machine.id))
        f.write(struct.pack('<I', self._session_id))
        f.write(struct.pack('<q', self._first))
        f.write(struct.pack('<q', self._last))

        # Compression (0 = none)
        f.write(struct.pack('<H', 0))
        # Machine type
        f.write(struct.pack('<H', int(self._machine.type)))

        # Data size and checksum (placeholders - would need compression to use)
        data_start = f.tell()
        f.write(struct.pack('<I', 0))  # datasize placeholder
        f.write(struct.pack('<H', 0))  # checksum placeholder

        # Count of channels
        f.write(struct.pack('<h', len(self._eventlist)))

        # Write event list metadata
        for channel_id, evlists in self._eventlist.items():
            f.write(struct.pack('<I', channel_id))
            f.write(struct.pack('<h', len(evlists)))

            for evlist in evlists:
                f.write(struct.pack('<q', evlist.first))
                f.write(struct.pack('<q', evlist.last))
                f.write(struct.pack('<i', evlist.count))
                f.write(struct.pack('<b', int(evlist.type)))
                f.write(struct.pack('<f', evlist.rate))
                f.write(struct.pack('<f', evlist.gain))
                f.write(struct.pack('<f', evlist.offset))
                f.write(struct.pack('<f', evlist.min))
                f.write(struct.pack('<f', evlist.max))

                # Dimension string
                dim_bytes = evlist.dimension.encode('utf-8')
                f.write(struct.pack('<I', len(dim_bytes)))
                f.write(dim_bytes)

                # Second field flag
                f.write(struct.pack('<B', 1 if evlist.has_second_field else 0))

                if evlist.has_second_field:
                    f.write(struct.pack('<f', evlist.min2))
                    f.write(struct.pack('<f', evlist.max2))

        # Write event list data
        for channel_id, evlists in self._eventlist.items():
            for evlist in evlists:
                # Data array (int16)
                f.write(evlist.raw_data().tobytes())

                # Second field if present
                if evlist.has_second_field:
                    f.write(evlist.raw_data2().tobytes())

                # Time deltas for events (not waveforms)
                if evlist.type != EventListType.EVL_Waveform:
                    f.write(evlist.raw_time().tobytes())

    def load_summary(self, debug: bool = False) -> bool:
        """Load session summary from disk.

        Args:
            debug: Print debug messages on error

        Returns:
            True on success
        """
        if self._summary_loaded:
            return True

        filename = self.summary_file()
        if not os.path.exists(filename):
            if debug:
                print(f"Summary file not found: {filename}")
            return False

        try:
            with open(filename, 'rb') as f:
                return self._read_summary(f, debug)
        except Exception as e:
            if debug:
                print(f"Error loading summary: {e}")
            return False

    def _read_summary(self, f: BinaryIO, debug: bool) -> bool:
        """Read summary data from file."""
        # Verify magic
        magic = struct.unpack('<I', f.read(4))[0]
        if magic != SESSION_MAGIC:
            if debug:
                print(f"Wrong magic number")
            return False

        # Version
        version = struct.unpack('<H', f.read(2))[0]
        if version < 6:
            if debug:
                print(f"Old file version: {version}")
            return False

        # File type
        filetype = struct.unpack('<H', f.read(2))[0]
        if filetype != FILETYPE_SUMMARY:
            if debug:
                print("Wrong file type")
            return False

        # Machine ID
        machine_id = struct.unpack('<I', f.read(4))[0]

        # Session ID
        self._session_id = struct.unpack('<I', f.read(4))[0]

        # Times
        self._first = struct.unpack('<q', f.read(8))[0]
        self._last = struct.unpack('<q', f.read(8))[0]

        # Settings and caches
        self._settings = self._read_dict_any(f)
        self._cnt = self._read_dict_float(f)
        self._sum = self._read_dict_double(f)
        self._avg = self._read_dict_float(f)
        self._wavg = self._read_dict_float(f)
        self._min = self._read_dict_float(f)
        self._max = self._read_dict_float(f)

        if version >= 12:
            self._physmin = self._read_dict_float(f)
            self._physmax = self._read_dict_float(f)

        self._cph = self._read_dict_float(f)
        self._sph = self._read_dict_float(f)
        self._firstchan = self._read_dict_int64(f)
        self._lastchan = self._read_dict_int64(f)

        if version >= 8:
            self._valuesummary = self._read_value_summary(f)
            self._timesummary = self._read_time_summary(f)

            if version >= 9:
                self._gain = self._read_dict_float(f)

        if version >= 15:
            count = struct.unpack('<I', f.read(4))[0]
            self._available_channels = [
                struct.unpack('<I', f.read(4))[0] for _ in range(count)
            ]
            self._time_above_threshold = self._read_dict_float(f)
            self._upper_threshold = self._read_dict_float(f)
            self._time_below_threshold = self._read_dict_float(f)
            self._lower_threshold = self._read_dict_float(f)

        if version >= 14:
            self._summary_only = struct.unpack('<B', f.read(1))[0] != 0

        if version >= 18:
            self._no_settings = struct.unpack('<B', f.read(1))[0] != 0
        else:
            self._no_settings = len(self._settings) == 0

        if version >= 17:
            count = struct.unpack('<I', f.read(4))[0]
            self._slices = []
            for _ in range(count):
                start = struct.unpack('<q', f.read(8))[0]
                length = struct.unpack('<I', f.read(4))[0]
                status = SliceStatus(struct.unpack('<H', f.read(2))[0])
                self._slices.append(SessionSlice(start, start + length, status))

        self._summary_loaded = True
        return True

    def _read_dict_float(self, f: BinaryIO) -> Dict[int, float]:
        """Read a dict of int->float."""
        count = struct.unpack('<I', f.read(4))[0]
        result = {}
        for _ in range(count):
            k = struct.unpack('<I', f.read(4))[0]
            v = struct.unpack('<f', f.read(4))[0]
            result[k] = v
        return result

    def _read_dict_double(self, f: BinaryIO) -> Dict[int, float]:
        """Read a dict of int->double."""
        count = struct.unpack('<I', f.read(4))[0]
        result = {}
        for _ in range(count):
            k = struct.unpack('<I', f.read(4))[0]
            v = struct.unpack('<d', f.read(8))[0]
            result[k] = v
        return result

    def _read_dict_int64(self, f: BinaryIO) -> Dict[int, int]:
        """Read a dict of int->int64."""
        count = struct.unpack('<I', f.read(4))[0]
        result = {}
        for _ in range(count):
            k = struct.unpack('<I', f.read(4))[0]
            v = struct.unpack('<Q', f.read(8))[0]
            result[k] = v
        return result

    def _read_dict_any(self, f: BinaryIO) -> Dict[int, Any]:
        """Read a dict of int->any."""
        count = struct.unpack('<I', f.read(4))[0]
        result = {}
        for _ in range(count):
            k = struct.unpack('<I', f.read(4))[0]
            type_tag = struct.unpack('<B', f.read(1))[0]
            if type_tag == 0:
                v = None
            elif type_tag == 1:  # bool
                v = struct.unpack('<B', f.read(1))[0] != 0
            elif type_tag == 2:  # int
                v = struct.unpack('<q', f.read(8))[0]
            elif type_tag == 3:  # float
                v = struct.unpack('<d', f.read(8))[0]
            elif type_tag == 4:  # string
                length = struct.unpack('<I', f.read(4))[0]
                v = f.read(length).decode('utf-8')
            else:
                v = None
            if v is not None:
                result[k] = v
        return result

    def _read_value_summary(self, f: BinaryIO) -> Dict[int, Dict[int, int]]:
        """Read value summary (nested dict)."""
        count = struct.unpack('<I', f.read(4))[0]
        result = {}
        for _ in range(count):
            k = struct.unpack('<I', f.read(4))[0]
            inner_count = struct.unpack('<I', f.read(4))[0]
            inner = {}
            for _ in range(inner_count):
                ik = struct.unpack('<h', f.read(2))[0]
                iv = struct.unpack('<h', f.read(2))[0]
                inner[ik] = iv
            result[k] = inner
        return result

    def _read_time_summary(self, f: BinaryIO) -> Dict[int, Dict[int, int]]:
        """Read time summary (nested dict)."""
        count = struct.unpack('<I', f.read(4))[0]
        result = {}
        for _ in range(count):
            k = struct.unpack('<I', f.read(4))[0]
            inner_count = struct.unpack('<I', f.read(4))[0]
            inner = {}
            for _ in range(inner_count):
                ik = struct.unpack('<h', f.read(2))[0]
                iv = struct.unpack('<I', f.read(4))[0]
                inner[ik] = iv
            result[k] = inner
        return result

    def load_events(self, filename: str = "", debug: bool = False) -> bool:
        """Load event data from disk.

        Args:
            filename: Optional filename (uses default if empty)
            debug: Print debug messages on error

        Returns:
            True on success
        """
        if not filename:
            filename = self.event_file()

        if not os.path.exists(filename):
            if debug:
                print(f"Event file not found: {filename}")
            return False

        try:
            with open(filename, 'rb') as f:
                return self._read_events(f, debug)
        except Exception as e:
            if debug:
                print(f"Error loading events: {e}")
            return False

    def open_events(self, debug: bool = False) -> bool:
        """Load events if not already loaded.

        Args:
            debug: Print debug messages on error

        Returns:
            True if events are loaded
        """
        if self._events_loaded:
            return True

        if len(self._eventlist) > 0:
            self._events_loaded = True
            return True

        return self.load_events(debug=debug)

    def _read_events(self, f: BinaryIO, debug: bool) -> bool:
        """Read event data from file."""
        import numpy as np

        # Header
        magic = struct.unpack('<I', f.read(4))[0]
        if magic != SESSION_MAGIC:
            if debug:
                print("Wrong magic number")
            return False

        version = struct.unpack('<H', f.read(2))[0]
        if version < 6:
            if debug:
                print(f"Old file version: {version}")
            return False

        filetype = struct.unpack('<H', f.read(2))[0]
        if filetype != FILETYPE_DATA:
            if debug:
                print("Wrong file type")
            return False

        machine_id = struct.unpack('<I', f.read(4))[0]
        session_id = struct.unpack('<I', f.read(4))[0]
        self._first = struct.unpack('<q', f.read(8))[0]
        self._last = struct.unpack('<q', f.read(8))[0]

        if version >= 10:
            comp_method = struct.unpack('<H', f.read(2))[0]
            machine_type = struct.unpack('<H', f.read(2))[0]
            datasize = struct.unpack('<I', f.read(4))[0]
            crc16 = struct.unpack('<H', f.read(2))[0]

            # Handle compression if needed
            if comp_method > 0:
                import zlib
                compressed_data = f.read()
                try:
                    data = zlib.decompress(compressed_data)
                    from io import BytesIO
                    f = BytesIO(data)
                except:
                    if debug:
                        print("Decompression failed")
                    return False

        # Number of channels
        num_channels = struct.unpack('<h', f.read(2))[0]

        # Read metadata for all channels
        channel_order = []
        size_vec = []

        for _ in range(num_channels):
            channel_id = struct.unpack('<I', f.read(4))[0]
            channel_order.append(channel_id)
            num_lists = struct.unpack('<h', f.read(2))[0]
            size_vec.append(num_lists)

            for _ in range(num_lists):
                ts1 = struct.unpack('<q', f.read(8))[0]
                ts2 = struct.unpack('<q', f.read(8))[0]
                evcount = struct.unpack('<i', f.read(4))[0]
                event_type = EventListType(struct.unpack('<b', f.read(1))[0])
                rate = struct.unpack('<f', f.read(4))[0]
                gain = struct.unpack('<f', f.read(4))[0]
                offset = struct.unpack('<f', f.read(4))[0]
                mn = struct.unpack('<f', f.read(4))[0]
                mx = struct.unpack('<f', f.read(4))[0]

                # Dimension string
                dim_len = struct.unpack('<I', f.read(4))[0]
                dimension = f.read(dim_len).decode('utf-8')

                # Second field flag
                second_field = struct.unpack('<B', f.read(1))[0] != 0

                # Create event list
                evlist = self.add_event_list(
                    channel_id, event_type, gain, offset, mn, mx, rate, second_field
                )
                evlist.dimension = dimension
                evlist._count = evcount
                evlist._first = ts1
                evlist._last = ts2

                if second_field:
                    evlist._min2 = struct.unpack('<f', f.read(4))[0]
                    evlist._max2 = struct.unpack('<f', f.read(4))[0]

        # Read data arrays
        for i, channel_id in enumerate(channel_order):
            num_lists = size_vec[i]
            evlists = self._eventlist.get(channel_id, [])

            for j in range(num_lists):
                evlist = evlists[j]
                count = evlist._count

                # Data array
                data_bytes = f.read(count * 2)
                evlist._data = np.frombuffer(data_bytes, dtype=np.int16).copy()

                # Second field
                if evlist.has_second_field:
                    data2_bytes = f.read(count * 2)
                    evlist._data2 = np.frombuffer(data2_bytes, dtype=np.int16).copy()

                # Time deltas for events
                if evlist.type != EventListType.EVL_Waveform:
                    time_bytes = f.read(count * 4)
                    evlist._time = np.frombuffer(time_bytes, dtype=np.uint32).copy()

        self._events_loaded = True
        return True

    def save(self, path: str = "") -> bool:
        """Save this session to disk.

        Args:
            path: Optional path override

        Returns:
            True on success
        """
        if path:
            return self.store(path)
        return self.store(self._machine.get_data_path())

    @classmethod
    def load(cls, machine: 'Machine', session_id: SessionID, load_events: bool = False) -> Optional['Session']:
        """Load a session from disk.

        Args:
            machine: The machine this session belongs to
            session_id: Session ID to load
            load_events: Whether to load event data

        Returns:
            Session instance or None on error
        """
        session = cls(machine, session_id)
        if not session.load_summary():
            return None

        if load_events:
            session.load_events()

        return session

    def __repr__(self) -> str:
        """Return string representation."""
        start = datetime.fromtimestamp(self._first / 1000) if self._first else None
        return (
            f"Session(id={self._session_id}, "
            f"start={start}, "
            f"hours={self.hours():.2f}, "
            f"channels={len(self._eventlist)})"
        )
