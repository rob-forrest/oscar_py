"""
SleepLib Summary Loader - Load OSCAR Session Summaries from Disk

This module provides functionality to load session summary data from
OSCAR's stored format (XML index + binary summary files).

Based on C++ implementation in oscar/SleepLib/session.cpp

Copyright (c) 2019-2025 The OSCAR Team
License: GPL v3
"""

import gzip
import struct
import xml.etree.ElementTree as ET
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, BinaryIO
import logging

from .schema import (
    MachineType, ChannelID,
    CPAP_FlowRate, CPAP_MaskPressure, CPAP_Leak, CPAP_RespRate,
    CPAP_Obstructive, CPAP_ClearAirway, CPAP_Hypopnea, CPAP_RERA,
    CPAP_Pressure, CPAP_AHI, CPAP_TidalVolume, CPAP_MinuteVent,
)
from .session import Session
from .machine import Day

logger = logging.getLogger(__name__)

# Binary summary file constants (from C++ session.h)
SUMMARY_MAGIC = 0xC73216AB
SUMMARY_VERSION = 18
FILETYPE_SUMMARY = 0


class QDataStreamReader:
    """Reader for Qt QDataStream binary format (Qt 4.6, Little Endian).

    This implements reading of Qt's serialized data structures.
    """

    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def read_bytes(self, n: int) -> bytes:
        """Read n raw bytes."""
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

    def read_uint64(self) -> int:
        return struct.unpack('<Q', self.read_bytes(8))[0]

    def read_double(self) -> float:
        return struct.unpack('<d', self.read_bytes(8))[0]

    def read_float(self) -> float:
        return struct.unpack('<f', self.read_bytes(4))[0]

    def read_qstring(self) -> str:
        """Read a Qt QString (stored as UTF-16 with 32-bit length prefix)."""
        length = self.read_uint32()
        if length == 0xFFFFFFFF:  # Null string marker
            return ""
        if length == 0:
            return ""
        # QString stores length in bytes (UTF-16 = 2 bytes per char)
        data = self.read_bytes(length)
        try:
            return data.decode('utf-16-le')
        except:
            return ""

    def read_qhash_int_double(self) -> Dict[int, float]:
        """Read QHash<int, double> (used for m_cnt, m_avg, etc.).

        Note: Qt serializes QHash keys as 32-bit even when declared as quint16.
        """
        result = {}
        count = self.read_uint32()
        for _ in range(count):
            key = self.read_uint32()  # Keys are serialized as 32-bit in Qt QHash
            value = self.read_double()  # EventDataType is double
            result[key] = value
        return result

    def read_qhash_int_variant(self) -> Dict[int, Any]:
        """Read QHash<int, QVariant> (used for settings).

        Note: Qt serializes QHash keys as 32-bit even when declared as quint16.
        """
        result = {}
        count = self.read_uint32()
        for _ in range(count):
            key = self.read_uint32()  # Keys are serialized as 32-bit in Qt QHash
            value = self.read_qvariant()
            result[key] = value
        return result

    def read_qvariant(self) -> Any:
        """Read a QVariant value.

        Note: Some OSCAR files use type ID 135 (0x87) for double values,
        possibly due to Qt version differences or custom type registration.
        """
        type_id = self.read_uint32()
        is_null = self.read_uint8()

        if is_null:
            return None

        # QVariant type IDs (from Qt)
        if type_id == 0:  # Invalid
            return None
        elif type_id == 1:  # Bool
            return self.read_uint8() != 0
        elif type_id == 2:  # Int
            return self.read_int32()
        elif type_id == 3:  # UInt
            return self.read_uint32()
        elif type_id == 4:  # LongLong
            return self.read_int64()
        elif type_id == 5:  # ULongLong
            return self.read_uint64()
        elif type_id == 6:  # Double
            return self.read_double()
        elif type_id == 10:  # QString
            return self.read_qstring()
        elif type_id == 38:  # Float
            return self.read_float()
        elif type_id == 135:  # OSCAR-specific: appears to be double
            return self.read_double()
        else:
            # Unknown type - try to skip
            logger.debug(f"Unknown QVariant type: {type_id}")
            return None

    def read_qlist_slice(self) -> List[Tuple[int, int, int]]:
        """Read QVector<SessionSlice>."""
        result = []
        count = self.read_uint32()
        for _ in range(count):
            start = self.read_int64()
            length = self.read_uint32()
            status = self.read_uint16()
            result.append((start, start + length, status))
        return result

    def remaining(self) -> int:
        """Return remaining bytes."""
        return len(self.data) - self.pos

    def skip(self, n: int):
        """Skip n bytes."""
        self.pos += n


