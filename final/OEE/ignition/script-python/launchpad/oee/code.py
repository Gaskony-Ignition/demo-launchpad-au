"""OEE project library: demo tag setup, shift and hour records, history seeding and repair."""

DATABASE_NAME = "OEE"

def db():
	"""Return the database connection name; the launchpad.database global overrides the default."""
	return system.util.getGlobals().get("launchpad.database") or DATABASE_NAME

BASE_TAG_FOLDER = "[Launchpad]OEE/Demo"


# Column order must match the order `params` is appended in; do not sort.

HOUR_START_COLUMNS = [
	"utc_timestamp", "stat_timestamp", "shift", "line_name", "tag_folder",
	"day_timestamp", "hour_timestamp", "hour_of_day", "hour_seconds_elapsed",
	"hour_seconds_running", "hour_down_seconds", "hour_idle_seconds",
	"start_production_count", "raw_production_count", "hour_production_count",
	"start_reject_count", "raw_reject_count", "hour_reject_count",
	"outfeed_factor", "reject_factor", "target_rate", "rate_name",
	"hour_oee_a", "hour_oee_p", "hour_oee_q", "hour_oee", "hour_rates",
	"hour_timestamps",
]

HOUR_END_COLUMNS = [
	"utc_timestamp", "stat_timestamp", "raw_production_count",
	"raw_reject_count", "hour_oee", "hour_oee_a", "hour_oee_p", "hour_oee_q",
	"hour_oee_u", "hour_production_count", "target_production_count",
	"hour_reject_count", "hour_seconds_running", "hour_seconds_elapsed",
	"hour_down_seconds", "hour_idle_seconds",
]

SHIFT_START_COLUMNS = [
	"utc_timestamp", "stat_timestamp", "shift", "line_name", "tag_folder",
	"shift_start", "shift_end", "shift_seconds_elapsed",
	"shift_running_seconds", "shift_idle_seconds", "shift_down_seconds",
	"start_production_count", "raw_production_count", "shift_production_count",
	"start_reject_count", "raw_reject_count", "shift_reject_count",
	"outfeed_factor", "reject_factor", "target_rate", "rate_name",
	"shift_oee_a", "shift_oee_p", "shift_oee_q", "shift_oee", "shift_rates",
	"shift_timestamps",
]

SHIFT_END_COLUMNS = [
	"utc_timestamp", "stat_timestamp", "raw_production_count",
	"raw_reject_count", "shift_end", "shift_oee", "shift_oee_a", "shift_oee_p",
	"shift_oee_q", "shift_oee_u", "shift_production_count",
	"target_production_count", "shift_reject_count", "shift_running_seconds",
	"shift_seconds_elapsed", "shift_down_seconds", "shift_idle_seconds",
]

SHIFT_HISTORY_COLUMNS = [
	"utc_timestamp", "stat_timestamp", "shift", "line_name", "tag_folder",
	"shift_start", "shift_end", "shift_seconds_elapsed",
	"shift_running_seconds", "shift_down_seconds", "shift_idle_seconds",
	"start_production_count", "raw_production_count", "shift_production_count",
	"target_production_count", "start_reject_count", "raw_reject_count",
	"shift_reject_count", "outfeed_factor", "reject_factor", "target_rate",
	"rate_name", "shift_oee_a", "shift_oee_p", "shift_oee_q", "shift_oee",
	"shift_rates", "shift_timestamps",
]

HOUR_HISTORY_COLUMNS = [
	"utc_timestamp", "stat_timestamp", "shift", "day_timestamp",
	"hour_timestamp", "hour_of_day", "line_name", "tag_folder",
	"hour_seconds_elapsed", "hour_seconds_running", "hour_down_seconds",
	"hour_idle_seconds", "start_production_count", "raw_production_count",
	"hour_production_count", "target_production_count", "start_reject_count",
	"raw_reject_count", "hour_reject_count", "outfeed_factor", "reject_factor",
	"target_rate", "rate_name", "hour_oee_a", "hour_oee_p", "hour_oee_q",
	"hour_oee_u", "hour_oee", "hour_rates", "hour_timestamps",
]


def ntz(value):
	"""Return 0 for None, otherwise the value."""
	if value == None:
		return 0
	else:
		return value

def getTargetRateDataset(targetRateName,targetRate):
	"""Return a one-row target rate history dataset with zeroed seconds."""
	targetRateHeaders = ["RateName","RateValue", "SecondsElapsed", "SecondsRunning",  "SecondsFaulted", "SecondsIdle" ]
	targetRateHistory = system.dataset.toDataSet(targetRateHeaders, [[targetRateName,targetRate, 0,0,0,0 ]])
	return targetRateHistory

def getTargetProductionCount(targetRateHistory):
	"""Return target production: running minutes times rate, summed over the history rows."""
	targetProductionCount = 0
	for row in range(targetRateHistory.rowCount):

		targetProductionCount+= (targetRateHistory.getValueAt(row,"SecondsRunning")/60.0)  * targetRateHistory.getValueAt(row,"RateValue")

	return targetProductionCount
	
def getLineNames(lineFolderPath):
	"""Return the names of the OEE/LineConfig UDT instances in the folder."""
	results = system.tag.browse(lineFolderPath, {"typeId":"OEE/LineConfig", "tagType":"UdtInstance"})
	lines = []
	for result in results.getResults():
		lines.append(result["name"])
	return lines

