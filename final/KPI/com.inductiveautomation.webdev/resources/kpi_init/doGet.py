def doGet(request, session):
	"""Installer endpoint for the Launchpad KPI example.

	GET /system/webdev/KPI/kpi_init?action=initDashboard

	The dashboard tables live in the same database as the OEE ones, but the script
	that creates them (launchpad.init) belongs to THIS project -- project
	script packages are not visible across projects, so OEE's lp_init cannot call it.

	Actions: initDashboard | backfill | repairBackfill | status
	"""
	action = request["params"].get("action", "status")
	out = {"action": action}
	try:
		if action == "initDashboard":
			# idempotent: the seed script issues bare CREATE TABLE, so re-running it
			# against a populated database would fail half-way and leave it torn.
			existing = system.db.runScalarQuery(
				"SELECT COUNT(*) FROM sqlite_master WHERE type = \'table\' AND name = \'ex_lp_dashboards\'",
				database=launchpad.init.db())
			if existing:
				out["skipped"] = "dashboard tables already present"
			else:
				launchpad.init.initDashboard()
				out["created"] = True
			out["dashboards"] = system.db.runScalarQuery(
				"SELECT COUNT(*) FROM ex_lp_dashboards", database=launchpad.init.db())
			out["widgets"] = system.db.runScalarQuery(
				"SELECT COUNT(*) FROM ex_lp_dashboard_widgets", database=launchpad.init.db())
			out["ok"] = True
		elif action == "setup":
			# the same call the Setup button makes -- one implementation, not two
			out["setup"] = launchpad.setup.run(
				force=request["params"].get("force", "") in ("1", "true", "yes"),
				history=request["params"].get("history", "1") not in ("0", "false", "no"),
				tags=request["params"].get("tags", "") in ("1", "true", "yes"))
			out["ok"] = out["setup"].get("ok", False)
		elif action == "check":
			out["check"] = launchpad.setup.check()
			out["ok"] = True
		elif action == "backfill":
			hours = int(request["params"].get("hours", 48))
			step = int(request["params"].get("step", 15))
			force = request["params"].get("force") in ("1", "true", "yes")
			out.update(launchpad.init.backfill(hours, step, force))
			out["ok"] = "error" not in out
		elif action == "repairBackfill":
			out["result"] = launchpad.init.repairBackfill()
			out["ok"] = True
		else:
			tables = system.db.runQuery(
				"SELECT name FROM sqlite_master WHERE type = \'table\' AND name LIKE \'ex_lp_%\' ORDER BY name",
				database=launchpad.init.db())
			out["tables"] = [r["name"] for r in tables]
			out["ok"] = True
	except:
		import traceback
		out["ok"] = False
		out["error"] = traceback.format_exc()
	return {"json": out}
