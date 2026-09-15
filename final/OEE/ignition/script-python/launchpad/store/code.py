"""
launchpad.store - the OEE records, with or without a database.

The demo keeps four tables of its own: an hour rollup, a shift rollup, a
per-line config and a rate lookup. On a standard gateway they are SQL. On
Ignition Edge there is no database of any kind, so the same rows are kept as
JSON in the gateway's own data directory.

Both paths go through the SAME contract - the caller names the table, how to
find the row, and the columns it is writing, and hands over values in that
order:

    store.insert(store.HOUR, HOUR_START_COLUMNS, params)
    store.update(store.HOUR,
                 [("line_name", store.EQ, name),
                  ("hour_timestamp", store.EQ, hourStart)],
                 HOUR_END_COLUMNS, params)

The SQL statement is GENERATED from that contract rather than written beside
it. Two hand-written column lists that have to stay in step are two lists that
will not, and the failure is a row written into the wrong columns - which SQL
accepts without complaint whenever the types happen to line up.

## How the file store is laid out

    data/launchpad-oee/hour/2026-09-10.json     one file per day
    data/launchpad-oee/shift/2026-09-10.json    one file per day
    data/launchpad-oee/config.json              small, one file
    data/launchpad-oee/rate.json                small, one file

Partitioned by day because the writer is a gateway timer that touches only the
current hour and shift: a single document holding thirty days of seven lines is
five thousand rows rewritten every tick. A day file is a few hundred rows and
is the only one a live tick opens. A query over a range opens the files in that
range and nothing else.

Timestamps are stored as epoch milliseconds. A java.util.Date does not survive
a JSON round trip, and a formatted string does not survive a timezone.
"""

from java.lang import System as JSystem
from java.lang import Throwable as JThrowable
from java.util import Date as JDate
from java.util.concurrent.locks import ReentrantLock

LOG = system.util.getLogger("launchpad.store")

# table id -> (SQL table name, timestamp column that partitions it or None)
HOUR = "hour"
SHIFT = "shift"
CONFIG = "config"
RATE = "rate"

TABLES = {
	HOUR: ("ex_launchpad_oee_hour", "hour_timestamp"),
	SHIFT: ("ex_launchpad_oee_shift", "shift_start"),
	CONFIG: ("ex_launchpad_oee_config", None),
	RATE: ("ex_launchpad_oee_rate", None),
}

# One writer at a time. The OEE timer is a single gateway thread, but the seed
# and the heal run on their own, and two threads rewriting one day file lose
# whichever finishes first.
_LOCK = ReentrantLock()

# Set only by the parity gate at the bottom of this module, which needs to ask
# the file implementation a question on a gateway that has a database.
_FORCE_FILE = {"on": False}


def sqlName(table):
	return TABLES[table][0]


def _noDatabase():
	# _FORCE_FILE is the parity gate holding this to the file implementation on
	# a gateway that has both; nothing else ever sets it.
	if _FORCE_FILE["on"]:
		return True
	return not launchpad.edition.hasDatabase()


# ---------------------------------------------------------------------------
# the file store
# ---------------------------------------------------------------------------


def root():
	"""Where the file store lives.

	The gateway runs with its installation directory as the working directory
	on every platform and in the official container image, and no scripting
	function returns it, so this is the portable way to ask.
	"""
	return JSystem.getProperty("user.dir") + "/data/launchpad-oee"


# While a rebuild is staging, every read and write goes to the staging copy
# instead - see seedBegin. Nothing else changes: the paths are built from this
# rather than from root().
_STAGE = {"root": None}


def _stagedRoot():
	return _STAGE["root"] or root()


def _millis(value):
	if isinstance(value, JDate):
		return long(system.date.toMillis(value))
	return value


def _encode(row):
	"""A row as something json can hold, without losing any of it.

	Dates become epoch millis. Java numbers become Python ones FIRST: a
	BigDecimal or a java.lang.Integer handed straight to jsonEncode does not
	always come back the same number, and the way that shows up is a rollup
	whose target count is a quarter short per row and whose total is a whole
	unit out over a shift. Measured against the SQL implementation by
	?action=parity, which is exactly the class of difference it exists to
	catch.
	"""
	from java.lang import Number as JNumber
	out = {}
	for k, v in row.items():
		v = _millis(v)
		if isinstance(v, JNumber):
			f = float(v.doubleValue())
			v = long(f) if f == long(f) else f
		out[k] = v
	return out


def _decode(row, dateColumns):
	out = dict(row)
	for c in dateColumns:
		v = out.get(c)
		if v is not None and not isinstance(v, JDate):
			out[c] = system.date.fromMillis(long(v))
	return out


# Which columns hold a timestamp, per table. Needed on the way back out: JSON
# gives back a number and every consumer wants the Date it put in.
DATE_COLUMNS = {
	HOUR: ("utc_timestamp", "day_timestamp", "hour_timestamp"),
	SHIFT: ("utc_timestamp", "shift_start", "shift_end"),
	CONFIG: ("utc_timestamp",),
	RATE: (),
}


def _dayKey(millis):
	return system.date.format(system.date.fromMillis(long(millis)), "yyyy-MM-dd")


