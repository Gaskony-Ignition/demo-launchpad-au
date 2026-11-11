DATABASE_NAME = "KPI"

def db():
	"""Return the database connection name: the launchpad.database global if set, else KPI."""
	return system.util.getGlobals().get("launchpad.database") or DATABASE_NAME

def initDashboard():
	"""Create and seed the dashboard tables (or ensure the store on an edition with no database)."""
	query = """
CREATE TABLE ex_lp_widget_parameter_types (
  id integer PRIMARY KEY AUTOINCREMENT,
  type text NOT NULL,
  path text NOT NULL
);
INSERT INTO ex_lp_widget_parameter_types VALUES(1,'Tag Realtime','Launchpad/Kpi/EmbeddedViews/Dashboard/Configuration/Parameter Types/Tag Realtime');
INSERT INTO ex_lp_widget_parameter_types VALUES(2,'Tag History','Launchpad/Kpi/EmbeddedViews/Dashboard/Configuration/Parameter Types/Tag History');
INSERT INTO ex_lp_widget_parameter_types VALUES(3,'String','Launchpad/Kpi/EmbeddedViews/Dashboard/Configuration/Parameter Types/String');
INSERT INTO ex_lp_widget_parameter_types VALUES(4,'Dropdown','Launchpad/Kpi/EmbeddedViews/Dashboard/Configuration/Parameter Types/Dropdown');

CREATE TABLE ex_lp_widgets (
  id integer PRIMARY KEY AUTOINCREMENT,
  name text NOT NULL,
  path text NOT NULL
);
INSERT INTO ex_lp_widgets VALUES(1,'Simple Gauge','Launchpad/Kpi/Components/SimpleGauge');
INSERT INTO ex_lp_widgets VALUES(2,'Value','Launchpad/Kpi/Components/ValueUnitLabel');
INSERT INTO ex_lp_widgets VALUES(3,'Sparkline','Launchpad/Kpi/Components/Sparkline');
INSERT INTO ex_lp_widgets VALUES(4,'Line Chart','Launchpad/Kpi/Components/LineChart');
INSERT INTO ex_lp_widgets VALUES(5,'Daily Production','Launchpad/Kpi/Components/DailyProduction');
INSERT INTO ex_lp_widgets VALUES(6,'Moving Analog Indicator','Launchpad/Kpi/Components/MovingAnalogIndicator');
INSERT INTO ex_lp_widgets VALUES(7,'Notepad','Launchpad/Kpi/Components/Notepad');
INSERT INTO ex_lp_widgets VALUES(8,'Progress Bar','Launchpad/Kpi/Components/ProgressBar');
INSERT INTO ex_lp_widgets VALUES(9,'Progress KPI','Launchpad/Kpi/Components/ProgressKpi');
INSERT INTO ex_lp_widgets VALUES(10,'Bar Chart','Launchpad/Kpi/Components/BarChart');

CREATE TABLE ex_lp_widget_parameters (
  id integer PRIMARY KEY AUTOINCREMENT,
  widget_id integer NOT NULL,
  parameter_name text NOT NULL,
  parameter text NOT NULL,
  parameter_type_id integer NOT NULL,
  default_value text,
  configuration text,
  FOREIGN KEY (widget_id) REFERENCES ex_lp_widgets (id) ON DELETE CASCADE,
  FOREIGN KEY (parameter_type_id) REFERENCES ex_lp_widget_parameter_types (id)
);
INSERT INTO ex_lp_widget_parameters VALUES(1,1,'Tag','path',1,'',NULL);
INSERT INTO ex_lp_widget_parameters VALUES(2,2,'Tag','path',1,'',NULL);
INSERT INTO ex_lp_widget_parameters VALUES(3,3,'Tag','path',2,'',NULL);
INSERT INTO ex_lp_widget_parameters VALUES(4,4,'Tag 1','path1',2,'',NULL);
INSERT INTO ex_lp_widget_parameters VALUES(5,4,'Tag 2','path2',2,'',NULL);
INSERT INTO ex_lp_widget_parameters VALUES(6,4,'Title','title',3,'',NULL);
INSERT INTO ex_lp_widget_parameters VALUES(7,5,'Tag','path',1,'',NULL);
INSERT INTO ex_lp_widget_parameters VALUES(8,6,'Tag','path',1,'',NULL);
INSERT INTO ex_lp_widget_parameters VALUES(9,7,'Tag','path',1,'',NULL);
INSERT INTO ex_lp_widget_parameters VALUES(10,8,'Tag','path',1,'',NULL);
INSERT INTO ex_lp_widget_parameters VALUES(11,9,'Folder Path','folderPath',1,'',NULL);
INSERT INTO ex_lp_widget_parameters VALUES(12,10,'Tag 1','path1',2,'',NULL);
INSERT INTO ex_lp_widget_parameters VALUES(13,10,'Tag 2','path2',2,'',NULL);
INSERT INTO ex_lp_widget_parameters VALUES(14,3,'Aggregation Mode','aggMode',4,'Average','{\"options\": [   {     "value": "Average",     "label": "Average"   },   {     "value": "MinMax",     "label": "MinMax"   },   {     "value": "LastValue",     "label": "LastValue"   },   {     "value": "SimpleAverage",     "label": "SimpleAverage"   },   {     "value": "Sum",     "label": "Sum"   },   {     "value": "Minimum",     "label": "Minimum"   },   {     "value": "Maximum",     "label": "Maximum"   },   {     "value": "DurationOn",     "label": "DurationOn"   },   {     "value": "DurationOff",     "label": "DurationOff"   },   {     "value": "CountOn",     "label": "CountOn"   },   {     "value": "CountOff",     "label": "CountOff"   },   {     "value": "Count",     "label": "Count"   },   {     "value": "Range",     "label": "Range"   },   {     "value": "Variance",     "label": "Variance"   },   {     "value": "StdDev",     "label": "StdDev"   },   {     "value": "PctGood",     "label": "PctGood"   },   {     "value": "PctBad",     "label": "PctBad"   } ]}');
INSERT INTO ex_lp_widget_parameters VALUES(15,4,'Aggregation Mode','aggMode',4,'Average','{\"options\": [   {     "value": "Average",     "label": "Average"   },   {     "value": "MinMax",     "label": "MinMax"   },   {     "value": "LastValue",     "label": "LastValue"   },   {     "value": "SimpleAverage",     "label": "SimpleAverage"   },   {     "value": "Sum",     "label": "Sum"   },   {     "value": "Minimum",     "label": "Minimum"   },   {     "value": "Maximum",     "label": "Maximum"   },   {     "value": "DurationOn",     "label": "DurationOn"   },   {     "value": "DurationOff",     "label": "DurationOff"   },   {     "value": "CountOn",     "label": "CountOn"   },   {     "value": "CountOff",     "label": "CountOff"   },   {     "value": "Count",     "label": "Count"   },   {     "value": "Range",     "label": "Range"   },   {     "value": "Variance",     "label": "Variance"   },   {     "value": "StdDev",     "label": "StdDev"   },   {     "value": "PctGood",     "label": "PctGood"   },   {     "value": "PctBad",     "label": "PctBad"   } ]}');
INSERT INTO ex_lp_widget_parameters VALUES(16,10,'Aggregation Mode','aggMode',4,'Average','{\"options\": [   {     "value": "Average",     "label": "Average"   },   {     "value": "MinMax",     "label": "MinMax"   },   {     "value": "LastValue",     "label": "LastValue"   },   {     "value": "SimpleAverage",     "label": "SimpleAverage"   },   {     "value": "Sum",     "label": "Sum"   },   {     "value": "Minimum",     "label": "Minimum"   },   {     "value": "Maximum",     "label": "Maximum"   },   {     "value": "DurationOn",     "label": "DurationOn"   },   {     "value": "DurationOff",     "label": "DurationOff"   },   {     "value": "CountOn",     "label": "CountOn"   },   {     "value": "CountOff",     "label": "CountOff"   },   {     "value": "Count",     "label": "Count"   },   {     "value": "Range",     "label": "Range"   },   {     "value": "Variance",     "label": "Variance"   },   {     "value": "StdDev",     "label": "StdDev"   },   {     "value": "PctGood",     "label": "PctGood"   },   {     "value": "PctBad",     "label": "PctBad"   } ]}');

CREATE TABLE ex_lp_dashboard_widgets (
  id integer PRIMARY KEY AUTOINCREMENT,
  dashboard_id integer NOT NULL,
  widget_id integer NOT NULL,
  name text NOT NULL,
  position text NOT NULL,
  FOREIGN KEY (dashboard_id) REFERENCES ex_lp_dashboards (id) ON DELETE CASCADE,
  FOREIGN KEY (widget_id) REFERENCES ex_lp_widgets (id)
);
INSERT INTO ex_lp_dashboard_widgets VALUES(22,1,10,'Production vs Expected','1,15,8,20');
INSERT INTO ex_lp_dashboard_widgets VALUES(23,1,4,'Hourly Case Analysis','1,13,20,27');
INSERT INTO ex_lp_dashboard_widgets VALUES(24,1,7,'Notepad','1,6,1,8');
INSERT INTO ex_lp_dashboard_widgets VALUES(25,1,5,'Daily Production','6,11,1,8');
INSERT INTO ex_lp_dashboard_widgets VALUES(26,1,9,'Progress KPI','13,27,20,27');
INSERT INTO ex_lp_dashboard_widgets VALUES(27,1,3,'Energy Yesterday','15,21,8,11');
INSERT INTO ex_lp_dashboard_widgets VALUES(28,1,3,'Real Power','15,21,11,14');
INSERT INTO ex_lp_dashboard_widgets VALUES(29,1,3,'Setpoint','15,21,14,17');
INSERT INTO ex_lp_dashboard_widgets VALUES(30,1,3,'Reactive','15,21,17,20');
INSERT INTO ex_lp_dashboard_widgets VALUES(31,1,3,'PoaIrradiance','21,27,8,11');
INSERT INTO ex_lp_dashboard_widgets VALUES(32,1,3,'LmpPrice','21,27,11,14');
INSERT INTO ex_lp_dashboard_widgets VALUES(33,1,3,'PerformanceMtd','21,27,14,17');
INSERT INTO ex_lp_dashboard_widgets VALUES(34,1,3,'Power Factor','21,27,17,20');
INSERT INTO ex_lp_dashboard_widgets VALUES(35,1,4,'Line 1 Prod Rate','11,20,1,8');
INSERT INTO ex_lp_dashboard_widgets VALUES(36,1,1,'Simple Gauge Battery','20,27,5,8');
INSERT INTO ex_lp_dashboard_widgets VALUES(37,1,6,'Moving Analog Indicator Coil Temp','20,25,1,5');
INSERT INTO ex_lp_dashboard_widgets VALUES(38,2,4,'Line 1 Battery vs Prod','1,14,1,10');
INSERT INTO ex_lp_dashboard_widgets VALUES(39,2,2,'L1 Oil Press','14,19,1,4');
INSERT INTO ex_lp_dashboard_widgets VALUES(40,2,2,'L1 Coil Temp','14,19,4,7');
INSERT INTO ex_lp_dashboard_widgets VALUES(41,2,2,'L1 Prod Rate','14,19,7,10');
INSERT INTO ex_lp_dashboard_widgets VALUES(42,2,2,'L1 Battery','19,24,1,4');
INSERT INTO ex_lp_dashboard_widgets VALUES(43,2,2,'L1 Reserve Oil Press','19,24,4,7');
INSERT INTO ex_lp_dashboard_widgets VALUES(44,2,2,'L1 Reserve 2 Press','19,24,7,10');
INSERT INTO ex_lp_dashboard_widgets VALUES(45,2,5,'Daily Production L1','24,30,1,10');
INSERT INTO ex_lp_dashboard_widgets VALUES(46,2,4,'Line 2 Battery vs Prod','1,14,11,20');
INSERT INTO ex_lp_dashboard_widgets VALUES(47,2,2,'Line2 Oil Press','14,19,11,14');
INSERT INTO ex_lp_dashboard_widgets VALUES(48,2,2,'Line2 Coil Temp','14,19,14,17');
INSERT INTO ex_lp_dashboard_widgets VALUES(49,2,2,'L2 Prod Rate','14,19,17,20');
INSERT INTO ex_lp_dashboard_widgets VALUES(50,2,2,'Line2 Battery','19,24,11,14');
INSERT INTO ex_lp_dashboard_widgets VALUES(51,2,2,'Line 2 Oil Press','19,24,14,17');
INSERT INTO ex_lp_dashboard_widgets VALUES(52,2,2,'Line2 Reserve 2 Press','19,24,17,20');
INSERT INTO ex_lp_dashboard_widgets VALUES(53,2,5,'Daily Production Line2','24,30,11,20');
INSERT INTO ex_lp_dashboard_widgets VALUES(54,2,4,'Line 3 Battery vs Prod','1,14,21,30');
INSERT INTO ex_lp_dashboard_widgets VALUES(55,2,2,'Line3 Oil Press','14,19,21,24');
INSERT INTO ex_lp_dashboard_widgets VALUES(56,2,2,'Line3 Coil Temp','14,19,24,27');
INSERT INTO ex_lp_dashboard_widgets VALUES(57,2,2,'Line3 Prod Rate','14,19,27,30');
INSERT INTO ex_lp_dashboard_widgets VALUES(58,2,2,'Line3 Battery Capacity','19,24,21,24');
INSERT INTO ex_lp_dashboard_widgets VALUES(59,2,2,'Line 3 Oil Press','19,24,24,27');
INSERT INTO ex_lp_dashboard_widgets VALUES(60,2,2,'Line3 Reserve 2 Press','19,24,27,30');
INSERT INTO ex_lp_dashboard_widgets VALUES(61,2,5,'Daily Production Line3','24,30,21,30');
INSERT INTO ex_lp_dashboard_widgets VALUES(62,1,8,'Progress Bar Oil Press L1','25,27,1,5');

CREATE TABLE ex_lp_dashboard_widget_parameters (
  id integer PRIMARY KEY AUTOINCREMENT,
  dashboard_widget_id integer NOT NULL,
  parameter_id integer NOT NULL,
  parameter_value text,
  FOREIGN KEY (dashboard_widget_id) REFERENCES ex_lp_dashboard_widgets (id) ON DELETE CASCADE,
  FOREIGN KEY (parameter_id) REFERENCES ex_lp_widget_parameters (id) ON DELETE CASCADE
);
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(26,22,12,'{HIST}dailyproduction');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(27,22,13,'{HIST}dailyproductionexpected');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(77,22,16,'Maximum');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(28,23,4,'{HIST}dailyproduction');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(29,23,5,'{HIST}dailyproductionexpected');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(30,23,6,'Hourly Case Analysis');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(78,23,15,'Maximum');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(31,24,9,'[Launchpad]KPI/Notepad');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(32,25,7,'[Launchpad]KPI/DailyProduction');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(33,26,11,'[Launchpad]KPI/Lines');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(34,27,3,'{HIST}ambienttemperature');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(79,27,14,'Average');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(35,28,3,'{HIST}ambienthumidity');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(80,28,14,'Average');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(36,29,3,'{HIST}workinprocess');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(81,29,14,'Average');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(37,30,3,'{HIST}buffer');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(82,30,14,'Average');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(38,31,3,'{HIST}cycletime');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(83,31,14,'Average');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(39,32,3,'{HIST}setuptime');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(84,32,14,'Average');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(40,33,3,'{HIST}airpressure');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(85,33,14,'Average');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(41,34,3,'{HIST}energyyesterday');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(86,34,14,'Average');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(42,35,4,'{HIST}lines/line1/productionrate');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(43,35,5,'');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(44,35,6,'Line 1 Prod Rate');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(87,35,15,'Maximum');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(45,36,1,'[Launchpad]KPI/Lines/Line1/BatteryCapacity');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(46,37,8,'[Launchpad]KPI/Lines/Line1/CoilTemperature');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(47,38,4,'{HIST}lines/line1/batterycapacity');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(48,38,5,'{HIST}lines/line1/productionrate');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(49,38,6,'Line 1 Battery vs Prod Rate');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(88,38,15,'Maximum');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(50,39,2,'[Launchpad]KPI/Lines/Line1/OilPressure');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(51,40,2,'[Launchpad]KPI/Lines/Line1/CoilTemperature');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(52,41,2,'[Launchpad]KPI/Lines/Line1/ProductionRate');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(53,42,2,'[Launchpad]KPI/Lines/Line1/BatteryCapacity');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(54,43,2,'[Launchpad]KPI/Lines/Line1/ReserveOilPressure');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(55,44,2,'[Launchpad]KPI/Lines/Line1/Reserve2Pressure');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(56,45,7,'[Launchpad]KPI/Lines/Line1/ProductionRate');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(57,46,4,'{HIST}lines/line2/batterycapacity');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(58,46,5,'{HIST}lines/line2/productionrate');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(59,46,6,'Line 2 Battery vs Prod Rate');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(89,46,15,'Maximum');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(60,47,2,'[Launchpad]KPI/Lines/Line2/OilPressure');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(61,48,2,'[Launchpad]KPI/Lines/Line2/CoilTemperature');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(62,49,2,'[Launchpad]KPI/Lines/Line2/ProductionRate');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(63,50,2,'[Launchpad]KPI/Lines/Line2/BatteryCapacity');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(64,51,2,'[Launchpad]KPI/Lines/Line2/ReserveOilPressure');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(65,52,2,'[Launchpad]KPI/Lines/Line2/Reserve2Pressure');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(66,53,7,'[Launchpad]KPI/Lines/Line2/ProductionRate');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(67,54,4,'{HIST}lines/line3/batterycapacity');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(68,54,5,'{HIST}lines/line3/productionrate');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(69,54,6,'Line 3 Battery vs Prod Rate');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(90,54,15,'Maximum');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(70,55,2,'[Launchpad]KPI/Lines/Line3/OilPressure');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(71,56,2,'[Launchpad]KPI/Lines/Line3/CoilTemperature');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(72,57,2,'[Launchpad]KPI/Lines/Line3/ProductionRate');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(73,58,2,'[Launchpad]KPI/Lines/Line3/BatteryCapacity');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(74,59,2,'[Launchpad]KPI/Lines/Line3/OilPressure');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(75,60,2,'[Launchpad]KPI/Lines/Line3/Reserve2Pressure');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(76,61,7,'[Launchpad]KPI/Lines/Line3/ProductionRate');
INSERT INTO ex_lp_dashboard_widget_parameters VALUES(91,62,10,'[Launchpad]KPI/Lines/Line1/OilPressure');

CREATE TABLE ex_lp_dashboards (
  id integer PRIMARY KEY AUTOINCREMENT,
  name text NOT NULL,
  icon text DEFAULT NULL,
  url text NOT NULL,
  username text DEFAULT NULL,
  grid text NOT NULL DEFAULT 'fixed',
  cell_size integer NOT NULL DEFAULT 100,
  grid_rows integer NOT NULL DEFAULT 10,
  row_gutter_size integer NOT NULL DEFAULT 6,
  grid_cols integer NOT NULL DEFAULT 10,
  col_gutter_size integer NOT NULL DEFAULT 6,
  last_modified integer NOT NULL
);
INSERT INTO ex_lp_dashboards VALUES(1,'Dashboard 1','dashboard','dash1','Anonymous','stretch',100,26,12,26,12,'2025-06-05 20:40:13');
INSERT INTO ex_lp_dashboards VALUES(2,'Dashboard 2','dashboard','dash2','Anonymous','stretch',100,29,6,29,6,'2025-06-05 20:45:49');
"""
	if not launchpad.edition.hasDatabase():
		# No schema here: the dashboards are files, and the store holds the same rows.
		return launchpad.store.ensure()
	# History paths must name this gateway's system name as the driver.
	query = query.replace("{HIST}", launchpad.init.historyPrefix())
	system.db.runUpdateQuery(query, database=db())


