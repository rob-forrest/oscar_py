"""
ResMed Data Loader - Python Port

This module provides the ResMed data loader for importing data from
ResMed CPAP devices (S9, AirSense 10/11, AirCurve 10/11).

Copyright (c) 2019-2025 The OSCAR Team
License: GPL v3

File types parsed:
- BRP.edf - High-resolution: Flow Rate, Mask Pressure, Resp Events
- PLD.edf - Low-resolution: Pressure, Leak, RespRate, MinuteVent, TidalVol
- EVE.edf - Events: Obstructive Apnea, Hypopnea, Central Apnea
- CSL.edf - Cheyne-Stokes Respiration flags
- SAD.edf - Oximetry: SpO2, Pulse Rate

Filename pattern: YYYYMMDD_HHMMSS_TYPE.edf
"""

from __future__ import annotations

import struct
import re
import json
from dataclasses import dataclass, field
from datetime import datetime, date, time, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Callable, Union
from enum import IntEnum
import logging

# Try to import from parent package, fall back to local imports for testing
try:
    from ..machine import Machine, MachineInfo
    from ..session import Session
    from ..event import EventListType
    from ..schema import (
        MachineType, CPAPMode, ChannelID,
        CPAP_FlowRate, CPAP_MaskPressure, CPAP_MaskPressureHi, CPAP_RespEvent,
        CPAP_Pressure, CPAP_IPAP, CPAP_EPAP, CPAP_Leak, CPAP_RespRate,
        CPAP_MinuteVent, CPAP_TidalVolume, CPAP_Snore, CPAP_FLG,
        CPAP_Ti, CPAP_Te, CPAP_IE, CPAP_TgMV,
        CPAP_Obstructive, CPAP_Hypopnea, CPAP_ClearAirway, CPAP_Apnea, CPAP_RERA,
        CPAP_CSR, CPAP_Mode,
        CPAP_PressureMin, CPAP_PressureMax, CPAP_PSMin, CPAP_PSMax,
        CPAP_EPAPLo, CPAP_EPAPHi, CPAP_IPAPLo, CPAP_IPAPHi, CPAP_PS,
        CPAP_RampTime, CPAP_RampPressure,
        OXI_Pulse, OXI_SPO2,
    )
    HAS_SLEEPLIB = True
except ImportError:
    HAS_SLEEPLIB = False
    EventListType = None
    # Define minimal stubs for standalone testing
    MachineType = type('MachineType', (), {'MT_CPAP': 1, 'MT_UNKNOWN': 0})()
    CPAPMode = type('CPAPMode', (), {
        'MODE_UNKNOWN': 0, 'MODE_CPAP': 1, 'MODE_APAP': 2,
        'MODE_BILEVEL_FIXED': 3, 'MODE_BILEVEL_AUTO_FIXED_PS': 4,
        'MODE_BILEVEL_AUTO_VARIABLE_PS': 5, 'MODE_ASV': 6,
        'MODE_ASV_VARIABLE_EPAP': 7, 'MODE_AVAPS': 8,
    })()

    # Channel IDs (from schema.py)
    CPAP_FlowRate = 0x1100
    CPAP_MaskPressure = 0x1101
    CPAP_MaskPressureHi = 0x1102
    CPAP_TidalVolume = 0x1103
    CPAP_Snore = 0x1104
    CPAP_MinuteVent = 0x1105
    CPAP_RespRate = 0x1106
    CPAP_Leak = 0x1108
    CPAP_IE = 0x1109
    CPAP_Te = 0x110A
    CPAP_Ti = 0x110B
    CPAP_Pressure = 0x110C
    CPAP_IPAP = 0x110D
    CPAP_EPAP = 0x110E
    CPAP_PS = 0x110F
    CPAP_RespEvent = 0x1112
    CPAP_FLG = 0x1113
    CPAP_TgMV = 0x1114
    CPAP_CSR = 0x1000
    CPAP_ClearAirway = 0x1001
    CPAP_Obstructive = 0x1002
    CPAP_Hypopnea = 0x1003
    CPAP_Apnea = 0x1004
    CPAP_RERA = 0x1006
    CPAP_Mode = 0x1200
    CPAP_PressureMin = 0x1020
    CPAP_PressureMax = 0x1021
    CPAP_RampTime = 0x1022
    CPAP_RampPressure = 0x1023
    CPAP_IPAPLo = 0x1110
    CPAP_IPAPHi = 0x1111
    CPAP_PSMin = 0x111A
    CPAP_PSMax = 0x111B
    CPAP_EPAPLo = 0x111C
    CPAP_EPAPHi = 0x111D
    OXI_Pulse = 0x1800
    OXI_SPO2 = 0x1801

    # Stub classes for testing
    @dataclass
    class MachineInfo:
        type: int = 1
        loadername: str = "ResMed"
        brand: str = "ResMed"
        model: str = ""
        modelnumber: str = ""
        serial: str = ""
        series: str = ""
        lastimported: Optional[datetime] = None
        version: int = 15
        properties: Dict[str, str] = field(default_factory=dict)

    class Machine:
        def __init__(self, profile=None, machine_id=0):
            self.info = MachineInfo()
            self.sessionlist = {}
            self._id = machine_id

        @property
        def id(self):
            return self._id

        def create_session_id(self):
            return int(datetime.now().timestamp())

        @property
        def type(self):
            return 1  # MT_CPAP

        def get_data_path(self):
            return "/tmp/oscar_data"

        def get_events_path(self):
            return "/tmp/oscar_data/Events"

        def get_summaries_path(self):
            return "/tmp/oscar_data/Summaries"

    class Session:
        """Stub Session class for standalone testing."""
        def __init__(self, machine=None, session_id=0):
            self._machine = machine
            self._session_id = session_id if session_id else int(datetime.now().timestamp())
            self._first = 0  # ms since epoch
            self._last = 0
            self._settings: Dict[int, Any] = {}
            self._eventlist: Dict[int, List[Any]] = {}
            self._changed = False

        @property
        def session_id(self):
            return self._session_id

        @property
        def id(self):
            return self._session_id

        @property
        def machine(self):
            return self._machine

        @property
        def type(self):
            return 1

        @property
        def first(self) -> Optional[datetime]:
            if self._first:
                return datetime.fromtimestamp(self._first / 1000.0)
            return None

        @first.setter
        def first(self, value: Optional[datetime]) -> None:
            if value:
                self._first = int(value.timestamp() * 1000)
            else:
                self._first = 0

        @property
        def last(self) -> Optional[datetime]:
            if self._last:
                return datetime.fromtimestamp(self._last / 1000.0)
            return None

        @last.setter
        def last(self, value: Optional[datetime]) -> None:
            if value:
                self._last = int(value.timestamp() * 1000)
            else:
                self._last = 0

        @property
        def events(self):
            return self._eventlist

        @property
        def settings(self):
            return self._settings

        def update_first(self, time_ms: int) -> None:
            if not self._first or self._first > time_ms:
                self._first = time_ms

        def update_last(self, time_ms: int) -> None:
            if not self._last or self._last < time_ms:
                self._last = time_ms

        def add_event_list(self, channel_id, event_type=None, gain=1.0, offset=0.0,
                          min_val=0.0, max_val=0.0, rate=0.0, second_field=False):
            """Add an event list for the given channel."""
            if channel_id not in self._eventlist:
                self._eventlist[channel_id] = []

            evlist = StubEventList(gain=gain, offset=offset, rate=rate)
            self._eventlist[channel_id].append(evlist)
            return evlist

    class StubEventList:
        """Stub EventList for standalone testing."""
        def __init__(self, gain=1.0, offset=0.0, rate=0.0):
            self.gain = gain
            self.offset = offset
            self.rate = rate
            self._data = []
            self._time = []
            self._first = 0
            self._last = 0
            self.dimension = ""

        @property
        def count(self):
            return len(self._data)

        def add_event(self, time_ms: int, value: float, duration: float = 0.0) -> None:
            self._data.append(value)
            self._time.append(time_ms)
            if not self._first or time_ms < self._first:
                self._first = time_ms
            if not self._last or time_ms > self._last:
                self._last = time_ms

        def add_waveform(self, start_time: int, data: List[int], count: int, duration: int) -> None:
            self._data = list(data[:count])
            self._first = start_time
            self._last = start_time + duration

