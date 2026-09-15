"""
launchpad.store - the KPI dashboards, with or without a database.

The dashboard builder is a relational application: six tables, four of them
joined together to answer one question, and rows created with auto-increment
ids. On a standard gateway that is SQL through named queries. Ignition Edge has
no database connectivity of any kind - not a slower one, an absent one, and a
named query cannot run there at all - so the same six tables are kept as JSON in
the gateway's own data directory and the same eleven questions are answered
here.

Every function below IS its named query on a gateway that has one: it runs the
resource, so there is one copy of that SQL and it is the copy that shipped.
Only the no-database path is a second implementation, and it returns the same
columns in the same order under the same names, because a table bound to
column 7 does not check what column 7 is called.

## What is stored where

    data/launchpad-kpi/<table>.json      one file per table, whole

Not partitioned, unlike the OEE store: these tables are tens of rows, not
thousands, and every question joins across all of them.

## Ids

SQLite hands out auto-increment ids and the dashboard code depends on getting
one back (`getKey=True`) to attach widgets to a dashboard it has just made.
`_nextId` is that, over the rows the file holds - MAX + 1, which is what
AUTOINCREMENT does once rows exist and what a fresh table does from its seed.
"""

from java.lang import System as JSystem
from java.lang import Throwable as JThrowable
from java.util import Date as JDate
from java.util.concurrent.locks import ReentrantLock

LOG = system.util.getLogger("launchpad.store")

DASHBOARDS = "ex_lp_dashboards"
DASHBOARD_WIDGETS = "ex_lp_dashboard_widgets"
DASHBOARD_WIDGET_PARAMETERS = "ex_lp_dashboard_widget_parameters"
WIDGETS = "ex_lp_widgets"
WIDGET_PARAMETERS = "ex_lp_widget_parameters"
WIDGET_PARAMETER_TYPES = "ex_lp_widget_parameter_types"

TABLES = (DASHBOARDS, DASHBOARD_WIDGETS, DASHBOARD_WIDGET_PARAMETERS,
          WIDGETS, WIDGET_PARAMETERS, WIDGET_PARAMETER_TYPES)

# One writer at a time: the dashboard editor saves a dashboard, its widgets and
# their parameters in a run of calls, and a second session saving at the same
# moment would otherwise lose whichever finished first.
_LOCK = ReentrantLock()


def _noDatabase():
	return not launchpad.edition.hasDatabase()


def root():
	"""Where the file store lives.

	The gateway runs with its installation directory as the working directory
	on every platform and in the official container image, and no scripting
	function returns it, so this is the portable way to ask.
	"""
	return JSystem.getProperty("user.dir") + "/data/launchpad-kpi"


def _path(table):
	return root() + "/" + table + ".json"


def _read(table):
	path = _path(table)
	try:
		if not system.file.fileExists(path):
			return []
		text = system.file.readFileAsString(path, "UTF-8")
		return system.util.jsonDecode(text) if text else []
	except (JThrowable, Exception):
		import traceback
		LOG.warn("could not read %s - treating it as empty: %s"
		         % (path, traceback.format_exc()))
		return []


def _write(table, rows):
	system.file.writeFile(_path(table), system.util.jsonEncode(rows, 0))


def _nextId(rows):
	best = 0
	for r in rows:
		try:
			best = max(best, int(r.get("id") or 0))
		except (JThrowable, Exception):
			pass
	return best + 1


def _stamp():
	"""What CURRENT_TIMESTAMP writes, as text, so the two stores read alike."""
	return system.date.format(system.date.now(), "yyyy-MM-dd HH:mm:ss")


def ready():
	"""Is the store able to answer yet? The question `tablesPresent` asks."""
	if not _noDatabase():
		return True
	return bool(_read(WIDGETS))


def ensure():
	"""Make the store exist, seeded exactly as the SQL schema seeds itself.

	Creates nothing on a gateway with a database - that is
	launchpad.init.initDashboard's job, and its CREATE TABLE script carries the
	same rows. Never overwrites: the dashboards table gains rows as people
	build dashboards, and this runs on every setup.
	"""
	if not _noDatabase():
		return u"tables are the database's"
	from java.io import File
	File(root()).mkdirs()
	made = []
	_LOCK.lock()
	try:
		# The seeded dashboards carry tag-history parameters, and a history path
		# names the historian provider, the driver (this gateway's system name)
		# and the tag provider - all three of which differ per gateway, and all
		# three of which differ again on Edge. The SQL script substitutes the
		# same placeholder for the same reason.
		prefix = launchpad.init.historyPrefix()
		for table in TABLES:
			if _read(table):
				continue
			rows = []
			for r in SEED.get(table, []):
				row = dict(r)
				for k, v in row.items():
					if isinstance(v, basestring) and "{HIST}" in v:
						row[k] = v.replace("{HIST}", prefix)
				rows.append(row)
			_write(table, rows)
			made.append("%s=%d" % (table, len(rows)))
	finally:
		_LOCK.unlock()
	if not made:
		return u"file store already seeded at %s" % root()
	return u"file store seeded at %s: %s" % (root(), ", ".join(made))


# ---------------------------------------------------------------------------
# the eleven questions the dashboard code asks
# ---------------------------------------------------------------------------