def _path(table, dayKey=None):
	base = _stagedRoot()
	if dayKey is None:
		return base + "/" + table + ".json"
	return base + "/" + table + "/" + dayKey + ".json"


def _read(path):
	try:
		if not system.file.fileExists(path):
			return []
		text = system.file.readFileAsString(path, "UTF-8")
		if not text:
			return []
		return system.util.jsonDecode(text)
	except (JThrowable, Exception):
		import traceback
		LOG.warn("could not read %s - treating it as empty: %s"
		         % (path, traceback.format_exc()))
		return []


def _write(path, rows):
	# Written whole, every time. These files are hundreds of rows, not
	# thousands, and a partial write of a day's OEE is worse than a slow one.
	system.file.writeFile(path, system.util.jsonEncode(rows, 0))


def _partitionOf(table, row):
	"""The day file a row belongs in, or None for an unpartitioned table."""
	_name, tsColumn = TABLES[table]
	if tsColumn is None:
		return None
	value = row.get(tsColumn)
	if value is None:
		return _dayKey(system.date.toMillis(system.date.now()))
	return _dayKey(_millis(value))


# A match is a list of (column, operator, value). Equality alone was not
# enough: the shift-end update finds its row with `shift_end is null`, which is
# the whole point of it - a shift is closed once, and the open one is the row
# without an end. A key list of column names cannot say that.
EQ, ISNULL, NOTNULL = "=", "isnull", "notnull"


def _matches(row, match):
	for column, op, value in match:
		have = row.get(column)
		if op == ISNULL:
			if have is not None:
				return False
		elif op == NOTNULL:
			if have is None:
				return False
		elif _millis(have) != _millis(value):
			return False
	return True


def _whereSql(match):
	"""(sql, params) for a match list."""
	parts, params = [], []
	for column, op, value in match:
		if op == ISNULL:
			parts.append("%s IS NULL" % column)
		elif op == NOTNULL:
			parts.append("%s IS NOT NULL" % column)
		else:
			parts.append("%s = ?" % column)
			params.append(value)
	return " AND ".join(parts), params


def _searchDays(table, match):
	"""The day files an update has to look in.

	When the match pins the partitioning timestamp, that is one file. When it
	does not - the shift-end update matches on shift name and a null end - the
	open row could be in yesterday's file as easily as today's, so the search
	runs newest-first over the recent ones. Newest-first matters: the row being
	closed is the most recent, and stopping at the first hit is what keeps a
	rate change from rewriting a shift that ended a week ago.
	"""
	_name, tsColumn = TABLES[table]
	if tsColumn is None:
		return [None]
	for column, op, value in match:
		if column == tsColumn and op == EQ:
			return [_dayKey(_millis(value))]
	days = _dayFiles(table)
	days.reverse()
	return days[:3]


def _fileUpdate(table, match, row):
	"""Change the first matching row. No match is a no-op, as in SQL."""
	_LOCK.lock()
	try:
		for day in _searchDays(table, match):
			path = _path(table, day)
			rows = _read(path)
			for i in range(len(rows)):
				if _matches(rows[i], match):
					merged = dict(rows[i])
					merged.update(_encode(row))
					rows[i] = merged
					_write(path, rows)
					return 1
		return 0
	finally:
		_LOCK.unlock()


def _fileInsert(table, row):
	_LOCK.lock()
	try:
		path = _path(table, _partitionOf(table, row))
		rows = _read(path)
		rows.append(_encode(row))
		_write(path, rows)
		return 1
	finally:
		_LOCK.unlock()


def _dayFiles(table):
	from java.io import File
	d = File(_stagedRoot() + "/" + table)
	names = d.list()
	if names is None:
		return []
	return sorted([unicode(n)[:-5] for n in names if unicode(n).endswith(".json")])


def _rowsBetween(table, startMillis, endMillis):
	"""Every row of a partitioned table whose own timestamp is in the window.

	Only the day files that overlap the window are opened. The bound is
	inclusive at both ends, which is what BETWEEN means in the query this
	replaces.
	"""
	_name, tsColumn = TABLES[table]
	first = _dayKey(startMillis)
	last = _dayKey(endMillis)
	out = []
	for day in _dayFiles(table):
		if day < first or day > last:
			continue
		for r in _read(_path(table, day)):
			ts = r.get(tsColumn)
			if ts is None:
				continue
			if long(ts) >= startMillis and long(ts) <= endMillis:
				out.append(r)
	return out


def _allRows(table):
	_name, tsColumn = TABLES[table]
	if tsColumn is None:
		return _read(_path(table))
	out = []
	for day in _dayFiles(table):
		out.extend(_read(_path(table, day)))
	return out


# ---------------------------------------------------------------------------
# the write API - one contract, two implementations
# ---------------------------------------------------------------------------


