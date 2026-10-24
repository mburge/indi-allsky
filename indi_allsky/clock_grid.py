"""Opt-in AWAPS wall-clock gating immediately before INDI exposure commands."""
import json
import logging
import math
from pathlib import Path
import time

logger = logging.getLogger('indi_allsky')
SETTINGS = Path('/etc/indi-allsky/awaps-clock-grid.json')


class ClockGrid:
    def __init__(self, phase=10.0, max_lateness=0.1, clock=time):
        if not math.isfinite(phase) or not 0 <= phase < 300:
            raise ValueError('Clock-grid phase must be 0–300 seconds')
        if not math.isfinite(max_lateness) or not 0 < max_lateness <= 0.1:
            raise ValueError('Clock-grid maximum lateness must be at most 100 ms')
        self.phase = phase
        self.max_lateness = max_lateness
        self.clock = clock
        self.last_slot = None
        self.period = None
        self.skipped = 0

    def future_slot(self, now, period):
        return self.phase + (math.floor((now - self.phase) / period) + 1) * period

    def wait(self, period):
        period = float(period)
        if not math.isfinite(period) or not 15 <= period <= 300:
            raise ValueError('Clock-grid period must be 15–300 seconds')
        now = self.clock.time()
        if self.period == period and self.last_slot is not None:
            target = self.last_slot + period
        else:
            target = self.future_slot(now, period)
            if self.last_slot is not None:
                target = max(target, self.future_slot(self.last_slot, period))
        self.period = period
        wall, mono = now, self.clock.monotonic()
        while True:
            now = self.clock.time()
            current_mono = self.clock.monotonic()
            # A wall-clock step invalidates the previous wait mapping. Never
            # issue the same or an older slot twice after a backward step.
            if abs((now - wall) - (current_mono - mono)) > 0.25:
                floor = max(now, self.last_slot) if self.last_slot is not None else now
                target = self.future_slot(floor, period)
                logger.warning('AWAPS_GRID clock step; rescheduled target=%.6f', target)
            wall, mono = now, current_mono
            if now > target + self.max_lateness:
                missed = math.ceil((now - target - self.max_lateness) / period)
                self.skipped += missed
                target += missed * period
                logger.warning('AWAPS_GRID skipped=%d total_skipped=%d target=%.6f', missed, self.skipped, target)
            remaining = target - now
            if remaining <= 0:
                self.last_slot = target
                return target
            # Short sleeps keep the wall/monotonic mapping responsive to NTP
            # steps; no busy spinning or accumulated relative-period error.
            self.clock.sleep(min(remaining, 0.02))


def load_clock_grid(path=SETTINGS):
    try:
        settings = json.loads(Path(path).read_text())
    except FileNotFoundError:
        return None
    if not isinstance(settings, dict) or not isinstance(settings.get('enabled'), bool):
        raise ValueError('Clock-grid settings must have an explicit boolean enabled flag')
    if not settings['enabled']:
        return None
    return ClockGrid(float(settings.get('phase_seconds', 10)),
                     float(settings.get('max_lateness_seconds', 0.1)))
