"""
launchpad.edition - what this gateway can actually do.

The demo ships in two builds, standard and Edge, and the difference is not
cosmetic. Ignition Edge loads no SQL Bridge, no JDBC driver module and no SQL
historian, so it has NO database connectivity at all - `system.db.*` has
nothing to run against, and a named-query binding cannot run there either.

Everything that follows from that is a RUNTIME branch decided here, so the two
zips differ in exactly one thing: the tag provider name, which is substituted
at build time because a tag path is a literal.

Nothing here raises. A gateway that will not answer is treated as the smaller
of the two - "no database" - because that path works everywhere.
"""

LOG = system.util.getLogger("launchpad.edition")

# The edition of a gateway and the modules it loads cannot change while it is
# running, and these are asked from view bindings that re-evaluate on a timer,
# so the answers are cached for the life of the module. A project scan reloads
# it, which is the only event that could make one stale.
_CACHE = {}


def _hasResourceType(module, typeId):
	"""Is a config resource type registered on this gateway?

	Catching java.lang.Throwable as well as Exception is deliberate: a Java
	error raised inside a system call is not an Exception in Jython and would
	walk straight past an `except Exception`.
	"""
	from java.lang import Throwable as JThrowable
	key = (module, typeId)
	if key in _CACHE:
		return _CACHE[key]
	try:
		answer = key in system.config.getResourceTypes()
	except (JThrowable, Exception):
		LOG.warn("could not read this gateway's resource types - "
		         "assuming '%s' is absent" % typeId)
		answer = False
	_CACHE[key] = answer
	return answer


def isEdge():
	"""Is this an Ignition Edge gateway?

	Asked of the ONE type only Edge registers: ('ignition',
	'edge-sync-settings').

	It is NOT 'edge-system-properties' - a standard gateway registers that too,
	so a detector built on it fires everywhere and every Edge branch runs in
	the wrong place. Measured by diffing both editions on 8.3.8: 60 registered
	types on standard, 55 on Edge, and exactly one of them Edge-only.
	"""
	return _hasResourceType("ignition", "edge-sync-settings")


def hasDatabase():
	"""Can this gateway hold a database connection at all?

	A question about the PLATFORM, not about whether a connection has been
	configured. 'database-connection' is one of the types that exist on
	standard and not on Edge.
	"""
	return _hasResourceType("ignition", "database-connection")


def historian():
	"""The tag historian this gateway stores history in.

	Edge has exactly one, made by the platform and named in its own settings
	resource (Edge Historian, unless a site renamed it); everywhere else this
	demo makes its own. There is no historian-provider CONFIG RESOURCE on Edge
	- the provider is implicit - so the name is read from the Edge settings
	rather than by enumerating providers, which returns nothing there.
	"""
	from java.lang import Throwable as JThrowable
	if not isEdge():
		return "launchpad"
	try:
		found = list(system.config.getResources(
			moduleId="ignition", typeId="edge-system-properties"))
		if found:
			cfg = system.util.jsonDecode(
				system.util.jsonEncode(found[0].getConfig()))
			name = cfg.get("historianName")
			if name:
				return name
	except (JThrowable, Exception):
		pass
	return "Edge Historian"


def describe():
	"""One line for the Settings screen, and for the status endpoint."""
	if isEdge():
		return (u"Ignition Edge - no database on this edition, so the OEE "
		        u"records are kept in the gateway's own data directory")
	if not hasDatabase():
		return (u"this gateway has no database module - the OEE records are "
		        u"kept in the gateway's own data directory")
	return u"standard Ignition - the OEE records are SQL"
