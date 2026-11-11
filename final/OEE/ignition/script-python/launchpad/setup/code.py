"""Gateway builder behind the Setup button: database, tag provider, historian, device, tags, seeding.

run(progress=None, force=False) builds what is missing; check() reports and changes nothing. Both are idempotent.
Each project uses its own SQLite file (${data}/OEE.db, ${data}/KPI.db); the schema is SQLite DDL, so it cannot target Postgres or MSSQL.
"""
import json
import os
import traceback

LOG = system.util.getLogger("launchpad.setup")

RESOURCES = "data/config/resources"
CORE = "core/ignition"
HISTORIAN_MODULE = "core/com.inductiveautomation.historian"
OPCUA_MODULE = "core/com.inductiveautomation.opcua"

# The tag historian is one gateway provider with one database, and every historised tag is KPI's, so OEE never creates it.
HISTORY_DATABASE = "KPI"

def _dbName():
	"""This project's own database: "OEE" or "KPI"."""
	return "OEE" if _isOee() else "KPI"


def _connectURL(name=None):
	"""The SQLite URL for a database of this name."""
	# WAL stops writers blocking readers; busy_timeout makes the second writer wait instead of failing with SQLITE_BUSY.
	return ("jdbc:sqlite:${data}/%s.db?journal_mode=WAL&busy_timeout=30000"
	        % (name or _dbName()))
PROVIDER = "launchpad"
HISTORIAN = "launchpad"
DEVICE = "Launchpad"
def scriptingProjectWanted():
	"""Return the running project's name (Edge names its project Edge, so not a literal "OEE")."""
	try:
		return system.project.getProjectName()
	except:
		return "OEE"


def _isOee():
	"""True when this copy runs in the OEE project; the file is identical in OEE and KPI."""
	return hasattr(launchpad, "oee")


def _lib():
	return launchpad.oee if _isOee() else launchpad.init


def _db():
	return _lib().db()


def _probeTag():
	"""A tag that exists only once this project's tags are imported."""
	if _isOee():
		return "[%s]OEE/Demo/Line 1/Enabled" % PROVIDER
	return "[%s]KPI/Lines/Line1/ProductionRate" % PROVIDER


def _emit(progress, message):
	LOG.info(message)
	if progress is not None:
		try:
			progress(message)
		except:
			pass  # a broken progress sink must never fail the install


class _Report:
	"""Running transcript shown by the Setup button: one line per step with its result."""

	def __init__(self, progress):
		self.progress = progress
		self.lines = []
		self.current = None

	def _flush(self, tail=None):
		body = list(self.lines)
		if tail:
			body.append(tail)
		if self.progress is not None:
			try:
				self.progress("\n".join(body))
			except:
				pass

	def start(self, message):
		"""Show message as the step in progress."""
		self.current = message
		LOG.info(message)
		self._flush("... %s" % message)

	def waiting(self, message, seconds):
		"""Show how long the current wait has lasted."""
		self._flush("... %s (%ds)" % (message, seconds))

	def done(self, outcome):
		"""Record the current step as done with its outcome."""
		if self.current:
			self.lines.append("[ok]   %s%s" % (self.current,
			    (" - %s" % outcome) if outcome else ""))
			self.current = None
		self._flush()

	def failed(self, why):
		"""Record the current step as failed."""
		if self.current:
			self.lines.append("[FAIL] %s - %s" % (self.current, why))
			self.current = None
		self._flush()

	def note(self, message):
		"""Add an indented note line."""
		self.lines.append("       %s" % message)
		self._flush()

	def finish(self, ok, summaryLine):
		"""Add the closing line and return the full transcript."""
		self.lines.append("")
		self.lines.append("SETUP COMPLETE - %s" % summaryLine if ok
		                  else "SETUP FINISHED WITH ERRORS - %s" % summaryLine)
		self._flush()
		return "\n".join(self.lines)


def _short(outcome):
	"""A step's result in a few words, for the line it leaves behind."""
	if outcome is None:
		return ""
	if isinstance(outcome, dict):
		if "shiftRows" in outcome:
			return "%s shift + %s hour rows" % (outcome.get("shiftRows"),
			                                    outcome.get("hourRows"))
		if "state" in outcome:
			return str(outcome["state"])[:70]
		if "tagsWritten" in outcome:
			if not outcome["tagsWritten"]:
				return "already correct"
			return "%s tags written" % outcome["tagsWritten"]
		if "healed" in outcome:
			if not outcome["healed"]:
				return "all correct"
			return "%s interval(s) re-anchored" % outcome["healed"]
		if "rows" in outcome:                       # the KPI history backfill
			seeded = outcome.get("tagsSeeded")
			return "%s rows%s" % (outcome["rows"],
			    (" across %s tags" % seeded) if seeded else "")
		return ""
	return str(outcome)[:70]


