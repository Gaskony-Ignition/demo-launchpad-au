"""Logic behind the OEE views' script transforms and event handlers."""


def hourlyStatsAverageJson(self, value):
	"""Parse the |~|-delimited binding text and return the hourly stats average as JSON, or None if incomplete."""
	# The expression carries the parameters as text so its references, not this script,
	# make the binding re-evaluate.
	parts = (value or u"").split(u"|~|")
	if len(parts) != 4:
		# A date not yet arrived leaves the expression short: return None, which renders empty,
		# where an exception renders as a red box over the chart.
		return None
	line_name = parts[0]
	tag_folder = parts[1]
	if not parts[2].isdigit():
		return None
	start_time = system.date.fromMillis(long(parts[2]))
	if not parts[3].isdigit():
		return None
	stop_time = system.date.fromMillis(long(parts[3]))
	return launchpad.store.rowsAsJson(launchpad.store.hourlyStatsAverage(line_name, tag_folder, start_time, stop_time))


def oeeCardCurrentRate(self, value):
	"""Return the live units-per-time rate in Realtime, or the first average's target rate in Historical."""
	if value.mode == "Realtime":
		if value.rate.time == "minute":
			time = value.secondsElapsed/60.0
		elif value.rate.time == "hour":
			time = value.secondsElapsed/3600.0
		else:
			time = value.secondsElapsed
			
		return round(value.units/time,2)
		
	else:
		return self.custom.averages[0].target_rate


def oeeCardRate(self, value):
	"""Return the line's rate name, target number and time unit as a dict, with defaults when empty."""
	name = "default"
	if value:
		if value.RateName != None:
			name = value.RateName
		number = value.TargetRate
		time = value.RateTime
		if time == "hour":
			number *= 60
		return {"name": name, "number": number, "time": time}
	else:
		return {"name": "", "number": 0, "time": "minute"}


def oeeCardScheduledOn(self, value):
	"""Return whether the card should show data: history exists, or the line is in a scheduled shift."""
	if value.mode == "Historical":
		if value.averages == None:
			return False
		elif len(value.averages) < 1:
			return False
			
		else:
			return True
	elif value.schedule.CurrentShift > 0 or value.interval == "Day":
		return True
	
	elif value.schedule[1].ShiftEnabled == False and value.schedule[2].ShiftEnabled == False and value.schedule[3].ShiftEnabled == False and value.interval != "Shift":
		return True
	
	else:
		return False


def oeeCardRateText(self, value):
	"""Format the target rate as 'number / unit' with a short unit (hr, min, d)."""
	time = ""
	if value.rate.time == "hour":
		time = "hr"
	elif value.rate.time == "minute":
		time = "min"
	elif value.rate.time == "day":
		time = "d"
	else:
		time = value.rate.time[0]
		
	return str(round(value.rate.number,2)) + " / " + time


def oeeCardCurrentRateText(self, value):
	"""Format the current rate to one decimal as 'value / unit' with a short unit."""
	duration = ""
	if value.rate.time == "hour":
		duration = "hr"
	elif value.rate.time == "minute":
		duration = "min"
	else:
		duration = value.rate.time[0]
	return "%.1f" % value.currentRate + " / " + duration


def oeeCardUnavailableMessage(self, value):
	"""Return 'No History Data' for an empty Historical result, otherwise 'Not Scheduled'."""
	messages = ["Not Scheduled", "No History Data"]
	
	pos = 0
	
	if value.mode == "Historical":
		if value.averages == None:
			pos = 1
		elif len(value.averages) < 1:
			pos = 1
	
	return messages[pos]


def oeeHistoricalStats(self, value):
	"""Build the OEE, A, P and Q stat rows (as 1 minus the loss) for the chart, all 1 when empty."""
	if value:
		stats = [
			{"stat": "OEE", "value": value.oee},
			{"stat": "A", "value": 1-value.availability},
			{"stat": "P", "value": 1-value.performance},
			{"stat": "Q", "value": 1-value.quality}
			]
	else:
		stats = [
			{"stat": "OEE", "value": 1},
			{"stat": "A", "value": 1},
			{"stat": "P", "value": 1},
			{"stat": "Q", "value": 1}
			]
	return stats