def _named(path, params, getKey=False):
	if getKey:
		return system.db.runNamedQuery(path=path, parameters=params, getKey=True)
	return system.db.runNamedQuery(path=path, parameters=params)


def _index(rows, key="id"):
	out = {}
	for r in rows:
		out[r.get(key)] = r
	return out


DASHBOARD_COLUMNS = ["id", "name", "url", "icon", "username", "grid",
                     "cell_size", "grid_rows", "row_gutter_size", "grid_cols",
                     "col_gutter_size"]


def dashboards():
	"""Every dashboard. Launchpad/Dashboard/Get."""
	if not _noDatabase():
		return _named("Launchpad/Dashboard/Get", {})
	rows = []
	for d in _read(DASHBOARDS):
		# COALESCE(d.icon, '') - a dashboard saved without one must not put a
		# null into a column the editor binds to a text field.
		rows.append([d.get("id"), d.get("name"), d.get("url"),
		             d.get("icon") or "", d.get("username"), d.get("grid"),
		             d.get("cell_size"), d.get("grid_rows"),
		             d.get("row_gutter_size"), d.get("grid_cols"),
		             d.get("col_gutter_size")])
	return system.dataset.toDataSet(DASHBOARD_COLUMNS, rows)


WIDGET_GET_COLUMNS = [
	"id", "name", "widget_id", "widget", "path", "parameter_id",
	"parameter_name", "parameter", "parameter_value", "parameter_type_id",
	"parameter_type_path", "parameter_configuration", "position",
]


def dashboardWidgets(dashboardId):
	"""One dashboard's widgets and their parameters.
	Launchpad/Dashboard/Widget/Get.

	The join that matters: a widget's parameters come from the WIDGET TYPE, and
	the value is the dashboard's own override where it has one and the type's
	default where it does not - which is the COALESCE in the query. A LEFT JOIN
	on the parameters means a widget type with no parameters still returns its
	row, and dropping that would make such a widget vanish from a dashboard it
	is on.
	"""
	if not _noDatabase():
		return _named("Launchpad/Dashboard/Widget/Get",
		              {"dashboard": dashboardId})

	widgets = _index(_read(WIDGETS))
	params = _read(WIDGET_PARAMETERS)
	types = _index(_read(WIDGET_PARAMETER_TYPES))
	overrides = {}
	for dp in _read(DASHBOARD_WIDGET_PARAMETERS):
		overrides[(dp.get("dashboard_widget_id"), dp.get("parameter_id"))] = dp

	rows = []
	mine = [dw for dw in _read(DASHBOARD_WIDGETS)
	        if dw.get("dashboard_id") == dashboardId]
	mine.sort(key=lambda dw: int(dw.get("id") or 0))
	for dw in mine:
		w = widgets.get(dw.get("widget_id"))
		if w is None:
			# an inner JOIN in the query: a widget row pointing at a type that
			# no longer exists is not shown at all
			continue
		mineParams = [p for p in params if p.get("widget_id") == dw.get("widget_id")]
		mineParams.sort(key=lambda p: (unicode(p.get("parameter") or ""),
		                               int(p.get("id") or 0)))
		if not mineParams:
			mineParams = [None]
		for p in mineParams:
			if p is None:
				rows.append([dw.get("id"), dw.get("name"), w.get("id"),
				             w.get("name"), w.get("path"), None, None, None,
				             None, None, None, None, dw.get("position")])
				continue
			t = types.get(p.get("parameter_type_id")) or {}
			override = overrides.get((dw.get("id"), p.get("id")))
			value = (override.get("parameter_value") if override is not None
			         else p.get("default_value"))
			rows.append([dw.get("id"), dw.get("name"), w.get("id"),
			             w.get("name"), w.get("path"), p.get("id"),
			             p.get("parameter_name"), p.get("parameter"), value,
			             t.get("id"), t.get("path"), p.get("configuration"),
			             dw.get("position")])
	return system.dataset.toDataSet(WIDGET_GET_COLUMNS, rows)


INSTALLED_WIDGET_COLUMNS = [
	"id", "widget", "path", "parameter_id", "parameter_name", "parameter",
	"parameter_value", "parameter_type_id", "parameter_type_path",
	"parameter_configuration",
]


def installedWidgets():
	"""Every widget type and its parameters, for the palette.
	Launchpad/Dashboard/Widget/Installed Widgets."""
	if not _noDatabase():
		return _named("Launchpad/Dashboard/Widget/Installed Widgets", {})

	params = _read(WIDGET_PARAMETERS)
	types = _index(_read(WIDGET_PARAMETER_TYPES))
	widgets = sorted(_read(WIDGETS),
	                 key=lambda w: (unicode(w.get("name") or ""),
	                                int(w.get("id") or 0)))
	rows = []
	for w in widgets:
		mine = [p for p in params if p.get("widget_id") == w.get("id")]
		mine.sort(key=lambda p: (unicode(p.get("parameter") or ""),
		                         int(p.get("id") or 0)))
		if not mine:
			rows.append([w.get("id"), w.get("name"), w.get("path"),
			             None, None, None, None, None, None, None])
			continue
		for p in mine:
			t = types.get(p.get("parameter_type_id")) or {}
			rows.append([w.get("id"), w.get("name"), w.get("path"),
			             p.get("id"), p.get("parameter_name"),
			             p.get("parameter"), p.get("default_value"),
			             t.get("id"), t.get("path"), p.get("configuration")])
	return system.dataset.toDataSet(INSTALLED_WIDGET_COLUMNS, rows)


