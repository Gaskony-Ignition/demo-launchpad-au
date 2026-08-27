#!/usr/bin/env bash
# Install the Launchpad OEE + KPI resources onto an Ignition 8.3 gateway.
#
#   tools/install.sh --container your-ignition-container --url http://your-gateway:9088 \
#                    --gateway testbed [--ssh your-ssh-host] [--skip-data]
#
#   --container  docker container name of the gateway
#   --url        base URL used for the HTTP init calls
#   --gateway    stanza name in the toolkit credentials file, used to drive the scans
#   --ssh        ssh alias, if the container is on another host (uses sudo docker there)
#   --skip-data  install resources only; do not seed tables/history/demo tags
#
# Everything is idempotent: re-running is safe and re-applies only what has drifted.
# Ordering matters and is not arbitrary -- see the phase comments.
#
# NOT A PROOF OF THE PACKAGE. This lands the projects by untarring them into
# data/projects, which accepts things the gateway's own Import Project dialog does
# not -- a resource folder holding a file its resource.json does not declare copies
# in happily and is DROPPED by the importer, taking the resource with it. That
# difference shipped a broken release once. To prove a release, install the packaged
# zips the way a user does: tools/install_ui.js.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"
SRC_PROJECTS="$ROOT/final"          # exact project trees, already signature-clean
SRC_CONFIG="$ROOT/live-config"      # gateway config resources

CONTAINER=""; URL=""; GATEWAY=""; SSH_ALIAS=""; SKIP_DATA=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --container) CONTAINER="$2"; shift 2 ;;
    --url)       URL="$2"; shift 2 ;;
    --gateway)   GATEWAY="$2"; shift 2 ;;
    --ssh)       SSH_ALIAS="$2"; shift 2 ;;
    --skip-data) SKIP_DATA=1; shift ;;
    *) echo "install: unknown argument $1" >&2; exit 2 ;;
  esac
done
[[ -n "$CONTAINER" && -n "$URL" && -n "$GATEWAY" ]] || {
  echo "install: --container, --url and --gateway are all required" >&2; exit 2; }

TOOLKIT="${IGNITION_TOOLKIT:-/Home-Claude/ignition-claude-toolkit}/plugins/ignition/skills"
[ -d "$TOOLKIT" ] || TOOLKIT=/claude/ignition-claude-toolkit/plugins/ignition/skills
DATA=/usr/local/bin/ignition/data
RES=$DATA/config/resources

if [[ -n "$SSH_ALIAS" ]]; then
  EXEC()      { ssh "$SSH_ALIAS" "sudo docker exec -i $CONTAINER $*"; }
  EXEC_ROOT() { ssh "$SSH_ALIAS" "sudo docker exec -u root -i $CONTAINER $*"; }
  UNTAR()     { ssh "$SSH_ALIAS" "sudo docker exec -i $CONTAINER tar -x -C $1"; }
else
  EXEC()      { docker exec -i "$CONTAINER" "$@"; }
  EXEC_ROOT() { docker exec -u root -i "$CONTAINER" "$@"; }
  UNTAR()     { docker exec -i "$CONTAINER" tar -x -C "$1"; }
fi

say()  { printf '\n=== %s\n' "$*"; }
step() { printf '  - %s\n' "$*"; }

api() {  # api <project> <endpoint> <action> -- returns the raw JSON body
  # The first call to a WebDev resource after a scan can come back 200 with an EMPTY
  # body while the module is still compiling it -- the work runs, but there is nothing
  # to parse. Retry until we get JSON rather than fail the install on a warm-up.
  local body
  for attempt in 1 2 3 4; do
    body="$(curl -s -m 300 "$URL/system/webdev/$1/$2?action=$3" || true)"
    [[ -n "$body" && "${body:0:1}" == "{" ]] && { printf '%s' "$body"; return 0; }
    sleep 5
  done
  printf '%s' "$body"
}

# require_ok <label> <json-body>
# The body is passed as an ARGUMENT, not piped: `python3 - <<PY` takes its program
# from stdin, so a heredoc there leaves sys.stdin.read() empty and every response
# looks like a failure no matter what the gateway actually returned.
require_ok() {
  python3 -c '
import json, sys
label, body = sys.argv[1], sys.argv[2]
try:
    d = json.loads(body)
except ValueError:
    print("    %s: FAILED - not JSON: %r" % (label, body[:200])); sys.exit(1)
if not d.get("ok"):
    print("    %s: FAILED - %s" % (label, str(d.get("error", d))[:500])); sys.exit(1)
extra = {k: v for k, v in d.items() if k not in ("ok", "action")}
print("    %s: ok %s" % (label, json.dumps(extra)[:220] if extra else ""))
' "$1" "$2"
}