def purgeHistory():
	"""Delete shift and hour rows older than 335 days."""
	purgeDate = system.date.addDays(system.date.now(), -335) 
	launchpad.store.deleteOlderThan(launchpad.store.SHIFT, "shift_start",
	                                purgeDate)
	launchpad.store.deleteOlderThan(launchpad.store.HOUR, "hour_timestamp",
	                                purgeDate)


def resetDemoTags():
	"""Reset config, state, run and down seconds and the rate history on demo lines 1 to 7."""
	for i in range(1,8): 
		linePath = "[Launchpad]OEE/Demo/Line %s" %(i)

		tagWritePaths = ["%s/Config/OutfeedFactor" %(linePath)]
		tagWritePaths.append("%s/Config/RateName" %(linePath))
		tagWritePaths.append("%s/Config/RateTime" %(linePath))
		tagWritePaths.append("%s/Config/RejectFactor" %(linePath))
		tagWritePaths.append("%s/Config/TargetRate" %(linePath))
		# Plc counters are free-running simulator tags; zeroing them races initDemoTags.

		tagWriteValues = [1,"Default", "minute", 1, 15 ]
		
		tagWritePaths.append("%s/Plc/State"%(linePath))
		tagWriteValues.append(1)

		# Production is Plc/Outfeed - StartCounter, so "zero" means the counter's current value.
		plcNow = system.tag.readBlocking(["%s/Plc/Outfeed"%(linePath),
		                                  "%s/Plc/Reject"%(linePath)])
		outfeedNow = plcNow[0].value or 0
		rejectNow = plcNow[1].value or 0

		tagWritePaths.append("%s/DayOee/StartCounter"%(linePath))
		tagWritePaths.append("%s/ShiftOee/StartCounter"%(linePath))
		tagWritePaths.append("%s/HourOee/StartCounter"%(linePath))
		
		tagWritePaths.append("%s/DayOee/StartReject"%(linePath))
		tagWritePaths.append("%s/ShiftOee/StartReject"%(linePath))
		tagWritePaths.append("%s/HourOee/StartReject"%(linePath))
		
		tagWritePaths.append("%s/DayOee/RunSeconds"%(linePath))
		tagWritePaths.append("%s/ShiftOee/RunSeconds"%(linePath))
		tagWritePaths.append("%s/HourOee/RunSeconds"%(linePath))
		
		tagWritePaths.append("%s/DayOee/DownSeconds"%(linePath))
		tagWritePaths.append("%s/ShiftOee/DownSeconds"%(linePath))
		tagWritePaths.append("%s/HourOee/DownSeconds"%(linePath))
		
		tagWriteValues.append(outfeedNow)
		tagWriteValues.append(outfeedNow)
		tagWriteValues.append(outfeedNow)
		tagWriteValues.append(rejectNow)
		tagWriteValues.append(rejectNow)
		tagWriteValues.append(rejectNow)

		tagWriteValues.append(0)
		tagWriteValues.append(0)
		tagWriteValues.append(0)
		
		tagWriteValues.append(0)
		tagWriteValues.append(0)
		tagWriteValues.append(0)
		
		targetRateHistory = launchpad.oee.getTargetRateDataset("Default", 15)
		tagWritePaths.append("%s/DayOee/TargetRateHistory" %(linePath))
		tagWritePaths.append("%s/ShiftOee/TargetRateHistory" %(linePath))
		tagWritePaths.append("%s/HourOee/TargetRateHistory" %(linePath))
		tagWriteValues.extend([targetRateHistory, targetRateHistory, targetRateHistory])

		
		system.tag.writeBlocking(tagWritePaths, tagWriteValues)
		
