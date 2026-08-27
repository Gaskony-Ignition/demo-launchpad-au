def doGet(request, session):
	"""One-shot maintenance endpoint for the Launchpad OEE example.

	GET /system/webdev/OEE/lp_init?action=initDemoTags
	Actions: setupShifts | seedHistory | initDemoTags | resetDemoTags | initTables | heal | diag | intervals | status
	Delete this resource before publishing the portable Exchange package.
	"""
	action = request["params"].get("action", "status")
	out = {"action": action}
	try:
		if action == "initDemoTags":
			launchpad.oee.initDemoTags()
			out["ok"] = True
		elif action == "resetDemoTags":
			launchpad.oee.resetDemoTags()
			out["ok"] = True
		elif action == "intervals":
			out["intervals"] = _allIntervals()
			out["ok"] = True
		elif action == "setupShifts":
			out["result"] = launchpad.oee.setupShifts()
			out["ok"] = True
		elif action == "seedHistory":
			out["result"] = launchpad.oee.seedHistory()
			out["ok"] = True
		elif action == "setup":
			# the same call the Setup button makes -- one implementation, not two
			out["setup"] = launchpad.setup.run(
				force=request["params"].get("force", "") in ("1", "true", "yes"),
				history=request["params"].get("history", "1") not in ("0", "false", "no"),
				tags=request["params"].get("tags", "") in ("1", "true", "yes"))
			out["ok"] = out["setup"].get("ok", False)
		elif action == "heal":
			# the same repair the scheduled self-heal runs, on demand
			out["heal"] = launchpad.oee.healAnchors()
			out["ok"] = True
		elif action == "check":
			out["check"] = launchpad.setup.check()
			out["ok"] = True
		elif action == "diag":
			out["diag"] = _diag()
			out["ok"] = True
		elif action == "initTables":
			# initTables issues bare CREATE UNIQUE INDEX and a seed INSERT, so a second
			# run throws half-way through and leaves the schema partly built.
			# tableExists goes through the gateway's own metadata provider, so it
			# works on any connection. A sqlite_master query does not: on Postgres
			# it throws, and the install fails at the first seeding step.
			done = launchpad.oee.tableExists(
				launchpad.oee.db(), "ex_launchpad_oee_shift")
			if done:
				out["skipped"] = "OEE tables already present"
			else:
				launchpad.oee.initTables()
				out["created"] = True
			out["ok"] = True
		else:
			lines = launchpad.oee.getLineNames("[Launchpad]OEE/Demo")
			paths = []
			for ln in lines:
				for leaf in ["Display/OEE", "Display/Availability", "Plc/State", "ShiftOee/O", "Enabled"]:
					paths.append("[Launchpad]OEE/Demo/%s/%s" % (ln, leaf))
			vals = system.tag.readBlocking(paths)
			out["lines"] = lines
			out["tags"] = dict(zip(paths, ["%s (%s)" % (v.value, v.quality) for v in vals]))
			out["ok"] = True
	except:
		import traceback
		out["ok"] = False
		out["error"] = traceback.format_exc()
	return {"json": out}


def _diag():
	DB = launchpad.oee.db()
	out = {}
	# what does the OEE engine currently hold for line 1?
	base = "[Launchpad]OEE/Demo/Line 1"
	leaves = ["ShiftOee/O","ShiftOee/A","ShiftOee/P","ShiftOee/Q","ShiftOee/U",
		"ShiftOee/RunSeconds","ShiftOee/SecondsElapsed","ShiftOee/ProductionCount",
		"ShiftOee/TargetProductionCount","ShiftOee/StartTime","ShiftOee/StartCounter",
		"ShiftOee/Duration","Plc/ProductionCounter","Plc/State",
		"Schedule/CurrentShift","Schedule/CurrentShiftStartTime","Config/TargetRate"]
	paths = ["%s/%s" % (base, l) for l in leaves]
	vals = system.tag.readBlocking(paths)
	out["line1"] = dict(zip(leaves, [str(v.value) for v in vals]))
	trh = system.tag.readBlocking(["%s/ShiftOee/TargetRateHistory" % base])[0].value
	if trh is not None:
		out["targetRateHistory"] = [[str(trh.getValueAt(r, c)) for c in range(trh.columnCount)]
			for r in range(trh.rowCount)]
		out["trhCols"] = list(trh.columnNames)
	# history coverage for the KPI chart tags
	out["hist"] = _histCoverage(DB)
	out["nowMs"] = str(system.date.toMillis(system.date.now()))
	# do the OEE named queries return anything?
	stop = system.date.now()
	start = system.date.addHours(stop, -24)
	try:
		r = system.db.runNamedQuery("OEE", "Launchpad/Oee/HourlyStats",
			{"line_name": "Line 1", "tag_folder": "[Launchpad]OEE/Demo",
			 "start_time": start, "stop_time": stop})
		out["hourlyStatsRows"] = r.rowCount
	except:
		import traceback
		out["hourlyStatsError"] = traceback.format_exc()[-500:]
	return out


def _allIntervals():
	lines = launchpad.oee.getLineNames("[Launchpad]OEE/Demo")
	paths, keys = [], []
	for ln in lines:
		for iv in ("DayOee", "ShiftOee", "HourOee"):
			for leaf in ("O", "A", "P", "Q", "U"):
				paths.append("[Launchpad]OEE/Demo/%s/%s/%s" % (ln, iv, leaf))
				keys.append("%s|%s|%s" % (ln, iv, leaf))
	vals = system.tag.readBlocking(paths)
	out = {}
	for k, v in zip(keys, vals):
		ln, iv, leaf = k.split("|")
		out.setdefault(ln, {}).setdefault(iv, {})[leaf] = (
			round(v.value, 4) if isinstance(v.value, (int, float)) else str(v.value))
	return out

def _histCoverage(DB):
	"""Row counts for a few KPI history tags, from THIS gateway's current partition.

	The partition name encodes a historian driver id and a month
	(sqlt_data_<drvid>_<yyyy>_<mm>). Neither is safe to compose: the driver id is not
	always 1, and the historian allocates a new one whenever the gateway's system name
	changes. Look up what exists instead -- a composed name is either a missing table
	or, worse, a retired generation that reads as healthy while the charts show nothing.
	"""
	sysName = system.tag.readBlocking(["[System]Gateway/SystemName"])[0].value
	drv = system.db.runPrepQuery("SELECT id FROM sqlth_drv WHERE lower(name) = ?",
		[sysName.lower()], database=DB)
	drvIds = [r["id"] for r in drv]
	if not drvIds:
		return [["(no historian driver for %s)" % sysName, "0"]]
	nowMs = system.date.toMillis(system.date.now())
	part = None
	for r in system.db.runQuery(
			"SELECT pname, drvid, start_time, end_time FROM sqlth_partitions", database=DB):
		if r["drvid"] in drvIds and r["start_time"] <= nowMs < r["end_time"]:
			part = r["pname"]; break
	if part is None:
		return [["(no history partition covers now)", "0"]]
	rows = system.db.runQuery(
		"SELECT te.tagpath, COUNT(*) n, MIN(d.t_stamp) mn, MAX(d.t_stamp) mx "
		"FROM sqlth_te te JOIN %s d ON d.tagid = te.id "
		"WHERE te.tagpath IN ('kpi/dailyproduction','kpi/dailyproductionexpected',"
		"'kpi/airpressure') GROUP BY te.tagpath" % part, database=DB)
	return [[str(c) for c in r] for r in rows]
