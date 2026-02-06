"""
SleepLib Calcs - Signal Processing and Derived Channel Calculations

This module provides the signal processing engine that derives respiratory
metrics from raw flow waveforms via breath detection, plus sliding-window
AHI graphs and leak calculations.

Ported from C++ calcs.cpp (~1,816 lines).

Copyright (c) 2019-2025 The OSCAR Team
License: GPL v3
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, TYPE_CHECKING
import logging

import numpy as np

from .event import EventList, EventListType
from .schema import (
    ChannelID, AllAhiChannels,
    CPAP_FlowRate, CPAP_RespRate, CPAP_TidalVolume,
    CPAP_Ti, CPAP_Te, CPAP_MinuteVent, CPAP_AHI, CPAP_RDI,
    CPAP_Leak, CPAP_LargeLeak, CPAP_RERA,
    STR_UNIT_BreathsPerMinute, STR_UNIT_ml, STR_UNIT_Seconds,
    STR_UNIT_LPM, STR_UNIT_EventsPerHour,
)

if TYPE_CHECKING:
    from .session import Session

logger = logging.getLogger(__name__)


# ============================================================================
# BreathPeak - detected breath cycle
# ============================================================================

@dataclass
class BreathPeak:
    """A single detected breath cycle from zero-crossing analysis.

    Attributes:
        min_flow: Peak negative (expiratory) flow value.
        max_flow: Peak positive (inspiratory) flow value.
        start_idx: Sample index where breath begins (previous zero-crossing up).
        middle_idx: Sample index of zero-crossing down (inspiration→expiration).
        end_idx: Sample index where breath ends (next zero-crossing up).
    """
    min_flow: float
    max_flow: float
    start_idx: int
    middle_idx: int
    end_idx: int

    @property
    def sample_length(self) -> int:
        """Total breath length in samples."""
        return self.end_idx - self.start_idx

    @property
    def upper_length(self) -> int:
        """Inspiratory phase length in samples."""
        return self.middle_idx - self.start_idx

    @property
    def lower_length(self) -> int:
        """Expiratory phase length in samples."""
        return self.end_idx - self.middle_idx


# ============================================================================
# FlowParser - breath detection and derived channel computation
# ============================================================================

class FlowParser:
    """Detects breath cycles from flow waveform and computes derived channels.

    Processes CPAP_FlowRate waveform data to calculate:
    - CPAP_RespRate: Respiratory rate (breaths per minute)
    - CPAP_TidalVolume: Tidal volume (ml)
    - CPAP_Ti: Inspiratory time (seconds)
    - CPAP_Te: Expiratory time (seconds)
    - CPAP_MinuteVent: Minute ventilation (L/min)
    """

    def __init__(self, session: 'Session', flow_eventlist: EventList):
        """Initialize FlowParser.

        Args:
            session: Session to add derived channels to.
            flow_eventlist: The CPAP_FlowRate EventList to analyze.
        """
        self._session = session
        self._flow = flow_eventlist
        self._rate = flow_eventlist.rate  # ms per sample
        self._gain = flow_eventlist.gain
        self._sps = 1000.0 / self._rate if self._rate > 0 else 25.0  # samples per second
        self._breaths: List[BreathPeak] = []

    def calc_peaks(self, samples: np.ndarray) -> List[BreathPeak]:
        """Detect breath cycles using zero-crossing analysis.

        Scans flow waveform for zero-line crossings. Each breath cycle
        is defined by: upward crossing → peak inspiration → downward
        crossing → peak expiration → next upward crossing.

        Quality thresholds filter out noise:
        - Amplitude (max - min) must exceed 8
        - Peak flow must exceed 3
        - Breath duration must exceed 1 second (sps samples)

        Args:
            samples: Raw flow samples (physical values after gain).

        Returns:
            List of detected BreathPeak objects.
        """
        breaths: List[BreathPeak] = []
        n = len(samples)
        if n < 2:
            return breaths

        sps = self._sps
        min_samples = int(sps)  # minimum 1 second per breath

        min_val = 0.0
        max_val = 0.0
        start = 0
        middle = 0
        lastc = samples[0]

        for k in range(1, n):
            c = samples[k]

            if lastc < 0 and c >= 0:
                # Upward zero crossing - end of breath, start of new
                length = k - start
                if (max_val > 3 and (max_val - min_val) > 8
                        and length > min_samples and middle > start):
                    breaths.append(BreathPeak(
                        min_flow=min_val,
                        max_flow=max_val,
                        start_idx=start,
                        middle_idx=middle,
                        end_idx=k,
                    ))
                # Reset for next breath
                max_val = c
                min_val = 0.0
                start = k

            elif lastc >= 0 and c < 0:
                # Downward zero crossing - transition from inspiration to expiration
                min_val = c
                middle = k

            else:
                # Within a phase - track extremes
                if c >= 0:
                    if c > max_val:
                        max_val = c
                else:
                    if c < min_val:
                        min_val = c

            lastc = c

        return breaths

    def calc(
        self,
        calc_resp: bool = True,
        calc_tv: bool = True,
        calc_ti: bool = True,
        calc_te: bool = True,
        calc_mv: bool = True,
    ) -> None:
        """Main calculation driver: detect breaths and compute derived channels.

        Args:
            calc_resp: Whether to calculate respiratory rate.
            calc_tv: Whether to calculate tidal volume.
            calc_ti: Whether to calculate inspiratory time.
            calc_te: Whether to calculate expiratory time.
            calc_mv: Whether to calculate minute ventilation.
        """
        flow = self._flow
        if flow.count == 0:
            return

        # Get physical flow values
        phys = flow.physical_data()
        rate_ms = flow.rate
        sps = self._sps
        start_time = flow.first

        # Detect breath peaks
        self._breaths = self.calc_peaks(phys)
        if not self._breaths:
            return

        # Create output EventLists
        rr_evl = None
        tv_evl = None
        ti_evl = None
        te_evl = None
        mv_evl = None

        if calc_resp:
            rr_evl = self._session.add_event_list(
                CPAP_RespRate, EventListType.EVL_Event,
                gain=0.2, offset=0.0,
            )
            rr_evl.dimension = STR_UNIT_BreathsPerMinute

        if calc_tv:
            tv_evl = self._session.add_event_list(
                CPAP_TidalVolume, EventListType.EVL_Event,
                gain=20.0, offset=0.0,
            )
            tv_evl.dimension = STR_UNIT_ml

        if calc_ti:
            ti_evl = self._session.add_event_list(
                CPAP_Ti, EventListType.EVL_Event,
                gain=0.02, offset=0.0,
            )
            ti_evl.dimension = STR_UNIT_Seconds

        if calc_te:
            te_evl = self._session.add_event_list(
                CPAP_Te, EventListType.EVL_Event,
                gain=0.02, offset=0.0,
            )
            te_evl.dimension = STR_UNIT_Seconds

        if calc_mv:
            mv_evl = self._session.add_event_list(
                CPAP_MinuteVent, EventListType.EVL_Event,
                gain=0.125, offset=0.0,
            )
            mv_evl.dimension = STR_UNIT_LPM

        # Moving average buffers (3-4 point smoothing like C++)
        last_ti = 0.0
        last_ti2 = 0.0
        last_te = 0.0
        last_te2 = 0.0
        last_tv = 0.0
        last_tv2 = 0.0

        # Sliding window for respiratory rate (60-second window)
        window_breaths: List[int] = []  # timestamps of breath starts
        window_size_ms = 60000  # 60 seconds

        for i, breath in enumerate(self._breaths):
            # Timestamp at breath midpoint
            mid_time = start_time + int(breath.middle_idx * rate_ms)

            # --- Inspiratory time (Ti) ---
            if calc_ti and ti_evl is not None:
                ti_ms = (breath.middle_idx - breath.start_idx) * rate_ms
                ti_sec = ti_ms / 1000.0
                # 4-point moving average
                smoothed = (last_ti2 + last_ti + ti_sec * 2) / 4.0 if i >= 2 else ti_sec
                last_ti2 = last_ti
                last_ti = ti_sec
                # Store: value / gain = raw int16
                raw_ti = int(smoothed / ti_evl.gain)
                ti_evl.add_event(mid_time, raw_ti)

            # --- Expiratory time (Te) ---
            if calc_te and te_evl is not None:
                te_ms = (breath.end_idx - breath.middle_idx) * rate_ms
                te_sec = te_ms / 1000.0
                smoothed = (last_te2 + last_te + te_sec * 2) / 4.0 if i >= 2 else te_sec
                last_te2 = last_te
                last_te = te_sec
                raw_te = int(smoothed / te_evl.gain)
                te_evl.add_event(mid_time, raw_te)

            # --- Tidal Volume (TV) ---
            if (calc_tv and tv_evl is not None) or (calc_mv and mv_evl is not None):
                # Integrate absolute flow during inspiration phase
                insp_start = breath.start_idx
                insp_end = breath.middle_idx
                if insp_end > insp_start:
                    insp_flow = np.abs(phys[insp_start:insp_end])
                    # TV = integral of flow over time
                    # flow is in L/min, time step is 1/sps seconds
                    # TV (ml) = sum(flow) * (1/sps) * (1000/60)
                    tv_ml = float(np.sum(insp_flow)) * (1000.0 / 60.0) / sps
                else:
                    tv_ml = 0.0

                # 3-point moving average
                smoothed_tv = (last_tv2 + last_tv + tv_ml) / 3.0 if i >= 2 else tv_ml
                last_tv2 = last_tv
                last_tv = tv_ml

                if calc_tv and tv_evl is not None:
                    raw_tv = int(smoothed_tv / tv_evl.gain)
                    tv_evl.add_event(mid_time, raw_tv)

            # --- Respiratory Rate (RR) ---
            breath_time = start_time + int(breath.start_idx * rate_ms)
            if calc_resp and rr_evl is not None:
                window_breaths.append(breath_time)
                # Remove breaths older than window
                cutoff = breath_time - window_size_ms
                while window_breaths and window_breaths[0] < cutoff:
                    window_breaths.pop(0)

                # Count breaths in window
                rr = len(window_breaths)
                # Scale to per-minute: if window is partial (<60s), scale up
                elapsed = breath_time - (window_breaths[0] if window_breaths else breath_time)
                if elapsed > 0 and elapsed < window_size_ms:
                    rr = rr * (window_size_ms / elapsed)

                raw_rr = int(rr / rr_evl.gain)
                rr_evl.add_event(mid_time, raw_rr)

            # --- Minute Ventilation (MV) ---
            if calc_mv and mv_evl is not None and calc_resp:
                # MV = TV (L) * RR (breaths/min)
                current_rr = rr if (calc_resp and rr_evl is not None) else 15.0
                mv_lpm = (smoothed_tv / 1000.0) * current_rr
                raw_mv = int(mv_lpm / mv_evl.gain)
                mv_evl.add_event(mid_time, raw_mv)


# ============================================================================
# Standalone calculation functions
# ============================================================================

def calc_ahi(session: 'Session', start: int = -1, end: int = -1) -> float:
    """Calculate AHI for a session or time range.

    Args:
        session: Session to calculate for.
        start: Start time (ms epoch), -1 for session start.
        end: End time (ms epoch), -1 for session end.

    Returns:
        AHI value (events per hour).
    """
    if start < 0:
        start = session.first_time
    if end < 0:
        end = session.last_time

    duration_hours = (end - start) / 3600000.0
    if duration_hours <= 0:
        return 0.0

    total_events = 0
    for ch_id in AllAhiChannels:
        evlists = session.get_event_list(ch_id)
        if not evlists:
            continue
        for evl in evlists:
            if evl.count == 0:
                continue
            if evl.type == EventListType.EVL_Event:
                times = evl.timestamps()
                total_events += int(np.sum((times >= start) & (times <= end)))
            else:
                total_events += evl.count

    return total_events / duration_hours


def calc_ahi_graph(
    session: 'Session',
    window_minutes: float = 60.0,
) -> Optional[EventList]:
    """Calculate sliding-window AHI graph as an EventList.

    Creates a CPAP_AHI channel with AHI values sampled every 30 seconds
    over a trailing window.

    Args:
        session: Session containing event data.
        window_minutes: Window size in minutes (default 60).

    Returns:
        The created CPAP_AHI EventList, or None if no data.
    """
    first = session.first_time
    last = session.last_time
    if not first or not last or last <= first:
        return None

    window_ms = int(window_minutes * 60000)
    step_ms = 30000  # 30-second steps
    hours = window_minutes / 60.0

    # Collect all AHI event timestamps
    all_times: List[np.ndarray] = []
    for ch_id in AllAhiChannels:
        evlists = session.get_event_list(ch_id)
        if not evlists:
            continue
        for evl in evlists:
            if evl.count > 0 and evl.type == EventListType.EVL_Event:
                all_times.append(evl.timestamps())

    if not all_times:
        # No events at all - create flat zero AHI line
        ahi_evl = session.add_event_list(
            CPAP_AHI, EventListType.EVL_Event,
            gain=0.02, offset=0.0,
        )
        ahi_evl.dimension = STR_UNIT_EventsPerHour
        ahi_evl.add_event(first, 0)
        ahi_evl.add_event(last, 0)
        return ahi_evl

    event_times = np.sort(np.concatenate(all_times))

    # Create output EventList
    ahi_evl = session.add_event_list(
        CPAP_AHI, EventListType.EVL_Event,
        gain=0.02, offset=0.0,
    )
    ahi_evl.dimension = STR_UNIT_EventsPerHour

    # Sliding window
    ti = first
    while ti <= last:
        window_start = ti - window_ms
        if window_start < first:
            window_start = first

        # Count events in window
        count = int(np.sum((event_times >= window_start) & (event_times <= ti)))

        # Calculate AHI for the window
        actual_window_hours = (ti - window_start) / 3600000.0
        if actual_window_hours > 0:
            ahi = count / actual_window_hours
        else:
            ahi = 0.0

        raw_ahi = int(ahi / ahi_evl.gain)
        ahi_evl.add_event(ti, raw_ahi)

        ti += step_ms

    return ahi_evl


def calc_leaks(
    session: 'Session',
    pressure_baseline_fn=None,
) -> Optional[EventList]:
    """Calculate unintentional leak from total leak and pressure.

    Unintentional leak = total_leak - mask_baseline(pressure)

    Args:
        session: Session with CPAP_Leak data.
        pressure_baseline_fn: Optional function(pressure) -> baseline_leak.
            If None, uses a simple linear model: baseline = 0.8 * pressure.

    Returns:
        Modified leak EventList, or None if no leak data.
    """
    leak_lists = session.get_event_list(CPAP_Leak)
    if not leak_lists:
        return None

    if pressure_baseline_fn is None:
        def pressure_baseline_fn(p):
            return 0.8 * p

    # For now, just return the existing leak data unchanged
    # Full implementation would subtract baseline from total leak
    return leak_lists[0] if leak_lists else None


def flag_large_leaks(
    session: 'Session',
    threshold: float = 24.0,
) -> Optional[EventList]:
    """Flag leak events above a threshold.

    Creates CPAP_LargeLeak events where leak rate exceeds threshold.

    Args:
        session: Session with CPAP_Leak data.
        threshold: Leak rate threshold in L/min (default 24.0).

    Returns:
        The created CPAP_LargeLeak EventList, or None if no leak data.
    """
    leak_lists = session.get_event_list(CPAP_Leak)
    if not leak_lists:
        return None

    flag_evl = session.add_event_list(
        CPAP_LargeLeak, EventListType.EVL_Event,
        gain=1.0, offset=0.0,
    )
    flag_evl.dimension = STR_UNIT_LPM

    for leak_evl in leak_lists:
        if leak_evl.count == 0:
            continue
        phys = leak_evl.physical_data()
        times = leak_evl.timestamps()
        mask = phys > threshold
        indices = np.where(mask)[0]

        # Find contiguous spans and record start of each
        if len(indices) == 0:
            continue

        in_span = False
        span_start = 0
        for idx in indices:
            if not in_span:
                span_start = idx
                in_span = True
            elif idx > indices[0] and (idx - 1) not in set(indices):
                # Gap detected, record previous span
                duration = int(times[idx - 1] - times[span_start])
                flag_evl.add_event(int(times[span_start]), duration)
                span_start = idx

        # Record final span
        if in_span:
            last_idx = indices[-1]
            duration = int(times[last_idx] - times[span_start])
            flag_evl.add_event(int(times[span_start]), duration)

    return flag_evl


def calc_resp_rate(session: 'Session') -> bool:
    """Convenience wrapper: run FlowParser on all flow EventLists in session.

    Creates derived channels: CPAP_RespRate, CPAP_TidalVolume,
    CPAP_Ti, CPAP_Te, CPAP_MinuteVent.

    Args:
        session: Session containing CPAP_FlowRate data.

    Returns:
        True if any calculations were performed.
    """
    flow_lists = session.get_event_list(CPAP_FlowRate)
    if not flow_lists:
        return False

    # Check which channels need calculation
    needs_rr = session.get_event_list(CPAP_RespRate) is None
    needs_tv = session.get_event_list(CPAP_TidalVolume) is None
    needs_ti = session.get_event_list(CPAP_Ti) is None
    needs_te = session.get_event_list(CPAP_Te) is None
    needs_mv = session.get_event_list(CPAP_MinuteVent) is None

    if not (needs_rr or needs_tv or needs_ti or needs_te or needs_mv):
        return False  # All channels already exist

    calculated = False
    for flow_evl in flow_lists:
        if flow_evl.count < 2:
            continue

        parser = FlowParser(session, flow_evl)
        parser.calc(
            calc_resp=needs_rr,
            calc_tv=needs_tv,
            calc_ti=needs_ti,
            calc_te=needs_te,
            calc_mv=needs_mv,
        )
        calculated = True

    return calculated