def _explain(tb):
	"""Turn a Jython traceback into a message the user can act on."""
	last = tb.strip().split("\n")[-1]
	if "no attribute 'payload'" in last:
		return ("the launchpad.payload script resource did not load. "
		        "Re-import the project, then press Set up again "
		        "(Config > Projects > Scan File System if it persists)")
	for name in ("oee", "init", "setup", "sql"):
		if "no attribute '%s'" % name in last:
			return ("the launchpad.%s script resource did not load. "
			        "Re-import the project and press Set up again" % name)
	if "no attribute" in last and "script.Scr" in last:
		return ("a project script resource did not load - re-import the project "
		        "and press Set up again (%s)" % last[-90:])
	return last[:180]


def _abs(rel):
	from java.io import File
	return File(rel).getAbsolutePath()


def _write(path, content, binary=False):
	f = open(path, "wb" if binary else "w")
	try:
		f.write(content)
	finally:
		f.close()


def _read(path):
	f = open(path)
	try:
		return f.read()
	finally:
		f.close()


def _stamp():
	return system.date.format(system.date.now(), "yyyy-MM-dd'T'HH:mm:ss'Z'")


def _resourceJson(files, description):
	from java.util import UUID
	return system.util.jsonEncode({
	    "scope": "A",
	    "description": description,
	    "version": 1,
	    "restricted": False,
	    "overridable": True,
	    "files": files,
	    "attributes": {
	        "uuid": str(UUID.randomUUID()),
	        "enabled": True,
	        "lastModification": {"actor": "launchpad-setup", "timestamp": _stamp()},
	    },
	})


def _configResource(module, kind, name, config, description, extra=None):
	"""Write a gateway config resource and return its directory; `extra` is (filename, content, binary) tuples."""
	# resource.json must list every file or the gateway ignores the lot.
	d = os.path.join(_abs(RESOURCES), module, kind, name)
	if not os.path.exists(d):
		os.makedirs(d)
	files = ["config.json"]
	_write(os.path.join(d, "config.json"), system.util.jsonEncode(config))
	for fname, content, binary in (extra or []):
		files.append(fname)
		_write(os.path.join(d, fname), content, binary)
	_write(os.path.join(d, "resource.json"), _resourceJson(files, description))
	return d


def _configScan():
	"""Register config resources by asking the configuration manager to scan."""
	# Not system.project.requestScan(): the gateway has two "Scan File System" buttons and the wrong one does nothing.
	from com.inductiveautomation.ignition.gateway import IgnitionGateway
	cm = IgnitionGateway.get().getConfigurationManager()
	before = str(cm.getScanInformation())
	cm.requestScan()
	# requestScan is asynchronous; wait for the scan information to change before relying on its result.
	_waitFor(lambda: str(cm.getScanInformation()) != before, 90, 1)
	return True


def _waitFor(test, seconds=60, interval=2, report=None, what=None):
	"""Poll test() until true or `seconds` elapse; return whether it became true."""
	from java.lang import Thread
	waited = 0
	while waited < seconds:
		try:
			if test():
				return True
		except:
			pass
		if report is not None and what and waited and waited % 10 == 0:
			report.waiting(what, waited)
		Thread.sleep(interval * 1000)
		waited += interval
	try:
		return bool(test())
	except:
		return False


def databaseReady(name=None):
	"""True if the connection answers; always True without a database module (Edge), where launchpad.store takes over."""
	if not launchpad.edition.hasDatabase():
		return True
	try:
		system.db.runScalarQuery("SELECT 1", database=(name or _db()))
		return True
	except:
		return False


def providerReady():
	"""True if the tag provider's config resource exists on disk."""
	# Not a browse: browsing a missing provider returns empty instead of raising.
	return os.path.exists(os.path.join(
	    _abs(RESOURCES), CORE, "tag-provider", PROVIDER))


def expectedLines():
	"""Return the number of demo lines in the shipped tag payload (0 for KPI)."""
	if not _isOee():
		return 0
	try:
		for rel, text in launchpad.payload.tagFiles().items():
			if rel.endswith("OEE/Demo/udts.json"):
				items = json.loads(text)
				return len([t for t in items if t.get("typeId")])
	except:
		LOG.warn("could not count the shipped lines: %s" % traceback.format_exc())
	return 0


def linesBrowsable():
	"""Return how many line instances the tag system browses right now."""
	# A browse taken mid-scan returns a partial list.
	try:
		return len(_lib().getLineNames(_lib().BASE_TAG_FOLDER))
	except:
		return 0


def linesReady():
	"""True once every shipped line is browsable."""
	want = expectedLines()
	return want > 0 and linesBrowsable() >= want


def tagsPresent():
	"""True if the probe tag exists."""
	try:
		return bool(system.tag.exists(_probeTag()))
	except:
		return False


def tagReading():
	"""Return whether the probe tag has a good value, not just a definition."""
	try:
		paths = [_probeTag()]
		if _isOee():
			# A null production counter stops the simulator script while every other probe stays green.
			paths.append("[%s]OEE/Demo/Line 1/Plc/ProductionCounter" % PROVIDER)
		vals = system.tag.readBlocking(paths)
		qv = vals[0]
		out = {"quality": str(qv.quality), "value": str(qv.value),
		       "ok": bool(qv.quality.isGood() and qv.value is not None)}
		if len(vals) > 1:
			cv = vals[1]
			out["productionCounter"] = str(cv.value)
			if cv.value is None:
				out["ok"] = False
				out["note"] = "the production counter has no value - the demo is not running"
		return out
	except:
		return {"ok": False}