def historyPrefix():
	"""Return the history path prefix for the dashboards' tag-history parameters."""
	# Provider, driver and tag provider all differ on Edge; a wrong one draws nothing, silently.
	sysName = system.tag.readBlocking(
		["[System]Gateway/SystemName"])[0].value.lower()
	if launchpad.edition.isEdge():
		return "histprov:%s:/drv:%s:%s:/tag:kpi/" % (
			launchpad.edition.historian(), sysName, launchpad.setup.PROVIDER)
	return "histprov:launchpad:/drv:%s:launchpad:/tag:kpi/" % sysName

def _driverIds():
	"""Return (system name, sqlth_drv ids for this gateway)."""
	# The historian keeps old rows when the system name changes; only the current ids are read.
	sysName = system.tag.readBlocking(["[System]Gateway/SystemName"])[0].value
	rows = system.db.runPrepQuery(
		"SELECT id FROM sqlth_drv WHERE lower(name) = ?", [sysName.lower()], database=db())
	return sysName, [r["id"] for r in rows]

def _partitions(drvIds):
	"""Return this gateway's data partitions as [(name, startMs, endMs)]."""
	# Names are sqlt_data_<drvid>_<yyyy>_<mm>; read them from sqlth_partitions, never compose one.
	if not drvIds:
		return []
	rows = system.db.runQuery(
		"SELECT pname, drvid, start_time, end_time FROM sqlth_partitions",
		database=db())
	return [(r["pname"], r["start_time"], r["end_time"])
		for r in rows if r["drvid"] in drvIds]

