"""
SleepLib Statistics - Statistics Calculation Engine

This module provides classes for calculating summary statistics and
daily summaries from sleep session data.

Copyright (c) 2019-2025 The OSCAR Team
License: GPL v3
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import List, Optional, Dict, TYPE_CHECKING
import statistics as stats

if TYPE_CHECKING:
    from .profile import Profile

from .schema import (
    MachineType,
    CPAP_Obstructive,
    CPAP_ClearAirway,
    CPAP_Hypopnea,
    CPAP_RERA,
    CPAP_Pressure,
    CPAP_Leak,
)


@dataclass
class DaySummary:
    """Summary statistics for a single day.

    Attributes:
        date: The date of the summary.
        hours: Total usage hours (mask on time).
        ahi: Total AHI (events per hour).
        oa_count: Obstructive apnea count.
        ca_count: Central/clear airway count.
        h_count: Hypopnea count.
        rera_count: RERA count.
        pressure_min: Minimum pressure (cmH2O).
        pressure_avg: Average pressure (cmH2O).
        pressure_max: Maximum pressure (cmH2O).
        leak_avg: Average leak rate (L/min).
    """
    date: date
    hours: float = 0.0
    ahi: float = 0.0
    oa_count: int = 0
    ca_count: int = 0
    h_count: int = 0
    rera_count: int = 0
    pressure_min: float = 0.0
    pressure_avg: float = 0.0
    pressure_max: float = 0.0
    leak_avg: float = 0.0

    @property
    def total_events(self) -> int:
        """Return total AHI-contributing events (OA + CA + H)."""
        return self.oa_count + self.ca_count + self.h_count

    @property
    def all_events(self) -> int:
        """Return total events including RERA."""
        return self.oa_count + self.ca_count + self.h_count + self.rera_count


@dataclass
class RangeSummary:
    """Summary statistics for a date range.

    Attributes:
        total_days: Total number of days in the range.
        days_with_data: Number of days that have sleep data.
        avg_hours: Average usage hours per day.
        median_hours: Median usage hours per day.
        ahi_avg: Average AHI across all days.
        ahi_median: Median AHI across all days.
        ahi_90th: 90th percentile AHI.
        compliance_percent: Percentage of days meeting compliance threshold.
        total_hours: Total hours across all days.
        pressure_avg: Average pressure across all days.
        leak_avg: Average leak rate across all days.
    """
    total_days: int = 0
    days_with_data: int = 0
    avg_hours: float = 0.0
    median_hours: float = 0.0
    ahi_avg: float = 0.0
    ahi_median: float = 0.0
    ahi_90th: float = 0.0
    compliance_percent: float = 0.0
    total_hours: float = 0.0
    pressure_avg: float = 0.0
    leak_avg: float = 0.0


class StatisticsCalculator:
    """Calculator for generating summary statistics from profile data.

    This class provides methods to calculate daily summaries and
    aggregate statistics over date ranges.

    Attributes:
        profile: The profile to calculate statistics for.
        compliance_hours: Minimum hours for compliance (default 4.0).
    """

    def __init__(
        self,
        profile: 'Profile',
        compliance_hours: float = 4.0
    ) -> None:
        """Initialize the StatisticsCalculator.

        Args:
            profile: The profile to calculate statistics for.
            compliance_hours: Minimum hours for compliance tracking.
        """
        self._profile = profile
        self._compliance_hours = compliance_hours
        self._cache: Dict[date, DaySummary] = {}

    @property
    def profile(self) -> 'Profile':
        """Return the profile."""
        return self._profile

    @property
    def compliance_hours(self) -> float:
        """Return the compliance hours threshold."""
        return self._compliance_hours

    @compliance_hours.setter
    def compliance_hours(self, value: float) -> None:
        """Set the compliance hours threshold."""
        self._compliance_hours = value

    def clear_cache(self) -> None:
        """Clear the cached day summaries."""
        self._cache.clear()

    def get_day_summary(self, day_date: date, use_cache: bool = True) -> Optional[DaySummary]:
        """Get summary statistics for a single day.

        Args:
            day_date: The date to get summary for.
            use_cache: Whether to use cached results.

        Returns:
            DaySummary for the day, or None if no data.
        """
        # Check cache
        if use_cache and day_date in self._cache:
            return self._cache[day_date]

        # Get day from profile
        if self._profile is None:
            return None

        day = self._profile.get_day(day_date, MachineType.MT_CPAP)
        if day is None:
            return None

        # Calculate summary from sessions
        summary = self._calculate_day_summary(day_date, day)

        # Cache result
        if use_cache:
            self._cache[day_date] = summary

        return summary

    def _calculate_day_summary(self, day_date: date, day) -> DaySummary:
        """Calculate summary statistics for a day.

        Args:
            day_date: The date.
            day: The Day object containing sessions.

        Returns:
            DaySummary with calculated statistics.
        """
        summary = DaySummary(date=day_date)

        if not hasattr(day, 'sessions') or not day.sessions:
            return summary

        total_hours = 0.0
        total_oa = 0
        total_ca = 0
        total_h = 0
        total_rera = 0

        pressure_values = []
        leak_values = []
        pressure_mins = []
        pressure_maxs = []

        for session in day.sessions:
            if not hasattr(session, 'enabled') or not session.enabled:
                continue

            # Get hours
            hours = 0.0
            if hasattr(session, 'hours'):
                hours = session.hours()
            elif hasattr(session, 'duration'):
                hours = session.duration()

            if hours <= 0:
                continue

            total_hours += hours

            # Get event counts
            if hasattr(session, 'count'):
                total_oa += int(session.count(CPAP_Obstructive) or 0)
                total_ca += int(session.count(CPAP_ClearAirway) or 0)
                total_h += int(session.count(CPAP_Hypopnea) or 0)
                total_rera += int(session.count(CPAP_RERA) or 0)

            # Get pressure stats
            if hasattr(session, 'avg'):
                pressure_avg = session.avg(CPAP_Pressure)
                if pressure_avg > 0:
                    pressure_values.append(pressure_avg)

            if hasattr(session, 'min_value'):
                pressure_min = session.min_value(CPAP_Pressure)
                if pressure_min > 0:
                    pressure_mins.append(pressure_min)

            if hasattr(session, 'max_value'):
                pressure_max = session.max_value(CPAP_Pressure)
                if pressure_max > 0:
                    pressure_maxs.append(pressure_max)

            # Get leak stats
            if hasattr(session, 'avg'):
                leak_avg = session.avg(CPAP_Leak)
                if leak_avg >= 0:
                    leak_values.append(leak_avg)

        # Populate summary
        summary.hours = total_hours
        summary.oa_count = total_oa
        summary.ca_count = total_ca
        summary.h_count = total_h
        summary.rera_count = total_rera

        # Calculate AHI
        if total_hours > 0:
            summary.ahi = (total_oa + total_ca + total_h) / total_hours

        # Calculate pressure stats
        if pressure_values:
            summary.pressure_avg = sum(pressure_values) / len(pressure_values)
        if pressure_mins:
            summary.pressure_min = min(pressure_mins)
        if pressure_maxs:
            summary.pressure_max = max(pressure_maxs)

        # Calculate leak average
        if leak_values:
            summary.leak_avg = sum(leak_values) / len(leak_values)

        return summary

    def get_range_summaries(
        self,
        start: date,
        end: date,
        use_cache: bool = True
    ) -> List[DaySummary]:
        """Get day summaries for a date range.

        Args:
            start: Start date (inclusive).
            end: End date (inclusive).
            use_cache: Whether to use cached results.

        Returns:
            List of DaySummary objects for days with data.
        """
        summaries = []
        current = start

        while current <= end:
            summary = self.get_day_summary(current, use_cache)
            if summary is not None and summary.hours > 0:
                summaries.append(summary)
            current += timedelta(days=1)

        return summaries

    def get_range_statistics(
        self,
        start: date,
        end: date,
        use_cache: bool = True
    ) -> RangeSummary:
        """Calculate aggregate statistics for a date range.

        Args:
            start: Start date (inclusive).
            end: End date (inclusive).
            use_cache: Whether to use cached results.

        Returns:
            RangeSummary with aggregate statistics.
        """
        # Get individual day summaries
        summaries = self.get_range_summaries(start, end, use_cache)

        # Calculate total days in range
        total_days = (end - start).days + 1

        result = RangeSummary(
            total_days=total_days,
            days_with_data=len(summaries)
        )

        if not summaries:
            return result

        # Extract values for calculations
        hours_list = [s.hours for s in summaries if s.hours > 0]
        ahi_list = [s.ahi for s in summaries if s.hours > 0]
        pressure_list = [s.pressure_avg for s in summaries if s.pressure_avg > 0]
        leak_list = [s.leak_avg for s in summaries if s.leak_avg >= 0]

        # Calculate hours statistics
        if hours_list:
            result.total_hours = sum(hours_list)
            result.avg_hours = stats.mean(hours_list)
            result.median_hours = stats.median(hours_list)

        # Calculate AHI statistics
        if ahi_list:
            result.ahi_avg = stats.mean(ahi_list)
            result.ahi_median = stats.median(ahi_list)
            # Calculate 90th percentile
            result.ahi_90th = self._percentile(ahi_list, 90)

        # Calculate compliance
        compliant_days = sum(1 for s in summaries if s.hours >= self._compliance_hours)
        if len(summaries) > 0:
            result.compliance_percent = (compliant_days / len(summaries)) * 100

        # Calculate pressure average
        if pressure_list:
            result.pressure_avg = stats.mean(pressure_list)

        # Calculate leak average
        if leak_list:
            result.leak_avg = stats.mean(leak_list)

        return result

    def _percentile(self, data: List[float], percentile: float) -> float:
        """Calculate a percentile value from a list.

        Args:
            data: List of values.
            percentile: Percentile to calculate (0-100).

        Returns:
            The percentile value.
        """
        if not data:
            return 0.0

        sorted_data = sorted(data)
        n = len(sorted_data)

        if n == 1:
            return sorted_data[0]

        # Calculate index
        k = (percentile / 100) * (n - 1)
        f = int(k)
        c = f + 1 if f + 1 < n else f

        # Linear interpolation
        if f == c:
            return sorted_data[f]

        d0 = sorted_data[f] * (c - k)
        d1 = sorted_data[c] * (k - f)
        return d0 + d1

    def get_available_date_range(self) -> Optional[tuple]:
        """Get the date range with available data.

        Returns:
            Tuple of (first_date, last_date) or None if no data.
        """
        if self._profile is None:
            return None

        first = self._profile.first_day(MachineType.MT_CPAP)
        last = self._profile.last_day(MachineType.MT_CPAP)

        if first is None or last is None:
            return None

        return (first, last)