def initDemoTags():
	"""Set demo lines 1 to 7 to a running state with day, shift and hour counters anchored to the live Plc counters."""
	import math
	for i in range(1,8): 
		linePath = "[Launchpad]OEE/Demo/Line %s" %(i)

		tagWritePaths = ["%s/Config/OutfeedFactor" %(linePath)]
		tagWritePaths.append("%s/Config/RateName" %(linePath))
		tagWritePaths.append("%s/Config/RateTime" %(linePath))
		tagWritePaths.append("%s/Config/RejectFactor" %(linePath))
		tagWritePaths.append("%s/Config/TargetRate" %(linePath))

		tagWriteValues = [1,"Default", "minute", 1, 15 ]
		
		tagWritePaths.append("%s/Plc/State"%(linePath))
		tagWriteValues.append(1)
		tagReadPaths = ["%s/Schedule/CurrentShift"%(linePath)]
		tagReadPaths.append("%s/Schedule/CurrentShiftStartTime"%(linePath))
		tagReadPaths.append("%s/Config/TargetRate"%(linePath))
		# The Plc counters are not zero here; every Start* counter is an offset from them.
		tagReadPaths.append("%s/Plc/Outfeed"%(linePath))
		tagReadPaths.append("%s/Plc/Reject"%(linePath))
		tagReadValues = system.tag.readBlocking(tagReadPaths)
		currentShift =  tagReadValues[0].value
		shiftStartTime =  tagReadValues[1].value
		# Freshly installed tags read None until the write below lands; fall back to the value written.
		targetRate = tagReadValues[2].value
		if targetRate is None:
			targetRate = 15
		if currentShift is None:
			currentShift = 0
		outfeedNow = tagReadValues[3].value or 0
		rejectNow = tagReadValues[4].value or 0

		tagWritePaths.append("%s/ShiftOee/StartTime"%(linePath))
		tagWriteValues.append(None)
		tagWritePaths.append("%s/ShiftOee/CurrentShift"%(linePath))
		tagWriteValues.append(0)
		system.tag.writeBlocking(tagWritePaths, tagWriteValues)
		now = system.date.now()
		dayStartTime = system.date.setTime(now, 0, 0, 0) 
		hourStartTime = system.date.setTime(now, system.date.getHour24(now), 0, 0) 
		tagWritePaths.append("%s/DayOee/StartTime"%(linePath))
		tagWriteValues.append(dayStartTime)
		tagWritePaths.append("%s/HourOee/StartTime"%(linePath))
		tagWriteValues.append(hourStartTime)
		dayRunTime = math.floor(system.date.secondsBetween(dayStartTime,now)*.95)
		if currentShift:
			shiftRunTime = system.date.secondsBetween(shiftStartTime,now)
		else:
			shiftRunTime = 0
		hourRunTime = math.floor(system.date.secondsBetween(hourStartTime,now)*.95)
	
		dayDownTime = math.floor(dayRunTime*.05)
		if currentShift:
			shiftDownTime = 0
		else:	
			shiftDownTime = 0
		hourDownTime = math.floor(hourRunTime*.05)

		tagWritePaths.append("%s/DayOee/RunSeconds"%(linePath))
		tagWritePaths.append("%s/ShiftOee/RunSeconds"%(linePath))
		tagWritePaths.append("%s/HourOee/RunSeconds"%(linePath))
		tagWriteValues.extend([dayRunTime, 0, hourRunTime])
		tagWritePaths.append("%s/DayOee/DownSeconds"%(linePath))
		tagWritePaths.append("%s/ShiftOee/DownSeconds"%(linePath))
		tagWritePaths.append("%s/HourOee/DownSeconds"%(linePath))
		tagWriteValues.extend([dayDownTime, hourRunTime, hourDownTime])

		# ProductionCount is Plc/Outfeed - StartCounter, so anchor at the current counter, not zero.
		tagWritePaths.append("%s/DayOee/StartCounter"%(linePath))
		tagWritePaths.append("%s/ShiftOee/StartCounter"%(linePath))
		tagWritePaths.append("%s/HourOee/StartCounter"%(linePath))
		tagWriteValues.extend([outfeedNow-(dayRunTime/60)*targetRate*.9,
		                       outfeedNow-(shiftRunTime/60)*targetRate*.9,
		                       outfeedNow-(hourRunTime/60)*targetRate*.9])

		tagWritePaths.append("%s/DayOee/StartReject"%(linePath))
		tagWritePaths.append("%s/ShiftOee/StartReject"%(linePath))
		tagWritePaths.append("%s/HourOee/StartReject"%(linePath))
		tagWriteValues.extend([rejectNow-(dayRunTime/60)*targetRate*.05,
		                       rejectNow-(shiftRunTime/60)*targetRate*.03,
		                       rejectNow-(hourRunTime/60)*targetRate*.01])
		
		targetRateHistory = launchpad.oee.getTargetRateDataset("default", 15)

		dayTargetRateHistory = system.dataset.setValue(targetRateHistory, 0, "SecondsElapsed", system.date.secondsBetween(dayStartTime,now))  
		dayTargetRateHistory = system.dataset.setValue(dayTargetRateHistory, 0, "SecondsRunning", dayRunTime)  
		dayTargetRateHistory = system.dataset.setValue(dayTargetRateHistory, 0, "SecondsFaulted", dayDownTime)  
		dayTargetRateHistory = system.dataset.setValue(dayTargetRateHistory, 0, "SecondsIdle", 0)  
		tagWritePaths.append("%s/DayOee/TargetRateHistory" %(linePath))
 
		# No shift is current on a gateway whose roster was just written.
		shiftElapsed = system.date.secondsBetween(shiftStartTime, now) if shiftStartTime else 0
		shiftTargetRateHistory = system.dataset.setValue(targetRateHistory, 0, "SecondsElapsed", shiftElapsed)
		shiftTargetRateHistory = system.dataset.setValue(shiftTargetRateHistory, 0, "SecondsRunning", shiftRunTime)  
		shiftTargetRateHistory = system.dataset.setValue(shiftTargetRateHistory, 0, "SecondsFaulted", shiftDownTime)  
		shiftTargetRateHistory = system.dataset.setValue(shiftTargetRateHistory, 0, "SecondsIdle", 0)  
		tagWritePaths.append("%s/ShiftOee/TargetRateHistory" %(linePath))
		
		hourTargetRateHistory = system.dataset.setValue(targetRateHistory, 0, "SecondsElapsed", system.date.secondsBetween(hourStartTime,now))  
		hourTargetRateHistory = system.dataset.setValue(hourTargetRateHistory, 0, "SecondsRunning", hourRunTime)  
		hourTargetRateHistory = system.dataset.setValue(hourTargetRateHistory, 0, "SecondsFaulted", hourDownTime)  
		hourTargetRateHistory = system.dataset.setValue(hourTargetRateHistory, 0, "SecondsIdle", system.date.secondsBetween(hourStartTime,now)-hourRunTime-hourDownTime)   
		tagWritePaths.append("%s/HourOee/TargetRateHistory" %(linePath))
		
		tagWriteValues.extend([dayTargetRateHistory, shiftTargetRateHistory, hourTargetRateHistory])
		
		tagWritePaths.append("%s/Enabled" %(linePath))
		tagWriteValues.append(1)
		
		if currentShift>0:
			tagWritePaths.append("%s/ShiftOee/StartTime"%(linePath))
			tagWriteValues.append(shiftStartTime)
			tagWritePaths.append("%s/ShiftOee/Current"%(linePath))
			tagWriteValues.append(currentShift)
			
		system.tag.writeBlocking(tagWritePaths, tagWriteValues)
		
		


