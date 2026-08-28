"""Build this gateway from nothing, from a button in the running session.

Everything a fresh gateway needs that is not the project itself: the database
connection, the tag provider, the historian, the simulator device and its programme,
the gateway scripting project, the tags, and then the seeding. All of it is reachable
from gateway scope, so none of it needs a Designer, an SSH session or a curl loop.

Two entry points:

    run(progress=None, force=False)   build everything that is missing
    check()                           report what is and is not in place, change nothing

Both are idempotent. `run` creates only what is absent unless `force` is set; `check`
writes nothing at all. The WebDev endpoint and the Setup button both call these, so
there is one implementation and not two that drift.

A note on the database. Each project ships its own SQLite file -- ${data}/OEE.db and
${data}/KPI.db -- on purpose:
the schema is SQLite DDL, and a self-contained demo should not need a database server.
A SQLite connection needs no credentials, which is why setup can create it outright
rather than asking. If you want the demo on Postgres or MSSQL you need portable DDL
first -- pointing it at an existing connection is not enough, and the failure would be
a half-built schema rather than a clean error.
"""
import json
import os
import traceback

LOG = system.util.getLogger("launchpad.setup")

RESOURCES = "data/config/resources"
CORE = "core/ignition"
HISTORIAN_MODULE = "core/com.inductiveautomation.historian"
OPCUA_MODULE = "core/com.inductiveautomation.opcua"

# Each project gets its OWN SQLite database, named after the project, so a
# glance at the gateway's connection list says which project a database belongs
# to (Nigel, 28/08/2026). They used to share one called "Examples", which told
# a user nothing and tied the two projects together for no reason -- OEE keeps
# its own SQL tables and KPI keeps tag history, and neither reads the other's.
#
# HISTORY_DATABASE is KPI's, always. The tag historian is ONE gateway provider
# called "launchpad" and can point at only one database, all 61 historised tags
# are KPI's, and OEE has none at all -- so the historian belongs to KPI and OEE
# does not create or touch it. Having each project point the shared provider at
# its own database would mean whichever installed last silently broke the
# other's history.
HISTORY_DATABASE = "KPI"

# The SQLite URL, and both parameters are load-bearing rather than tuning.
#
# journal_mode=WAL: this application writes CONTINUOUSLY while sessions read --
# the simulator's gateway timer writes the OEE tables and the historian writes
# its partition, both while Perspective pages query them for every chart on
# screen. Under SQLite's default rollback journal a writer blocks every reader
# for the length of the write, so the symptom is a chart that stalls in front of
# whoever you are demonstrating to. WAL lets readers carry on against the last
# committed state. It is a property of the FILE, not the connection, so setting
# it here converts an existing database file the first time it connects.
#
# busy_timeout=30000: the one case WAL does not cover is two writers, and this
# has two (the OEE timer and the historian). Without it the loser of that race
# fails immediately with SQLITE_BUSY rather than waiting its turn.
#
# Verified on a blank gateway 28/08/2026: without these, PRAGMA journal_mode on
# the created file reads `delete`.
def _dbName():
    """This project's own database: "OEE" or "KPI"."""
    return "OEE" if _isOee() else "KPI"


def _connectURL(name=None):
    """The SQLite URL for a database of this name."""
    return ("jdbc:sqlite:${data}/%s.db?journal_mode=WAL&busy_timeout=30000"
            % (name or _dbName()))
PROVIDER = "launchpad"
HISTORIAN = "launchpad"
DEVICE = "Launchpad"
SCRIPTING_PROJECT = "OEE"


def _isOee():
    """Which of the two projects this copy is running in.

    This file is byte-identical in OEE and in KPI on purpose -- two copies of a
    gateway builder drift, and the half that drifts is the half nobody runs. The
    project-specific parts are the seeding steps and the tag probe, and both are
    decided here rather than by maintaining two files.
    """
    return hasattr(launchpad, "oee")


def _lib():
    return launchpad.oee if _isOee() else launchpad.init


def _db():
    return _lib().db()


