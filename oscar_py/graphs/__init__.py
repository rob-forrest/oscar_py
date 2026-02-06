"""
Graph Visualization Framework for OSCAR Python Port

This module provides PyQtGraph-based graph visualization components
for displaying sleep data waveforms, events, and statistics.

Copyright (c) 2019-2025 The OSCAR Team
License: GPL v3
"""

from .graph_view import GraphView
from .line_chart import LineChart
from .time_axis import TimeAxisItem
from .event_flags import (
    EventFlag,
    EventFlagItem,
    EventFlagsOverlay,
    EventFlagsLayer,
    EventSummaryWidget,
    EVENT_COLORS,
    EVENT_LABELS,
    create_sample_events,
    add_event_flags_to_chart,
)

__all__ = [
    'GraphView',
    'LineChart',
    'TimeAxisItem',
    'EventFlag',
    'EventFlagItem',
    'EventFlagsOverlay',
    'EventFlagsLayer',
    'EventSummaryWidget',
    'EVENT_COLORS',
    'EVENT_LABELS',
    'create_sample_events',
    'add_event_flags_to_chart',
]
