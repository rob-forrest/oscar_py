# OSCAR Data Format Documentation

This document describes the binary data formats used by OSCAR for storing
CPAP session data. Based on analysis of oscar/SleepLib/session.cpp.

## Directory Structure

```
OSCAR_Data/
└── Profiles/
    └── {profile_name}/
        ├── Profile.xml           # Profile settings
        ├── machines.xml          # Machine registry
        └── {Loader}_{Serial}/    # Machine data folder (e.g., ResMed_23254434021)
            ├── Summaries.xml.gz  # Session index (gzipped XML)
            ├── Summaries/        # Binary summary files
            │   └── {session_id_hex}.000
            └── Events/           # Binary event/waveform files
                └── {session_id_hex}.001
```

## Common Constants

```python
MAGIC = 0xC73216AB          # Magic number for all binary files
FILETYPE_SUMMARY = 0        # Summary file type
FILETYPE_DATA = 1           # Event/waveform file type
```

## Qt QDataStream Format Notes

OSCAR uses Qt 4.6 QDataStream with Little Endian byte order.

**Important**: Qt serializes QHash keys as 32-bit even when declared as uint16.
This affects both summary and event files.

---

## Summary File Format (.000)

Summary files contain aggregated statistics for a session (counts, averages,
min/max values) without the actual waveform data.

### Header (32 bytes)

| Offset | Type    | Field       | Description |
|--------|---------|-------------|-------------|
| 0      | uint32  | magic       | 0xC73216AB |
| 4      | uint16  | version     | Format version (current: 18) |
| 6      | uint16  | filetype    | 0 = summary |
| 8      | uint32  | machine_id  | Machine identifier |
| 12     | uint32  | session_id  | Session ID (Unix timestamp) |
| 16     | int64   | first       | Start time (milliseconds since epoch) |
| 24     | int64   | last        | End time (milliseconds since epoch) |

### Data Section

After the header, the following QHash structures are stored sequentially:

```
settings    QHash<ChannelID, QVariant>   Session settings
m_cnt       QHash<ChannelID, double>     Event counts per channel
m_sum       QHash<ChannelID, double>     Sum of values
m_avg       QHash<ChannelID, double>     Average values
m_wavg      QHash<ChannelID, double>     Weighted averages
m_min       QHash<ChannelID, double>     Minimum values
m_max       QHash<ChannelID, double>     Maximum values
m_physmin   QHash<ChannelID, double>     Physical minimum
m_physmax   QHash<ChannelID, double>     Physical maximum
m_cph       QHash<ChannelID, double>     Counts per hour
m_sph       QHash<ChannelID, double>     Seconds per hour
```

For version >= 8:
```
m_firstchan QHash<ChannelID, double>     First timestamp per channel
m_lastchan  QHash<ChannelID, double>     Last timestamp per channel
```

### QHash<ChannelID, double> Format

```
count       uint32              Number of entries
entries     (key, value)[]      Repeated count times
  key       uint32              Channel ID (stored as 32-bit!)
  value     double              IEEE 754 double (8 bytes)
```

### QHash<ChannelID, QVariant> Format

```
count       uint32              Number of entries
entries     (key, variant)[]    Repeated count times
  key       uint32              Channel ID (stored as 32-bit!)
  variant   QVariant            Qt variant value
```

### QVariant Format

```
type_id     uint32              Qt metatype ID
is_null     uint8               1 if null, 0 otherwise
value       varies              Type-dependent value
```

| Type ID | Type    | Value Size |
|---------|---------|------------|
| 1       | Bool    | 1 byte     |
| 2       | Int     | 4 bytes    |
| 3       | UInt    | 4 bytes    |
| 4       | Int64   | 8 bytes    |
| 5       | UInt64  | 8 bytes    |
| 6       | Double  | 8 bytes    |
| 10      | QString | 4-byte length + UTF-16 data |
| 38      | Float   | 4 bytes    |
| 135     | Double* | 8 bytes (OSCAR-specific) |

*Type 135 appears in newer OSCAR files and is treated as double.

---

## Event File Format (.001)

Event files contain actual waveform data and discrete event markers.

### Header