def insert(table, columns, values, tx=None):
	"""Add a row. `columns` and `values` are positional partners.

	`tx` is passed through to the database so the thirty-day seed stays one
	transaction; the file store ignores it, having nothing to roll back to.
	"""
	if len(columns) != len(values):
		raise ValueError("insert(%s): %d columns and %d values"
		                 % (table, len(columns), len(values)))
	if _noDatabase():
		return _fileInsert(table, dict(zip(columns, values)))
	sql = ("INSERT INTO %s (%s) VALUES (%s)"
	       % (sqlName(table), ", ".join(columns),
	          ", ".join(["?"] * len(columns))))
	if tx is not None:
		return system.db.runPrepUpdate(sql, list(values), tx=tx)
	return system.db.runPrepUpdate(sql, list(values), database=launchpad.oee.db())


def insertMany(table, columns, values, tx=None):
	"""Add several rows at once from ONE flat list of values.

	`values` is every row's values end to end - 24 hours of 30 columns is a
	list of 720 - which is the shape the history generator already builds,
	because it was assembling a multi-row INSERT by repeating the VALUES
	clause. Keeping the batch matters on SQL: the thirty-day seed is 5,000-odd
	rows, and one statement per row makes it minutes rather than seconds.

	The file store has no such distinction and appends them one at a time; it
	is writing one day file per call either way.
	"""
	width = len(columns)
	if width == 0 or len(values) % width:
		raise ValueError("insertMany(%s): %d values do not divide into rows of "
		                 "%d columns" % (table, len(values), width))
	rows = [values[i:i + width] for i in range(0, len(values), width)]
	if _noDatabase():
		for row in rows:
			_fileInsert(table, dict(zip(columns, row)))
		return len(rows)
	clause = "(%s)" % ", ".join(["?"] * width)
	sql = ("INSERT INTO %s (%s) VALUES %s"
	       % (sqlName(table), ", ".join(columns),
	          ", ".join([clause] * len(rows))))
	if tx is not None:
		return system.db.runPrepUpdate(sql, list(values), tx=tx)
	return system.db.runPrepUpdate(sql, list(values),
	                               database=launchpad.oee.db())


def update(table, match, columns, values):
	"""Change the row `match` finds. No match is a no-op, exactly as in SQL.

	`match` is a list of (column, operator, value) - see EQ / ISNULL / NOTNULL.
	`columns`/`values` are the SET list and are positional partners.
	"""
	if len(columns) != len(values):
		raise ValueError("update(%s): %d columns and %d values"
		                 % (table, len(columns), len(values)))
	row = dict(zip(columns, values))
	if _noDatabase():
		return _fileUpdate(table, match, row)
	where, whereParams = _whereSql(match)
	sql = ("UPDATE %s SET %s WHERE %s"
	       % (sqlName(table),
	          ", ".join(["%s = ?" % c for c in columns]), where))
	return system.db.runPrepUpdate(sql, list(values) + whereParams,
	                               database=launchpad.oee.db())


def appendText(table, match, appends):
	"""Append to comma-separated TEXT columns on the row `match` finds.

	`appends` is {column: value}. Two columns on each rollup row keep the
	rate changes that happened during it as a comma-separated list, and in SQL
	that is `col = col || ',' || cast(? as text)`. It is a read-modify-write
	either way; this is the one operation where the two implementations do not
	look alike, so it lives here rather than at the call site.
	"""
	if _noDatabase():
		_LOCK.lock()
		try:
			for day in _searchDays(table, match):
				path = _path(table, day)
				rows = _read(path)
				for i in range(len(rows)):
					if not _matches(rows[i], match):
						continue
					for column, value in appends.items():
						have = rows[i].get(column)
						rows[i][column] = (u"%s,%s" % (have, value)
						                   if have not in (None, "")
						                   else unicode(value))
					_write(path, rows)
					return 1
			return 0
		finally:
			_LOCK.unlock()
	where, whereParams = _whereSql(match)
	sets, params = [], []
	for column, value in appends.items():
		# cast on BOTH sides, as the hand-written statements did: the column
		# is TEXT but a first append onto a numeric-looking value is where a
		# database decides to do arithmetic instead of concatenation.
		sets.append("%s = cast(%s as text) || ',' || cast(? as text)"
		            % (column, column))
		params.append(value)
	return system.db.runPrepUpdate(
		"UPDATE %s SET %s WHERE %s" % (sqlName(table), ", ".join(sets), where),
		params + whereParams, database=launchpad.oee.db())


def upsert(table, match, columns, values):
	"""Change the row if it is there, add it if it is not."""
	if update(table, match, columns, values):
		return 1
	return insert(table, columns, values)


def deleteOlderThan(table, column, cutoff):
	"""Drop rows whose `column` is before `cutoff`."""
	if _noDatabase():
		_LOCK.lock()
		try:
			bound = _millis(cutoff)
			removed = 0
			_name, tsColumn = TABLES[table]
			if tsColumn is None:
				path = _path(table)
				rows = _read(path)
				keep = [r for r in rows
				        if r.get(column) is None or long(r[column]) >= bound]
				removed = len(rows) - len(keep)
				if removed:
					_write(path, keep)
				return removed
			for day in _dayFiles(table):
				path = _path(table, day)
				rows = _read(path)
				keep = [r for r in rows
				        if r.get(column) is None or long(r[column]) >= bound]
				if len(keep) != len(rows):
					removed += len(rows) - len(keep)
					_write(path, keep)
			return removed
		finally:
			_LOCK.unlock()
	return system.db.runPrepUpdate(
		"DELETE FROM %s WHERE %s < ?" % (sqlName(table), column),
		[cutoff], database=launchpad.oee.db())


