# AWAPS indi-allsky maintenance branch

Upstream: <https://github.com/aaronwmorris/indi-allsky>.
Fork: <https://github.com/mburge/indi-allsky/tree/awaps>.

`main` remains upstream's source. `awaps` carries small separate commits for our
local application patches, tests, and build documentation. Deployment is always
a separate action against a tested package; this branch is not installed on any
camera merely because it was pushed.

See [patch inventory](patches.md), [recovered provenance](recovered-source.json),
and [fixed-clock scheduling proposal](scheduler-proposal.md).

## Test the recovered fix

Use Python 3.9+ with `ephem` installed (the only non-standard dependency these
tests need):

```sh
python3 -m unittest discover -s awaps/tests -v
```

The tests import the real exposure controller classes and exercise gain limits
without opening cameras, modifying configuration, or connecting to INDI.

## Build the camera .deb

Requires Docker with Linux ARM64 support, Python 3, Git, and network access.
Run from a committed `awaps` checkout:

```sh
bash awaps/build-deb.sh /absolute/path/to/test-artifacts
```

The build archives exactly the committed source into a separate temporary
workspace, resolves the Debian Trixie container image to its digest, and uses
upstream `debian/rules`/`dpkg-buildpackage` to construct the application's ARM64
package, including upstream's bundled virtualenv. It does not rebuild or deploy
INDI core or camera drivers. The package version includes the source commit:
`<upstream-version>+awaps.<12-character-commit>+trixie`.

Outputs include the `.deb`, build metadata, recorded source/image identities,
package inspection, and SHA256 checksums. The build workspace is retained for
inspection. No package maintainer scripts are executed by our inspection, and
no installation or service operation occurs on the cameras.

Upstream dependencies are resolved online and are not fully pinned. A source
commit and image digest make the source/build identity auditable but do **not**
make dependency resolution bit-for-bit reproducible. Retain the produced
package and build logs; stricter dependency locking is future work.

A separate **manual-only**, read-permission GitHub Actions workflow is provided
in `.github/workflows/awaps-test-build.yml`. It uploads artifacts and contains no
schedule, release publishing, APT publishing, deployment, or camera credentials.
It has not been enabled or run. GitHub may require workflow registration on the
default branch before manual dispatch; do not change `main` or enable inherited
workflows to work around that without an explicit decision.

## Updating upstream

```sh
git fetch upstream
git switch awaps
git rebase upstream/main
python3 -m unittest discover -s awaps/tests -v
```

If upstream has incorporated a patch, retire that commit after checking its
behavior and keep its regression coverage. Inspect package changes and compare
our tests before building. Rebase rewrites the branch: coordinate before any
force push. Do not change camera package holds or install a new package as part
of a source update.

## Initial verification, October 23, 2026

- Recovered source is byte-identical across all three installed camera copies.
- Moon-mode regression cases fail against unpatched upstream, with no fixture
  errors; all six test methods pass with the recovered fix.
- Branch is based on identified upstream commit `18b8407d3184`; the exact source
  commit of the installed October 5 package is not established.
- Test build has not run: local Docker daemon is unavailable. Automatic approval
  review rejected enabling the inherited workflow because it includes scheduled
  publication and deployment. That inherited workflow was not enabled or run.
- Package-build scripts and manual workflow are prepared; a successful package
  build and installation test are still required before deployment.
