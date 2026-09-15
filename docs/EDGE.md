# Running these projects on Ignition Edge

There are **four release zips** and they are not interchangeable.

| Gateway | OEE | KPI |
| ------- | --- | --- |
| Ignition (standard), Maker | `OEE-<version>.zip` | `KPI-<version>.zip` |
| Ignition Edge | `OEE_Edge-<version>.zip` | `KPI_Edge-<version>.zip` |

Everything below was measured on real gateways of both editions, 8.3.8.

## What Edge is, from these projects' point of view

An Edge gateway loads a strict subset of the modules a standard one does:
Perspective, OPC-UA and its drivers, the Historian, Alarm Notification, WebDev,
Vision, Symbol Factory and EAM — and **not** SQL Bridge, any JDBC driver module,
or the SQL historian. There is no database connectivity of any kind.

Two consequences run through everything here:

* `system.db.*` has nothing to run against.
* **A named-query binding cannot run at all.** Not slowly — at all. That is why
  the view bindings changed in the source rather than only in the Edge build.

Three more limits matter:

* **One realtime tag provider**, made by the platform and called `edge`. A
  second is refused at startup.
* **The Visualization Module ships set to VISION**, and until it is PERSPECTIVE
  no Perspective session opens at all. The browser gets **"Sessions Exceeded"**,
  which reads as a licensing problem and is not one.
* **A low cap on concurrent Perspective sessions**, which matters when you are
  verifying pages headlessly rather than looking at them.

## How each project answers that

Everything except the tag provider name is a **runtime** decision, made by
`launchpad.edition` asking the gateway what it can do:

| Question | How it is asked |
| -------- | --------------- |
| Is this Edge? | `('ignition', 'edge-sync-settings')` is registered — the one resource type only Edge has. It is NOT `edge-system-properties`; a standard gateway registers that too. |
| Can it hold a database? | `('ignition', 'database-connection')` is registered. A question about the platform, not about whether a connection was configured. |
| Which historian records? | The demo's own where it makes one; the name out of Edge's own settings resource where the platform owns it. |

The **tag provider name** is the one thing substituted at build time, by
`package.sh`. A tag path is a literal in over a hundred bindings and a
provider-less path does not resolve, so the Edge build is the same project with
`[Launchpad]` → `[edge]`, `prov:launchpad:` → `prov:edge:` and the alarm table's
`"provider": "launchpad"` filter condition → `"edge"`, and the build refuses to
produce a zip in which any of the three survives.

That third form was missed in 3.3.0 and cost the Edge build its whole Alarming
page: the table filtered on a tag provider Edge does not have, so it showed
nothing at all. It is worth knowing why it hid — it is a bare provider NAME
rather than a path or a `prov:` source filter, so a substitution written for
paths walked straight past it, and the result was an empty table rather than an
error. The build now refuses on all three spellings.

The tag payload is the exception to the exception: it is a compressed blob, so a
build-time substitution cannot reach inside it. Its resource paths and the tag
paths within them are rewritten for the gateway's own provider **at install
time**, by `launchpad.setup.payloadFiles`.

### OEE — the records move, the screens do not

OEE's four `ex_launchpad_oee_*` tables are the demo: every screen reads them and
none of it is tag history. `launchpad.store` puts one contract in front of both
implementations — the caller names the table, how to find the row, and the
columns it is writing — and generates the SQL from that column list on a gateway
with a database, or writes the same names into day-partitioned JSON under
`data/launchpad-oee/` on one without.

Partitioned by day because the writer is a gateway timer that touches only the
current hour and shift. A single document holding thirty days of seven lines
would be five thousand rows rewritten every tick; a day file is a few hundred
and is the only one a live tick opens.

The thirty-day seed is all-or-nothing on both: a transaction on SQL, and a
staging directory swapped in at the end on files. That matters because this is a
button the install instructions tell every user to press, and a failure that
destroys history and then invites a retry is the worst shape available.

### KPI — the dashboards move, and the history is seeded properly

KPI's dashboard builder is a relational application: six tables, four of them
joined to answer one question, and rows created with auto-increment ids. The
same six tables live under `data/launchpad-kpi/`, one JSON file each, and
`launchpad.store` answers the same eleven questions — including the join that
gives a widget its parameters from its TYPE and its values from the dashboard's
own overrides.

The seed rows are **generated from the CREATE TABLE script** by
`tools/kpi_seed.py`, which `package.sh` runs as a check. Two copies of a seed is
one copy that goes stale, and the way that shows up is a widget palette missing
whatever was added to the other one.

**KPI's tag history is seeded on Edge too.** This is the part that looked
impossible at first and is not:

* `system.tag.storeTagHistory` is a legacy bridge. Against Edge's Internal
  Historian it accepts the call, logs nothing, moves no store-and-forward
  metric, and stores nothing at all.
* `system.historian.storeDataPoints(paths=, values=, qualities=, timestamps=)`
  is the 8.3 API and it works — measured at 480 backdated points across 20 days
  on a real Edge gateway, and read back through **both** APIs, so the existing
  `system.tag.queryTagHistory` bindings work over seeded data unchanged.