def maxDashboardId():
	"""COALESCE(MAX(id), 0). Launchpad/Dashboard/Get URL."""
	if not _noDatabase():
		return _named("Launchpad/Dashboard/Get URL", {})
	best = 0
	for d in _read(DASHBOARDS):
		best = max(best, int(d.get("id") or 0))
	return best


def dashboardIdForUrl(url):
	"""The dashboard using this url, or None. Launchpad/Dashboard/Check URL."""
	if not _noDatabase():
		return _named("Launchpad/Dashboard/Check URL", {"url": url})
	for d in _read(DASHBOARDS):
		if d.get("url") == url:
			return d.get("id")
	return None


def lastModified(dashboardId):
	"""Launchpad/Dashboard/Last Modified."""
	if not _noDatabase():
		return _named("Launchpad/Dashboard/Last Modified", {"id": dashboardId})
	for d in _read(DASHBOARDS):
		if d.get("id") == dashboardId:
			return d.get("last_modified")
	return None


def dbCheck():
	"""Can the store answer at all? Launchpad/Dashboard/DB Check."""
	if not _noDatabase():
		return _named("Launchpad/Dashboard/DB Check", {})
	return 1 if ready() else None


def addDashboard(fields):
	"""Create a dashboard and return its new id. Launchpad/Dashboard/Add."""
	if not _noDatabase():
		return _named("Launchpad/Dashboard/Add", fields, getKey=True)
	_LOCK.lock()
	try:
		rows = _read(DASHBOARDS)
		row = dict(fields)
		row["id"] = _nextId(rows)
		row["last_modified"] = _stamp()
		rows.append(row)
		_write(DASHBOARDS, rows)
		return row["id"]
	finally:
		_LOCK.unlock()


def editDashboard(fields):
	"""Launchpad/Dashboard/Edit. `fields` carries the id."""
	if not _noDatabase():
		return _named("Launchpad/Dashboard/Edit", fields)
	_LOCK.lock()
	try:
		rows = _read(DASHBOARDS)
		for r in rows:
			if r.get("id") == fields.get("id"):
				r.update(fields)
				r["last_modified"] = _stamp()
				_write(DASHBOARDS, rows)
				return 1
		return 0
	finally:
		_LOCK.unlock()


def deleteDashboard(dashboardId):
	"""Launchpad/Dashboard/Delete.

	The schema declares ON DELETE CASCADE from widgets to dashboards, so the
	file store has to do by hand what the database does by declaration - and
	the widgets' own parameter overrides with them, or the next dashboard to be
	handed a recycled widget id inherits somebody else's settings.
	"""
	if not _noDatabase():
		return _named("Launchpad/Dashboard/Delete", {"id": dashboardId})
	_LOCK.lock()
	try:
		widgets = _read(DASHBOARD_WIDGETS)
		doomed = set([w.get("id") for w in widgets
		              if w.get("dashboard_id") == dashboardId])
		_write(DASHBOARD_WIDGETS,
		       [w for w in widgets if w.get("dashboard_id") != dashboardId])
		_write(DASHBOARD_WIDGET_PARAMETERS,
		       [p for p in _read(DASHBOARD_WIDGET_PARAMETERS)
		        if p.get("dashboard_widget_id") not in doomed])
		_write(DASHBOARDS, [d for d in _read(DASHBOARDS)
		                    if d.get("id") != dashboardId])
		return 1
	finally:
		_LOCK.unlock()


def addWidget(fields):
	"""Put a widget on a dashboard, returning its new id.
	Launchpad/Dashboard/Widget/Add."""
	if not _noDatabase():
		return _named("Launchpad/Dashboard/Widget/Add", fields, getKey=True)
	_LOCK.lock()
	try:
		rows = _read(DASHBOARD_WIDGETS)
		row = dict(fields)
		row["id"] = _nextId(rows)
		rows.append(row)
		_write(DASHBOARD_WIDGETS, rows)
		return row["id"]
	finally:
		_LOCK.unlock()


def editWidget(fields):
	"""Launchpad/Dashboard/Widget/Edit."""
	if not _noDatabase():
		return _named("Launchpad/Dashboard/Widget/Edit", fields)
	_LOCK.lock()
	try:
		rows = _read(DASHBOARD_WIDGETS)
		for r in rows:
			if r.get("id") == fields.get("id"):
				r.update(fields)
				_write(DASHBOARD_WIDGETS, rows)
				return 1
		return 0
	finally:
		_LOCK.unlock()


def deleteWidget(widgetId):
	"""Launchpad/Dashboard/Widget/Delete, and its parameter overrides."""
	if not _noDatabase():
		return _named("Launchpad/Dashboard/Widget/Delete", {"id": widgetId})
	_LOCK.lock()
	try:
		_write(DASHBOARD_WIDGETS, [w for w in _read(DASHBOARD_WIDGETS)
		                           if w.get("id") != widgetId])
		_write(DASHBOARD_WIDGET_PARAMETERS,
		       [p for p in _read(DASHBOARD_WIDGET_PARAMETERS)
		        if p.get("dashboard_widget_id") != widgetId])
		return 1
	finally:
		_LOCK.unlock()