def deleteAll(table, tx=None):
	if _noDatabase():
		_LOCK.lock()
		try:
			from java.io import File
			_name, tsColumn = TABLES[table]
			if tsColumn is None:
				_write(_path(table), [])
				return
			for day in _dayFiles(table):
				File(_path(table, day)).delete()
		finally:
			_LOCK.unlock()
		return
	sql = "DELETE FROM %s" % sqlName(table)
	if tx is not None:
		system.db.runUpdateQuery(sql, tx=tx)
	else:
		system.db.runUpdateQuery(sql, database=launchpad.oee.db())


def count(table, tx=None):
	if _noDatabase():
		return len(_allRows(table))
	sql = "SELECT COUNT(*) FROM %s" % sqlName(table)
	if tx is not None:
		return system.db.runScalarQuery(sql, tx=tx)
	return system.db.runScalarQuery(sql, database=launchpad.oee.db())


# ---------------------------------------------------------------------------
# rebuilding the history atomically
# ---------------------------------------------------------------------------
# The thirty-day seed DELETEs both rollups and regenerates them, so a failure
# part way through - a generator error, a gateway restart - must not be able to
# leave a gateway with no history and no way back. On a button the install
# instructions tell every user to press, a failure that destroys data and then
# invites a retry is the worst possible shape.
#
# On SQL that is a transaction. On the file store it is a staging directory
# swapped in at the end: the live files are untouched until the new set is
# complete, and a failure leaves them exactly as they were.
#
# A live timer tick that lands mid-seed writes into the staging set and is
# swapped in with it, which is the behaviour we want and is not what the SQL
# path does - there the tick is simply outside the transaction. Neither loses
# the tick.

def seedBegin():
	"""Start an all-or-nothing rebuild. Returns the handle to pass back."""
	if not _noDatabase():
		return system.db.beginTransaction(database=launchpad.oee.db(),
		                                  timeout=300000)
	from java.io import File
	stage = root() + ".rebuilding"
	_deleteTree(File(stage))
	for sub in ("", "/" + HOUR, "/" + SHIFT):
		File(stage + sub).mkdirs()
	# carry the small unpartitioned tables across - the rebuild replaces the
	# rollups, not the rate lookup or the per-line config
	for table in (CONFIG, RATE):
		rows = _read(_path(table))
		if rows:
			system.file.writeFile(stage + "/" + table + ".json",
			                      system.util.jsonEncode(rows, 0))
	_STAGE["root"] = stage
	return stage


def seedCommit(handle):
	if not _noDatabase():
		system.db.commitTransaction(handle)
		return
	from java.io import File
	live, stage = File(root()), File(handle)
	old = File(root() + ".replaced")
	_deleteTree(old)
	_STAGE["root"] = None
	if live.exists() and not live.renameTo(old):
		raise Exception("could not move the live OEE store aside")
	if not stage.renameTo(live):
		# put it back rather than leave the gateway with nothing
		old.renameTo(live)
		raise Exception("could not swap the rebuilt OEE store into place")
	_deleteTree(old)


def seedRollback(handle):
	if not _noDatabase():
		system.db.rollbackTransaction(handle)
		return
	from java.io import File
	_STAGE["root"] = None
	_deleteTree(File(handle))


def seedClose(handle):
	if not _noDatabase():
		system.db.closeTransaction(handle)
		return
	_STAGE["root"] = None


def _deleteTree(f):
	if not f.exists():
		return
	children = f.listFiles()
	if children:
		for c in children:
			_deleteTree(c)
	f.delete()


# The rate lookup the SQL schema seeds with its CREATE TABLE. The file store
# has no DDL to hang it off, so it is written here - and the demo reads
# 'default' for every line that has not been given a rate of its own, so an
# empty rate file is a demo with no target rate anywhere.
DEFAULT_RATE = {"rate_name": "default", "uom": "units", "target_rate": 15,
                "interval": "minute"}


def ready():
	"""Is the store able to hold records yet?

	The question `tablesPresent` asks, answered for a store that has no tables.
	It is the directories and the default rate, which is what ensure() makes.
	"""
	from java.io import File
	if not _noDatabase():
		return True
	return (File(root() + "/" + SHIFT).exists()
	        and File(root() + "/" + HOUR).exists()
	        and bool(_read(_path(RATE))))


def ensure():
	"""Make the store ready to be written to.

	Creates nothing on SQL - that is launchpad.oee.initTables' job, and its
	CREATE TABLE seeds the default rate on the way past. On a gateway with no
	database it makes the directories and writes that same default rate.
	"""
	if not _noDatabase():
		return u"tables are the database's"
	from java.io import File
	for sub in ("", "/" + HOUR, "/" + SHIFT):
		File(root() + sub).mkdirs()
	if not [r for r in _read(_path(RATE))
	        if r.get("rate_name") == DEFAULT_RATE["rate_name"]]:
		insert(RATE, list(DEFAULT_RATE.keys()),
		       [DEFAULT_RATE[k] for k in DEFAULT_RATE.keys()])
	return u"file store ready at %s" % root()