def historianReady():
	"""True if a tag historian exists: Edge's own, else the historian-provider config resource."""
	if launchpad.edition.isEdge():
		return bool(launchpad.edition.historian())
	return os.path.exists(os.path.join(
	    _abs(RESOURCES), HISTORIAN_MODULE, "historian-provider", HISTORIAN))


def deviceState():
	"""Return the simulator's connection state, or None if the device is absent."""
	try:
		devices = system.device.listDevices()
		for row in range(devices.getRowCount()):
			if devices.getValueAt(row, "Name") == DEVICE:
				return str(devices.getValueAt(row, "State"))
	except:
		pass
	return None


def deviceReady():
	"""True if the simulator is up."""
	# A simulator reports Running, a real driver Connected.
	return deviceState() in ("Connected", "Running")


def scriptingProject():
	"""The gateway's configured scripting project, or None if it cannot be read."""
	try:
		p = os.path.join(_abs(RESOURCES), CORE, "system-properties", "config.json")
		return system.util.jsonDecode(_read(p)).get("gatewayScriptingProject")
	except:
		return None


def tablesPresent():
	"""True if this project's own tables exist (the file store's readiness on Edge)."""
	if not launchpad.edition.hasDatabase():
		# No tables by design: the store reports its own readiness.
		return launchpad.store.ready()
	try:
		from com.inductiveautomation.ignition.gateway import IgnitionGateway
		from com.inductiveautomation.ignition.common.db.schema import TableType
		want = "ex_launchpad_oee_shift" if _isOee() else "ex_lp_dashboards"
		tables = IgnitionGateway.get().getDatasourceManager().getMetaProvider() \
		    .getTables(_db(), TableType.Table)
		return want in tables
	except:
		return False


def drawableHistory():
	"""Return OEE hour rows older than the hour in progress (KPI: history rows), or None if unreadable."""
	# The live engine opens a row for the current hour, so only older rows count as drawable.
	if not _isOee():
		# A seeded window holds a sample per tag, so fewer rows than tags means it is not seeded.
		rows = historyRows(24)
		try:
			tags = launchpad.init.registeredTagCount()
		except:
			tags = 0
		if tags and rows < tags:
			return 0
		return rows
	try:
		now = system.date.now()
		hourStart = system.date.setTime(now, system.date.getHour24(now), 0, 0)
		if not launchpad.edition.hasDatabase():
			# Ask the store for rows; a day file holds many.
			return launchpad.store.hourlyStats(
			    "", launchpad.oee.BASE_TAG_FOLDER,
			    system.date.addDays(hourStart, -400),
			    system.date.addSeconds(hourStart, -1)).getRowCount()
		return system.db.runScalarPrepQuery(
		    "SELECT COUNT(*) FROM ex_launchpad_oee_hour WHERE hour_timestamp < ?",
		    [hourStart], database=_db())
	except:
		return None


def historyRows(withinHours=24):
	"""Return how many history rows fall in the last `withinHours`, or None if unreadable."""
	# Binds a Date rather than parsing a returned timestamp, whose type varies by driver.
	try:
		since = system.date.addHours(system.date.now(), -withinHours)
		if _isOee():
			if not launchpad.edition.hasDatabase():
				return launchpad.store.hourlyStats(
				    "", launchpad.oee.BASE_TAG_FOLDER, since,
				    system.date.now()).getRowCount()
			return system.db.runScalarPrepQuery(
			    "SELECT COUNT(*) FROM ex_launchpad_oee_hour WHERE hour_timestamp >= ?",
			    [since], database=_db())
		if not launchpad.edition.hasDatabase():
			# The historian is internal here, so ask it instead of counting partition tables.
			return launchpad.init.historyRowsSince(since)
		drvIds = launchpad.init._driverIds()[1]
		total = 0
		# _partitions returns tuples of (name, startMs, endMs), not dicts
		for name, _, _ in launchpad.init._partitions(drvIds):
			total += system.db.runScalarPrepQuery(
			    "SELECT COUNT(*) FROM %s WHERE t_stamp >= ?" % name,
			    [system.date.toMillis(since)], database=_db())
		return total
	except:
		return None


def shiftsEnabled():
	"""True if line 1's first shift is enabled (KPI: always True); without a roster Performance divides by zero."""
	try:
		if not _isOee():
			return True  # the roster belongs to OEE; KPI has no shifts of its own
		lines = launchpad.oee.getLineNames("[%s]OEE/Demo" % PROVIDER)
		if not lines:
			return False
		# ShiftEnabled, not Enabled: the line's own Enabled tag would report an unwritten roster as healthy.
		paths = ["[%s]OEE/Demo/%s/Schedule/1/ShiftEnabled" % (PROVIDER, lines[0])]
		qv = system.tag.readBlocking(paths)[0]
		return bool(qv.quality.isGood() and qv.value)
	except:
		return False