def recordHourStart(hour, startTime, lineName, lineValue ):
	"""Insert the opening row for an hour; does nothing if lineValue is None."""
	if lineValue is None:
		return
	params = []
	tagFolder = BASE_TAG_FOLDER
	now = system.date.now()
	day = system.date.setTime(now, 0, 0, 0)
	params.append(now)
	params.append(system.date.format(now,"yyyy-MM-dd HH:mm:ss"))
	params.append(lineValue["Schedule"]["CurrentShift"])
	params.append(lineName)
	params.append(tagFolder)
	params.append(day)
	params.append(startTime)
	params.append(hour)
	params.append(0)
	params.append(0)
	params.append(0)
	params.append(0)
	params.append(lineValue["Plc"]["ProductionCounter"])
	params.append(lineValue["Plc"]["ProductionCounter"])
	params.append(0)
	params.append(lineValue["Plc"]["RejectCounter"])
	params.append(lineValue["Plc"]["RejectCounter"])
	params.append(0)
	params.append(lineValue["Config"]["OutfeedFactor"])
	params.append(lineValue["Config"]["RejectFactor"])
	params.append(lineValue["Config"]["TargetRate"])
	params.append(lineValue["Config"]["RateName"])
	params.append(1)
	params.append(1)
	params.append(1)
	params.append(1)
	params.append(round(lineValue["Config"]["TargetRate"],2))
	params.append(system.date.format(now,"yyyy-MM-dd HH:mm:ss" ))

	launchpad.store.insert(launchpad.store.HOUR,
	                       HOUR_START_COLUMNS, params)
	


def recordHourEnd(lineName,  lineValue, hourStartTime):
	"""Update the row for the hour starting at hourStartTime with its final figures; does nothing if lineValue is None."""
	if lineValue is None:
		return
	params = []
	now = system.date.now()
	secondsElapsed = min(system.date.secondsBetween(hourStartTime, now ),3600)
	idleSeconds = (secondsElapsed -lineValue["HourOee"]["DownSeconds"] -lineValue["HourOee"]["RunSeconds"]) 

	
	params.append(now)
	params.append(now)
	params.append(lineValue["Plc"]["ProductionCounter"])
	params.append(lineValue["Plc"]["RejectCounter"])
	
	runSeconds = lineValue["HourOee"]["RunSeconds"]
	duration = lineValue["HourOee"]["Duration"]
	oee_u = lineValue["HourOee"]["U"]
	# Idle of 5 s or less is rounding at the interval edge; fold it into run time.
	if idleSeconds <= 5:
		runSeconds = min(runSeconds + idleSeconds,duration)
		idleSeconds = 0
		oee_u =1

	ooe_a  = 1.0*runSeconds/secondsElapsed
	if runSeconds >0:
		ooe_p =  lineValue["HourOee"]["P"]
	else:
		ooe_p = 1
	ooe_q =  lineValue["HourOee"]["Q"]
	if secondsElapsed>0:
		oee_u = (1.0*secondsElapsed-idleSeconds)/secondsElapsed
	else:
		secondsElapsed= 1
	
	params.append(ooe_p * ooe_q* ooe_a)
	params.append(ooe_a)
	params.append(ooe_p)
	params.append(lineValue["HourOee"]["Q"])
	params.append(oee_u)
	
	params.append(lineValue["HourOee"]["ProductionCount"])
	params.append(lineValue["HourOee"]["TargetProductionCount"])
	params.append(lineValue["HourOee"]["RejectCount"])
	params.append(lineValue["HourOee"]["RunSeconds"])
	params.append(secondsElapsed)
	params.append(lineValue["HourOee"]["DownSeconds"])
	params.append(idleSeconds)
	launchpad.store.update(
		launchpad.store.HOUR,
		[("line_name", launchpad.store.EQ, lineName),
		 ("hour_timestamp", launchpad.store.EQ, hourStartTime)],
		HOUR_END_COLUMNS, params)
	

def recordShiftRateChange(shift,  lineName,  lineBasePath, newTargetRate, newTargetRateName):
	"""Append a target rate change to the shift's rate history tag and to the open shift row."""
	tagReadPaths= ["%s/%s/ShiftOee/TargetRateHistory" %(lineBasePath,lineName)]
	tagValues = system.tag.readBlocking(tagReadPaths)
	targetRateHistory = tagValues[0].value
	targetRateHistory = system.dataset.addRow(targetRateHistory, [newTargetRateName,newTargetRate, 0,0,0,0 ])
	tagWritePaths= ["%s/%s/ShiftOee/TargetRateHistory" %(lineBasePath,lineName)]
	system.tag.writeAsync(tagWritePaths, [targetRateHistory])

	launchpad.store.appendText(
		launchpad.store.SHIFT,
		[("shift", launchpad.store.EQ, shift),
		 ("line_name", launchpad.store.EQ, lineName),
		 ("shift_end", launchpad.store.ISNULL, None)],
		{"shift_rates": round(newTargetRate, 2),
		 "rate_name": newTargetRateName,
		 "shift_timestamps": system.date.format(system.date.now(),
		                                        "yyyy-MM-dd HH:mm:ss")})