def _partitionFor(tsMs, parts):
	"""Return the name of the partition covering tsMs, or None."""
	for name, start, end in parts:
		if start <= tsMs < end:
			return name
	return None

def _liveTagIds(drvIds):
	"""Return (tagid, tagpath, datatype) for the kpi tags of the current gateway."""
	if not drvIds:
		return {}
	marks = ",".join(["?"] * len(drvIds))
	# Concatenated, not %-formatted: the literal 'kpi/%' wildcard would read as a format spec.
	rows = system.db.runPrepQuery(
		"SELECT te.id AS id, te.tagpath AS tagpath, te.datatype AS datatype "
		"FROM sqlth_te te JOIN sqlth_scinfo sc ON te.scid = sc.id "
		"WHERE te.tagpath LIKE 'kpi/%' AND te.retired IS NULL "
		"AND sc.drvid IN (" + marks + ")", list(drvIds), database=db())
	return [(r["id"], r["tagpath"], r["datatype"]) for r in rows]

# Lowercase sqlth_te paths that are not sensors, so the generic sine band would misrepresent them.
_SHAPES = {
	"kpi/dailyproduction": "ramp",
	"kpi/dailyproductionexpected": "flat",
}


def registeredTagCount():
	"""Return how many of this project's tags the historian has registered."""
	# A tag registers after its first value; seeding before all do locks in a partial backfill.
	try:
		if not launchpad.edition.hasDatabase():
			return len(historisedTags())
		drvIds = _driverIds()[1]
		return len(_liveTagIds(drvIds))
	except:
		return 0