def setWidgetParameter(widgetId, parameterId, value, add):
	"""Launchpad/Dashboard/Widget/Parameter/Add or .../Edit.

	`add` is the caller's own idea of which it is doing. The file store does
	not need to be told - it writes the override either way - but honouring the
	distinction keeps the two implementations doing the same thing, including
	when the caller is wrong about it.
	"""
	params = {"widget_id": widgetId, "parameter_id": parameterId,
	          "parameter_value": value}
	if not _noDatabase():
		return _named("Launchpad/Dashboard/Widget/Parameter/%s"
		              % ("Add" if add else "Edit"), params)
	_LOCK.lock()
	try:
		rows = _read(DASHBOARD_WIDGET_PARAMETERS)
		for r in rows:
			if (r.get("dashboard_widget_id") == widgetId
					and r.get("parameter_id") == parameterId):
				r["parameter_value"] = value
				_write(DASHBOARD_WIDGET_PARAMETERS, rows)
				return 1
		rows.append({"id": _nextId(rows), "dashboard_widget_id": widgetId,
		             "parameter_id": parameterId, "parameter_value": value})
		_write(DASHBOARD_WIDGET_PARAMETERS, rows)
		return 1
	finally:
		_LOCK.unlock()


# ---------------------------------------------------------------------------
# the seed
# ---------------------------------------------------------------------------
# GENERATED from the CREATE TABLE script in launchpad.init.initDashboard by
# tools/kpi_seed.py, which package.sh runs as a check. Do not edit by hand: the
# SQL script is the authority, and a second copy that drifts is a gateway whose
# widget palette is missing whatever was added to the other one.