# Try to import EDF parser if available
try:
    from .edf_parser import EDFParser, EDFSignal, Annotation as EDFAnnotation
    HAS_EDF_PARSER = True
except ImportError:
    EDFParser = None
    EDFSignal = None
    EDFAnnotation = None
    HAS_EDF_PARSER = False

logger = logging.getLogger(__name__)

# Constants
RESMED_DATA_VERSION = 15
RESMED_CLASS_NAME = "ResMed"
DATALOG_FOLDER = "DATALOG"
STR_FILE = "STR.edf"
IDENT_TGT = "Identification.tgt"
IDENT_JSON = "Identification.json"


class EDFType(IntEnum):
    """EDF file types for ResMed data."""
    EDF_UNKNOWN = 0
    EDF_BRP = 1  # High-resolution breathing data
    EDF_PLD = 2  # Low-resolution pressure/leak data
    EDF_SAD = 3  # SpO2/Oximetry data
    EDF_EVE = 4  # Events (apneas, hypopneas)
    EDF_CSL = 5  # Cheyne-Stokes data
    EDF_STR = 6  # Summary/Settings data
    EDF_SA2 = 7  # Additional oximetry data


def lookup_edf_type(filename: str) -> EDFType:
    """Determine EDF file type from filename."""
    name = filename.upper()
    if "_BRP" in name:
        return EDFType.EDF_BRP
    elif "_PLD" in name:
        return EDFType.EDF_PLD
    elif "_SAD" in name:
        return EDFType.EDF_SAD
    elif "_SA2" in name:
        return EDFType.EDF_SA2
    elif "_EVE" in name:
        return EDFType.EDF_EVE
    elif "_CSL" in name:
        return EDFType.EDF_CSL
    elif name.startswith("STR"):
        return EDFType.EDF_STR
    return EDFType.EDF_UNKNOWN


# Channel name mappings - maps signal labels to channel IDs
# Based on setupResMedTranslationMap() in C++
RESMED_SIGNAL_MAP: Dict[int, List[str]] = {
    # BRP file signals
    CPAP_FlowRate: ["Flow", "Flow.40ms"],
    CPAP_MaskPressureHi: ["Mask Pres", "Press.40ms"],
    CPAP_RespEvent: ["Resp Event", "TrigCycEvt.40ms"],

    # PLD file signals
    CPAP_MaskPressure: ["Mask Pres", "MaskPress.2s"],
    CPAP_Pressure: ["Therapy Pres", "Press.2s"],
    CPAP_IPAP: ["Insp Pres", "IPAP", "S.BL.IPAP", "S.S.IPAP"],
    CPAP_EPAP: ["Exp Pres", "EprPress.2s", "EPAP", "S.BL.EPAP", "EPRPress.2s", "S.S.EPAP"],
    CPAP_Leak: ["Leak", "Leck", "Fuites", "Fuite", "Fuga", "Lekk", "Leak.2s"],
    CPAP_RespRate: ["RR", "AF", "FR", "RespRate.2s"],
    CPAP_MinuteVent: ["MV", "VM", "MinVent.2s"],
    CPAP_TidalVolume: ["Vt", "VC", "TidVol.2s"],
    CPAP_IE: ["I:E", "IERatio.2s"],
    CPAP_Snore: ["Snore", "Snore.2s"],
    CPAP_FLG: ["FFL Index", "FlowLim.2s"],
    CPAP_Ti: ["Ti", "B5ITime.2s"],
    CPAP_Te: ["Te", "B5ETime.2s"],
    CPAP_TgMV: ["TgMV", "TgtVent.2s"],

    # Oximetry signals
    OXI_Pulse: ["Pulse", "Puls", "Pouls", "Pols", "Pulse.1s", "Nabiz"],
    OXI_SPO2: ["SpO2", "SpO2.1s"],

    # Event annotations
    CPAP_Obstructive: ["Obstructive apnea"],
    CPAP_Hypopnea: ["Hypopnea"],
    CPAP_Apnea: ["Apnea"],
    CPAP_RERA: ["Arousal"],
    CPAP_ClearAirway: ["Central apnea"],

    # Settings signals
    CPAP_Mode: ["Mode", "Modus", "Funktion", "Mod"],
    CPAP_PressureMax: ["Max Pressure", "Max. Druck", "S.AS.MaxPress", "S.A.MaxPress"],
    CPAP_PressureMin: ["Min Pressure", "Min. Druck", "S.AS.MinPress", "S.A.MinPress"],
}


def match_signal(channel_id: int, label: str) -> bool:
    """Check if a signal label matches a channel ID."""
    if channel_id not in RESMED_SIGNAL_MAP:
        return False
    for name in RESMED_SIGNAL_MAP[channel_id]:
        if label.lower().startswith(name.lower()):
            return True
    return False


def find_channel_for_label(label: str) -> Optional[int]:
    """Find the channel ID for a given signal label."""
    for channel_id, names in RESMED_SIGNAL_MAP.items():
        for name in names:
            if label.lower().startswith(name.lower()):
                return channel_id
    return None


# ============================================================================
# EDF Parser (inline implementation)
# ============================================================================

@dataclass
class EDFHeader:
    """EDF file header information."""
    version: str = ""
    patient_id: str = ""
    recording_id: str = ""
    start_date: date = None
    start_time: time = None
    header_bytes: int = 0
    reserved: str = ""
    num_records: int = 0
    record_duration: float = 0.0  # seconds
    num_signals: int = 0

    @property
    def startdatetime(self) -> Optional[datetime]:
        """Get combined start datetime."""
        if self.start_date and self.start_time:
            return datetime.combine(self.start_date, self.start_time)
        return None


