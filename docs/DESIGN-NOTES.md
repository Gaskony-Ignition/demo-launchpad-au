# Design notes for the script library

Notes for whoever maintains `launchpad.*`. They were module docstrings; the code now carries one-line summaries.

## launchpad.setup (OEE and KPI, byte-identical)

- Each project ships its own SQLite file, `${data}/OEE.db` and `${data}/KPI.db`. The schema is SQLite DDL and SQLite needs no credentials, so Setup can create the connection outright. Moving to Postgres or MSSQL needs portable DDL first; pointing Setup at an existing non-SQLite connection would half-build the schema, which is why it refuses.
- The tag historian is one gateway provider with one database. It belongs to KPI; OEE never creates it.
- The connection URL sets `journal_mode=WAL` so writers do not block readers, and `busy_timeout=30000` so a second writer waits instead of failing with SQLITE_BUSY.
- Pressing Setup again does not reinstall tags. Installing over live tags leaves the old tag script subscribed, so the counter runs twice per tick until a gateway restart. A reinstall is asked for explicitly (`tags=1`, the Update tags button).

## launchpad.store (OEE)

- One contract, two implementations: callers pass the table, a match list of `(column, op, value)` and positional columns and values. SQL is generated from that, so there are no two hand-written column lists to drift apart.
- On Edge the records are files: `data/launchpad-oee/hour/YYYY-MM-DD.json` and `shift/YYYY-MM-DD.json`, one per day; `config.json` and `rate.json` are single files. Day files, because the timer only touches the current hour and shift: one document for thirty days of seven lines would rewrite about 5,000 rows every tick.
- Timestamps are stored as epoch milliseconds: a `java.util.Date` does not survive a JSON round trip and a formatted string does not survive a timezone.
- `seedBegin` / commit / rollback are a SQL transaction on a gateway with a database, and a staging directory swapped in at commit on the file store. A timer tick that lands mid-seed writes into staging and is swapped in with it.
- `parity()` copies the SQL records into a scratch file store and compares the read functions on both. Its window stops at the top of the hour, because the engine rewrites the current hour every tick.
- SQLite keeps `7091.25` in an INTEGER column but the JDBC driver returns `7091`, while `SUM()` keeps the `.25`. The mirror reads `typeof()` and `CAST AS REAL` per column for that reason.

## launchpad.store (KPI)

- On Edge the six dashboard tables are whole JSON files under `data/launchpad-kpi/<table>.json`, with the same columns in the same order as the named queries. They are not partitioned: the tables are tens of rows and every question joins across all of them.
- New ids are `MAX + 1`, matching AUTOINCREMENT, because the dashboard code needs the new id back to attach widgets to it.
- A widget's parameters come from its widget type; the value is the dashboard's override if there is one, else the type's default.
- `deleteDashboard` on the file store does by hand the `ON DELETE CASCADE` the schema declares, including the widgets' parameter overrides; otherwise a recycled widget id would inherit another widget's settings.
