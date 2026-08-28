DATABASE_NAME = "OEE"

def db():
	"""The database connection to use.

	This project owns a SQLite database named after itself, so the connection
	list on a gateway says which project each database belongs to. The globals
	lookup stays as an override hook for anyone pointing the project at a
	differently named connection; nothing in this project writes it.
	"""
	return system.util.getGlobals().get("launchpad.database") or DATABASE_NAME

BASE_TAG_FOLDER = "[Launchpad]OEE/Demo"

def ntz(value):
	if value == None:
		return 0
	else:
		return value

def getTargetRateDataset(targetRateName,targetRate):
	#return a dataset for initial target rate history
	targetRateHeaders = ["RateName","RateValue", "SecondsElapsed", "SecondsRunning",  "SecondsFaulted", "SecondsIdle" ]
	targetRateHistory = system.dataset.toDataSet(targetRateHeaders, [[targetRateName,targetRate, 0,0,0,0 ]])
	return targetRateHistory

def getTargetProductionCount(targetRateHistory):
	#target production count = run time * target rate

	rowIndex = targetRateHistory.rowCount - 1
	targetProductionCount = 0
	for row in range(targetRateHistory.rowCount):

		targetProductionCount+= (targetRateHistory.getValueAt(row,"SecondsRunning")/60.0)  * targetRateHistory.getValueAt(row,"RateValue")

	return targetProductionCount
	
def getLineNames(lineFolderPath):
	#line udt instances should all be in one folder.  provide path to folder and get back line name
	results = system.tag.browse(lineFolderPath, {"typeId":"OEE/LineConfig", "tagType":"UdtInstance"})
	lines = []
	for result in results.getResults():
		lines.append(result["name"])
	return lines

def purgeHistory():
	#hour and shift tables should hold no more than 365 days
	purgeDate = system.date.addDays(system.date.now(), -335) 
	sql = "DELETE FROM ex_launchpad_oee_shift WHERE shift_start < ?"
	system.db.runPrepUpdate(sql, [purgeDate], database = db())
	sql = "DELETE FROM ex_launchpad_oee_hour WHERE hour_timestamp < ?"
	system.db.runPrepUpdate(sql, [purgeDate], database = db())


def resetDemoTags():
	#reset lines in demo folder
	
	for i in range(1,8): 
		linePath = "[Launchpad]OEE/Demo/Line %s" %(i)

		#config folder
		tagWritePaths = ["%s/Config/OutfeedFactor" %(linePath)]
		tagWritePaths.append("%s/Config/RateName" %(linePath))
		tagWritePaths.append("%s/Config/RateTime" %(linePath))
		tagWritePaths.append("%s/Config/RejectFactor" %(linePath))
		tagWritePaths.append("%s/Config/TargetRate" %(linePath))
		# Plc/ProductionCounter and Plc/RejectCounter are deliberately NOT zeroed here.
		# They are OPC tags on a running simulator, so a write to zero races the next
		# device scan: initDemoTags reads them a moment later to anchor its offsets, and
		# a read that lands on the wrong side of that race makes the period's production
		# either the whole counter or a negative number. Everything downstream is an
		# offset from wherever the counter happens to be, so leave it free-running.

		tagWriteValues = [1,"Default", "minute", 1, 15 ]
		
		#running state
		tagWritePaths.append("%s/Plc/State"%(linePath))
		tagWriteValues.append(1)
	
		now = system.date.now()
		dayStartTime = system.date.setTime(now, 0, 0, 0)
		hourStartTime = system.date.setTime(now, system.date.getHour24(now), 0, 0)

		# "reset" means the period's production reads zero from here, and production is
		# the expression Plc/Outfeed - StartCounter -- so the reset value is wherever the
		# free-running simulator counter is now, not literal zero.
		plcNow = system.tag.readBlocking(["%s/Plc/Outfeed"%(linePath),
		                                  "%s/Plc/Reject"%(linePath)])
		outfeedNow = plcNow[0].value or 0
		rejectNow = plcNow[1].value or 0

		#reset counters
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
		
		#day/shift/hour production and rejects all start from here
		tagWriteValues.append(outfeedNow)
		tagWriteValues.append(outfeedNow)
		tagWriteValues.append(outfeedNow)
		tagWriteValues.append(rejectNow)
		tagWriteValues.append(rejectNow)
		tagWriteValues.append(rejectNow)

		#set zero run time
		tagWriteValues.append(0)
		tagWriteValues.append(0)
		tagWriteValues.append(0)
		
		#set zero down time
		tagWriteValues.append(0)
		tagWriteValues.append(0)
		tagWriteValues.append(0)
		
		#reset target rate history
		targetRateHistory = launchpad.oee.getTargetRateDataset("Default", 15)
		tagWritePaths.append("%s/DayOee/TargetRateHistory" %(linePath))
 		tagWritePaths.append("%s/ShiftOee/TargetRateHistory" %(linePath))
		tagWritePaths.append("%s/HourOee/TargetRateHistory" %(linePath))
		tagWriteValues.extend([targetRateHistory, targetRateHistory, targetRateHistory])

		
		system.tag.writeBlocking(tagWritePaths, tagWriteValues)
		