@dataclass
class EDFSignalInternal:
    """EDF signal/channel information (internal implementation)."""
    label: str = ""
    transducer: str = ""
    physical_dimension: str = ""
    physical_minimum: float = 0.0
    physical_maximum: float = 0.0
    digital_minimum: int = 0
    digital_maximum: int = 0
    prefiltering: str = ""
    sample_count: int = 0  # samples per data record
    reserved: str = ""

    # Computed values
    gain: float = 1.0
    offset: float = 0.0

    # Data storage
    data: List[int] = field(default_factory=list)

    def compute_gain_offset(self):
        """Compute gain and offset from physical/digital ranges."""
        digital_range = self.digital_maximum - self.digital_minimum
        if digital_range != 0:
            self.gain = (self.physical_maximum - self.physical_minimum) / digital_range
            self.offset = self.physical_minimum - (self.digital_minimum * self.gain)
        else:
            self.gain = 1.0
            self.offset = 0.0


@dataclass
class EDFAnnotationInternal:
    """EDF+ annotation (internal implementation)."""
    offset: float = 0.0  # seconds from start
    duration: float = 0.0
    text: str = ""


@dataclass
class EDFInfo:
    """Complete EDF file information."""
    filename: str = ""
    header: EDFHeader = field(default_factory=EDFHeader)
    signals: List[EDFSignalInternal] = field(default_factory=list)
    annotations: List[List[EDFAnnotationInternal]] = field(default_factory=list)

    # Convenience properties
    @property
    def startdate(self) -> Optional[int]:
        """Get start date as milliseconds since epoch."""
        dt = self.header.startdatetime
        if dt:
            return int(dt.timestamp() * 1000)
        return None

    @property
    def num_records(self) -> int:
        return self.header.num_records

    @property
    def record_duration_ms(self) -> int:
        """Get record duration in milliseconds."""
        return int(self.header.record_duration * 1000)

    @property
    def serialnumber(self) -> str:
        """Extract serial number from recording ID."""
        # ResMed format: "Device Serial=XXXXXXXXX"
        rec_id = self.header.recording_id
        if "=" in rec_id:
            parts = rec_id.split("=")
            if len(parts) >= 2:
                return parts[1].strip().split()[0]
        return ""

    def lookup_label(self, label: str) -> Optional[EDFSignalInternal]:
        """Find signal by label."""
        for sig in self.signals:
            if sig.label.strip() == label or sig.label.strip().startswith(label):
                return sig
        return None

    def lookup_signal(self, channel_id: int) -> Optional[EDFSignalInternal]:
        """Find signal by channel ID."""
        for sig in self.signals:
            if match_signal(channel_id, sig.label):
                return sig
        return None


def parse_edf(filepath: Path) -> Optional[EDFInfo]:
    """Parse an EDF file and return EDFInfo structure.

    Uses the existing EDFParser from edf_parser.py if available,
    otherwise falls back to inline parsing.
    """
    # Try using the existing EDF parser first
    if HAS_EDF_PARSER and EDFParser is not None:
        try:
            parser = EDFParser(filepath)
            if parser.parse():
                # Convert to our EDFInfo structure
                info = EDFInfo(filename=str(filepath))
                info.header.version = str(parser.header.version)
                info.header.patient_id = parser.header.patient_id
                info.header.recording_id = parser.header.recording_id
                if parser.header.start_datetime:
                    info.header.start_date = parser.header.start_datetime.date()
                    info.header.start_time = parser.header.start_datetime.time()
                info.header.header_bytes = parser.header.num_header_bytes
                info.header.reserved = parser.header.reserved
                info.header.num_records = parser.header.num_data_records
                info.header.record_duration = parser.header.duration_seconds
                info.header.num_signals = parser.header.num_signals

                # Convert signals
                for sig in parser.signals:
                    edf_sig = EDFSignalInternal(
                        label=sig.label,
                        transducer=sig.transducer_type,
                        physical_dimension=sig.physical_dimension,
                        physical_minimum=sig.physical_min,
                        physical_maximum=sig.physical_max,
                        digital_minimum=sig.digital_min,
                        digital_maximum=sig.digital_max,
                        prefiltering=sig.prefiltering,
                        sample_count=sig.samples_per_record,
                        reserved=sig.reserved,
                        data=list(sig.data) if hasattr(sig, 'data') and sig.data is not None else []
                    )
                    edf_sig.compute_gain_offset()
                    info.signals.append(edf_sig)

                # Convert annotations
                for anno_list in parser.annotations:
                    converted_annos = []
                    for anno in anno_list:
                        converted_annos.append(EDFAnnotationInternal(
                            offset=anno.offset,
                            duration=anno.duration if anno.duration >= 0 else 0.0,
                            text=anno.text
                        ))
                    if converted_annos:
                        info.annotations.append(converted_annos)

                return info
        except Exception as e:
            logger.warning(f"EDFParser failed for {filepath}: {e}, falling back to inline parser")

    # Fall back to inline parsing
    try:
        with open(filepath, 'rb') as f:
            return _parse_edf_data(f, str(filepath))
    except Exception as e:
        logger.error(f"Failed to parse EDF file {filepath}: {e}")
        return None