def existingDatabase():
	"""Return "absent", "ours" (SQLite), "unreadable" or the translator name of another connection under this name."""
	# An unreadable connection counts as not ours: refusing is cheaper than building a schema in someone else's database.
	p = os.path.join(_abs(RESOURCES), CORE, "database-connection", _dbName(),
	                 "config.json")
	if not os.path.exists(p):
		return "absent"
	try:
		translator = system.util.jsonDecode(_read(p)).get("translator") or ""
	except:
		return "unreadable"
	return "ours" if str(translator).upper() == "SQLITE" else str(translator)


def ensureDatabase(force=False):
	"""Create the SQLite connection (no credentials needed), or repair its URL on an older release's connection."""
	if not launchpad.edition.hasDatabase():
		return "not needed on this edition"
	kind = existingDatabase()
	if kind not in ("absent", "ours"):
		# A same-named non-SQLite connection also answers SELECT 1; stop rather than run SQLite DDL against it.
		raise Exception(
		    "a connection called '%s' already exists here and is %s, not SQLite. "
		    "This schema is SQLite DDL. Rename or remove it, then press Set up again"
		    % (_dbName(), kind))
	if kind == "ours" and databaseReady(_dbName()) and not force:
		# An older release's URL lacks the WAL parameters, so a working connection can still need repair.
		if existingConnectURL() == _connectURL():
			return "already connected"
		# Patch connectURL only; rewriting the file would reset pool settings someone may have tuned.
		existing = _readConfig(CORE, "database-connection", _dbName())
		if existing is not None:
			existing["connectURL"] = _connectURL()
			_configResource(CORE, "database-connection", _dbName(), existing,
			                "SQLite database for the Launchpad OEE + KPI example "
			                "resources")
			return "updated"
		# Unreadable config.json: write a known-good one.
	_configResource(CORE, "database-connection", _dbName(), {
	    "connectURL": _connectURL(),
	    "connectionProps": "", "connectionResetParams": "",
	    "defaultTransactionLevel": "DEFAULT", "driver": "SQLite",
	    "evictionRate": -1, "evictionTests": 3, "evictionTime": 1800000,
	    "failoverMode": "STANDARD", "failoverProfile": "",
	    "includeSchemaInTableName": False,
	    "poolInitSize": 0, "poolMaxActive": 8, "poolMaxIdle": 8, "poolMaxWait": 5000,
	    "poolMinIdle": 0, "slowQueryLogThreshold": 60000,
	    "testOnBorrow": True, "testOnReturn": False, "testWhileIdle": False,
	    "translator": "SQLITE", "username": "",
	    "validationQuery": "SELECT 1", "validationSleepTime": 10000,
	}, "SQLite database for the Launchpad OEE + KPI example resources")
	return "created" if kind == "absent" else "updated"


def _readConfig(module, kind, name):
	"""Return a resource's config.json as a dict, or None if absent or unreadable."""
	p = os.path.join(_abs(RESOURCES), module, kind, name, "config.json")
	if not os.path.exists(p):
		return None
	try:
		return system.util.jsonDecode(_read(p))
	except:
		return None


def existingConnectURL():
	"""Return this project's connection URL as installed, or "" if there is no readable one."""
	p = os.path.join(_abs(RESOURCES), CORE, "database-connection", _dbName(),
	                 "config.json")
	if not os.path.exists(p):
		return ""
	try:
		return str(system.util.jsonDecode(_read(p)).get("connectURL") or "")
	except:
		return ""


EDGE_VISUALIZATION = "PERSPECTIVE"


def _edgeSystemProperties():
	"""Return Edge's settings resource, or None off Edge."""
	# A singleton with no name segment, so find it by enumerating the type.
	try:
		found = list(system.config.getResources(
		    moduleId="ignition", typeId="edge-system-properties"))
	except:
		return None
	return found[0] if found else None


def edgeVisualizationReady():
	"""True if Edge's visualization is Perspective (always True off Edge)."""
	res = _edgeSystemProperties()
	if res is None:
		return not launchpad.edition.isEdge()
	try:
		cfg = system.util.jsonDecode(system.util.jsonEncode(res.getConfig()))
		return cfg.get("visualizationName") == EDGE_VISUALIZATION
	except:
		return False


def ensureEdgeVisualization(force=False):
	"""Point Edge's Visualization Module at Perspective, live via system.config."""
	# Edge ships on VISION, and until this is PERSPECTIVE no Perspective session opens ("Sessions Exceeded").
	if not launchpad.edition.isEdge():
		return "not an Edge gateway"
	res = _edgeSystemProperties()
	if res is None:
		raise Exception("this gateway has no Ignition Edge settings resource")
	cfg = system.util.jsonDecode(system.util.jsonEncode(res.getConfig()))
	was = cfg.get("visualizationName")
	if was == EDGE_VISUALIZATION and not force:
		return "already %s" % EDGE_VISUALIZATION
	cfg["visualizationName"] = EDGE_VISUALIZATION
	# `replace` is optimistic concurrency and needs the CURRENT signature.
	system.config.replace(moduleId="ignition", typeId="edge-system-properties",
	                      name=res.getName(), config=cfg,
	                      signature=res.getSignature(),
	                      actor="launchpad.setup")
	return "changed from %s to %s" % (was or "unset", EDGE_VISUALIZATION)


