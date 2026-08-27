#!/usr/bin/env bash
# Push final/<PROJECT> into a local Docker gateway's project folder.
#
#   tools/deploy_local.sh OEE [container]
#
# Two things this has to do that a plain `docker cp` does not:
#
#   * Strip lastModificationSignature from every resource.json. The gateway compares
#     the signature before it reads the file, so a resource copied in with its old
#     signature is silently skipped and the deploy looks like it did nothing.
#   * Touch project.json afterwards, which is what makes the gateway notice.
set -euo pipefail

PROJECT="${1:?usage: deploy_local.sh <PROJECT> [container]}"
CONTAINER="${2:-ignition-module-testing}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/final/$PROJECT"
[ -d "$SRC" ] || { echo "no such project: $SRC" >&2; exit 1; }

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
cp -a "$SRC/." "$STAGE/"

python3 - "$STAGE" <<'PY'
import datetime, json, os, sys
now = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
touched = 0
for dirpath, _, files in os.walk(sys.argv[1]):
    if 'resource.json' not in files:
        continue
    p = os.path.join(dirpath, 'resource.json')
    d = json.load(open(p))
    for holder in (d, d.get('attributes') or {}):
        holder.pop('lastModificationSignature', None)
        lm = holder.get('lastModification')
        if lm:
            # the gateway skips a resource whose recorded timestamp has not moved,
            # so a deploy that leaves this alone lands the file and changes nothing
            lm['timestamp'] = now
            touched += 1
    json.dump(d, open(p, 'w'), indent=2)
print('  resources restamped: %d (%s)' % (touched, now))
PY

# a gateway that has never held this project has no folder to untar into, and the
# gateway process must own it or it cannot rewrite the resources later
docker exec "$CONTAINER" sh -c "mkdir -p /usr/local/bin/ignition/data/projects/$PROJECT && \
  chown -R ignition:ignition /usr/local/bin/ignition/data/projects/$PROJECT"
tar -cz -C "$STAGE" . | docker exec -i "$CONTAINER" \
  tar -xz -C "/usr/local/bin/ignition/data/projects/$PROJECT"
docker exec "$CONTAINER" touch "/usr/local/bin/ignition/data/projects/$PROJECT/project.json"
echo "  deployed $PROJECT -> $CONTAINER"

# Landing the files changes nothing on its own -- the gateway reads them on a project
# scan, and there is no scriptable hook to ask for one from inside a project whose
# scripts are themselves the stale copy. The toolkit drives the web UI's button.
SCAN="${IGNITION_TOOLKIT:-/Home-Claude/ignition-claude-toolkit}/plugins/ignition/skills/scan/tool/scan.js"
[ -f "$SCAN" ] || SCAN=/claude/ignition-claude-toolkit/plugins/ignition/skills/scan/tool/scan.js
GATEWAY="${SCAN_GATEWAY:-module-testing}"
if [ -f "$SCAN" ]; then
  node "$SCAN" --gateway "$GATEWAY"
else
  echo "  NOTE: no scan tool found -- run Config > Projects > Scan File System by hand" >&2
fi
