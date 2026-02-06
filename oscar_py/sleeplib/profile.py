"""
SleepLib Profile - User Profile Implementation

This module provides the Profile class and related settings classes
for managing user profiles, ported from the C++ OSCAR codebase.

Copyright (c) 2019-2025 The OSCAR Team
License: GPL v3
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, date, time
from pathlib import Path
from typing import Dict, Optional, List, Any
from enum import IntEnum
import hashlib
import xml.etree.ElementTree as ET
from xml.dom import minidom

from .preferences import Preferences, PrefSettings, get_app_data, STR_APP_NAME
from .schema import (
    MachineType, MachineID, ChannelID, EventDataType, CPAPMode
)
from .machine import Machine, MachineInfo, Day, Session, CPAP, Oximeter


class Gender(IntEnum):
    """User gender enumeration."""
    GenderNotSpecified = 0
    Male = 1
    Female = 2


class MaskType(IntEnum):
    """CPAP mask type enumeration."""
    Mask_Unknown = 0
    Mask_NasalPillows = 1
    Mask_Hybrid = 2
    Mask_StandardNasal = 3
    Mask_FullFace = 4


class UnitSystem(IntEnum):
    """Unit system enumeration."""
    US_Metric = 0
    US_Imperial = 1


# ============================================================================
# Preference Key Constants
# ============================================================================

# Doctor Info Keys
STR_DI_Name = "DoctorName"
STR_DI_Phone = "DoctorPhone"
STR_DI_Email = "DoctorEmail"
STR_DI_Practice = "DoctorPractice"
STR_DI_Address = "DoctorAddress"
STR_DI_PatientID = "DoctorPatientID"

# User Info Keys
STR_UI_DOB = "DOB"
STR_UI_FirstName = "FirstName"
STR_UI_LastName = "LastName"
STR_UI_UserName = "UserName"
STR_UI_Password = "Password"
STR_UI_Address = "Address"
STR_UI_Phone = "Phone"
STR_UI_EmailAddress = "EmailAddress"
STR_UI_Country = "Country"
STR_UI_Height = "Height"
STR_UI_Gender = "Gender"
STR_UI_TimeZone = "TimeZone"
STR_UI_DST = "DST"

# Oximetry Settings Keys
STR_OS_EnableOximetry = "EnableOximetry"
STR_OS_DefaultDevice = "DefaultOxiDevice"
STR_OS_SyncOximeterClock = "SyncOximeterClock"
STR_OS_OximeterType = "OximeterType"
STR_OS_SkipOxiIntroScreen = "SkipOxiIntroScreen"
STR_OS_SPO2DropDuration = "SPO2DropDuration"
STR_OS_SPO2DropPercentage = "SPO2DropPercentage"
STR_OS_PulseChangeDuration = "PulseChangeDuration"
STR_OS_PulseChangeBPM = "PulseChangeBPM"
STR_OS_oxiDesaturationThreshold = "oxiDesaturationThreshold"
STR_OS_flagPulseAbove = "flagPulseAbove"
STR_OS_flagPulseBelow = "flagPulseBelow"
STR_OS_OxiDiscardThreshold = "OxiDiscardThreshold"

# CPAP Settings Keys
STR_CS_ComplianceHours = "ComplianceHours"
STR_CS_ClinicalMode = "ClinicalMode"
STR_CS_ZombieMode = "ZombieMode"
STR_CS_ShowLeaksMode = "ShowLeaksMode"
STR_CS_MaskStartDate = "MaskStartDate"
STR_CS_MaskDescription = "MaskDescription"
STR_CS_MaskType = "MaskType"
STR_CS_PrescribedMode = "CPAPPrescribedMode"
STR_CS_PrescribedMinPressure = "CPAPPrescribedMinPressure"
STR_CS_PrescribedMaxPressure = "CPAPPrescribedMaxPressure"
STR_CS_UntreatedAHI = "UntreatedAHI"
STR_CS_Notes = "CPAPNotes"
STR_CS_DateDiagnosed = "DateDiagnosed"
STR_CS_UserEventFlagging = "UserEventFlagging"
STR_CS_AutoImport = "AutoImport"
STR_CS_BrickWarning = "BrickWarning"
STR_CS_UserFlowRestriction = "UserFlowRestriction"
STR_CS_UserEventDuration = "UserEventDuration"
STR_CS_UserFlowRestriction2 = "UserFlowRestriction2"
STR_CS_UserEventDuration2 = "UserEventDuration2"
STR_CS_UserEventDuplicates = "UserEventDuplicates"
STR_CS_ResyncFromUserFlagging = "ResyncFromUserFlagging"
STR_CS_AHIWindow = "AHIWindow"
STR_CS_AHIReset = "AHIReset"
STR_CS_ClockDrift = "ClockDrift"
STR_CS_LeakRedline = "LeakRedline"
STR_CS_ShowLeakRedline = "ShowLeakRedline"
STR_CS_CalculateUnintentionalLeaks = "CalculateUnintentionalLeaks"
STR_CS_4cmH2OLeaks = "Custom4cmH2OLeaks"
STR_CS_20cmH2OLeaks = "Custom20cmH2OLeaks"
STR_CS_EventPostcontext = "EventPostcontext"
STR_CS_ConsolidateEvents = "ConsolidateEvents"

# Import/Session Settings Keys
STR_IS_DaySplitTime = "DaySplitTime"
STR_IS_PreloadSummaries = "PreloadSummaries"
STR_IS_CombineCloseSessions = "CombineCloserSessions"
STR_IS_IgnoreShorterSessions = "IgnoreShorterSessions"
STR_IS_BackupCardData = "BackupCardData"
STR_IS_CompressBackupData = "CompressBackupData"
STR_IS_CompressSessionData = "CompressSessionData"
STR_IS_IgnoreOlderSessions = "IgnoreOlderSessions"
STR_IS_IgnoreOlderSessionsDate = "IgnoreOlderSessionsDate"
STR_IS_LockSummarySessions = "LockSummarySessions"
STR_IS_WarnOnUntestedMachine = "WarnOnUntestedMachine"
STR_IS_WarnOnUnexpectedData = "WarnOnUnexpectedData"

# User Settings Keys
STR_US_UnitSystem = "UnitSystem"
STR_US_EventWindowSize = "EventWindowSize"
STR_US_SkipEmptyDays = "SkipEmptyDays"
STR_US_RebuildCache = "RebuildCache"
STR_US_CalculateRDI = "CalculateRDI"
STR_US_PrefCalcMiddle = "PrefCalcMiddle"
STR_US_PrefCalcPercentile = "PrefCalcPercentile"
STR_US_PrefCalcMax = "PrefCalcMax"
STR_US_ShowUnknownFlags = "ShowUnknownFlags"
STR_US_StatReportMode = "StatReportMode"

# Stat report modes
STAT_MODE_STANDARD = 0
STAT_MODE_MONTHLY = 1
STAT_MODE_RANGE = 2


class DoctorInfo(PrefSettings):
    """Profile options relating to doctor information."""

    def __init__(self, profile: 'Profile'):
        super().__init__(profile)
        self.init_pref(STR_DI_Name, "")
        self.init_pref(STR_DI_Phone, "")
        self.init_pref(STR_DI_Email, "")
        self.init_pref(STR_DI_Practice, "")
        self.init_pref(STR_DI_Address, "")
        self.init_pref(STR_DI_PatientID, "")

    @property
    def name(self) -> str:
        return str(self.get_pref(STR_DI_Name) or "")

    @name.setter
    def name(self, value: str) -> None:
        self.set_pref(STR_DI_Name, value)

    @property
    def phone(self) -> str:
        return str(self.get_pref(STR_DI_Phone) or "")

    @phone.setter
    def phone(self, value: str) -> None:
        self.set_pref(STR_DI_Phone, value)

    @property
    def email(self) -> str:
        return str(self.get_pref(STR_DI_Email) or "")

    @email.setter
    def email(self, value: str) -> None:
        self.set_pref(STR_DI_Email, value)

    @property
    def practice_name(self) -> str:
        return str(self.get_pref(STR_DI_Practice) or "")

    @practice_name.setter
    def practice_name(self, value: str) -> None:
        self.set_pref(STR_DI_Practice, value)

    @property
    def address(self) -> str:
        return str(self.get_pref(STR_DI_Address) or "")

    @address.setter
    def address(self, value: str) -> None:
        self.set_pref(STR_DI_Address, value)

    @property
    def patient_id(self) -> str:
        return str(self.get_pref(STR_DI_PatientID) or "")

    @patient_id.setter
    def patient_id(self, value: str) -> None:
        self.set_pref(STR_DI_PatientID, value)


class UserInfo(PrefSettings):
    """Profile options relating to user information."""

    def __init__(self, profile: 'Profile'):
        super().__init__(profile)
        self.init_pref(STR_UI_DOB, date(1970, 1, 1))
        self.init_pref(STR_UI_FirstName, "")
        self.init_pref(STR_UI_LastName, "")
        self.init_pref(STR_UI_UserName, "")
        self.init_pref(STR_UI_Password, "")
        self.init_pref(STR_UI_Address, "")
        self.init_pref(STR_UI_Phone, "")
        self.init_pref(STR_UI_EmailAddress, "")
        self.init_pref(STR_UI_Country, "")
        self.init_pref(STR_UI_Height, 0.0)
        self.init_pref(STR_UI_Gender, Gender.GenderNotSpecified)
        self.init_pref(STR_UI_TimeZone, "")
        self.init_pref(STR_UI_DST, False)

    @property
    def dob(self) -> date:
        val = self.get_pref(STR_UI_DOB)
        if isinstance(val, date):
            return val
        return date(1970, 1, 1)

    @dob.setter
    def dob(self, value: date) -> None:
        self.set_pref(STR_UI_DOB, value)

    @property
    def first_name(self) -> str:
        return str(self.get_pref(STR_UI_FirstName) or "")

    @first_name.setter
    def first_name(self, value: str) -> None:
        self.set_pref(STR_UI_FirstName, value)

    @property
    def last_name(self) -> str:
        return str(self.get_pref(STR_UI_LastName) or "")

    @last_name.setter
    def last_name(self, value: str) -> None:
        self.set_pref(STR_UI_LastName, value)

    @property
    def user_name(self) -> str:
        return str(self.get_pref(STR_UI_UserName) or "")

    @user_name.setter
    def user_name(self, value: str) -> None:
        self.set_pref(STR_UI_UserName, value)

    @property
    def address(self) -> str:
        return str(self.get_pref(STR_UI_Address) or "")

    @address.setter
    def address(self, value: str) -> None:
        self.set_pref(STR_UI_Address, value)

    @property
    def phone(self) -> str:
        return str(self.get_pref(STR_UI_Phone) or "")

    @phone.setter
    def phone(self, value: str) -> None:
        self.set_pref(STR_UI_Phone, value)

    @property
    def email(self) -> str:
        return str(self.get_pref(STR_UI_EmailAddress) or "")

    @email.setter
    def email(self, value: str) -> None:
        self.set_pref(STR_UI_EmailAddress, value)

    @property
    def height(self) -> float:
        val = self.get_pref(STR_UI_Height)
        return float(val) if val else 0.0

    @height.setter
    def height(self, value: float) -> None:
        self.set_pref(STR_UI_Height, value)

    @property
    def country(self) -> str:
        return str(self.get_pref(STR_UI_Country) or "")

    @country.setter
    def country(self, value: str) -> None:
        self.set_pref(STR_UI_Country, value)

    @property
    def gender(self) -> Gender:
        val = self.get_pref(STR_UI_Gender)
        if isinstance(val, Gender):
            return val
        return Gender(int(val) if val else 0)

    @gender.setter
    def gender(self, value: Gender) -> None:
        self.set_pref(STR_UI_Gender, int(value))

    @property
    def time_zone(self) -> str:
        return str(self.get_pref(STR_UI_TimeZone) or "")

    @time_zone.setter
    def time_zone(self, value: str) -> None:
        self.set_pref(STR_UI_TimeZone, value)

    @property
    def daylight_saving(self) -> bool:
        return bool(self.get_pref(STR_UI_DST))

    @daylight_saving.setter
    def daylight_saving(self, value: bool) -> None:
        self.set_pref(STR_UI_DST, value)

    def has_password(self) -> bool:
        """Check if a password is set."""
        pwd = self.get_pref(STR_UI_Password)
        return bool(pwd)

    def check_password(self, password: str) -> bool:
        """Check if the provided password matches."""
        hashed = hashlib.sha1(password.encode('utf-8')).hexdigest()
        return self.get_pref(STR_UI_Password) == hashed

    def set_password(self, password: str) -> None:
        """Set the password (stores SHA1 hash)."""
        hashed = hashlib.sha1(password.encode('utf-8')).hexdigest()
        self.set_pref(STR_UI_Password, hashed)


class OxiSettings(PrefSettings):
    """Profile options relating to oximetry settings."""

    # Default values
    DEFAULT_SPO2_DROP_DURATION = 8.0
    DEFAULT_SPO2_DROP_PERCENTAGE = 3.0
    DEFAULT_PULSE_CHANGE_DURATION = 8.0
    DEFAULT_PULSE_CHANGE_BPM = 5.0
    DEFAULT_OXI_DISCARD_THRESHOLD = 0.0
    DEFAULT_OXI_DESAT_THRESHOLD = 88.0
    DEFAULT_FLAG_PULSE_ABOVE = 99.0
    DEFAULT_FLAG_PULSE_BELOW = 40.0

    def __init__(self, profile: 'Profile'):
        super().__init__(profile)
        self.init_pref(STR_OS_EnableOximetry, False)
        self.init_pref(STR_OS_DefaultDevice, "")
        self.init_pref(STR_OS_SyncOximeterClock, True)
        self.init_pref(STR_OS_OximeterType, 0)
        self.init_pref(STR_OS_SkipOxiIntroScreen, False)
        self.init_pref(STR_OS_SPO2DropDuration, self.DEFAULT_SPO2_DROP_DURATION)
        self.init_pref(STR_OS_SPO2DropPercentage, self.DEFAULT_SPO2_DROP_PERCENTAGE)
        self.init_pref(STR_OS_PulseChangeDuration, self.DEFAULT_PULSE_CHANGE_DURATION)
        self.init_pref(STR_OS_PulseChangeBPM, self.DEFAULT_PULSE_CHANGE_BPM)
        self.init_pref(STR_OS_OxiDiscardThreshold, self.DEFAULT_OXI_DISCARD_THRESHOLD)
        self.init_pref(STR_OS_oxiDesaturationThreshold, self.DEFAULT_OXI_DESAT_THRESHOLD)
        self.init_pref(STR_OS_flagPulseAbove, self.DEFAULT_FLAG_PULSE_ABOVE)
        self.init_pref(STR_OS_flagPulseBelow, self.DEFAULT_FLAG_PULSE_BELOW)

    @property
    def oximetry_enabled(self) -> bool:
        return bool(self.get_pref(STR_OS_EnableOximetry))

    @oximetry_enabled.setter
    def oximetry_enabled(self, value: bool) -> None:
        self.set_pref(STR_OS_EnableOximetry, value)

    @property
    def spo2_drop_duration(self) -> float:
        return float(self.get_pref(STR_OS_SPO2DropDuration) or self.DEFAULT_SPO2_DROP_DURATION)

    @spo2_drop_duration.setter
    def spo2_drop_duration(self, value: float) -> None:
        self.set_pref(STR_OS_SPO2DropDuration, value)

    @property
    def spo2_drop_percentage(self) -> float:
        return float(self.get_pref(STR_OS_SPO2DropPercentage) or self.DEFAULT_SPO2_DROP_PERCENTAGE)

    @spo2_drop_percentage.setter
    def spo2_drop_percentage(self, value: float) -> None:
        self.set_pref(STR_OS_SPO2DropPercentage, value)


class CPAPSettings(PrefSettings):
    """Profile options relating to CPAP settings."""

    def __init__(self, profile: 'Profile'):
        super().__init__(profile)
        # Initialize defaults (init_pref only sets if not already present)
        self.init_pref(STR_CS_ComplianceHours, 4.0)
        self.init_pref(STR_CS_ClinicalMode, False)
        self.init_pref(STR_CS_ShowLeaksMode, 0)
        self.init_pref(STR_CS_MaskStartDate, None)
        self.init_pref(STR_CS_MaskDescription, "")
        self.init_pref(STR_CS_MaskType, MaskType.Mask_Unknown)
        self.init_pref(STR_CS_PrescribedMode, CPAPMode.MODE_UNKNOWN)
        self.init_pref(STR_CS_PrescribedMinPressure, 0.0)
        self.init_pref(STR_CS_PrescribedMaxPressure, 0.0)
        self.init_pref(STR_CS_UntreatedAHI, 0.0)
        self.init_pref(STR_CS_Notes, "")
        self.init_pref(STR_CS_DateDiagnosed, None)
        self.init_pref(STR_CS_UserFlowRestriction, 20.0)
        self.init_pref(STR_CS_UserEventDuration, 8.0)
        self.init_pref(STR_CS_UserFlowRestriction2, 50.0)
        self.init_pref(STR_CS_UserEventDuration2, 8.0)
        self.init_pref(STR_CS_UserEventDuplicates, False)
        self.init_pref(STR_CS_UserEventFlagging, False)
        self.init_pref(STR_CS_AHIWindow, 60.0)
        self.init_pref(STR_CS_AHIReset, False)
        self.init_pref(STR_CS_LeakRedline, 24.0)
        self.init_pref(STR_CS_ShowLeakRedline, True)
        self.init_pref(STR_CS_AutoImport, False)
        self.init_pref(STR_CS_BrickWarning, True)
        self.init_pref(STR_CS_CalculateUnintentionalLeaks, True)
        self.init_pref(STR_CS_4cmH2OLeaks, 20.167)
        self.init_pref(STR_CS_20cmH2OLeaks, 48.333)
        self.init_pref(STR_CS_ClockDrift, 0)

    @property
    def compliance_hours(self) -> float:
        val = self.get_pref(STR_CS_ComplianceHours)
        return float(val) if val is not None else 4.0

    @compliance_hours.setter
    def compliance_hours(self, value: float) -> None:
        self.set_pref(STR_CS_ComplianceHours, value)

    @property
    def clinical_mode(self) -> bool:
        val = self.get_pref(STR_CS_ClinicalMode)
        return bool(val) if val is not None else False

    @clinical_mode.setter
    def clinical_mode(self, value: bool) -> None:
        self.set_pref(STR_CS_ClinicalMode, value)

    @property
    def leak_mode(self) -> int:
        return int(self.get_pref(STR_CS_ShowLeaksMode) or 0)

    @leak_mode.setter
    def leak_mode(self, value: int) -> None:
        self.set_pref(STR_CS_ShowLeaksMode, value)

    @property
    def mask_type(self) -> MaskType:
        val = self.get_pref(STR_CS_MaskType)
        if isinstance(val, MaskType):
            return val
        return MaskType(int(val) if val else 0)

    @mask_type.setter
    def mask_type(self, value: MaskType) -> None:
        self.set_pref(STR_CS_MaskType, int(value))

    @property
    def mode(self) -> CPAPMode:
        val = self.get_pref(STR_CS_PrescribedMode)
        if isinstance(val, CPAPMode):
            return val
        return CPAPMode(int(val) if val else 0)

    @mode.setter
    def mode(self, value: CPAPMode) -> None:
        self.set_pref(STR_CS_PrescribedMode, int(value))

    @property
    def min_pressure(self) -> float:
        return float(self.get_pref(STR_CS_PrescribedMinPressure) or 0.0)

    @min_pressure.setter
    def min_pressure(self, value: float) -> None:
        self.set_pref(STR_CS_PrescribedMinPressure, value)

    @property
    def max_pressure(self) -> float:
        return float(self.get_pref(STR_CS_PrescribedMaxPressure) or 0.0)

    @max_pressure.setter
    def max_pressure(self, value: float) -> None:
        self.set_pref(STR_CS_PrescribedMaxPressure, value)

    @property
    def ahi_window(self) -> float:
        val = self.get_pref(STR_CS_AHIWindow)
        return float(val) if val is not None else 60.0

    @ahi_window.setter
    def ahi_window(self, value: float) -> None:
        self.set_pref(STR_CS_AHIWindow, value)

    @property
    def leak_redline(self) -> float:
        val = self.get_pref(STR_CS_LeakRedline)
        return float(val) if val is not None else 24.0

    @leak_redline.setter
    def leak_redline(self, value: float) -> None:
        self.set_pref(STR_CS_LeakRedline, value)

    @property
    def auto_import(self) -> bool:
        return bool(self.get_pref(STR_CS_AutoImport))

    @auto_import.setter
    def auto_import(self, value: bool) -> None:
        self.set_pref(STR_CS_AutoImport, value)


class SessionSettings(PrefSettings):
    """Profile options relating to session/import settings."""

    def __init__(self, profile: 'Profile'):
        super().__init__(profile)
        # Initialize defaults (init_pref only sets if not already present)
        self.init_pref(STR_IS_DaySplitTime, time(12, 0, 0))
        self.init_pref(STR_IS_PreloadSummaries, False)
        self.init_pref(STR_IS_CombineCloseSessions, 240.0)
        self.init_pref(STR_IS_IgnoreShorterSessions, 5.0)
        self.init_pref(STR_IS_BackupCardData, True)
        self.init_pref(STR_IS_CompressBackupData, False)
        self.init_pref(STR_IS_CompressSessionData, False)
        self.init_pref(STR_IS_IgnoreOlderSessions, False)
        self.init_pref(STR_IS_LockSummarySessions, True)
        self.init_pref(STR_IS_WarnOnUntestedMachine, True)
        self.init_pref(STR_IS_WarnOnUnexpectedData, True)

    @property
    def day_split_time(self) -> time:
        val = self.get_pref(STR_IS_DaySplitTime)
        if isinstance(val, time):
            return val
        return time(12, 0, 0)

    @day_split_time.setter
    def day_split_time(self, value: time) -> None:
        self.set_pref(STR_IS_DaySplitTime, value)

    @property
    def preload_summaries(self) -> bool:
        val = self.get_pref(STR_IS_PreloadSummaries)
        return bool(val) if val is not None else False

    @preload_summaries.setter
    def preload_summaries(self, value: bool) -> None:
        self.set_pref(STR_IS_PreloadSummaries, value)

    @property
    def combine_close_sessions(self) -> float:
        val = self.get_pref(STR_IS_CombineCloseSessions)
        return float(val) if val is not None else 240.0

    @combine_close_sessions.setter
    def combine_close_sessions(self, value: float) -> None:
        self.set_pref(STR_IS_CombineCloseSessions, value)

    @property
    def ignore_short_sessions(self) -> float:
        val = self.get_pref(STR_IS_IgnoreShorterSessions)
        return float(val) if val is not None else 5.0

    @ignore_short_sessions.setter
    def ignore_short_sessions(self, value: float) -> None:
        self.set_pref(STR_IS_IgnoreShorterSessions, value)

    @property
    def backup_card_data(self) -> bool:
        val = self.get_pref(STR_IS_BackupCardData)
        return bool(val) if val is not None else True

    @backup_card_data.setter
    def backup_card_data(self, value: bool) -> None:
        self.set_pref(STR_IS_BackupCardData, value)

    @property
    def warn_on_untested_machine(self) -> bool:
        val = self.get_pref(STR_IS_WarnOnUntestedMachine)
        return bool(val) if val is not None else True

    @warn_on_untested_machine.setter
    def warn_on_untested_machine(self, value: bool) -> None:
        self.set_pref(STR_IS_WarnOnUntestedMachine, value)


class UserSettings(PrefSettings):
    """Profile options relating to general user settings."""

    def __init__(self, profile: 'Profile'):
        super().__init__(profile)
        # Initialize defaults (init_pref only sets if not already present)
        self.init_pref(STR_US_UnitSystem, UnitSystem.US_Metric)
        self.init_pref(STR_US_EventWindowSize, 3.0)
        self.init_pref(STR_US_SkipEmptyDays, True)
        self.init_pref(STR_US_RebuildCache, False)
        self.init_pref(STR_US_CalculateRDI, False)
        self.init_pref(STR_US_PrefCalcMiddle, 0)
        self.init_pref(STR_US_PrefCalcPercentile, 95.0)
        self.init_pref(STR_US_PrefCalcMax, 0)
        self.init_pref(STR_US_StatReportMode, 0)
        self.init_pref(STR_US_ShowUnknownFlags, False)

    @property
    def unit_system(self) -> UnitSystem:
        val = self.get_pref(STR_US_UnitSystem)
        if isinstance(val, UnitSystem):
            return val
        return UnitSystem(int(val) if val else 0)

    @unit_system.setter
    def unit_system(self, value: UnitSystem) -> None:
        self.set_pref(STR_US_UnitSystem, int(value))

    @property
    def skip_empty_days(self) -> bool:
        val = self.get_pref(STR_US_SkipEmptyDays)
        return bool(val) if val is not None else True

    @skip_empty_days.setter
    def skip_empty_days(self, value: bool) -> None:
        self.set_pref(STR_US_SkipEmptyDays, value)

    @property
    def calculate_rdi(self) -> bool:
        val = self.get_pref(STR_US_CalculateRDI)
        return bool(val) if val is not None else False

    @calculate_rdi.setter
    def calculate_rdi(self, value: bool) -> None:
        self.set_pref(STR_US_CalculateRDI, value)

    @property
    def pref_calc_percentile(self) -> float:
        val = self.get_pref(STR_US_PrefCalcPercentile)
        return float(val) if val is not None else 95.0

    @pref_calc_percentile.setter
    def pref_calc_percentile(self, value: float) -> None:
        self.set_pref(STR_US_PrefCalcPercentile, value)


class Profile(Preferences):
    """User profile containing all information and device data indexes.

    The Profile class extends Preferences to provide user-specific
    settings and manages the collection of machines and daily data.
    """

    def __init__(self, path: str, open_profile: bool = True):
        """Initialize a Profile.

        Args:
            path: Path to the profile directory
            open_profile: Whether to load the profile from disk
        """
        super().__init__("Profile")
        self.p_path = path
        self.p_filename = str(Path(path) / "Profile.xml")

        # Date tracking
        self._first: Optional[date] = None
        self._last: Optional[date] = None
        self._opened = False
        self.is_first_day = False

        # Day list mapping dates to Day objects
        self.daylist: Dict[date, Day] = {}

        # Machine management
        self.m_machlist: List[Machine] = []
        self._machine_list: Dict[str, Dict[str, Machine]] = {}

        # Settings sub-objects will be initialized after loading
        self.user: Optional[UserInfo] = None
        self.cpap: Optional[CPAPSettings] = None
        self.oxi: Optional[OxiSettings] = None
        self.doctor: Optional[DoctorInfo] = None
        self.general: Optional[UserSettings] = None
        self.session: Optional[SessionSettings] = None

        if open_profile:
            self.open()

        # Initialize settings objects after loading so init_pref respects loaded values
        self._init_settings()

    def _init_settings(self) -> None:
        """Initialize settings sub-objects.

        This is called after loading preferences so that init_pref
        will respect any loaded values instead of overwriting them.
        """
        self.user = UserInfo(self)
        self.cpap = CPAPSettings(self)
        self.oxi = OxiSettings(self)
        self.doctor = DoctorInfo(self)
        self.general = UserSettings(self)
        self.session = SessionSettings(self)

    def path(self) -> str:
        """Return the profile path."""
        return self.p_path

    def data_folder(self) -> str:
        """Return the data folder path."""
        return self.get("{DataFolder}")

    def is_open(self) -> bool:
        """Return whether the profile has been opened."""
        return self._opened

    def open(self, filename: str = "") -> bool:
        """Open and load the profile.

        Args:
            filename: Optional override filename

        Returns:
            True if successful
        """
        if not filename:
            filename = self.p_filename

        result = super().open(filename)
        if result:
            self._opened = True
        return result

    def save(self, filename: str = "") -> bool:
        """Save the profile.

        Args:
            filename: Optional override filename

        Returns:
            True if successful
        """
        if not filename:
            filename = self.p_filename

        return super().save(filename)

    def open_machines(self) -> bool:
        """Parse and load machines.xml.

        Returns:
            True if successful
        """
        machines_file = Path(self.p_path) / "machines.xml"
        if not machines_file.exists():
            return False

        try:
            tree = ET.parse(str(machines_file))
            root = tree.getroot()

            for mach_elem in root.findall(".//machine"):
                # Parse machine info from attributes and child elements
                mach_id = int(mach_elem.get("id", "0"))  # ID is decimal in machines.xml
                mach_type = MachineType(int(mach_elem.get("type", "0")))

                # Get child element text values
                def get_elem_text(parent, tag: str, default: str = "") -> str:
                    elem = parent.find(tag)
                    return elem.text if elem is not None and elem.text else default

                info = MachineInfo(
                    type=mach_type,
                    loadername=mach_elem.get("class", ""),  # Loader is in 'class' attribute
                    brand=get_elem_text(mach_elem, "brand"),
                    model=get_elem_text(mach_elem, "model"),
                    modelnumber=get_elem_text(mach_elem, "modelnumber"),
                    serial=get_elem_text(mach_elem, "serial"),
                    series=get_elem_text(mach_elem, "series"),
                )

                # Create appropriate machine type
                machine = self.create_machine(info, mach_id)
                if machine:
                    self.add_machine(machine)

            return True
        except Exception as e:
            print(f"Error loading machines: {e}")
            return False

    def store_machines(self) -> bool:
        """Save machines to machines.xml.

        Returns:
            True if successful
        """
        root = ET.Element("machines")

        for machine in self.m_machlist:
            mach_elem = ET.SubElement(root, "machine")
            mach_elem.set("id", f"0x{machine.id:08x}")
            mach_elem.set("type", str(int(machine.type)))
            mach_elem.set("loader", machine.loader_name)
            mach_elem.set("brand", machine.brand)
            mach_elem.set("model", machine.model)
            mach_elem.set("serial", machine.serial)

        try:
            tree = ET.ElementTree(root)
            machines_file = Path(self.p_path) / "machines.xml"
            tree.write(str(machines_file), encoding="utf-8", xml_declaration=True)
            return True
        except Exception as e:
            print(f"Error saving machines: {e}")
            return False

    def add_machine(self, machine: Machine) -> None:
        """Add a machine to the profile.

        Args:
            machine: The machine to add
        """
        if machine not in self.m_machlist:
            self.m_machlist.append(machine)

        serial = machine.serial
        loader = machine.loader_name

        if loader not in self._machine_list:
            self._machine_list[loader] = {}
        self._machine_list[loader][serial] = machine

    def del_machine(self, machine: Machine) -> None:
        """Remove a machine from the profile.

        Args:
            machine: The machine to remove
        """
        if machine in self.m_machlist:
            self.m_machlist.remove(machine)

        serial = machine.serial
        loader = machine.loader_name

        if loader in self._machine_list and serial in self._machine_list[loader]:
            del self._machine_list[loader][serial]

    def remove_machine(self, machine: Machine) -> None:
        """Alias for del_machine."""
        self.del_machine(machine)

    def lookup_machine(self, serial: str, loadername: str) -> Optional[Machine]:
        """Look up a machine by serial and loader name.

        Args:
            serial: Device serial number
            loadername: Loader name

        Returns:
            The machine if found, None otherwise
        """
        if loadername in self._machine_list:
            return self._machine_list[loadername].get(serial)
        return None

    def create_machine(self, info: MachineInfo, machine_id: MachineID = 0) -> Machine:
        """Create a new machine with the given info.

        Args:
            info: Machine information
            machine_id: Optional machine ID (generated if 0)

        Returns:
            The created machine
        """
        # Create appropriate machine subclass based on type
        if info.type == MachineType.MT_CPAP:
            machine = CPAP(self, machine_id)
        elif info.type == MachineType.MT_OXIMETER:
            machine = Oximeter(self, machine_id)
        else:
            machine = Machine(self, machine_id)

        machine.set_info(info)
        return machine

    def get_machines(self, mtype: MachineType = MachineType.MT_UNKNOWN) -> List[Machine]:
        """Get all machines of a given type.

        Args:
            mtype: Machine type filter (MT_UNKNOWN for all)

        Returns:
            List of matching machines
        """
        if mtype == MachineType.MT_UNKNOWN:
            return list(self.m_machlist)

        return [m for m in self.m_machlist if m.type == mtype]

    def get_machine(self, mtype: MachineType, date_val: Optional[date] = None) -> Optional[Machine]:
        """Get a machine of the given type, optionally for a specific date.

        Args:
            mtype: Machine type
            date_val: Optional date filter

        Returns:
            First matching machine or None
        """
        for machine in self.m_machlist:
            if machine.type == mtype:
                if date_val is None:
                    return machine
                if date_val in machine.day:
                    return machine
        return None

    def add_day(self, date_val: date) -> Day:
        """Add or get a Day record for the given date.

        Args:
            date_val: The date

        Returns:
            The Day object
        """
        if date_val not in self.daylist:
            self.daylist[date_val] = Day(date_val)

        return self.daylist[date_val]

    def get_day(self, date_val: date, mtype: MachineType = MachineType.MT_UNKNOWN) -> Optional[Day]:
        """Get a Day record if data available.

        Args:
            date_val: The date
            mtype: Optional machine type filter

        Returns:
            The Day object or None
        """
        day = self.daylist.get(date_val)
        if day is None:
            return None

        if mtype == MachineType.MT_UNKNOWN:
            return day

        if day.has_data(mtype):
            return day

        return None

    def find_day(self, date_val: date, mtype: MachineType = MachineType.MT_UNKNOWN) -> Optional[Day]:
        """Same as get_day but doesn't open summaries."""
        return self.get_day(date_val, mtype)

    def unlink_day(self, day: Day) -> bool:
        """Remove a day from the daylist.

        Args:
            day: The day to remove

        Returns:
            True if removed
        """
        if day.date in self.daylist:
            del self.daylist[day.date]
            return True
        return False

    def get_days(self, mtype: MachineType, start: date, end: date) -> List[Day]:
        """Get all days between start and end dates.

        Args:
            mtype: Machine type filter
            start: Start date
            end: End date

        Returns:
            List of Day objects
        """
        result = []
        for day_date, day in sorted(self.daylist.items()):
            if start <= day_date <= end:
                if mtype == MachineType.MT_UNKNOWN or day.has_data(mtype):
                    result.append(day)
        return result

    def count_days(
        self,
        mtype: MachineType = MachineType.MT_UNKNOWN,
        start: Optional[date] = None,
        end: Optional[date] = None
    ) -> int:
        """Count days with data.

        Args:
            mtype: Machine type filter
            start: Optional start date
            end: Optional end date

        Returns:
            Number of days
        """
        count = 0
        for day_date, day in self.daylist.items():
            if start and day_date < start:
                continue
            if end and day_date > end:
                continue
            if mtype == MachineType.MT_UNKNOWN or day.has_data(mtype):
                count += 1
        return count

    def first_day(self, mtype: MachineType = MachineType.MT_UNKNOWN) -> Optional[date]:
        """Get the first date with data.

        Args:
            mtype: Machine type filter

        Returns:
            The first date or None
        """
        for day_date in sorted(self.daylist.keys()):
            day = self.daylist[day_date]
            if mtype == MachineType.MT_UNKNOWN or day.has_data(mtype):
                return day_date
        return None

    def last_day(self, mtype: MachineType = MachineType.MT_UNKNOWN) -> Optional[date]:
        """Get the last date with data.

        Args:
            mtype: Machine type filter

        Returns:
            The last date or None
        """
        for day_date in sorted(self.daylist.keys(), reverse=True):
            day = self.daylist[day_date]
            if mtype == MachineType.MT_UNKNOWN or day.has_data(mtype):
                return day_date
        return None

    def has_channel(self, code: ChannelID) -> bool:
        """Check if any machines have the given channel.

        Args:
            code: Channel ID

        Returns:
            True if channel is available
        """
        for machine in self.m_machlist:
            if machine.has_channel(code):
                return True
        return False

    def channel_available(self, code: ChannelID) -> bool:
        """Alias for has_channel."""
        return self.has_channel(code)