def recordHourRateChange(hourTimestamp,  lineName, lineBasePath, newTargetRate, newTargetRateName):
	"""Append a target rate change to the day and hour rate history tags and to the hour row."""
	tagReadPaths= ["%s/%s/DayOee/TargetRateHistory" %(lineBasePath,lineName)]
	tagValues = system.tag.readBlocking(tagReadPaths)
	targetRateHistory = tagValues[0].value
	targetRateHistory = system.dataset.addRow(targetRateHistory, [newTargetRateName,newTargetRate, 0,0,0,0 ])
	tagWritePaths= ["%s/%s/DayOee/TargetRateHistory" %(lineBasePath,lineName)]
	system.tag.writeAsync(tagWritePaths, [targetRateHistory])
	
	tagReadPaths= ["%s/%s/HourOee/TargetRateHistory" %(lineBasePath,lineName)]
	tagValues = system.tag.readBlocking(tagReadPaths)
	targetRateHistory = tagValues[0].value
	targetRateHistory = system.dataset.addRow(targetRateHistory, [newTargetRateName,newTargetRate, 0,0,0,0 ])
	tagWritePaths= ["%s/%s/HourOee/TargetRateHistory" %(lineBasePath,lineName)]
	system.tag.writeAsync(tagWritePaths, [targetRateHistory])

	launchpad.store.appendText(
		launchpad.store.HOUR,
		[("line_name", launchpad.store.EQ, lineName),
		 ("hour_timestamp", launchpad.store.EQ, hourTimestamp)],
		{"hour_rates": round(newTargetRate, 2),
		 "rate_name": newTargetRateName,
		 "hour_timestamps": system.date.format(system.date.now(),
		                                       "yyyy-MM-dd HH:mm:ss")})
	
	
def recordShiftEnd(shift, lineName,  lineValue, shiftStart):
	"""Update the open row for the shift with its final figures; does nothing if lineValue is None."""
	if lineValue is None:
		return
	params = []
	now = system.date.now()
	shiftEnd = now 
	now = system.date.now()
	runSeconds = lineValue["ShiftOee"]["RunSeconds"]
	idleSeconds = lineValue["ShiftOee"]["IdleSeconds"]
	oee_u = lineValue["ShiftOee"]["U"]
	duration = lineValue["ShiftOee"]["Duration"]
	# Idle of 5 s or less is rounding at the interval edge; fold it into run time.
	if idleSeconds <= 5:		
		runSeconds = min(runSeconds + idleSeconds,duration)
		idleSeconds = 0	
		oee_u =1
		
	params.append(now)
	params.append(now)
	params.append(lineValue["Plc"]["ProductionCounter"])
	params.append(lineValue["Plc"]["RejectCounter"])
	params.append(shiftEnd)

	params.append(lineValue["ShiftOee"]["O"])
	params.append(lineValue["ShiftOee"]["A"])
	params.append(lineValue["ShiftOee"]["P"])
	params.append(lineValue["ShiftOee"]["Q"])
	params.append(oee_u)
	
	params.append(lineValue["ShiftOee"]["ProductionCount"])
	params.append(lineValue["ShiftOee"]["TargetProductionCount"])
	params.append(lineValue["ShiftOee"]["RejectCount"])
	params.append(runSeconds)
	params.append(lineValue["ShiftOee"]["SecondsElapsed"])
	params.append(lineValue["ShiftOee"]["DownSeconds"])
	params.append(idleSeconds)

	# The open shift is the row with no end; shift names repeat every day.
	launchpad.store.update(
		launchpad.store.SHIFT,
		[("shift", launchpad.store.EQ, shift),
		 ("line_name", launchpad.store.EQ, lineName),
		 ("shift_end", launchpad.store.ISNULL, None)],
		SHIFT_END_COLUMNS, params)
	

def recordShiftStart(shift, lineName, lineValue ):
	"""Insert the opening row for a shift; does nothing if lineValue is None."""
	if lineValue is None:
		return
	params = []
	tagFolder = BASE_TAG_FOLDER
	now = system.date.now()
	params.append(now)
	params.append(system.date.format(now,"yyyy-MM-dd HH:mm:ss"))
	params.append(shift)
	params.append(lineName)
	params.append(tagFolder)
	params.append(system.date.addSeconds(system.date.addMillis(now, 0-system.date.getMillis(now)), 0-system.date.getSecond(now)))
	params.append(None)
	params.append(0)
	params.append(0)
	params.append(0)
	params.append(0)
	params.append(lineValue["Plc"]["ProductionCounter"])
	params.append(lineValue["Plc"]["ProductionCounter"])
	params.append(0)
	params.append(lineValue["Plc"]["RejectCounter"])
	params.append(lineValue["Plc"]["RejectCounter"])
	params.append(0)
	params.append(lineValue["Config"]["OutfeedFactor"])
	params.append(lineValue["Config"]["RejectFactor"])
	params.append(lineValue["Config"]["TargetRate"])
	params.append(lineValue["Config"]["RateName"])
	params.append(1)
	params.append(1)
	params.append(1)
	params.append(1)
	params.append(round(lineValue["Config"]["TargetRate"],2))
	params.append(system.date.format(now,"yyyy-MM-dd HH:mm:ss" ))

	launchpad.store.insert(launchpad.store.SHIFT,
	                       SHIFT_START_COLUMNS, params)
	