def ensureTagProvider(force=False):
	"""Create the tag provider; on Edge only check that the one it owns exists."""
	if launchpad.edition.isEdge():
		# Edge permits one realtime provider, made by the platform, so there is nothing to create.
		if providerReady():
			return "using '%s', which Edge owns" % PROVIDER
		raise Exception(
		    "tag provider '%s' does not exist. Edge keeps one realtime "
		    "provider and this build is built for a provider of that name - "
		    "set Config -> Ignition Edge -> Tag Provider to '%s' and save"
		    % (PROVIDER, PROVIDER))
	if providerReady() and not force:
		return "already present"
	config = launchpad.payload.tagProvider()
	config["settings"]["defaultDatasourceName"] = _dbName()
	_configResource(CORE, "tag-provider", PROVIDER, config,
	                "Tag provider for the Launchpad OEE + KPI example resources")
	return "created"


def ensureHistorian(force=False):
	"""Create the tag historian; on Edge use the one the platform owns."""
	if launchpad.edition.isEdge():
		# Edge's historian is not a config resource, so there is nothing to write or force.
		return "using %s, which Edge owns" % launchpad.edition.historian()
	if historianReady() and not force:
		return "already present"
	config = launchpad.payload.historian()
	config["settings"]["database"] = HISTORY_DATABASE
	_configResource(HISTORIAN_MODULE, "historian-provider", HISTORIAN, config,
	                "Tag historian for the Launchpad OEE + KPI example resources")
	return "created"


def ensureDevice(force=False):
	"""Create the programmable simulator device with its programme."""
	# Without the programme the device exists but every KPI tag reads stale.
	if deviceReady() and not force:
		return "already present"
	_configResource(OPCUA_MODULE, "device", DEVICE,
	                launchpad.payload.device(),
	                "Programmable simulator driving the Launchpad example tags",
	                extra=[("instructions.csv", deviceInstructions(), True)])
	return "created"


def deviceInstructions():
	"""Return the simulator's programme."""
	# Its browse paths are bare, so unlike the tag payload it needs no provider rewrite.
	return launchpad.payload.instructions()


def ensureScriptingProject(force=False):
	"""Point the gateway scripting project at this one (OEE only); never take it off another project."""
	# The OEE UDT event scripts resolve launchpad.oee from this setting; unset, every OEE figure is zero with nothing in the log.
	if not _isOee():
		# KPI has no tag-scope scripts, and this is a gateway-wide setting.
		return "not needed - this is the KPI project"
	if scriptingProject() == scriptingProjectWanted() and not force:
		return "already %s" % scriptingProjectWanted()
	if not os.path.exists(os.path.join(_abs("data/projects"), scriptingProjectWanted())):
		return "not needed - the %s project is not installed" % scriptingProjectWanted()
	current = scriptingProject()
	if current and current != scriptingProjectWanted() and not force:
		return ("left alone - this gateway already uses '%s'; set it to %s by hand if "
		        "the OEE demo is meant to own it" % (current, scriptingProjectWanted()))
	d = os.path.join(_abs(RESOURCES), CORE, "system-properties")
	cfgPath = os.path.join(d, "config.json")
	if not os.path.exists(cfgPath):
		return "system-properties resource missing - set it by hand"
	cfg = system.util.jsonDecode(_read(cfgPath))
	cfg["gatewayScriptingProject"] = scriptingProjectWanted()
	_write(cfgPath, system.util.jsonEncode(cfg))
	# Rewrite resource.json in place to keep its other attributes; a stale signature makes the scan skip the file.
	resPath = os.path.join(d, "resource.json")
	if os.path.exists(resPath):
		res = system.util.jsonDecode(_read(resPath))
		attrs = res.get("attributes", res)
		if "lastModificationSignature" in attrs:
			del attrs["lastModificationSignature"]
		attrs["lastModification"] = {"actor": "launchpad-setup", "timestamp": _stamp()}
		_write(resPath, system.util.jsonEncode(res))
	return "set to %s" % scriptingProjectWanted()


def ensureTags(force=False):
	"""Install the tags as gateway config resources, then scan them in."""
	# Not system.tag.configure: configuring a subtree at the provider root removes the provider's other subtrees.
	# UDT types go under tag-type-definition so they land in the type namespace.
	if tagsPresent() and not force:
		return "already present"
	base = os.path.join(_abs(RESOURCES), CORE)
	written = 0
	for rel, text in payloadFiles().items():
		dest = os.path.join(base, *rel.split("/"))
		parent = os.path.dirname(dest)
		if not os.path.exists(parent):
			os.makedirs(parent)
		_write(dest, text)
		written += 1
	# requestScan is asynchronous and does nothing while the previous scan is running, so scan, wait, retry.
	for _attempt in range(6):
		_configScan()
		if _waitFor(tagsPresent, 20, 2):
			return "installed %d resources" % written
	raise Exception("tags did not appear at %s after %d scans" % (_probeTag(), 6))


# The provider name baked into the compressed tag payload; payloadFiles rewrites it, since a build-time sed cannot reach inside.
PAYLOAD_PROVIDER = "launchpad"