Edge caps its historian at roughly 35 days and ten million points; the two days
the backfill seeds sits well inside that.

## Installing on Edge

**There is no project import UI on Edge.** Unzip the Edge build over Edge's own
project folder, chown it to the gateway user, and run a project scan:

```
unzip -q OEE_Edge-<version>.zip -d ./edge-project
tar -C ./edge-project -cf - . | docker exec -i -u root <container> \
  tar -C /usr/local/bin/ignition/data/projects/Edge -xf -
docker exec -u root <container> \
  chown -R ignition:ignition /usr/local/bin/ignition/data/projects/Edge
```

Then run the setup **through the endpoint**, not from the Settings screen:

```
curl -u <user>:<pass> 'http://<edge>/system/webdev/Edge/lp_init?action=setup'
```

That is not a preference. Edge ships with its Visualization Module set to
VISION, so until setup has changed it there is no Perspective session to press a
button in — and changing it is the first thing setup does. It is an ordinary
config resource, so the project does it live: no restart, no config-resource
editing by hand.

One press turns a fresh Edge gateway green: the provider is adopted, the tags
are installed under it, the file store is created and thirty days of OEE history
are generated — 630 shift rows and 5,229 hour rows across seven lines. Pressing
it again changes nothing.

The build assumes Edge's provider is called `edge`, which is the name it ships
with. If a site renamed theirs, either rename it back or rebuild with a
different provider in `package.sh`.

## Proving the two implementations agree

`?action=parity` on the **standard** gateway runs every OEE query BOTH ways and
compares the answers:

```
curl -u <user>:<pass> \
  'http://<gateway>/system/webdev/OEE/lp_init?action=parity&hours=720'
```

Unlike a demo where both implementations read one store, these two read
different ones — so the gate first MIRRORS the SQL records into a scratch file
store, and asks both about the same rows. It only runs where there is a database;
on Edge there is no SQL side and it says so rather than reporting a vacuous pass.

Two things it taught us, both of which look like bugs in the new code and are not:

* **The window has to stop at the top of the current hour.** The demo is running
  while the gate runs, and the live engine rewrites the hour in progress on every
  tick — so a window that includes it compares two reads of a moving row.
* **The mirror has to ask SQLite what it is actually holding.** The schema
  declares `target_production_count INTEGER` and the generator writes 7091.25
  into it. SQLite keeps the REAL, `SUM()` keeps the .25, and the JDBC driver
  honours the DECLARED type and hands back 7091 — so the standard build already
  disagrees with itself between a row read and a rollup, and a naive mirror
  reports the file store wrong for holding the number that was written.

`?action=stats` is the quicker check on either edition: it runs every query and
reports the row counts and per-line figures without a browser, which on Edge is
the only way to ask, because the screens are the thing being checked.

## The test rigs

Both editions use the same image; the **edition is chosen at commissioning** and
there is no environment variable for it, so `tools/commission.js` presses the
button:

```
node tools/commission.js http://localhost:8888 admin password 'Edge Edition'
node tools/commission.js http://localhost:8988 admin password 'Ignition'
node tools/dismiss-quickstart.js http://localhost:8988
```

Two traps, both of which look like something else:

* A fresh **standard** gateway raises an "Enable Quick Start" modal whose scrim
  covers the whole page. Every headless click times out on an element that is
  plainly visible in the screenshot.
* A **new project directory needs TWO scans**: the first registers the project,
  the second registers its resources with the modules. Between them the project
  is running and its WebDev endpoints 404.

## Tools

| Script | What it checks |
| ------ | --------------- |
| `tools/build_tag_exports.py` | Rebuilds a Designer-importable tag export from the gateway's config-resource tags |
| `tools/check_columns.py` | Fails the build if a store function's params list drifts out of order with its column list |
| `tools/check_page_scroll.js` | Fails if a project page scrolls as a page at the smallest supported window |
| `tools/check_recovery.js` | Asserts a session opened before setup recovers once setup runs |
| `tools/check_resources.py` | Fails the build if a project resource folder contains files its `resource.json` does not declare |
| `tools/commission.js` | Commissions a fresh gateway headlessly, choosing standard or Edge Edition |
| `tools/dismiss-quickstart.js` | Dismisses the "Enable Quick Start" modal that blocks headless clicks on a fresh gateway |
| `tools/gen_setup_payload.py` | Bakes the Setup button's tag/table/history payload into each project |
| `tools/install_ui.js` | Installs the packaged projects through the gateway's own Import Project dialog and presses Setup |
| `tools/kpi_seed.py` | Generates the KPI file-store seed from the dashboard's CREATE TABLE script, or checks it matches |
| `tools/preflight.js` | Gets a fresh gateway past its first-login modal so scan tooling can drive it |
| `tools/reset_trial.js` | Resets an Ignition trial licence headlessly |
| `tools/shoot-page.js` | Screenshots one Perspective page, waiting out the connection banner first |
| `tools/theme_border_check.js` | Checks `var(--containerBorder)` actually renders a border under every theme a gateway offers |
| `tools/verify.js` | Acceptance check against a running install — reads the rendered DOM for AU units, dates and formats |