def historisedTags():
	"""Return (path, isInteger) for every KPI tag configured to record history."""
	base = "[%s]KPI" % launchpad.setup.PROVIDER
	out = []
	for node in system.tag.browse(base, {"recursive": True}).getResults():
		path = unicode(node["fullPath"])
		# Atomic tags only: a UDT instance has no value to write and stalls storeDataPoints.
		if unicode(node["tagType"]) != "AtomicTag":
			continue
		cfg = system.tag.getConfiguration(path, False)
		if not cfg:
			continue
		props = cfg[0]
		if not props.get("historyEnabled"):
			continue
		dt = unicode(props.get("dataType") or "")
		out.append((path, dt.startswith("Int")))
	return out


def baseValue(path, shape, attempts=10):
	"""Return the live value to centre a tag's generated history on, waiting for a non-zero one for flat and ramp shapes."""
	import time
	needsReal = shape in ("flat", "ramp")
	for attempt in range(attempts):
		v = system.tag.readBlocking([path])[0].value
		if v is not None and not (needsReal and not v):
			return v
		if attempt < attempts - 1:
			time.sleep(2)
	return system.tag.readBlocking([path])[0].value


def sampleValue(path, base, engHigh, tsMs, amp, shape):
	"""Return one generated sample at tsMs: a daily ramp, a flat target, or a sine band around base."""
	import math, random
	if shape == "ramp" and engHigh:
		midnight = system.date.toMillis(
			system.date.midnight(system.date.fromMillis(tsMs)))
		return float(engHigh) * (tsMs - midnight) / 86400000.0
	if shape == "flat":
		return base
	phase = (tsMs / 3600000.0) * (math.pi / 12.0)
	return base + amp * math.sin(phase) + random.uniform(-amp * 0.35, amp * 0.35)