def tableExists(database,tableName):
	"""Return True if the table exists on the database connection."""
	from com.inductiveautomation.ignition.gateway import IgnitionGateway
	from com.inductiveautomation.ignition.common.db.schema import TableType
	context = IgnitionGateway.get()
	tables = context.getDatasourceManager().getMetaProvider().getTables(database, TableType.Table)
	if tableName in tables:
		return True
	else:
		return False


def makeHistory(lineName, tx=None):
	"""Insert 31 days of generated shift rows for the line, then its hourly history."""
	from random import randrange

	now = system.date.now()
	startProductionCount = 100
	startRejectCount = 10
	tagFolder = BASE_TAG_FOLDER
	for day in range(30,-1,-1):
		
		shiftDay = system.date.addDays(now, 0-day)
		for shift in [1,2,3]:
			params = []
			if shift == 1:
				startTime = system.date.setTime(system.date.addDays(shiftDay,-1), 22, 0, 0)
				stopTime = system.date.setTime(shiftDay, 6, 0, 0)
			elif shift == 2:
				startTime = system.date.setTime(shiftDay, 6, 0, 0)
				stopTime = system.date.setTime(shiftDay, 14, 0, 0)
			else:
				startTime = system.date.setTime(shiftDay, 14, 0, 0)
				stopTime = system.date.setTime(shiftDay, 22, 0, 0)
			targetRate = 15
			if system.date.minutesBetween(now, stopTime) >0:
				# The shift in progress gets an open starter row; the insert below is skipped for it.
				stopTime = None
				shiftSeconds = 0
				runSeconds = 0
				targetCount = 0
				a = 1
				p = 1
				q = 1
				shiftProduction = 0
				shiftReject = 0
				startProductionCount = 0
				startRejectCount = 0
			else:
				shiftSeconds = system.date.secondsBetween(startTime, stopTime)
				runSeconds = shiftSeconds - randrange(120,3600)
				targetCount = (runSeconds/60.0) * targetRate
				a = 1.0*runSeconds/shiftSeconds
				shiftProduction = 7200 -  randrange(1000,3000)
				shiftReject = randrange(10,100)
				# Capped at 100% so generated performance stays physical.
				p = min(((1.0/targetRate)*shiftProduction)/(runSeconds/60.0), 1.0)
				q = (shiftProduction-shiftReject)/(1.0*shiftProduction)

			# Stopped time is split between breakdown and idle, as in makeHourlyHistory.
			shiftIdle = int((shiftSeconds-runSeconds) * randrange(20, 55) / 100.0)
			params.extend([now, stopTime, shift, lineName, tagFolder, startTime, stopTime, shiftSeconds, runSeconds, (shiftSeconds-runSeconds)-shiftIdle, shiftIdle])
			params.extend([startProductionCount, startProductionCount+shiftProduction, shiftProduction, targetCount ])
			params.extend([startRejectCount, startRejectCount+shiftReject, shiftReject])
			params.extend([1,1,15,"default"])
			params.extend([a, p, q, a*p*q])
			params.extend(["default",stopTime])
			if stopTime:
				launchpad.store.insert(launchpad.store.SHIFT,
				                       SHIFT_HISTORY_COLUMNS, params, tx)
			startProductionCount += shiftProduction
			startRejectCount += shiftReject
	makeHourlyHistory(lineName, tx)
	
def makeHourlyHistory(lineName, tx=None):
	"""Insert 32 days of generated hour rows for the line, excluding the hour in progress."""
	from random import randrange
	tagFolder = BASE_TAG_FOLDER
	now = system.date.now()
	
	startProductionCount = 100
	startRejectCount = 10
	# The current hour belongs to the live engine (recordHourStart/recordHourEnd), so skip it.
	currentHourStart = system.date.setTime(now, system.date.getHour24(now), 0, 0)
	for day in range(31,-1,-1):
		hourStartTime = system.date.addDays(now, 0-day)
		params = []
		for hour in range(24):


			hourStartTime = system.date.setTime(hourStartTime, hour,0,0)
			if hourStartTime < currentHourStart:
				dayTimestamp = system.date.setTime(hourStartTime, 0, 0, 0)
	
				targetRate = 15
				elapsedSeconds = min(system.date.secondsBetween( hourStartTime, now), 3600)
				if elapsedSeconds == 3600:
					runSeconds = elapsedSeconds - randrange(120,480)
					hourProduction = 900 -  randrange(50,150)
					# Stopped time is split between breakdown and idle.
					stoppedSeconds = elapsedSeconds - runSeconds
					idleSeconds = int(stoppedSeconds * randrange(20, 55) / 100.0)
					downSeconds = stoppedSeconds - idleSeconds
				else:
					runSeconds = elapsedSeconds
					downSeconds = 0
					idleSeconds = 0
					hourProduction = runSeconds/60 * targetRate


				hourReject = randrange(0,20)
				
				targetCount = (runSeconds/60.0) * targetRate
				a = 1.0*runSeconds/elapsedSeconds
				p = min(((1.0/targetRate)*hourProduction)/(runSeconds/60.0), 1.0)
				if hourProduction >0:
					q = (hourProduction-hourReject)/(1.0*hourProduction)
				else:
					q = 1
				
				params.extend([hourStartTime, hourStartTime, 0, dayTimestamp, hourStartTime, hour, lineName, tagFolder, elapsedSeconds, runSeconds, downSeconds, idleSeconds])
				params.extend([startProductionCount, startProductionCount+hourProduction, hourProduction, targetCount])
				params.extend([startRejectCount, startRejectCount+hourReject, hourReject])
				params.extend([1,1,15,"default"])
				# Utilisation: share of the hour that was not idle.
				u = (1.0*elapsedSeconds - idleSeconds)/elapsedSeconds
				params.extend([a, p, q, u, a*p*q])
				params.extend(["default",hourStartTime])	
				startProductionCount += hourProduction
				startRejectCount += hourReject
		
		if params:
			# `params` holds a whole day of hours end to end: one multi-row insert per day.
			launchpad.store.insertMany(launchpad.store.HOUR,
			                           HOUR_HISTORY_COLUMNS, params, tx)
	  
	