def lineDisplayOptionsRangeChanged(self, previousValue, currentValue, origin, missedEvents):
	"""Convert the chosen date range into start and stop day offsets in the session's display rangeDays."""
	start = 0
	stop = 0
	
	'''
	Yesterday 0
	This Week 1
	Last Week 2
	This Month 3
	Last Month 4
	Last 30 Days 5
	This Quarter 6
	Last Quarter 7
	Year To Date 8
	Last 365 Days 9
	'''
	if currentValue.value == 0:
		start = -1
		stop = 0
	
	elif currentValue.value == 1:
		day = system.date.getDayOfWeek(system.date.now())
		
		start = 1 - day
		stop = 1
	
	elif currentValue.value == 2:
		day = system.date.getDayOfWeek(system.date.now())
		
		stop = 1 - day
		start = stop - 7
	
	elif currentValue.value == 3:
		day = system.date.getDayOfMonth(system.date.now())
		
		start = 1 - day
		stop = 1
	
	elif currentValue.value == 4:
		month = system.date.getMonth(system.date.now())
		year = system.date.getYear(system.date.now())
		
		stop = 0 - system.date.daysBetween(system.date.midnight(system.date.getDate(year, month, 1)),system.date.midnight(system.date.now()))
		if month == 0:
			year = year - 1
		start = 0 - system.date.daysBetween(system.date.midnight(system.date.getDate(year, month-1, 1)),system.date.midnight(system.date.now()))		

	
	elif currentValue.value == 5:
		start = -30	
		stop = 1
		
	elif currentValue.value == 6:
		month = system.date.getMonth(system.date.now())
		year = system.date.getYear(system.date.now())
		
		
		startYear = year
		stopYear = year
		
		if month <= 2:
			startMonth = 0
			stopMonth = 3
		elif month >= 3 and month <= 5:
			startMonth = 3
			stopMonth = 6
		elif month >= 6 and month <= 8:
			startMonth = 6
			stopMonth = 9
		else:
			startMonth = 9
			stopMonth = 0
			stopYear = year + 1

		
		start = 0 - system.date.daysBetween(system.date.midnight(system.date.getDate(startYear, startMonth, 1)),system.date.midnight(system.date.now()))		
		stop = 0 - system.date.daysBetween(system.date.midnight(system.date.getDate(stopYear, stopMonth, 1)),system.date.midnight(system.date.now()))
	
	elif currentValue.value == 7:
		month = system.date.getMonth(system.date.now())
		year = system.date.getYear(system.date.now())
		
		
		startYear = year
		stopYear = year
		
		if month <= 2:
			startMonth = 9
			startYear = year - 1
			stopMonth = 0
		elif month >= 3 and month <= 5:
			startMonth = 0
			stopMonth = 3
		elif month >= 6 and month <= 8:
			startMonth = 3
			stopMonth = 6
		else:
			startMonth = 6
			stopMonth = 9
		
		start = 0 - system.date.daysBetween(system.date.midnight(system.date.getDate(startYear, startMonth, 1)),system.date.midnight(system.date.now()))		
		stop = 0 - system.date.daysBetween(system.date.midnight(system.date.getDate(stopYear, stopMonth, 1)),system.date.midnight(system.date.now()))
	
	elif currentValue.value == 8:
		year = system.date.getYear(system.date.now())

		stop = 1
		start = 0 - system.date.daysBetween(system.date.midnight(system.date.getDate(year, 0, 1)),system.date.midnight(system.date.now()))	
		
		
	elif currentValue.value == 9:
		start = -365
		stop = 1
		
	if currentValue.value != "":
		self.session.custom.launchpad.oee.display.rangeDays.start = start
		self.session.custom.launchpad.oee.display.rangeDays.stop = stop


def lineSelectionOptions(self, value):
	"""Build the line dropdown options, with an '<All Lines>' entry when showAllOption is set."""
	if self.view.params.showAllOption:
		lines = [{"value":"","label":"<All Lines>"}]
		lines.extend( [{"value":lineName,"label":lineName} for lineName in value])
		return lines
	else:
		return [{"value":lineName,"label":lineName} for lineName in value]


def lineSelectionRefreshLines(self, event):
	"""Reload the line names from the base tag folder into the session and select the first."""
	lineFolderPath = launchpad.oee.BASE_TAG_FOLDER
	lines = launchpad.oee.getLineNames(lineFolderPath) 
	self.session.custom.launchpad.oee.lineTagFolder = lineFolderPath
	self.session.custom.launchpad.oee.lines = lines
	self.session.custom.launchpad.oee.selectedLine = ""
	if len(lines)>0:
		self.session.custom.launchpad.oee.selectedLine = lines[0]


