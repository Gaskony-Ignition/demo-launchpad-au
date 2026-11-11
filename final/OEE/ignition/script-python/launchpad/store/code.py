"""
launchpad.store - the OEE records, in SQL or, on Edge, as JSON files in the gateway data directory.
Callers name the table, the match and the columns; the SQL is generated from that.
"""

from java.lang import System as JSystem
from java.lang import Throwable as JThrowable
from java.util import Date as JDate
from java.util.concurrent.locks import ReentrantLock

LOG = system.util.getLogger("launchpad.store")

# table id -> (SQL table name, timestamp column that partitions it, or None)
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

# Two threads rewriting one day file lose whichever finishes first.
_LOCK = ReentrantLock()

# Set only by the parity check, to run the file implementation on a gateway with a database.
_FORCE_FILE = {"on": False}


def sqlName(table):
	"""Return the SQL table name for a table id."""
	return TABLES[table][0]


def _noDatabase():
	if _FORCE_FILE["on"]:
		return True
	return not launchpad.edition.hasDatabase()


def root():
	"""Return the file store directory, under the gateway's working directory."""
	return JSystem.getProperty("user.dir") + "/data/launchpad-oee"


# While a rebuild is staging, paths are built from here instead of root().
_STAGE = {"root": None}


def _stagedRoot():
	return _STAGE["root"] or root()


def _millis(value):
	if isinstance(value, JDate):
		return long(system.date.toMillis(value))
	return value


def _encode(row):
	"""Return the row with dates as epoch millis and Java numbers as Python ones."""
	# A BigDecimal or Integer passed straight to jsonEncode does not always come back the same.
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


# Timestamp columns per table; JSON returns a number where consumers want a Date.
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


# A match is a list of (column, operator, value); ISNULL finds the open shift row.
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
	"""Return the day files to search: one if the match pins the timestamp, else the newest three."""
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
	"""Return rows whose timestamp is in the window, inclusive at both ends."""
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


def insert(table, columns, values, tx=None):
	"""Add a row; `columns` and `values` are positional. `tx` is used by SQL only."""
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
	"""Add several rows from one flat list of values, every row's values end to end."""
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
	"""Change the row `match` finds (a list of (column, op, value)); no match is a no-op."""
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
	"""Append each value in `appends` ({column: value}) to a comma-separated TEXT column of the matched row."""
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
		# Cast both sides: a numeric-looking value can make the database add instead of concatenate.
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
	"""Delete every row of the table."""
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
	"""Return the number of rows in the table."""
	if _noDatabase():
		return len(_allRows(table))
	sql = "SELECT COUNT(*) FROM %s" % sqlName(table)
	if tx is not None:
		return system.db.runScalarQuery(sql, tx=tx)
	return system.db.runScalarQuery(sql, database=launchpad.oee.db())


def seedBegin():
	"""Start an all-or-nothing rebuild (SQL transaction or staging directory); return its handle."""
	if not _noDatabase():
		return system.db.beginTransaction(database=launchpad.oee.db(),
		                                  timeout=300000)
	from java.io import File
	stage = root() + ".rebuilding"
	_deleteTree(File(stage))
	for sub in ("", "/" + HOUR, "/" + SHIFT):
		File(stage + sub).mkdirs()
	for table in (CONFIG, RATE):
		rows = _read(_path(table))
		if rows:
			system.file.writeFile(stage + "/" + table + ".json",
			                      system.util.jsonEncode(rows, 0))
	_STAGE["root"] = stage
	return stage


def seedCommit(handle):
	"""Make the rebuild live: commit the transaction or swap the staging directory in."""
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
		old.renameTo(live)
		raise Exception("could not swap the rebuilt OEE store into place")
	_deleteTree(old)


def seedRollback(handle):
	"""Discard the rebuild and leave the live records untouched."""
	if not _noDatabase():
		system.db.rollbackTransaction(handle)
		return
	from java.io import File
	_STAGE["root"] = None
	_deleteTree(File(handle))


def seedClose(handle):
	"""Release the rebuild handle after commit or rollback."""
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


# The SQL schema seeds this row; lines without their own rate read 'default'.
DEFAULT_RATE = {"rate_name": "default", "uom": "units", "target_rate": 15,
                "interval": "minute"}