def _probeTag():
    """A tag that only exists once this project's tags are imported.

    Distinguishes "tags present" from "provider exists but empty", which look
    identical if you only browse the provider root.
    """
    if _isOee():
        return "[%s]OEE/Demo/Line 1/Enabled" % PROVIDER
    return "[%s]KPI/Lines/Line1/ProductionRate" % PROVIDER


# --------------------------------------------------------------- small helpers

def _emit(progress, message):
    LOG.info(message)
    if progress is not None:
        try:
            progress(message)
        except:
            pass  # a broken progress sink must never fail the install


class _Report:
    """Builds the running transcript the Setup button shows while it works.

    The button used to replace its label with the current step, which gives a user
    two things they cannot act on: no idea what has already succeeded, and no idea
    whether a step that is taking a while is working or wedged. On a bare gateway one
    step waits up to 90 seconds and said nothing at all for the whole of it, so the
    honest reading of the screen was "it has stopped". Every step now leaves a line
    behind with its result on it, and anything that waits says what it is waiting for
    and for how long.
    """

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
        self.current = message
        LOG.info(message)
        self._flush("... %s" % message)

    def waiting(self, message, seconds):
        self._flush("... %s (%ds)" % (message, seconds))

    def done(self, outcome):
        if self.current:
            self.lines.append("[ok]   %s%s" % (self.current,
                (" - %s" % outcome) if outcome else ""))
            self.current = None
        self._flush()

    def failed(self, why):
        if self.current:
            self.lines.append("[FAIL] %s - %s" % (self.current, why))
            self.current = None
        self._flush()

    def note(self, message):
        self.lines.append("       %s" % message)
        self._flush()

    def finish(self, ok, summaryLine):
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
        WORDS = {"shiftRows": None,                 # handled below
                 "tagsWritten": "tags written",
                 "healed": "interval(s) re-anchored",
                 "state": None}
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
    """Turn a Jython traceback into something the person reading it can act on.

    The raw last line of a Jython traceback is frequently useless to a user -- the
    one that sent this function into existence was

        AttributeError: 'com.inductiveautomation.ignition.common.script.Scr' object
        has no attribute 'payload'

    which is Ignition's way of saying a project script resource did not load. Nothing
    about that tells you to re-import the project, and it was displayed with no
    indication of which step had produced it.
    """
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
    """Write a gateway config resource. Returns the directory it landed in.

    `extra` is a list of (filename, content, binary) for resources that carry more
    than config.json -- the simulator device carries its programme alongside it, and
    a resource.json that does not list every file makes the gateway ignore the lot.
    """
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
    """Register config resources written above.

    This is NOT the project scan. The gateway has two identically labelled "Scan File
    System" buttons and running the wrong one does nothing at all, silently -- so this
    goes through the configuration manager, not system.project.requestScan().
    """
    from com.inductiveautomation.ignition.gateway import IgnitionGateway
    cm = IgnitionGateway.get().getConfigurationManager()
    before = str(cm.getScanInformation())
    cm.requestScan()
    # requestScan is ASYNCHRONOUS. Anything that depends on the scan having finished
    # -- restarting the tag provider, reading a tag that was just written -- acts on
    # the state from before the scan unless it waits for the reading to move. That is
    # the whole reason the second project's tags appeared to need a human to press
    # Scan File System: the scan was fine, the code just did not wait for it.
    # (scanSynchronous is not the synchronous form of this; it takes a Runnable to
    # run under the scan lock.)
    _waitFor(lambda: str(cm.getScanInformation()) != before, 90, 1)
    return True


def _waitFor(test, seconds=60, interval=2, report=None, what=None):
    """Poll until `test()` is true. Returns whether it became true.

    A fixed sleep is the usual way this is written and it is wrong in both directions:
    too short on a loaded gateway, and needlessly slow on a quick one.

    Pass `report` and `what` for anything a user is waiting on. A wait that prints
    nothing is indistinguishable from a hang, and this one can last 90 seconds.
    """
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


# --------------------------------------------------------------- state probes

def databaseReady(name=None):
    """Whether the connection exists AND answers. Existing but faulted reads as no."""
    try:
        system.db.runScalarQuery("SELECT 1", database=(name or _db()))
        return True
    except:
        return False