def lineRatesCurrentRateOptions(self, value):
	"""Build the rate dropdown options (name: target uom /interval) from the rates dataset."""
	options = []
	for row in range(value.rowCount):
		option = {
		"value": value.getValueAt(row,"rate_name"),
		"label": "%s: %s %s /%s" %(value.getValueAt(row,"rate_name"), value.getValueAt(row,"target_rate") ,value.getValueAt(row,"uom"), value.getValueAt(row,"interval"))
		}
		options.append(option)
	return options


def lineRatesSetRate(self, event):
	"""Write the selected rate to the line's tags and record the hourly rate change."""
	lineBasePath = self.session.custom.launchpad.oee.lineTagFolder
	tagWritePaths = [self.parent.custom.path, "%s.Tooltip" %(self.parent.custom.path), "%s.EngUnit"%(self.parent.custom.path), self.parent.custom.path.replace("TargetRate", "RateName"), self.parent.custom.path.replace("TargetRate", "RateTime")]
	data = self.parent.custom.selectedData[0]
	interval = data.interval
	if interval.lower() == "hour":
		newTargetRate = data.target_rate/60.0
	else:
		newTargetRate = data.target_rate
	tagWriteValues = [newTargetRate, data.rate_name, data.uom, data.rate_name, data.interval]
	
	system.tag.writeBlocking(tagWritePaths, tagWriteValues)
		
	currentShift = self.view.custom.currentShift
	lineName = self.view.custom.selectedLine
	newTargetRateName = data.rate_name
	hourTimestamp = self.view.custom.currentHourTimestamp
	if currentShift > 0:
		launchpad.oee.recordShiftRateChange(currentShift,  lineName, lineBasePath, newTargetRate, data.rate_name)
	launchpad.oee.recordHourRateChange(hourTimestamp,  lineName,  lineBasePath, newTargetRate, data.rate_name)


def reportDisplayOptionsRangeChanged(self, previousValue, currentValue, origin, missedEvents):
	"""Convert the chosen date range into start and stop day offsets in the session's report rangeDays."""
	start = 0
	stop = 0
	
	'''
	Yesterday 0
	This Week 1
	Last Week 2
	This Month 3
	Last Month 4
	Last 30 Days 5
	This Quarter 6
	Last Quarter 7
	Year To Date 8
	Last 365 Days 9
	'''
	if currentValue.value == 0:
		start = -1
		stop = 0
	
	elif currentValue.value == 1:
		day = system.date.getDayOfWeek(system.date.now())
		
		start = 1 - day
		stop = 1
	
	elif currentValue.value == 2:
		day = system.date.getDayOfWeek(system.date.now())
		
		stop = 1 - day
		start = stop - 7
	
	elif currentValue.value == 3:
		day = system.date.getDayOfMonth(system.date.now())
		
		start = 1 - day
		stop = 1
	
	elif currentValue.value == 4:
		month = system.date.getMonth(system.date.now())
		year = system.date.getYear(system.date.now())
		
		stop = 0 - system.date.daysBetween(system.date.midnight(system.date.getDate(year, month, 1)),system.date.midnight(system.date.now()))
		if month == 0:
			year = year - 1
		start = 0 - system.date.daysBetween(system.date.midnight(system.date.getDate(year, month-1, 1)),system.date.midnight(system.date.now()))		

	
	elif currentValue.value == 5:
		start = -30	
		stop = 1
		
	elif currentValue.value == 6:
		month = system.date.getMonth(system.date.now())
		year = system.date.getYear(system.date.now())
		
		
		startYear = year
		stopYear = year
		
		if month <= 2:
			startMonth = 0
			stopMonth = 3
		elif month >= 3 and month <= 5:
			startMonth = 3
			stopMonth = 6
		elif month >= 6 and month <= 8:
			startMonth = 6
			stopMonth = 9
		else:
			startMonth = 9
			stopMonth = 0
			stopYear = year + 1

		
		start = 0 - system.date.daysBetween(system.date.midnight(system.date.getDate(startYear, startMonth, 1)),system.date.midnight(system.date.now()))		
		stop = 0 - system.date.daysBetween(system.date.midnight(system.date.getDate(stopYear, stopMonth, 1)),system.date.midnight(system.date.now()))
	
	elif currentValue.value == 7:
		month = system.date.getMonth(system.date.now())
		year = system.date.getYear(system.date.now())
		
		
		startYear = year
		stopYear = year
		
		if month <= 2:
			startMonth = 9
			startYear = year - 1
			stopMonth = 0
		elif month >= 3 and month <= 5:
			startMonth = 0
			stopMonth = 3
		elif month >= 6 and month <= 8:
			startMonth = 3
			stopMonth = 6
		else:
			startMonth = 6
			stopMonth = 9
		
		start = 0 - system.date.daysBetween(system.date.midnight(system.date.getDate(startYear, startMonth, 1)),system.date.midnight(system.date.now()))		
		stop = 0 - system.date.daysBetween(system.date.midnight(system.date.getDate(stopYear, stopMonth, 1)),system.date.midnight(system.date.now()))
	
	elif currentValue.value == 8:
		year = system.date.getYear(system.date.now())

		stop = 1
		start = 0 - system.date.daysBetween(system.date.midnight(system.date.getDate(year, 0, 1)),system.date.midnight(system.date.now()))	
		
		
	elif currentValue.value == 9:
		start = -365
		stop = 1
		
	if currentValue.value != "":
		self.session.custom.launchpad.oee.report.rangeDays.start = start
		self.session.custom.launchpad.oee.report.rangeDays.stop = stop


