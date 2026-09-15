# What the Setup button does

The Launchpad OEE and KPI examples install as project zips and then build the
rest of the gateway themselves. This document lists everything that happens
when you press **Set up**, so the decision to press it can be made on evidence
rather than on trust.

Every claim here names the function that makes it true. The code is
`launchpad/setup/code.py` inside each project — the file is byte-identical in
OEE and KPI, and decides which project it is running in from
`hasattr(launchpad, "oee")`.

## In one line

It creates a SQLite database connection, a tag provider, a simulator device, a
tag historian (KPI only), the tags, the tables and the seed history — by
writing config-resource files into the gateway's own data directory and asking
the gateway to rescan them. It creates nothing outside those, it sends nothing
anywhere, and it edits exactly one resource it did not make.

## Where it is called from

| Surface | Entry point | Who can reach it |
| ------- | ----------- | ---------------- |
| Setup screen | `launchpad.setup.run()`, `.check()` | any Perspective session that can open the project |
| WebDev endpoint | `/system/webdev/<project>/lp_init?action=setup` | authenticated callers in a released zip |

`package.sh` sets `"require-auth": true` on the endpoint in the zip it builds,
so the released project does not expose it anonymously. The working tree under
`final/` leaves it open for development.

`check()` writes nothing at all. `run()` creates only what is absent unless
`force=True` is passed.

## How it applies changes

Not through `system.config`. It writes the resource files —
`data/config/resources/<module>/<type>/<name>/config.json` plus a matching
`resource.json` — and then asks the configuration manager to rescan
(`_configResource`, `_configScan`):

```text
IgnitionGateway.get().getConfigurationManager().requestScan()
```

That request is asynchronous, so the code waits for the scan reading to move
before it acts on anything the scan was meant to register. It is a
configuration rescan, not a gateway restart, and nothing here restarts the
gateway.

## What it creates

### 1. Database connection — `OEE` or `KPI`

`ensureDatabase`. Each project gets its own SQLite file, named after the
project:

```text
jdbc:sqlite:${data}/OEE.db?journal_mode=WAL&busy_timeout=30000
```

`${data}` is expanded by Ignition to the gateway's data directory. Driver
`SQLite`, translator `SQLITE`, username empty, no password — which is the whole
reason this can be automated. Pool and timeout values are Ignition's defaults.

`journal_mode=WAL` and `busy_timeout` are load-bearing rather than tuning: the
simulator writes continuously while Perspective sessions read, and SQLite's
default rollback journal blocks readers for the length of every write.

The SQLite file itself is created by the JDBC driver on first connect.

### 2. Tag provider — `launchpad`

`ensureTagProvider`. A standard provider, value persistence Database, default
datasource set to this project's own connection. No read/write/edit permissions
set.

### 3. Tag historian — `launchpad`, **KPI only**

`ensureHistorian`. A SQL historian pointed at the `KPI` database, monthly
partitions, pruning disabled.

OEE never creates or touches it. There is one shared historian provider on a
gateway and it can name only one database; every historised tag is KPI's and
OEE has none, so OEE creating it would either point it at a database with no
history or repoint KPI's away from its own.

### 4. Simulator device — `Launchpad`

`ensureDevice`. A Programmable Simulator device on the OPC-UA module, 1000 ms
interval, repeating, and its programme as `instructions.csv` alongside the
config — about 4 KB of `cosine(...)` and `random(...)` expressions bound to the
demo's own tag paths. Without the programme every tag reads stale and the demo
looks like a broken historian.

### 5. Tags

`ensureTags`. Nine resource files under
`core/ignition/tag-definition/launchpad/...` and
`tag-type-definition/launchpad/...`, then a config scan, then a wait until the
tags are actually browsable.

Deliberately not `system.tag.configure`: configuring a subtree at the provider
root takes the provider's other subtrees with it, so installing one project's
tags removed the other's. Writing the resource files composes — each project
installs only its own paths.

