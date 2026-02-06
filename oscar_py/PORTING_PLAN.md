# OSCAR C++ to Python Porting Plan

## Overview
Port OSCAR (Open Source CPAP Analysis Reporter) from C++/Qt to Python/PyQt6 with faithful GUI reproduction.

**Technology Stack:**
- GUI Framework: PyQt6
- Visualization: PyQtGraph (GPU-accelerated, Qt-native)
- Data Processing: NumPy, pandas
- Binary Parsing: struct, numpy.frombuffer
- EDF Files: pyedflib or custom parser

---

## Architecture Overview

```
oscar_py/
├── main.py                    # Application entry point
├── sleeplib/                  # Core data library (port of SleepLib/)
│   ├── __init__.py
│   ├── preferences.py         # Base Preferences class
│   ├── profile.py             # Profile management
│   ├── machine.py             # Machine/device representation
│   ├── session.py             # Session data container
│   ├── day.py                 # Daily aggregation
│   ├── event.py               # EventList with compression
│   ├── schema.py              # Channel definitions (70+ channels)
│   └── loader_plugins/        # Device-specific loaders
│       ├── __init__.py
│       ├── loader_base.py     # Abstract loader base class
│       ├── resmed_loader.py   # ResMed S9/AirSense 10/11
│       └── edf_parser.py      # EDF+ file format parser
├── gui/                       # PyQt6 GUI components
│   ├── __init__.py
│   ├── main_window.py         # Main application window
│   ├── profile_selector.py    # Profile selection widget
│   ├── daily_view.py          # Daily tab with graphs
│   ├── overview_view.py       # Overview/statistics tab
│   ├── new_profile_dialog.py  # Create new profile
│   └── preferences_dialog.py  # Settings dialog
├── graphs/                    # PyQtGraph visualization
│   ├── __init__.py
│   ├── graph_view.py          # Main graph container
│   ├── line_chart.py          # Time-series line plots
│   └── event_flags.py         # Event flag rendering
├── resources/                 # Icons, stylesheets
│   └── icons/
└── tests/                     # Unit tests
    ├── test_profile.py
    ├── test_resmed_loader.py
    └── test_edf_parser.py
```

---

## Phase 1: Foundation (Profile Selector)
**Goal:** Launch application, display profile selector, create/edit profiles

### 1.1 Core Data Structures (Agent: data-models)
- [ ] `sleeplib/preferences.py` - Preferences base class with QSettings-like API
- [ ] `sleeplib/schema.py` - Channel definitions (ChannelID, ChanType, DataType)
- [ ] `sleeplib/machine.py` - Machine class with MachineInfo
- [ ] `sleeplib/profile.py` - Profile class with UserInfo, CPAPSettings, etc.

### 1.2 Profile Selector UI (Agent: profile-ui)
- [ ] `gui/profile_selector.py` - QTableView with profile list
- [ ] `gui/new_profile_dialog.py` - Create new profile dialog
- [ ] Profile persistence (XML files matching C++ format)
- [ ] Password protection (optional)

### 1.3 Application Shell (Agent: app-shell)
- [ ] `main.py` - Application entry, QApplication setup
- [ ] `gui/main_window.py` - MainWindow skeleton (tabs, menus)
- [ ] Data directory initialization
- [ ] Logging setup

### 1.4 Resources & Styling
- [ ] Port icons from oscar/icons/
- [ ] Basic stylesheet matching OSCAR look

---

## Phase 2: ResMed Data Import
**Goal:** Import data from ResMed SD card, store in profile

### 2.1 EDF Parser (Agent: edf-parser)
- [ ] `sleeplib/loader_plugins/edf_parser.py` - EDF+ file format parser
- [ ] Signal extraction with gain/offset conversion
- [ ] Multi-record file support
- [ ] Annotation parsing

### 2.2 ResMed Loader (Agent: resmed-loader)
- [ ] `sleeplib/loader_plugins/resmed_loader.py` - Main loader class
- [ ] Folder structure detection (/DATALOG/)
- [ ] STR.edf parsing (settings, summary data)
- [ ] BRP file parsing (flow, pressure waveforms)
- [ ] PLD file parsing (low-resolution data)
- [ ] EVE file parsing (apnea events)
- [ ] SAD file parsing (oximetry)
- [ ] CSL file parsing (Cheyne-Stokes)