def initDemoTags():
	#initialize lines in demo folder
	logger = system.util.getLogger("launchpad.oee.initOeeDemo")
	import math
	for i in range(1,8): 
		linePath = "[Launchpad]OEE/Demo/Line %s" %(i)

		#config folder
		tagWritePaths = ["%s/Config/OutfeedFactor" %(linePath)]
		tagWritePaths.append("%s/Config/RateName" %(linePath))
		tagWritePaths.append("%s/Config/RateTime" %(linePath))
		tagWritePaths.append("%s/Config/RejectFactor" %(linePath))
		tagWritePaths.append("%s/Config/TargetRate" %(linePath))

		tagWriteValues = [1,"Default", "minute", 1, 15 ]
		
		#set running state
		tagWritePaths.append("%s/Plc/State"%(linePath))
		tagWriteValues.append(1)
		#read current shift and rate
		tagReadPaths = ["%s/Schedule/CurrentShift"%(linePath)]
		tagReadPaths.append("%s/Schedule/CurrentShiftStartTime"%(linePath))
		tagReadPaths.append("%s/Config/TargetRate"%(linePath))
		# The Plc counters are OPC tags off the simulator, which has been free-running
		# since the device was created -- they are NOT zero when this runs. Every
		# Start* counter below is an offset against them, so read where they are now.
		tagReadPaths.append("%s/Plc/Outfeed"%(linePath))
		tagReadPaths.append("%s/Plc/Reject"%(linePath))
		tagReadValues = system.tag.readBlocking(tagReadPaths)
		currentShift =  tagReadValues[0].value
		shiftStartTime =  tagReadValues[1].value
		# Config/TargetRate is read here but only written by the writeBlocking below, so on
		# a gateway whose tags were installed moments ago it is still None and every rate
		# calculation under it throws. Fall back to the value this function is about to
		# write rather than failing the whole setup.
		targetRate = tagReadValues[2].value
		if targetRate is None:
			targetRate = 15
		if currentShift is None:
			currentShift = 0
		outfeedNow = tagReadValues[3].value or 0
		rejectNow = tagReadValues[4].value or 0

		
		
		#reset shift start
		tagWritePaths.append("%s/ShiftOee/StartTime"%(linePath))
		tagWriteValues.append(None)
		tagWritePaths.append("%s/ShiftOee/CurrentShift"%(linePath))
		tagWriteValues.append(0)
		system.tag.writeBlocking(tagWritePaths, tagWriteValues)
		#set times
		now = system.date.now()
		dayStartTime = system.date.setTime(now, 0, 0, 0) 
		hourStartTime = system.date.setTime(now, system.date.getHour24(now), 0, 0) 
		tagWritePaths.append("%s/DayOee/StartTime"%(linePath))
		tagWriteValues.append(dayStartTime)
		tagWritePaths.append("%s/HourOee/StartTime"%(linePath))
		tagWriteValues.append(hourStartTime)
		#set seconds running
		dayRunTime = math.floor(system.date.secondsBetween(dayStartTime,now)*.95)
		if currentShift:
			shiftRunTime = system.date.secondsBetween(shiftStartTime,now)
		else:
			shiftRunTime = 0
		hourRunTime = math.floor(system.date.secondsBetween(hourStartTime,now)*.95)
	
		#set seconds down
		dayDownTime = math.floor(dayRunTime*.05)
		if currentShift:
			shiftDownTime = 0
		else:	
			shiftDownTime = 0
		hourDownTime = math.floor(hourRunTime*.05)
		
		
		# (the Start* counters are set once, further down, against the live Plc counters --
		#  they used to be zeroed here as well, twice in one writeBlocking call, which
		#  left the outcome depending on which duplicate path won)

		#set running seconds
		tagWritePaths.append("%s/DayOee/RunSeconds"%(linePath))
		tagWritePaths.append("%s/ShiftOee/RunSeconds"%(linePath))
		tagWritePaths.append("%s/HourOee/RunSeconds"%(linePath))
		tagWriteValues.extend([dayRunTime, 0, hourRunTime])
		#set faulted seconds
		tagWritePaths.append("%s/DayOee/DownSeconds"%(linePath))
		tagWritePaths.append("%s/ShiftOee/DownSeconds"%(linePath))
		tagWritePaths.append("%s/HourOee/DownSeconds"%(linePath))
		tagWriteValues.extend([dayDownTime, hourRunTime, hourDownTime])
		
		
		#set starting counts back so we can get production counts
		# ProductionCount is the expression Plc/Outfeed - StartCounter, so the offset
		# has to be measured FROM where the counter is now. Anchoring it at zero makes
		# the period's production the whole free-running counter -- which is how a
		# freshly set-up gateway reported four figures of output in its first hour.
		tagWritePaths.append("%s/DayOee/StartCounter"%(linePath))
		tagWritePaths.append("%s/ShiftOee/StartCounter"%(linePath))
		tagWritePaths.append("%s/HourOee/StartCounter"%(linePath))
		tagWriteValues.extend([outfeedNow-(dayRunTime/60)*targetRate*.9,
		                       outfeedNow-(shiftRunTime/60)*targetRate*.9,
		                       outfeedNow-(hourRunTime/60)*targetRate*.9])

		#set reject offsets on the same basis
		tagWritePaths.append("%s/DayOee/StartReject"%(linePath))
		tagWritePaths.append("%s/ShiftOee/StartReject"%(linePath))
		tagWritePaths.append("%s/HourOee/StartReject"%(linePath))
		tagWriteValues.extend([rejectNow-(dayRunTime/60)*targetRate*.05,
		                       rejectNow-(shiftRunTime/60)*targetRate*.03,
		                       rejectNow-(hourRunTime/60)*targetRate*.01])
		
		#set target rate history
		targetRateHistory = launchpad.oee.getTargetRateDataset("default", 15)
		targetRateHeaders = ["RateName","RateValue", "SecondsElapsed", "SecondsRunning",  "SecondsFaulted", "SecondsIdle" ]
		
		dayTargetRateHistory = system.dataset.setValue(targetRateHistory, 0, "SecondsElapsed", system.date.secondsBetween(dayStartTime,now))  
		dayTargetRateHistory = system.dataset.setValue(dayTargetRateHistory, 0, "SecondsRunning", dayRunTime)  
		dayTargetRateHistory = system.dataset.setValue(dayTargetRateHistory, 0, "SecondsFaulted", dayDownTime)  
		dayTargetRateHistory = system.dataset.setValue(dayTargetRateHistory, 0, "SecondsIdle", 0)  
		tagWritePaths.append("%s/DayOee/TargetRateHistory" %(linePath))
 		
 		# no shift is current on a gateway whose roster was written seconds ago
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
		
		#enable 
		tagWritePaths.append("%s/Enabled" %(linePath))
		tagWriteValues.append(1)
		
		#set shift 
		if currentShift>0:
			tagWritePaths.append("%s/ShiftOee/StartTime"%(linePath))
			tagWriteValues.append(shiftStartTime)
			tagWritePaths.append("%s/ShiftOee/Current"%(linePath))
			tagWriteValues.append(currentShift)
			
		system.tag.writeBlocking(tagWritePaths, tagWriteValues)
		
		