def _parse_edf_data(f, filename: str) -> Optional[EDFInfo]:
    """Internal EDF parsing from file handle."""
    info = EDFInfo(filename=filename)
    header = info.header

    # Read fixed header (256 bytes)
    header.version = f.read(8).decode('ascii', errors='replace').strip()
    header.patient_id = f.read(80).decode('ascii', errors='replace').strip()
    header.recording_id = f.read(80).decode('ascii', errors='replace').strip()

    # Parse date (DD.MM.YY)
    date_str = f.read(8).decode('ascii', errors='replace').strip()
    try:
        day, month, year = map(int, date_str.split('.'))
        # Handle Y2K: years < 85 are 2000s, >= 85 are 1900s
        if year < 85:
            year += 2000
        else:
            year += 1900
        header.start_date = date(year, month, day)
    except (ValueError, AttributeError):
        logger.warning(f"Failed to parse date: {date_str}")
        header.start_date = date(2000, 1, 1)

    # Parse time (HH.MM.SS)
    time_str = f.read(8).decode('ascii', errors='replace').strip()
    try:
        hour, minute, second = map(int, time_str.split('.'))
        header.start_time = time(hour, minute, second)
    except (ValueError, AttributeError):
        logger.warning(f"Failed to parse time: {time_str}")
        header.start_time = time(0, 0, 0)

    header.header_bytes = int(f.read(8).decode('ascii', errors='replace').strip())
    header.reserved = f.read(44).decode('ascii', errors='replace').strip()
    header.num_records = int(f.read(8).decode('ascii', errors='replace').strip())
    header.record_duration = float(f.read(8).decode('ascii', errors='replace').strip())
    header.num_signals = int(f.read(4).decode('ascii', errors='replace').strip())

    ns = header.num_signals
    if ns <= 0 or ns > 256:
        logger.error(f"Invalid number of signals: {ns}")
        return None

    # Read signal headers (ns * 256 bytes total)
    signals = [EDFSignalInternal() for _ in range(ns)]

    # Labels (16 chars each)
    for i in range(ns):
        signals[i].label = f.read(16).decode('ascii', errors='replace').strip()

    # Transducer types (80 chars each)
    for i in range(ns):
        signals[i].transducer = f.read(80).decode('ascii', errors='replace').strip()

    # Physical dimensions (8 chars each)
    for i in range(ns):
        signals[i].physical_dimension = f.read(8).decode('ascii', errors='replace').strip()

    # Physical minimums (8 chars each)
    for i in range(ns):
        try:
            signals[i].physical_minimum = float(f.read(8).decode('ascii', errors='replace').strip())
        except ValueError:
            signals[i].physical_minimum = 0.0

    # Physical maximums (8 chars each)
    for i in range(ns):
        try:
            signals[i].physical_maximum = float(f.read(8).decode('ascii', errors='replace').strip())
        except ValueError:
            signals[i].physical_maximum = 1.0

    # Digital minimums (8 chars each)
    for i in range(ns):
        try:
            signals[i].digital_minimum = int(f.read(8).decode('ascii', errors='replace').strip())
        except ValueError:
            signals[i].digital_minimum = -32768

    # Digital maximums (8 chars each)
    for i in range(ns):
        try:
            signals[i].digital_maximum = int(f.read(8).decode('ascii', errors='replace').strip())
        except ValueError:
            signals[i].digital_maximum = 32767

    # Prefiltering (80 chars each)
    for i in range(ns):
        signals[i].prefiltering = f.read(80).decode('ascii', errors='replace').strip()

    # Sample counts (8 chars each)
    for i in range(ns):
        try:
            signals[i].sample_count = int(f.read(8).decode('ascii', errors='replace').strip())
        except ValueError:
            signals[i].sample_count = 0

    # Reserved (32 chars each)
    for i in range(ns):
        signals[i].reserved = f.read(32).decode('ascii', errors='replace').strip()

    # Compute gain/offset for each signal
    for sig in signals:
        sig.compute_gain_offset()

    info.signals = signals

    # Read data records
    record_size = sum(sig.sample_count * 2 for sig in signals)  # 2 bytes per sample (int16)

    for _ in range(header.num_records):
        record_data = f.read(record_size)
        if len(record_data) < record_size:
            break

        offset = 0
        for sig in signals:
            num_samples = sig.sample_count
            # Check for annotation channel
            if sig.label.startswith("EDF Annotations"):
                # Parse annotations
                ann_data = record_data[offset:offset + num_samples * 2]
                annotations = _parse_annotations(ann_data)
                if annotations:
                    info.annotations.append(annotations)
            else:
                # Regular signal data (16-bit signed integers)
                for j in range(num_samples):
                    idx = offset + j * 2
                    if idx + 2 <= len(record_data):
                        value = struct.unpack('<h', record_data[idx:idx + 2])[0]
                        sig.data.append(value)
            offset += num_samples * 2

    return info


def _parse_annotations(data: bytes) -> List[EDFAnnotation]:
    """Parse EDF+ annotations from raw data."""
    annotations = []

    # Annotations are TAL (Time-stamped Annotation Lists)
    # Format: +onset\x14duration\x14annotation\x14\x00
    # Or: +onset\x14\x14annotation\x14\x00 (no duration)

    try:
        text = data.decode('ascii', errors='replace').rstrip('\x00')
    except:
        return annotations

    # Split by record separator (0x14 0x00 or just 0x00)
    parts = re.split(r'[\x14\x15]', text)

    current_offset = 0.0
    i = 0
    while i < len(parts):
        part = parts[i].strip()
        if not part:
            i += 1
            continue

        # Check if this is a timestamp (+offset or -offset)
        if part.startswith('+') or part.startswith('-'):
            try:
                # May include duration after \x15
                if '\x15' in part:
                    offset_str, dur_str = part.split('\x15', 1)
                    current_offset = float(offset_str)
                    duration = float(dur_str) if dur_str else 0.0
                else:
                    current_offset = float(part)
                    duration = 0.0

                # Next parts until next timestamp are annotation texts
                i += 1
                while i < len(parts) and not (parts[i].startswith('+') or parts[i].startswith('-')):
                    ann_text = parts[i].strip().rstrip('\x00')
                    if ann_text:
                        ann = EDFAnnotationInternal(
                            offset=current_offset,
                            duration=duration,
                            text=ann_text
                        )
                        annotations.append(ann)
                    i += 1
                continue
            except ValueError:
                pass
        i += 1

    return annotations


# ============================================================================
# ResMed Day Data Structure
# ============================================================================

@dataclass
class STRRecord:
    """Summary record from STR.edf file for a single day."""
    date: Optional[date] = None
    maskon: List[int] = field(default_factory=list)  # Timestamps when mask was put on
    maskoff: List[int] = field(default_factory=list)  # Timestamps when mask was removed
    maskevents: int = 0
    maskdur: float = 0.0  # Duration in hours

    # Mode and settings
    mode: int = 0  # CPAPMode
    rms9_mode: int = 0  # Raw ResMed mode value

    # Pressure settings
    set_pressure: float = -1.0
    min_pressure: float = -1.0
    max_pressure: float = -1.0
    epap: float = -1.0
    ipap: float = -1.0
    min_epap: float = -1.0
    max_epap: float = -1.0
    min_ipap: float = -1.0
    max_ipap: float = -1.0
    ps: float = -1.0
    min_ps: float = -1.0
    max_ps: float = -1.0

    # EPR settings
    epr: int = -1
    epr_level: int = -1

    # Ramp settings
    s_RampEnable: int = -1
    s_RampTime: int = -1
    s_RampPressure: float = -1.0

    # Other settings
    s_SmartStart: int = -1
    s_SmartStop: int = -1
    s_ABFilter: int = -1
    s_ClimateControl: int = -1
    s_Mask: int = -1
    s_PtAccess: int = -1
    s_HumEnable: int = -1
    s_HumLevel: int = -1
    s_TempEnable: int = -1
    s_Temp: int = -1
    s_Comfort: int = -1
    s_PtView: int = -1

    # Statistics
    leak50: float = -1.0
    leak95: float = -1.0
    leakmax: float = -1.0
    rr50: float = -1.0
    rr95: float = -1.0
    rrmax: float = -1.0
    mv50: float = -1.0
    mv95: float = -1.0
    mvmax: float = -1.0
    tv50: float = -1.0
    tv95: float = -1.0
    tvmax: float = -1.0
    mp50: float = -1.0
    mp95: float = -1.0
    mpmax: float = -1.0

    # Event indices
    oai: float = 0.0  # Obstructive Apnea Index
    hi: float = 0.0   # Hypopnea Index
    cai: float = 0.0  # Central Apnea Index
    uai: float = 0.0  # Unclassified Apnea Index
    csr: float = 0.0  # Cheyne-Stokes Respiration

    # Session tracking
    sessionid: int = 0