# ---------------------------------------------------------------------------
# the read API - every query the screens make
# ---------------------------------------------------------------------------
# One function per named query, returning the same columns in the same order
# under the same names, because a chart bound to column 7 does not check what
# column 7 is called.
#
# On a gateway with a database each of these IS the named query - it runs the
# resource, so there is one copy of that SQL and it is the copy that shipped.
# On a gateway without one the same answer is computed from the file store.
# ?cmd=parity runs both over the same records and compares them.


def _num(v):
	return 0.0 if v is None else float(v)


def rowsAsJson(ds):
	"""A dataset as a list of dicts.

	The bindings these functions replace came in two flavours: some asked the
	query for a dataset, some for `returnFormat: json`, which Perspective hands
	back as an array of objects. A script binding returns whatever the script
	returns, so the ones that wanted json call this and the rest do not - and
	the consumers on the other side of them are unchanged.
	"""
	out = []
	names = [unicode(ds.getColumnName(c)) for c in range(ds.getColumnCount())]
	for r in range(ds.getRowCount()):
		row = {}
		for c in range(ds.getColumnCount()):
			row[names[c]] = ds.getValueAt(r, c)
		out.append(row)
	return out


def _named(path, params):
	return system.db.runNamedQuery(path, params)


def _windowParams(lineName, tagFolder, startTime, stopTime):
	return {"line_name": lineName or "", "tag_folder": tagFolder,
	        "start_time": startTime, "stop_time": stopTime}


def _hourRowsInWindow(lineName, tagFolder, startMillis, endMillis, column):
	"""Hour rows filtered on `column`, which is hour_timestamp or day_timestamp.

	The day files are partitioned by hour_timestamp. A window on day_timestamp
	therefore has to look one day wider at each end - the midnight an hour
	belongs to can fall outside the window its own timestamp is in - and then
	filter exactly.
	"""
	pad = 86400000 if column == "day_timestamp" else 0
	rows = _rowsBetween(HOUR, startMillis - pad, endMillis + pad)
	out = []
	for r in rows:
		if r.get("tag_folder") != tagFolder:
			continue
		if lineName and r.get("line_name") != lineName:
			continue
		v = r.get(column)
		if v is None or long(v) < startMillis or long(v) > endMillis:
			continue
		out.append(r)
	return out


DAILY_STATS_COLUMNS = [
	"line_name", "time_stamp", "oee_a", "oee_p", "oee_q", "oee_u", "oee",
	"target_rate", "target_production_count", "production_count",
	"reject_count", "downtime", "idletime", "runtime", "minutes_elapsed",
	"minutes_running", "down_minutes", "idle_minutes",
]


def dailyStats(lineName, tagFolder, startTime, stopTime):
	"""Hour rollups averaged into days, per line. Launchpad/Oee/DailyStats."""
	if not _noDatabase():
		return _named("Launchpad/Oee/DailyStats",
		              _windowParams(lineName, tagFolder, startTime, stopTime))

	rows = _hourRowsInWindow(lineName, tagFolder, _millis(startTime),
	                         _millis(stopTime), "day_timestamp")
	groups = {}
	for r in rows:
		groups.setdefault((r.get("line_name"), long(r["day_timestamp"])),
		                  []).append(r)
	out = []
	for key in sorted(groups.keys(), key=lambda k: (k[1], k[0])):
		g = groups[key]
		n = float(len(g))
		avg = lambda c: sum([_num(r.get(c)) for r in g]) / n
		total = lambda c: sum([_num(r.get(c)) for r in g])
		out.append([
			key[0], system.date.fromMillis(key[1]),
			avg("hour_oee_a"), avg("hour_oee_p"), avg("hour_oee_q"),
			avg("hour_oee_u"), avg("hour_oee"), avg("target_rate"),
			total("target_production_count"), total("hour_production_count"),
			total("hour_reject_count"), total("hour_down_seconds"),
			total("hour_idle_seconds"), total("hour_seconds_running"),
			total("hour_seconds_elapsed") / 60.0,
			total("hour_seconds_running") / 60.0,
			total("hour_down_seconds") / 60.0,
			total("hour_idle_seconds") / 60.0,
		])
	return system.dataset.toDataSet(DAILY_STATS_COLUMNS, out)


HOURLY_STATS_COLUMNS = [
	"line_name", "time_stamp", "oee_a", "oee_p", "oee_q", "oee_u", "oee",
	"target_rate", "target_production_count", "production_count",
	"reject_count", "seconds_elapsed", "seconds_running", "down_seconds",
	"idle_seconds", "minutes_elapsed", "minutes_running", "down_minutes",
	"idle_minutes", "day_timestamp",
]