def recordHourStart(hour, startTime, lineName, lineValue ):
	# safe-guard: skip if lineValue is None
	if lineValue is None:
		return
	#record start of hour
	
	sql = """
	INSERT INTO ex_launchpad_oee_hour (
    utc_timestamp,
    stat_timestamp,
    shift,
    line_name,
    tag_folder, 
    day_timestamp,
    hour_timestamp,
    hour_of_day,
    hour_seconds_elapsed,
    hour_seconds_running,
   	hour_down_seconds,
   	hour_idle_seconds,
    
    start_production_count,
    raw_production_count,
    hour_production_count,
    
    start_reject_count,
    raw_reject_count,
    hour_reject_count,
   
    outfeed_factor ,
	reject_factor ,
    target_rate,
    rate_name,
    hour_oee_a,
    hour_oee_p,
    hour_oee_q,
    hour_oee,
    hour_rates,
    hour_timestamps
) VALUES (
    ?,  -- utc_timestamp
    ?,  -- stat_timestamp
    ?,  -- shift
    ?,  -- line_name
    ?, --  tag_folder
    ?,  -- day_timestsamp
    ?,  -- hour_timestsamp
    ?,  -- hour_of_day
    ?,  -- hour_seconds_elapsed
    ?,  -- hour_running_seconds
    ?, -- hour_down_seconds,
   	?, -- hour_idle_seconds,
    ?,  -- start_production_count
    ?,  -- raw_production_count
    ?,  -- hour_production_count
    ?,  -- start_reject_count
    ?,  -- raw_reject_count
    ?,  -- hour_reject_count
    ?,	-- outfeed_factor ,
	?, --  reject_factor ,
    ?,  -- target_rate
    ?,  -- rate_name
    ?,  -- hour_oee_a
    ?,  -- hour_oee_p
    ?,  -- hour_oee_q
    ?,  -- hour_oee
    ?,  -- hour_rates (TEXT - often JSON string of rates, e.g., '[100, 120, 115]')
    ?   -- hour_timestamps (TEXT - often JSON string of timestamps, e.g., '["2023-03-15 06:00:00", "2023-03-15 07:00:00"]')
	) """
	  
	params = []
	tagFolder = BASE_TAG_FOLDER
	now = system.date.now()
	day = system.date.setTime(now, 0, 0, 0)
	params.append(now) #utc_timestamp
	params.append(system.date.format(now,"yyyy-MM-dd HH:mm:ss")) #stat_timestamp 
	params.append(lineValue["Schedule"]["CurrentShift"]) #shift
	params.append(lineName) #line_name 
	params.append(tagFolder) #tag folder name 
	params.append(day) #day_timestsamp
	params.append(startTime) #hour_timestsamp
	params.append(hour) #hour_of_day 
	params.append(0) #hour_seconds_elapsed 
	params.append(0) #hour_running_seconds 
	params.append(0) #hour_down_elapsed 
	params.append(0) #hour_idle_seconds 
	params.append(lineValue["Plc"]["ProductionCounter"]) #start_production_count 
	params.append(lineValue["Plc"]["ProductionCounter"]) #raw_production_count 
	params.append(0) #hour_production_count 
	params.append(lineValue["Plc"]["RejectCounter"])  #start_reject_count 
	params.append(lineValue["Plc"]["RejectCounter"])  #raw_reject_count 
	params.append(0) #hour_reject_count
	params.append(lineValue["Config"]["OutfeedFactor"]) #outfeed_factor
	params.append(lineValue["Config"]["RejectFactor"]) #reject_factor
	params.append(lineValue["Config"]["TargetRate"]) #target_rate 
	params.append(lineValue["Config"]["RateName"]) #rate_name      
	params.append(1) #hour_oee_a 
	params.append(1) #hour_oee_p 
	params.append(1) #hour_oee_q 
	params.append(1) #hour_oee 
	params.append(round(lineValue["Config"]["TargetRate"],2)) #_rates 
	params.append(system.date.format(now,"yyyy-MM-dd HH:mm:ss" )) #timestamps 

	system.db.runPrepUpdate(sql, params, database=db())
	


