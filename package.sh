#!/usr/bin/env bash
# Build the two importable Ignition project zips.
#
#   ./package.sh                  -> dist/OEE.zip       dist/OEE_Edge.zip
#                                    dist/KPI.zip       dist/KPI_Edge.zip
#   ./package.sh --release [VER]  -> dist/OEE-<VER>.zip dist/OEE_Edge-<VER>.zip
#                                    dist/KPI-<VER>.zip dist/KPI_Edge-<VER>.zip
#
# FOUR zips, every time: each project needs both a standard-gateway build and
# an Edge build, and a flag that could skip one is a flag that eventually will.
# These are plain project exports -- Platform > Projects > Import Project takes
# them directly, and everything else a gateway needs is built by the Setup
# button on the project's own Settings page.
#
# The zip is built from INSIDE the project directory (`cd final/OEE && zip -r`),
# which is what the importer expects: a zip whose members start with project.json,
# not with a wrapping folder.
#
# VER defaults to the tag HEAD is exactly on, so cutting a release is
#   git tag v3.0.0 && ./package.sh --release
set -euo pipefail
# Repo gate (REPO-STANDARD.md). Blocking; bypass deliberately with --skip-readme-check.
if [[ " $* " != *" --skip-readme-check "* ]]; then
    _repo=$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)
    _gate=""; _d="$_repo"
    while [ "$_d" != / ]; do
        [ -x "$_d/modules/readme-gate.sh" ] && { _gate="$_d/modules/readme-gate.sh"; break; }
        _d=$(dirname "$_d")
    done
    if [ -n "$_gate" ]; then
        "$_gate" "$_repo" || { echo "repo gate failed: fix the README/tree or pass --skip-readme-check" >&2; exit 1; }
    else
        echo "readme-gate.sh not found above $_repo; gate skipped" >&2
    fi
fi
# Accessibility gate (WCAG 2.1 AA). Blocking; bypass deliberately with
# --skip-a11y-check. Checks the gateway a11y.json points at, which has to
# already be running the build under test - deploy before packaging, not
# the other way round.
if [[ " $* " != *" --skip-a11y-check "* ]]; then
    _repo=$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)
    _a11ygate=""; _d="$_repo"
    while [ "$_d" != / ]; do
        [ -x "$_d/modules/a11y-gate.sh" ] && { _a11ygate="$_d/modules/a11y-gate.sh"; break; }
        _d=$(dirname "$_d")
    done
    if [ -n "$_a11ygate" ]; then
        "$_a11ygate" "$_repo" || { echo "a11y gate failed: fix the finding(s) above or record a reasoned exception in a11y.json, or pass --skip-a11y-check" >&2; exit 1; }
    else
        echo "a11y-gate.sh not found above $_repo; gate skipped" >&2
    fi
fi
# Strip --skip-readme-check/--skip-a11y-check (already consumed by the gates
# above) so this script's own argument parsing -- which rejects unrecognised
# args -- never sees it.
_pkgargs=(); for _a in "$@"; do
    [[ "$_a" == "--skip-readme-check" || "$_a" == "--skip-a11y-check" ]] || _pkgargs+=("$_a")
done
set -- "${_pkgargs[@]}"

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIST="$HERE/dist"

# The zips are built from the working tree, not from git, so a gitignored file on
# disk ships without ever appearing in `git status`. That is exactly how a stray
# __pycache__ went out inside a script resource in 2.1.0. Fail here rather than
# discover it on someone else's gateway.
python3 "$HERE/tools/check_resources.py" "$HERE/final/OEE" "$HERE/final/KPI"

# ...and that every OEE record function still writes as many values as the
# column list it writes them into. A drifted pair does not fail: it puts a
# reject count in the idle-seconds column, which is a plausible number on a
# chart and nothing anywhere calls it wrong.
python3 "$HERE/tools/check_columns.py" "$HERE/final/OEE"

# ...and that the KPI file store's seed still matches the schema that defines
# it. Two copies of a seed is one copy that goes stale, and the way it shows up
# is a widget palette missing whatever was added to the other one.
python3 "$HERE/tools/kpi_seed.py"

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
# always requires auth.
harden() {
  python3 -c '
import json, sys
p = sys.argv[1]
d = json.load(open(p))
d["doGet"]["require-auth"] = True
json.dump(d, open(p, "w"), indent=2)' "$1"
}

# Every released project carries its version in the Title AND at the end of the
# Description: Config > Projects shows only the Description column, while the
# Title shows in the Edit drawer and on the Perspective launch surfaces, so both
# are stamped. The working copy under final/ keeps a "(dev)" title, and this
# only ever touches the staged copy in dist/.
stamp_version() {
  python3 -c '
import json, re, sys
p, version = sys.argv[1], sys.argv[2]
d = json.load(open(p))
d["title"] = re.sub(r"\s*\(dev\)$", "", d["title"]) + " " + version
d["description"] = d["description"] + " · v" + version
json.dump(d, open(p, "w"), indent=2)' "$1" "$2"
}


