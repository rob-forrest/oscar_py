# OSCAR-Py Implementation Notes

This document captures key implementation details, gotchas, and lessons learned during development.

## Binary File Parsing

### Qt QDataStream Format

OSCAR uses Qt 4.6 QDataStream with Little Endian byte order. Several quirks must be handled:

#### QHash Key Serialization
**Critical**: Qt serializes QHash keys as **32-bit integers** even when the key type is declared as `uint16` (like `ChannelID`).

```python
# WRONG - will cause misaligned reads
key = struct.unpack('<H', data[offset:offset+2])[0]  # 16-bit

# CORRECT - Qt uses 32-bit for hash keys
key = struct.unpack('<I', data[offset:offset+4])[0]  # 32-bit
```

This affects:
- `sleeplib/summary_loader.py` - All QHash reads
- `sleeplib/event_loader.py` - Channel ID reads

#### QVariant Format
QVariant serialization format:
```
type_id     uint32      Qt metatype ID
is_null     uint8       1 if null, 0 otherwise
value       varies      Type-dependent value
```

Type IDs encountered in OSCAR files:
| Type ID | Qt Type | Value Size |
|---------|---------|------------|
| 1 | Bool | 1 byte |
| 2 | Int | 4 bytes |
| 3 | UInt | 4 bytes |
| 4 | Int64 | 8 bytes |
| 5 | UInt64 | 8 bytes |
| 6 | Double | 8 bytes |
| 10 | QString | 4-byte length + UTF-16 |
| 38 | Float | 4 bytes |
| **135** | Double* | 8 bytes |

*Type 135 is OSCAR-specific and should be treated as double.

#### QString Format
Qt stores QString as UTF-16 with length prefix:
```python
def read_qstring(data, offset):
    length = struct.unpack('<I', data[offset:offset+4])[0]
    if length == 0xFFFFFFFF:
        return None, offset + 4  # Null string
    text = data[offset+4:offset+4+length].decode('utf-16-le')
    return text, offset + 4 + length
```

#### qCompress Format
Qt's `qCompress` prepends a 4-byte **big-endian** size header to zlib data:
```python
import zlib
import struct

def decompress_qt(data):
    uncompressed_size = struct.unpack('>I', data[:4])[0]  # Big-endian!
    return zlib.decompress(data[4:])
```

---

## Machine Path Resolution

### machines.xml Parsing

The machine folder name format is `{Loader}_{Serial}`.

**Critical**: Machine info is stored in nested elements, NOT attributes:
```xml
<machine class="ResMed" id="688672065" type="1">
    <properties>...</properties>
    <brand>ResMed</brand>           <!-- Child element, not attribute -->
    <model>AirSense 11 AutoSet</model>
    <serial>23254434021</serial>    <!-- Child element, not attribute -->
</machine>
```

Correct parsing:
```python
loader_name = machine_elem.get('class')  # Attribute: "ResMed"
serial = machine_elem.find('serial').text  # Element: "23254434021"

folder_path = f"{loader_name}_{serial}"  # "ResMed_23254434021"
```

### Machine ID
The `id` attribute is a **decimal integer**, not hex:
```python
machine_id = int(machine_elem.get('id'))  # NOT int(id, 16)
```

---

## Session Organization

### Day Split Time
OSCAR groups sessions into "sleep days" based on a configurable split time (default: 12:00 noon).

A session starting at 2:00 AM on January 5th belongs to the January 4th sleep day.

```python
def get_session_date(session_start_time, day_split_hour=12):
    dt = datetime.fromtimestamp(session_start_time / 1000.0)
    if dt.hour < day_split_hour:
        return (dt - timedelta(days=1)).date()
    return dt.date()
```

### Session ID
Session IDs are Unix timestamps (seconds since epoch) representing the session start time:
```python
session_id = 1721391341  # = 2024-07-19 14:15:41 UTC
```

---

## Event/Waveform Data

### Event File Structure (.001)

1. **Header** (32-42 bytes depending on version)
2. **Compressed data** (if version >= 10 and compmethod > 0)

Decompressed data structure:
```
Phase 1: Channel Metadata
  num_channels    int16
  For each channel:
    code          uint32      # Channel ID
    num_lists     int16
    For each event list:
      timestamps, sample rate, gain, offset, etc.

Phase 2: Event Data Arrays
  For each channel, for each event list:
    data          int16[]     # Raw samples
    time          uint32[]    # Only for discrete events
```

### Value Conversion
Raw int16 samples are converted to actual values:
```python
actual_value = (raw_int16 * gain) + offset
```

### Timestamp Calculation
For waveforms (continuous data):
```python
sample_time_ms = event_list_start_ms + (sample_index * 1000.0 / sample_rate)
```

