def handleScheduleEvent():
	# Keeps the demo honest between Setup presses. healAnchors only writes when an
	# interval's anchor is provably wrong, so on a healthy gateway this does nothing.
	logger = system.util.getLogger("launchpad.oee.selfHeal")
	launchpad.oee.healAnchors(logger)
