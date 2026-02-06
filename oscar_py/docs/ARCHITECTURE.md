# OSCAR-Py Architecture Guide

This document describes the architecture and code organization of OSCAR-Py.

## Overview

OSCAR-Py follows a layered architecture:

```
┌─────────────────────────────────────────────────────────────┐
│                      GUI Layer (gui/)                        │
│  MainWindow, DailyView, OverviewView, ProfileSelector       │
├─────────────────────────────────────────────────────────────┤
│                  Visualization Layer (graphs/)               │
│  GraphView, LineChart, TimeAxis, EventFlags                 │
├─────────────────────────────────────────────────────────────┤
│                    Data Layer (sleeplib/)                    │
│  Profile, Machine, Session, SummaryLoader, EventLoader      │
├─────────────────────────────────────────────────────────────┤
│                    Storage (Binary Files)                    │
│  .000 summary files, .001 event files, XML configuration    │
└─────────────────────────────────────────────────────────────┘
```

## Module Organization

### sleeplib/ - Core Data Library

The `sleeplib` package handles all data loading and representation.

#### profile.py - Profile Management
```python
class Profile:
    """Represents a user profile containing multiple machines and days."""

    def open(path: str) -> bool
    def get_day(date: date) -> Optional[Day]
    def last_day() -> Optional[date]
```

Key responsibilities:
- Load profile configuration from `Profile.xml`
- Parse machine registry from `machines.xml`
- Coordinate loading of machine data
- Provide access to days and sessions

#### machine.py - CPAP Machine
```python
class MachineInfo:
    """Machine metadata (brand, model, serial)."""

class CPAP:
    """Represents a CPAP machine with session data."""

    def load_sessions(progress=None) -> bool
    def get_data_path() -> str
```

Key responsibilities:
- Store machine metadata
- Load session summaries and events
- Organize sessions into days

#### session.py - Session Data
```python
class Session:
    """A single CPAP therapy session."""

    def hours() -> float
    def count(channel_id) -> float
    def avg(channel_id) -> float
    def load_events() -> None
    def get_events(channel_id) -> List[EventList]
```

Key responsibilities:
- Store summary statistics (counts, averages, min/max)
- Lazy-load event/waveform data on demand
- Provide access to waveform data

#### summary_loader.py - Binary Summary Parser
```python
class SummaryLoader:
    """Loads session data from OSCAR binary format."""

    def load_session_index() -> int
    def load_session_summaries(profile, day_split_hour) -> int
```

Parses:
- `Summaries.xml.gz` - Session index
- `Summaries/*.000` - Binary summary files

#### event_loader.py - Binary Waveform Parser
```python
class EventLoader:
    """Loads waveform data from OSCAR binary event files."""

    def load(session_id: int) -> Dict[ChannelID, List[EventList]]

@dataclass
class EventList:
    """Container for waveform or event data."""
    channel_id: ChannelID
    event_type: int  # EVL_Waveform or EVL_Event
    data: np.ndarray

    def get_values() -> np.ndarray
    def get_times_ms() -> np.ndarray
```

Parses:
- `Events/*.001` - Compressed waveform data

#### schema.py - Channel Definitions
```python
# Channel ID constants
CPAP_FlowRate = 0x1100
CPAP_MaskPressure = 0x1101
CPAP_Leak = 0x1108
# ... etc

class Channel:
    """Channel metadata (name, unit, color)."""
```

Defines all 70+ channel IDs used by OSCAR.

---

### gui/ - User Interface

The `gui` package contains PyQt6 widgets.

#### main_window.py - Application Window
```python
class MainWindow(QMainWindow):
    """Main application window with tabs."""

    def open_profile(name: str) -> bool
    def close_profile() -> None
```

Layout:
- Menu bar (File, View, Help)
- Tab widget (Daily, Overview, Statistics)
- Status bar

#### daily_view.py - Daily View Tab
```python
class DailyView(QWidget):
    """Daily view with calendar, session list, and graphs."""

    def set_profile(profile: Profile) -> None
    def select_date(date: date) -> None
    def select_session(session: Session) -> None
```