def initTables():
	"""Create the OEE tables and indexes, or the file store's directories on an edition without a database."""
	sql = """
	CREATE TABLE IF NOT EXISTS ex_launchpad_oee_config (
	  id INTEGER PRIMARY KEY,
	  utc_timestamp INTEGER,
	  stat_timestamp TIMESTAMP,
	  shift TEXT,
	  hour_of_day INTEGER,
	  line_name TEXT,


	  outfeed_factor REAL,
	  reject_factor REAL,
	  target_rate INTEGER,
	  rate_name TEXT
	
	);
	
	
	
	
	CREATE TABLE IF NOT EXISTS ex_launchpad_oee_shift (
	  id INTEGER PRIMARY KEY,
	  utc_timestamp INTEGER,
	  stat_timestamp TIMESTAMP,
	  shift TEXT,
	  line_name TEXT,
	  tag_folder TEXT,
	  shift_start TIMESTAMP,
	  shift_end TIMESTAMP,
	  shift_seconds_elapsed INTEGER DEFAULT 0 ,
	  shift_running_seconds INTEGER DEFAULT 0 ,
	  shift_down_seconds INTEGER DEFAULT 0 ,
	  shift_idle_seconds INTEGER DEFAULT 0 ,
	  start_production_count INTEGER DEFAULT 0 ,
	  raw_production_count INTEGER DEFAULT 0 ,
	  shift_production_count INTEGER DEFAULT 0  ,
	  target_production_count INTEGER DEFAULT 0 ,
	  start_reject_count INTEGER DEFAULT 0 ,
	  raw_reject_count INTEGER DEFAULT 0 ,
	  shift_reject_count INTEGER DEFAULT 0 ,  
	  outfeed_factor REAL,
	  reject_factor REAL,
	  target_rate INTEGER,
	  rate_name TEXT,        
	  shift_oee_a REAL DEFAULT 1 ,
	  shift_oee_p REAL DEFAULT 1 ,
	  shift_oee_q REAL DEFAULT 1 ,
	  shift_oee_u REAL DEFAULT 1 ,
	  shift_oee REAL DEFAULT 1 ,
	  shift_rates TEXT ,
	  shift_timestamps TEXT  
	
	);
	
	
	CREATE TABLE IF NOT EXISTS ex_launchpad_oee_hour (
	  id INTEGER PRIMARY KEY,
	  utc_timestamp INTEGER,
	  stat_timestamp TIMESTAMP,
	  shift TEXT,
	  day_timestamp TIMESTAMP, 
	  hour_timestamp TIMESTAMP,
	  hour_of_day INTEGER,
	  line_name TEXT,
	  tag_folder TEXT,

	  hour_seconds_elapsed INTEGER DEFAULT 0 ,
	  hour_seconds_running INTEGER DEFAULT 0 ,
	  hour_down_seconds INTEGER DEFAULT 0  ,
	  hour_idle_seconds INTEGER DEFAULT 0 ,
	  
	  start_production_count INTEGER DEFAULT 0 ,
	  raw_production_count INTEGER DEFAULT 0 ,
	  hour_production_count INTEGER DEFAULT 0 ,
	  target_production_count INTEGER DEFAULT 0 ,
	  
	  start_reject_count INTEGER DEFAULT 0 ,
	  raw_reject_count INTEGER DEFAULT 0 ,
	  hour_reject_count INTEGER DEFAULT 0 , 
	  
	  outfeed_factor REAL,
	  reject_factor REAL,
	  target_rate INTEGER,
	  rate_name TEXT,        
	  hour_oee_a REAL DEFAULT 1 ,
	  hour_oee_p REAL DEFAULT 1 ,
	  hour_oee_q REAL DEFAULT 1 ,
	  hour_oee_u REAL DEFAULT 1 ,
	  hour_oee REAL,
	  hour_rates TEXT ,
	  hour_timestamps TEXT  
	
	);
	
	CREATE TABLE IF NOT EXISTS ex_launchpad_oee_rate (
  	rate_name TEXT,
  	uom TEXT,
  	interval TEXT,
  	target_rate INTEGER
	);
	
	INSERT INTO ex_launchpad_oee_rate (rate_name, uom, target_rate, interval) VALUES ('default', 'units', 15, 'minute');
	
	CREATE UNIQUE INDEX idx_ex_launchpad_oee_rate
    ON ex_launchpad_oee_rate (rate_name);  

	CREATE UNIQUE INDEX idx_ex_launchpad_oee_shift_line
	ON ex_launchpad_oee_shift(shift, line_name, shift_start);  
	
	CREATE UNIQUE INDEX idx_ex_launchpad_oee_hour
	ON ex_launchpad_oee_hour( line_name, hour_timestamp);
	

	CREATE UNIQUE INDEX idx_ex_launchpad_oee_config
	ON ex_launchpad_oee_config( line_name, hour_of_day, shift);
	
	
	"""
	if not launchpad.edition.hasDatabase():
		# No schema to create; the records are files, but the store needs its directories.
		return launchpad.store.ensure()
	system.db.runUpdateQuery(sql, database=db())


