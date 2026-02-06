"""
SleepLib Event Loader - Load OSCAR Session Events from Disk

This module provides functionality to load session event data (waveforms,
flags) from OSCAR's stored format (binary event files).

Based on C++ implementation in oscar/SleepLib/session.cpp

Copyright (c) 2019-2025 The OSCAR Team
License: GPL v3
"""

import struct
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging
import numpy as np

from .schema import ChannelID

logger = logging.getLogger(__name__)

# Binary event file constants (from C++ session.h/common.h)
EVENT_MAGIC = 0xC73216AB
FILETYPE_DATA = 1

# Event list types
EVL_Waveform = 0  # Continuous waveform with fixed sample rate
EVL_Event = 1     # Discrete events with timestamps


@dataclass
class EventList:
    """Represents a list of events or waveform samples for a channel.

    For waveforms (EVL_Waveform):
        - data contains raw sample values
        - actual_value = (raw_value * gain) + offset
        - samples are evenly spaced at 'rate' samples per second

    For events (EVL_Event):
        - data contains event values
        - time contains timestamps (ms offset from first)
    """
    channel_id: ChannelID
    event_type: int  # EVL_Waveform or EVL_Event
    first: int  # Start time in ms
    last: int   # End time in ms
    count: int  # Number of samples/events
    rate: float  # Sample rate (samples per second) for waveforms
    gain: float  # Gain multiplier
    offset: float  # Offset to add after gain
    min_val: float  # Minimum value
    max_val: float  # Maximum value
    dimension: str  # Unit string (e.g., "cmH2O", "L/min")

    # Raw data arrays
    data: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.int16))
    data2: Optional[np.ndarray] = None  # Secondary data field
    time: Optional[np.ndarray] = None   # Timestamps for EVL_Event type

    # Secondary min/max (for dual-field data)
    min2: Optional[float] = None
    max2: Optional[float] = None

    def get_values(self) -> np.ndarray:
        """Get actual values with gain and offset applied."""
        return (self.data.astype(np.float64) * self.gain) + self.offset

    def get_times_ms(self) -> np.ndarray:
        """Get timestamps in milliseconds from session start.

        For waveforms, generates evenly spaced times based on rate.
        For events, returns the stored timestamps.
        """
        if self.event_type == EVL_Waveform:
            # Generate times based on sample rate
            if self.rate > 0:
                interval_ms = 1000.0 / self.rate
                return np.arange(self.count) * interval_ms
            return np.zeros(self.count)
        else:
            # Return stored timestamps
            if self.time is not None:
                return self.time.astype(np.float64)
            return np.zeros(self.count)

    def is_waveform(self) -> bool:
        return self.event_type == EVL_Waveform


class QDataStreamReader:
    """Reader for Qt QDataStream binary format."""

    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def read_bytes(self, n: int) -> bytes:
        result = self.data[self.pos:self.pos + n]
        self.pos += n
        return result

    def read_uint8(self) -> int:
        return struct.unpack('<B', self.read_bytes(1))[0]

    def read_int16(self) -> int:
        return struct.unpack('<h', self.read_bytes(2))[0]

    def read_uint16(self) -> int:
        return struct.unpack('<H', self.read_bytes(2))[0]

    def read_int32(self) -> int:
        return struct.unpack('<i', self.read_bytes(4))[0]

    def read_uint32(self) -> int:
        return struct.unpack('<I', self.read_bytes(4))[0]

    def read_int64(self) -> int:
        return struct.unpack('<q', self.read_bytes(8))[0]

    def read_double(self) -> float:
        return struct.unpack('<d', self.read_bytes(8))[0]

    def read_qstring(self) -> str:
        """Read a Qt QString (UTF-16 with 32-bit length prefix)."""
        length = self.read_uint32()
        if length == 0xFFFFFFFF or length == 0:
            return ""
        data = self.read_bytes(length)
        try:
            return data.decode('utf-16-le')
        except:
            return ""

    def read_bool(self) -> bool:
        return self.read_uint8() != 0

    def read_raw(self, n: int) -> bytes:
        """Read raw bytes without interpretation."""
        return self.read_bytes(n)

    def remaining(self) -> int:
        return len(self.data) - self.pos

    def skip(self, n: int):
        self.pos += n


def qt_uncompress(data: bytes) -> bytes:
    """Decompress Qt's qCompress format.

    Qt's qCompress prepends a 4-byte big-endian uncompressed size
    to standard zlib compressed data.
    """
    if len(data) < 4:
        return data

    # First 4 bytes are big-endian uncompressed size
    expected_size = struct.unpack('>I', data[:4])[0]

    # Rest is zlib compressed data
    try:
        decompressed = zlib.decompress(data[4:])
        if len(decompressed) != expected_size:
            logger.warning(f"Decompressed size mismatch: {len(decompressed)} != {expected_size}")
        return decompressed
    except zlib.error as e:
        logger.error(f"Decompression failed: {e}")
        return b''