# A tag naming a historian that does not exist records nothing, and scripted writes fail with "Failed to normalize N data points".
PAYLOAD_HISTORIAN = "launchpad"


def payloadFiles():
	"""Return the tag resources this build installs, with provider and historian names rewritten for this gateway."""
	files = launchpad.payload.tagFiles()
	if (PROVIDER == PAYLOAD_PROVIDER
	        and launchpad.edition.historian() == PAYLOAD_HISTORIAN):
		return files
	out = {}
	for rel, text in files.items():
		parts = rel.split("/")
		# <kind>/<provider>/rest...
		if len(parts) > 1 and parts[1] == PAYLOAD_PROVIDER:
			parts[1] = PROVIDER
		# "ns=1;s=[Launchpad]..." is an OPC item path whose brackets name the device, which is never renamed;
		# protect it with a sentinel while the tag paths are rewritten.
		SENTINEL = "\x00opc\x00"
		opc = "ns=1;s=[%s]" % PAYLOAD_PROVIDER.capitalize()
		text = text.replace(opc, SENTINEL)
		for old in ("[%s]" % PAYLOAD_PROVIDER.capitalize(),
		            "[%s]" % PAYLOAD_PROVIDER):
			text = text.replace(old, "[%s]" % PROVIDER)
		text = text.replace(SENTINEL, opc)
		text = text.replace("prov:%s:" % PAYLOAD_PROVIDER,
		                    "prov:%s:" % PROVIDER)
		historian = launchpad.edition.historian()
		if historian != PAYLOAD_HISTORIAN:
			text = text.replace('"historyProvider": "%s"' % PAYLOAD_HISTORIAN,
			                    '"historyProvider": "%s"' % historian)
		out["/".join(parts)] = text
	return out


def staleTagResources():
	"""Return installed tag files that differ from the ones this build ships."""
	# run() does not reinstall tags, so a changed tag script cannot reach an existing gateway unless this flags it.
	base = os.path.join(_abs(RESOURCES), CORE)
	stale = []
	for rel, text in payloadFiles().items():
		dest = os.path.join(base, *rel.split("/"))
		if not os.path.exists(dest):
			stale.append("%s (missing)" % rel)
			continue
		try:
			if _read(dest) != text:
				stale.append(rel)
		except:
			stale.append("%s (unreadable)" % rel)
	return stale


def run(progress=None, force=False, history=True, tags=False):
	"""Create everything that is missing and return a report of what changed."""
	report = {}

	reporter = _Report(progress)

	def step(name, fn, message):
		reporter.start(message)
		try:
			outcome = fn()
			report[name] = outcome
			reporter.done(_short(outcome))
		except:
			why = _explain(traceback.format_exc())
			report[name] = "FAILED"
			report.setdefault("errors", []).append("%s: %s" % (name, why))
			reporter.failed(why)
			LOG.warn("setup step %s failed: %s" % (name, traceback.format_exc()))

	# First, on Edge only: no Perspective session opens until the visualization is Perspective.
	if launchpad.edition.isEdge():
		step("edgeVisualization", lambda: ensureEdgeVisualization(force),
		     "pointing Edge at Perspective")
	step("database", lambda: ensureDatabase(force), "creating the database connection")
	# Stop here on failure: every later resource names this database.
	if report.get("database") == "FAILED":
		reporter.note("stopping: nothing below can be built without the database")
		report["ok"] = False
		report["detail"] = reporter.finish(False, summary(report))
		return report

	step("tagProvider", lambda: ensureTagProvider(force), "creating the tag provider")
	# KPI only: the historian points at one database and every historised tag is KPI's.
	if not _isOee():
		step("historian", lambda: ensureHistorian(force), "creating the tag historian")
	step("device", lambda: ensureDevice(force), "creating the simulator device")
	step("scriptingProject", lambda: ensureScriptingProject(force),
	     "setting the gateway scripting project")

	# Scan only if something was written: a config scan re-fires each Enabled handler, which resets the shift in progress.
	written = [name for name in ("database", "tagProvider", "historian", "device",
	                             "scriptingProject")
	           if isinstance(report.get(name), str)
	           and report[name] != "FAILED"
	           and not report[name].startswith("already")]
	if report.get("errors"):
		# Later steps need these, and the 90s wait would only disguise the failure.
		reporter.note("stopping: %d step(s) above failed" % len(report["errors"]))
		report["ok"] = False
		report["detail"] = reporter.finish(False, summary(report))
		return report
	if written:
		reporter.start("registering gateway resources")
		_configScan()
		report["configScan"] = "registered: %s" % ", ".join(written)
		reporter.done(", ".join(written))
	else:
		report["configScan"] = "skipped - nothing new to register"
	reporter.start("waiting for the database connection and tag provider")
	if not _waitFor(lambda: databaseReady(_dbName()) and providerReady(), 90,
	                report=reporter, what="waiting for the database connection "
	                                      "and tag provider"):
		reporter.failed("still not available after 90s")
		report.setdefault("errors", []).append(
		    "gateway resources did not come up within 90s - press Set up again")
		report["ok"] = False
		report["detail"] = reporter.finish(False, summary(report))
		return report

	# Reinstalling tags over live ones leaves the old tag script subscribed (the counter runs twice per tick) until restart,
	# so it needs tags=1.
	step("tags", lambda: ensureTags(force and tags), "importing the tags")
	if not tagsPresent():
		# Seeding reads tags.
		report.setdefault("errors", []).append(
		    "tags are not present - seeding skipped")
		report["ok"] = False
		reporter.note("tags did not import - stopping")
		report["detail"] = reporter.finish(False, summary(report))
		return report

	# tagsPresent goes true at the first instance while the scan is still building the rest; seeding a subset reads as success.
	want = expectedLines()
	if want:
		reporter.start("waiting for all %d lines to be browsable" % want)
		if _waitFor(linesReady, 120, report=reporter,
		            what="waiting for all %d lines to be browsable" % want):
			reporter.done("%d of %d" % (linesBrowsable(), want))
		else:
			got = linesBrowsable()
			reporter.failed("only %d of %d lines are browsable" % (got, want))
			report.setdefault("errors", []).append(
			    "only %d of %d lines are browsable - seeding would cover a subset. "
			    "Press Set up again once the tags have finished loading." % (got, want))
			report["ok"] = False
			report["detail"] = reporter.finish(False, summary(report))
			return report

	_seed(step, report, reporter, history)

	report["ok"] = "errors" not in report
	report["detail"] = reporter.finish(report["ok"], summary(report))
	LOG.info("setup complete: %s" % report)
	return report


