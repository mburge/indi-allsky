# Fixed-clock exposure scheduling — proposal only

Status: no scheduling code has been changed or deployed. The user approved a
common clock grid and skipping missed slots. Values/edge cases below remain
reviewable proposals.

## Concrete target

With a 15-second period and a 10-second phase, each camera aims for UTC seconds
`:10`, `:25`, `:40`, `:55`. UTC and local seconds agree; use Unix wall-clock time
for the common phase, independent of startup time or timezone/DST. For periods
that do not divide 60, define the grid as `10 + k * period` seconds since the
Unix epoch rather than resetting the phase every minute.

The installed upstream loop currently sets `frame_start_time = now_time` and
then `next_frame_time = frame_start_time + EXPOSURE_PERIOD + add_period_delay`.
Its 50 ms polling sleep and variable work can move each following start. FITS
measurements after October 22's startup show 0.183 s initial spread becoming
23.927 s by morning over 1,274 corresponding 30-second cycles.

## Proposed implementation boundary

1. Add an opt-in clock-grid scheduler, disabled by default; do not change normal
   indi-allsky scheduling or any database schema when it is disabled.
2. Start at the next future grid slot after initialization. Ignore/segregate
   startup, focus, calibration, and SQM exposures so they cannot masquerade as
   synchronized science frames. Inspect every `shoot()` entry point before
   claiming complete coverage.
3. Compute the next slot from the fixed phase and period, never from the last
   actual exposure time. Use a monotonic deadline while waiting and re-evaluate
   the wall-clock mapping after clock corrections or a configuration change.
4. Do not start when the camera is busy, not ready, or under a safety backoff.
   Skip missed slots; retain the common grid when work resumes. No catch-up
   bursts and no service restarts for ordinary drift.
5. Suggested initial lateness allowance: 100 ms after the target. Strictly zero
   lateness is not realistic for Linux/USB/INDI. This value needs agreement and
   measurement; it must not silently become the one-second alignment target.
6. Account for pre-capture hooks running after the existing readiness check.
   Re-check deadline immediately before issuing the exposure command. A hook
   failure must not produce an off-grid exposure in grid mode.
7. Log target UTC, command-issue UTC/monotonic time, lateness, skipped-slot count,
   readiness/backoff reason, and period. FITS DATE-OBS remains the independent
   existing comparison point; do not relabel a late exposure as on-time by
   changing its timestamp. Driver/USB latency can require measured per-camera
   command offsets, which must not be guessed.

## Coordination with AWAPS controls

The existing controller can restart cameras repeatedly and persists per-camera
startup delays. In clock-grid mode those startup phase corrections would be
inappropriate. Keep health/status reporting, replace drift recovery with
observation/alerts, and explicitly gate legacy corrective restarts while grid
mode is active. Do not change that timer until the source patch is reviewed and
all participating cameras report the same grid configuration.

The GUI/config import path must preserve the new setting; inspect config
validation, defaults, and serialization before choosing its final key. Avoid
introducing an option that disappears on the next settings save. The configured
period must still pass exposure duration and disk budgeting checks.

## Required verification before using cameras

- Fake-clock tests: arbitrary startup phase, exact boundary, 15/30/45-second
  periods, long busy exposure, missed slots, hooks exceeding a deadline, forward
  and backward wall-clock adjustments, period changes, disabled-mode behavior,
  and queue backoff. Late frames must never move the grid or trigger bursts.
- Package regression tests for the preserved moon-mode fix.
- Build and inspect a test ARM64/Trixie `.deb`; validate install/upgrade in a
  disposable environment before a physical camera trial.
- Agree on a bounded camera trial, preserve rollback package/configuration, then
  graph scheduled, command-issued, and FITS starts through a meaningful session.
- Full-night verification must measure persistent alignment, missing exposures,
  processing backlog, clock health, and end-of-night behavior. Two successful
  startup cycles are insufficient acceptance criteria.

The next implementation decision is the lateness allowance and scope of the
first trial. No camera-side changes are authorized by this proposal alone.
