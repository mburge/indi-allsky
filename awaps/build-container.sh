#!/usr/bin/env bash
# Run only inside an isolated Debian Trixie ARM64 build container.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
cd /build/source
if [[ $(dpkg --print-architecture) != arm64 ]]; then
    echo 'This build is scoped to the AWAPS ARM64 cameras.' >&2
    exit 1
fi
apt-get update
apt-get install -y --no-install-recommends \
    build-essential dpkg-dev debhelper dh-python python3-all python3-setuptools \
    python3-venv python3-dev python3-pip python3-wheel zstd git ca-certificates \
    pkgconf libindi-dev swig libcurl4-gnutls-dev libssl-dev libusb-1.0-0-dev \
    libdbus-1-dev libglib2.0-dev libsystemd-dev libraw-dev libopenblas-dev \
    libjpeg-dev libpng-dev libtiff-dev zlib1g-dev libffi-dev
python3 -m venv /tmp/awaps-regression-venv
/tmp/awaps-regression-venv/bin/python -m pip install ephem
/tmp/awaps-regression-venv/bin/python -m unittest discover -s awaps/tests -v
python3 misc/bump_version.py "$AWAPS_PACKAGE_VERSION" unstable
export SOURCE_DATE_EPOCH="$AWAPS_SOURCE_DATE_EPOCH"
export DEB_BUILD_OPTIONS='noautodbgsym noddebs'
dpkg-buildpackage -b -us -uc -j"$(nproc)"
# Retain package artifacts and Debian build metadata.
mkdir -p /build/artifacts
for file in /build/indi-allsky_*.deb /build/*.buildinfo /build/*.changes; do
    [[ -f $file ]] && cp "$file" /build/artifacts/
done
python3 awaps/inspect-deb.py /build/artifacts "$AWAPS_SOURCE_COMMIT"
cp /build/source-record.json /build/artifacts/
python3 - <<'PY'
import hashlib,json,pathlib
folder=pathlib.Path('/build/artifacts')
files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.iterdir()) if p.is_file()}
(folder/'SHA256SUMS').write_text(''.join(f'{digest}  {name}\n' for name,digest in files.items()))
PY