def providerReady():
    """Whether the tag provider exists.

    Not a browse: system.tag.browse against a provider that does not exist returns an
    empty result rather than raising, so a browse-based probe reports every bare
    gateway as healthy. The config resource on disk is the thing that actually
    determines whether the provider is there.
    """
    return os.path.exists(os.path.join(
        _abs(RESOURCES), CORE, "tag-provider", PROVIDER))


def expectedLines():
    """How many demo lines this build ships, read from the payload it installs.

    Not a constant: the number is already stated once, in the tag definitions, and a
    second statement of it here is a thing to forget when a line is added.
    """
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
    """How many line instances the tag system will actually hand back right now.

    A UDT instance is not browsable the instant its file lands: the scan works
    through the tree, and a browse taken mid-scan returns however many have been
    built so far. Every seeding step below iterates this list, so a browse taken one
    second early seeds a subset -- and says nothing about it.
    """
    try:
        return len(_lib().getLineNames(_lib().BASE_TAG_FOLDER))
    except:
        return 0


def linesReady():
    want = expectedLines()
    return want > 0 and linesBrowsable() >= want


def tagsPresent():
    try:
        return bool(system.tag.exists(_probeTag()))
    except:
        return False


def tagReading():
    """Whether the probe tag has a good value, not merely a definition.

    Imported tags exist immediately; they only carry values once the device is
    running and the scan class has ticked. The difference matters because a seeder
    that centres its generated band on the live value silently skips every tag that
    reads null -- reporting success while writing nothing.
    """
    try:
        paths = [_probeTag()]
        if _isOee():
            # Enabled being good says the tags installed; it says nothing about whether
            # the demo is actually running. A null production counter stops the
            # simulator script dead for every line while every other probe here stays
            # green -- so the counter is part of the probe, not just the definition.
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
    return os.path.exists(os.path.join(
        _abs(RESOURCES), HISTORIAN_MODULE, "historian-provider", HISTORIAN))


def deviceState():
    """The simulator's connection state, or None if the gateway has no such device.

    "Exists" is not the same as "connected": a device that is present but faulted
    leaves every OPC tag stale, which reads downstream as an empty historian rather
    than as a device problem.
    """
    try:
        devices = system.device.listDevices()
        for row in range(devices.getRowCount()):
            if devices.getValueAt(row, "Name") == DEVICE:
                return str(devices.getValueAt(row, "State"))
    except:
        pass
    return None


def deviceReady():
    # a simulator reports Running, a real driver reports Connected -- both are healthy,
    # and only Connected would report every working simulator as broken
    return deviceState() in ("Connected", "Running")


def scriptingProject():
    """The gateway's configured scripting project, or None if it cannot be read."""
    try:
        p = os.path.join(_abs(RESOURCES), CORE, "system-properties", "config.json")
        return system.util.jsonDecode(_read(p)).get("gatewayScriptingProject")
    except:
        return None


def tablesPresent():
    """Whether this project's own tables exist.

    tableExists goes through the gateway's metadata provider, so it answers for any
    connection type -- a "SELECT FROM sqlite_master" probe throws on Postgres and
    reports a healthy gateway as broken.
    """
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
    """OEE hour rows that predate the hour in progress. None if it cannot be read.

    The live engine opens a row per line for the current hour as soon as it starts
    running, so a gateway with no demo history at all still counts seven rows and
    looks current to any probe that just counts. That is not a subtle distinction:
    it is the difference between a Line View with a full day of trend on it and one
    with nothing, and it defeated both the seeder's "is it already current" guard and
    the check that was supposed to notice. Everything the charts and the summary
    tables draw is older than the hour in progress, so count that instead.
    """
    if not _isOee():
        # Same trap on the KPI side, and waiting for the historian to settle before
        # seeding is what exposed it: by then the historian has recorded a couple of
        # live samples of its own, so "rows exist" went true and setup skipped the
        # backfill entirely -- reporting "already current (2 rows)" on a gateway with
        # no seeded history at all. A properly seeded window holds one sample per tag
        # every fifteen minutes, so it cannot have fewer rows than there are tags.
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
        return system.db.runScalarPrepQuery(
            "SELECT COUNT(*) FROM ex_launchpad_oee_hour WHERE hour_timestamp < ?",
            [hourStart], database=_db())
    except:
        return None