For discrete events:
```python
event_time_ms = event_list_start_ms + time_offset_array[event_index]
```

---

## GUI Components

### GraphView Scrolling

When displaying many waveform channels, the GraphView must be scrollable. Key implementation:

```python
# Wrap splitter in scroll area
self._scroll_area = QScrollArea()
self._scroll_area.setWidgetResizable(True)

# Set fixed heights on graph panels to prevent compression
panel.setFixedHeight(height)

# Update container size when adding graphs
def _update_container_size(self):
    total_height = sum(p._preferred_height + 4 for p in self._graphs.values())
    self._scroll_container.setMinimumHeight(total_height)
```

### X-Axis Synchronization

All graphs share the same time range through PyQtGraph's view linking:
```python
def _link_x_axes(self):
    panels = list(self._graphs.values())
    reference_view = panels[0].chart.getPlotItem().getViewBox()
    for panel in panels[1:]:
        view_box = panel.chart.getPlotItem().getViewBox()
        view_box.setXLink(reference_view)
```

---

## Channel IDs Reference

### Waveform Channels (0x11xx)
| ID | Name | Description |
|----|------|-------------|
| 0x1100 | CPAP_FlowRate | Flow rate waveform |
| 0x1101 | CPAP_MaskPressure | Mask pressure (event samples) |
| 0x1102 | CPAP_MaskPressureHi | Mask pressure (high resolution) |
| 0x1103 | CPAP_TidalVolume | Tidal volume |
| 0x1104 | CPAP_Snore | Snore detection |
| 0x1105 | CPAP_MinuteVent | Minute ventilation |
| 0x1106 | CPAP_RespRate | Respiratory rate |
| 0x1108 | CPAP_Leak | Leak rate |
| 0x1109 | CPAP_IE | I:E ratio |
| 0x110A | CPAP_Te | Expiratory time |
| 0x110B | CPAP_Ti | Inspiratory time |
| 0x110C | CPAP_Pressure | Therapy pressure |
| 0x110D | CPAP_IPAP | IPAP |
| 0x110E | CPAP_EPAP | EPAP |
| 0x1113 | CPAP_FLG | Flow limitation graph |
| 0x1116 | CPAP_AHI | Running AHI |

### Event Flag Channels (0x10xx)
| ID | Name | Description |
|----|------|-------------|
| 0x1001 | CPAP_ClearAirway | Central apnea (CA) |
| 0x1002 | CPAP_Obstructive | Obstructive apnea (OA) |
| 0x1003 | CPAP_Hypopnea | Hypopnea (H) |
| 0x1006 | CPAP_RERA | RERA |

### Setting Channels (0x10xx, 0x12xx)
| ID | Name | Description |
|----|------|-------------|
| 0x1020 | CPAP_PressureMin | Minimum pressure setting |
| 0x1021 | CPAP_PressureMax | Maximum pressure setting |
| 0x1200 | CPAP_Mode | PAP mode (CPAP/APAP/BiLevel) |

---

## Common Issues & Solutions

### Issue: "No data" in graphs
**Cause**: Events not loaded for session.
**Solution**: Ensure `session.load_events()` is called before `session.get_events()`.

### Issue: Misaligned binary data
**Cause**: Reading QHash keys as 16-bit instead of 32-bit.
**Solution**: Always read QHash keys as uint32.

### Issue: Profile not found
**Cause**: Incorrect data path or missing underscore in path.
**Solution**: Check that data path points to `OSCAR_Data` (with underscore).

### Issue: Graphs compressed/unreadable
**Cause**: Too many graphs without scroll container.
**Solution**: GraphView uses QScrollArea with fixed-height panels.

### Issue: Unknown QVariant type 135
**Cause**: OSCAR-specific type not in Qt standard.
**Solution**: Treat type 135 as double (8 bytes).

---

## Testing with Real Data

To test with actual OSCAR data:

1. Install OSCAR C++ and import ResMed data
2. Note the OSCAR_Data path (e.g., `/Users/name/Documents/OSCAR_Data`)
3. Run OSCAR-Py with that path:
   ```bash
   python main.py --data /Users/name/Documents/OSCAR_Data --profile ProfileName
   ```

Compare waveforms and statistics with OSCAR C++ to verify accuracy.

---

## Performance Considerations

### Large Datasets
The test dataset contains:
- 4108 days of data
- 8231 sessions across 3 machines
- ~10 years of CPAP usage

Loading strategy:
1. Load session index on profile open (~1 second)
2. Load session summaries on profile open (~0.5 seconds per machine)
3. Load event data only when session is selected (~100ms per session)

### Waveform Rendering
High-resolution waveforms (25 Hz flow rate) can have 100,000+ samples per session. PyQtGraph handles this efficiently with:
- OpenGL acceleration
- Automatic downsampling for zoomed-out views