def historyRowsSince(since):
	"""Return how many history samples this project's tags have recorded since `since`, via system.historian."""
	end = system.date.now()
	total = 0
	for path, _isInt in historisedTags():
		try:
			total += system.historian.queryRawPoints(
				paths=[path], startTime=since, endTime=end).getRowCount()
		except:
			pass
	return total


def backfillEdge(hours=48, step=15, force=False):
	"""Seed KPI tag history through system.historian on a gateway with no database."""
	# system.tag.storeTagHistory accepts the call against Edge's historian but stores nothing.
	import random
	random.seed(7)
	tags = historisedTags()
	if not tags:
		return {"rows": 0, "tags": 0,
		        "error": "no KPI tag on this gateway is recording history yet - "
		                 "let the historian register them, then retry"}
	nowMs = system.date.toMillis(system.date.now())
	stepMs = step * 60 * 1000
	count = hours * 60 / step
	startMs = nowMs - count * stepMs
	stamps = [int(startMs + i * stepMs) for i in range(count)]

	if not force:
		# Probe the old end of the window: only a backfill writes there, live recording fills the recent end.
		try:
			probe = system.historian.queryRawPoints(
				paths=[tags[0][0]],
				startTime=system.date.fromMillis(startMs),
				endTime=system.date.fromMillis(int(startMs + 2 * stepMs)))
			if probe.getRowCount():
				return {"rows": 0, "tags": len(tags), "tagsSeeded": 0,
				        "tagsSkipped": len(tags),
				        "note": "already seeded - pass force to redo it"}
		except:
			pass

	total, skipped, skippedPaths = 0, 0, []
	# Wait once for the set to publish; per-tag waits would multiply the delay.
	import time
	for _attempt in range(10):
		if any([v.value is not None
		        for v in system.tag.readBlocking([t[0] for t in tags])]):
			break
		time.sleep(2)

	for path, isInt in tags:
		leaf = path.split("]")[-1].lower()
		shape = _SHAPES.get(leaf)
		base = baseValue(path, shape, attempts=(10 if shape else 1))
		if base is None or isinstance(base, basestring):
			skipped += 1
			skippedPaths.append(path)
			continue
		base = float(base)
		if base == 0.0:
			base = 1.0
		amp = abs(base) * 0.12
		engHigh = None
		if shape == "ramp":
			engHigh = system.tag.readBlocking([path + ".EngHigh"])[0].value
			if not engHigh:
				shape = None

		values, quals, times = [], [], []
		for ts in stamps:
			v = sampleValue(path, base, engHigh, ts, amp, shape)
			values.append(int(round(v)) if isInt else v)
			quals.append(192)
			times.append(system.date.fromMillis(ts))
		chunk = 500
		for i in range(0, len(values), chunk):
			n = len(values[i:i + chunk])
			system.historian.storeDataPoints(
				paths=[path] * n, values=values[i:i + chunk],
				qualities=quals[i:i + chunk], timestamps=times[i:i + chunk])
			total += n
	out = {"rows": total, "tags": len(tags), "historian":
	       launchpad.edition.historian(), "tagsSeeded": len(tags) - skipped,
	       "tagsSkipped": skipped, "tagsSkippedPaths": skippedPaths}
	return out