Tags are **not** reinstalled by a plain `force`. Installing over a live
subscription leaves the previous definition's tag event script subscribed as
well, so the simulator's counter runs twice per tick. Reinstalling has to be
asked for by name (`tags=1`), after which the gateway wants a restart.

### 6. Gateway scripting project — the one existing resource it edits

`ensureScriptingProject`. Sets `gatewayScriptingProject` to `OEE` in
`core/ignition/system-properties/config.json`, because the OEE tag event
scripts resolve `launchpad.oee.*` through that setting.

It patches that one key and rewrites the sibling `resource.json` to restamp
`lastModification` and drop the stale signature — nothing else in the file is
touched. Two refusals are built in:

- it will not set it when the OEE project is not installed;
- it will not take the setting off another project. On a gateway already using
  it, the step reports what it found and leaves it alone.

### 7. Tables and seed history

`_initTables` creates the project's tables in its own SQLite file.
`_freshHistory` seeds history and then re-seeds it whenever what is there has
gone stale, because seeded history is a snapshot and a demo gateway that sat
idle for a few days draws empty charts for "today". It verifies afterwards that
rows exist inside the recent window rather than assuming the seed worked.

## What it will not do

- **It will not overwrite a database connection it does not recognise.** If a
  connection already exists under this project's name and is not SQLite,
  `ensureDatabase` raises and names it, and the whole run stops there —
  everything below names that connection, so carrying on would half-build a
  schema in somebody else's database.
- **It will not rewrite a connection it does recognise.** Upgrading an older
  install patches `connectURL` and nothing else, so pool settings anyone has
  tuned survive.
- **It will not claim the gateway scripting project from another project.**
- **It will not scan when nothing was written.** A config scan reloads tag
  definitions, which restamps shift start times and zeroes run counters — so
  scanning on every press threw away a shift in progress. The scan now runs
  only when a step actually created something.
- **It will not reach the network.** There is no `system.net.*` call, no HTTP
  client and no outbound request in `launchpad.setup` or its payload.
- **It will not restart the gateway.**

## What it reads

Existing `config.json` files under `data/config/resources`, to tell "absent"
from "ours" from "someone else's"; the presence of `data/projects/OEE`; tag
values and browse results; and its own tables. `check()` does all of this and
writes nothing.

## The payload is inspectable

The resources it writes are carried in `launchpad/payload/code.py` as
zlib-compressed base64, generated by `tools/gen_setup_payload.py`. Nothing in
them is obscured — decode any of them:

```python
import re, base64, zlib, json
src = open('final/OEE/ignition/script-python/launchpad/payload/code.py').read()
def blob(name):
    body = re.search(r'^%s = \(\n(.*?)\n\)' % name, src, re.S | re.M).group(1)
    return zlib.decompress(base64.b64decode("".join(re.findall(r'"([^"]*)"', body))))
print(json.dumps(json.loads(blob("_DEVICE")), indent=1))   # also _PROVIDER, _HISTORIAN, _TAGS
print(blob("_INSTRUCTIONS").decode())                      # the simulator programme
```

## Removing it

1. Delete the config resources: database connection `OEE` / `KPI`, tag provider
   `launchpad`, historian provider `launchpad`, device `Launchpad`, and the tag
   definitions under `tag-definition/launchpad` and
   `tag-type-definition/launchpad`.
2. Unset `gatewayScriptingProject` if the OEE demo had claimed it.
3. Delete `${data}/OEE.db` and `${data}/KPI.db`.
4. Delete the projects.

The SQLite files hold the tables and the history, so deleting them removes the
entire data footprint in one step.

## Checking this document against the code

```bash
grep -n "_configResource\|_configScan\|_write(" \
    final/OEE/ignition/script-python/launchpad/setup/code.py
```

Every gateway change this project makes goes through those three. The `run()`
function near the bottom of the file lists the steps in the order they execute.
