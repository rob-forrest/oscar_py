# OSCAR-Py

A Python port of [OSCAR](https://www.sleepfiles.com/OSCAR/) (Open Source CPAP Analysis Reporter) - a cross-platform application for reviewing and analyzing CPAP therapy data.

## Overview

OSCAR-Py reads CPAP data stored by the original OSCAR C++ application and displays it using Python/PyQt6. It provides:

- **Daily View**: Detailed waveform graphs for individual sessions (Flow Rate, Pressure, Leak, etc.)
- **Overview**: Summary charts and statistics over configurable date ranges
- **Statistics**: Compliance tracking and trend analysis

## Features

### Data Loading
- Reads OSCAR's binary data format (`.000` summary files, `.001` event/waveform files)
- Loads session index from `Summaries.xml.gz`
- Parses machine configuration from `machines.xml`
- Supports ResMed S9, AirSense 10, and AirSense 11 devices

### Waveform Display
All available CPAP waveforms are displayed in scrollable, synchronized graphs:

| Channel | Description | Unit |
|---------|-------------|------|
| Flow Rate | Breathing flow waveform | L/min |
| Mask Pressure | Mask pressure (high resolution) | cmH2O |
| Leak Rate | Detected mask leakage | L/min |
| Resp Rate | Respiratory rate | br/min |
| Tidal Volume | Volume per breath | ml |
| Minute Vent | Minute ventilation | L/min |
| Ti / Te | Inspiratory/Expiratory time | seconds |
| I:E Ratio | Inspiratory to expiratory ratio | - |
| Pressure | Therapy pressure | cmH2O |
| IPAP / EPAP | Bi-level pressures | cmH2O |
| Snore | Snore detection | - |
| Flow Limitation | Flow limitation index | - |

### Event Flags
Respiratory events are displayed as colored overlays on the flow rate graph:
- **OA** (Teal): Obstructive Apnea
- **CA** (Purple): Central Apnea
- **H** (Blue): Hypopnea
- **RERA** (Yellow): Respiratory Effort Related Arousal

## Installation

### Requirements
- Python 3.9+
- PyQt6
- PyQtGraph
- NumPy

### Install Dependencies
```bash
pip install PyQt6 pyqtgraph numpy
```

## Usage

### Launch Application
```bash
cd oscar_py
python main.py --data /path/to/OSCAR_Data --profile ProfileName
```

### Command Line Arguments
| Argument | Description |
|----------|-------------|
| `--data PATH` | Path to OSCAR_Data directory |
| `--profile NAME` | Profile name to open |
| `--debug` | Enable debug logging |

### Default Data Location
If `--data` is not specified, the application looks for data in:
- macOS: `~/Documents/OSCAR_Data`
- Linux: `~/OSCAR_Data`
- Windows: `Documents\OSCAR_Data`

## Project Structure

```
oscar_py/
├── main.py                 # Application entry point
├── sleeplib/               # Core data library
│   ├── profile.py          # Profile management
│   ├── machine.py          # Machine/CPAP device
│   ├── session.py          # Session data container
│   ├── schema.py           # Channel definitions
│   ├── summary_loader.py   # Binary summary file parser
│   ├── event_loader.py     # Binary event/waveform parser
│   └── statistics.py       # Statistics calculations
├── gui/                    # PyQt6 GUI components
│   ├── main_window.py      # Main application window
│   ├── daily_view.py       # Daily view with waveforms
│   ├── overview_view.py    # Overview/statistics tab
│   └── profile_selector.py # Profile selection
├── graphs/                 # PyQtGraph visualization
│   ├── graph_view.py       # Scrollable graph container
│   ├── line_chart.py       # Time-series line plots
│   └── time_axis.py        # Time axis formatting
└── docs/                   # Documentation
    ├── OSCAR_DATA_FORMAT.md   # Binary file format spec
    ├── ARCHITECTURE.md        # Code architecture
    └── IMPLEMENTATION_NOTES.md # Implementation details
```

## Documentation

- [Data Format Specification](docs/OSCAR_DATA_FORMAT.md) - Detailed binary file format documentation
- [Architecture Guide](docs/ARCHITECTURE.md) - Code organization and design patterns
- [Implementation Notes](docs/IMPLEMENTATION_NOTES.md) - Key implementation details and gotchas

## Data Directory Structure

OSCAR stores data in the following structure:

```
OSCAR_Data/
└── Profiles/
    └── {profile_name}/
        ├── Profile.xml           # Profile settings
        ├── machines.xml          # Machine registry
        └── {Loader}_{Serial}/    # Machine data (e.g., ResMed_23254434021)
            ├── Summaries.xml.gz  # Session index
            ├── Summaries/        # Binary summary files
            │   └── {session_id}.000
            └── Events/           # Binary waveform files
                └── {session_id}.001
```

## Compatibility

OSCAR-Py reads data created by OSCAR C++ versions 1.4.0 through 1.7.0. It does not modify any data files, making it safe to use alongside the original OSCAR application.

## Development Status

This is an early development version (0.1.0-dev). Current capabilities:
- [x] Load OSCAR binary data format
- [x] Display all available waveform channels
- [x] Synchronized scrolling/zooming across graphs
- [x] Event flag overlay display
- [x] Session statistics panel
- [ ] Overview statistics (in progress)
- [ ] Data import from SD card
- [ ] Report generation

## License

This project is licensed under the GNU General Public License v3.0, the same license as the original OSCAR project.

## Credits

- Original OSCAR C++ application by the OSCAR Team
- Python port implementation

## See Also

- [OSCAR Website](https://www.sleepfiles.com/OSCAR/)
- [OSCAR GitHub](https://gitlab.com/pholy/OSCAR-code)
