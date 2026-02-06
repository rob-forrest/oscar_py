# Changelog

All notable changes to OSCAR-Py are documented in this file.

## [0.1.0-dev] - 2026-02-05

### Added

#### Data Loading
- **Summary Loader** (`sleeplib/summary_loader.py`)
  - Parse `Summaries.xml.gz` session index
  - Load binary `.000` summary files
  - Handle Qt QDataStream format with 32-bit hash keys
  - Support QVariant type 135 (OSCAR-specific double)
  - Organize sessions into days based on day split time

- **Event Loader** (`sleeplib/event_loader.py`)
  - Parse binary `.001` event/waveform files
  - Decompress Qt qCompress data (zlib with BE size header)
  - Extract waveform and discrete event data
  - Convert raw int16 samples using gain/offset

- **Machine Support** (`sleeplib/machine.py`)
  - Parse `machines.xml` for machine registry
  - Resolve machine data paths (`{Loader}_{Serial}` format)
  - Load session data for ResMed S9, AirSense 10, AirSense 11

#### User Interface
- **Daily View** (`gui/daily_view.py`)
  - Calendar date selector with data highlighting
  - Session list for multi-session days
  - Session info panel (date, time, duration, AHI, events, leak, pressure)
  - Scrollable waveform display for all available channels

- **GraphView** (`graphs/graph_view.py`)
  - Scrollable container for multiple synchronized graphs
  - Mouse wheel zoom centered on cursor
  - Click-drag pan
  - Double-click to reset zoom
  - X-axis synchronization across all graphs

- **All Waveform Channels**
  - Flow Rate (0x1100)
  - Mask Pressure Hi/Lo (0x1102, 0x1101)
  - Leak Rate (0x1108)
  - Respiratory Rate (0x1106)
  - Tidal Volume (0x1103)
  - Minute Ventilation (0x1105)
  - Inspiratory/Expiratory Time (0x110B, 0x110A)
  - I:E Ratio (0x1109)
  - Pressure (0x110C)
  - IPAP/EPAP (0x110D, 0x110E)
  - Snore (0x1104)
  - Flow Limitation (0x1113)
  - AHI Graph (0x1116)

- **Event Flag Overlay**
  - Obstructive Apnea (OA) - Teal
  - Central Apnea (CA) - Purple
  - Hypopnea (H) - Blue
  - RERA - Yellow

#### Documentation
- `README.md` - Project overview and usage
- `docs/OSCAR_DATA_FORMAT.md` - Binary file format specification
- `docs/ARCHITECTURE.md` - Code architecture guide
- `docs/IMPLEMENTATION_NOTES.md` - Implementation details and gotchas

### Fixed
- Machine path construction (was `Machines/{hexid}`, now `{Loader}_{Serial}`)
- machines.xml parsing (loader in `class` attr, brand/model/serial as child elements)
- QHash key reading (32-bit, not 16-bit)
- QVariant type 135 handling (treat as double)
- Session attribute name (`_session_id` not `_id`)
- Graph compression when displaying many channels (added scroll area)

### Known Issues
- Overview tab not yet functional (placeholder)
- Statistics tab not yet functional (placeholder)
- No data import capability (reads existing OSCAR data only)
- Event regions limited to first 100 events per type for performance

---

## Development Notes

### Binary Format Discoveries

1. **Qt QDataStream quirk**: Hash keys are always 32-bit, even for uint16 key types
2. **QVariant type 135**: OSCAR-specific, treat as double (8 bytes)
3. **qCompress header**: 4-byte big-endian uncompressed size before zlib data
4. **Session organization**: Split by configurable time (default noon)

### Tested With
- OSCAR C++ 1.7.0 data format
- ResMed S9 AutoSet (~3200 sessions)
- ResMed AirSense 10 AutoSet (~3500 sessions)
- ResMed AirSense 11 AutoSet (~1400 sessions)
- Total: 4108 days, 8231 sessions