def recordHourEnd(lineName,  lineValue, hourStartTime):
	# safe-guard: skip if lineValue is None
	if lineValue is None:
		return
	#record end of hour which started at the given hourStartTime

	sql = """ UPDATE ex_launchpad_oee_hour SET 
	utc_timestamp = ?,
	stat_timestamp = ?,
	raw_production_count = ?,
	raw_reject_count = ?,

	hour_oee = ?,
	hour_oee_a = ?,
	hour_oee_p = ?,
	hour_oee_q = ?,
	hour_oee_u = ?,
	hour_production_count = ?,
	target_production_count = ?,
	hour_reject_count = ?,
	hour_seconds_running = ?,
	hour_seconds_elapsed = ?,
	hour_down_seconds = ?,
	hour_idle_seconds = ?
	WHERE  line_name = ? and hour_timestamp = ? """
	
	params = []
	
	#get seconds elpapsed since start of hour
	now = system.date.now()
	#now = system.date.setTime(now, system.date.getHour24(now), 0, 0)
	secondsElapsed = min(system.date.secondsBetween(hourStartTime, now ),3600)
	idleSeconds = (secondsElapsed -lineValue["HourOee"]["DownSeconds"] -lineValue["HourOee"]["RunSeconds"]) 

	
	params.append(now) #utc_timestamp
	params.append(now) #stat_timestamp 
	params.append(lineValue["Plc"]["ProductionCounter"]) #raw_production_count
	params.append(lineValue["Plc"]["RejectCounter"]) #raw_reject_count
	
	targetRate = lineValue["Config"]["TargetRate"]
	runSeconds = lineValue["HourOee"]["RunSeconds"]
	duration = lineValue["HourOee"]["Duration"]
	#adjust for  last second
	if idleSeconds <= 5:		
		runSeconds = min(runSeconds + idleSeconds,duration)
		idleSeconds = 0	
		oee_u =1
		
	hourProductionCount = lineValue["HourOee"]["ProductionCount"]
	
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
	
	params.append(ooe_p * ooe_q* ooe_a) #oee
	params.append(ooe_a) #oee_a
	params.append(ooe_p) #oee_p
	params.append(lineValue["HourOee"]["Q"]) #oee_q
	params.append(oee_u) #oee_u
	
	params.append(lineValue["HourOee"]["ProductionCount"]) #production_count 
	params.append(lineValue["HourOee"]["TargetProductionCount"]) #target production_count 
	params.append(lineValue["HourOee"]["RejectCount"]) #reject_count 
	params.append(lineValue["HourOee"]["RunSeconds"]) #running_seconds
	params.append(secondsElapsed) #seconds_elapsed
	params.append(lineValue["HourOee"]["DownSeconds"]) #down_seconds
	params.append(idleSeconds) #idle 
	params.append(lineName) #line_name 
	params.append(hourStartTime)
	system.db.runPrepUpdate(sql, params, database=db())
	

def recordShiftRateChange(shift,  lineName,  lineBasePath, newTargetRate, newTargetRateName):
	#record target rate changes in both database and OEE tags
	logger = system.util.getLogger("launchpad.oee.recordShiftRateChange")
	
	#add new row to the target rate history for the shift
	tagReadPaths= ["%s/%s/ShiftOee/TargetRateHistory" %(lineBasePath,lineName)]
	tagValues = system.tag.readBlocking(tagReadPaths)
	targetRateHistory = tagValues[0].value
	targetRateHistory = system.dataset.addRow(targetRateHistory, [newTargetRateName,newTargetRate, 0,0,0,0 ])
	tagWritePaths= ["%s/%s/ShiftOee/TargetRateHistory" %(lineBasePath,lineName)]
	system.tag.writeAsync(tagWritePaths, [targetRateHistory])
	
	#update the shift database record
	sql = """ UPDATE ex_launchpad_oee_shift 
	SET  shift_rates = cast(shift_rates as text) || ',' || cast(? as text)
	, rate_name = cast(rate_name as text) || ',' || cast(? as text)
	,shift_timestamps = cast(shift_timestamps as text) || ',' || cast(? as text) 
	WHERE shift = ? AND line_name = ? and shift_end is null """
	
	params = [round(newTargetRate,2), newTargetRateName,  system.date.format(system.date.now(),"yyyy-MM-dd HH:mm:ss" ), shift, lineName]
	system.db.runPrepUpdate(sql, params, database=db())