### 2.3 Session Storage (Agent: session-storage)
- [ ] `sleeplib/session.py` - Session class with EventList storage
- [ ] `sleeplib/event.py` - EventList with qint16 compression
- [ ] `sleeplib/day.py` - Day aggregation
- [ ] Binary file format (compatible with C++ OSCAR)
- [ ] XML machine metadata

### 2.4 Import Progress UI
- [ ] Progress dialog during import
- [ ] Multi-threaded import (ProcessPoolExecutor)
- [ ] Error/warning collection

---

## Phase 3: Visualization & Daily View
**Goal:** Display imported data in interactive graphs

### 3.1 Graph Framework (Agent: graph-core)
- [ ] `graphs/graph_view.py` - PyQtGraph-based graph container
- [ ] Zoom/pan controls
- [ ] Time axis synchronization
- [ ] Multiple graph stacking

### 3.2 Daily View (Agent: daily-view)
- [ ] `gui/daily_view.py` - Daily tab implementation
- [ ] Calendar date selector
- [ ] Session selector (multiple sessions per day)
- [ ] Graph panels: Flow, Pressure, Leak, Events

### 3.3 Event Rendering
- [ ] Event flags (apneas, hypopneas, snores)
- [ ] Event tooltips
- [ ] Event summary panel

---

## Phase 4: Statistics & Overview
**Goal:** Statistical analysis and overview displays

### 4.1 Overview Tab (Agent: overview)
- [ ] `gui/overview_view.py` - Overview statistics
- [ ] Date range graphs
- [ ] AHI trending
- [ ] Usage statistics

### 4.2 Calculations
- [ ] Per-session statistics (AHI, leak, pressure)
- [ ] Per-day aggregations
- [ ] Date range summaries
- [ ] Percentile calculations

---

## Parallel Agent Assignments

### Wave 1 (Foundation) - Run in Parallel:
| Agent | Task | Files |
|-------|------|-------|
| `data-models` | Core data structures | sleeplib/*.py |
| `profile-ui` | Profile selector UI | gui/profile_selector.py, gui/new_profile_dialog.py |
| `app-shell` | Application shell | main.py, gui/main_window.py |

### Wave 2 (ResMed Import) - After Wave 1:
| Agent | Task | Files |
|-------|------|-------|
| `edf-parser` | EDF+ file parser | sleeplib/loader_plugins/edf_parser.py |
| `resmed-loader` | ResMed loader (depends on edf-parser) | sleeplib/loader_plugins/resmed_loader.py |
| `session-storage` | Session persistence | sleeplib/session.py, sleeplib/event.py |

### Wave 3 (Visualization) - After Wave 2:
| Agent | Task | Files |
|-------|------|-------|
| `graph-core` | Graph framework | graphs/*.py |
| `daily-view` | Daily view UI | gui/daily_view.py |

---

## Testing Strategy

### Unit Tests
- Profile creation/loading
- EDF parsing accuracy
- ResMed file detection
- Event compression/decompression
- Channel calculations

### Integration Tests
- Full import workflow
- Profile persistence roundtrip
- Graph rendering with real data

### Visual Verification
- Side-by-side comparison with C++ OSCAR
- Screenshot comparison tool

---

## File Format Compatibility

The Python port will read/write files compatible with C++ OSCAR:
- `Profile.xml` - Profile metadata
- `Machines.xml` - Device list
- `*.sum` - Session summary (binary)
- `*.evt` - Event data (binary)

This allows users to switch between C++ and Python versions.

---

## Dependencies

```
PyQt6>=6.4
pyqtgraph>=0.13
numpy>=1.21
pandas>=1.4
pyedflib>=0.1.30  # Optional, can use custom parser
lxml>=4.9         # For XML parsing
```

---

## Success Criteria

Phase 1 Complete When:
- [ ] Application launches with profile selector
- [ ] Can create new profile with user info
- [ ] Can select/open existing profile
- [ ] Main window displays with empty tabs
- [ ] Profile data persists across restarts

Phase 2 Complete When:
- [ ] ResMed SD card data detected
- [ ] All file types parsed (STR, BRP, PLD, EVE, SAD, CSL)
- [ ] Sessions stored in profile
- [ ] Import progress shown
- [ ] Data matches C++ OSCAR import

Phase 3 Complete When:
- [ ] Daily view shows calendar
- [ ] Graphs display waveforms
- [ ] Zoom/pan works smoothly
- [ ] Event flags visible
- [ ] Multiple sessions selectable