@dataclass
class ResmedDay:
    """Container for a single day's worth of ResMed data files."""
    date: date
    str_record: STRRecord = field(default_factory=STRRecord)

    # File lists - key is filename, value is full path
    files: Dict[str, Path] = field(default_factory=dict)

    @property
    def brp_files(self) -> List[Path]:
        """Get list of BRP (high-res breathing) files."""
        return [p for f, p in self.files.items() if lookup_edf_type(f) == EDFType.EDF_BRP]

    @property
    def pld_files(self) -> List[Path]:
        """Get list of PLD (low-res pressure/leak) files."""
        return [p for f, p in self.files.items() if lookup_edf_type(f) == EDFType.EDF_PLD]

    @property
    def eve_files(self) -> List[Path]:
        """Get list of EVE (event) files."""
        return [p for f, p in self.files.items() if lookup_edf_type(f) == EDFType.EDF_EVE]

    @property
    def csl_files(self) -> List[Path]:
        """Get list of CSL (Cheyne-Stokes) files."""
        return [p for f, p in self.files.items() if lookup_edf_type(f) == EDFType.EDF_CSL]

    @property
    def sad_files(self) -> List[Path]:
        """Get list of SAD (oximetry) files."""
        return [p for f, p in self.files.items()
                if lookup_edf_type(f) in (EDFType.EDF_SAD, EDFType.EDF_SA2)]


# ============================================================================
# Event/Waveform Data Structures
# ============================================================================

@dataclass
class EventData:
    """Container for event data."""
    timestamp: int  # milliseconds since epoch
    value: float
    duration: float = 0.0


@dataclass
class WaveformData:
    """Container for waveform data."""
    channel_id: int
    start_time: int  # milliseconds since epoch
    sample_rate: float  # samples per second
    gain: float = 1.0
    offset: float = 0.0
    data: List[int] = field(default_factory=list)
    unit: str = ""

    @property
    def duration_ms(self) -> int:
        """Get duration in milliseconds."""
        if self.sample_rate > 0:
            return int(len(self.data) / self.sample_rate * 1000)
        return 0


# ============================================================================
# ResMed Loader Class
# ============================================================================