**Version < 10** (32 bytes):
| Offset | Type    | Field       | Description |
|--------|---------|-------------|-------------|
| 0      | uint32  | magic       | 0xC73216AB |
| 4      | uint16  | version     | Format version |
| 6      | uint16  | filetype    | 1 = event data |
| 8      | uint32  | machine_id  | Machine identifier |
| 12     | uint32  | session_id  | Session ID |
| 16     | int64   | first       | Start time (ms) |
| 24     | int64   | last        | End time (ms) |

**Version >= 10** (42 bytes, additional fields):
| Offset | Type    | Field       | Description |
|--------|---------|-------------|-------------|
| 32     | uint16  | compmethod  | Compression (0=none, 1=qCompress) |
| 34     | uint16  | machtype    | Machine type |
| 36     | int32   | datasize    | Uncompressed data size |
| 40     | uint16  | crc16       | CRC16 checksum |

### Data Section

For version >= 10 with compmethod > 0, data is compressed using Qt's
qCompress (zlib with 4-byte big-endian size header).

#### Decompressed Data Structure

**Phase 1: Channel Metadata**

```
num_channels    int16           Number of channels

For each channel:
  code          uint32          Channel ID (32-bit even for quint16!)
  num_lists     int16           Number of event lists

  For each event list:
    ts1         int64           Start timestamp (ms)
    ts2         int64           End timestamp (ms)
    evcount     int32           Number of events/samples
    elt         uint8           Event list type (0=Waveform, 1=Event)
    rate        double          Sample rate (Hz) for waveforms
    gain        double          Gain multiplier
    offset      double          Offset value
    min         double          Minimum value
    max         double          Maximum value
    dimension   QString         Unit string (e.g., "cmH2O", "L/M")

    (version >= 7):
    second_field bool           Has secondary data field

    (if second_field):
    min2        double          Secondary minimum
    max2        double          Secondary maximum
```

**Phase 2: Event Data Arrays**

For each channel, for each event list:

```
data            int16[]         Primary data (evcount * 2 bytes)

(if second_field):
data2           int16[]         Secondary data (evcount * 2 bytes)

(if elt != EVL_Waveform):
time            uint32[]        Timestamps (evcount * 4 bytes)
```

### Event List Types

| Value | Name        | Description |
|-------|-------------|-------------|
| 0     | EVL_Waveform | Continuous waveform with fixed sample rate |
| 1     | EVL_Event    | Discrete events with individual timestamps |

### Value Calculation

To get actual values from raw data:
```python
actual_value = (raw_int16 * gain) + offset
```

For waveforms, timestamps are calculated from sample rate:
```python
time_ms = sample_index * (1000.0 / rate)
```

---

## QString Format

Qt stores QString as UTF-16 with a 4-byte length prefix:

```
length      uint32      Byte length of UTF-16 data (0xFFFFFFFF = null)
data        bytes       UTF-16-LE encoded string
```

---

## Qt qCompress Format

Qt's qCompress prepends a 4-byte big-endian uncompressed size to zlib data:

```
size        uint32 (BE) Uncompressed size
data        bytes       Standard zlib compressed data
```

To decompress in Python:
```python
import zlib
import struct
uncompressed_size = struct.unpack('>I', data[:4])[0]
decompressed = zlib.decompress(data[4:])
```

---

## Channel IDs (Complete Reference)

### Event Flag Channels (0x10xx)

| ID     | Constant         | Description | Unit |
|--------|------------------|-------------|------|
| 0x1000 | CPAP_CSR         | Cheyne-Stokes respiration | - |
| 0x1001 | CPAP_ClearAirway | Central apnea (CA) | events/hr |
| 0x1002 | CPAP_Obstructive | Obstructive apnea (OA) | events/hr |
| 0x1003 | CPAP_Hypopnea    | Hypopnea (H) | events/hr |
| 0x1004 | CPAP_Apnea       | Unclassified apnea | events/hr |
| 0x1005 | CPAP_FlowLimit   | Flow limitation flag | - |
| 0x1006 | CPAP_RERA        | RERA | events/hr |
| 0x1007 | CPAP_VSnore      | Vibratory snore | - |
| 0x100a | CPAP_LeakFlag    | Leak flag | - |

