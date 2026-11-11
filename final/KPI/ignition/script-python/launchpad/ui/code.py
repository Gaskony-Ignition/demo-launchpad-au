"""Appearance options for the Settings page theme dropdown."""


def themeOptions():
	"""Return dropdown options: the six stock themes, then the gateway's custom themes."""
	# `light` and `dark` are not config resources, so the stock six are fixed rather than listed.
	from java.lang import Throwable as JThrowable
	stock = [u"light", u"light-warm", u"light-cool",
	         u"dark", u"dark-warm", u"dark-cool"]
	extra = []
	try:
		for res in system.config.getResources(
		        moduleId="com.inductiveautomation.perspective", typeId="themes"):
			name = unicode(res.getName())
			if name not in stock and name not in extra:
				extra.append(name)
	except (JThrowable, Exception) as exc:
		# Jython's `except Exception` does not catch a Java Error.
		system.util.getLogger("launchpad.ui").warn(u"theme listing failed: %s" % exc)
	return [{u"value": n, u"label": n.replace(u"-", u" ").capitalize()}
	        for n in stock + sorted(extra)]