def hourlyStats(lineName, tagFolder, startTime, stopTime):
	"""One row per line per hour. Launchpad/Oee/HourlyStats."""
	if not _noDatabase():
		return _named("Launchpad/Oee/HourlyStats",
		              _windowParams(lineName, tagFolder, startTime, stopTime))

	rows = _hourRowsInWindow(lineName, tagFolder, _millis(startTime),
	                         _millis(stopTime), "hour_timestamp")
	rows.sort(key=lambda r: long(r["hour_timestamp"]))
	out = []
	for r in rows:
		elapsed = _num(r.get("hour_seconds_elapsed"))
		running = _num(r.get("hour_seconds_running"))
		down = _num(r.get("hour_down_seconds"))
		idle = _num(r.get("hour_idle_seconds"))
		out.append([
			r.get("line_name"),
			system.date.fromMillis(long(r["hour_timestamp"])),
			r.get("hour_oee_a"), r.get("hour_oee_p"), r.get("hour_oee_q"),
			r.get("hour_oee_u"), r.get("hour_oee"), r.get("target_rate"),
			r.get("target_production_count"), r.get("hour_production_count"),
			r.get("hour_reject_count"), r.get("hour_seconds_elapsed"),
			r.get("hour_seconds_running"), r.get("hour_down_seconds"),
			r.get("hour_idle_seconds"),
			elapsed / 60.0, running / 60.0, down / 60.0, idle / 60.0,
			system.date.fromMillis(long(r["day_timestamp"]))
			if r.get("day_timestamp") is not None else None,
		])
	return system.dataset.toDataSet(HOURLY_STATS_COLUMNS, out)


HOURLY_AVERAGE_COLUMNS = [
	"line_name", "oee_a", "oee_p", "oee_q", "oee_u", "oee",
	"target_production_count", "production_count", "reject_count",
	"downtime", "idletime", "runtime", "target_rate", "minutes_elapsed",
	"minutes_running", "down_minutes", "idle_minutes",
]


def hourlyStatsAverage(lineName, tagFolder, startTime, stopTime):
	"""One row per line, averaged over the window.
	Launchpad/Oee/HourlyStatsAverage."""
	if not _noDatabase():
		return _named("Launchpad/Oee/HourlyStatsAverage",
		              _windowParams(lineName, tagFolder, startTime, stopTime))

	rows = _hourRowsInWindow(lineName, tagFolder, _millis(startTime),
	                         _millis(stopTime), "hour_timestamp")
	groups = {}
	for r in rows:
		groups.setdefault(r.get("line_name"), []).append(r)
	out = []
	for line in sorted(groups.keys()):
		g = groups[line]
		n = float(len(g))
		avg = lambda c: sum([_num(r.get(c)) for r in g]) / n
		total = lambda c: sum([_num(r.get(c)) for r in g])
		out.append([
			line,
			avg("hour_oee_a"), avg("hour_oee_p"), avg("hour_oee_q"),
			avg("hour_oee_u"), avg("hour_oee"),
			total("target_production_count"), total("hour_production_count"),
			total("hour_reject_count"), total("hour_down_seconds"),
			total("hour_idle_seconds"), total("hour_seconds_running"),
			avg("target_rate"),
			total("hour_seconds_elapsed") / 60.0,
			total("hour_seconds_running") / 60.0,
			total("hour_down_seconds") / 60.0,
			total("hour_idle_seconds") / 60.0,
		])
	return system.dataset.toDataSet(HOURLY_AVERAGE_COLUMNS, out)


SHIFT_STATS_COLUMNS = [
	"line_name", "time_stamp", "shift", "oee_a", "oee_p", "oee_q", "oee_u",
	"oee", "target_production_count", "production_count", "reject_count",
	"downtime", "idletime", "runtime", "target_rate", "minutes_elapsed",
	"minutes_running", "down_minutes", "idle_minutes",
]


def shiftStats(lineName, tagFolder, startTime, stopTime):
	"""Shift rollups over a window, per line and shift.
	Launchpad/Oee/ShiftStats."""
	if not _noDatabase():
		return _named("Launchpad/Oee/ShiftStats",
		              _windowParams(lineName, tagFolder, startTime, stopTime))

	rows = _rowsBetween(SHIFT, _millis(startTime), _millis(stopTime))
	groups = {}
	for r in rows:
		if r.get("tag_folder") != tagFolder:
			continue
		if lineName and r.get("line_name") != lineName:
			continue
		groups.setdefault((r.get("line_name"), long(r.get("shift_start") or 0),
		                   r.get("shift")), []).append(r)
	out = []
	for key in sorted(groups.keys(), key=lambda k: (k[1], k[0])):
		g = groups[key]
		n = float(len(g))
		avg = lambda c: sum([_num(r.get(c)) for r in g]) / n
		total = lambda c: sum([_num(r.get(c)) for r in g])
		out.append([
			key[0], system.date.fromMillis(key[1]), key[2],
			avg("shift_oee_a"), avg("shift_oee_p"), avg("shift_oee_q"),
			avg("shift_oee_u"), avg("shift_oee"),
			total("target_production_count"),
			total("shift_production_count"), total("shift_reject_count"),
			total("shift_down_seconds"), total("shift_idle_seconds"),
			total("shift_running_seconds"), avg("target_rate"),
			total("shift_seconds_elapsed") / 60.0,
			total("shift_running_seconds") / 60.0,
			total("shift_down_seconds") / 60.0,
			total("shift_idle_seconds") / 60.0,
		])
	return system.dataset.toDataSet(SHIFT_STATS_COLUMNS, out)