def historyRows(withinHours=24):
    """How many history rows land inside the last `withinHours`.

    Counting against a BOUND date rather than reading MAX() back and converting it:
    the timestamp columns come back from the driver as whatever it feels like (the
    OEE hour table declares utc_timestamp INTEGER and the generator writes Dates into
    it), so any probe that parses a returned timestamp reports a healthy gateway as
    empty. Binding a Date into the comparison is the same path the named queries use
    at read time, and it is the thing that actually has to work.
    """
    try:
        since = system.date.addHours(system.date.now(), -withinHours)
        if _isOee():
            return system.db.runScalarPrepQuery(
                "SELECT COUNT(*) FROM ex_launchpad_oee_hour WHERE hour_timestamp >= ?",
                [since], database=_db())
        drvIds = launchpad.init._driverIds()[1]
        total = 0
        # _partitions returns tuples of (name, startMs, endMs), not dicts
        for name, startMs, endMs in launchpad.init._partitions(drvIds):
            total += system.db.runScalarPrepQuery(
                "SELECT COUNT(*) FROM %s WHERE t_stamp >= ?" % name,
                [system.date.toMillis(since)], database=_db())
        return total
    except:
        return None


def shiftsEnabled():
    """A roster that covers the day is what stops Performance dividing by zero."""
    try:
        if not _isOee():
            return True  # the roster belongs to OEE; KPI has no shifts of its own
        lines = launchpad.oee.getLineNames("[%s]OEE/Demo" % PROVIDER)
        if not lines:
            return False
        # ShiftEnabled, not Enabled: the line itself has an Enabled tag, and reading
        # that one instead reports a roster that was never written as healthy
        paths = ["[%s]OEE/Demo/%s/Schedule/1/ShiftEnabled" % (PROVIDER, lines[0])]
        qv = system.tag.readBlocking(paths)[0]
        return bool(qv.quality.isGood() and qv.value)
    except:
        return False


# --------------------------------------------------------------- build steps

def existingDatabase():
    """What a connection already under this project's name actually is.

    Returns "absent", "ours" for the SQLite one these projects are written against,
    or the translator name of whatever else is sitting under that name.

    A connection that cannot be read counts as NOT ours. Refusing costs a person one
    message telling them exactly what to look at; guessing wrong costs them a
    half-created schema in a database they chose.
    """
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
    """Create the SQLite connection the projects are written against.

    No credentials are involved, which is the whole reason this can be automated: a
    Postgres or MSSQL connection would need a password nobody can supply from here.

    Nothing here needs a connection to exist first -- on a gateway with no database
    connections at all this is what makes the first one.
    """
    kind = existingDatabase()
    if kind not in ("absent", "ours"):
        # databaseReady only asks whether the name answers SELECT 1, so a gateway
        # that already has a connection under this name pointing at Postgres reads as
        # ready and every later step would run SQLite DDL against it -- half-building
        # a schema in somebody else's database instead of stopping. The README has
        # always said this does not happen; this is what makes that true.
        # Kept short on purpose: _explain truncates a step's message at 180
        # characters, and the half that matters is the instruction, not the reason.
        raise Exception(
            "a connection called '%s' already exists here and is %s, not SQLite. "
            "This schema is SQLite DDL. Rename or remove it, then press Set up again"
            % (_dbName(), kind))
    if kind == "ours" and databaseReady(_dbName()) and not force:
        # A connection made by an older release is SQLite and answers SELECT 1, so
        # it reads as fine -- but it carries the parameterless URL and the file is
        # still on the rollback journal. Returning "already connected" there would
        # leave the stall in place on exactly the gateways that have been running
        # longest.
        if existingConnectURL() == _connectURL():
            return "already connected"
        # Repair the URL and NOTHING else. This connection is almost certainly the
        # one this project created, but "almost certainly" is not a licence to
        # rewrite a resource wholesale: a config.json written from the dict below
        # would also reset every pool and eviction setting, so anyone who had tuned
        # poolMaxActive on a busy gateway would lose it silently to an upgrade they
        # asked for on other grounds. The create path already refuses to overwrite
        # a connection it does not recognise; a repair path has no business being
        # more invasive than the create path it is repairing. Patch the one key
        # that is wrong and leave the rest of the file exactly as found.
        existing = _readConfig(CORE, "database-connection", _dbName())
        if existing is not None:
            existing["connectURL"] = _connectURL()
            _configResource(CORE, "database-connection", _dbName(), existing,
                            "SQLite database for the Launchpad OEE + KPI example "
                            "resources")
            return "updated"
        # Unreadable config.json: fall through and write a known-good one rather
        # than leaving a connection nobody can repair.
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
    """A config resource's config.json as a dict, or None if absent/unreadable.

    Used to change one key of an existing resource without rewriting the others.
    """
    p = os.path.join(_abs(RESOURCES), module, kind, name, "config.json")
    if not os.path.exists(p):
        return None
    try:
        return system.util.jsonDecode(_read(p))
    except:
        return None