def lineViewOeeSeries(self, value):
	"""Build the OEE trend dataset (A, P, Q, OEE), dropping the in-progress interval in Realtime."""
	pyData = system.dataset.toPyDataSet(value.data)
	headers = ["Timestamp", "Availability", "Performance", "Quality", "OEE"]
	data = []
	# Realtime only: the last row is the in-progress interval and drags the line down;
	# in Historical every row is complete.
	rows = pyData.getRowCount()
	if value.mode == 'Realtime' and rows > 0:
		rows -= 1
	for r in range(rows):
		data.append([pyData.getValueAt(r, "time_stamp"), pyData.getValueAt(r, "oee_a"),
					pyData.getValueAt(r, "oee_p"), pyData.getValueAt(r, "oee_q"),
					pyData.getValueAt(r, "oee")])
	return system.dataset.toDataSet(headers, data)


def lineViewProductionSeries(self, value):
	"""Build the rejects, target and production dataset, dropping the in-progress interval in Realtime."""
	pyData = system.dataset.toPyDataSet(value.data)
	headers = ["Timestamp", "Rejects", "Target", "Production"]
	data = []
	# Realtime only: the last row is the in-progress interval and drags the line down;
	# in Historical every row is complete.
	rows = pyData.getRowCount()
	if value.mode == 'Realtime' and rows > 0:
		rows -= 1
	for r in range(rows):
		data.append([pyData.getValueAt(r, "time_stamp"), pyData.getValueAt(r, "reject_count"),
					pyData.getValueAt(r, "target_rate") * 60, pyData.getValueAt(r, "production_count")])
	return system.dataset.toDataSet(headers, data)


def hourlyStatsJson(self, value):
	"""Parse the |~|-delimited binding text and return the hourly stats, or None if incomplete."""
	# The expression carries the parameters as text so its references, not this script,
	# make the binding re-evaluate.
	parts = (value or u"").split(u"|~|")
	if len(parts) != 4:
		# A date not yet arrived leaves the expression short: return None, which renders empty,
		# where an exception renders as a red box over the chart.
		return None
	line_name = parts[0]
	tag_folder = parts[1]
	if not parts[2].isdigit():
		return None
	start_time = system.date.fromMillis(long(parts[2]))
	if not parts[3].isdigit():
		return None
	stop_time = system.date.fromMillis(long(parts[3]))
	return launchpad.store.hourlyStats(line_name, tag_folder, start_time, stop_time)