class EventLoader:
    """Load session event data from OSCAR's binary format."""

    def __init__(self, machine_path: Path):
        """Initialize the EventLoader.

        Args:
            machine_path: Path to the machine's data folder.
        """
        self.machine_path = Path(machine_path)
        self.events_path = self.machine_path / "Events"

    def load_events(self, session_id: int) -> Optional[Dict[ChannelID, List[EventList]]]:
        """Load events for a session.

        Args:
            session_id: The session ID (used to find the .001 file).

        Returns:
            Dictionary mapping channel IDs to lists of EventList objects,
            or None if loading fails.
        """
        hex_id = format(session_id, 'x')
        event_file = self.events_path / f"{hex_id}.001"

        if not event_file.exists():
            logger.debug(f"Event file not found: {event_file}")
            return None

        return self._load_event_file(event_file)

    def _load_event_file(self, filepath: Path) -> Optional[Dict[ChannelID, List[EventList]]]:
        """Load and parse an event file.

        Args:
            filepath: Path to the .001 event file.

        Returns:
            Dictionary mapping channel IDs to EventList objects.
        """
        try:
            with open(filepath, 'rb') as f:
                file_data = f.read()

            if len(file_data) < 32:
                logger.debug(f"Event file too small: {filepath}")
                return None

            # Parse header
            header = QDataStreamReader(file_data[:42])

            magic = header.read_uint32()
            if magic != EVENT_MAGIC:
                logger.debug(f"Invalid magic in {filepath}: {hex(magic)}")
                return None

            version = header.read_uint16()
            if version < 6:
                logger.debug(f"Old event version {version} in {filepath}")
                return None

            filetype = header.read_uint16()
            if filetype != FILETYPE_DATA:
                logger.debug(f"Wrong filetype {filetype} in {filepath}")
                return None

            machine_id = header.read_uint32()
            session_id = header.read_uint32()
            first = header.read_int64()
            last = header.read_int64()

            # Handle version-specific header
            if version < 10:
                data_start = 32
                compmethod = 0
            else:
                compmethod = header.read_uint16()
                machtype = header.read_uint16()
                datasize = header.read_int32()
                crc16 = header.read_uint16()
                data_start = 42

            # Get data portion
            raw_data = file_data[data_start:]

            # Decompress if needed
            if version >= 10 and compmethod > 0:
                data_bytes = qt_uncompress(raw_data)
                if not data_bytes:
                    logger.error(f"Failed to decompress {filepath}")
                    return None
            else:
                data_bytes = raw_data

            # Parse event data
            return self._parse_event_data(data_bytes, version, first, last)

        except Exception as e:
            logger.error(f"Error loading events from {filepath}: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _parse_event_data(
        self,
        data: bytes,
        version: int,
        session_first: int,
        session_last: int
    ) -> Dict[ChannelID, List[EventList]]:
        """Parse the event data section.

        Args:
            data: Decompressed event data bytes.
            version: File format version.
            session_first: Session start time in ms.
            session_last: Session end time in ms.

        Returns:
            Dictionary mapping channel IDs to EventList objects.
        """
        reader = QDataStreamReader(data)
        result: Dict[ChannelID, List[EventList]] = {}

        # Read number of channels
        num_channels = reader.read_int16()

        # First pass: read channel metadata
        channel_info = []  # List of (code, event_lists) tuples

        for i in range(num_channels):
            # Read channel code
            # Note: Qt serializes QHash keys as 32-bit even for quint16
            if version < 8:
                # Old format used QString channel names
                name = reader.read_qstring()
                code = 0  # Would need schema lookup
                logger.warning(f"Old string channel format not fully supported: {name}")
            else:
                code = reader.read_uint32()  # Keys are serialized as 32-bit

            # Number of event lists for this channel
            num_lists = reader.read_int16()

            event_lists = []
            for j in range(num_lists):
                ts1 = reader.read_int64()  # Start time
                ts2 = reader.read_int64()  # End time
                evcount = reader.read_int32()  # Event count
                elt = reader.read_uint8()  # Event list type
                rate = reader.read_double()
                gain = reader.read_double()
                offset = reader.read_double()
                mn = reader.read_double()  # Min
                mx = reader.read_double()  # Max
                dim = reader.read_qstring()  # Dimension/unit

                second_field = False
                min2 = None
                max2 = None
                if version >= 7:
                    second_field = reader.read_bool()

                if second_field:
                    min2 = reader.read_double()
                    max2 = reader.read_double()

                evlist = EventList(
                    channel_id=code,
                    event_type=elt,
                    first=ts1,
                    last=ts2,
                    count=evcount,
                    rate=rate,
                    gain=gain,
                    offset=offset,
                    min_val=mn,
                    max_val=mx,
                    dimension=dim,
                    min2=min2,
                    max2=max2,
                )
                evlist._has_second_field = second_field
                event_lists.append(evlist)

            channel_info.append((code, event_lists))

        # Second pass: read actual data arrays
        for code, event_lists in channel_info:
            for evlist in event_lists:
                # Read primary data (int16 array)
                data_bytes = reader.read_raw(evlist.count * 2)
                evlist.data = np.frombuffer(data_bytes, dtype=np.int16).copy()

                # Read secondary data if present
                if getattr(evlist, '_has_second_field', False):
                    data2_bytes = reader.read_raw(evlist.count * 2)
                    evlist.data2 = np.frombuffer(data2_bytes, dtype=np.int16).copy()

                # Read timestamps for non-waveform types
                if evlist.event_type != EVL_Waveform:
                    time_bytes = reader.read_raw(evlist.count * 4)
                    evlist.time = np.frombuffer(time_bytes, dtype=np.uint32).copy()

            # Add to result
            if code not in result:
                result[code] = []
            result[code].extend(event_lists)

        return result


def load_session_events(machine_path: Path, session_id: int) -> Optional[Dict[ChannelID, List[EventList]]]:
    """Convenience function to load events for a session.

    Args:
        machine_path: Path to the machine's data folder.
        session_id: The session ID.

    Returns:
        Dictionary mapping channel IDs to EventList objects.
    """
    loader = EventLoader(machine_path)
    return loader.load_events(session_id)
