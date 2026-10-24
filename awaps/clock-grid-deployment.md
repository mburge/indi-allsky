# Clock-grid deployment for October 23, 2026

Authorized target: allsky-02 and allsky-03. Leave allsky-01 untouched while its
SSH access is unavailable. The user approved a narrow `.deb` overlay against
the installed October 5 application and a 100 ms maximum command lateness.

## Runtime design

`clock_grid.py` reads root-managed `/etc/indi-allsky/awaps-clock-grid.json` when
the INDI client is created. Missing/disabled settings retain upstream behavior.
At night, the ordinary `indi` client gates the actual CCD_EXPOSURE number-vector
send after gain/binning and control lookup. It waits for epoch slots
`10 + k * EXPOSURE_PERIOD`, revalidates/reapplies the vector before sending,
records the actual command timestamp, and logs `AWAPS_GRID` target/issued time,
lateness, period, and skipped slots. The capture loop prepares the next command as soon as the previous frame
is complete; the driver then waits for its fixed target. Waiting until the
target in the outer loop was observed to skip alternate slots during the first
live trial because ordinary control lookup then exceeded the 100 ms deadline. Existing processing backoff is
preserved and results in skipped slots, not off-grid catch-up exposures.

At 15 seconds: :10, :25, :40, :55. A missed command deadline waits for the next
eligible slot. Hardware/driver latency after the command and host-clock error
remain possible; compare real FITS timestamps and monitor persistence before
claiming physical exposure alignment. Existing SDK USB resets are not changed.

Daytime is unchanged. Grid mode refuses nighttime focus/SQM capture rather than
silently taking off-grid frames. Other camera backends and calibration capture
paths are not certified by this first deployment. Stop grid mode before using
those workflows; do not assume GUI settings will toggle this root-managed file.

## Package and rollback

`awaps/build-overlay.py OUTPUT_DIR` builds `indi-allsky-awaps-grid`, a pure-Python
package that depends on the exact installed indi-allsky version. It replaces
only `capture.py` and `camera/indi.py`, adds `clock_grid.py` and opt-in settings,
and preserves originals using package-owned dpkg diversions. Original source
SHA256 checks run before adding any diversion. It does not replace camera SDKs,
drivers, virtualenvs, image data, or the existing moon-mode patch, and it does
not stop/start services automatically.

A source archive exported from a committed branch can be built on a native
Debian host with `AWAPS_ARCHIVE_COMMIT=<full-source-commit> python3
awaps/build-overlay.py OUTPUT_DIR`. This is for the reviewed archive only;
compare payload hashes with the manifest/source commit before installation.

The deployment procedure must:

1. Confirm both clocks synchronized, cadence 15, capture healthy, focus/SQM off,
   baseline source checksums matched, and adequate disk space.
2. Save original source and a service-state record; inspect package metadata,
   checksums, and syntax. Install on one camera and verify diversion ownership.
3. Install the committed AWAPS clock-grid condition drop-in and active marker
   on the controller so legacy restart-based correction cannot fight grid
   capture if node 01 returns. Keep ordinary health/status collection running.
4. Stop capture gracefully using SIGINT plus a runtime `Restart=no` override;
   wait for the main process to exit before restarting. Never force-kill active
   image workers. Remove only the deployment's own runtime override before start.
5. Validate AWAPS_GRID logs and new FITS on the first camera, then deploy the
   exact same package on the second and compare at least ten consecutive cycles.

Rollback: gracefully stop capture; `sudo dpkg --remove indi-allsky-awaps-grid`
restores original source through dpkg-divert. Verify original SHA256s, remove
only the deployment's runtime restart override, and start capture. Remove the
residual `/etc/indi-allsky/awaps-clock-grid.json` conffile only when no longer
needed (unpatched source does not read it). Remove the controller's active marker/condition guard only after grid mode is
removed from all participating nodes; the timer itself remains enabled.

No success/deployment result is claimed by this runbook. Record actual package
version, start time, per-camera checks, gaps, and verification measurements in
the deployment report after those actions complete.