def recordHourRateChange(hourTimestamp,  lineName, lineBasePath, newTargetRate, newTargetRateName):
	#record target rate changes in both database and OEE tags
	logger = system.util.getLogger("launchpad.oee.recordShiftRateChange")
	
		
	#add new row to the target rate history for the day and hour 
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
	
	
	
	sql = """ UPDATE ex_launchpad_oee_hour 
	SET  hour_rates = cast(hour_rates as text) || ',' || cast(? as text)
	, rate_name = cast(rate_name as text) || ',' || cast(? as text)
	,hour_timestamps = cast(hour_timestamps as text) || ',' || cast(? as text) 
	WHERE  line_name = ? and hour_timestamp =? """
	
	params = [round(newTargetRate,2), newTargetRateName,  system.date.format(system.date.now(),"yyyy-MM-dd HH:mm:ss" ),  lineName, hourTimestamp]
	system.db.runPrepUpdate(sql, params, database=db())
	
	
def recordShiftEnd(shift, lineName,  lineValue, shiftStart):
	# safe-guard: skip if lineValue is None
	if lineValue is None:
		return
	#record end of shift
#	logger = system.util.getLogger("timerscripts")

	sql = """ UPDATE ex_launchpad_oee_shift SET 
	utc_timestamp = ?,
	stat_timestamp = ?,
	raw_production_count = ?,
	raw_reject_count = ?,
	shift_end = ?,
	shift_oee = ?,
	shift_oee_a = ?,
	shift_oee_p = ?,
	shift_oee_q = ?,
	shift_oee_u = ?,
	shift_production_count = ?,
	target_production_count = ?,
	shift_reject_count = ?,
	shift_running_seconds = ?,
	shift_seconds_elapsed = ?,
	shift_down_seconds = ?,
	shift_idle_seconds = ?
	
	WHERE shift = ? AND line_name = ? and shift_end is null """
	
	params = []
	now = system.date.now()
	shiftEnd = now 
	now = system.date.now()
	#now = system.date.setTime(now, system.date.getHour24(now), 0, 0)
	runSeconds = lineValue["ShiftOee"]["RunSeconds"]
	idleSeconds = lineValue["ShiftOee"]["IdleSeconds"]
	oee_u = lineValue["ShiftOee"]["U"]
	duration = lineValue["ShiftOee"]["Duration"]
	#adjust for  last second
	if idleSeconds <= 5:		
		runSeconds = min(runSeconds + idleSeconds,duration)
		idleSeconds = 0	
		oee_u =1
		
	params.append(now) #utc_timestamp
	params.append(now) #stat_timestamp 
	params.append(lineValue["Plc"]["ProductionCounter"]) #raw_production_count
	params.append(lineValue["Plc"]["RejectCounter"]) #raw_reject_count
	params.append(shiftEnd) #shift_end

	params.append(lineValue["ShiftOee"]["O"]) #oee
	params.append(lineValue["ShiftOee"]["A"]) #oee_a
	params.append(lineValue["ShiftOee"]["P"]) #oee_p
	params.append(lineValue["ShiftOee"]["Q"]) #oee_q
	params.append(oee_u) #oee_u
	
	params.append(lineValue["ShiftOee"]["ProductionCount"]) #production_count 
	params.append(lineValue["ShiftOee"]["TargetProductionCount"]) #target_production_count 
	params.append(lineValue["ShiftOee"]["RejectCount"]) #reject_count 
	params.append(runSeconds) #running_seconds
	params.append(lineValue["ShiftOee"]["SecondsElapsed"]) #seconds_elapsed
	params.append(lineValue["ShiftOee"]["DownSeconds"]) #running_seconds
	params.append(idleSeconds)

	params.append(shift) #shift
	params.append(lineName) #line_name 
	#params.append(shiftStart)
	system.db.runPrepUpdate(sql, params, database=db())
	

