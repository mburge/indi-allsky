#!/usr/bin/env python3
"""Build only the version-checked AWAPS timing overlay; never install it."""
import hashlib,json,os,pathlib,re,shutil,subprocess,sys,tempfile
repo=pathlib.Path(__file__).resolve().parents[1]
commit=os.environ.get('AWAPS_ARCHIVE_COMMIT')
if commit:
    if not re.fullmatch('[0-9a-f]{40}',commit):raise SystemExit('Invalid archive source commit')
else:
    commit=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()
    if subprocess.run(['git','-C',str(repo),'diff','--quiet','HEAD','--']).returncode:
        raise SystemExit('Commit tracked source changes before building')
output=pathlib.Path(sys.argv[1]).resolve();output.mkdir(parents=True,exist_ok=True)
version='0.1.1+git'+commit[:12]
base_version='2026.09.01~nightly.20261005.0834+trixie'
base={
 'indi_allsky/capture.py':'d024e7eda5964d04ffc9389e14c8fcda1f5100d08d38842a612e2f76c0d314a7',
 'indi_allsky/camera/indi.py':'ed71a47447424741f148811efeaf7eb7a62b99ef3c5f2de039f7edeba9a613d2',
}
with tempfile.TemporaryDirectory(prefix='awaps-grid-deb-') as temp:
 root=pathlib.Path(temp);control=root/'DEBIAN';control.mkdir()
 (control/'control').write_text(f'''Package: indi-allsky-awaps-grid
Version: {version}
Architecture: all
Maintainer: AWAPS local administration
Depends: python3 (>= 3.9), indi-allsky (= {base_version})
Section: science
Priority: optional
Description: AWAPS fixed-clock nighttime INDI exposure gate
 Version-checked overlay preserving original files with dpkg-divert.
 Does not restart services or replace INDI drivers or the bundled virtualenv.
''')
 hashes={}
 for relative in [*base,'indi_allsky/clock_grid.py']:
  content=(repo/relative).read_bytes();compile(content,relative,'exec')
  dest=root/'usr/share/indi-allsky'/relative;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(content);dest.chmod(0o644)
  hashes[relative]=hashlib.sha256(content).hexdigest()
 cfg=root/'etc/indi-allsky/awaps-clock-grid.json';cfg.parent.mkdir(parents=True);cfg.write_text(json.dumps({'enabled':True,'phase_seconds':10,'max_lateness_seconds':0.1},indent=2)+'\n');cfg.chmod(0o644)
 (control/'conffiles').write_text('/etc/indi-allsky/awaps-clock-grid.json\n')
 manifest={'source_commit':commit,'package_version':version,'base_package_version':base_version,'baseline_sha256':base,'patched_sha256':hashes,'services_restarted_by_package':False}
 doc=root/'usr/share/doc/indi-allsky-awaps-grid';doc.mkdir(parents=True);(doc/'source.json').write_text(json.dumps(manifest,indent=2)+'\n')
 preinst='''#!/usr/bin/python3
import hashlib,pathlib,subprocess,sys
PACKAGE='indi-allsky-awaps-grid'
BASE_VERSION=BASE_VERSION_VALUE
BASE=BASE_VALUE
version=subprocess.check_output(['dpkg-query','-W','-f=${Version}','indi-allsky'],text=True)
if version!=BASE_VERSION:raise SystemExit('Unexpected indi-allsky version; refusing overlay')
module=pathlib.Path('/usr/share/indi-allsky/indi_allsky/clock_grid.py')
owned=subprocess.run(['dpkg-query','-W','-f=${Status}',PACKAGE],text=True,capture_output=True).stdout
if module.exists() and 'installed' not in owned:raise SystemExit('Unmanaged clock_grid.py exists; refusing overwrite')
for rel,digest in BASE.items():
 p=pathlib.Path('/usr/share/indi-allsky')/rel
 owner=subprocess.check_output(['dpkg-divert','--listpackage',str(p)],text=True).strip()
 if owner and owner!=PACKAGE:raise SystemExit('Another diversion owns '+str(p))
 original=pathlib.Path(str(p)+'.awaps-original') if owner else p
 if not original.is_file() or hashlib.sha256(original.read_bytes()).hexdigest()!=digest:
  raise SystemExit('Original source checksum mismatch: '+str(p))
added=[]
try:
 for rel in BASE:
  p=pathlib.Path('/usr/share/indi-allsky')/rel
  owner=subprocess.check_output(['dpkg-divert','--listpackage',str(p)],text=True).strip()
  if not owner:
   subprocess.run(['dpkg-divert','--package',PACKAGE,'--add','--rename','--divert',str(p)+'.awaps-original',str(p)],check=True);added.append(p)
except Exception:
 for p in reversed(added):subprocess.run(['dpkg-divert','--package',PACKAGE,'--remove','--rename','--divert',str(p)+'.awaps-original',str(p)],check=True)
 raise
'''.replace('BASE_VERSION_VALUE',repr(base_version)).replace('BASE_VALUE',repr(base))
 (control/'preinst').write_text(preinst);(control/'preinst').chmod(0o755)
 postrm='''#!/usr/bin/python3
import pathlib,subprocess,sys
if sys.argv[1] in ('remove','abort-install','disappear'):
 for rel in BASE_VALUE:
  p=pathlib.Path('/usr/share/indi-allsky')/rel
  owner=subprocess.check_output(['dpkg-divert','--listpackage',str(p)],text=True).strip()
  if owner=='indi-allsky-awaps-grid':
   if p.exists():raise SystemExit('Refusing to replace an unexpected remaining file: '+str(p))
   subprocess.run(['dpkg-divert','--package','indi-allsky-awaps-grid','--remove','--rename','--divert',str(p)+'.awaps-original',str(p)],check=True)
'''.replace('BASE_VALUE',repr(base))
 (control/'postrm').write_text(postrm);(control/'postrm').chmod(0o755)
 (control/'postinst').write_text('#!/bin/sh\nset -eu\necho "AWAPS clock-grid source installed. Services were not restarted; an explicit controlled restart is required."\n');(control/'postinst').chmod(0o755)
 for p in root.rglob('*'):
  if p.is_dir():p.chmod(0o755)
 package=output/f'indi-allsky-awaps-grid_{version}_all.deb'
 subprocess.run(['dpkg-deb','--build','--root-owner-group',str(root),str(package)],check=True)
 (output/'overlay-source.json').write_text(json.dumps(manifest,indent=2)+'\n')
 print(package)