### Waveform Channels (0x11xx)

| ID     | Constant             | Description | Unit |
|--------|----------------------|-------------|------|
| 0x1100 | CPAP_FlowRate        | Flow rate waveform | L/min |
| 0x1101 | CPAP_MaskPressure    | Mask pressure (event samples) | cmH2O |
| 0x1102 | CPAP_MaskPressureHi  | Mask pressure (high resolution) | cmH2O |
| 0x1103 | CPAP_TidalVolume     | Tidal volume | ml |
| 0x1104 | CPAP_Snore           | Snore detection | - |
| 0x1105 | CPAP_MinuteVent      | Minute ventilation | L/min |
| 0x1106 | CPAP_RespRate        | Respiratory rate | br/min |
| 0x1107 | CPAP_PTB             | Patient triggered breath | - |
| 0x1108 | CPAP_Leak            | Leak rate | L/min |
| 0x1109 | CPAP_IE              | I:E ratio | - |
| 0x110A | CPAP_Te              | Expiratory time | s |
| 0x110B | CPAP_Ti              | Inspiratory time | s |
| 0x110C | CPAP_Pressure        | Therapy pressure | cmH2O |
| 0x110D | CPAP_IPAP            | IPAP | cmH2O |
| 0x110E | CPAP_EPAP            | EPAP | cmH2O |
| 0x110F | CPAP_PS              | Pressure support | cmH2O |
| 0x1113 | CPAP_FLG             | Flow limitation graph | - |
| 0x1116 | CPAP_AHI             | Running AHI | events/hr |
| 0x1117 | CPAP_LeakTotal       | Total leak | L/min |

### Setting Channels (0x10xx, 0x12xx)

| ID     | Constant          | Description |
|--------|-------------------|-------------|
| 0x1020 | CPAP_PressureMin  | Minimum pressure setting |
| 0x1021 | CPAP_PressureMax  | Maximum pressure setting |
| 0x1022 | CPAP_RampTime     | Ramp time |
| 0x1023 | CPAP_RampPressure | Ramp start pressure |
| 0x1200 | CPAP_Mode         | PAP mode (CPAP/APAP/BiLevel) |

### Oximeter Channels (0x18xx)

| ID     | Constant      | Description | Unit |
|--------|---------------|-------------|------|
| 0x1800 | OXI_Pulse     | Pulse rate | bpm |
| 0x1801 | OXI_SPO2      | Blood oxygen saturation | % |
| 0x1802 | OXI_Plethy    | Plethysmograph | - |

---

## machines.xml Format

```xml
<machines>
  <machine class="ResMed" id="688672065" type="1">
    <properties>
      <SerialNumber>23254434021</SerialNumber>
      <ProductCode>39523</ProductCode>
      <ProductName>AirSense 11 AutoSet</ProductName>
    </properties>
    <brand>ResMed</brand>
    <model>AirSense 11 AutoSet</model>
    <modelnumber>39523</modelnumber>
    <serial>23254434021</serial>
    <series>AirSense 11</series>
    <dataversion>15</dataversion>
    <lastimported>2026-01-17T11:12:57</lastimported>
  </machine>
</machines>
```

Key attributes:
- `class`: Loader name (used in folder path)
- `id`: Machine ID (decimal)
- `type`: Machine type (1=CPAP, 2=Oximeter, 4=Journal)

---

## Summaries.xml.gz Format

Gzipped XML file containing session index:

```xml
<sessions loader="ResMed" version="1" count="1464" profile="rforrest" serial="23254434021">
  <session id="1721391341" last="1721391463000" events="1" first="1721391341000" enabled="1">
    <channels>1004,1106,1002,1104,1003,1105,...</channels>
    <settings>1020,1021,1200</settings>
  </session>
  ...
</sessions>
```

Session attributes:
- `id`: Session ID (Unix timestamp in seconds)
- `first`: Start time (milliseconds)
- `last`: End time (milliseconds)
- `enabled`: Whether session is enabled (1/0)
- `events`: Whether event data exists (1/0)

Channel/settings values are comma-separated hex channel IDs.