def recordShiftStart(shift, lineName, lineValue ):
	# safe-guard: skip if lineValue is None
	if lineValue is None:
		return
	#record start of shift
	

	sql = """
	INSERT INTO ex_launchpad_oee_shift (
    utc_timestamp,
    stat_timestamp,
    shift,
    line_name,
    tag_folder, 
    shift_start,
    shift_end,
    shift_seconds_elapsed,
    shift_running_seconds,
    shift_idle_seconds,
    shift_down_seconds,
    start_production_count,
    raw_production_count,
    shift_production_count,
    start_reject_count,
    raw_reject_count,
    shift_reject_count,
    outfeed_factor ,
	reject_factor ,
    target_rate,
    rate_name,
    shift_oee_a,
    shift_oee_p,
    shift_oee_q,
    shift_oee,
    shift_rates,
    shift_timestamps
) VALUES (
    ?,  -- utc_timestamp
    ?,  -- stat_timestamp
    ?,  -- shift
    ?,  -- line_name
    ?,  -- shift_start
    ?, --  tagFolder
    ?,  -- shift_end
    ?,  -- shift_seconds_elapsed
    ?,  -- shift_running_seconds
    ?,  -- shift_idle_seconds,
    ?,  -- shift_down_seconds,
    ?,  -- start_production_count
    ?,  -- raw_production_count
    ?,  -- shift_production_count
    ?,  -- start_reject_count
    ?,  -- raw_reject_count
    ?,  -- shift_reject_count
    ?,	-- outfeed_factor ,
	?, --  reject_factor ,
    ?,  -- target_rate
    ?,  -- rate_name
    ?,  -- shift_oee_a
    ?,  -- shift_oee_p
    ?,  -- shift_oee_q
    ?,  -- shift_oee
    ?,  -- shift_rates (TEXT - often JSON string of rates, e.g., '[100, 120, 115]')
    ?   -- shift_timestamps (TEXT - often JSON string of timestamps, e.g., '["2023-03-15 06:00:00", "2023-03-15 07:00:00"]')
	) """
	  
	params = []
	tagFolder = BASE_TAG_FOLDER
	now = system.date.now()
	params.append(now) #utc_timestamp
	params.append(system.date.format(now,"yyyy-MM-dd HH:mm:ss")) #stat_timestamp 
	params.append(shift) #shift
	params.append(lineName) #line_name 
	params.append(tagFolder) #tag folder name 
	params.append(system.date.addSeconds(system.date.addMillis(now, 0-system.date.getMillis(now)), 0-system.date.getSecond(now))) #shift_start
	params.append(None) #shift_end 
	params.append(0) #shift_seconds_elapsed 
	params.append(0) #shift_running_seconds 
	params.append(0) #shift_idle_elapsed 
	params.append(0) #shift_down_seconds 
	params.append(lineValue["Plc"]["ProductionCounter"]) #start_production_count 
	params.append(lineValue["Plc"]["ProductionCounter"]) #raw_production_count 
	params.append(0) #shift_production_count 
	params.append(lineValue["Plc"]["RejectCounter"])  #start_reject_count 
	params.append(lineValue["Plc"]["RejectCounter"])  #raw_reject_count 
	params.append(0) #shift_reject_count
	params.append(lineValue["Config"]["OutfeedFactor"]) #outfeed_factor
	params.append(lineValue["Config"]["RejectFactor"]) #reject_factor
	params.append(lineValue["Config"]["TargetRate"]) #target_rate 
	params.append(lineValue["Config"]["RateName"]) #rate_name      
	params.append(1) #shift_oee_a 
	params.append(1) #shift_oee_p 
	params.append(1) #shift_oee_q 
	params.append(1) #shift_oee 
	params.append(round(lineValue["Config"]["TargetRate"],2)) #shift_rates 
	params.append(system.date.format(now,"yyyy-MM-dd HH:mm:ss" )) #shift_timestamps 

	system.db.runPrepUpdate(sql, params, database=db())
	
def tableExists(database,tableName):
	from com.inductiveautomation.ignition.gateway import IgnitionGateway
	from com.inductiveautomation.ignition.common.db.schema import TableType
	context = IgnitionGateway.get()
	tables = context.getDatasourceManager().getMetaProvider().getTables(database, TableType.Table)
	if tableName in tables:
		return True
	else:
		return False


def _update(sql, params, tx=None):
	"""Run an insert either standalone or inside a caller's transaction.

	system.db does not accept a database and a tx together -- a tx already knows its
	connection -- so the two calls have to be spelled separately.
	"""
	if tx:
		return system.db.runPrepUpdate(sql, params, tx=tx)
	return system.db.runPrepUpdate(sql, params, database=db())


def makeHistory(lineName, tx=None):
	
	
	#generate history for line
	from random import randrange

	sql = """ INSERT INTO ex_launchpad_oee_shift (
	
	    utc_timestamp,
	    stat_timestamp,
	    shift,
	    line_name,
	    tag_folder,
	    shift_start,
	    shift_end,
	    shift_seconds_elapsed,
	    shift_running_seconds,
	    shift_down_seconds,
	    shift_idle_seconds,
	    start_production_count,
	    raw_production_count,
	    shift_production_count,
	    target_production_count,
	    start_reject_count,
	    raw_reject_count,
	    shift_reject_count,
	    outfeed_factor,
	    reject_factor,
	    target_rate,
	    rate_name,
	    shift_oee_a,
	    shift_oee_p,
	    shift_oee_q,
	    shift_oee,
	    shift_rates,
	    shift_timestamps
	) VALUES (
	
	    ?,  -- utc_timestamp
	    ?,  -- stat_timestamp
	    ?,  -- shift
	    ?,  -- line_name
	    ?,  -- tag_folder
	    ?,  -- shift_start
	    ?,  -- shift_end
	    ?,  -- shift_seconds_elapsed
	    ?,  -- shift_running_seconds
	    ?,  -- shift_down_seconds
	    ?,  -- shift_idle_seconds
	    ?,  -- start_production_count
	    ?,  -- raw_production_count
	    ?,  -- shift_production_count
	    ?,  -- target_production_count
	    ?,  -- start_reject_count
	    ?,  -- raw_reject_count
	    ?,  -- shift_reject_count
	    ?,  -- outfeed_factor
	    ?,  -- reject_factor
	    ?,  -- target_rate
	    ?,  -- rate_name
	    ?,  -- shift_oee_a
	    ?,  -- shift_oee_p
	    ?,  -- shift_oee_q
	    ?,  -- shift_oee
	    ?,  -- shift_rates (TEXT - expected to be a JSON string)
	    ?   -- shift_timestamps (TEXT - expected to be a JSON string)
	)"""  
	
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
			elif shift == 3:
				startTime = system.date.setTime(shiftDay, 14, 0, 0)
				stopTime = system.date.setTime(shiftDay, 22, 0, 0)
			targetRate = 15
			if system.date.minutesBetween(now, stopTime) >0:
				#current shift gets starter record
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
				#generated demo history: cap performance at 100% so the charts stay physical
				p = min(((1.0/targetRate)*shiftProduction)/(runSeconds/60.0), 1.0)
				q = (shiftProduction-shiftReject)/(1.0*shiftProduction)
			
			# same split as the hourly generator: stopped time is part breakdown,
			# part idle, so the shift view has an idle figure of its own
			shiftIdle = int((shiftSeconds-runSeconds) * randrange(20, 55) / 100.0)
			params.extend([now, stopTime, shift, lineName, tagFolder, startTime, stopTime, shiftSeconds, runSeconds, (shiftSeconds-runSeconds)-shiftIdle, shiftIdle])
			params.extend([startProductionCount, startProductionCount+shiftProduction, shiftProduction, targetCount ])
			params.extend([startRejectCount, startRejectCount+shiftReject, shiftReject])
			params.extend([1,1,15,"default"])
			params.extend([a, p, q, a*p*q])
			params.extend(["default",stopTime])
			if stopTime:  #prevent adding future shifts
				_update(sql, params, tx)
			startProductionCount += shiftProduction
			startRejectCount += shiftReject
	makeHourlyHistory(lineName, tx)
	
