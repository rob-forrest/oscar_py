"""
Loader Plugins - File Format Parsers for Sleep Device Data

This package provides parsers for various file formats used by sleep
therapy devices, ported from the C++ OSCAR application.

Copyright (c) 2019-2025 The OSCAR Team
License: GPL v3

Available Modules:
    - edf_parser: EDF/EDF+ file format parser
    - resmed_loader: ResMed CPAP device data loader
"""

from .edf_parser import (
    # Classes
    EDFParser,
    EDFSignal,
    EDFHeader,
    Annotation,
    # Enums
    EDFType,
    # Constants
    STR_EXT_EDF,
    STR_EXT_GZ,
    EDF_HEADER_SIZE,
    # Utility functions
    print_edf_info,
)

from .resmed_loader import (
    # Main loader class
    ResmedLoader,
    # Data structures
    ResmedDay,
    STRRecord,
    WaveformData,
    EventData,
    EDFInfo,
    # Functions
    parse_edf,
    load_brp,
    load_pld,
    load_eve,
    load_csl,
    load_sad,
    lookup_edf_type,
    match_signal,
    find_channel_for_label,
    # Constants
    RESMED_SIGNAL_MAP,
    RESMED_DATA_VERSION,
)

__all__ = [
    # EDF Parser Classes
    "EDFParser",
    "EDFSignal",
    "EDFHeader",
    "Annotation",
    # EDF Enums
    "EDFType",
    # EDF Constants
    "STR_EXT_EDF",
    "STR_EXT_GZ",
    "EDF_HEADER_SIZE",
    # EDF Functions
    "print_edf_info",
    # ResMed Loader
    "ResmedLoader",
    "ResmedDay",
    "STRRecord",
    "WaveformData",
    "EventData",
    "EDFInfo",
    "parse_edf",
    "load_brp",
    "load_pld",
    "load_eve",
    "load_csl",
    "load_sad",
    "lookup_edf_type",
    "match_signal",
    "find_channel_for_label",
    "RESMED_SIGNAL_MAP",
    "RESMED_DATA_VERSION",
]