def existingConnectURL():
    """The connectURL of this project's connection as it stands, or "" if there is
    no readable one. Used to tell an up-to-date connection from an older
    release's, which are otherwise indistinguishable -- both are SQLite and both
    answer SELECT 1."""
    p = os.path.join(_abs(RESOURCES), CORE, "database-connection", _dbName(),
                     "config.json")
    if not os.path.exists(p):
        return ""
    try:
        return str(system.util.jsonDecode(_read(p)).get("connectURL") or "")
    except:
        return ""


def ensureTagProvider(force=False):
    if providerReady() and not force:
        return "already present"
    config = launchpad.payload.tagProvider()
    config["settings"]["defaultDatasourceName"] = _dbName()
    _configResource(CORE, "tag-provider", PROVIDER, config,
                    "Tag provider for the Launchpad OEE + KPI example resources")
    return "created"


def ensureHistorian(force=False):
    if historianReady() and not force:
        return "already present"
    config = launchpad.payload.historian()
    config["settings"]["database"] = HISTORY_DATABASE
    _configResource(HISTORIAN_MODULE, "historian-provider", HISTORIAN, config,
                    "Tag historian for the Launchpad OEE + KPI example resources")
    return "created"


def ensureDevice(force=False):
    """The programmable simulator, including its programme.

    Without the programme every KPI tag reads stale -- the device exists, the tags
    resolve, and nothing ever changes, which looks like a broken historian.
    """
    if deviceReady() and not force:
        return "already present"
    _configResource(OPCUA_MODULE, "device", DEVICE,
                    launchpad.payload.device(),
                    "Programmable simulator driving the Launchpad example tags",
                    extra=[("instructions.csv",
                            launchpad.payload.instructions(), True)])
    return "created"


def ensureScriptingProject(force=False):
    """Point the gateway's scripting project at OEE.

    The OEE UDT event scripts call launchpad.oee.* and resolve it from this
    setting. Until it is right nothing computes, every OEE figure sits at zero, and
    the gateway logs nothing to say why -- it is the single most confusing way for
    this resource to be broken.

    Two things it will not do. It will not point the gateway at OEE when OEE is not
    installed -- KPI has no tag-scope scripts and does not need this at all. And it
    will not take the setting off another project: this is a gateway-wide setting, so
    on a gateway that already uses it for something else, silently claiming it would
    break that other project's tag events. Both cases are reported, not performed.
    """
    if scriptingProject() == SCRIPTING_PROJECT and not force:
        return "already %s" % SCRIPTING_PROJECT
    if not os.path.exists(os.path.join(_abs("data/projects"), SCRIPTING_PROJECT)):
        return "not needed - the %s project is not installed" % SCRIPTING_PROJECT
    current = scriptingProject()
    if current and current != SCRIPTING_PROJECT and not force:
        return ("left alone - this gateway already uses '%s'; set it to %s by hand if "
                "the OEE demo is meant to own it" % (current, SCRIPTING_PROJECT))
    d = os.path.join(_abs(RESOURCES), CORE, "system-properties")
    cfgPath = os.path.join(d, "config.json")
    if not os.path.exists(cfgPath):
        return "system-properties resource missing - set it by hand"
    cfg = system.util.jsonDecode(_read(cfgPath))
    cfg["gatewayScriptingProject"] = SCRIPTING_PROJECT
    _write(cfgPath, system.util.jsonEncode(cfg))
    # rewrite the sibling resource.json in place: it carries attributes we did not
    # write and must not lose, and a stale signature makes the scan skip the file
    resPath = os.path.join(d, "resource.json")
    if os.path.exists(resPath):
        res = system.util.jsonDecode(_read(resPath))
        attrs = res.get("attributes", res)
        if "lastModificationSignature" in attrs:
            del attrs["lastModificationSignature"]
        attrs["lastModification"] = {"actor": "launchpad-setup", "timestamp": _stamp()}
        _write(resPath, system.util.jsonEncode(res))
    return "set to %s" % SCRIPTING_PROJECT