def makeHourlyHistory(lineName, tx=None):
	#generaate hourly history
	from random import randrange
	tagFolder = BASE_TAG_FOLDER
  	sql = """ INSERT INTO ex_launchpad_oee_hour (
	
	  utc_timestamp ,
	  stat_timestamp ,
	  shift ,
	  day_timestamp,
	  hour_timestamp ,
	  hour_of_day ,
	  line_name ,
	  tag_folder,	
	  hour_seconds_elapsed ,
	  hour_seconds_running ,
	  hour_down_seconds,
	  hour_idle_seconds,
	  start_production_count ,
	  raw_production_count ,
	  hour_production_count ,
	  target_production_count,
	  start_reject_count ,
	  raw_reject_count ,
	  hour_reject_count , 
	  
	  outfeed_factor ,
	  reject_factor ,
	  target_rate ,
	  rate_name ,        
	  hour_oee_a ,
	  hour_oee_p ,
	  hour_oee_q ,
	  hour_oee_u ,
	  hour_oee,
	  hour_rates,
	  hour_timestamps   
	) VALUES """
	valuesClause = """ (
	
	  ?, -- utc_timestamp 
	  ?, -- stat_timestamp 
	  ?, -- shift 
	  ?, -- day_timestsamp 
	  ?, -- hour_timestsamp 
	  ?, -- hour_of_day 
	  ?, -- line_name 
	  ?, -- tag_folder	
	  ?, -- hour_seconds_elapsed 
	  ?, -- hour_seconds_running 
	  ?, -- hour_down_seconds,
	  ?, -- hour_idle_seconds,
	 
	  ?, -- start_production_count 
	  ?, -- raw_production_count 
	  ?, -- hour_production_count 
	  ?, -- target_production_count 
	  ?, -- start_reject_count 
	  ?, -- raw_reject_count 
	  ?, -- hour_reject_count  
	  
	  ?, -- outfeed_factor 
	  ?, -- reject_factor 
	  ?, -- target_rate 
	  ?, -- rate_name         
	  ?, -- hour_oee_a 
	  ?, -- hour_oee_p 
	  ?, -- hour_oee_q 
	  ?, -- hour_oee_u 
	  ?, -- hour_oee
	  ?, -- hour_rates
	  ? -- hour_timestamps   
	) """
	
	now = system.date.now()
	
	startProductionCount = 100
	startRejectCount = 10
	# The hour in progress belongs to the live engine, not to the generator. It opens
	# that hour with recordHourStart and closes it with recordHourEnd, and recordHourEnd
	# is an UPDATE keyed on (line_name, hour_timestamp) -- so a generated row sitting on
	# the current hour gets overwritten with the running counters rather than the
	# generated ones, and the first hour after a seed reads as the whole counter.
	# The shift generator already declines the shift in progress for the same reason.
	currentHourStart = system.date.setTime(now, system.date.getHour24(now), 0, 0)
	for day in range(31,-1,-1):
		hourStartTime = system.date.addDays(now, 0-day)
		params = []
		sqlValues = ""
		for hour in range(24):


			hourStartTime = system.date.setTime(hourStartTime, hour,0,0)
			if hourStartTime < currentHourStart:
				dayTimestamp = system.date.setTime(hourStartTime, 0, 0, 0)
	
				targetRate = 15
				elapsedSeconds = min(system.date.secondsBetween( hourStartTime, now), 3600)
				if elapsedSeconds == 3600:
					runSeconds = elapsedSeconds - randrange(120,480)
					hourProduction = 900 -  randrange(50,150)
					# Not-running time is not all breakdown. Splitting it gives the
					# Utilisation figure and the Idle Time column something to say --
					# generated hours used to carry zero idle, so every line read
					# 100.0% utilised and a column of zeroes, which is a signal that
					# tells the viewer nothing.
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
				# Utilisation is the share of the hour that was not idle. The column defaults
				# to 1, so leaving it unset made every generated row read 100.0% -- a column
				# that says the same thing on every line in every period is not a measurement.
				u = (1.0*elapsedSeconds - idleSeconds)/elapsedSeconds
				params.extend([a, p, q, u, a*p*q])
				params.extend(["default",hourStartTime])	
				startProductionCount += hourProduction
				startRejectCount += hourReject
				if sqlValues:
					sqlValues += ",%s" %(valuesClause)
				else:
					sqlValues = valuesClause
		
		if params:
			_update(sql + sqlValues, params, tx)
	  
	
