"""
SleepLib Schema - Channel and Type Definitions

This module contains the channel definitions and enumerations used throughout
the SleepLib data model, ported from the C++ OSCAR codebase.

Copyright (c) 2019-2025 The OSCAR Team
License: GPL v3
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import IntEnum, IntFlag, auto
from typing import Dict, Optional, List, Callable
import xml.etree.ElementTree as ET
from pathlib import Path


# Type aliases matching C++ types
ChannelID = int
MachineID = int
SessionID = int
EventDataType = float


class MachineType(IntEnum):
    """Generalized type of device.

    MT_CPAP is any type of xPAP device, MT_OXIMETER any type of Oximeter,
    MT_SLEEPSTAGE for sleep stage detector (ZEO), MT_JOURNAL for notes,
    MT_POSITION for sleep position detector (Somnopose).
    """
    MT_UNKNOWN = 0
    MT_CPAP = 1
    MT_OXIMETER = 2
    MT_SLEEPSTAGE = 3
    MT_JOURNAL = 4
    MT_POSITION = 5
    MT_UNCATEGORIZED = 99


class CPAPMode(IntEnum):
    """CPAP Machine mode of operation."""
    MODE_UNKNOWN = 0
    MODE_CPAP = 1
    MODE_APAP = 2
    MODE_BILEVEL_FIXED = 3
    MODE_BILEVEL_AUTO_FIXED_PS = 4
    MODE_BILEVEL_AUTO_VARIABLE_PS = 5
    MODE_ASV = 6
    MODE_ASV_VARIABLE_EPAP = 7
    MODE_AVAPS = 8
    MODE_TRILEVEL_AUTO_VARIABLE_PDIFF = 9


class PRTypes(IntEnum):
    """Pressure Relief Types used by CPAP devices."""
    PR_UNKNOWN = 0
    PR_NONE = 1
    PR_CFLEX = 2
    PR_CFLEXPLUS = 3
    PR_AFLEX = 4
    PR_BIFLEX = 5
    PR_EPR = 6
    PR_SMARTFLEX = 7
    PR_EASYBREATHE = 8
    PR_SENSAWAKE = 9


class PRTimeModes(IntEnum):
    """Pressure Relief Time Modes."""
    PM_UNKNOWN = 0
    PM_RampOnly = 1
    PM_FullTime = 2


class ChanType(IntFlag):
    """Channel type flags defining the type of data channel.

    Bit flags so multiple settings are possible.
    - DATA: A single number such as Height, ZombieMeter
    - SETTING: Device setting, such as EPR, temperature, Ramp enabled
    - FLAG: Event flags reported by CPAP device
    - MINOR_FLAG: More event flags such as PressurePulse and TimedBreath
    - SPAN: A flag that has a timespan associated with it (CSR, LeakSpan, Ramp)
    - WAVEFORM: A waveform such as flow rate
    - UNKNOWN: Some PRS1 flags, not sure what they are for
    """
    DATA = 1
    SETTING = 2
    FLAG = 4
    MINOR_FLAG = 8
    SPAN = 16
    WAVEFORM = 32
    UNKNOWN = 64
    ALL = 0xFFFF


class DataType(IntEnum):
    """Data types stored by Profile/Preferences objects."""
    DEFAULT = 0
    INTEGER = 1
    BOOL = 2
    DOUBLE = 3
    STRING = 4
    RICHTEXT = 5
    DATE = 6
    TIME = 7
    DATETIME = 8
    LOOKUP = 9


class ScopeType(IntEnum):
    """Scope of the channel data."""
    GLOBAL = 0
    MACHINE = 1
    DAY = 2
    SESSION = 3


class SummaryType(IntEnum):
    """Calculation/Display method for summary information."""
    ST_CNT = 0
    ST_SUM = 1
    ST_AVG = 2
    ST_WAVG = 3
    ST_PERC = 4
    ST_90P = 5
    ST_MIN = 6
    ST_MAX = 7
    ST_MID = 8
    ST_CPH = 9
    ST_SPH = 10
    ST_FIRST = 11
    ST_LAST = 12
    ST_HOURS = 13
    ST_SESSIONS = 14
    ST_SETMIN = 15
    ST_SETAVG = 16
    ST_SETMAX = 17
    ST_SETWAVG = 18
    ST_SETSUM = 19
    ST_SESSIONID = 20
    ST_DATE = 21


class Function(IntEnum):
    """Schema function types for calculations."""
    NONE = 0
    AVG = 1
    WAVG = 2
    MIN = 3
    MAX = 4
    SUM = 5
    CNT = 6
    P90 = 7
    CPH = 8
    SPH = 9
    HOURS = 10
    SET = 11


class ChannelCalcType(IntEnum):
    """Channel calculation types."""
    Calc_Zero = 0
    Calc_Min = 1
    Calc_Middle = 2
    Calc_Perc = 3
    Calc_Max = 4
    Calc_UpperThresh = 5
    Calc_LowerThresh = 6


@dataclass
class ChannelCalc:
    """Channel calculation information."""
    code: ChannelID = 0
    calc_type: ChannelCalcType = ChannelCalcType.Calc_Zero
    color: str = "black"
    enabled: bool = False


@dataclass
class Channel:
    """Contains information about a SleepLib data Channel (signal).

    Attributes:
        id: Unique identifier of channel
        chan_type: Type of channel (WAVEFORM, FLAG, etc.)
        machtype: Type of device (CPAP, Oximeter, etc.)
        scope: Scope of the data
        code: Unique string identifier (not translated, used as graph key)
        fullname: Full name of channel (translatable)
        description: Short description (translatable, used in tooltips)
        label: Short-form label (translatable, used for graph labels)
        unit: Units string (cmH2O, events per hour, etc.)
        datatype: Data format (integer vs RTF, etc.)
        default_color: Default color for plotting
        link_id: Links to better versions of this data type
        upper_threshold: Upper threshold for calculations
        lower_threshold: Lower threshold for calculations
        enabled: Whether channel is enabled
        order: Sort order for event flags
        show_in_overview: Whether to show in Overview page
    """
    id: ChannelID = 0
    chan_type: ChanType = ChanType.DATA
    machtype: MachineType = MachineType.MT_UNKNOWN
    scope: ScopeType = ScopeType.SESSION
    code: str = ""
    fullname: str = ""
    description: str = ""
    label: str = ""
    unit: str = ""
    datatype: DataType = DataType.DEFAULT
    default_color: str = "black"
    link_id: ChannelID = 0
    upper_threshold: EventDataType = 0.0
    lower_threshold: EventDataType = 0.0
    upper_threshold_color: str = "red"
    lower_threshold_color: str = "green"
    enabled: bool = True
    order: int = 255
    show_in_overview: bool = False
    options: Dict[int, str] = field(default_factory=dict)
    colors: Dict[Function, str] = field(default_factory=dict)
    links: List['Channel'] = field(default_factory=list)
    calc: Dict[ChannelCalcType, ChannelCalc] = field(default_factory=dict)

    def is_null(self) -> bool:
        """Check if this is an empty channel."""
        return self.id == 0 and self.code == "Empty"

    def add_option(self, i: int, option: str) -> None:
        """Add an option value."""
        self.options[i] = option

    def add_color(self, func: Function, color: str) -> None:
        """Add a color for a function."""
        self.colors[func] = color

    def option(self, i: int) -> Optional[str]:
        """Get option value by index."""
        return self.options.get(i)


# Empty channel singleton
EmptyChannel = Channel(id=0, code="Empty", fullname="Empty", description="Empty Channel")


class ChannelList:
    """A list containing Channel objects with XML storage capability."""

    def __init__(self):
        self.channels: Dict[ChannelID, Channel] = {}
        self.names: Dict[str, Channel] = {}
        self.groups: Dict[str, Dict[str, Channel]] = {}
        self._doctype = "channels"

    def __getitem__(self, key) -> Channel:
        """Get channel by ID or name."""
        if isinstance(key, int):
            return self.channels.get(key, EmptyChannel)
        elif isinstance(key, str):
            return self.names.get(key, EmptyChannel)
        return EmptyChannel

    def add(self, group: str, chan: Channel) -> None:
        """Add a channel to the list."""
        if chan is None:
            raise ValueError("Cannot add None channel")

        if chan.id in self.channels:
            raise ValueError(f"Channel ID {chan.id} already exists")

        if chan.code in self.names:
            raise ValueError(f"Channel code {chan.code} already exists")

        self.channels[chan.id] = chan
        self.names[chan.code] = chan

        if group not in self.groups:
            self.groups[group] = {}
        self.groups[group][chan.code] = chan

        # Handle linked channels
        if chan.link_id > 0 and chan.link_id in self.channels:
            linked = self.channels[chan.link_id]
            linked.links.append(chan)

    def load(self, filename: str) -> bool:
        """Load channel list from XML file."""
        try:
            tree = ET.parse(filename)
            root = tree.getroot()

            if root.tag.lower() != "channels":
                return False

            for grp_elem in root.findall("group"):
                group = grp_elem.get("name", "")

                for ch_elem in grp_elem.findall("channel"):
                    id_str = ch_elem.get("id", "0")
                    try:
                        chan_id = int(id_str, 16)
                    except ValueError:
                        continue

                    chan = Channel(
                        id=chan_id,
                        code=ch_elem.get("name", ""),
                        description=ch_elem.get("details", ""),
                        label=ch_elem.get("label", ""),
                        unit=ch_elem.get("unit", ""),
                        default_color=ch_elem.get("color", "black"),
                    )

                    # Parse options
                    for opt_elem in ch_elem.findall("option"):
                        opt_id = int(opt_elem.get("id", "0"))
                        opt_value = opt_elem.get("value", "")
                        chan.add_option(opt_id, opt_value)

                    try:
                        self.add(group, chan)
                    except ValueError:
                        continue

            return True
        except Exception as e:
            print(f"Error loading channels: {e}")
            return False

    def save(self, filename: str) -> bool:
        """Save channel list to XML file."""
        root = ET.Element("channels")

        for group_name, chanlist in self.groups.items():
            grp = ET.SubElement(root, "group", name=group_name)

            for code, chan in chanlist.items():
                ch_elem = ET.SubElement(grp, "channel")
                ch_elem.set("id", f"0x{chan.id:04x}")
                ch_elem.set("code", code)
                ch_elem.set("label", chan.label)
                ch_elem.set("name", chan.fullname)
                ch_elem.set("description", chan.description)
                ch_elem.set("color", chan.default_color)

                for opt_id, opt_value in chan.options.items():
                    opt_elem = ET.SubElement(ch_elem, "option")
                    opt_elem.set("key", str(opt_id))
                    opt_elem.set("value", opt_value)

        tree = ET.ElementTree(root)
        try:
            tree.write(filename, encoding="utf-8", xml_declaration=True)
            return True
        except Exception as e:
            print(f"Error saving channels: {e}")
            return False


# Global channel list
channel = ChannelList()


# ============================================================================
# Channel ID Constants
# These match the C++ ChannelID values defined in machine_common.h and schema.cpp
# ============================================================================

# Special channels
NoChannel: ChannelID = 0
SESSION_ENABLED: ChannelID = 1

# CPAP Pressure channels
CPAP_Pressure: ChannelID = 0x110C
CPAP_IPAP: ChannelID = 0x110D
CPAP_IPAPLo: ChannelID = 0x1110
CPAP_IPAPHi: ChannelID = 0x1111
CPAP_EPAP: ChannelID = 0x110E
CPAP_EPAPLo: ChannelID = 0x111C
CPAP_EPAPHi: ChannelID = 0x111D
CPAP_EEPAP: ChannelID = 0x11A7
CPAP_EEPAPLo: ChannelID = 0x11A8
CPAP_EEPAPHi: ChannelID = 0x11A9
CPAP_PS: ChannelID = 0x110F
CPAP_PSMin: ChannelID = 0x111A
CPAP_PSMax: ChannelID = 0x111B
CPAP_PressureMin: ChannelID = 0x1020
CPAP_PressureMax: ChannelID = 0x1021
CPAP_RampTime: ChannelID = 0x1022
CPAP_RampPressure: ChannelID = 0x1023
CPAP_Ramp: ChannelID = 0x1027
CPAP_PressureSet: ChannelID = 0x11A4
CPAP_IPAPSet: ChannelID = 0x11A5
CPAP_EPAPSet: ChannelID = 0x11A6

# CPAP Event Flags
CPAP_CSR: ChannelID = 0x1000
CPAP_PB: ChannelID = 0x1028
CPAP_ClearAirway: ChannelID = 0x1001
CPAP_Obstructive: ChannelID = 0x1002
CPAP_Hypopnea: ChannelID = 0x1003
CPAP_Apnea: ChannelID = 0x1004
CPAP_AllApnea: ChannelID = 0x1010
CPAP_FlowLimit: ChannelID = 0x1005
CPAP_RERA: ChannelID = 0x1006
CPAP_VSnore: ChannelID = 0x1007
CPAP_VSnore2: ChannelID = 0x1008
CPAP_LeakFlag: ChannelID = 0x100a
CPAP_LargeLeak: ChannelID = 0x1158
CPAP_NRI: ChannelID = 0x100b
CPAP_ExP: ChannelID = 0x100c
CPAP_SensAwake: ChannelID = 0x100d
CPAP_UserFlag1: ChannelID = 0x101e
CPAP_UserFlag2: ChannelID = 0x101f
CPAP_UserFlag3: ChannelID = 0x1024

# CPAP Waveforms
CPAP_FlowRate: ChannelID = 0x1100
CPAP_MaskPressure: ChannelID = 0x1101
CPAP_MaskPressureHi: ChannelID = 0x1102
CPAP_TidalVolume: ChannelID = 0x1103
CPAP_Snore: ChannelID = 0x1104
CPAP_MinuteVent: ChannelID = 0x1105
CPAP_RespRate: ChannelID = 0x1106
CPAP_PTB: ChannelID = 0x1107
CPAP_Leak: ChannelID = 0x1108
CPAP_IE: ChannelID = 0x1109
CPAP_Te: ChannelID = 0x110A
CPAP_Ti: ChannelID = 0x110B
CPAP_RespEvent: ChannelID = 0x1112
CPAP_FLG: ChannelID = 0x1113
CPAP_TgMV: ChannelID = 0x1114
CPAP_MaxLeak: ChannelID = 0x1115
CPAP_AHI: ChannelID = 0x1116
CPAP_LeakTotal: ChannelID = 0x1117
CPAP_LeakMedian: ChannelID = 0x1118
CPAP_RDI: ChannelID = 0x1119

# CPAP Settings
CPAP_Mode: ChannelID = 0x1200
CPAP_SummaryOnly: ChannelID = 0x1026
CPAP_PresReliefMode: ChannelID = 0
CPAP_PresReliefLevel: ChannelID = 0
CPAP_HumidSetting: ChannelID = 0

# Test channels
CPAP_Test1: ChannelID = 0x111e
CPAP_Test2: ChannelID = 0x111f

# Oximeter channels
OXI_Pulse: ChannelID = 0x1800
OXI_SPO2: ChannelID = 0x1801
OXI_Plethy: ChannelID = 0x1802
OXI_PulseChange: ChannelID = 0x1803
OXI_SPO2Drop: ChannelID = 0x1804
OXI_Perf: ChannelID = 0x1805

# Journal channels
Journal_Notes: ChannelID = 0xd000
Journal_Weight: ChannelID = 0x0803
Journal_BMI: ChannelID = 0x0806
Journal_ZombieMeter: ChannelID = 0x0807
Bookmark_Start: ChannelID = 0x0808
Bookmark_End: ChannelID = 0x0809
Bookmark_Notes: ChannelID = 0x0805
LastUpdated: ChannelID = 0x080a

# Position sensor channels
POS_Orientation: ChannelID = 0x2990
POS_Inclination: ChannelID = 0x2991
POS_Movement: ChannelID = 0x2992

# Sleep stage channels (ZEO)
ZEO_SleepStage: ChannelID = 0x2000
ZEO_ZQ: ChannelID = 0x2009
ZEO_TotalZ: ChannelID = 0
ZEO_TimeToZ: ChannelID = 0x2008
ZEO_TimeInWake: ChannelID = 0x2004
ZEO_TimeInREM: ChannelID = 0x2005
ZEO_TimeInLight: ChannelID = 0x2006
ZEO_TimeInDeep: ChannelID = 0x2007
ZEO_Awakenings: ChannelID = 0x2002
ZEO_MorningFeel: ChannelID = 0x2003

# Manufacturer-specific channels
RMS9_MaskOnTime: ChannelID = 0x1025
RMS9_E01: ChannelID = 0
RMS9_E02: ChannelID = 0
RMS9_SetPressure: ChannelID = 0
PRS1_BND: ChannelID = 0
BMC_PressureWave: ChannelID = 0x1210
BMC_FlowAbnormality: ChannelID = 0x1211
BMC_IE_Ratio: ChannelID = 0x1212

# Group names
GRP_CPAP = "CPAP"
GRP_POS = "POS"
GRP_OXI = "OXI"
GRP_JOURNAL = "JOURNAL"
GRP_SLEEP = "SLEEP"

# Unit strings
STR_UNIT_CMH2O = "cmH2O"
STR_UNIT_LPM = "L/min"
STR_UNIT_BPM = "bpm"
STR_UNIT_Percentage = "%"
STR_UNIT_EventsPerHour = "events/hr"
STR_UNIT_Minutes = "min"
STR_UNIT_Seconds = "s"
STR_UNIT_ml = "ml"
STR_UNIT_Hz = "Hz"
STR_UNIT_Ratio = "ratio"
STR_UNIT_Degrees = "deg"
STR_UNIT_KG = "kg"
STR_UNIT_CM = "cm"
STR_UNIT_Unknown = ""
STR_UNIT_BreathsPerMinute = "br/min"
STR_UNIT_Severity = ""

# AHI contributing channels
ahiChannels: List[ChannelID] = [
    CPAP_ClearAirway,
    CPAP_AllApnea,
    CPAP_Obstructive,
    CPAP_Hypopnea,
    CPAP_Apnea,
]


def init_channels() -> None:
    """Initialize the channel schema with default channels.

    This is the Python equivalent of schema::init() in C++.
    """
    global channel

    # Add pressure-related channels
    channel.add(GRP_CPAP, Channel(
        id=CPAP_Pressure, chan_type=ChanType.WAVEFORM, machtype=MachineType.MT_CPAP,
        scope=ScopeType.SESSION, code="Pressure", fullname="Pressure",
        description="Therapy Pressure", label="Pressure", unit=STR_UNIT_CMH2O,
        default_color="red"
    ))

    channel.add(GRP_CPAP, Channel(
        id=CPAP_IPAP, chan_type=ChanType.WAVEFORM, machtype=MachineType.MT_CPAP,
        scope=ScopeType.SESSION, code="IPAP", fullname="IPAP",
        description="Inspiratory Pressure", label="IPAP", unit=STR_UNIT_CMH2O,
        default_color="red"
    ))

    channel.add(GRP_CPAP, Channel(
        id=CPAP_EPAP, chan_type=ChanType.WAVEFORM, machtype=MachineType.MT_CPAP,
        scope=ScopeType.SESSION, code="EPAP", fullname="EPAP",
        description="Expiratory Pressure", label="EPAP", unit=STR_UNIT_CMH2O,
        default_color="green"
    ))

    # Add event flags
    channel.add(GRP_CPAP, Channel(
        id=CPAP_Obstructive, chan_type=ChanType.FLAG, machtype=MachineType.MT_CPAP,
        scope=ScopeType.SESSION, code="Obstructive", fullname="Obstructive Apnea (OA)",
        description="An apnea caused by airway obstruction", label="OA",
        unit=STR_UNIT_EventsPerHour, default_color="#40c0ff"
    ))

    channel.add(GRP_CPAP, Channel(
        id=CPAP_Hypopnea, chan_type=ChanType.FLAG, machtype=MachineType.MT_CPAP,
        scope=ScopeType.SESSION, code="Hypopnea", fullname="Hypopnea (H)",
        description="A partially obstructed airway", label="H",
        unit=STR_UNIT_EventsPerHour, default_color="blue"
    ))

    channel.add(GRP_CPAP, Channel(
        id=CPAP_ClearAirway, chan_type=ChanType.FLAG, machtype=MachineType.MT_CPAP,
        scope=ScopeType.SESSION, code="ClearAirway", fullname="Clear Airway (CA)",
        description="An apnea where the airway is open", label="CA",
        unit=STR_UNIT_EventsPerHour, default_color="purple"
    ))

    channel.add(GRP_CPAP, Channel(
        id=CPAP_AHI, chan_type=ChanType.WAVEFORM, machtype=MachineType.MT_CPAP,
        scope=ScopeType.SESSION, code="AHI", fullname="Apnea Hypopnea Index (AHI)",
        description="Graph showing running AHI for the past hour", label="AHI",
        unit=STR_UNIT_EventsPerHour, default_color="dark red"
    ))

    # Add waveforms
    channel.add(GRP_CPAP, Channel(
        id=CPAP_FlowRate, chan_type=ChanType.WAVEFORM, machtype=MachineType.MT_CPAP,
        scope=ScopeType.SESSION, code="FlowRate", fullname="Flow Rate",
        description="Breathing flow rate waveform", label="Flow Rate",
        unit=STR_UNIT_LPM, default_color="black"
    ))

    channel.add(GRP_CPAP, Channel(
        id=CPAP_Leak, chan_type=ChanType.WAVEFORM, machtype=MachineType.MT_CPAP,
        scope=ScopeType.SESSION, code="LeakRate", fullname="Leak Rate",
        description="Rate of detected mask leakage", label="Leak Rate",
        unit=STR_UNIT_LPM, default_color="dark green", lower_threshold=24.0,
        show_in_overview=True
    ))

    # Add oximetry channels
    channel.add(GRP_OXI, Channel(
        id=OXI_Pulse, chan_type=ChanType.WAVEFORM, machtype=MachineType.MT_OXIMETER,
        scope=ScopeType.SESSION, code="Pulse", fullname="Pulse Rate",
        description="Heart rate in beats per minute", label="Pulse Rate",
        unit=STR_UNIT_BPM, default_color="red"
    ))

    channel.add(GRP_OXI, Channel(
        id=OXI_SPO2, chan_type=ChanType.WAVEFORM, machtype=MachineType.MT_OXIMETER,
        scope=ScopeType.SESSION, code="SPO2", fullname="SpO2 %",
        description="Blood-oxygen saturation percentage", label="SpO2",
        unit=STR_UNIT_Percentage, default_color="blue"
    ))

    # Add CPAP mode setting
    mode_chan = Channel(
        id=CPAP_Mode, chan_type=ChanType.SETTING, machtype=MachineType.MT_CPAP,
        scope=ScopeType.SESSION, code="PAPMode", fullname="PAP Mode",
        description="PAP Device Mode", label="PAP Mode",
        datatype=DataType.LOOKUP, default_color="black"
    )
    mode_chan.add_option(0, "Unknown")
    mode_chan.add_option(1, "CPAP")
    mode_chan.add_option(2, "APAP (Variable)")
    mode_chan.add_option(3, "Fixed Bi-Level")
    mode_chan.add_option(4, "Auto Bi-Level (Fixed PS)")
    mode_chan.add_option(5, "Auto Bi-Level (Variable PS)")
    mode_chan.add_option(6, "ASV (Fixed EPAP)")
    mode_chan.add_option(7, "ASV (Variable EPAP)")
    mode_chan.add_option(8, "AVAPS")
    channel.add(GRP_CPAP, mode_chan)


def reset_channels() -> None:
    """Reset and reinitialize channel schema."""
    global channel
    channel = ChannelList()
    init_channels()
