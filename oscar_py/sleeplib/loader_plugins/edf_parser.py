"""
EDF/EDF+ Parser - European Data Format File Parser

This module provides classes for parsing EDF and EDF+ files, commonly used
for storing physiological signals in sleep medicine applications.

Copyright (c) 2019-2025 The OSCAR Team
License: GPL v3

Based on the C++ implementation in OSCAR (edfparser.h/edfparser.cpp)

EDF+ Format Overview:
    - 256-byte fixed header with patient info, recording info, dates
    - Per-signal headers (256 bytes per signal)
    - Data records containing interleaved signal samples

References:
    - EDF specification: https://www.edfplus.info/specs/edf.html
    - EDF+ specification: https://www.edfplus.info/specs/edfplus.html
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Optional, List, Dict
import struct
import numpy as np
import gzip
import logging

logger = logging.getLogger(__name__)

# EDF file extensions
STR_EXT_EDF = ".edf"
STR_EXT_GZ = ".gz"

# Annotation markers (EDF+ specification)
ANNO_SEP = 20        # Separator between annotations (decimal 20)
ANNO_DUR_MARK = 21   # Duration marker (decimal 21)
ANNO_END = 0         # End of annotation (null byte)

# Header sizes
EDF_HEADER_SIZE = 256
EDF_SIGNAL_HEADER_SIZE = 256  # Per signal


class EDFType(Enum):
    """EDF file types used by various loaders (ResMed, SleepStyle, etc.)"""
    EDF_UNKNOWN = auto()
    EDF_BRP = auto()    # Breathing rate/pressure
    EDF_PLD = auto()    # Pressure/leak data
    EDF_SAD = auto()    # SpO2 and other data
    EDF_SA2 = auto()    # Secondary SpO2 data
    EDF_EVE = auto()    # Events
    EDF_CSL = auto()    # Settings/configuration
    EDF_AEV = auto()    # Additional events
    EDF_RT = auto()     # Real-time data


@dataclass
class Annotation:
    """
    Holds annotation text from an EDF+ file.

    Annotations are time-stamped events or markers embedded in EDF+ files.
    They can have an optional duration.

    Attributes:
        offset: Time offset in seconds from the start of the recording
        duration: Duration in seconds (-1.0 if not specified)
        text: Annotation text (UTF-8)
    """
    offset: float
    duration: float = -1.0
    text: str = ""


@dataclass
class EDFSignal:
    """
    Contains information about a single EDF/EDF+ signal channel.

    Each signal in an EDF file has associated metadata describing how to
    interpret the raw digital values as physical measurements.

    Attributes:
        label: Channel name (e.g., "Pressure", "Flow", "SpO2")
        transducer_type: Type of transducer used (usually blank)
        physical_dimension: Units of measurement (e.g., "cmH2O", "L/s")
        physical_min: Minimum physical value
        physical_max: Maximum physical value
        digital_min: Minimum digital value (typically -32768 for int16)
        digital_max: Maximum digital value (typically 32767 for int16)
        prefiltering: Any prefiltering applied (usually blank)
        samples_per_record: Number of samples in each data record
        reserved: Reserved field (32 bytes, usually blank)
        data: NumPy array of raw digital samples (int16)
    """
    label: str = ""
    transducer_type: str = ""
    physical_dimension: str = ""
    physical_min: float = 0.0
    physical_max: float = 0.0
    digital_min: int = -32768
    digital_max: int = 32767
    prefiltering: str = ""
    samples_per_record: int = 0
    reserved: str = ""
    data: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.int16))

    @property
    def gain(self) -> float:
        """
        Calculate the gain factor for digital-to-physical conversion.

        Formula: gain = (physical_max - physical_min) / (digital_max - digital_min)

        Returns:
            The gain multiplier for converting digital values to physical units.
        """
        digital_range = self.digital_max - self.digital_min
        if digital_range == 0:
            return 1.0
        return (self.physical_max - self.physical_min) / digital_range

    @property
    def offset(self) -> float:
        """
        Calculate the offset for digital-to-physical conversion.

        Formula: offset = physical_max - gain * digital_max

        Returns:
            The offset value for converting digital values to physical units.
        """
        return self.physical_max - self.gain * self.digital_max

    def get_physical_data(self) -> np.ndarray:
        """
        Convert digital data to physical values.

        Applies the formula: physical_value = digital_value * gain + offset

        Returns:
            NumPy array of physical values (float64).
        """
        if len(self.data) == 0:
            return np.array([], dtype=np.float64)
        return self.data.astype(np.float64) * self.gain + self.offset

    @property
    def is_annotation(self) -> bool:
        """Check if this signal is an EDF+ Annotations channel."""
        return "annotation" in self.label.lower()

    @property
    def total_samples(self) -> int:
        """Total number of samples in the signal."""
        return len(self.data)

    def __repr__(self) -> str:
        return (f"EDFSignal(label='{self.label}', "
                f"samples={self.total_samples}, "
                f"unit='{self.physical_dimension}')")


@dataclass
class EDFHeader:
    """
    Contains the EDF header information in a Python-friendly format.

    The raw EDF header is 256 bytes of ASCII text with fixed-width fields.
    This class parses those fields into appropriate Python types.

    Attributes:
        version: EDF version (0 for EDF, possibly other for EDF+)
        patient_id: Patient identification string
        recording_id: Recording identification string
        start_datetime: Start date and time of the recording
        num_header_bytes: Total bytes in header (256 + 256*num_signals)
        reserved: Reserved field (44 bytes, "EDF+C" or "EDF+D" for EDF+)
        num_data_records: Number of data records in the file
        duration_seconds: Duration of each data record in seconds
        num_signals: Number of signals in the file
    """
    version: int = 0
    patient_id: str = ""
    recording_id: str = ""
    start_datetime: Optional[datetime] = None
    num_header_bytes: int = 0
    reserved: str = ""
    num_data_records: int = 0
    duration_seconds: float = 0.0
    num_signals: int = 0

    @property
    def is_edfplus(self) -> bool:
        """Check if this is an EDF+ file (vs standard EDF)."""
        return self.reserved.startswith("EDF+")

    @property
    def is_continuous(self) -> bool:
        """Check if this is a continuous EDF+ recording (vs discontinuous)."""
        return not self.reserved.startswith("EDF+D")

    @property
    def total_duration(self) -> float:
        """Total duration of the recording in seconds."""
        return self.duration_seconds * self.num_data_records


class EDFParser:
    """
    Parse EDF/EDF+ files into Python data structures.

    This class handles both standard EDF and EDF+ file formats, including
    support for:
        - Compressed (.edf.gz) files
        - EDF+ annotations
        - Multiple signal channels with different sample rates

    Example Usage:
        parser = EDFParser(Path("/path/to/file.edf"))
        if parser.parse():
            print(f"Patient: {parser.patient_id}")
            print(f"Duration: {parser.duration} seconds")
            for sig in parser.signals:
                print(f"  {sig.label}: {sig.total_samples} samples")

            # Get specific signal
            pressure = parser.get_signal("Pressure")
            if pressure:
                physical_data = pressure.get_physical_data()

    Attributes:
        filepath: Path to the EDF file
        header: Parsed header information
        signals: List of EDFSignal objects
        annotations: List of annotation lists (one per data record)
    """

    def __init__(self, filepath: Path):
        """
        Initialize the EDF parser.

        Args:
            filepath: Path to the EDF file to parse.
        """
        self.filepath = Path(filepath)
        self.header = EDFHeader()
        self.signals: List[EDFSignal] = []
        self.annotations: List[List[Annotation]] = []
        self._signal_lookup: Dict[str, List[EDFSignal]] = {}
        self._raw_data: bytes = b""
        self._parsed = False

    @property
    def patient_id(self) -> str:
        """Patient identification string from the header."""
        return self.header.patient_id

    @property
    def recording_id(self) -> str:
        """Recording identification string from the header."""
        return self.header.recording_id

    @property
    def start_datetime(self) -> Optional[datetime]:
        """Start date and time of the recording."""
        return self.header.start_datetime

    @property
    def duration(self) -> float:
        """Total duration of the recording in seconds."""
        return self.header.total_duration

    @property
    def num_records(self) -> int:
        """Number of data records in the file."""
        return self.header.num_data_records

    @property
    def num_signals(self) -> int:
        """Number of signals in the file."""
        return self.header.num_signals

    @property
    def signal_labels(self) -> List[str]:
        """List of signal labels/names."""
        return [sig.label for sig in self.signals]

    def _read_file(self) -> bool:
        """
        Read the EDF file contents into memory.

        Handles both compressed (.gz) and uncompressed files.

        Returns:
            True if file was read successfully, False otherwise.
        """
        try:
            if not self.filepath.exists():
                logger.error(f"File not found: {self.filepath}")
                return False

            # Handle compressed files
            if str(self.filepath).endswith(STR_EXT_GZ):
                with gzip.open(self.filepath, 'rb') as f:
                    self._raw_data = f.read()
            else:
                with open(self.filepath, 'rb') as f:
                    self._raw_data = f.read()

            if len(self._raw_data) < EDF_HEADER_SIZE:
                logger.error(f"File too short: {self.filepath}")
                return False

            return True

        except Exception as e:
            logger.error(f"Error reading file {self.filepath}: {e}")
            return False

    def _parse_datetime(self, date_str: str) -> Optional[datetime]:
        """
        Parse the EDF datetime string.

        EDF format: "dd.MM.yyHH.mm.ss" (16 characters)
        Note: Years 00-84 are interpreted as 2000-2084,
              years 85-99 are interpreted as 1985-1999.

        Args:
            date_str: The datetime string from the EDF header.

        Returns:
            A datetime object, or None if parsing fails.
        """
        try:
            if len(date_str) < 16:
                return None

            date_part = date_str[:8]   # dd.MM.yy
            time_part = date_str[8:16]  # HH.mm.ss

            day = int(date_part[0:2])
            month = int(date_part[3:5])
            year = int(date_part[6:8])

            hour = int(time_part[0:2])
            minute = int(time_part[3:5])
            second = int(time_part[6:8])

            # Y2K handling: years 85-99 are 1985-1999, others are 2000+
            if year >= 85:
                year += 1900
            else:
                year += 2000

            return datetime(year, month, day, hour, minute, second)

        except (ValueError, IndexError) as e:
            logger.warning(f"Failed to parse datetime '{date_str}': {e}")
            return None

    def _parse_header(self) -> bool:
        """
        Parse the 256-byte EDF header.

        Returns:
            True if header was parsed successfully, False otherwise.
        """
        try:
            data = self._raw_data[:EDF_HEADER_SIZE]

            # Version (8 bytes)
            version_str = data[0:8].decode('latin-1').strip()
            try:
                self.header.version = int(version_str)
            except ValueError:
                logger.warning(f"Invalid version string: '{version_str}'")
                return False

            # Patient identification (80 bytes)
            self.header.patient_id = data[8:88].decode('latin-1').strip()

            # Recording identification (80 bytes)
            self.header.recording_id = data[88:168].decode('latin-1').strip()

            # Start date/time (16 bytes)
            datetime_str = data[168:184].decode('latin-1')
            self.header.start_datetime = self._parse_datetime(datetime_str)

            # Number of header bytes (8 bytes)
            try:
                self.header.num_header_bytes = int(data[184:192].decode('latin-1').strip())
            except ValueError:
                logger.warning("Invalid header byte count")
                return False

            # Reserved (44 bytes) - "EDF+C" or "EDF+D" for EDF+
            self.header.reserved = data[192:236].decode('latin-1').strip()

            # Number of data records (8 bytes)
            try:
                self.header.num_data_records = int(data[236:244].decode('latin-1').strip())
            except ValueError:
                logger.warning("Invalid data record count")
                return False

            # Duration of each data record in seconds (8 bytes)
            try:
                self.header.duration_seconds = float(data[244:252].decode('latin-1').strip())
            except ValueError:
                logger.warning("Invalid duration")
                return False

            # Number of signals (4 bytes)
            try:
                self.header.num_signals = int(data[252:256].decode('latin-1').strip())
            except ValueError:
                logger.warning("Invalid signal count")
                return False

            # Validate signal count
            if self.header.num_signals < 1 or self.header.num_signals > 256:
                logger.warning(f"Invalid number of signals: {self.header.num_signals}")
                return False

            return True

        except Exception as e:
            logger.error(f"Error parsing header: {e}")
            return False

    def _parse_signal_headers(self) -> bool:
        """
        Parse the signal headers (256 bytes per signal after main header).

        The signal headers are organized as ns (number of signals) values
        for each field, rather than grouping all fields for each signal.

        Returns:
            True if signal headers were parsed successfully, False otherwise.
        """
        try:
            ns = self.header.num_signals
            offset = EDF_HEADER_SIZE

            # Initialize signals
            self.signals = [EDFSignal() for _ in range(ns)]

            # Labels (16 bytes each)
            for i in range(ns):
                label = self._raw_data[offset:offset+16].decode('latin-1').strip()
                self.signals[i].label = label
                # Build lookup dictionary (same label can appear multiple times)
                if label not in self._signal_lookup:
                    self._signal_lookup[label] = []
                self._signal_lookup[label].append(self.signals[i])
                offset += 16

            # Transducer type (80 bytes each)
            for i in range(ns):
                self.signals[i].transducer_type = self._raw_data[offset:offset+80].decode('latin-1').strip()
                offset += 80

            # Physical dimension/units (8 bytes each)
            for i in range(ns):
                self.signals[i].physical_dimension = self._raw_data[offset:offset+8].decode('latin-1').strip()
                offset += 8

            # Physical minimum (8 bytes each)
            for i in range(ns):
                try:
                    self.signals[i].physical_min = float(self._raw_data[offset:offset+8].decode('latin-1').strip())
                except ValueError:
                    self.signals[i].physical_min = 0.0
                offset += 8

            # Physical maximum (8 bytes each)
            for i in range(ns):
                try:
                    self.signals[i].physical_max = float(self._raw_data[offset:offset+8].decode('latin-1').strip())
                except ValueError:
                    self.signals[i].physical_max = 0.0
                offset += 8

            # Digital minimum (8 bytes each)
            for i in range(ns):
                try:
                    self.signals[i].digital_min = int(self._raw_data[offset:offset+8].decode('latin-1').strip())
                except ValueError:
                    self.signals[i].digital_min = -32768
                offset += 8

            # Digital maximum (8 bytes each)
            for i in range(ns):
                try:
                    self.signals[i].digital_max = int(self._raw_data[offset:offset+8].decode('latin-1').strip())
                except ValueError:
                    self.signals[i].digital_max = 32767
                offset += 8

            # Prefiltering (80 bytes each)
            for i in range(ns):
                self.signals[i].prefiltering = self._raw_data[offset:offset+80].decode('latin-1').strip()
                offset += 80

            # Samples per data record (8 bytes each)
            for i in range(ns):
                try:
                    self.signals[i].samples_per_record = int(self._raw_data[offset:offset+8].decode('latin-1').strip())
                except ValueError:
                    self.signals[i].samples_per_record = 0
                offset += 8

            # Reserved (32 bytes each)
            for i in range(ns):
                self.signals[i].reserved = self._raw_data[offset:offset+32].decode('latin-1').strip()
                offset += 32

            return True

        except Exception as e:
            logger.error(f"Error parsing signal headers: {e}")
            return False

    def _parse_annotations(self, data: bytes) -> List[Annotation]:
        """
        Parse EDF+ annotations from a data block.

        Annotation format:
            +/-offset[ANNO_DUR_MARK duration][ANNO_SEP text]ANNO_SEP[ANNO_SEP text]...ANNO_END

        Args:
            data: Raw bytes from the annotation signal.

        Returns:
            List of Annotation objects.
        """
        annotations = []
        pos = 0
        data_len = len(data)

        while pos < data_len:
            # Annotations must start with + or -
            if pos >= data_len:
                break

            c = data[pos:pos+1]
            if c not in (b'+', b'-'):
                break

            sign = 1 if c == b'+' else -1
            pos += 1

            # Read offset value
            offset_str = b""
            while pos < data_len:
                c = data[pos:pos+1]
                if c == bytes([ANNO_SEP]) or c == bytes([ANNO_DUR_MARK]):
                    break
                offset_str += c
                pos += 1

            try:
                offset = float(offset_str.decode('latin-1')) * sign
            except ValueError:
                break

            # Check for optional duration
            duration = -1.0
            if pos < data_len and data[pos:pos+1] == bytes([ANNO_DUR_MARK]):
                pos += 1
                dur_str = b""
                while pos < data_len and data[pos:pos+1] != bytes([ANNO_SEP]):
                    dur_str += data[pos:pos+1]
                    pos += 1
                try:
                    duration = float(dur_str.decode('latin-1'))
                except ValueError:
                    pass

            # Read annotation text(s)
            while pos < data_len and data[pos:pos+1] == bytes([ANNO_SEP]):
                pos += 1
                if pos >= data_len or data[pos:pos+1] == bytes([ANNO_END]):
                    break
                if data[pos:pos+1] == bytes([ANNO_SEP]):
                    pos += 1
                    break

                # Collect annotation text
                text_start = pos
                while pos < data_len and data[pos:pos+1] != bytes([ANNO_SEP]):
                    pos += 1

                try:
                    text = data[text_start:pos].decode('utf-8')
                    annotations.append(Annotation(offset=offset, duration=duration, text=text))
                except UnicodeDecodeError:
                    # Try latin-1 as fallback
                    try:
                        text = data[text_start:pos].decode('latin-1')
                        annotations.append(Annotation(offset=offset, duration=duration, text=text))
                    except:
                        pass

            # Skip any trailing null bytes
            while pos < data_len and data[pos:pos+1] == bytes([ANNO_END]):
                pos += 1

        return annotations

    def _parse_signal_data(self) -> bool:
        """
        Parse the signal data records.

        Data records are interleaved: all samples for signal 0 in record 0,
        then all samples for signal 1 in record 0, etc.

        Returns:
            True if data was parsed successfully, False otherwise.
        """
        try:
            ns = self.header.num_signals
            nr = self.header.num_data_records

            if nr <= 0:
                # No data records (header-only file)
                return True

            # Calculate expected data size
            samples_per_record = sum(sig.samples_per_record for sig in self.signals)
            expected_data_size = samples_per_record * nr * 2  # 2 bytes per sample

            data_offset = self.header.num_header_bytes
            available_data = len(self._raw_data) - data_offset

            if expected_data_size > available_data:
                logger.warning(f"File truncated: expected {expected_data_size} bytes, "
                             f"got {available_data} bytes")
                return False

            # Allocate arrays for each signal
            for sig in self.signals:
                if not sig.is_annotation:
                    total_samples = sig.samples_per_record * nr
                    sig.data = np.zeros(total_samples, dtype=np.int16)

            # Parse data records
            pos = data_offset
            for rec_no in range(nr):
                for sig_idx, sig in enumerate(self.signals):
                    num_samples = sig.samples_per_record
                    byte_count = num_samples * 2

                    if sig.is_annotation:
                        # Parse annotations
                        anno_data = self._raw_data[pos:pos+byte_count]
                        record_annotations = self._parse_annotations(anno_data)
                        self.annotations.append(record_annotations)
                    else:
                        # Parse numerical data (little-endian int16)
                        start_sample = rec_no * sig.samples_per_record
                        for j in range(num_samples):
                            if pos + 2 <= len(self._raw_data):
                                value = struct.unpack('<h', self._raw_data[pos:pos+2])[0]
                                sig.data[start_sample + j] = value
                            pos += 2
                            continue
                        pos -= num_samples * 2  # Adjust since we're about to add byte_count

                    pos += byte_count

            return True

        except Exception as e:
            logger.error(f"Error parsing signal data: {e}")
            return False

    def parse(self) -> bool:
        """
        Parse the EDF file.

        This method reads the file, parses the header, signal headers,
        and signal data. After calling this method, the header, signals,
        and annotations attributes will be populated.

        Returns:
            True if parsing was successful, False otherwise.
        """
        if self._parsed:
            return True

        if not self._read_file():
            return False

        if not self._parse_header():
            return False

        if not self._parse_signal_headers():
            return False

        if not self._parse_signal_data():
            return False

        # Clear raw data to free memory
        self._raw_data = b""
        self._parsed = True

        return True

    def get_signal(self, label: str, index: int = 0) -> Optional[EDFSignal]:
        """
        Look up a signal by its label.

        Some EDF files (e.g., ResMed) reuse signal names. Use the index
        parameter to access duplicate labels.

        Args:
            label: The signal label to look up.
            index: Index for duplicate labels (default 0 for first match).

        Returns:
            The EDFSignal object, or None if not found.
        """
        if label in self._signal_lookup:
            signals = self._signal_lookup[label]
            if index < len(signals):
                return signals[index]
        return None

    def get_physical_data(self, signal_index: int) -> Optional[np.ndarray]:
        """
        Get physical data for a signal by index.

        Args:
            signal_index: Index of the signal (0 to num_signals-1).

        Returns:
            NumPy array of physical values, or None if index is invalid.
        """
        if 0 <= signal_index < len(self.signals):
            return self.signals[signal_index].get_physical_data()
        return None

    def get_all_annotations(self) -> List[Annotation]:
        """
        Get all annotations flattened into a single list.

        Returns:
            List of all Annotation objects from all data records.
        """
        all_annos = []
        for record_annos in self.annotations:
            all_annos.extend(record_annos)
        return all_annos

    def get_edf_type(self) -> EDFType:
        """
        Determine the EDF file type based on filename.

        Returns:
            The EDFType enum value.
        """
        name = self.filepath.stem.upper()

        if name.endswith("_BRP"):
            return EDFType.EDF_BRP
        elif name.endswith("_PLD"):
            return EDFType.EDF_PLD
        elif name.endswith("_SAD"):
            return EDFType.EDF_SAD
        elif name.endswith("_SA2"):
            return EDFType.EDF_SA2
        elif name.endswith("_EVE"):
            return EDFType.EDF_EVE
        elif name.endswith("_CSL"):
            return EDFType.EDF_CSL
        elif name.endswith("_AEV"):
            return EDFType.EDF_AEV
        elif name.endswith("_RT"):
            return EDFType.EDF_RT
        else:
            return EDFType.EDF_UNKNOWN

    def __repr__(self) -> str:
        if not self._parsed:
            return f"EDFParser(filepath='{self.filepath}', parsed=False)"
        return (f"EDFParser(filepath='{self.filepath}', "
                f"signals={self.num_signals}, "
                f"records={self.num_records}, "
                f"duration={self.duration:.1f}s)")


def print_edf_info(filepath: Path) -> None:
    """
    Utility function to print EDF file information.

    Args:
        filepath: Path to the EDF file.
    """
    parser = EDFParser(filepath)

    if not parser.parse():
        print(f"Failed to parse: {filepath}")
        return

    print(f"\n{'='*60}")
    print(f"EDF File: {filepath.name}")
    print(f"{'='*60}")
    print(f"EDF Type: {parser.get_edf_type().name}")
    print(f"Patient ID: {parser.patient_id}")
    print(f"Recording ID: {parser.recording_id}")
    print(f"Start Time: {parser.start_datetime}")
    print(f"Duration: {parser.duration:.2f} seconds ({parser.duration/60:.2f} minutes)")
    print(f"Data Records: {parser.num_records}")
    print(f"Record Duration: {parser.header.duration_seconds} seconds")
    print(f"Number of Signals: {parser.num_signals}")
    print(f"EDF+ Format: {parser.header.is_edfplus}")

    print(f"\nSignals:")
    print(f"{'-'*60}")
    for i, sig in enumerate(parser.signals):
        print(f"  [{i}] {sig.label}")
        print(f"      Samples/record: {sig.samples_per_record}")
        print(f"      Total samples: {sig.total_samples}")
        print(f"      Physical range: {sig.physical_min} to {sig.physical_max} {sig.physical_dimension}")
        print(f"      Digital range: {sig.digital_min} to {sig.digital_max}")
        print(f"      Gain: {sig.gain:.6f}, Offset: {sig.offset:.6f}")

        # Show data statistics if not annotation
        if not sig.is_annotation and sig.total_samples > 0:
            phys_data = sig.get_physical_data()
            print(f"      Data stats: min={phys_data.min():.4f}, "
                  f"max={phys_data.max():.4f}, mean={phys_data.mean():.4f}")

    # Print annotations if present
    all_annos = parser.get_all_annotations()
    if all_annos:
        print(f"\nAnnotations ({len(all_annos)}):")
        print(f"{'-'*60}")
        for anno in all_annos[:10]:  # Show first 10
            dur_str = f" (dur: {anno.duration}s)" if anno.duration >= 0 else ""
            print(f"  @{anno.offset:.3f}s{dur_str}: {anno.text}")
        if len(all_annos) > 10:
            print(f"  ... and {len(all_annos) - 10} more")


# Test the parser if run directly
if __name__ == "__main__":
    import sys

    # Default test file
    test_dir = Path("/Users/rforrest/Documents/DATALOG/2025/")

    if len(sys.argv) > 1:
        # Use provided file
        test_file = Path(sys.argv[1])
        if test_file.exists():
            print_edf_info(test_file)
        else:
            print(f"File not found: {test_file}")
    else:
        # Test with sample files from test directory
        if test_dir.exists():
            edf_files = list(test_dir.glob("*.edf"))[:5]  # First 5 files
            if edf_files:
                for edf_file in edf_files:
                    print_edf_info(edf_file)
            else:
                print(f"No EDF files found in {test_dir}")
        else:
            print(f"Test directory not found: {test_dir}")
            print("Usage: python edf_parser.py [path/to/file.edf]")