Layout:
```
┌──────────────────────────────────────────────────────────┐
│ [<] [Date Display] [>] [>>]                              │
├─────────────┬────────────────────────────────────────────┤
│  Calendar   │                                            │
│             │         GraphView (scrollable)             │
├─────────────┤                                            │
│  Sessions   │    Flow Rate ═══════════════════════       │
│  ─────────  │    Pressure  ═══════════════════════       │
│  Session 1  │    Leak      ═══════════════════════       │
│  Session 2  │    ...                                     │
├─────────────┤                                            │
│  Details    │                                            │
│             │                                            │
└─────────────┴────────────────────────────────────────────┘
│ Date | Time Range | Duration | AHI | Events | Leak | P  │
└──────────────────────────────────────────────────────────┘
```

#### overview_view.py - Overview Tab
Statistics and charts over date ranges.

---

### graphs/ - Visualization

The `graphs` package provides PyQtGraph-based visualization.

#### graph_view.py - Graph Container
```python
class GraphView(QWidget):
    """Scrollable container for multiple synchronized graphs."""

    def add_graph(name, height, y_label, y_unit, color) -> LineChart
    def remove_graph(name) -> bool
    def set_time_range(start_ms, end_ms) -> None
    def zoom_in/zoom_out/reset_zoom()
```

Features:
- Vertical scrolling through graphs
- Synchronized X-axis across all graphs
- Mouse wheel zoom
- Click-drag pan

#### line_chart.py - Line Plot Widget
```python
class LineChart(pg.PlotWidget):
    """Single time-series line chart."""

    def set_data(times, values, auto_range=True) -> None
    def add_region(start, end, color, alpha) -> None
```

Wraps PyQtGraph PlotWidget with:
- Custom time axis
- Y-axis label and unit
- Configurable line color

#### time_axis.py - Time Axis
```python
class TimeAxisItem(pg.AxisItem):
    """Custom X-axis showing time of day."""
```

Formats time as HH:MM:SS based on zoom level.

---

## Data Flow

### Profile Loading
```
main.py
  └── MainWindow.open_profile(name)
        └── Profile.open(path)
              ├── Parse Profile.xml
              ├── Parse machines.xml
              └── For each machine:
                    └── CPAP.load_sessions()
                          └── SummaryLoader.load_session_index()
                          └── SummaryLoader.load_session_summaries()
```

### Waveform Display
```
DailyView.select_session(session)
  └── DailyView._load_and_display_waveforms()
        ├── session.load_events()
        │     └── EventLoader.load(session_id)
        │           └── Parse .001 file
        │           └── Decompress with zlib
        │           └── Create EventList objects
        │
        └── For each channel:
              └── GraphView.add_graph()
                    └── LineChart.set_data(times, values)
```

---

## Key Design Decisions

### 1. Lazy Loading
Event/waveform data is loaded on-demand when a session is selected, not when the profile opens. This keeps startup fast even with thousands of sessions.

### 2. Qt Data Stream Compatibility
Binary files use Qt's QDataStream format with specific quirks:
- Little-endian byte order
- QHash keys are 32-bit even when declared as uint16
- QVariant has type ID + null flag + value
- qCompress uses 4-byte big-endian size header

### 3. Day Split Time
Sessions are grouped into "days" based on a configurable split time (default: noon). A session at 2 AM belongs to the previous calendar day's sleep period.

### 4. Synchronized Graphs
All graphs in the GraphView share the same X-axis range. When you zoom or pan one graph, all graphs update together. This is achieved through:
- X-axis linking in PyQtGraph
- Shared time range state in GraphView

### 5. Scrollable Graph Container
With many waveform channels available, the GraphView uses a scroll area to allow viewing all graphs at readable sizes. Each graph maintains its specified height rather than being compressed.

---

## Adding New Features

### Adding a New Channel
1. Add channel ID constant to `schema.py`
2. Add to `waveform_channels` list in `daily_view.py`
3. Choose appropriate color and height

### Adding a New View
1. Create new widget in `gui/`
2. Add tab in `main_window.py`
3. Connect to profile changes

### Supporting New Machine Type
1. Create loader in `sleeplib/loader_plugins/`
2. Register loader by brand name
3. Implement file parsing