def backfill(hours=48, step=15, force=False):
	"""Seed KPI tag history into the historian's partition tables; returns a summary dict."""
	import math, random
	if not launchpad.edition.hasDatabase():
		return backfillEdge(hours, step, force)
	random.seed(7)
	sysName, drvIds = _driverIds()
	tags = _liveTagIds(drvIds)
	parts = _partitions(drvIds)
	now = system.date.now()
	nowMs = system.date.toMillis(now)
	stepMs = step * 60 * 1000
	count = hours * 60 / step
	startMs = nowMs - count * stepMs

	# Samples can only go where a partition exists; count the ones outside any.
	buckets = {}
	unpartitioned = 0
	for i in range(count):
		ts = int(startMs + i * stepMs)
		p = _partitionFor(ts, parts)
		if p is None:
			unpartitioned += 1
		else:
			buckets.setdefault(p, []).append(ts)
	if not buckets:
		return {"rows": 0, "gateway": sysName, "tags": len(tags),
			"error": "no history partition covers the requested window - "
				 "let the historian record for a minute, then retry"}

	if force:
		# Drop old samples so a re-seed does not mix two scales in one series.
		ids = [t[0] for t in tags]
		if ids:
			marks = ",".join(["?"] * len(ids))
			for p in buckets:
				system.db.runPrepUpdate(
					"DELETE FROM %s WHERE tagid IN (%s)" % (p, marks), ids, database=db())

	total = 0
	skipped = 0
	skippedPaths = []
	for tagid, path, datatype in tags:
		# datatype 0 = integer, 1 = float; an int sample in floatvalue leaves intvalue NULL (plots as 0).
		isInt = (datatype == 0)
		shape = _SHAPES.get(path.lower())
		base = baseValue("[Launchpad]" + path, shape)
		if base is None or isinstance(base, basestring):
			skipped += 1
			skippedPaths.append(path)
			continue
		base = float(base)
		if base == 0.0:
			base = 1.0
		amp = abs(base) * 0.12
		# dailyproduction ramps to EngHigh over the day; dailyproductionexpected is a constant.
		engHigh = None
		if shape == "ramp":
			engHigh = system.tag.readBlocking(["[Launchpad]" + path + ".EngHigh"])[0].value
			if not engHigh:
				shape = None
		if not force:
			# Skip if the old end of the window is populated (only a backfill writes there).
			# runScalarQuery does not bind args; use runScalarPrepQuery.
			oldest = None
			for p in buckets:
				v = system.db.runScalarPrepQuery(
					"SELECT MIN(t_stamp) FROM %s WHERE tagid = ?" % p,
					[tagid], database=db())
				if v is not None and (oldest is None or v < oldest):
					oldest = v
			if oldest is not None and oldest <= startMs + stepMs:
				skipped += 1
				continue
		col = "intvalue" if isInt else "floatvalue"
		for p, stamps in buckets.items():
			vals = []
			for ts in stamps:
				if shape == "ramp":
					midnight = system.date.toMillis(
						system.date.midnight(system.date.fromMillis(ts)))
					v = float(engHigh) * (ts - midnight) / 86400000.0
				elif shape == "flat":
					v = base
				else:
					phase = (ts / 3600000.0) * (math.pi / 12.0)
					v = base + amp * math.sin(phase) + random.uniform(-amp * 0.35, amp * 0.35)
				vals.append((tagid, v, ts))
			chunk = 200
			for s in range(0, len(vals), chunk):
				part = vals[s:s + chunk]
				sql = ("INSERT INTO %s (tagid, %s, dataintegrity, t_stamp) VALUES " % (p, col)
					+ ",".join(["(?,?,192,?)"] * len(part)))
				args = []
				for tid, v, ts in part:
					args.extend([tid, int(round(v)) if isInt else v, ts])
				system.db.runPrepUpdate(sql, args, database=db())
				total += len(part)
	out = {"rows": total, "gateway": sysName, "tags": len(tags),
	       "partitions": sorted(buckets.keys()),
	       "tagsSeeded": len(tags) - skipped, "tagsSkipped": skipped,
	       "tagsSkippedPaths": skippedPaths}
	if unpartitioned:
		out["samplesOutsideAnyPartition"] = unpartitioned
	return out

def repairBackfill():
	"""Move integer tags' samples from floatvalue into intvalue in the current partition."""
	if not launchpad.edition.hasDatabase():
		# system.historian picks the column itself.
		return {"rowsRepaired": 0, "note": "not applicable on this edition"}
	drvIds = _driverIds()[1]
	nowMs = system.date.toMillis(system.date.now())
	p = _partitionFor(nowMs, _partitions(drvIds))
	if p is None:
		return {"rowsRepaired": 0, "error": "no current history partition"}
	n = system.db.runUpdateQuery(
		"UPDATE %s SET intvalue = CAST(floatvalue AS INTEGER), floatvalue = NULL "
		"WHERE floatvalue IS NOT NULL "
		"AND tagid IN (SELECT id FROM sqlth_te WHERE datatype = 0)" % p, database=db())
	return {"rowsRepaired": n, "partition": p}
