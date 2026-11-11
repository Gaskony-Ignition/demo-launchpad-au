"""Which edition this gateway is (standard or Ignition Edge) and what it can do.

Edge has no database connectivity, so the two builds branch at runtime on the checks here.
Nothing raises: a gateway that will not answer is treated as "no database".
"""

LOG = system.util.getLogger("launchpad.edition")

# Cached: these are asked from timer-driven bindings and cannot change while the gateway runs.
_CACHE = {}


def _hasResourceType(module, typeId):
	"""Is a config resource type registered on this gateway?"""
	# Jython's `except Exception` does not catch a Java Error.
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
	"""Is this an Ignition Edge gateway?"""
	# 'edge-sync-settings' is the only Edge-only type; standard registers 'edge-system-properties' too.
	return _hasResourceType("ignition", "edge-sync-settings")


def hasDatabase():
	"""Can this gateway hold a database connection at all (platform, not configuration)?"""
	return _hasResourceType("ignition", "database-connection")


def historian():
	"""Return the historian name: Edge's own (from its settings), else "launchpad"."""
	# Edge has no historian config resource, so enumerating providers returns nothing.
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
	"""Return one line describing the edition, for the Settings screen and status endpoint."""
	if isEdge():
		return (u"Ignition Edge - no database on this edition, so the OEE "
		        u"records are kept in the gateway's own data directory")
	if not hasDatabase():
		return (u"this gateway has no database module - the OEE records are "
		        u"kept in the gateway's own data directory")
	return u"standard Ignition - the OEE records are SQL"