class SummaryLoader:
    """Load session summary data from OSCAR's stored format."""

    def __init__(self, machine_path: Path):
        """Initialize the SummaryLoader.

        Args:
            machine_path: Path to the machine's data folder.
        """
        self.machine_path = Path(machine_path)
        self._sessions: Dict[int, Dict[str, Any]] = {}

    def load_session_index(self) -> int:
        """Load session index from Summaries.xml.gz.

        Returns:
            Number of sessions loaded.
        """
        xml_path = self.machine_path / "Summaries.xml.gz"
        if not xml_path.exists():
            logger.warning(f"Session index not found: {xml_path}")
            return 0

        try:
            with gzip.open(xml_path, 'rt', encoding='utf-8') as f:
                tree = ET.parse(f)
                root = tree.getroot()

            for session_elem in root.findall('session'):
                session_id = int(session_elem.get('id', 0))
                if session_id == 0:
                    continue

                self._sessions[session_id] = {
                    'id': session_id,
                    'first': int(session_elem.get('first', 0)),
                    'last': int(session_elem.get('last', 0)),
                    'enabled': session_elem.get('enabled', '1') == '1',
                    'events': session_elem.get('events', '0') == '1',
                    'channels': self._parse_channels(session_elem.find('channels')),
                    'settings_channels': self._parse_channels(session_elem.find('settings')),
                }

            logger.info(f"Loaded {len(self._sessions)} sessions from index")
            return len(self._sessions)

        except Exception as e:
            logger.error(f"Error loading session index: {e}")
            return 0

    def _parse_channels(self, elem: Optional[ET.Element]) -> List[int]:
        """Parse comma-separated channel IDs from hex."""
        if elem is None or elem.text is None:
            return []
        try:
            return [int(ch, 16) for ch in elem.text.split(',')]
        except ValueError:
            return []

    def load_session_summaries(self, profile, day_split_hour: int = 12) -> int:
        """Load binary summary data for all sessions.

        Args:
            profile: The Profile object to populate with days/sessions.
            day_split_hour: Hour at which day boundary occurs (default 12 = noon).

        Returns:
            Number of sessions loaded with summary data.
        """
        summaries_dir = self.machine_path / "Summaries"
        if not summaries_dir.exists():
            logger.warning(f"Summaries directory not found: {summaries_dir}")
            return 0

        loaded = 0
        for session_id, session_info in self._sessions.items():
            # Find the summary file
            hex_id = format(session_id, 'x')
            summary_file = summaries_dir / f"{hex_id}.000"

            if summary_file.exists():
                summary_data = self._load_binary_summary(summary_file)
                if summary_data:
                    session_info['summary'] = summary_data
                    loaded += 1

            # Create session and add to profile
            self._create_session(profile, session_info, day_split_hour)

        logger.info(f"Loaded {loaded} session summaries from binary files")
        return loaded

    def _load_binary_summary(self, filepath: Path) -> Optional[Dict[str, Any]]:
        """Load binary summary data from a .000 file.

        Format (from C++ Session::StoreSummary):
        - magic: quint32 (0xC73216AB)
        - version: quint16
        - filetype: quint16
        - machine_id: quint32
        - session_id: quint32
        - first: qint64 (ms)
        - last: qint64 (ms)
        - settings: QHash<ChannelID, QVariant>
        - m_cnt: QHash<ChannelID, EventDataType>
        - m_sum, m_avg, m_wavg, m_min, m_max, etc.

        Args:
            filepath: Path to the .000 file.

        Returns:
            Dictionary of parsed summary data, or None on error.
        """
        try:
            with open(filepath, 'rb') as f:
                data = f.read()

            if len(data) < 32:
                return None

            reader = QDataStreamReader(data)

            # Read header
            magic = reader.read_uint32()
            if magic != SUMMARY_MAGIC:
                logger.debug(f"Invalid magic in {filepath}: {hex(magic)}")
                return None

            version = reader.read_uint16()
            if version < 6:
                logger.debug(f"Old summary version {version} in {filepath}")
                return None

            filetype = reader.read_uint16()
            if filetype != FILETYPE_SUMMARY:
                logger.debug(f"Wrong filetype {filetype} in {filepath}")
                return None

            machine_id = reader.read_uint32()
            session_id = reader.read_uint32()
            first = reader.read_int64()
            last = reader.read_int64()

            summary = {
                'version': version,
                'machine_id': machine_id,
                'session_id': session_id,
                'first': first,
                'last': last,
                'settings': {},
                'cnt': {},
                'sum': {},
                'avg': {},
                'wavg': {},
                'min': {},
                'max': {},
                'physmin': {},
                'physmax': {},
                'cph': {},
                'sph': {},
            }

            # Read QHash data structures
            try:
                summary['settings'] = reader.read_qhash_int_variant()
                summary['cnt'] = reader.read_qhash_int_double()
                summary['sum'] = reader.read_qhash_int_double()
                summary['avg'] = reader.read_qhash_int_double()
                summary['wavg'] = reader.read_qhash_int_double()
                summary['min'] = reader.read_qhash_int_double()
                summary['max'] = reader.read_qhash_int_double()
                summary['physmin'] = reader.read_qhash_int_double()
                summary['physmax'] = reader.read_qhash_int_double()
                summary['cph'] = reader.read_qhash_int_double()
                summary['sph'] = reader.read_qhash_int_double()

                if version >= 8:
                    summary['firstchan'] = reader.read_qhash_int_double()
                    summary['lastchan'] = reader.read_qhash_int_double()

            except Exception as e:
                logger.debug(f"Error parsing summary data in {filepath}: {e}")
                # Return what we have so far
                pass

            return summary

        except Exception as e:
            logger.debug(f"Error loading summary {filepath}: {e}")
            return None

    def _create_session(
        self,
        profile,
        session_info: Dict[str, Any],
        day_split_hour: int = 12
    ) -> Optional[Session]:
        """Create a Session object and add it to the profile.

        Args:
            profile: The Profile object.
            session_info: Session metadata and summary data.
            day_split_hour: Hour for day boundary.

        Returns:
            The created Session, or None.
        """
        if not session_info.get('enabled', True):
            return None

        first_ms = session_info.get('first', 0)
        last_ms = session_info.get('last', 0)

        # Get from binary summary if available
        summary = session_info.get('summary', {})
        if summary:
            first_ms = summary.get('first', first_ms)
            last_ms = summary.get('last', last_ms)

        if first_ms == 0 or last_ms == 0:
            return None

        # Calculate the day this session belongs to
        session_dt = datetime.fromtimestamp(first_ms / 1000)

        # If session starts before split time, it belongs to previous day
        if session_dt.hour < day_split_hour:
            session_date = session_dt.date() - timedelta(days=1)
        else:
            session_date = session_dt.date()

        # Create session
        session = Session.__new__(Session)
        session._session_id = session_info['id']
        session._first = first_ms
        session._last = last_ms
        session._enabled = session_info.get('enabled', True)
        session._slices = []
        session._eventlist = {}

        # Initialize stat caches from summary
        session._cnt = {}
        session._avg = {}
        session._min = {}
        session._max = {}
        session._sum = {}
        session._cph = {}

        if summary:
            # Copy data from summary
            session._cnt = {int(k): int(v) for k, v in summary.get('cnt', {}).items()}
            session._avg = {int(k): float(v) for k, v in summary.get('avg', {}).items()}
            session._min = {int(k): float(v) for k, v in summary.get('min', {}).items()}
            session._max = {int(k): float(v) for k, v in summary.get('max', {}).items()}
            session._sum = {int(k): float(v) for k, v in summary.get('sum', {}).items()}
            session._cph = {int(k): float(v) for k, v in summary.get('cph', {}).items()}

        # Store machine path for event loading
        session._machine_path = self.machine_path

        # Create mock machine reference
        class MachineRef:
            type = MachineType.MT_CPAP
        session._machine = MachineRef()

        # Event loading state
        session._events_loaded = False

        # Add methods (closures capture session)
        def make_hours(s):
            def hours():
                return (s._last - s._first) / 3600000.0
            return hours
        session.hours = make_hours(session)

        def make_count(s):
            def count(channel_id):
                return s._cnt.get(channel_id, 0)
            return count
        session.count = make_count(session)

        def make_avg(s):
            def avg(channel_id):
                return s._avg.get(channel_id, 0.0)
            return avg
        session.avg = make_avg(session)

        def make_min_value(s):
            def min_value(channel_id):
                return s._min.get(channel_id, 0.0)
            return min_value
        session.min_value = make_min_value(session)

        def make_max_value(s):
            def max_value(channel_id):
                return s._max.get(channel_id, 0.0)
            return max_value
        session.max_value = make_max_value(session)

        session.enabled = True

        # Add load_events method
        def make_load_events(s):
            def load_events():
                """Load event data (waveforms, flags) for this session."""
                if s._events_loaded:
                    return True
                if not hasattr(s, '_machine_path') or s._machine_path is None:
                    return False
                from .event_loader import EventLoader
                loader = EventLoader(s._machine_path)
                events = loader.load_events(s._session_id)
                if events:
                    s._eventlist = events
                    s._events_loaded = True
                    return True
                return False
            return load_events
        session.load_events = make_load_events(session)

        # Add get_event_list method
        def make_get_events(s):
            def get_events(channel_id):
                """Get event lists for a channel. Loads events if needed."""
                if not s._events_loaded:
                    s.load_events()
                return s._eventlist.get(channel_id, [])
            return get_events
        session.get_events = make_get_events(session)

        # Add to profile's day
        day = profile.add_day(session_date)
        if not hasattr(day, 'sessions') or day.sessions is None:
            day.sessions = []
        day.sessions.append(session)

        return session

    @property
    def session_count(self) -> int:
        """Return number of sessions in index."""
        return len(self._sessions)

    def get_date_range(self) -> Optional[Tuple[date, date]]:
        """Get the date range of loaded sessions.

        Returns:
            Tuple of (first_date, last_date) or None.
        """
        if not self._sessions:
            return None

        first_ts = min(s['first'] for s in self._sessions.values() if s['first'] > 0)
        last_ts = max(s['last'] for s in self._sessions.values() if s['last'] > 0)

        if first_ts == 0 or last_ts == 0:
            return None

        first_date = datetime.fromtimestamp(first_ts / 1000).date()
        last_date = datetime.fromtimestamp(last_ts / 1000).date()

        return (first_date, last_date)