SEED = {
	"ex_lp_dashboard_widget_parameters": [
		{"id": 26, "dashboard_widget_id": 22, "parameter_id": 12, "parameter_value": '{HIST}dailyproduction'},
		{"id": 27, "dashboard_widget_id": 22, "parameter_id": 13, "parameter_value": '{HIST}dailyproductionexpected'},
		{"id": 77, "dashboard_widget_id": 22, "parameter_id": 16, "parameter_value": 'Maximum'},
		{"id": 28, "dashboard_widget_id": 23, "parameter_id": 4, "parameter_value": '{HIST}dailyproduction'},
		{"id": 29, "dashboard_widget_id": 23, "parameter_id": 5, "parameter_value": '{HIST}dailyproductionexpected'},
		{"id": 30, "dashboard_widget_id": 23, "parameter_id": 6, "parameter_value": 'Hourly Case Analysis'},
		{"id": 78, "dashboard_widget_id": 23, "parameter_id": 15, "parameter_value": 'Maximum'},
		{"id": 31, "dashboard_widget_id": 24, "parameter_id": 9, "parameter_value": '[Launchpad]KPI/Notepad'},
		{"id": 32, "dashboard_widget_id": 25, "parameter_id": 7, "parameter_value": '[Launchpad]KPI/DailyProduction'},
		{"id": 33, "dashboard_widget_id": 26, "parameter_id": 11, "parameter_value": '[Launchpad]KPI/Lines'},
		{"id": 34, "dashboard_widget_id": 27, "parameter_id": 3, "parameter_value": '{HIST}ambienttemperature'},
		{"id": 79, "dashboard_widget_id": 27, "parameter_id": 14, "parameter_value": 'Average'},
		{"id": 35, "dashboard_widget_id": 28, "parameter_id": 3, "parameter_value": '{HIST}ambienthumidity'},
		{"id": 80, "dashboard_widget_id": 28, "parameter_id": 14, "parameter_value": 'Average'},
		{"id": 36, "dashboard_widget_id": 29, "parameter_id": 3, "parameter_value": '{HIST}workinprocess'},
		{"id": 81, "dashboard_widget_id": 29, "parameter_id": 14, "parameter_value": 'Average'},
		{"id": 37, "dashboard_widget_id": 30, "parameter_id": 3, "parameter_value": '{HIST}buffer'},
		{"id": 82, "dashboard_widget_id": 30, "parameter_id": 14, "parameter_value": 'Average'},
		{"id": 38, "dashboard_widget_id": 31, "parameter_id": 3, "parameter_value": '{HIST}cycletime'},
		{"id": 83, "dashboard_widget_id": 31, "parameter_id": 14, "parameter_value": 'Average'},
		{"id": 39, "dashboard_widget_id": 32, "parameter_id": 3, "parameter_value": '{HIST}setuptime'},
		{"id": 84, "dashboard_widget_id": 32, "parameter_id": 14, "parameter_value": 'Average'},
		{"id": 40, "dashboard_widget_id": 33, "parameter_id": 3, "parameter_value": '{HIST}airpressure'},
		{"id": 85, "dashboard_widget_id": 33, "parameter_id": 14, "parameter_value": 'Average'},
		{"id": 41, "dashboard_widget_id": 34, "parameter_id": 3, "parameter_value": '{HIST}energyyesterday'},
		{"id": 86, "dashboard_widget_id": 34, "parameter_id": 14, "parameter_value": 'Average'},
		{"id": 42, "dashboard_widget_id": 35, "parameter_id": 4, "parameter_value": '{HIST}lines/line1/productionrate'},
		{"id": 43, "dashboard_widget_id": 35, "parameter_id": 5, "parameter_value": ''},
		{"id": 44, "dashboard_widget_id": 35, "parameter_id": 6, "parameter_value": 'Line 1 Prod Rate'},
		{"id": 87, "dashboard_widget_id": 35, "parameter_id": 15, "parameter_value": 'Maximum'},
		{"id": 45, "dashboard_widget_id": 36, "parameter_id": 1, "parameter_value": '[Launchpad]KPI/Lines/Line1/BatteryCapacity'},
		{"id": 46, "dashboard_widget_id": 37, "parameter_id": 8, "parameter_value": '[Launchpad]KPI/Lines/Line1/CoilTemperature'},
		{"id": 47, "dashboard_widget_id": 38, "parameter_id": 4, "parameter_value": '{HIST}lines/line1/batterycapacity'},
		{"id": 48, "dashboard_widget_id": 38, "parameter_id": 5, "parameter_value": '{HIST}lines/line1/productionrate'},
		{"id": 49, "dashboard_widget_id": 38, "parameter_id": 6, "parameter_value": 'Line 1 Battery vs Prod Rate'},
		{"id": 88, "dashboard_widget_id": 38, "parameter_id": 15, "parameter_value": 'Maximum'},
		{"id": 50, "dashboard_widget_id": 39, "parameter_id": 2, "parameter_value": '[Launchpad]KPI/Lines/Line1/OilPressure'},
		{"id": 51, "dashboard_widget_id": 40, "parameter_id": 2, "parameter_value": '[Launchpad]KPI/Lines/Line1/CoilTemperature'},
		{"id": 52, "dashboard_widget_id": 41, "parameter_id": 2, "parameter_value": '[Launchpad]KPI/Lines/Line1/ProductionRate'},
		{"id": 53, "dashboard_widget_id": 42, "parameter_id": 2, "parameter_value": '[Launchpad]KPI/Lines/Line1/BatteryCapacity'},
		{"id": 54, "dashboard_widget_id": 43, "parameter_id": 2, "parameter_value": '[Launchpad]KPI/Lines/Line1/ReserveOilPressure'},
		{"id": 55, "dashboard_widget_id": 44, "parameter_id": 2, "parameter_value": '[Launchpad]KPI/Lines/Line1/Reserve2Pressure'},
		{"id": 56, "dashboard_widget_id": 45, "parameter_id": 7, "parameter_value": '[Launchpad]KPI/Lines/Line1/ProductionRate'},
		{"id": 57, "dashboard_widget_id": 46, "parameter_id": 4, "parameter_value": '{HIST}lines/line2/batterycapacity'},
		{"id": 58, "dashboard_widget_id": 46, "parameter_id": 5, "parameter_value": '{HIST}lines/line2/productionrate'},
		{"id": 59, "dashboard_widget_id": 46, "parameter_id": 6, "parameter_value": 'Line 2 Battery vs Prod Rate'},
		{"id": 89, "dashboard_widget_id": 46, "parameter_id": 15, "parameter_value": 'Maximum'},
		{"id": 60, "dashboard_widget_id": 47, "parameter_id": 2, "parameter_value": '[Launchpad]KPI/Lines/Line2/OilPressure'},
		{"id": 61, "dashboard_widget_id": 48, "parameter_id": 2, "parameter_value": '[Launchpad]KPI/Lines/Line2/CoilTemperature'},
		{"id": 62, "dashboard_widget_id": 49, "parameter_id": 2, "parameter_value": '[Launchpad]KPI/Lines/Line2/ProductionRate'},
		{"id": 63, "dashboard_widget_id": 50, "parameter_id": 2, "parameter_value": '[Launchpad]KPI/Lines/Line2/BatteryCapacity'},
		{"id": 64, "dashboard_widget_id": 51, "parameter_id": 2, "parameter_value": '[Launchpad]KPI/Lines/Line2/ReserveOilPressure'},
		{"id": 65, "dashboard_widget_id": 52, "parameter_id": 2, "parameter_value": '[Launchpad]KPI/Lines/Line2/Reserve2Pressure'},
		{"id": 66, "dashboard_widget_id": 53, "parameter_id": 7, "parameter_value": '[Launchpad]KPI/Lines/Line2/ProductionRate'},
		{"id": 67, "dashboard_widget_id": 54, "parameter_id": 4, "parameter_value": '{HIST}lines/line3/batterycapacity'},
		{"id": 68, "dashboard_widget_id": 54, "parameter_id": 5, "parameter_value": '{HIST}lines/line3/productionrate'},
		{"id": 69, "dashboard_widget_id": 54, "parameter_id": 6, "parameter_value": 'Line 3 Battery vs Prod Rate'},
		{"id": 90, "dashboard_widget_id": 54, "parameter_id": 15, "parameter_value": 'Maximum'},
		{"id": 70, "dashboard_widget_id": 55, "parameter_id": 2, "parameter_value": '[Launchpad]KPI/Lines/Line3/OilPressure'},
		{"id": 71, "dashboard_widget_id": 56, "parameter_id": 2, "parameter_value": '[Launchpad]KPI/Lines/Line3/CoilTemperature'},
		{"id": 72, "dashboard_widget_id": 57, "parameter_id": 2, "parameter_value": '[Launchpad]KPI/Lines/Line3/ProductionRate'},
		{"id": 73, "dashboard_widget_id": 58, "parameter_id": 2, "parameter_value": '[Launchpad]KPI/Lines/Line3/BatteryCapacity'},
		{"id": 74, "dashboard_widget_id": 59, "parameter_id": 2, "parameter_value": '[Launchpad]KPI/Lines/Line3/OilPressure'},
		{"id": 75, "dashboard_widget_id": 60, "parameter_id": 2, "parameter_value": '[Launchpad]KPI/Lines/Line3/Reserve2Pressure'},
		{"id": 76, "dashboard_widget_id": 61, "parameter_id": 7, "parameter_value": '[Launchpad]KPI/Lines/Line3/ProductionRate'},
		{"id": 91, "dashboard_widget_id": 62, "parameter_id": 10, "parameter_value": '[Launchpad]KPI/Lines/Line1/OilPressure'},
	],
	"ex_lp_dashboard_widgets": [
		{"id": 22, "dashboard_id": 1, "widget_id": 10, "name": 'Production vs Expected', "position": '1,15,8,20'},
		{"id": 23, "dashboard_id": 1, "widget_id": 4, "name": 'Hourly Case Analysis', "position": '1,13,20,27'},
		{"id": 24, "dashboard_id": 1, "widget_id": 7, "name": 'Notepad', "position": '1,6,1,8'},
		{"id": 25, "dashboard_id": 1, "widget_id": 5, "name": 'Daily Production', "position": '6,11,1,8'},
		{"id": 26, "dashboard_id": 1, "widget_id": 9, "name": 'Progress KPI', "position": '13,27,20,27'},
		{"id": 27, "dashboard_id": 1, "widget_id": 3, "name": 'Energy Yesterday', "position": '15,21,8,11'},
		{"id": 28, "dashboard_id": 1, "widget_id": 3, "name": 'Real Power', "position": '15,21,11,14'},
		{"id": 29, "dashboard_id": 1, "widget_id": 3, "name": 'Setpoint', "position": '15,21,14,17'},
		{"id": 30, "dashboard_id": 1, "widget_id": 3, "name": 'Reactive', "position": '15,21,17,20'},
		{"id": 31, "dashboard_id": 1, "widget_id": 3, "name": 'PoaIrradiance', "position": '21,27,8,11'},
		{"id": 32, "dashboard_id": 1, "widget_id": 3, "name": 'LmpPrice', "position": '21,27,11,14'},
		{"id": 33, "dashboard_id": 1, "widget_id": 3, "name": 'PerformanceMtd', "position": '21,27,14,17'},
		{"id": 34, "dashboard_id": 1, "widget_id": 3, "name": 'Power Factor', "position": '21,27,17,20'},
		{"id": 35, "dashboard_id": 1, "widget_id": 4, "name": 'Line 1 Prod Rate', "position": '11,20,1,8'},
		{"id": 36, "dashboard_id": 1, "widget_id": 1, "name": 'Simple Gauge Battery', "position": '20,27,5,8'},
		{"id": 37, "dashboard_id": 1, "widget_id": 6, "name": 'Moving Analog Indicator Coil Temp', "position": '20,25,1,5'},
		{"id": 38, "dashboard_id": 2, "widget_id": 4, "name": 'Line 1 Battery vs Prod', "position": '1,14,1,10'},
		{"id": 39, "dashboard_id": 2, "widget_id": 2, "name": 'L1 Oil Press', "position": '14,19,1,4'},
		{"id": 40, "dashboard_id": 2, "widget_id": 2, "name": 'L1 Coil Temp', "position": '14,19,4,7'},
		{"id": 41, "dashboard_id": 2, "widget_id": 2, "name": 'L1 Prod Rate', "position": '14,19,7,10'},
		{"id": 42, "dashboard_id": 2, "widget_id": 2, "name": 'L1 Battery', "position": '19,24,1,4'},
		{"id": 43, "dashboard_id": 2, "widget_id": 2, "name": 'L1 Reserve Oil Press', "position": '19,24,4,7'},
		{"id": 44, "dashboard_id": 2, "widget_id": 2, "name": 'L1 Reserve 2 Press', "position": '19,24,7,10'},
		{"id": 45, "dashboard_id": 2, "widget_id": 5, "name": 'Daily Production L1', "position": '24,30,1,10'},
		{"id": 46, "dashboard_id": 2, "widget_id": 4, "name": 'Line 2 Battery vs Prod', "position": '1,14,11,20'},
		{"id": 47, "dashboard_id": 2, "widget_id": 2, "name": 'Line2 Oil Press', "position": '14,19,11,14'},
		{"id": 48, "dashboard_id": 2, "widget_id": 2, "name": 'Line2 Coil Temp', "position": '14,19,14,17'},
		{"id": 49, "dashboard_id": 2, "widget_id": 2, "name": 'L2 Prod Rate', "position": '14,19,17,20'},
		{"id": 50, "dashboard_id": 2, "widget_id": 2, "name": 'Line2 Battery', "position": '19,24,11,14'},
		{"id": 51, "dashboard_id": 2, "widget_id": 2, "name": 'Line 2 Oil Press', "position": '19,24,14,17'},
		{"id": 52, "dashboard_id": 2, "widget_id": 2, "name": 'Line2 Reserve 2 Press', "position": '19,24,17,20'},
		{"id": 53, "dashboard_id": 2, "widget_id": 5, "name": 'Daily Production Line2', "position": '24,30,11,20'},
		{"id": 54, "dashboard_id": 2, "widget_id": 4, "name": 'Line 3 Battery vs Prod', "position": '1,14,21,30'},
		{"id": 55, "dashboard_id": 2, "widget_id": 2, "name": 'Line3 Oil Press', "position": '14,19,21,24'},
		{"id": 56, "dashboard_id": 2, "widget_id": 2, "name": 'Line3 Coil Temp', "position": '14,19,24,27'},
		{"id": 57, "dashboard_id": 2, "widget_id": 2, "name": 'Line3 Prod Rate', "position": '14,19,27,30'},
		{"id": 58, "dashboard_id": 2, "widget_id": 2, "name": 'Line3 Battery Capacity', "position": '19,24,21,24'},
		{"id": 59, "dashboard_id": 2, "widget_id": 2, "name": 'Line 3 Oil Press', "position": '19,24,24,27'},
		{"id": 60, "dashboard_id": 2, "widget_id": 2, "name": 'Line3 Reserve 2 Press', "position": '19,24,27,30'},
		{"id": 61, "dashboard_id": 2, "widget_id": 5, "name": 'Daily Production Line3', "position": '24,30,21,30'},
		{"id": 62, "dashboard_id": 1, "widget_id": 8, "name": 'Progress Bar Oil Press L1', "position": '25,27,1,5'},
	],
	"ex_lp_dashboards": [
		{"id": 1, "name": 'Dashboard 1', "icon": 'dashboard', "url": 'dash1', "username": 'Anonymous', "grid": 'stretch', "cell_size": 100, "grid_rows": 26, "row_gutter_size": 12, "grid_cols": 26, "col_gutter_size": 12, "last_modified": '2025-06-05 20:40:13'},
		{"id": 2, "name": 'Dashboard 2', "icon": 'dashboard', "url": 'dash2', "username": 'Anonymous', "grid": 'stretch', "cell_size": 100, "grid_rows": 29, "row_gutter_size": 6, "grid_cols": 29, "col_gutter_size": 6, "last_modified": '2025-06-05 20:45:49'},
	],
	"ex_lp_widget_parameter_types": [
		{"id": 1, "type": 'Tag Realtime', "path": 'Launchpad/Kpi/EmbeddedViews/Dashboard/Configuration/Parameter Types/Tag Realtime'},
		{"id": 2, "type": 'Tag History', "path": 'Launchpad/Kpi/EmbeddedViews/Dashboard/Configuration/Parameter Types/Tag History'},
		{"id": 3, "type": 'String', "path": 'Launchpad/Kpi/EmbeddedViews/Dashboard/Configuration/Parameter Types/String'},
		{"id": 4, "type": 'Dropdown', "path": 'Launchpad/Kpi/EmbeddedViews/Dashboard/Configuration/Parameter Types/Dropdown'},
	],
	"ex_lp_widget_parameters": [
		{"id": 1, "widget_id": 1, "parameter_name": 'Tag', "parameter": 'path', "parameter_type_id": 1, "default_value": '', "configuration": None},
		{"id": 2, "widget_id": 2, "parameter_name": 'Tag', "parameter": 'path', "parameter_type_id": 1, "default_value": '', "configuration": None},
		{"id": 3, "widget_id": 3, "parameter_name": 'Tag', "parameter": 'path', "parameter_type_id": 2, "default_value": '', "configuration": None},
		{"id": 4, "widget_id": 4, "parameter_name": 'Tag 1', "parameter": 'path1', "parameter_type_id": 2, "default_value": '', "configuration": None},
		{"id": 5, "widget_id": 4, "parameter_name": 'Tag 2', "parameter": 'path2', "parameter_type_id": 2, "default_value": '', "configuration": None},
		{"id": 6, "widget_id": 4, "parameter_name": 'Title', "parameter": 'title', "parameter_type_id": 3, "default_value": '', "configuration": None},
		{"id": 7, "widget_id": 5, "parameter_name": 'Tag', "parameter": 'path', "parameter_type_id": 1, "default_value": '', "configuration": None},
		{"id": 8, "widget_id": 6, "parameter_name": 'Tag', "parameter": 'path', "parameter_type_id": 1, "default_value": '', "configuration": None},
		{"id": 9, "widget_id": 7, "parameter_name": 'Tag', "parameter": 'path', "parameter_type_id": 1, "default_value": '', "configuration": None},
		{"id": 10, "widget_id": 8, "parameter_name": 'Tag', "parameter": 'path', "parameter_type_id": 1, "default_value": '', "configuration": None},
		{"id": 11, "widget_id": 9, "parameter_name": 'Folder Path', "parameter": 'folderPath', "parameter_type_id": 1, "default_value": '', "configuration": None},
		{"id": 12, "widget_id": 10, "parameter_name": 'Tag 1', "parameter": 'path1', "parameter_type_id": 2, "default_value": '', "configuration": None},
		{"id": 13, "widget_id": 10, "parameter_name": 'Tag 2', "parameter": 'path2', "parameter_type_id": 2, "default_value": '', "configuration": None},
		{"id": 14, "widget_id": 3, "parameter_name": 'Aggregation Mode', "parameter": 'aggMode', "parameter_type_id": 4, "default_value": 'Average', "configuration": '{"options": [   {     "value": "Average",     "label": "Average"   },   {     "value": "MinMax",     "label": "MinMax"   },   {     "value": "LastValue",     "label": "LastValue"   },   {     "value": "SimpleAverage",     "label": "SimpleAverage"   },   {     "value": "Sum",     "label": "Sum"   },   {     "value": "Minimum",     "label": "Minimum"   },   {     "value": "Maximum",     "label": "Maximum"   },   {     "value": "DurationOn",     "label": "DurationOn"   },   {     "value": "DurationOff",     "label": "DurationOff"   },   {     "value": "CountOn",     "label": "CountOn"   },   {     "value": "CountOff",     "label": "CountOff"   },   {     "value": "Count",     "label": "Count"   },   {     "value": "Range",     "label": "Range"   },   {     "value": "Variance",     "label": "Variance"   },   {     "value": "StdDev",     "label": "StdDev"   },   {     "value": "PctGood",     "label": "PctGood"   },   {     "value": "PctBad",     "label": "PctBad"   } ]}'},
		{"id": 15, "widget_id": 4, "parameter_name": 'Aggregation Mode', "parameter": 'aggMode', "parameter_type_id": 4, "default_value": 'Average', "configuration": '{"options": [   {     "value": "Average",     "label": "Average"   },   {     "value": "MinMax",     "label": "MinMax"   },   {     "value": "LastValue",     "label": "LastValue"   },   {     "value": "SimpleAverage",     "label": "SimpleAverage"   },   {     "value": "Sum",     "label": "Sum"   },   {     "value": "Minimum",     "label": "Minimum"   },   {     "value": "Maximum",     "label": "Maximum"   },   {     "value": "DurationOn",     "label": "DurationOn"   },   {     "value": "DurationOff",     "label": "DurationOff"   },   {     "value": "CountOn",     "label": "CountOn"   },   {     "value": "CountOff",     "label": "CountOff"   },   {     "value": "Count",     "label": "Count"   },   {     "value": "Range",     "label": "Range"   },   {     "value": "Variance",     "label": "Variance"   },   {     "value": "StdDev",     "label": "StdDev"   },   {     "value": "PctGood",     "label": "PctGood"   },   {     "value": "PctBad",     "label": "PctBad"   } ]}'},
		{"id": 16, "widget_id": 10, "parameter_name": 'Aggregation Mode', "parameter": 'aggMode', "parameter_type_id": 4, "default_value": 'Average', "configuration": '{"options": [   {     "value": "Average",     "label": "Average"   },   {     "value": "MinMax",     "label": "MinMax"   },   {     "value": "LastValue",     "label": "LastValue"   },   {     "value": "SimpleAverage",     "label": "SimpleAverage"   },   {     "value": "Sum",     "label": "Sum"   },   {     "value": "Minimum",     "label": "Minimum"   },   {     "value": "Maximum",     "label": "Maximum"   },   {     "value": "DurationOn",     "label": "DurationOn"   },   {     "value": "DurationOff",     "label": "DurationOff"   },   {     "value": "CountOn",     "label": "CountOn"   },   {     "value": "CountOff",     "label": "CountOff"   },   {     "value": "Count",     "label": "Count"   },   {     "value": "Range",     "label": "Range"   },   {     "value": "Variance",     "label": "Variance"   },   {     "value": "StdDev",     "label": "StdDev"   },   {     "value": "PctGood",     "label": "PctGood"   },   {     "value": "PctBad",     "label": "PctBad"   } ]}'},
	],
	"ex_lp_widgets": [
		{"id": 1, "name": 'Simple Gauge', "path": 'Launchpad/Kpi/Components/SimpleGauge'},
		{"id": 2, "name": 'Value', "path": 'Launchpad/Kpi/Components/ValueUnitLabel'},
		{"id": 3, "name": 'Sparkline', "path": 'Launchpad/Kpi/Components/Sparkline'},
		{"id": 4, "name": 'Line Chart', "path": 'Launchpad/Kpi/Components/LineChart'},
		{"id": 5, "name": 'Daily Production', "path": 'Launchpad/Kpi/Components/DailyProduction'},
		{"id": 6, "name": 'Moving Analog Indicator', "path": 'Launchpad/Kpi/Components/MovingAnalogIndicator'},
		{"id": 7, "name": 'Notepad', "path": 'Launchpad/Kpi/Components/Notepad'},
		{"id": 8, "name": 'Progress Bar', "path": 'Launchpad/Kpi/Components/ProgressBar'},
		{"id": 9, "name": 'Progress KPI', "path": 'Launchpad/Kpi/Components/ProgressKpi'},
		{"id": 10, "name": 'Bar Chart', "path": 'Launchpad/Kpi/Components/BarChart'},
	],
}
