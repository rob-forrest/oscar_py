"""
SleepLib - Python Port of OSCAR Sleep Data Library

This package provides the core data structures for managing sleep
therapy device data, ported from the C++ OSCAR application.

Copyright (c) 2019-2025 The OSCAR Team
License: GPL v3

Main Classes:
    - Preferences: Base class for storing settings
    - Profile: User profile with device data and settings
    - Machine: Device class representing a single device
    - Channel: Information about a data channel/signal

Enumerations:
    - MachineType: Types of devices (CPAP, Oximeter, etc.)
    - CPAPMode: CPAP operating modes
    - ChanType: Types of data channels
    - DataType: Data storage types

Example Usage:
    from oscar_py.sleeplib import Profile, Machine, MachineType
    from oscar_py.sleeplib.schema import CPAP_AHI, CPAP_Leak

    # Create or load a profile
    profile = Profile("/path/to/profile")

    # Access machines
    for machine in profile.get_machines(MachineType.MT_CPAP):
        print(f"Device: {machine.brand} {machine.model}")

    # Access settings
    print(f"Compliance hours: {profile.cpap.compliance_hours}")
"""

from .preferences import (
    Preferences,
    PrefSettings,
    get_app_data,
    get_user_name,
    STR_APP_NAME,
    STR_EXT_XML,
)

from .schema import (
    # Type aliases
    ChannelID,
    MachineID,
    SessionID,
    EventDataType,
    # Enumerations
    MachineType,
    CPAPMode,
    PRTypes,
    PRTimeModes,
    ChanType,
    DataType,
    ScopeType,
    SummaryType,
    Function,
    ChannelCalcType,
    # Classes
    Channel,
    ChannelCalc,
    ChannelList,
    EmptyChannel,
    # Global channel list
    channel,
    # Channel ID constants
    NoChannel,
    CPAP_Pressure,
    CPAP_IPAP,
    CPAP_EPAP,
    CPAP_PS,
    CPAP_FlowRate,
    CPAP_Leak,
    CPAP_AHI,
    CPAP_Obstructive,
    CPAP_Hypopnea,
    CPAP_ClearAirway,
    CPAP_Mode,
    OXI_Pulse,
    OXI_SPO2,
    # Group names
    GRP_CPAP,
    GRP_OXI,
    GRP_POS,
    GRP_JOURNAL,
    GRP_SLEEP,
    # Unit strings
    STR_UNIT_CMH2O,
    STR_UNIT_LPM,
    STR_UNIT_BPM,
    STR_UNIT_Percentage,
    STR_UNIT_EventsPerHour,
    # Functions
    init_channels,
    reset_channels,
)

from .machine import (
    Machine,
    MachineInfo,
    Day,
    CPAP,
    Oximeter,
    SleepStage,
    PositionSensor,
    to_hexid,
    generate_machine_id,
)

from .session import (
    Session,
    SessionSlice,
    SliceStatus,
)

from .event import (
    EventList,
    EventListType,
)

from .profile import (
    Profile,
    # Settings classes
    DoctorInfo,
    UserInfo,
    OxiSettings,
    CPAPSettings,
    SessionSettings,
    UserSettings,
    # Enumerations
    Gender,
    MaskType,
    UnitSystem,
    # Profile management
    profiles,
    scan_profiles,
    done_profiles,
    create_profile,
    get_profile,
    # Setting key constants
    STR_CS_ComplianceHours,
    STR_CS_ClinicalMode,
    STR_CS_MaskType,
    STR_UI_FirstName,
    STR_UI_LastName,
)

__version__ = "0.1.0"
__all__ = [
    # Version
    "__version__",
    # Preferences
    "Preferences",
    "PrefSettings",
    "get_app_data",
    "get_user_name",
    "STR_APP_NAME",
    "STR_EXT_XML",
    # Schema types
    "ChannelID",
    "MachineID",
    "SessionID",
    "EventDataType",
    # Schema enums
    "MachineType",
    "CPAPMode",
    "PRTypes",
    "PRTimeModes",
    "ChanType",
    "DataType",
    "ScopeType",
    "SummaryType",
    "Function",
    "ChannelCalcType",
    # Schema classes
    "Channel",
    "ChannelCalc",
    "ChannelList",
    "EmptyChannel",
    "channel",
    # Channel constants
    "NoChannel",
    "CPAP_Pressure",
    "CPAP_IPAP",
    "CPAP_EPAP",
    "CPAP_PS",
    "CPAP_FlowRate",
    "CPAP_Leak",
    "CPAP_AHI",
    "CPAP_Obstructive",
    "CPAP_Hypopnea",
    "CPAP_ClearAirway",
    "CPAP_Mode",
    "OXI_Pulse",
    "OXI_SPO2",
    # Groups
    "GRP_CPAP",
    "GRP_OXI",
    "GRP_POS",
    "GRP_JOURNAL",
    "GRP_SLEEP",
    # Units
    "STR_UNIT_CMH2O",
    "STR_UNIT_LPM",
    "STR_UNIT_BPM",
    "STR_UNIT_Percentage",
    "STR_UNIT_EventsPerHour",
    # Schema functions
    "init_channels",
    "reset_channels",
    # Machine classes
    "Machine",
    "MachineInfo",
    "Day",
    "CPAP",
    "Oximeter",
    "SleepStage",
    "PositionSensor",
    "to_hexid",
    "generate_machine_id",
    # Session classes
    "Session",
    "SessionSlice",
    "SliceStatus",
    # Event classes
    "EventList",
    "EventListType",
    # Profile
    "Profile",
    "DoctorInfo",
    "UserInfo",
    "OxiSettings",
    "CPAPSettings",
    "SessionSettings",
    "UserSettings",
    "Gender",
    "MaskType",
    "UnitSystem",
    "profiles",
    "scan_profiles",
    "done_profiles",
    "create_profile",
    "get_profile",
    # Setting keys
    "STR_CS_ComplianceHours",
    "STR_CS_ClinicalMode",
    "STR_CS_MaskType",
    "STR_UI_FirstName",
    "STR_UI_LastName",
]