def ready():
	"""Return True if the store can hold records (file store: directories and default rate exist)."""
	from java.io import File
	if not _noDatabase():
		return True
	return (File(root() + "/" + SHIFT).exists()
	        and File(root() + "/" + HOUR).exists()
	        and bool(_read(_path(RATE))))


def ensure():
	"""Create the file store directories and default rate; does nothing on SQL."""
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


# Each read function returns its named query's columns in the same order and names.

def _num(v):
	return 0.0 if v is None else float(v)


def rowsAsJson(ds):
	"""Return a dataset as a list of dicts keyed by column name."""
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
	"""Return hour rows with `column` (hour_timestamp or day_timestamp) in the window."""
	# Files are partitioned by hour_timestamp, so a day_timestamp window reads a day wider each side.
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
	"""Return hour rollups averaged into days per line; same as Launchpad/Oee/DailyStats."""
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
	"""Return one row per line per hour; same as named query Launchpad/Oee/HourlyStats."""
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
	"""Return one row per line averaged over the window; same as Launchpad/Oee/HourlyStatsAverage."""
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
	"""Return shift rollups per line and shift; same as Launchpad/Oee/ShiftStats."""
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
	"""Return the line's hours ordered by smallest shortfall against target; same as Launchpad/Oee/TopProduction."""
	# Does not filter on tag_folder, matching the query.
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
	"""Return every rate definition by name; same as Launchpad/Oee/SelectRates."""
	if not _noDatabase():
		return _named("Launchpad/Oee/SelectRates", {})
	rows = sorted(_read(_path(RATE)),
	              key=lambda r: unicode(r.get("rate_name") or ""))
	return system.dataset.toDataSet(
		RATE_COLUMNS,
		[[r.get("rate_name"), r.get("uom"), r.get("target_rate"),
		  r.get("interval")] for r in rows])


def rateData(rateName):
	"""Return the named rate definition (zero rows if unknown); same as Launchpad/Oee/SelectRateData."""
	if not _noDatabase():
		return _named("Launchpad/Oee/SelectRateData", {"rate_name": rateName})
	out = []
	for r in _read(_path(RATE)):
		if r.get("rate_name") == rateName:
			out.append([r.get("rate_name"), r.get("uom"),
			            r.get("target_rate"), r.get("interval")])
	return system.dataset.toDataSet(RATE_COLUMNS, out)


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
	"""Copy every OEE record from SQL into a file store at scratchRoot; return row counts per table."""
	from java.io import File
	_deleteTree(File(scratchRoot))
	for sub in ("", "/" + HOUR, "/" + SHIFT):
		File(scratchRoot + sub).mkdirs()
	counts = {}
	for table in (HOUR, SHIFT, RATE, CONFIG):
		columns = _tableColumns(table)
		# SQLite keeps 7091.25 in an INTEGER column but the JDBC driver returns 7091,
		# so each column is also read as typeof() and CAST AS REAL.
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
	"""Reduce a dataset to plain values (dates as millis, numbers rounded) so two answers compare with ==."""
	from java.util import Date as JDate
	rows = []
	for r in range(value.getRowCount()):
		row = []
		for c in range(value.getColumnCount()):
			v = value.getValueAt(r, c)
			if isinstance(v, JDate):
				v = long(system.date.toMillis(v))
			elif isinstance(v, (int, long, float)):
				# Compare by value: SUM returns a Long from the driver and a float from the file store.
				v = round(float(v), 4)
			elif v is not None and not isinstance(v, (unicode, str)):
				v = unicode(v)
			row.append(v)
		rows.append(row)
	return rows


def parity(lineName="", tagFolder=None, hours=720):
	"""Run the read functions on SQL and on a mirrored file store; return {ok, comparable, results}."""
	if _noDatabase():
		return {"ok": True, "comparable": False,
		        "note": (u"this gateway has no database, so there is no SQL "
		                 u"implementation to compare against - the file store "
		                 u"is the only one that runs here")}

	folder = tagFolder or launchpad.oee.BASE_TAG_FOLDER
	# Stop at the top of the hour: the live engine rewrites the current hour every tick.
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
	# topProduction needs a real line name; "" means all lines to the others.
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