def ensureTags(force=False):
    """Install the tags as gateway config resources, then scan them in.

    Deliberately NOT system.tag.configure. The runtime API looks tidier and cost a
    day: configuring a subtree at the provider root takes the provider's other
    subtrees with it, so installing KPI's tags silently removed OEE's -- on disk the
    definitions were still there, at runtime every path read Bad_NotFound. Writing
    the resource files and running a config scan is what the shell installer has
    always done, and it composes: each project installs only its own paths.

    UDT types come along in the same tree, under tag-type-definition rather than
    tag-definition, which is what puts them in the type namespace instead of leaving
    a tag folder literally called _types_ and every instance typeless.
    """
    if tagsPresent() and not force:
        return "already present"
    base = os.path.join(_abs(RESOURCES), CORE)
    written = 0
    for rel, text in launchpad.payload.tagFiles().items():
        dest = os.path.join(base, *rel.split("/"))
        parent = os.path.dirname(dest)
        if not os.path.exists(parent):
            os.makedirs(parent)
        _write(dest, text)
        written += 1
    # Scan, then wait, then scan again if needed. requestScan does pick these up --
    # verified with a throwaway nested tag folder -- but it is asynchronous and a
    # request made while the gateway is still working through the previous scan does
    # nothing at all. That is exactly the second project's situation: its setup runs
    # moments after the first one's, so a single fire-and-hope scan is the difference
    # between "tags imported" and "tags sitting on disk reading Bad_NotFound".
    for attempt in range(6):
        _configScan()
        if _waitFor(tagsPresent, 20, 2):
            return "installed %d resources" % written
    raise Exception("tags did not appear at %s after %d scans" % (_probeTag(), 6))
    return "installed %d resources" % written