def lineViewStats(self, value):
	"""Return OEE, A, P, Q and downtime from the live tags in Realtime or the first average in Historical."""
		
	if value.mode == "Realtime":
		
		a = value.tag["%sOee"%(value.interval)]["A"]
		p = value.tag["%sOee"%(value.interval)]["P"]
		q = value.tag["%sOee"%(value.interval)]["Q"]
		d = value.tag["%sOee"%(value.interval)]["D"]
		oee = value.tag["%sOee"%(value.interval)]["O"]
		data = {"oee":oee, "availability":a, "performance":p, "quality":q, "downtime":d, "currentShift": self.custom.tag.Schedule.CurrentShift}
	else:
		if self.custom.avgData == None:
			data = {}
		elif len(self.custom.avgData) >= 1:
			a =  self.custom.avgData[0].oee_a
			oee = self.custom.avgData[0].oee
			p = self.custom.avgData[0].oee_p
			q = self.custom.avgData[0].oee_q
			d = self.custom.avgData[0].downtime
			data = {"oee":oee, "availability":a, "performance":p, "quality":q, "downtime":d, "currentShift":0}
		else:
			data = {}
		
	

	
	return data


def lineViewTopProduction(self, value):
	"""Parse the |~|-delimited binding text and return the top production hours, or None if incomplete."""
	# The expression carries the parameters as text so its references, not this script,
	# make the binding re-evaluate.
	parts = (value or u"").split(u"|~|")
	if len(parts) != 3:
		# A date not yet arrived leaves the expression short: return None, which renders empty,
		# where an exception renders as a red box over the chart.
		return None
	lineName = parts[0]
	if not parts[1].isdigit():
		return None
	startTime = system.date.fromMillis(long(parts[1]))
	if not parts[2].isdigit():
		return None
	endTime = system.date.fromMillis(long(parts[2]))
	return launchpad.store.topProduction(lineName, startTime, endTime)


def lineViewLargeProductionInstances(self, value):
	"""Build up to 7 repeater instances (label, production, target) from the top production rows."""
	pyData = system.dataset.toPyDataSet(value)
	instances = []
	
	
	
	for r in range(7):
		if r < pyData.getRowCount():
			startDate = pyData.getValueAt(r, "hour_timestamp")
			label = system.date.format(startDate, "dd/MM/yyyy HH:mm")
		
			instances.append({
			"instanceStyle": {
				"classes": ""
			},
			"instancePosition": {},
			"production": pyData.getValueAt(r, "hour_production_count"),
			"label": label,
			"target": pyData.getValueAt(r, "target_hour")
			})
		
	return instances


def lineViewSmallProductionInstances(self, value):
	"""Build up to 8 repeater instances (label, production, target) from the top production rows."""
	pyData = system.dataset.toPyDataSet(value)
	instances = []
	
	
	
	for r in range(8):
		if r < pyData.getRowCount():
			startDate = pyData.getValueAt(r, "hour_timestamp")
			label = system.date.format(startDate, "dd/MM/yyyy HH:mm")
		
			instances.append({
			"instanceStyle": {
				"classes": ""
			},
			"instancePosition": {},
			"production": pyData.getValueAt(r, "hour_production_count"),
			"label": label,
			"target": pyData.getValueAt(r, "target_hour")
			})
		
	return instances


def oeeValuesAddTargetProduction(self, value):
	"""Add a TargetProd column: minutes running times the rate value for each row."""
	

	pt = []
	for row in range(value.rowCount):
		runTime = value.getValueAt(row,"SecondsRunning") /60.0
		pt.append(runTime*value.getValueAt(row,"RateValue"))
	

	value= system.dataset.addColumn(value,   pt, "TargetProd", float)
	return value


def overviewDowntimeBars(self, value):
	"""Build bar instances per line with downtime as a fraction of elapsed minutes."""
	instances = []
	for row in value:
		instance = {
		"format": "#0.0%",
		"high": 1,
		"low": 0,
		"title": row.line_name,
		"units": "",
		"value": row.down_minutes/row.minutes_elapsed
		
		}
		instances.append(instance)

	return instances


def overviewOeeBars(self, value):
	"""Build bar instances per line with its OEE value."""
	instances = []
	for row in value:
		instance = {
		"format": "#0.0%",
		"high": 1,
		"low": 0,
		"title": row.line_name,
		"units": "",
		"value": row.oee
		}
		instances.append(instance)

	return instances


def greyOutWhenEmptyStyle(self, value):
	"""Return a greyed-out, non-interactive style when the value is empty, otherwise an empty style."""
	if value == '':
		return {
			"filter": "contrast(0) brightness(0.26)",
			"pointer-events": "none"
		}
	else:
		return {}