def _seed(step, report, reporter, history):
	"""The part that differs between the two projects."""
	step("tables", _initTables, "creating the database tables")
	if not _isOee():
		if history:
			step("history", lambda: _freshHistory(reporter), "seeding tag history")
		else:
			report["history"] = "skipped"
		return

	step("shifts", launchpad.oee.setupShifts, "writing the shift roster")
	if history:
		step("history", lambda: _freshHistory(reporter), "generating demo history")
	else:
		report["history"] = "skipped"
	# Re-anchor a running demo rather than resetting it to zero.
	if _demoInitialised():
		step("demoTags", lambda: launchpad.oee.healAnchors(LOG),
		     "checking the demo counters")
	else:
		step("resetDemoTags", launchpad.oee.resetDemoTags,
		     "zeroing the counters")
		# initDemoTags needs the shift start, which the schedule publishes only once it has ticked.
		reporter.waiting("waiting for the shift schedule to publish", 0)
		_waitFor(_shiftStartPublished, 90, report=reporter,
		         what="waiting for the shift schedule to publish")
		step("demoTags", launchpad.oee.initDemoTags,
		     "seeding the demo counters")


def _backfillWhenReady(reporter, attempts=16, waitSeconds=15, force=False):
	"""Seed KPI history once the historian has a partition and has registered this project's tags."""
	# A zero-row result counts as not ready, not as success.
	from java.lang import Thread

	# Seeding before the tag count settles marks the window seeded, so later-registering tags never get history.
	if not force:
		seen = -1
		for settle in range(20):
			count = 0
			try:
				count = launchpad.init.registeredTagCount()
			except:
				pass
			if count and count == seen:
				break
			if reporter is not None:
				reporter.waiting("waiting for the historian to register this project's "
				                 "tags (%d so far)" % count, settle * 10)
			seen = count
			Thread.sleep(10000)

	result = None
	for attempt in range(attempts):
		try:
			result = launchpad.init.backfill(force=force)
			if not result.get("error") and result.get("rows"):
				return result
			if result.get("error"):
				why = result["error"]
			else:
				why = ("the historian has registered %d of this project's tags so far "
				       "- each one appears when it records its first value"
				       % result.get("tags", 0))
		except:
			# SQLite has one writer at a time and the historian is writing; retry on a lock.
			why = traceback.format_exc().strip().split("\n")[-1]
			result = {"error": why}
		if reporter is not None:
			reporter.waiting("waiting for the historian to be ready (%d/%d): %s"
			                 % (attempt + 1, attempts, why[:90]), attempt * waitSeconds)
		Thread.sleep(waitSeconds * 1000)
	return result


def _freshHistory(reporter, maxAgeHours=3):
	"""Re-seed history if it stops short of now, then verify rows exist in the last `maxAgeHours`."""
	existing = historyRows(maxAgeHours)
	# The live engine opens a row for the current hour; counting those called an empty history current.
	if existing and drawableHistory():
		return "already current (%d rows in the last %d hours)" % (existing, maxAgeHours)
	stale = historyRows(24 * 365)
	if stale:
		reporter.waiting("history stops short of now - regenerating it", 0)
	if _isOee():
		result = launchpad.oee.seedHistory()
	else:
		# force: the window has moved on, so a non-forced pass leaves the recent end empty.
		result = _backfillWhenReady(reporter, force=bool(stale))
	if not historyRows(maxAgeHours):
		raise Exception("history still has no rows inside the last %d hours after "
		                "seeding" % maxAgeHours)
	return result