def staleTagResources():
    """Which installed tag resources differ from the ones this build ships.

    The simulator's counter script lives in a tag definition, and `run` will not
    reinstall tags -- installing them over a live subscription leaves the previous
    definition's script subscribed as well, so the counter runs twice per tick. The
    consequence is easy to miss and was: a fix to that script cannot reach a gateway
    that already has the tags, and every other probe here still reports the gateway
    healthy. A demo shipped running a third above its own target rate with a green
    setup report and a green check.

    Comparing the files on disk against what this build would write catches any
    drift, not just a version bump, and needs nothing added to the tag schema. A
    gateway installed from an earlier package shows every file as differing; one
    installed from this build shows none.
    """
    base = os.path.join(_abs(RESOURCES), CORE)
    stale = []
    for rel, text in launchpad.payload.tagFiles().items():
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

    step("database", lambda: ensureDatabase(force), "creating the database connection")
    # The database is the one step nothing else may run past. Every resource below
    # names it -- the tag provider's default datasource, the historian's store -- so
    # carrying on after it fails leaves three resources pointing at whatever WAS
    # under that name, which for the case ensureDatabase refuses (someone else's
    # Postgres) is precisely the harm it refuses in order to avoid.
    if report.get("database") == "FAILED":
        reporter.note("stopping: nothing below can be built without the database")
        report["ok"] = False
        report["detail"] = reporter.finish(False, summary(report))
        return report

    step("tagProvider", lambda: ensureTagProvider(force), "creating the tag provider")
    # KPI only: the historian is one shared gateway provider pointing at ONE
    # database, every historised tag is KPI's, and OEE has none -- so OEE
    # creating it would either point it at a database with no history in it or,
    # worse, repoint KPI's away from its own. See HISTORY_DATABASE above.
    if not _isOee():
        step("historian", lambda: ensureHistorian(force), "creating the tag historian")
    step("device", lambda: ensureDevice(force), "creating the simulator device")
    step("scriptingProject", lambda: ensureScriptingProject(force),
         "setting the gateway scripting project")

    # Only scan when something was actually written. A config scan reloads the tag
    # definitions, which re-fires each interval's Enabled handler, and that handler
    # restamps StartTime and zeroes the run counters unconditionally -- so scanning
    # on every press threw away the shift in progress even when every step above had
    # just reported "already present". That is the whole of what made pressing Set up
    # a second time destructive; the steps themselves were already idempotent.
    # "FAILED" is a string that does not start with "already", so the first version of
    # this counted a failed step as a reason to scan -- and then waited 90 seconds for
    # a tag provider that could never appear, printing nothing the whole time.
    written = [name for name in ("database", "tagProvider", "historian", "device",
                                 "scriptingProject")
               if isinstance(report.get(name), str)
               and report[name] != "FAILED"
               and not report[name].startswith("already")]
    if report.get("errors"):
        # nothing below can work without these, and the 90s wait below would only
        # dress the failure up as a timeout
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

    # Tags are NOT reinstalled by a plain force. Installing the resources over
    # themselves leaves the previous definition's tag event script subscribed as
    # well as the new one, so the simulator's counter runs twice per tick, then
    # three times, and the demo produces at a multiple of its target rate until the
    # gateway restarts. Removing the files first was tried and measured: it does not
    # drop the old subscription, it adds another. So pressing Setup again is always
    # safe, and reinstalling tags has to be asked for by name (tags=1) -- after
    # which the gateway wants a restart.
    step("tags", lambda: ensureTags(force and tags), "importing the tags")
    if not tagsPresent():
        # every seeding step below reads tags. Carrying on produces a page of
        # confusing downstream failures instead of the one that matters.
        report.setdefault("errors", []).append(
            "tags are not present - seeding skipped")
        report["ok"] = False
        reporter.note("tags did not import - stopping")
        report["detail"] = reporter.finish(False, summary(report))
        return report

    # Every seeding step below iterates the line list, and the line list comes from a
    # tag BROWSE. tagsPresent() only asks whether one tag inside one line exists, so
    # it goes true the moment the first instance is built -- while the scan is still
    # working through the rest. Seeding then ran against four lines of seven and
    # reported "36 tags written" and five thousand history rows, both of which read
    # like success. Wait for the whole set, and if it never arrives say which number
    # was reached rather than quietly seeding a subset.
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
    # Pressing Set up on a gateway that is already running the demo should not throw
    # it back to zero. A full reset is what a bare gateway needs and what a working
    # one least wants -- so re-anchor whatever is actually wrong, and keep the reset
    # for the case it was written for.
    if _demoInitialised():
        step("demoTags", lambda: launchpad.oee.healAnchors(LOG),
             "checking the demo counters")
    else:
        step("resetDemoTags", launchpad.oee.resetDemoTags,
             "zeroing the counters")
        # initDemoTags reads the current shift start, which the schedule expressions
        # only publish once they have ticked. Poll for it rather than sleeping 45s.
        reporter.waiting("waiting for the shift schedule to publish", 0)
        _waitFor(_shiftStartPublished, 90, report=reporter,
                 what="waiting for the shift schedule to publish")
        step("demoTags", launchpad.oee.initDemoTags,
             "seeding the demo counters")