wait_http() {  # the gateway 402s for everything once an unlicensed trial lapses,
               # while /StatusPing still answers RUNNING -- so probe a real endpoint
  local tries=${2:-60}
  for ((i=0; i<tries; i++)); do
    code=$(curl -s -m 8 -o /dev/null -w '%{http_code}' "$1" || true)
    [[ "$code" == "200" ]] && return 0
    [[ "$code" == "402" ]] && { step "trial expired - resetting"; node "$ROOT/tools/reset_trial.js" --gateway "$GATEWAY" >/dev/null 2>&1 || true; }
    sleep 5
  done
  echo "    timed out waiting for $1 (last HTTP $code)" >&2; return 1
}

config_scan()  { node "$TOOLKIT/config-scan/tool/config-scan.js" --gateway "$GATEWAY" >/dev/null && step "config scan done"; }
project_scan() { node "$TOOLKIT/scan/tool/scan.js"               --gateway "$GATEWAY" >/dev/null && step "project scan done"; }

# A stale lastModificationSignature makes the scan skip the resource in silence -- the
# single most common reason a file deploy "does nothing". Strip it from every copy we
# are about to push.
clean_signatures() {
  python3 - "$1" <<'PY'
import json, os, sys, datetime
root = sys.argv[1]
now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
n = 0
for dirpath, _, files in os.walk(root):
    for f in files:
        if f not in ('resource.json', 'unary-resource.json'):
            continue
        p = os.path.join(dirpath, f)
        d = json.load(open(p))
        a = d.get('attributes', d)
        if 'lastModificationSignature' in a:
            a.pop('lastModificationSignature'); n += 1
        a['lastModification'] = {'actor': 'external', 'timestamp': now}
        json.dump(d, open(p, 'w'), indent=2)
print('    stripped %d stale signatures' % n)
PY
}

STAGE="$(mktemp -d)"; trap 'rm -rf "$STAGE"' EXIT

say "Target: $CONTAINER via $URL (creds stanza: $GATEWAY)"

# A gateway nobody has logged into yet puts an "Enable Quick Start" modal over the
# whole web UI. It swallows every click, so the scans time out hunting for "Platform"
# and nothing in the logs explains it. Clear that before anything else.
node "$ROOT/tools/preflight.js" --gateway "$GATEWAY" | sed 's/^/  - /'
step "gateway version: $(EXEC cat $DATA/../lib/install-info.txt 2>/dev/null | grep -i '^version' || echo unknown)"

# ---------------------------------------------------------------- phase 1
# Infrastructure first. The tag provider has to exist before any tag definition
# lands under it, and the historian needs its database connection to already be
# there or it comes up faulted.
say "Phase 1/6  infrastructure (database, tag provider, historian, simulator)"
mkdir -p "$STAGE/p1/core/ignition" "$STAGE/p1/core/com.inductiveautomation.historian" "$STAGE/p1/core/com.inductiveautomation.opcua"
cp -r "$SRC_CONFIG/database-connection" "$STAGE/p1/core/ignition/"
cp -r "$SRC_CONFIG/tag-provider"        "$STAGE/p1/core/ignition/"
cp -r "$SRC_CONFIG/historian-provider"  "$STAGE/p1/core/com.inductiveautomation.historian/"
cp -r "$SRC_CONFIG/device"              "$STAGE/p1/core/com.inductiveautomation.opcua/"
clean_signatures "$STAGE/p1"
tar -c -C "$STAGE/p1" core | UNTAR "$RES"
EXEC_ROOT chown -R ignition:ignition "$RES"
config_scan

# ---------------------------------------------------------------- phase 2
# Projects before tags: the UDT event scripts call launchpad.oee.*, which
# only resolves once the gateway scripting project is set. Land that first and the
# tags come alive against working scripts instead of logging errors for a minute.
say "Phase 2/6  projects + gateway scripting project"
mkdir -p "$STAGE/p2"
cp -r "$SRC_PROJECTS/OEE" "$SRC_PROJECTS/KPI" "$STAGE/p2/"
clean_signatures "$STAGE/p2"
tar -c -C "$STAGE/p2" OEE KPI | UNTAR "$DATA/projects"
EXEC_ROOT chown -R ignition:ignition "$DATA/projects/OEE" "$DATA/projects/KPI"

EXEC cat "$RES/core/ignition/system-properties/config.json" > "$STAGE/sysprops.json"
python3 - "$STAGE/sysprops.json" <<'PY'
import json, sys
p = sys.argv[1]
d = json.load(open(p))
if d.get('gatewayScriptingProject') != 'OEE':
    d['gatewayScriptingProject'] = 'OEE'
    json.dump(d, open(p, 'w'), indent=2)
    print('    gatewayScriptingProject -> OEE')
else:
    print('    gatewayScriptingProject already OEE')
PY
python3 - "$STAGE/sysprops-resource.json" <<'PY'
import json, sys, datetime
json.dump({"scope": "A", "version": 1, "restricted": False, "overridable": True,
           "files": ["config.json"],
           "attributes": {"lastModification": {"actor": "external",
             "timestamp": datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}}},
          open(sys.argv[1], 'w'), indent=2)
PY
tar -c -C "$STAGE" --transform 's|sysprops.json|config.json|' \
    --transform 's|sysprops-resource.json|resource.json|' sysprops.json sysprops-resource.json \
  | UNTAR "$RES/core/ignition/system-properties"
