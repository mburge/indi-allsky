# AWAPS patch inventory

Branch baseline: upstream `main` at `18b8407d31843f3df9c69f8b5b16443f7df65c82`
(October 19, 2026). This is a maintenance/test branch, not a deployment record.

## 1. Exposure-priority auto-gain: moon-mode limits

Recovered October 23, 2026 from the package-managed application source on all
three cameras. All three installed package versions were
`2026.09.01~nightly.20261005.0834+trixie` (ARM64).

- File: `indi_allsky/exposure/autogain_exposurepriority_dB.py`.
- Change: when both nighttime and moon mode are active, return the moon-mode
  minimum and maximum gain rather than the normal night limits.
- Recovery SHA256, identical on all three cameras:
  `6dc5caddb45e` (full digest recorded in `recovered-source.json`).
- All 280 installed package-listed `.py`, `.sh`, and `.json` files were compared
  with their package MD5 manifest on each camera. Only this application source
  file differed. This scope excludes generated configuration, virtualenvs,
  native camera libraries, systemd overrides, and files outside the manifest.
- The recovered file's unpatched content matches the current upstream file;
  this six-line fix remains absent from the selected upstream baseline.
- No changes to capture period or image/exposure data are included.

The exact Git revision used to produce the installed October 5 package has not
been established. Its version must not be treated as proof of a specific source
commit. The branch is deliberately based on the identified October 19 upstream
commit rather than a guessed package source revision.

Regression checks exercise all four gain-scale classes, nighttime/daytime mode
selection, live mode transitions, and minimum/maximum gain clamping. The tests
must fail on the unpatched upstream baseline and pass with the recovered fix.

## 2. Fixed-clock exposure scheduler — proposed, not implemented

See `scheduler-proposal.md`. This branch does not yet change exposure timing.
AWAPS's node manager and OliveTin are maintained in `mburge/awaps`; they are not
indi-allsky patches and must not be mixed into this upstream source fork.