def _backfillWhenReady(reporter, attempts=16, waitSeconds=15, force=False):
    """Seed KPI history, once there is somewhere to put it AND something to put there.

    Two separate things have to be true, and only the first was being waited for.

    A sample can only be written where a history partition already exists, and the
    historian creates its first one when it first records. On a gateway built from
    nothing that is a minute away, so an immediate backfill reports "no partition
    covers the requested window" and seeds nothing.

    The second is subtler and got through: a tag only appears in the historian's tag
    table once it has recorded its first value, and the backfill seeds the tags it
    finds there. Run seconds after the tags are installed, it finds almost none --
    measured on a fresh gateway it found exactly one, a string tag it then correctly
    skipped, and returned `rows: 0` with no error at all. That is a successful install
    with two days of missing history behind every KPI chart, and it reported ok.

    So "seeded nothing" is treated as not-ready-yet rather than as success.
    """
    from java.lang import Thread

    # Wait for the historian's tag count to STOP CLIMBING before seeding at all.
    # Seeding early does not merely under-fill: backfill's own guard then counts the
    # window as already seeded, so the tags that registered a moment later never get
    # history and no later run repairs it. Measured on a gateway where KPI's setup
    # ran first: one tag registered, 192 rows written, reported ok, and the other
    # fifty-seven tags stayed empty for good.
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
            # SQLite takes one writer at a time and the historian is recording while
            # this runs, so a bulk insert can lose the race. Retrying is right; failing
            # the install over a transient lock is not.
            why = traceback.format_exc().strip().split("\n")[-1]
            result = {"error": why}
        if reporter is not None:
            reporter.waiting("waiting for the historian to be ready (%d/%d): %s"
                             % (attempt + 1, attempts, why[:90]), attempt * waitSeconds)
        Thread.sleep(waitSeconds * 1000)
    return result


def _freshHistory(reporter, maxAgeHours=3):
    """Leave this gateway with history that runs up to now.

    Seeded history is a snapshot, not a subscription: it ends at the moment it was
    generated. A demo gateway that sat idle for a few days therefore has full, healthy,
    entirely historical tables -- and every chart and table whose window is "today"
    draws nothing. Since these projects are nearly always installed on a short-lived
    trial gateway that gets built, looked at, and thrown away, "seed it once at install
    and hope" is the wrong bargain: setup re-seeds whenever what is there has gone
    stale, and then verifies that it worked rather than assuming it.
    """
    existing = historyRows(maxAgeHours)
    # "rows exist" is not "there is something to draw": on OEE the live engine has
    # already opened a row per line for the hour in progress, and counting those made
    # this guard report the history current on a gateway whose tables held nothing
    # else. Setup then declined to rebuild, check told the user to press Setup, and
    # pressing it changed nothing -- with the tables empty the whole time.
    if existing and drawableHistory():
        return "already current (%d rows in the last %d hours)" % (existing, maxAgeHours)
    stale = historyRows(24 * 365)
    if stale:
        reporter.waiting("history stops short of now - regenerating it", 0)
    if _isOee():
        result = launchpad.oee.seedHistory()
    else:
        # force: the existing samples stop where the last run left off and the window
        # has moved on since, so a non-forced pass leaves the recent end empty
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
    """Has this gateway's demo already been seeded and left running?

    Both halves matter. A shift start time means the interval engine has run, and a
    counter above zero means the simulator is turning -- after a tag reinstall the
    counters are back at their shipped zero and the demo does need the full reset.
    """
    try:
        v = system.tag.readBlocking([
            "[%s]OEE/Demo/Line 1/ShiftOee/StartTime" % PROVIDER,
            "[%s]OEE/Demo/Line 1/Plc/ProductionCounter" % PROVIDER])
        return v[0].value is not None and (v[1].value or 0) > 0
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

    probe("database", lambda: {"name": DATABASE, "ok": databaseReady(_dbName())})
    probe("tagProvider", lambda: {"name": PROVIDER, "ok": providerReady()})
    probe("historian", lambda: {"name": HISTORIAN, "ok": historianReady()})
    probe("device", lambda: {"name": DEVICE, "state": deviceState(),
                             "ok": deviceReady()})
    probe("scriptingProject", lambda: {
        "is": scriptingProject(),
        # only OEE needs it; on a KPI-only gateway the setting is irrelevant
        "ok": (scriptingProject() == SCRIPTING_PROJECT
               or not os.path.exists(os.path.join(_abs("data/projects"), SCRIPTING_PROJECT)))})
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
    """One line per item, for a status label with room for more than a verdict.

    The one-line summary answers "is it ready"; this answers "what is missing", which
    is the question anyone actually has when the answer to the first one is no.
    """
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
    """Fresh, stale or absent -- "the tables exist" is not the same as "the charts
    have anything to draw", and only the second one is what anyone is asking."""
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
