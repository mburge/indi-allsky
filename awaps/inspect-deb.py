#!/usr/bin/env python3
"""Check a built test package without executing its installation scripts."""
import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile

folder=pathlib.Path(sys.argv[1])
commit=sys.argv[2]
packages=list(folder.glob('indi-allsky_*.deb'))
if len(packages)!=1:
    raise SystemExit(f'Expected one indi-allsky package, found {len(packages)}')
package=packages[0]
fields=subprocess.check_output(['dpkg-deb','-f',str(package),'Package','Version','Architecture'],text=True)
if 'Architecture: arm64' not in fields or f'+awaps.{commit[:12]}+trixie' not in fields:
    raise SystemExit('Package architecture/version does not match the recorded source')
with tempfile.TemporaryDirectory(prefix='awaps-package-inspection-') as temp:
    subprocess.run(['dpkg-deb','-x',str(package),temp],check=True)
    root=pathlib.Path(temp)/'usr/share/indi-allsky'
    relative=pathlib.Path('indi_allsky/exposure/autogain_exposurepriority_dB.py')
    expected=pathlib.Path(relative).read_bytes()
    if (root/relative).read_bytes()!=expected:
        raise SystemExit('Packaged exposure source differs from the build source')
    # Check that upstream's bundled dependency archive is present.
    archive=root/'venv.tar.zst'
    if not archive.is_file() or not archive.stat().st_size:
        raise SystemExit('Bundled virtualenv is missing')
    manifest={'source_commit':commit,'package':package.name,'control_fields':fields,'exposure_source_sha256':hashlib.sha256(expected).hexdigest(),'bundled_venv_bytes':archive.stat().st_size,'validation_scope':'package metadata, recovered source bytes, bundled-venv presence; no installation or camera validation'}
(folder/'package-inspection.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(fields,end='')
print('Package source and bundled virtualenv checks passed; installation not performed.')