TOP_PRODUCTION_COLUMNS = ["hour_timestamp", "hour_production_count",
                          "target_hour"]


def topProduction(lineName, startTime, endTime):
	"""The line's hours, best first. Launchpad/Oee/TopProduction.

	"Best" is the SQL's own ordering: the shortfall against target as a
	fraction of target, ascending. Note it does NOT filter on tag_folder -
	neither does the query - so the parameters here are the query's.
	"""
	if not _noDatabase():
		return _named("Launchpad/Oee/TopProduction",
		              {"lineName": lineName, "startTime": startTime,
		               "endTime": endTime})

	rows = _rowsBetween(HOUR, _millis(startTime), _millis(endTime))
	out = []
	for r in rows:
		if r.get("line_name") != lineName:
			continue
		target = _num(r.get("target_rate")) * 60.0
		produced = _num(r.get("hour_production_count"))
		shortfall = ((target - produced) / target) if target else 0.0
		out.append((shortfall,
		            [system.date.fromMillis(long(r["hour_timestamp"])),
		             r.get("hour_production_count"), target]))
	out.sort(key=lambda pair: pair[0])
	return system.dataset.toDataSet(TOP_PRODUCTION_COLUMNS,
	                                [row for _s, row in out])


RATE_COLUMNS = ["rate_name", "uom", "target_rate", "interval"]


def selectRates():
	"""Every rate definition, by name. Launchpad/Oee/SelectRates."""
	if not _noDatabase():
		return _named("Launchpad/Oee/SelectRates", {})
	rows = sorted(_read(_path(RATE)),
	              key=lambda r: unicode(r.get("rate_name") or ""))
	return system.dataset.toDataSet(
		RATE_COLUMNS,
		[[r.get("rate_name"), r.get("uom"), r.get("target_rate"),
		  r.get("interval")] for r in rows])


def rateData(rateName):
	"""One rate definition. Launchpad/Oee/SelectRateData.

	Zero rows when the name is unknown, which is what the caller checks.
	"""
	if not _noDatabase():
		return _named("Launchpad/Oee/SelectRateData", {"rate_name": rateName})
	out = []
	for r in _read(_path(RATE)):
		if r.get("rate_name") == rateName:
			out.append([r.get("rate_name"), r.get("uom"),
			            r.get("target_rate"), r.get("interval")])
	return system.dataset.toDataSet(RATE_COLUMNS, out)


# ---------------------------------------------------------------------------
# proving the two implementations agree
# ---------------------------------------------------------------------------
# Two implementations of seven queries is two chances for the Edge build to
# start answering something different, and neither one fails loudly when it
# does: a drifted rollup is a plausible number on a chart.
#
# Unlike the alarm demo - where both implementations read one journal - these
# two read different stores, so they cannot simply be run side by side. The
# gate therefore MIRRORS the SQL records into a scratch file store and asks the
# same seven questions of both over the same rows. It only runs on a gateway
# that has a database; on Edge there is no SQL side and it says so rather than
# reporting a vacuous pass.

def _forceFile(on, scratchRoot=None):
	_FORCE_FILE["on"] = bool(on)
	_STAGE["root"] = scratchRoot if on else None


def _tableColumns(table):
	"""Every column of a table, in the order the database reports them."""
	ds = system.db.runPrepQuery("SELECT * FROM %s WHERE 1 = 0" % sqlName(table),
	                            [], launchpad.oee.db())
	return [unicode(ds.getUnderlyingDataset().getColumnName(c))
	        for c in range(ds.getUnderlyingDataset().getColumnCount())]


def mirrorFromSql(scratchRoot):
	"""Copy every OEE record out of SQL and into a file store at scratchRoot.

	This is what makes the comparison honest: the file implementation is asked
	about the SAME rows the SQL implementation is, rather than about a second
	generated history that would differ in every random number.
	"""
	from java.io import File
	_deleteTree(File(scratchRoot))
	for sub in ("", "/" + HOUR, "/" + SHIFT):
		File(scratchRoot + sub).mkdirs()
	counts = {}
	for table in (HOUR, SHIFT, RATE, CONFIG):
		columns = _tableColumns(table)
		# Every column TWICE: once as itself, once as SQLite's own idea of
		# what it is holding.
		#
		# The OEE schema declares target_production_count INTEGER and the
		# generator writes 7091.25 into it. SQLite keeps the REAL - typeof()
		# says so - but the JDBC driver honours the DECLARED type and hands
		# back 7091, while SUM() is computed inside SQLite and keeps the .25.
		# So the shipped standard build already disagrees with itself: a row
		# read shows 7091 and a rollup of that one row shows 7091.25.
		#
		# It matters here because a mirror that reads through the driver
		# truncates, and then reports the file implementation as wrong for
		# holding the number that was actually written. Ask for the REAL where
		# SQLite says the value is one.
		select = []
		for c in columns:
			select.append(c)
			select.append('typeof("%s") AS "%s__ty"' % (c, c))
			select.append('CAST("%s" AS REAL) AS "%s__real"' % (c, c))
		ds = system.db.runPrepQuery("SELECT %s FROM %s"
		                            % (", ".join(select), sqlName(table)),
		                            [], launchpad.oee.db())
		rows = []
		for r in range(ds.getRowCount()):
			row = []
			for i, c in enumerate(columns):
				value = ds.getValueAt(r, i * 3)
				kind = ds.getValueAt(r, i * 3 + 1)
				if unicode(kind) == u"real":
					value = ds.getValueAt(r, i * 3 + 2)
				row.append(value)
			rows.append(row)
		counts[table] = len(rows)
		_forceFile(True, scratchRoot)
		try:
			for row in rows:
				_fileInsert(table, dict(zip(columns, row)))
		finally:
			_forceFile(False)
	return counts


