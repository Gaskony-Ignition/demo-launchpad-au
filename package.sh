#!/usr/bin/env bash
# Build the two Ignition Exchange resource packages.
#
#   ./package.sh     -> dist/launchpad_oee_au.<version>.zip
#                       dist/launchpad_kpi_au.<version>.zip
#
# Layout follows the same Exchange convention as the ACME Alarm Demo package:
#
#   MANIFEST                    name, version, minimum Ignition, modules
#   README.md                   what it is, how to install, custom instructions
#   LICENSE                     MIT
#   Projects/<name>.zip         the project export
#   Tags/                       tag + UDT exports, and the simulator programme
#   Gateway/                    config resources a project import cannot create
#                               for itself - tag provider, database connection,
#                               historian, and (KPI) the simulator device
#
# Gateway/ is an addition to the Exchange convention, not part of it; it is
# described in each README's Custom Instructions, which is where an Exchange
# resource is expected to put anything a plain project import does not cover.
#
# The two packages are independent: either installs on its own, and where they
# overlap (tag provider, Examples database) both ship the same resource, so
# installing the second over the first is a no-op.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIST="$HERE/dist"
VERSION=2.1.8

# The packages are built from the working tree, not from git, so a gitignored file
# on disk ships without ever appearing in `git status`. That is exactly how a stray
# __pycache__ went out inside a script resource in 2.1.0. Fail here rather than
# discover it on someone else's gateway.
python3 "$HERE/tools/check_resources.py" "$HERE/final/OEE" "$HERE/final/KPI"

command -v zip >/dev/null || { echo "package: zip not installed" >&2; exit 2; }

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

# Every released project carries its version in the Title (workspace CLAUDE.md):
# project.json's "title" becomes "<Project Title> <version>" so that landing on a
# gateway's Config -> Projects list shows what is actually running. The working
# copy under final/ keeps a "(dev)" title instead -- this is the one place that
# turns it into a release title, and it only ever touches the packaged copy in
# dist/, never final/ itself. VERSION above is the only place the number lives.
stamp_title() {
  python3 -c '
import json, sys
p, title = sys.argv[1], sys.argv[2]
d = json.load(open(p))
d["title"] = title
json.dump(d, open(p, "w"), indent=2)' "$1" "$2"
}

# Same rule, applied to the Description: Config -> Projects only shows that
# column, not the Title, so the version has to land there too (workspace
# CLAUDE.md, 24/08/2026). Suffix rather than replace -- the existing prose
# stays intact -- and again only ever touches the packaged copy in dist/.
append_desc_suffix() {
  python3 -c '
import json, sys
p, version = sys.argv[1], sys.argv[2]
d = json.load(open(p))
d["description"] = d["description"] + " · v" + version
json.dump(d, open(p, "w"), indent=2)' "$1" "$2"
}

rm -rf "$DIST"
mkdir -p "$DIST"

echo "--> tag exports"
python3 "$HERE/tools/build_tag_exports.py" "$DIST/tags"

for PKG in oee kpi; do
  case "$PKG" in
    oee) PROJ=OEE; SLUG=launchpad_oee_au; TITLE="Launchpad OEE (AU)"; ENDPOINT=lp_init ;;
    kpi) PROJ=KPI; SLUG=launchpad_kpi_au; TITLE="Launchpad KPI (AU)"; ENDPOINT=kpi_init ;;
  esac
  STAGE="$DIST/stage-$PKG"
  mkdir -p "$STAGE/Projects" "$STAGE/Tags" "$STAGE/Gateway"

  echo "--> $TITLE"

  # project export, with the title stamped to this release's version and the
  # installer endpoint closed
  rm -rf "$DIST/proj-$PKG"
  cp -r "$HERE/final/$PROJ" "$DIST/proj-$PKG"
  stamp_title "$DIST/proj-$PKG/project.json" "$TITLE $VERSION"
  append_desc_suffix "$DIST/proj-$PKG/project.json" "$VERSION"
  harden "$DIST/proj-$PKG/com.inductiveautomation.webdev/resources/$ENDPOINT/config.json"
  ( cd "$DIST/proj-$PKG" && zip -qr "$STAGE/Projects/$PROJ.zip" . )
  rm -rf "$DIST/proj-$PKG"

  # gateway resources both packages need
  ITEMS="tag-provider/launchpad database-connection/Examples historian-provider/launchpad"
  # only KPI is driven by the simulator; the OEE demo lines are memory tags driven
  # by their own tag event scripts, so shipping the device with OEE would be noise
  [[ "$PKG" == "kpi" ]] && ITEMS="$ITEMS device/Launchpad"
  for it in $ITEMS; do
    mkdir -p "$STAGE/Gateway/$(dirname "$it")"
    cp -r "$HERE/live-config/$it" "$STAGE/Gateway/$it"
  done

  cp "$HERE/exchange/$PKG/MANIFEST" "$STAGE/MANIFEST"
  cp "$HERE/exchange/$PKG/README.md" "$STAGE/README.md"
  cp "$HERE/exchange/LICENSE" "$STAGE/LICENSE"
  # README screenshots -- the package must be self-contained inside the zip too.
  # Written as a full `if` rather than `[ -d ... ] && cp ...`: under the
  # `set -e` above, the && form exits the whole script for any package that
  # happens to have no docs/ folder.
  if [ -d "$HERE/exchange/$PKG/docs" ]; then
    cp -r "$HERE/exchange/$PKG/docs" "$STAGE/docs"
  fi

  cp -r "$DIST/tags/$PKG/." "$STAGE/Tags/"
  ( cd "$STAGE" && zip -qr "$DIST/$SLUG.$VERSION.zip" . )
  rm -rf "$STAGE"
  echo "    dist/$SLUG.$VERSION.zip"
done

rm -rf "$DIST/tags"
echo
echo "packages built:"
ls -1sh "$DIST"/*.zip
