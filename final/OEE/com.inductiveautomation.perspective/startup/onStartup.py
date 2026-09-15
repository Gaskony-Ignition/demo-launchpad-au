def onStartup(session):
	lineFolderPath = launchpad.oee.BASE_TAG_FOLDER
	session.custom.launchpad.oee.lineTagFolder = lineFolderPath 
	lines = launchpad.oee.getLineNames(lineFolderPath) 

	session.custom.launchpad.oee.lines = lines
	session.custom.launchpad.oee.selectedLine = ""
	if len(lines)>0:
		session.custom.launchpad.oee.selectedLine = lines[0]
		