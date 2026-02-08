# Wave 5: Data Import & End-to-End Integration

## Goal
Wire the Import menu to ResmedLoader so users can import CPAP data from a DATALOG folder through the GUI, creating a complete end-to-end workflow: Import → Profile → Display.

## Current State
- Waves 1-4 complete (20,300 lines, all modules implemented)
- DailyView ↔ Profile: WIRED (end-to-end)
- OverviewView ↔ Profile: WIRED (end-to-end)
- **Import menu → ResmedLoader: DISCONNECTED (placeholder stub)**
- Data must already exist on disk in OSCAR format; no way to ingest new data from GUI

## What This Wave Delivers
1. **Import Dialog** - Progress dialog with ResmedLoader scanning + importing
2. **Import Wiring** - MainWindow.import_data() calls ResmedLoader, creates Machine/Sessions, saves to profile
3. **Post-Import Refresh** - Views update after import completes
4. **Direct DATALOG Import** - Support the user's setup (DATALOG folder only, no STR.edf)

## Implementation Plan

### Task Group A: Import Progress Dialog (independent)
**File:** `gui/import_dialog.py` (~150 lines, NEW)

A QDialog that:
- Shows a progress bar and status text
- Runs ResmedLoader.scan_files() then ResmedLoader._import_day() per day
- Uses QTimer-based batch processing (not threads) to keep UI responsive
- Emits signal with (machine, session_count) on completion
- Shows summary: "Imported X sessions over Y days"

Key methods:
```python
class ImportDialog(QDialog):
    import_complete = pyqtSignal(object, int)  # machine, session_count

    def __init__(self, source_path, profile, parent=None)
    def start_import(self)
    def _process_next_day(self)       # QTimer callback
    def _on_import_finished(self)
```

### Task Group B: Wire Import into MainWindow (depends on A)
**File:** `gui/main_window.py` (~40 lines changed)

Replace the stub `import_data()` with:
1. Show folder picker (already exists)
2. Detect ResMed data via `ResmedLoader.detect()` or scan DATALOG directly
3. Ensure a profile is open (create default if needed)
4. Launch ImportDialog
5. On completion: register Machine in profile, save machines.xml, refresh views

Also handle the "DATALOG-only" case: if user selects a folder that IS the DATALOG folder (no STR.edf), bypass detect() and go straight to scan_files().

### Task Group C: Profile Integration for Import (independent)
**File:** `sleeplib/profile.py` (~30 lines added)

Add method:
```python
def import_from_loader(self, machine, sessions):
    """Register an imported machine and its sessions into the profile."""
    self.add_machine(machine)
    for session in machine.sessionlist.values():
        session_date = session.first.date() if session.first else None
        if session_date:
            day = self.add_day(session_date)
            day.add_session(session)
    self.store_machines()
```

### Task Group D: ResmedLoader Enhancement for DATALOG-Only (independent)
**File:** `sleeplib/loader_plugins/resmed_loader.py` (~20 lines changed)

The current `detect()` requires STR.edf which the user doesn't have. Add:
```python
@staticmethod
def detect_datalog(path: Path) -> bool:
    """Detect if path is/contains a DATALOG folder (no STR.edf required)."""
```

And update `scan_files()` to accept a bare DATALOG path (already partially handles this).

## Files to Modify/Create

| File | Action | Est. Lines |
|------|--------|------------|
| `gui/import_dialog.py` | **New** | ~150 |
| `gui/main_window.py` | Edit | ~40 changed |
| `sleeplib/profile.py` | Edit | ~30 added |
| `sleeplib/loader_plugins/resmed_loader.py` | Edit | ~20 changed |
| **Total** | | ~240 new/changed |

## Parallel Execution Plan
- **Group A** (import_dialog.py) and **Group C** (profile.py) and **Group D** (resmed_loader.py) can run in parallel
- **Group B** (main_window.py wiring) depends on A, C, D

## Verification
1. `python3 main.py` → Select profile → File > Import Data → Pick DATALOG folder → Sessions imported
2. Views refresh with imported data
3. Close and reopen app → data persists (saved to profile)
4. Smoke test: `python3 -c "from gui.import_dialog import ImportDialog; print('OK')"`