class ResmedLoader:
    """Loader for ResMed CPAP device data.

    Supports S9, AirSense 10/11, and AirCurve 10/11 devices.
    """

    VERSION = RESMED_DATA_VERSION
    LOADER_NAME = RESMED_CLASS_NAME

    def __init__(self):
        """Initialize the ResMed loader."""
        self._resday_list: Dict[date, ResmedDay] = {}
        self._session_count = 0
        self._abort = False
        self._unexpected_messages: set = set()

    @staticmethod
    def detect(path: Path) -> bool:
        """Detect if the given path contains ResMed data.

        Args:
            path: Path to check for ResMed data

        Returns:
            True if ResMed data is detected, False otherwise
        """
        path = Path(path)

        if not path.exists() or not path.is_dir():
            return False

        # Check for DATALOG folder
        datalog = path / DATALOG_FOLDER
        if not datalog.exists():
            return False

        # Check for STR.edf file
        str_file = path / STR_FILE
        str_file_gz = path / (STR_FILE + ".gz")
        if not str_file.exists() and not str_file_gz.exists():
            return False

        return True

    @staticmethod
    def peek_info(path: Path) -> Optional[MachineInfo]:
        """Get device info without performing full import.

        Args:
            path: Path to ResMed data

        Returns:
            MachineInfo if device info could be read, None otherwise
        """
        path = Path(path)

        if not ResmedLoader.detect(path):
            return None

        info = MachineInfo(
            type=1,  # MT_CPAP
            loadername=RESMED_CLASS_NAME,
            brand="ResMed",
            version=RESMED_DATA_VERSION,
        )

        # Try to read Identification.json first (AirSense 11)
        ident_json = path / IDENT_JSON
        if ident_json.exists():
            try:
                with open(ident_json, 'r') as f:
                    ident_data = json.load(f)

                if "FlowGenerator" in ident_data:
                    fg = ident_data["FlowGenerator"]
                    if "IdentificationProfiles" in fg:
                        profiles = fg["IdentificationProfiles"]
                        if "Product" in profiles:
                            product = profiles["Product"]
                            info.serial = product.get("SerialNumber", "")
                            info.modelnumber = product.get("ModelNumber", "")
                            info.model = product.get("ProductDescription", "")

                            # Determine series from model number
                            model_num = int(info.modelnumber) if info.modelnumber.isdigit() else 0
                            if model_num >= 39000:
                                info.series = "AirSense 11"
                            elif model_num >= 37000:
                                info.series = "AirCurve 10"
                            elif model_num >= 36000:
                                info.series = "AirSense 10" if "Sense" in info.model else "S9"
                            else:
                                info.series = "S9"

                return info
            except Exception as e:
                logger.warning(f"Failed to parse {ident_json}: {e}")

        # Fall back to Identification.tgt (S9, AirSense 10)
        ident_tgt = path / IDENT_TGT
        if ident_tgt.exists():
            try:
                with open(ident_tgt, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if not line or not line.startswith('#'):
                            continue

                        # Parse #KEY value format (space separated)
                        # Remove the leading #
                        content = line[1:]
                        parts = content.split(None, 1)  # Split on whitespace, max 2 parts
                        if len(parts) >= 2:
                            key = parts[0].strip()
                            value = parts[1].strip()

                            if key == "SRN":
                                info.serial = value
                            elif key == "PNA":
                                info.model = value.replace("_", " ")
                            elif key == "PCD":
                                info.modelnumber = value

                            # Store all properties
                            info.properties[key] = value

                # Determine series from model name and number
                model_name = info.model.lower()
                model_num = int(info.modelnumber) if info.modelnumber.isdigit() else 0

                if "airsense 11" in model_name or model_num >= 39000:
                    info.series = "AirSense 11"
                elif "aircurve" in model_name:
                    info.series = "AirCurve 10"
                elif "airsense" in model_name or model_num >= 36000:
                    info.series = "AirSense 10"
                else:
                    info.series = "S9"

                return info
            except Exception as e:
                logger.warning(f"Failed to parse {ident_tgt}: {e}")

        return None

    def scan_files(self, path: Path) -> List[ResmedDay]:
        """Scan for ResMed data files and group by date.

        Args:
            path: Path to ResMed data (root or DATALOG folder)

        Returns:
            List of ResmedDay objects, sorted by date
        """
        path = Path(path)
        self._resday_list.clear()

        # Handle both root path and DATALOG path
        if path.name == DATALOG_FOLDER:
            datalog_path = path
        else:
            datalog_path = path / DATALOG_FOLDER

        if not datalog_path.exists():
            logger.error(f"DATALOG folder not found: {datalog_path}")
            return []

        # Collect all EDF files
        edf_files: List[Path] = []

        # Check for files directly in DATALOG (S9 style)
        for f in datalog_path.glob("*.edf"):
            edf_files.append(f)

        # Check for files in year/date subfolders (AirSense 10/11 style)
        for year_dir in datalog_path.iterdir():
            if not year_dir.is_dir():
                continue

            # Check if it's a year folder (4 digits) or date folder (8 digits)
            name = year_dir.name
            if len(name) == 4 and name.isdigit():
                # Year folder - scan subfolders
                for date_dir in year_dir.iterdir():
                    if date_dir.is_dir() and len(date_dir.name) == 8:
                        for f in date_dir.glob("*.edf"):
                            edf_files.append(f)
                    elif date_dir.suffix.lower() == ".edf":
                        edf_files.append(date_dir)
            elif len(name) == 8 and name.isdigit():
                # Date folder directly in DATALOG
                for f in year_dir.glob("*.edf"):
                    edf_files.append(f)

        # Process each EDF file
        for edf_path in edf_files:
            filename = edf_path.name

            # Parse filename: YYYYMMDD_HHMMSS_TYPE.edf
            match = re.match(r'(\d{8})_(\d{6})_(\w+)\.edf', filename, re.IGNORECASE)
            if not match:
                continue

            date_str, time_str, file_type = match.groups()

            try:
                file_date = datetime.strptime(date_str, "%Y%m%d").date()
                file_time = datetime.strptime(time_str, "%H%M%S").time()
                file_datetime = datetime.combine(file_date, file_time)

                # ResMed splits days at noon - sessions before noon belong to previous day
                if file_time.hour < 12:
                    session_date = file_date - timedelta(days=1)
                else:
                    session_date = file_date

            except ValueError:
                logger.warning(f"Failed to parse date/time from filename: {filename}")
                continue

            # Get or create ResmedDay for this date
            if session_date not in self._resday_list:
                self._resday_list[session_date] = ResmedDay(date=session_date)

            resday = self._resday_list[session_date]
            resday.files[filename] = edf_path

        # Sort by date and return as list
        sorted_days = sorted(self._resday_list.values(), key=lambda d: d.date)

        logger.info(f"Found {len(sorted_days)} days of ResMed data with {len(edf_files)} EDF files")

        return sorted_days

    def open(self, path: Path, machine: Machine = None,
             progress_callback: Callable[[str, int, int], None] = None) -> int:
        """Import all ResMed data from the given path.

        Args:
            path: Path to ResMed data
            machine: Machine object to add sessions to (created if None)
            progress_callback: Optional callback for progress updates
                              (message, current, total)

        Returns:
            Number of sessions imported, or -1 on error
        """
        path = Path(path)

        if not self.detect(path):
            logger.error(f"No ResMed data detected at {path}")
            return -1

        # Get machine info
        info = self.peek_info(path)
        if not info or not info.serial:
            logger.error("Could not read device identification")
            return -1

        if machine is None:
            machine = Machine()
            machine.info = info

        # Scan for files
        if progress_callback:
            progress_callback("Scanning files...", 0, 100)

        days = self.scan_files(path)
        if not days:
            logger.warning("No data files found")
            return 0

        # Import each day
        self._session_count = 0
        total_days = len(days)

        for i, resday in enumerate(days):
            if self._abort:
                break

            if progress_callback:
                progress_callback(
                    f"Importing {resday.date}...",
                    i,
                    total_days
                )

            sessions = self._import_day(resday, machine)
            self._session_count += len(sessions)

        if progress_callback:
            progress_callback("Import complete", total_days, total_days)

        logger.info(f"Imported {self._session_count} sessions")
        return self._session_count

    def _import_day(self, resday: ResmedDay, machine: Machine) -> List[Session]:
        """Import data for a single day.

        Args:
            resday: ResmedDay with file list
            machine: Machine to add sessions to

        Returns:
            List of imported sessions
        """
        sessions = []

        if not resday.files:
            return sessions

        # Group files by session (based on timestamps)
        session_groups = self._group_files_by_session(resday)

        for session_start, file_group in session_groups.items():
            session = Session(machine, session_start)
            session.first = datetime.fromtimestamp(session_start)

            # Load each file type
            for filepath in file_group:
                filename = filepath.name
                file_type = lookup_edf_type(filename)

                try:
                    if file_type == EDFType.EDF_BRP:
                        self._load_brp(session, filepath)
                    elif file_type == EDFType.EDF_PLD:
                        self._load_pld(session, filepath)
                    elif file_type == EDFType.EDF_EVE:
                        self._load_eve(session, filepath)
                    elif file_type == EDFType.EDF_CSL:
                        self._load_csl(session, filepath)
                    elif file_type in (EDFType.EDF_SAD, EDFType.EDF_SA2):
                        self._load_sad(session, filepath)
                except Exception as e:
                    logger.error(f"Error loading {filepath}: {e}")

            if session.last is None and session.first:
                session.last = session.first

            sessions.append(session)
            machine.sessionlist[session.session_id] = session

        return sessions

    def _group_files_by_session(self, resday: ResmedDay) -> Dict[int, List[Path]]:
        """Group EDF files into sessions based on timestamps.

        Args:
            resday: ResmedDay with file list

        Returns:
            Dict mapping session start timestamp to list of file paths
        """
        # Extract timestamps from filenames
        file_times: List[Tuple[int, Path]] = []

        for filename, filepath in resday.files.items():
            match = re.match(r'(\d{8})_(\d{6})_', filename)
            if match:
                date_str, time_str = match.groups()
                try:
                    dt = datetime.strptime(f"{date_str}{time_str}", "%Y%m%d%H%M%S")
                    timestamp = int(dt.timestamp())
                    file_times.append((timestamp, filepath))
                except ValueError:
                    continue

        if not file_times:
            return {}

        # Sort by timestamp
        file_times.sort(key=lambda x: x[0])

        # Group files that are within 60 seconds of each other
        groups: Dict[int, List[Path]] = {}
        current_group_start = file_times[0][0]
        groups[current_group_start] = [file_times[0][1]]

        for timestamp, filepath in file_times[1:]:
            # Check if this file belongs to current group (within 60 seconds of group start)
            if timestamp - current_group_start <= 60:
                groups[current_group_start].append(filepath)
            else:
                # Start new group
                current_group_start = timestamp
                groups[current_group_start] = [filepath]

        return groups

    def _load_brp(self, session: Session, filepath: Path) -> bool:
        """Load BRP (high-resolution breathing) file into session.

        Contains: Flow Rate, Mask Pressure, Resp Events
        """
        edf = parse_edf(filepath)
        if not edf:
            return False

        # Calculate total duration
        total_duration_ms = edf.num_records * edf.record_duration_ms if edf.num_records > 0 else 0

        # Update session times
        if edf.startdate:
            session.update_first(edf.startdate)
            if total_duration_ms > 0:
                session.update_last(edf.startdate + total_duration_ms)

        # Process signals
        for sig in edf.signals:
            if sig.label.startswith("EDF Annotations") or sig.label == "Crc16":
                continue

            total_samples = len(sig.data)
            if total_samples <= 0:
                continue

            channel_id = None
            gain = sig.gain
            offset = sig.offset

            if match_signal(CPAP_FlowRate, sig.label):
                channel_id = CPAP_FlowRate
                # Convert L/s to L/min
                gain *= 60.0
            elif match_signal(CPAP_MaskPressureHi, sig.label):
                channel_id = CPAP_MaskPressureHi
            elif match_signal(CPAP_RespEvent, sig.label):
                channel_id = CPAP_RespEvent
            else:
                if sig.label:
                    logger.debug(f"Unknown BRP signal: {sig.label}")
                continue

            if channel_id:
                # Calculate sample rate (ms per sample)
                total_duration_sec = edf.num_records * edf.header.record_duration
                rate_ms = (total_duration_sec * 1000.0) / total_samples if total_samples > 0 else 0

                # Get EventListType - use stub if not available
                evl_type = EventListType.EVL_Waveform if EventListType else 0

                # Create EventList for waveform
                evlist = session.add_event_list(
                    channel_id=channel_id,
                    event_type=evl_type,
                    gain=gain,
                    offset=offset,
                    rate=rate_ms
                )
                evlist.dimension = sig.physical_dimension

                # Add waveform data
                evlist.add_waveform(
                    start_time_ms=edf.startdate,
                    samples=sig.data,
                    duration_ms=total_duration_ms
                )

        return True

    def _load_pld(self, session: Session, filepath: Path) -> bool:
        """Load PLD (low-resolution) file into session.

        Contains: Pressure, Leak, RespRate, MinuteVent, TidalVol, Snore, etc.
        """
        edf = parse_edf(filepath)
        if not edf:
            return False

        # Calculate total duration
        total_duration_ms = edf.num_records * edf.record_duration_ms if edf.num_records > 0 else 0

        # Update session times
        if edf.startdate:
            session.update_first(edf.startdate)
            if total_duration_ms > 0:
                session.update_last(edf.startdate + total_duration_ms)

        # Track duplicate signals
        found_ti = False
        found_te = False

        # Process signals
        for sig in edf.signals:
            if sig.label.startswith("EDF Annotations") or sig.label == "Crc16" or not sig.label:
                continue

            total_samples = len(sig.data)
            if total_samples <= 0:
                continue

            channel_id = None
            gain = sig.gain
            offset = sig.offset

            if match_signal(CPAP_Snore, sig.label):
                channel_id = CPAP_Snore
            elif match_signal(CPAP_Pressure, sig.label):
                channel_id = CPAP_Pressure
            elif match_signal(CPAP_IPAP, sig.label):
                channel_id = CPAP_IPAP
            elif match_signal(CPAP_EPAP, sig.label):
                channel_id = CPAP_EPAP
            elif match_signal(CPAP_MinuteVent, sig.label):
                channel_id = CPAP_MinuteVent
            elif match_signal(CPAP_RespRate, sig.label):
                channel_id = CPAP_RespRate
            elif match_signal(CPAP_TidalVolume, sig.label):
                channel_id = CPAP_TidalVolume
                # Convert L to mL
                gain *= 1000.0
            elif match_signal(CPAP_Leak, sig.label):
                channel_id = CPAP_Leak
                # Convert L/s to L/min
                gain *= 60.0
            elif match_signal(CPAP_FLG, sig.label):
                channel_id = CPAP_FLG
            elif match_signal(CPAP_MaskPressure, sig.label):
                channel_id = CPAP_MaskPressure
            elif match_signal(CPAP_IE, sig.label):
                channel_id = CPAP_IE
                gain /= 100.0
            elif match_signal(CPAP_Ti, sig.label):
                if found_ti:
                    continue  # Skip duplicate
                found_ti = True
                channel_id = CPAP_Ti
            elif match_signal(CPAP_Te, sig.label):
                if found_te:
                    continue  # Skip duplicate
                found_te = True
                channel_id = CPAP_Te
            elif match_signal(CPAP_TgMV, sig.label):
                channel_id = CPAP_TgMV
            else:
                if sig.label:
                    logger.debug(f"Unknown PLD signal: {sig.label}")
                continue

            if channel_id:
                # Calculate sample rate (ms per sample)
                total_duration_sec = edf.num_records * edf.header.record_duration
                rate_ms = (total_duration_sec * 1000.0) / total_samples if total_samples > 0 else 0

                # Get EventListType - use stub if not available
                evl_type = EventListType.EVL_Waveform if EventListType else 0

                # Create EventList for waveform
                evlist = session.add_event_list(
                    channel_id=channel_id,
                    event_type=evl_type,
                    gain=gain,
                    offset=offset,
                    rate=rate_ms
                )
                evlist.dimension = sig.physical_dimension

                # Add waveform data
                evlist.add_waveform(
                    start_time_ms=edf.startdate,
                    samples=sig.data,
                    duration_ms=total_duration_ms
                )

        return True

    def _load_eve(self, session: Session, filepath: Path) -> bool:
        """Load EVE (event) file into session.

        Contains: Obstructive Apnea, Hypopnea, Central Apnea events
        """
        edf = parse_edf(filepath)
        if not edf:
            return False

        # Get EventListType - use stub if not available
        evl_type = EventListType.EVL_Event if EventListType else 1

        # Create event lists for each event type (lazily)
        event_lists: Dict[int, Any] = {}

        def get_event_list(channel_id: int):
            """Get or create an EventList for the given channel."""
            if channel_id not in event_lists:
                evlist = session.add_event_list(
                    channel_id=channel_id,
                    event_type=evl_type,
                    gain=1.0,
                    offset=0.0
                )
                event_lists[channel_id] = evlist
            return event_lists[channel_id]

        # Process annotations
        for ann_list in edf.annotations:
            for ann in ann_list:
                if not ann.text or ann.text == "Recording starts":
                    continue

                # Calculate absolute timestamp
                timestamp = edf.startdate + int(ann.offset * 1000)

                # Duration value (store as raw int16, use gain for physical)
                duration_val = int(ann.duration * 10)  # Store with 0.1s precision

                if match_signal(CPAP_Obstructive, ann.text):
                    evlist = get_event_list(CPAP_Obstructive)
                    evlist.add_event(timestamp, duration_val)
                elif match_signal(CPAP_Hypopnea, ann.text):
                    evlist = get_event_list(CPAP_Hypopnea)
                    evlist.add_event(timestamp, duration_val)
                elif match_signal(CPAP_Apnea, ann.text):
                    evlist = get_event_list(CPAP_Apnea)
                    evlist.add_event(timestamp, duration_val)
                elif match_signal(CPAP_RERA, ann.text):
                    evlist = get_event_list(CPAP_RERA)
                    evlist.add_event(timestamp, duration_val)
                elif match_signal(CPAP_ClearAirway, ann.text):
                    evlist = get_event_list(CPAP_ClearAirway)
                    evlist.add_event(timestamp, duration_val)
                else:
                    logger.debug(f"Unknown EVE annotation: {ann.text}")

        return True

    def _load_csl(self, session: Session, filepath: Path) -> bool:
        """Load CSL (Cheyne-Stokes) file into session.

        Contains: CSR Start/End events
        """
        edf = parse_edf(filepath)
        if not edf:
            return False

        # Get EventListType - use stub if not available
        evl_type = EventListType.EVL_Event if EventListType else 1

        # Create CSR event list lazily
        csr_evlist = None
        csr_start = 0

        # Process annotations
        for ann_list in edf.annotations:
            for ann in ann_list:
                if not ann.text:
                    continue

                timestamp = edf.startdate + int(ann.offset * 1000)

                if ann.text == "CSR Start":
                    csr_start = timestamp
                elif ann.text == "CSR End":
                    if csr_start > 0:
                        duration = (timestamp - csr_start) / 1000.0  # seconds
                        duration_val = int(duration * 10)  # Store with 0.1s precision

                        # Create EventList if not exists
                        if csr_evlist is None:
                            csr_evlist = session.add_event_list(
                                channel_id=CPAP_CSR,
                                event_type=evl_type,
                                gain=0.1,  # To convert back to seconds
                                offset=0.0
                            )

                        csr_evlist.add_event(csr_start, duration_val)
                        csr_start = 0

        return True

    def _load_sad(self, session: Session, filepath: Path) -> bool:
        """Load SAD (oximetry) file into session.

        Contains: SpO2, Pulse Rate
        """
        edf = parse_edf(filepath)
        if not edf:
            return False

        # Calculate total duration
        total_duration_ms = edf.num_records * edf.record_duration_ms if edf.num_records > 0 else 0

        # Update session times
        if edf.startdate:
            session.update_first(edf.startdate)
            if total_duration_ms > 0:
                session.update_last(edf.startdate + total_duration_ms)

        # Process signals
        for sig in edf.signals:
            if sig.label.startswith("EDF Annotations") or sig.label == "Crc16":
                continue

            total_samples = len(sig.data)
            if total_samples <= 0:
                continue

            # Check for valid data (not all -1)
            has_data = any(v != -1 for v in sig.data)
            if not has_data:
                continue

            channel_id = None

            if match_signal(OXI_Pulse, sig.label):
                channel_id = OXI_Pulse
            elif match_signal(OXI_SPO2, sig.label):
                channel_id = OXI_SPO2
            else:
                if sig.label:
                    logger.debug(f"Unknown SAD signal: {sig.label}")
                continue

            if channel_id:
                # Calculate sample rate (ms per sample)
                total_duration_sec = edf.num_records * edf.header.record_duration
                rate_ms = (total_duration_sec * 1000.0) / total_samples if total_samples > 0 else 0

                # Get EventListType - use stub if not available
                evl_type = EventListType.EVL_Waveform if EventListType else 0

                # Create EventList for waveform
                evlist = session.add_event_list(
                    channel_id=channel_id,
                    event_type=evl_type,
                    gain=sig.gain,
                    offset=sig.offset,
                    rate=rate_ms
                )
                evlist.dimension = sig.physical_dimension

                # Add waveform data
                evlist.add_waveform(
                    start_time_ms=edf.startdate,
                    samples=sig.data,
                    duration_ms=total_duration_ms
                )

        return True


# ============================================================================
# Convenience functions for loading
# ============================================================================

def load_brp(session: Session, filepath: Path) -> bool:
    """Load BRP file into session."""
    loader = ResmedLoader()
    return loader._load_brp(session, filepath)


def load_pld(session: Session, filepath: Path) -> bool:
    """Load PLD file into session."""
    loader = ResmedLoader()
    return loader._load_pld(session, filepath)


def load_eve(session: Session, filepath: Path) -> bool:
    """Load EVE file into session."""
    loader = ResmedLoader()
    return loader._load_eve(session, filepath)


def load_csl(session: Session, filepath: Path) -> bool:
    """Load CSL file into session."""
    loader = ResmedLoader()
    return loader._load_csl(session, filepath)


def load_sad(session: Session, filepath: Path) -> bool:
    """Load SAD file into session."""
    loader = ResmedLoader()
    return loader._load_sad(session, filepath)


# ============================================================================
# Main entry point for testing
# ============================================================================

def main():
    """Test the ResMed loader by scanning a DATALOG folder."""
    import sys

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    # Default test path
    test_path = Path("/Users/rforrest/Documents/DATALOG")

    if len(sys.argv) > 1:
        test_path = Path(sys.argv[1])

    # Find parent directory containing DATALOG if we're pointed at DATALOG
    if test_path.name == DATALOG_FOLDER:
        root_path = test_path.parent
    else:
        root_path = test_path

    print(f"\n{'='*60}")
    print(f"ResMed Data Loader Test")
    print(f"{'='*60}")
    print(f"Path: {root_path}")

    # Test detection
    print(f"\n--- Detection ---")
    if not ResmedLoader.detect(root_path):
        # Try with DATALOG as the test path
        if ResmedLoader.detect(test_path.parent if test_path.name == DATALOG_FOLDER else test_path):
            root_path = test_path.parent if test_path.name == DATALOG_FOLDER else test_path
        else:
            print(f"No ResMed data detected at {root_path}")
            print("Looking for DATALOG folder and STR.edf file...")

            # Show what we found
            datalog = root_path / DATALOG_FOLDER
            print(f"  DATALOG exists: {datalog.exists()}")
            str_file = root_path / STR_FILE
            print(f"  STR.edf exists: {str_file.exists()}")
            return

    print(f"ResMed data detected!")

    # Test peek_info
    print(f"\n--- Device Info ---")
    info = ResmedLoader.peek_info(root_path)
    if info:
        print(f"Serial: {info.serial}")
        print(f"Model: {info.model}")
        print(f"Model Number: {info.modelnumber}")
        print(f"Series: {info.series}")
        print(f"Brand: {info.brand}")
    else:
        print("Could not read device info")

    # Test scan_files
    print(f"\n--- Scanning Files ---")
    loader = ResmedLoader()
    days = loader.scan_files(root_path)

    print(f"Found {len(days)} days of data")

    if days:
        # Show first and last few days
        print(f"\nFirst 5 days:")
        for day in days[:5]:
            print(f"  {day.date}: {len(day.files)} files")
            print(f"    BRP: {len(day.brp_files)}, PLD: {len(day.pld_files)}, "
                  f"EVE: {len(day.eve_files)}, CSL: {len(day.csl_files)}, "
                  f"SAD: {len(day.sad_files)}")

        if len(days) > 10:
            print(f"\n  ... {len(days) - 10} more days ...")

        if len(days) > 5:
            print(f"\nLast 5 days:")
            for day in days[-5:]:
                print(f"  {day.date}: {len(day.files)} files")
                print(f"    BRP: {len(day.brp_files)}, PLD: {len(day.pld_files)}, "
                      f"EVE: {len(day.eve_files)}, CSL: {len(day.csl_files)}, "
                      f"SAD: {len(day.sad_files)}")

    # Test importing a single day's data
    if days:
        print(f"\n--- Testing Import of Most Recent Day ---")
        test_day = days[-1]
        print(f"Date: {test_day.date}")

        # Create machine - handle both real and stub Machine classes
        if HAS_SLEEPLIB:
            # Create a minimal mock profile for testing
            class MockProfile:
                def path(self):
                    return "/tmp/test_profile"
            machine = Machine(MockProfile())
        else:
            machine = Machine()

        sessions = loader._import_day(test_day, machine)

        print(f"Imported {len(sessions)} sessions")
        for i, sess in enumerate(sessions):
            print(f"\n  Session {i+1}:")
            print(f"    ID: {sess.session_id}")
            print(f"    Start: {sess.first}")
            print(f"    End: {sess.last}")

            # Display event data using the Session API
            if hasattr(sess, 'events') and sess.events:
                print(f"    Channels: {len(sess.events)}")
                for ch, evlists in sess.events.items():
                    if evlists:
                        total_count = sum(evl.count if hasattr(evl, 'count') else len(evl) for evl in evlists)
                        evl_type = "Waveform" if evlists[0].type == 0 else "Event" if hasattr(evlists[0], 'type') else "Data"
                        print(f"      {hex(ch)}: {total_count} samples ({evl_type})")

    print(f"\n{'='*60}")
    print("Test complete!")


if __name__ == "__main__":
    main()