def initTables():
	#initialize database tables
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
	system.db.runUpdateQuery(sql, database=db())


def setupShifts():
	"""Enable a standard 3 x 8h roster on every demo line.

	Times are HHMM ints. At least one shift must be enabled: with none
	enabled CurrentShift = 0 and the whole ShiftOee branch is degenerate
	(elapsed 0, target 0, so Performance divides by zero).
	This roster matches the shift boundaries the seeded history uses.

	Only writes what actually differs. Rewriting the roster with the values it
	already holds still counts as a change to the schedule, which moves CurrentShift,
	which fires the interval-change handler and restarts the shift -- so pressing Set
	up on a running gateway threw away the shift in progress and started counting
	again from zero. Writing nothing when nothing has changed is what makes the
	button safe to press twice.
	"""
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
	"""Rebuild the OEE shift/hour tables using the example's own generator.

	Going through makeHistory (rather than inserting rows from outside) keeps the
	timestamp binding identical to what the named queries bind at read time --
	hand-written text timestamps do not compare equal against bound Dates.

	The whole rebuild runs in one transaction, and it refuses to commit a result with
	no hourly rows in it. This used to DELETE both tables and then start generating,
	which means anything that went wrong afterwards -- a generator failure, a gateway
	restart mid-run -- left the gateway with no history at all and no way back. On a
	button the install instructions tell every user to press, and that `check` tells
	them to press again when it finds the tables empty, a failure that destroys data
	and then invites a retry is the worst possible shape.
	"""
	lines = launchpad.oee.getLineNames(BASE_TAG_FOLDER)
	tx = system.db.beginTransaction(database=db(), timeout=300000)
	try:
		system.db.runUpdateQuery("DELETE FROM ex_launchpad_oee_shift", tx=tx)
		system.db.runUpdateQuery("DELETE FROM ex_launchpad_oee_hour", tx=tx)
		for ln in lines:
			launchpad.oee.makeHistory(ln, tx)
		shiftRows = system.db.runScalarQuery(
			"SELECT COUNT(*) FROM ex_launchpad_oee_shift", tx=tx)
		hourRows = system.db.runScalarQuery(
			"SELECT COUNT(*) FROM ex_launchpad_oee_hour", tx=tx)
		# every chart and table on the Line View and Production Summary reads the hour
		# table; committing an empty one is the failure this function exists to avoid
		if not hourRows:
			raise Exception("the generator produced no hourly rows - keeping the "
				"history that was already there")
		system.db.commitTransaction(tx)
	except:
		system.db.rollbackTransaction(tx)
		raise
	finally:
		system.db.closeTransaction(tx)
	return {"lines": lines, "shiftRows": shiftRows, "hourRows": hourRows}


def healAnchors(logger=None):
	"""Repair any interval the demo can no longer describe, and leave the rest alone.

	Two things go wrong on a demo gateway, and neither fixes itself.

	The anchor comes adrift. ProductionCount is Plc/Outfeed - StartCounter, so the
	counter and its anchor have to move together, and they come apart whenever one is
	reset without the other: a trial licence expiring and being reset, a tag
	reinstall (the counters ship as memory tags with value 0, so reinstalling zeroes
	the anchor while the simulator keeps climbing), a device rebuilt underneath a
	running line. The result is not a small error -- an anchor of zero against a
	counter at twenty thousand reports the whole counter as one interval's output,
	which is what a line reading several hundred per cent actually is, and an anchor
	above the counter reports negative production.

	The interval misses its rollover. An interval only rolls over because something
	watched it roll over; while the gateway is stopped nothing does, so it comes back
	still pointing at an hour or a shift that ended long ago. Elapsed keeps climbing,
	run seconds do not, and Availability sinks towards zero for the rest of it.

	A repaired interval is restarted rather than just re-anchored -- start time,
	rejects and the run and down timers all move with the counter. Measured both
	ways: re-anchoring alone leaves production counting from the repair while elapsed
	still counts from the old start, so the line reads 0% for the remainder. On a day
	interval that is a day, and zero for eight hours misdescribes a line as badly as
	nine hundred per cent did.

	A healthy gateway is not written to at all, which is what makes this safe to run
	on a schedule and safe to run from the Setup button.
	"""
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
			# the most this interval could have produced, with room for the
			# simulator's own variation, before the anchor is the only explanation
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

			# rejects move with production: a reject anchor left behind counts scrap
			# against output no longer being counted, driving Quality to zero as
			# surely as the anchor drove Performance
			for leaf, value in (("StartCounter", rawCount),
			                    ("StartReject", rawReject),
			                    ("RunSeconds", 0),
			                    ("DownSeconds", 0),
			                    # the repair point, not the interval boundary: restarting
			                    # at the boundary sets elapsed to the whole time since
			                    # it while the run timer starts at zero, which is the
			                    # 0% reading this is here to avoid. The real boundary
			                    # still rolls the interval over on schedule.
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