EXEC_ROOT chown -R ignition:ignition "$RES/core/ignition/system-properties"
config_scan
project_scan

# ---------------------------------------------------------------- phase 3
# Tag types before instances: an instance whose typeId does not resolve loads as a
# broken tag and does not repair itself when the type turns up later.
say "Phase 3/6  tag types and tag definitions"
mkdir -p "$STAGE/p3/core/ignition"
cp -r "$SRC_CONFIG/tag-type-definition" "$STAGE/p3/core/ignition/"
clean_signatures "$STAGE/p3"
tar -c -C "$STAGE/p3" core | UNTAR "$RES"
EXEC_ROOT chown -R ignition:ignition "$RES/core/ignition/tag-type-definition"
config_scan

mkdir -p "$STAGE/p3b/core/ignition"
cp -r "$SRC_CONFIG/tag-definition" "$STAGE/p3b/core/ignition/"
clean_signatures "$STAGE/p3b"
tar -c -C "$STAGE/p3b" core | UNTAR "$RES"
EXEC_ROOT chown -R ignition:ignition "$RES/core/ignition/tag-definition"
config_scan

# ---------------------------------------------------------------- phase 4
say "Phase 4/6  waiting for the installer endpoints"
wait_http "$URL/system/webdev/OEE/lp_init?action=status"
wait_http "$URL/system/webdev/KPI/kpi_init?action=status"
step "both endpoints responding"

if [[ "$SKIP_DATA" == "1" ]]; then
  say "Phase 5/6  skipped (--skip-data)"
else
  say "Phase 5/6  seeding database, schedule, history and demo tags"
  require_ok "OEE tables" "$(api OEE lp_init initTables)"
  require_ok "KPI dashboard tables" "$(api KPI kpi_init initDashboard)"
  require_ok "shift roster" "$(api OEE lp_init setupShifts)"
  require_ok "OEE history" "$(api OEE lp_init seedHistory)"
  require_ok "counters zeroed" "$(api OEE lp_init resetDemoTags)"
  # the schedule expressions need a tick to publish CurrentShiftStartTime before
  # initDemoTags reads it; initialising too early dates the shift wrongly
  step "letting the shift schedule settle"; sleep 45
  require_ok "demo tags" "$(api OEE lp_init initDemoTags)"
  require_ok "KPI tables" "$(api KPI kpi_init status)"
  step "backfilling 48h of KPI history (this takes a couple of minutes)"
  require_ok "KPI history backfill" "$(api KPI kpi_init backfill)"
  require_ok "integer-tag repair" "$(api KPI kpi_init repairBackfill)"
fi

say "Verify"
api OEE lp_init diag | python3 -c "
import json, sys
d = json.load(sys.stdin)['diag']
l = d['line1']
print('    shift            : %s starting %s' % (l['Schedule/CurrentShift'], l['Schedule/CurrentShiftStartTime']))
print('    named-query rows : %s (HourlyStats over 24h)' % d['hourlyStatsRows'])
print('    KPI history      : %s' % ', '.join('%s=%s' % (r[0], r[1]) for r in d['hist']))
"
api OEE lp_init intervals | python3 -c "
import json, sys
d = json.load(sys.stdin)['intervals']
bad = [(ln, iv, k) for ln in d for iv in d[ln] for k in d[ln][iv]
       if isinstance(d[ln][iv][k], float) and d[ln][iv][k] > 1.0]
print('    lines reporting  : %d' % len(d))
print('    components >100%% : %d%s' % (len(bad), '  ' + str(bad[:3]) if bad else ''))
"
# ---------------------------------------------------------------- phase 6
# The installer endpoints have to be reachable unauthenticated to be driven from
# here, but they can truncate the OEE tables -- so close them once the seeding is
# done. Re-running the installer re-opens them in phase 2, so this is not one-way.
say "Phase 6/6  closing the installer endpoints"
mkdir -p "$STAGE/harden"
for spec in "OEE:lp_init" "KPI:kpi_init"; do
  proj="${spec%%:*}"; name="${spec##*:}"
  dir="$STAGE/harden/$proj/com.inductiveautomation.webdev/resources/$name"
  mkdir -p "$dir"
  cp "$SRC_PROJECTS/$proj/com.inductiveautomation.webdev/resources/$name/"* "$dir/"
  python3 - "$dir/config.json" <<'PY'
import json, sys
p = sys.argv[1]
d = json.load(open(p))
d['doGet']['require-auth'] = True
json.dump(d, open(p, 'w'), indent=2)
PY
  step "$proj/$name now requires authentication"
done
clean_signatures "$STAGE/harden" >/dev/null
tar -c -C "$STAGE/harden" OEE KPI | UNTAR "$DATA/projects"
EXEC_ROOT chown -R ignition:ignition "$DATA/projects/OEE" "$DATA/projects/KPI"
project_scan

say "Done. Open $URL/data/perspective/client/OEE/ and $URL/data/perspective/client/KPI/"