def _initTables():
	if tablesPresent():
		return "already present"
	if _isOee():
		launchpad.oee.initTables()
	else:
		launchpad.init.initDashboard()
	return "created"


def _demoInitialised():
	"""True if the demo is seeded and running; SecondsElapsed is non-zero only once the engine has ticked."""
	# Not StartCounter: it is legitimately zero after a reset.
	try:
		v = system.tag.readBlocking([
		    "[%s]OEE/Demo/Line 1/ShiftOee/StartTime" % PROVIDER,
		    "[%s]OEE/Demo/Line 1/Plc/ProductionCounter" % PROVIDER,
		    "[%s]OEE/Demo/Line 1/ShiftOee/SecondsElapsed" % PROVIDER])
		return (v[0].value is not None
		        and (v[1].value or 0) > 0
		        and (v[2].value or 0) > 0)
	except:
		return False


def _shiftStartPublished():
	lines = launchpad.oee.getLineNames("[%s]OEE/Demo" % PROVIDER)
	if not lines:
		return False
	v = system.tag.readBlocking(
	    ["[%s]OEE/Demo/%s/Schedule/CurrentShiftStartTime" % (PROVIDER, lines[0])])[0]
	return v.value is not None


def check():
	"""Report what is and is not in place. Changes nothing."""
	report = {}

	def probe(name, fn):
		try:
			report[name] = fn()
		except:
			report[name] = "FAILED: %s" % traceback.format_exc().strip().split("\n")[-1]

	if launchpad.edition.isEdge():
		probe("edgeVisualization",
		      lambda: {"is": EDGE_VISUALIZATION, "ok": edgeVisualizationReady()})
	probe("database", lambda: {"name": _dbName(),
	                           "ok": databaseReady(_dbName())})
	probe("tagProvider", lambda: {"name": PROVIDER, "ok": providerReady()})
	probe("historian", lambda: {"name": launchpad.edition.historian(),
	                            "ok": historianReady()})
	probe("device", lambda: {"name": DEVICE, "state": deviceState(),
	                         "ok": deviceReady()})
	probe("scriptingProject", lambda: {
	    "is": scriptingProject(),
		# only OEE needs it; on a KPI-only gateway the setting is irrelevant
	    "ok": (not _isOee()
	           or scriptingProject() == scriptingProjectWanted())})
	probe("tags", lambda: {"probe": _probeTag(), "ok": tagsPresent()})
	probe("tagDefinitions", _tagResourceProbe)
	probe("tagValues", tagReading)
	probe("tables", lambda: {"ok": tablesPresent()})
	probe("shifts", lambda: {"ok": shiftsEnabled()})
	probe("history", _historyProbe)
	probe("project", lambda: {"is": system.project.getProjectName(),
	                          "oee": _isOee(), "ok": True})

	report["ok"] = all(isinstance(v, dict) and v.get("ok", True)
	                   for k, v in report.items() if k != "ok")
	return report


def detail(report):
	"""Return one line per report item plus the summary, to show what is missing."""
	lines = []
	for name in sorted(report.keys()):
		if name in ("ok", "errors"):
			continue
		value = report[name]
		if isinstance(value, dict):
			state = "ok" if value.get("ok", True) else "MISSING"
			note = value.get("state") or value.get("is") or value.get("name") or ""
			lines.append("%s: %s%s" % (name, state, (" (%s)" % note) if note else ""))
		else:
			lines.append("%s: %s" % (name, str(value)[:70]))
	for err in report.get("errors", []):
		lines.append("error - %s" % err[:120])
	return "\n".join(lines + ["", summary(report)])


def _tagResourceProbe():
	"""Are the installed tag definitions the ones this build ships?"""
	stale = staleTagResources()
	if not stale:
		return {"ok": True, "state": "match this build"}
	return {"ok": False,
	        "count": len(stale),
	        "files": stale[:6],
	        "state": "%d tag file(s) are older than this build - the simulator is "
	                 "running the definitions it was installed with. Reinstall them "
	                 "with the Update tags action, then restart the gateway "
	                 "(a reinstall alone leaves the previous script subscribed too)."
	                 % len(stale)}


def _historyProbe():
	"""Report whether history is fresh, stale or absent."""
	rows = historyRows(24)
	if rows is None:
		return {"ok": False, "state": "could not be read"}
	if drawableHistory() == 0:
		return {"ok": False,
		        "state": "only the hour in progress (%d row(s)) - nothing for the "
		                 "charts to draw. Press Set up to rebuild the demo "
		                 "history." % rows}
	if rows == 0:
		return {"ok": False, "state": "nothing in the last 24 hours - press Set up "
		                              "to rebuild the demo history (it replaces the "
		                              "shift and hour tables, and keeps what is "
		                              "there if the rebuild fails)"}
	return {"ok": True, "state": "%d rows in the last 24 hours" % rows}


def summary(report):
	"""One line a human can read, from either run() or check()."""
	if report.get("ok"):
		return "everything is in place"
	missing = [k for k, v in report.items()
	           if isinstance(v, dict) and not v.get("ok", True)]
	if missing:
		return "not ready: %s" % ", ".join(sorted(missing))
	return "; ".join(report.get("errors", ["failed"]))