# Turn a staged project into its Edge build, in place.
#
# ONE thing is substituted: the tag provider name. Ignition Edge permits
# exactly one realtime provider, the platform makes it and calls it `edge`, and
# a second is refused at startup - so the Edge build adopts the name that is
# already there rather than asking a customer to rename theirs. It has to
# happen at BUILD time because a tag path is a literal in over a hundred
# bindings and a provider-less path does not resolve.
#
# Everything else that differs between the editions is decided at RUNTIME by
# launchpad.edition asking the gateway what it can do: the records go to SQL or
# to the file store, the historian is the demo's or the platform's, the
# database step runs or reports that there is nothing to run.
#
# FOUR forms carry the provider, and the ones that are missed do not fail -
# they come back EMPTY:
#
#   [Launchpad]        a tag path                    (bindings and tag writes)
#   prov:launchpad:    an alarm source filter
#   PROVIDER = "..."   the constant the setup steps derive from
#   "provider": "..."  an alarm table's filter CONDITION
#
# That last one was missed until 10/09/2026 and is the reason the Edge build
# showed no alarms at all on its Alarming page. It is spelled differently from
# the other three - a bare provider NAME, not a path and not a `prov:` source
# filter - so it survived a substitution written for paths, and the failure was
# an empty table rather than an error. It appears exactly once, on the KPI
# alarm status table, and the source spells it `launchpad` to match the
# provider the setup step actually creates: it shipped as `Launchpad`, which
# tag PATHS resolve case-insensitively but which left the one spelling in the
# project that nothing checked.
#
# What must NOT be substituted, and is why this is not a blanket sed: the
# SCRIPT PACKAGE `launchpad.oee` and its siblings, the session property tree
# `session.custom.launchpad.oee.*` which is named after the project rather than
# the provider, the device named `Launchpad`, and HISTORIAN - on Edge the
# historian is the platform's own and launchpad.edition asks it for the name.
edgeify() {
  local stage="$1"
  local provider="edge"

  find "$stage" -type f \( -name '*.json' -o -name '*.py' -o -name '*.sql' \) -print0 \
    | xargs -0 sed -i \
        -e "s/\[Launchpad\]/[${provider}]/g" \
        -e "s/prov:launchpad:/prov:${provider}:/g" \
        -e "s/\"provider\": \"launchpad\"/\"provider\": \"${provider}\"/g"
  sed -i "s/^PROVIDER = \"launchpad\"/PROVIDER = \"${provider}\"/" \
    "$stage/ignition/script-python/launchpad/setup/code.py"

  # Prove it. A silent no-op here ships a zip that looks right and reads no
  # tags - or worse, reads tags and shows an empty chart.
  local left
  for form in '\[Launchpad\]' 'prov:launchpad:' '"provider": "launchpad"'; do
    left="$(grep -rl "$form" "$stage" || true)"
    if [[ -n "$left" ]]; then
      echo "package: these still carry $form after the Edge substitution:" >&2
      printf '%s\n' "$left" | sed "s|$stage|  project|" >&2
      exit 1
    fi
  done
  grep -q "^PROVIDER = \"${provider}\"" \
    "$stage/ignition/script-python/launchpad/setup/code.py" || {
    echo "package: the Edge build did not rewrite PROVIDER" >&2; exit 1; }
  grep -rq 'launchpad\.store' "$stage" || {
    echo "package: the Edge substitution ate the launchpad script package" >&2
    exit 1; }
  # The session property tree is named after the project, not the provider, and
  # every screen's date range and selected line hang off it.
  grep -rq 'session\.custom\.launchpad\.' "$stage" || {
    echo "package: the Edge substitution ate the session property tree" >&2
    exit 1; }
}

# The project TITLE says which build it is, so a gateway running the wrong one
# says so on its own launch page rather than in a support call.
mark_edge() {
  python3 -c '
import json, sys
p = sys.argv[1]
d = json.load(open(p))
d["title"] = d["title"].replace(" (dev)", "") + " (Edge)"
d["description"] = d["description"] + " Built for Ignition Edge."
json.dump(d, open(p, "w"), indent=2)' "$1"
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

  # ...and the same project again, for Edge.
  STAGE="$DIST/stage-$PROJ-edge"
  cp -r "$HERE/final/$PROJ" "$STAGE"
  harden "$STAGE/com.inductiveautomation.webdev/resources/$ENDPOINT/config.json"
  edgeify "$STAGE"
  mark_edge "$STAGE/project.json"
  if [[ -n "$VERSION" ]]; then
    stamp_version "$STAGE/project.json" "$VERSION"
    rm -rf "$STAGE/ignition/global-props"
  fi
  ZIP="$DIST/${PROJ}_Edge${VERSION:+-$VERSION}.zip"
  ( cd "$STAGE" && zip -qr "$ZIP" . )
  rm -rf "$STAGE"
  echo "  $(basename "$ZIP")"
done

echo
echo "project zips built:"
ls -1sh "$DIST"/*.zip
