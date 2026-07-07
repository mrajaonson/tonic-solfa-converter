"""Duration assignment and hold consolidation."""

from .models import TimedEvent


def assign_durations(measures: list[dict], time_sig: str) -> list[list[TimedEvent]]:
    """
    Walk through parsed measures and compute quarter-length durations.

    Duration logic:
      measure_ql = num_beats * (4.0 / denominator)
      Each beat group (separated by :) gets measure_ql / num_groups.
      Within a group, notes share the group's duration equally.
    """
    num, den = map(int, time_sig.split("/"))
    beat_ql = 4.0 / den
    measure_ql = num * beat_ql

    result = []
    for meas in measures:
        timed_events: list[TimedEvent] = []
        beats = meas["beats"]
        n_groups = len(beats) if beats else 1
        # A partial/pickup measure (boundary barline omitted, fewer beats than
        # the time signature) keeps each beat at its natural length instead of
        # stretching the fragment across a full measure - so it stays short and
        # renders as a proper incomplete measure downstream.
        if meas.get("is_partial"):
            group_ql = beat_ql
        else:
            group_ql = measure_ql / n_groups

        for beat_notes in beats:
            n_events = len(beat_notes)
            if n_events == 0:
                continue
            sub_ql = group_ql / n_events
            for evt in beat_notes:
                if evt.is_rest and evt.raw == "**":
                    timed_events.append(TimedEvent(evt, beat_ql * 2))
                else:
                    timed_events.append(TimedEvent(evt, sub_ql))

        result.append(timed_events)
    return result


def consolidate_holds(timed_measures: list[list[TimedEvent]]) -> list[list[TimedEvent]]:
    """
    Merge consecutive holds into the preceding note, extending its duration.
    Fermata and dynamics on a hold are transferred to the note being extended.
    Cross-measure holds are handled separately via ties.
    """
    result = []
    for events in timed_measures:
        consolidated: list[TimedEvent] = []
        for te in events:
            if te.event.is_hold and consolidated:
                # Extend previous note's duration
                consolidated[-1].quarter_length += te.quarter_length
                # Transfer fermata from hold to the note
                if te.event.fermata:
                    consolidated[-1].event.fermata = True
                # Transfer dynamic from hold to the note (if not already set)
                if te.event.dynamic and not consolidated[-1].event.dynamic:
                    consolidated[-1].event.dynamic = te.event.dynamic
            else:
                consolidated.append(TimedEvent(te.event, te.quarter_length))
        result.append(consolidated)
    return result