def _comparable(value):
	"""A dataset as something two answers can be ==.

	Reduced to plain values because the two implementations build theirs from
	different primitives - a Date out of the JDBC driver on one side and out of
	system.date.fromMillis on the other - and the comparison is about the
	ANSWER, not the types it arrived in. Floats are rounded because a sum of
	the same numbers in a different order is the same number to any reader and
	not always to the last bit.
	"""
	from java.util import Date as JDate
	rows = []
	for r in range(value.getRowCount()):
		row = []
		for c in range(value.getColumnCount()):
			v = value.getValueAt(r, c)
			if isinstance(v, JDate):
				v = long(system.date.toMillis(v))
			elif isinstance(v, (int, long, float)):
				# By VALUE, not by type. SUM over an INTEGER column comes back
				# from the driver as a Long and out of the file implementation
				# as a float; 4879 and 4879.0 are the same answer and a gate
				# that calls them a difference is a gate nobody will read.
				v = round(float(v), 4)
			elif v is not None and not isinstance(v, (unicode, str)):
				v = unicode(v)
			row.append(v)
		rows.append(row)
	return rows


def parity(lineName="", tagFolder=None, hours=720):
	"""Ask both implementations the same seven questions over the same records.

	Returns {ok, comparable, results:[{name, match, rows, sqlSample, ...}]}.
	The two answers are included only where they differ - a matching pair is a
	line saying so, not a wall of numbers.
	"""
	if _noDatabase():
		return {"ok": True, "comparable": False,
		        "note": (u"this gateway has no database, so there is no SQL "
		                 u"implementation to compare against - the file store "
		                 u"is the only one that runs here")}

	folder = tagFolder or launchpad.oee.BASE_TAG_FOLDER
	# The window STOPS at the top of the current hour. The demo is running
	# while this runs: the live engine rewrites the hour in progress on every
	# tick, so a window that includes it compares two reads of a moving row and
	# reports a difference that is only elapsed time. Seen on a 24-hour window,
	# where it looked exactly like a boundary bug in the file implementation.
	now = system.date.now()
	end = system.date.setTime(now, system.date.getHour24(now), 0, 0)
	start = system.date.addHours(end, -int(hours))
	scratch = root() + ".parity"
	mirrored = mirrorFromSql(scratch)

	cases = [
		("dailyStats", lambda: dailyStats(lineName, folder, start, end)),
		("hourlyStats", lambda: hourlyStats(lineName, folder, start, end)),
		("hourlyStatsAverage",
		 lambda: hourlyStatsAverage(lineName, folder, start, end)),
		("shiftStats", lambda: shiftStats(lineName, folder, start, end)),
		("selectRates", lambda: selectRates()),
		("rateData", lambda: rateData("default")),
	]
	# topProduction needs a real line name; "" means every line to the others
	lines = launchpad.oee.getLineNames(folder)
	if lines:
		first = lineName or lines[0]
		cases.append(("topProduction",
		              lambda: topProduction(first, start, end)))

	results, allOk = [], True
	try:
		for name, fn in cases:
			_forceFile(False)
			left = _comparable(fn())
			_forceFile(True, scratch)
			try:
				right = _comparable(fn())
			finally:
				_forceFile(False)
			match = left == right
			allOk = allOk and match
			row = {"name": name, "match": match, "rows": len(left)}
			if not match:
				row["sqlRows"] = len(left)
				row["fileRows"] = len(right)
				for i in range(min(len(left), len(right))):
					if left[i] != right[i]:
						row["firstDifference"] = {
							"row": i,
							"sql": unicode(left[i])[:400],
							"file": unicode(right[i])[:400]}
						break
			results.append(row)
	finally:
		from java.io import File
		_forceFile(False)
		_deleteTree(File(scratch))

	return {"ok": allOk, "comparable": True, "mirrored": mirrored,
	        "window": {"hours": hours, "line": lineName or "(all)",
	                   "tagFolder": folder,
	                   "endsAt": system.date.format(end, "yyyy-MM-dd HH:mm:ss"),
	                   "note": "ends at the top of the hour - the hour in "
	                           "progress is still being written"},
	        "results": results}
