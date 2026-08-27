#!/usr/bin/env bash
# Build the two importable Ignition project zips.
#
#   ./package.sh                  -> dist/OEE.zip
#                                    dist/KPI.zip            (dev titles)
#   ./package.sh --release [VER]  -> dist/OEE-<VER>.zip
#                                    dist/KPI-<VER>.zip
#
# These are plain project exports, nothing else: Platform > Projects > Import
# Project takes them directly, and everything a gateway needs beyond the project
# itself -- database, tag provider, historian, simulator, tags, tables, roster,
# demo history -- is built by the Setup button on the project's own Settings page.
# There is no separate resource package any more, no MANIFEST, and no Tags/ or
# Gateway/ folder to unpack by hand.
#
# The zip is built from INSIDE the project directory (`cd final/OEE && zip -r`),
# which is what the importer expects: a zip whose members start with project.json,
# not with a wrapping folder.
#
# VER defaults to the tag HEAD is exactly on, so cutting a release is
#   git tag v3.0.0 && ./package.sh --release
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIST="$HERE/dist"

# The zips are built from the working tree, not from git, so a gitignored file on
# disk ships without ever appearing in `git status`. That is exactly how a stray
# __pycache__ went out inside a script resource in 2.1.0. Fail here rather than
# discover it on someone else's gateway.
python3 "$HERE/tools/check_resources.py" "$HERE/final/OEE" "$HERE/final/KPI"

command -v zip >/dev/null || { echo "package: zip not installed" >&2; exit 2; }

VERSION=""
if [[ "${1:-}" == "--release" ]]; then
  VERSION="${2:-}"
  if [[ -z "$VERSION" ]]; then
    VERSION="$(cd "$HERE" && git describe --tags --exact-match 2>/dev/null || true)"
    [[ -n "$VERSION" ]] || {
      echo "package.sh --release: no version given and HEAD is not exactly on a tag" >&2
      exit 2; }
  fi
  VERSION="${VERSION#v}"   # tags are vX.Y.Z; the title wants the bare number
elif [[ -n "${1:-}" ]]; then
  echo "package: unknown argument $1" >&2; exit 2
fi

# The installer endpoints must be reachable unauthenticated to be driven from a
# script, but they can truncate the example tables -- so the published copy
# always requires auth. install.sh re-opens them for the duration of an install.
harden() {
  python3 -c '
import json, sys
p = sys.argv[1]
d = json.load(open(p))
d["doGet"]["require-auth"] = True
json.dump(d, open(p, "w"), indent=2)' "$1"
}

# Every released project carries its version in the Title AND at the end of the
# Description (workspace CLAUDE.md, 24/08/2026): Config > Projects shows only the
# Description column, while the Title shows in the Edit drawer and on the
# Perspective launch surfaces, so both are stamped. The working copy under final/
# keeps a "(dev)" title, and this only ever touches the staged copy in dist/.
stamp_version() {
  python3 -c '
import json, re, sys
p, version = sys.argv[1], sys.argv[2]
d = json.load(open(p))
d["title"] = re.sub(r"\s*\(dev\)$", "", d["title"]) + " " + version
d["description"] = d["description"] + " · v" + version
json.dump(d, open(p, "w"), indent=2)' "$1" "$2"
}

rm -rf "$DIST"
mkdir -p "$DIST"

for PROJ in OEE KPI; do
  case "$PROJ" in
    OEE) ENDPOINT=lp_init ;;
    KPI) ENDPOINT=kpi_init ;;
  esac
  STAGE="$DIST/stage-$PROJ"
  cp -r "$HERE/final/$PROJ" "$STAGE"

  harden "$STAGE/com.inductiveautomation.webdev/resources/$ENDPOINT/config.json"

  if [[ -n "$VERSION" ]]; then
    stamp_version "$STAGE/project.json" "$VERSION"
    # ignition/global-props/data.bin is THIS RIG's Project Properties, serialised
    # by Ignition. Nothing in either project needs it -- every named query names
    # its own database ("Examples") and neither project has an identity provider
    # -- so shipping it would only push this machine's settings onto whoever
    # imports the zip. Excluded, a fresh import registers with no global-props
    # resource at all and falls back to Ignition's own defaults. Note that an
    # import over an EXISTING project with "Allow Overwrite" ticked is a
    # resource-level replace, so it clears the target's Project Properties too.
    rm -rf "$STAGE/ignition/global-props"
  fi

  # A release artefact carries its version in the FILENAME as well (Nigel,
  # 26/08/2026) -- a bare downloaded zip is unidentifiable. Dev builds stay
  # unversioned.
  ZIP="$DIST/$PROJ${VERSION:+-$VERSION}.zip"
  ( cd "$STAGE" && zip -qr "$ZIP" . )
  rm -rf "$STAGE"
  echo "  $(basename "$ZIP")"
done

echo
echo "project zips built:"
ls -1sh "$DIST"/*.zip