def overviewLargeOeeBarParams(self, value):
	"""Build the OEE bars' params: tag property in Realtime, supplied instances in Historical."""
	if value["mode"] == "Realtime":
		params ={
		"folderPath": value["folderPath"],
		"title": "OEE",
		"property": "%sOee/O" %(value["interval"])
		}
	else:
		params = {"title": "OEE", "instances":value["instances"]}
	return params


def overviewLargeDowntimeBarParams(self, value):
	"""Build the downtime bars' params: tag property in Realtime, supplied instances in Historical."""
	if value["mode"] == "Realtime":
		params ={
		"folderPath": value["folderPath"],
		"title": "Downtime",
		"property": "%sOee/D" %(value["interval"])
		}
	else:
		params = {"title": "Downtime", "instances":value["instances"] }
	return params


def overviewLineInstances(self, value):
	"""Build a repeater instance per line with its tag path, interval, mode and time range."""
	instances = []
	
	for item in value.oeeConfig.lines:
		instances.append({
		"instanceStyle": {
			"classes": ""
		},
		"instancePosition": {},
		"path": value.oeeConfig.lineTagFolder + "/" + item,
		"interval": value.interval,
		"mode": value.mode,
		"startTime": value.startTime,
		"stopTime": value.stopTime
		})
		
	return instances


def overviewSmallOeeBarParams(self, value):
	"""Build the untitled OEE bars' params: tag property in Realtime, supplied instances in Historical."""
	if value["mode"] == "Realtime":
		params ={
		"folderPath": value["folderPath"],
		"title": "",
		"property": "%sOee/O" %(value["interval"])
		}
	else:
		params = {"title": "", "instances":value["instances"]}
	return params


def overviewSmallDowntimeBarParams(self, value):
	"""Build the untitled downtime bars' params: tag property in Realtime, supplied instances in Historical."""
	if value["mode"] == "Realtime":
		params ={
		"folderPath": value["folderPath"],
		"title": "",
		"property": "%sOee/D" %(value["interval"])
		}
	else:
		params = {"title": "", "instances":value["instances"] }
	return params


def productionSummaryDailyStats(self, value):
	"""Parse the |~|-delimited binding text and return the daily stats, or None if incomplete."""
	# The expression carries the parameters as text so its references, not this script,
	# make the binding re-evaluate.
	parts = (value or u"").split(u"|~|")
	if len(parts) != 4:
		# A date not yet arrived leaves the expression short: return None, which renders empty,
		# where an exception renders as a red box over the chart.
		return None
	line_name = parts[0]
	tag_folder = parts[1]
	if not parts[2].isdigit():
		return None
	start_time = system.date.fromMillis(long(parts[2]))
	if not parts[3].isdigit():
		return None
	stop_time = system.date.fromMillis(long(parts[3]))
	return launchpad.store.dailyStats(line_name, tag_folder, start_time, stop_time)


def productionSummaryShiftStats(self, value):
	"""Parse the |~|-delimited binding text and return the shift stats, or None if incomplete."""
	# The expression carries the parameters as text so its references, not this script,
	# make the binding re-evaluate.
	parts = (value or u"").split(u"|~|")
	if len(parts) != 4:
		# A date not yet arrived leaves the expression short: return None, which renders empty,
		# where an exception renders as a red box over the chart.
		return None
	line_name = parts[0]
	tag_folder = parts[1]
	if not parts[2].isdigit():
		return None
	start_time = system.date.fromMillis(long(parts[2]))
	if not parts[3].isdigit():
		return None
	stop_time = system.date.fromMillis(long(parts[3]))
	return launchpad.store.shiftStats(line_name, tag_folder, start_time, stop_time)


def productionSummaryHourlyAverage(self, value):
	"""Parse the |~|-delimited binding text and return the hourly stats average, or None if incomplete."""
	# The expression carries the parameters as text so its references, not this script,
	# make the binding re-evaluate.
	parts = (value or u"").split(u"|~|")
	if len(parts) != 4:
		# A date not yet arrived leaves the expression short: return None, which renders empty,
		# where an exception renders as a red box over the chart.
		return None
	line_name = parts[0]
	tag_folder = parts[1]
	if not parts[2].isdigit():
		return None
	start_time = system.date.fromMillis(long(parts[2]))
	if not parts[3].isdigit():
		return None
	stop_time = system.date.fromMillis(long(parts[3]))
	return launchpad.store.hourlyStatsAverage(line_name, tag_folder, start_time, stop_time)