# ============================================================================
# Profile Management Functions
# ============================================================================

# Global profile storage
profiles: Dict[str, Profile] = {}
p_profile: Optional[Profile] = None


def scan_profiles() -> None:
    """Scan and load all profiles from the data directory."""
    global profiles
    profiles.clear()

    data_dir = get_app_data()
    if not data_dir.exists():
        return

    for profile_dir in data_dir.iterdir():
        if profile_dir.is_dir():
            profile_xml = profile_dir / "Profile.xml"
            if profile_xml.exists():
                profile = Profile(str(profile_dir), open_profile=True)
                profiles[profile_dir.name] = profile


def done_profiles() -> None:
    """Save all profiles and clear the list."""
    global profiles
    for profile in profiles.values():
        profile.save()
    profiles.clear()


def create_profile(name: str, path: Optional[str] = None) -> Profile:
    """Create a new profile.

    Args:
        name: Profile name
        path: Optional custom path

    Returns:
        The created Profile
    """
    if path is None:
        path = str(get_app_data() / name)

    # Ensure directory exists
    Path(path).mkdir(parents=True, exist_ok=True)

    profile = Profile(path, open_profile=False)
    profiles[name] = profile
    return profile


def get_profile(name: str = "") -> Optional[Profile]:
    """Get a profile by name.

    Args:
        name: Profile name (empty for current)

    Returns:
        The Profile or None
    """
    global p_profile
    if not name:
        return p_profile
    return profiles.get(name)