def setupShifts():
	"""Enable a 3 x 8h roster (HHMM ints) on every demo line, writing only tags that differ."""
	# Rewriting an unchanged roster still counts as a schedule change and restarts the shift.
	SHIFTS = [(1, 2200, 600), (2, 600, 1400), (3, 1400, 2200)]
	lines = launchpad.oee.getLineNames(BASE_TAG_FOLDER)
	paths, values = [], []
	for ln in lines:
		base = "%s/%s/Schedule" % (BASE_TAG_FOLDER, ln)
		for num, start, stop in SHIFTS:
			paths.append("%s/%d/StartTime" % (base, num)); values.append(start)
			paths.append("%s/%d/StopTime" % (base, num)); values.append(stop)
			paths.append("%s/%d/ShiftEnabled" % (base, num)); values.append(True)
	current = system.tag.readBlocking(paths)
	writePaths, writeValues = [], []
	for path, wanted, held in zip(paths, values, current):
		if held.value != wanted:
			writePaths.append(path)
			writeValues.append(wanted)
	if writePaths:
		system.tag.writeBlocking(writePaths, writeValues)
	return {"lines": lines, "tagsWritten": len(writePaths),
		"alreadyCorrect": len(paths) - len(writePaths)}


def seedHistory():
	"""Replace the shift and hour history with generated rows in one transaction; rolls back if no hourly rows result."""
	lines = launchpad.oee.getLineNames(BASE_TAG_FOLDER)
	tx = launchpad.store.seedBegin()
	try:
		launchpad.store.deleteAll(launchpad.store.SHIFT, tx)
		launchpad.store.deleteAll(launchpad.store.HOUR, tx)
		for ln in lines:
			launchpad.oee.makeHistory(ln, tx)
		shiftRows = launchpad.store.count(launchpad.store.SHIFT, tx)
		hourRows = launchpad.store.count(launchpad.store.HOUR, tx)
		# The charts read the hour table; never commit it empty.
		if not hourRows:
			raise Exception("the generator produced no hourly rows - keeping the "
				"history that was already there")
		launchpad.store.seedCommit(tx)
	except:
		launchpad.store.seedRollback(tx)
		raise
	finally:
		launchpad.store.seedClose(tx)
	return {"lines": lines, "shiftRows": shiftRows, "hourRows": hourRows}


def healAnchors(logger=None):
	"""Restart any day, shift or hour interval whose anchor or rollover is wrong; writes nothing when healthy."""
	INTERVALS = ("DayOee", "ShiftOee", "HourOee")
	LEAVES = ("StartCounter", "StartReject", "SecondsElapsed", "StartTime")
	healed = []
	for i in range(1, 8):
		linePath = "%s/Line %s" % (BASE_TAG_FOLDER, i)
		paths = ["%s/Plc/ProductionCounter" % linePath,
		         "%s/Plc/RejectCounter" % linePath,
		         "%s/Config/TargetRate" % linePath,
		         "%s/Schedule/CurrentShiftStartTime" % linePath]
		for iv in INTERVALS:
			for leaf in LEAVES:
				paths.append("%s/%s/%s" % (linePath, iv, leaf))
		values = system.tag.readBlocking(paths)

		rawCount = values[0].value
		rawReject = values[1].value or 0
		targetRate = values[2].value or 15
		shiftStart = values[3].value
		if rawCount is None:
			continue

		now = system.date.now()
		boundaries = {
			"HourOee": system.date.setTime(now, system.date.getHour24(now), 0, 0),
			"DayOee": system.date.setTime(now, 0, 0, 0),
			"ShiftOee": shiftStart}

		writePaths, writeValues = [], []
		for n, iv in enumerate(INTERVALS):
			base = 4 + n * len(LEAVES)
			start = values[base].value
			elapsed = values[base + 2].value or 0
			startTime = values[base + 3].value
			# Most this interval could plausibly have produced; beyond it the anchor is wrong.
			ceiling = targetRate * (max(elapsed, 60) / 60.0) * 3 + 200
			boundary = boundaries.get(iv)

			if start is None:
				why = "no anchor"
			elif start > rawCount:
				why = "anchor %s above counter %s" % (start, rawCount)
			elif (rawCount - start) > ceiling:
				why = "implies %d units in %ds" % (rawCount - start, elapsed)
			elif startTime is not None and boundary is not None and startTime < boundary:
				why = "missed its rollover (started %s, current interval began %s)" % (
					startTime, boundary)
			else:
				continue

			# Rejects move with production, or Quality drops to zero.
			for leaf, value in (("StartCounter", rawCount),
			                    ("StartReject", rawReject),
			                    ("RunSeconds", 0),
			                    ("DownSeconds", 0),
			                    # Restart at now, not the boundary: elapsed would otherwise exceed run seconds.
			                    ("StartTime", now),
			                    ("TargetRateHistory",
			                     getTargetRateDataset("Default", targetRate))):
				writePaths.append("%s/%s/%s" % (linePath, iv, leaf))
				writeValues.append(value)
			healed.append("Line %s %s: %s" % (i, iv, why))

		if writePaths:
			system.tag.writeBlocking(writePaths, writeValues)

	if healed and logger:
		logger.info("re-anchored %d interval(s): %s" % (len(healed), "; ".join(healed)))
	return {"healed": len(healed), "detail": healed}