def ratesSetAddEditMode(self, payload):
	"""Set the add and update mode flags on the editor from the message payload's mode."""
	mode = payload["mode"]
	self.print("mode set")
	if mode == "add":
		self.custom.addMode = True
		self.custom.updateMode = False
	elif mode == "update":
		self.custom.addMode = False
		self.custom.updateMode = True
	else:
		self.custom.addMode = False
		self.custom.updateMode = False


def ratesSave(self, event):
	"""Insert or update the rate record from the form, then refresh the rates table and rates."""
	tableName = "ex_launchpad_oee_rate"
	databaseName = launchpad.oee.db()
	rate_name = self.parent.parent.getChild("NameEntry").getChild("TextEntry").props.text
	interval = self.parent.parent.getChild("RateEntry").getChild("Interval").props.value
	uom = self.parent.parent.getChild("RateEntry").getChild("UnitsEntry").props.text
	target_rate = self.parent.parent.getChild("RateEntry").getChild("RateValue").props.value
	
	if self.parent.parent.parent.getChild("AddEdit").custom.updateMode:
		data = {"rate_name": rate_name , "uom": uom, "target_rate": target_rate, "interval": interval}
		key_rate_name = self.parent.parent.parent.getChild("RateTable").props.selection.data[0].rate_name
		keys = {"rate_name": key_rate_name }
		launchpad.sql.runDatabaseUpdate(tableName, databaseName, data, keys)
	else:
		data = {"rate_name": rate_name , "uom": uom, "target_rate": target_rate, "interval": interval}
		launchpad.sql.runDatabaseInsert(tableName, databaseName, data)
	system.perspective.sendMessage("launchpadOeeRateMode", payload = {"mode": ""} , scope="page")
	system.perspective.sendMessage("launchpadOeeRefreshRatesTable", scope="page")	
	system.perspective.sendMessage("launchpadOeeRefreshRates", scope="page")


def ratesDelete(self, event):
	"""Delete the selected rate record, refresh the rates, and reset the table and editor mode."""
	
	tableName = "ex_launchpad_oee_rate"

	key_rate_name = self.parent.parent.parent.parent.getChild("RateTable").props.selection.data[0].rate_name
	databaseName = launchpad.oee.db()
	launchpad.sql.runDatabaseDelete(tableName, databaseName, idValue=key_rate_name, idField="rate_name")
	
	system.perspective.sendMessage("launchpadOeeRefreshRatesTable", scope="page")	
	system.perspective.sendMessage("launchpadOeeRefreshRates", scope="page")
	self.parent.parent.parent.getChild("Actions").custom.deleteMode = False
	system.perspective.sendMessage("launchpadOeeTableReset", scope="page")
	system.perspective.sendMessage("launchpadOeeRateMode", payload = {"mode": ""} , scope="page")


def settingsRunSetup(self, event):
	"""Run Setup on a worker thread, streaming its transcript into view.custom.setupResult."""
	# Worker thread: a bare gateway takes up to a minute and a synchronous click freezes the button.
	view = self.view
	view.custom.setupResult = "starting..."
	def build():
		def progress(message):
			view.custom.setupResult = message
		report = launchpad.setup.run(progress=progress)
		view.custom.setupResult = report.get("detail") or \
			launchpad.setup.detail(report)
	system.util.invokeAsynchronous(build)


def settingsCheckSetup(self, event):
	"""Check what Setup has and has not put in place, without changing anything, and show the result."""
	view = self.view
	view.custom.setupResult = "checking..."
	def look():
		view.custom.setupResult = launchpad.setup.detail(
			launchpad.setup.check())
	system.util.invokeAsynchronous(look)


def settingsUpdateTags(self, event):
	"""Reinstall the tag definitions on a worker thread and tell the user to restart the gateway."""
	# Reinstalling over a live subscription leaves the old definition's script running
	# until the gateway restarts.
	view = self.view
	view.custom.setupResult = "updating the tag definitions..."
	def build():
		def progress(message):
			view.custom.setupResult = message
		report = launchpad.setup.run(progress=progress, force=True, tags=True)
		view.custom.setupResult = launchpad.setup.detail(report) + (
			"\n\nRESTART THE GATEWAY to finish: until you do, the previous "
			"definition's script is still subscribed as well and the demo counts "
			"more than once per tick.")
	system.util.invokeAsynchronous(build)
