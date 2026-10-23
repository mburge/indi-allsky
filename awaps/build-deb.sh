#!/usr/bin/env bash
# Build a test artifact only. Never install packages or start camera services.
set -euo pipefail
repo=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
cd "$repo"
if ! git diff --quiet HEAD --; then
    echo 'Commit tracked changes before building an identified source revision.' >&2
    exit 1
fi
commit=$(git rev-parse HEAD)
short_commit=$(git rev-parse --short=12 HEAD)
source_date=$(git show -s --format=%ct HEAD)
base_version=$(python3 misc/bump_version.py --show | awk '{print $NF}')
version="${base_version}+awaps.${short_commit}+trixie"
output=${1:-"$repo/awaps/build"}
mkdir -p "$output"
output=$(cd "$output" && pwd)
docker info >/dev/null
build_dir=$(mktemp -d "${TMPDIR:-/tmp}/awaps-indi-build.XXXXXX")
printf 'Source: %s\nVersion: %s\nBuild workspace: %s\nArtifacts: %s\n' "$commit" "$version" "$build_dir" "$output"
mkdir -p "$build_dir/source"
git archive "$commit" | tar -x -C "$build_dir/source"
docker pull --platform linux/arm64 debian:trixie
image=$(docker image inspect debian:trixie --format '{{index .RepoDigests 0}}')
python3 - "$build_dir/source-record.json" "$commit" "$version" "$image" <<'PY'
import json,pathlib,sys
path,commit,version,image=sys.argv[1:]
pathlib.Path(path).write_text(json.dumps({'source_commit':commit,'package_version':version,'container_image':image,'architecture':'arm64','distribution':'trixie','deployment_performed':False},indent=2)+'\n')
PY
docker run --rm --platform linux/arm64 \
    --mount "type=bind,source=$build_dir,target=/build" \
    -e "AWAPS_SOURCE_COMMIT=$commit" \
    -e "AWAPS_PACKAGE_VERSION=$version" \
    -e "AWAPS_SOURCE_DATE_EPOCH=$source_date" \
    "$image" bash /build/source/awaps/build-container.sh
cp "$build_dir"/artifacts/* "$output/"
printf '\nBuild finished. No installation performed. Build workspace retained: %s\n' "$build_dir"
