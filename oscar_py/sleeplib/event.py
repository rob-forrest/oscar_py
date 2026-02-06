"""
SleepLib Event - Event and Waveform Data Classes

This module provides the EventList class for storing time-series data
with compression, ported from the C++ OSCAR codebase.

Copyright (c) 2019-2025 The OSCAR Team
License: GPL v3
"""

from __future__ import annotations
from enum import IntEnum
from typing import Optional, BinaryIO, List, Union
import struct
import numpy as np

from .schema import EventDataType


class EventListType(IntEnum):
    """Event list types matching C++ EVL_Waveform and EVL_Event."""
    EVL_Waveform = 0  # Continuous sampled data at fixed rate
    EVL_Event = 1     # Discrete timestamped events


# Binary format constants (matching C++ OSCAR format)
EVENTLIST_MAGIC = 0x4556454E  # 'EVEN' in little-endian
EVENTLIST_VERSION = 1


class EventList:
    """Contains waveforms at a specified rate, or a list of event and time data.

    This class stores time-series data efficiently using int16 storage with
    gain/offset conversion, matching the C++ OSCAR implementation.

    For waveforms (EVL_Waveform):
        - Data is sampled at a fixed rate
        - Time is calculated as: first + (index * rate)
        - No separate time storage needed

    For events (EVL_Event):
        - Each event has an explicit timestamp
        - Times stored as delta from first timestamp (uint32)

    Physical value = raw_value * gain + offset

    Attributes:
        type: EventListType (Waveform or Event)
        gain: Multiplier for converting raw to physical values
        offset: Offset added after gain multiplication
        rate: Sample rate in milliseconds per sample (waveforms only)
        dimension: Unit string (e.g., "cmH2O", "L/min")
    """

    def __init__(
        self,
        event_type: EventListType = EventListType.EVL_Event,
        gain: EventDataType = 1.0,
        offset: EventDataType = 0.0,
        min_val: EventDataType = 0.0,
        max_val: EventDataType = 0.0,
        rate: EventDataType = 0.0,
        second_field: bool = False
    ):
        """Initialize an EventList.

        Args:
            event_type: EVL_Waveform or EVL_Event
            gain: Multiplier for raw to physical conversion
            offset: Offset for raw to physical conversion
            min_val: Minimum value (0 means auto-update)
            max_val: Maximum value (0 means auto-update)
            rate: Sample rate in ms (waveforms only)
            second_field: Whether to store a second data field
        """
        self._type = event_type
        self._gain = float(gain)
        self._offset = float(offset)
        self._rate = float(rate)
        self._second_field = second_field
        self._dimension = ""

        # Time boundaries (milliseconds since epoch)
        self._first: int = 0
        self._last: int = 0

        # Data count
        self._count: int = 0

        # Min/max tracking
        if min_val == max_val:
            self._update_minmax = True
            self._min: EventDataType = float('inf')
            self._max: EventDataType = float('-inf')
            self._min2: EventDataType = float('inf')
            self._max2: EventDataType = float('-inf')
        else:
            self._update_minmax = False
            self._min = float(min_val)
            self._max = float(max_val)
            self._min2 = float(min_val)
            self._max2 = float(max_val)

        # Data storage - using numpy for efficiency
        # Raw data stored as int16 (EventStoreType in C++)
        self._data: np.ndarray = np.array([], dtype=np.int16)
        self._data2: np.ndarray = np.array([], dtype=np.int16)

        # Time deltas stored as uint32 (offset from first)
        self._time: np.ndarray = np.array([], dtype=np.uint32)

    def clear(self) -> None:
        """Clear all data and reset to initial state."""
        self._min = float('inf')
        self._max = float('-inf')
        self._min2 = float('inf')
        self._max2 = float('-inf')
        self._update_minmax = True
        self._first = 0
        self._last = 0
        self._count = 0

        self._data = np.array([], dtype=np.int16)
        self._data2 = np.array([], dtype=np.int16)
        self._time = np.array([], dtype=np.uint32)

    # Properties

    @property
    def type(self) -> EventListType:
        """Return the event list type."""
        return self._type

    @type.setter
    def type(self, value: EventListType) -> None:
        """Set the event list type."""
        self._type = value

    @property
    def count(self) -> int:
        """Return the number of events/samples."""
        return self._count

    @count.setter
    def count(self, value: int) -> None:
        """Set the count (use with caution)."""
        self._count = value

    @property
    def duration(self) -> int:
        """Return duration in milliseconds."""
        return self._last - self._first if self._last > self._first else 0

    @property
    def first(self) -> int:
        """Return first timestamp (ms since epoch)."""
        return self._first

    @first.setter
    def first(self, value: int) -> None:
        """Set first timestamp."""
        self._first = value

    @property
    def last(self) -> int:
        """Return last timestamp (ms since epoch)."""
        return self._last

    @last.setter
    def last(self, value: int) -> None:
        """Set last timestamp."""
        self._last = value

    @property
    def min(self) -> EventDataType:
        """Return minimum value."""
        return self._min if self._min != float('inf') else 0.0

    @min.setter
    def min(self, value: EventDataType) -> None:
        """Set minimum value."""
        self._min = float(value)

    @property
    def max(self) -> EventDataType:
        """Return maximum value."""
        return self._max if self._max != float('-inf') else 0.0

    @max.setter
    def max(self, value: EventDataType) -> None:
        """Set maximum value."""
        self._max = float(value)

    @property
    def min2(self) -> EventDataType:
        """Return minimum value for second field."""
        return self._min2 if self._min2 != float('inf') else 0.0

    @min2.setter
    def min2(self, value: EventDataType) -> None:
        """Set minimum value for second field."""
        self._min2 = float(value)

    @property
    def max2(self) -> EventDataType:
        """Return maximum value for second field."""
        return self._max2 if self._max2 != float('-inf') else 0.0

    @max2.setter
    def max2(self, value: EventDataType) -> None:
        """Set maximum value for second field."""
        self._max2 = float(value)

    @property
    def gain(self) -> EventDataType:
        """Return the gain multiplier."""
        return self._gain

    @gain.setter
    def gain(self, value: EventDataType) -> None:
        """Set the gain multiplier."""
        self._gain = float(value)

    @property
    def offset(self) -> EventDataType:
        """Return the offset value."""
        return self._offset

    @offset.setter
    def offset(self, value: EventDataType) -> None:
        """Set the offset value."""
        self._offset = float(value)

    @property
    def rate(self) -> EventDataType:
        """Return the sample rate (ms per sample)."""
        return self._rate

    @rate.setter
    def rate(self, value: EventDataType) -> None:
        """Set the sample rate."""
        self._rate = float(value)

    @property
    def dimension(self) -> str:
        """Return the unit string."""
        return self._dimension

    @dimension.setter
    def dimension(self, value: str) -> None:
        """Set the unit string."""
        self._dimension = value

    @property
    def has_second_field(self) -> bool:
        """Return whether this EventList uses a second data field."""
        return self._second_field

    @property
    def update_minmax(self) -> bool:
        """Return whether min/max are auto-updated."""
        return self._update_minmax

    # Data access methods

    def raw(self, index: int) -> int:
        """Return raw (ungained) value at index."""
        if index < 0 or index >= self._count:
            raise IndexError(f"Index {index} out of range [0, {self._count})")
        return int(self._data[index])

    def raw2(self, index: int) -> int:
        """Return raw (ungained) value from second field at index."""
        if index < 0 or index >= self._count:
            raise IndexError(f"Index {index} out of range [0, {self._count})")
        if not self._second_field:
            raise ValueError("No second field in this EventList")
        return int(self._data2[index])

    def data(self, index: int) -> EventDataType:
        """Return physical value at index (applies gain).

        Physical value = raw * gain

        Args:
            index: Index into the data array

        Returns:
            Physical (gained) value
        """
        if index < 0 or index >= self._count:
            raise IndexError(f"Index {index} out of range [0, {self._count})")
        return float(self._data[index]) * self._gain

    def data2(self, index: int) -> EventDataType:
        """Return physical value from second field at index."""
        if index < 0 or index >= self._count:
            raise IndexError(f"Index {index} out of range [0, {self._count})")
        if not self._second_field:
            raise ValueError("No second field in this EventList")
        return float(self._data2[index])

    def time(self, index: int) -> int:
        """Return timestamp at index (ms since epoch).

        For waveforms: first + (index * rate)
        For events: first + time_delta[index]

        Args:
            index: Index into the data array

        Returns:
            Timestamp in milliseconds since epoch
        """
        if index < 0 or index >= self._count:
            raise IndexError(f"Index {index} out of range [0, {self._count})")

        if self._type == EventListType.EVL_Event:
            return self._first + int(self._time[index])
        else:
            # Waveform: calculate time from index and rate
            return self._first + int(float(index) * self._rate)

    def raw_data(self) -> np.ndarray:
        """Return numpy array of all raw values."""
        return self._data[:self._count].copy()

    def raw_data2(self) -> np.ndarray:
        """Return numpy array of all raw values from second field."""
        if not self._second_field:
            return np.array([], dtype=np.int16)
        return self._data2[:self._count].copy()

    def raw_time(self) -> np.ndarray:
        """Return numpy array of all time deltas (events only)."""
        if self._type != EventListType.EVL_Event:
            return np.array([], dtype=np.uint32)
        return self._time[:self._count].copy()

    def physical_data(self) -> np.ndarray:
        """Return numpy array of all physical (gained) values."""
        return self._data[:self._count].astype(np.float64) * self._gain

    def timestamps(self) -> np.ndarray:
        """Return numpy array of all timestamps (ms since epoch)."""
        if self._type == EventListType.EVL_Event:
            return self._first + self._time[:self._count].astype(np.int64)
        else:
            # Waveform: generate timestamps from rate
            indices = np.arange(self._count, dtype=np.float64)
            return (self._first + indices * self._rate).astype(np.int64)

    # Data addition methods

    def add_event(self, time_ms: int, value: Union[int, float], value2: Optional[Union[int, float]] = None) -> None:
        """Add a discrete event.

        Args:
            time_ms: Timestamp in milliseconds since epoch
            value: Data value (will be stored as int16)
            value2: Optional second data value
        """
        # Convert to raw int16
        raw_value = int(value)
        if raw_value < -32768:
            raw_value = -32768
        elif raw_value > 32767:
            raw_value = 32767

        # Apply gain for physical value (for min/max)
        physical_value = float(raw_value) * self._gain

        # Update min/max
        if self._update_minmax:
            if self._count == 0:
                self._min = self._max = physical_value
            else:
                if physical_value < self._min:
                    self._min = physical_value
                if physical_value > self._max:
                    self._max = physical_value

        # Handle first timestamp
        if self._first == 0:
            self._first = time_ms
            self._last = time_ms

        # Handle out-of-order timestamps
        if self._first > time_ms:
            # Adjust existing time deltas
            delta = self._first - time_ms
            if self._count > 0:
                self._time = self._time + delta
            self._first = time_ms

        if self._last < time_ms:
            self._last = time_ms

        # Calculate time delta
        time_delta = time_ms - self._first
        if time_delta > 0xFFFFFFFF:
            time_delta = 0xFFFFFFFF

        # Append data
        self._data = np.append(self._data, np.int16(raw_value))
        self._time = np.append(self._time, np.uint32(time_delta))
        self._count += 1

        # Handle second field
        if self._second_field and value2 is not None:
            raw_value2 = int(value2)
            if raw_value2 < -32768:
                raw_value2 = -32768
            elif raw_value2 > 32767:
                raw_value2 = 32767

            if raw_value2 < self._min2:
                self._min2 = raw_value2
            if raw_value2 > self._max2:
                self._max2 = raw_value2

            self._data2 = np.append(self._data2, np.int16(raw_value2))

    def add_waveform(
        self,
        start_time_ms: int,
        samples: Union[List[int], np.ndarray],
        duration_ms: Optional[int] = None
    ) -> None:
        """Add waveform data.

        Args:
            start_time_ms: Start timestamp in milliseconds since epoch
            samples: Array of sample values (int16)
            duration_ms: Optional duration in milliseconds (for rate calculation)
        """
        if self._type != EventListType.EVL_Waveform:
            raise ValueError("Cannot add waveform data to non-waveform EventList")

        if self._rate == 0 and duration_ms is None:
            raise ValueError("Sample rate not set and no duration provided")

        samples_array = np.asarray(samples, dtype=np.int16)
        num_samples = len(samples_array)

        if num_samples == 0:
            return

        # Calculate duration
        if duration_ms is not None:
            actual_duration = duration_ms
        else:
            actual_duration = int(num_samples * self._rate)

        end_time = start_time_ms + actual_duration

        # Initialize first/last
        if self._first == 0:
            self._first = start_time_ms
            self._last = end_time

        if self._last < end_time:
            self._last = end_time

        # Store starting index
        start_idx = self._count

        # Resize data array
        self._count += num_samples
        new_data = np.zeros(self._count, dtype=np.int16)
        new_data[:start_idx] = self._data[:start_idx] if start_idx > 0 else []
        new_data[start_idx:] = samples_array
        self._data = new_data

        # Update min/max
        if self._update_minmax:
            physical_values = samples_array.astype(np.float64) * self._gain + self._offset
            sample_min = float(np.min(physical_values))
            sample_max = float(np.max(physical_values))

            if self._min == float('inf') or sample_min < self._min:
                self._min = sample_min
            if self._max == float('-inf') or sample_max > self._max:
                self._max = sample_max

    # Binary I/O

    def save(self, file: BinaryIO) -> bool:
        """Save EventList to binary file.

        Binary format:
            - magic (4 bytes): 0x4556454E
            - version (4 bytes): 1
            - type (1 byte): EventListType
            - first (8 bytes): int64 first timestamp
            - last (8 bytes): int64 last timestamp
            - count (4 bytes): uint32 number of samples
            - gain (4 bytes): float32
            - offset (4 bytes): float32
            - min (4 bytes): float32
            - max (4 bytes): float32
            - rate (4 bytes): float32
            - second_field (1 byte): bool
            - dimension_len (2 bytes): uint16
            - dimension (N bytes): UTF-8 string
            - data (count * 2 bytes): int16 array
            - data2 (count * 2 bytes if second_field): int16 array
            - time (count * 4 bytes if Event type): uint32 array

        Args:
            file: Binary file object for writing

        Returns:
            True on success
        """
        try:
            # Header
            file.write(struct.pack('<I', EVENTLIST_MAGIC))
            file.write(struct.pack('<I', EVENTLIST_VERSION))
            file.write(struct.pack('<B', int(self._type)))
            file.write(struct.pack('<q', self._first))
            file.write(struct.pack('<q', self._last))
            file.write(struct.pack('<I', self._count))
            file.write(struct.pack('<f', self._gain))
            file.write(struct.pack('<f', self._offset))
            file.write(struct.pack('<f', self._min if self._min != float('inf') else 0.0))
            file.write(struct.pack('<f', self._max if self._max != float('-inf') else 0.0))
            file.write(struct.pack('<f', self._rate))
            file.write(struct.pack('<B', 1 if self._second_field else 0))

            # Dimension string
            dim_bytes = self._dimension.encode('utf-8')
            file.write(struct.pack('<H', len(dim_bytes)))
            file.write(dim_bytes)

            # Min2/Max2 if second field
            if self._second_field:
                file.write(struct.pack('<f', self._min2 if self._min2 != float('inf') else 0.0))
                file.write(struct.pack('<f', self._max2 if self._max2 != float('-inf') else 0.0))

            # Data arrays
            file.write(self._data[:self._count].tobytes())

            if self._second_field:
                file.write(self._data2[:self._count].tobytes())

            if self._type == EventListType.EVL_Event:
                file.write(self._time[:self._count].tobytes())

            return True

        except Exception as e:
            print(f"Error saving EventList: {e}")
            return False

    @classmethod
    def load(cls, file: BinaryIO) -> Optional['EventList']:
        """Load EventList from binary file.

        Args:
            file: Binary file object for reading

        Returns:
            EventList instance or None on error
        """
        try:
            # Read and verify magic
            magic_bytes = file.read(4)
            if len(magic_bytes) < 4:
                return None
            magic = struct.unpack('<I', magic_bytes)[0]
            if magic != EVENTLIST_MAGIC:
                return None

            # Read version
            version = struct.unpack('<I', file.read(4))[0]
            if version > EVENTLIST_VERSION:
                print(f"Warning: EventList version {version} newer than supported {EVENTLIST_VERSION}")

            # Read header fields
            event_type = EventListType(struct.unpack('<B', file.read(1))[0])
            first = struct.unpack('<q', file.read(8))[0]
            last = struct.unpack('<q', file.read(8))[0]
            count = struct.unpack('<I', file.read(4))[0]
            gain = struct.unpack('<f', file.read(4))[0]
            offset = struct.unpack('<f', file.read(4))[0]
            min_val = struct.unpack('<f', file.read(4))[0]
            max_val = struct.unpack('<f', file.read(4))[0]
            rate = struct.unpack('<f', file.read(4))[0]
            second_field = struct.unpack('<B', file.read(1))[0] != 0

            # Read dimension string
            dim_len = struct.unpack('<H', file.read(2))[0]
            dimension = file.read(dim_len).decode('utf-8')

            # Create EventList
            evlist = cls(
                event_type=event_type,
                gain=gain,
                offset=offset,
                min_val=min_val,
                max_val=max_val,
                rate=rate,
                second_field=second_field
            )
            evlist._first = first
            evlist._last = last
            evlist._count = count
            evlist._dimension = dimension
            evlist._update_minmax = False

            # Read min2/max2 if second field
            if second_field:
                evlist._min2 = struct.unpack('<f', file.read(4))[0]
                evlist._max2 = struct.unpack('<f', file.read(4))[0]

            # Read data arrays
            if count > 0:
                data_bytes = file.read(count * 2)
                evlist._data = np.frombuffer(data_bytes, dtype=np.int16).copy()

                if second_field:
                    data2_bytes = file.read(count * 2)
                    evlist._data2 = np.frombuffer(data2_bytes, dtype=np.int16).copy()

                if event_type == EventListType.EVL_Event:
                    time_bytes = file.read(count * 4)
                    evlist._time = np.frombuffer(time_bytes, dtype=np.uint32).copy()

            return evlist

        except Exception as e:
            print(f"Error loading EventList: {e}")
            return None

    def __len__(self) -> int:
        """Return the number of data points."""
        return self._count

    def __repr__(self) -> str:
        """Return string representation."""
        type_name = "Waveform" if self._type == EventListType.EVL_Waveform else "Event"
        return (
            f"EventList(type={type_name}, count={self._count}, "
            f"gain={self._gain}, rate={self._rate}, "
            f"min={self.min:.2f}, max={self.max:.2f})"
        )
