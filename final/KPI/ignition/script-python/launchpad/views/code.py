"""Logic behind the KPI views' script transforms and event handlers."""


def barChartHistoryData(self, value):
	"""Query tag history for the configured tags and return one dict per row, with a 'blank' column."""
	if value.get('mode') == 'Historical':
		startDate = value.get('startDate')
		endDate = value.get('endDate')
	else:
		startDate = value.get('realtime').get('startDate')
		endDate = value.get('realtime').get('endDate')
	
	tagPaths = []
	columnNames = []
	
	for tag in value['tags']:
		tagPaths.append(tag['path'])
		columnNames.append(tag['alias'])
		
	res = system.tag.queryTagHistory(paths = tagPaths, aggregationMode = value['aggMode'], columnNames = columnNames, startDate = startDate, endDate = endDate, intervalMinutes = value.get('interval'))
	resColNames = system.dataset.getColumnHeaders(res)
	
	data = []

	for x in range(0, res.getRowCount()):
		newRow = {'blank': 0}
		for resColName in resColNames:
			val = res.getValueAt(x, resColName)
			newRow[resColName] = val
			
		data.append(newRow)
		
	return data


def barChartTags(self, value):
	"""Build the tag list (alias, realtime path) for up to two tag paths, named from Documentation and units."""
	def getTagName(tagPath):
		tagName = system.tag.read('{tagPath}.Documentation'.format(tagPath = tagPath)).value
		
		if not tagName:
			tagName = system.tag.read('{tagPath}.name'.format(tagPath = tagPath)).value
			
		engUnit = system.tag.read('{tagPath}.engUnit'.format(tagPath = tagPath)).value
		
		if engUnit:
			return '{tagName} ({engUnit})'.format(tagName = tagName, engUnit = engUnit)
		else:
			return tagName
			
	def getRealtimePath(historicalPath):
		tagDelim = ":/tag:"
		
		parts = historicalPath.rsplit(tagDelim, 1)
		
		extractedPath = ""
		
		if len(parts) > 1:
			extractedPath = parts[1]
		else:
			extractedPath = historicalPath
	
		provName = "default"
		
		if tagDelim in historicalPath:
			segBeforeTagDelim = historicalPath.split(tagDelim, 1)[0]
			lastColonIndex = segBeforeTagDelim.rfind(":")
			
			if lastColonIndex != -1:
				provName = segBeforeTagDelim[lastColonIndex + 1:]
			else:
				provName = segBeforeTagDelim.rsplit(":", 1)[-1]
				
				if provName.startswith("histprov"):
					provName = provName.split(":", 1)[-1]
				if not provName:
					provName = "default"
					
		return "[{}]{}".format(provName, extractedPath)
	
	tags = []
	
	tagPath1 = value.get('tagPath1')
	tagPath2 = value.get('tagPath2')
	
	realtimePath1 = getRealtimePath(tagPath1) if ":/tag:" in tagPath1 else tagPath1
	realtimePath2 = getRealtimePath(tagPath2) if ":/tag:" in tagPath2 else tagPath2
	
	if tagPath1:
		tags.append({"alias": getTagName(realtimePath1), "path": realtimePath1})
		
	if tagPath2:
		tags.append({"alias": getTagName(realtimePath2), "path": realtimePath2})
		
	return tags


def barChartOpenHistoryPopup(self, event):
	"""Open the dual-tag history popup for this chart's first two tags."""
	viewPath = 'Launchpad/Kpi/EmbeddedViews/PopupDualTag'
	tags = self.view.custom.tags
	if len(tags) == 0:
		path1 = ''
		path2 = ''
	elif len(tags) == 1:
		path1 = tags[0]['path']
		path2 = ''
	else:
		path1 = tags[0]['path']
		path2 = tags[1]['path']
		
	viewParams = {'path1': path1, 'path2': path2, 'historyProvider': self.session.custom.launchpad.historyProvider}
	popupTitle = 'Historical Data'
	launchpad.util.popup(self, viewPath, viewParams, popupTitle)


def barChartOpenHistoryPopupOnKey(self, event):
	"""On Enter or Space, open the dual-tag history popup for this chart's first two tags."""
	if event.key in ('Enter', ' '):
		viewPath = 'Launchpad/Kpi/EmbeddedViews/PopupDualTag'
		tags = self.view.custom.tags
		if len(tags) == 0:
			path1 = ''
			path2 = ''
		elif len(tags) == 1:
			path1 = tags[0]['path']
			path2 = ''
		else:
			path1 = tags[0]['path']
			path2 = tags[1]['path']
			
		viewParams = {'path1': path1, 'path2': path2, 'historyProvider': self.session.custom.launchpad.historyProvider}
		popupTitle = 'Historical Data'
		launchpad.util.popup(self, viewPath, viewParams, popupTitle)


def barChartSeries(self, value):
	"""Build the column series definitions for the bar chart, one per tag plus a hidden blank series."""
	columns = [{"name": '', "label": {"text": ''}, "visible": True, "hiddenInLegend": True, "defaultState": {"visible": True},
					"data": {"source": "data", "x": "t_stamp", "y": "blank"}, "xAxis": "date", "yAxis": "y", "zIndex": 1, 
					"tooltip": {"enabled": True, "text": "", "cornerRadius": 3, "pointerLength": 4, "background": {"color": "", "opacity": 1}},
					"render": "column", "candlestick": {"open": {"x": "", "y": ""}, "high": {"x": "", "y": ""}, "low": {"x": "", "y": ""}, 
					"appearance": {"fill": {"color": "", "opacity": 1}, "stroke": {"color": "", "opacity": 1, "width": 1}, "stacked": False,
					"deriveFieldsFromData": {"fill": {"color": "", "opacity": ""}, "stroke": {"color": "", "opacity": "", "width": ""}}, 
					"heatRules": {"enabled": False, "max": "", "min": "", "dataField": ""}}}, "column": {"open": {"x": "", "y": ""},
					"appearance": {"fill": {"color": '', "opacity": 1}, "stroke": {"color": "", "opacity": 0, "width": 0}, "width": None, "height": None, "stacked": False,
					"deriveFieldsFromData": {"fill": {"color": "", "opacity": ""}, "stroke": {"color": "","opacity": "","width": ""}}, 
					"heatRules": {"enabled": False, "max": "", "min": "", "dataField": ""}}}, "line": {"open": {"x": "", "y": ""}, 
					"appearance": {"connect": True, "tensionX": 1, "tensionY": 1, "minDistance": 0.5, "stroke": {"width": 3, "opacity": 1, "color": "", "dashArray": ""},
					"fill": {"color": "", "opacity": 0}, "bullets": [{"enabled": False, "render": "circle", "width": 10, "height": 10,
					"label": {"text": "{value}","position": {"dx": 0, "dy": 0}}, "tooltip": {"enabled": True, "text": "{name}: [bold]{valueY}[/]", "cornerRadius": 3, "pointerLength": 4,
					"background": {"color": "", "opacity": 1}}, "fill": {"color": "", "opacity": 1}, "stroke": {"color": "", "width": 1, "opacity": 1}, "rotation": 0, 
					"deriveFieldsFromData": {"fill": {"color": "", "opacity": ""}, "stroke": {"color": "", "opacity": "", "width": ""}, "rotation": ""},
					"heatRules": {"enabled": False, "max": 100, "min": 2, "dataField": ""}}]}}, "stepLine": {"open": {"x": "", "y": ""},"appearance": {"connect": True, "tensionX": 1, 
					"tensionY": 1, "minDistance": 0.5, "stroke": {"width": 3, "opacity": 1, "color": "", "dashArray": ""}, "fill": {"color": "", "opacity": 0}, "bullets": [{
					"enabled": True, "render": "circle", "width": 10, "height": 10, "label": {"text": "{value}", "position": {"dx": 0, "dy": 0}}, "tooltip": {"enabled": True,
					"text": "{name}: [bold]{valueY}[/]", "cornerRadius": 3, "pointerLength": 4, "background": {"color": "", "opacity": 1}}, "fill": {"color": "", "opacity": 1},
					"stroke": {"color": "", "width": 1, "opacity": 1}, "rotation": 0, "deriveFieldsFromData": {"fill": {"color": "", "opacity": ""}, "stroke": {"color": "", "opacity": "",
					"width": ""}, "rotation": ""}, "heatRules": {"enabled": False, "max": 100, "min": 2, "dataField": ""}}]}}}]
	
	colors = ["#FFB35E", "#62C3DA"]
	index = 0
	
	tooltipText = "{name}: [bold]{valueY}[/]\nDate: [bold]{dateX.formatDate('h a')}[/]" if value.get('interval') == 60 else "{name}: [bold]{valueY}[/]\nDate: [bold]{dateX.formatDate('M/d')}[/]"
	
	for tag in value.get('tags'):
		try:
			color = colors[index]
		except:
			# Designed for two tags; beyond that let the chart pick a color.
			color = ''
		
		column = {"name": tag['alias'], "label": {"text": tag['alias']}, "visible": True, "hiddenInLegend": False, "defaultState": {"visible": True},
					"data": {"source": "data", "x": "t_stamp", "y": tag['alias']}, "xAxis": "date", "yAxis": "y", "zIndex": 1, 
					"tooltip": {"enabled": True, "text": tooltipText, "cornerRadius": 3, "pointerLength": 4, "background": {"color": "", "opacity": 1}},
					"render": "column", "candlestick": {"open": {"x": "", "y": ""}, "high": {"x": "", "y": ""}, "low": {"x": "", "y": ""}, 
					"appearance": {"fill": {"color": "", "opacity": 1}, "stroke": {"color": "", "opacity": 1, "width": 1}, "stacked": False,
					"deriveFieldsFromData": {"fill": {"color": "", "opacity": ""}, "stroke": {"color": "", "opacity": "", "width": ""}}, 
					"heatRules": {"enabled": False, "max": "", "min": "", "dataField": ""}}}, "column": {"open": {"x": "", "y": ""},
					"appearance": {"fill": {"color": color, "opacity": 1}, "stroke": {"color": "", "opacity": 0, "width": 0}, "width": None, "height": None, "stacked": False,
					"deriveFieldsFromData": {"fill": {"color": "", "opacity": ""}, "stroke": {"color": "","opacity": "","width": ""}}, 
					"heatRules": {"enabled": False, "max": "", "min": "", "dataField": ""}}}, "line": {"open": {"x": "", "y": ""}, 
					"appearance": {"connect": True, "tensionX": 1, "tensionY": 1, "minDistance": 0.5, "stroke": {"width": 3, "opacity": 1, "color": "", "dashArray": ""},
					"fill": {"color": "", "opacity": 0}, "bullets": [{"enabled": False, "render": "circle", "width": 10, "height": 10,
					"label": {"text": "{value}","position": {"dx": 0, "dy": 0}}, "tooltip": {"enabled": True, "text": "{name}: [bold]{valueY}[/]", "cornerRadius": 3, "pointerLength": 4,
					"background": {"color": "", "opacity": 1}}, "fill": {"color": "", "opacity": 1}, "stroke": {"color": "", "width": 1, "opacity": 1}, "rotation": 0, 
					"deriveFieldsFromData": {"fill": {"color": "", "opacity": ""}, "stroke": {"color": "", "opacity": "", "width": ""}, "rotation": ""},
					"heatRules": {"enabled": False, "max": 100, "min": 2, "dataField": ""}}]}}, "stepLine": {"open": {"x": "", "y": ""},"appearance": {"connect": True, "tensionX": 1, 
					"tensionY": 1, "minDistance": 0.5, "stroke": {"width": 3, "opacity": 1, "color": "", "dashArray": ""}, "fill": {"color": "", "opacity": 0}, "bullets": [{
					"enabled": True, "render": "circle", "width": 10, "height": 10, "label": {"text": "{value}", "position": {"dx": 0, "dy": 0}}, "tooltip": {"enabled": True,
					"text": "{name}: [bold]{valueY}[/]", "cornerRadius": 3, "pointerLength": 4, "background": {"color": "", "opacity": 1}}, "fill": {"color": "", "opacity": 1},
					"stroke": {"color": "", "width": 1, "opacity": 1}, "rotation": 0, "deriveFieldsFromData": {"fill": {"color": "", "opacity": ""}, "stroke": {"color": "", "opacity": "",
					"width": ""}, "rotation": ""}, "heatRules": {"enabled": False, "max": 100, "min": 2, "dataField": ""}}]}}}
			
		columns.append(column)
		
		index = index + 1
		
	columns.append({"name": '', "label": {"text": ''}, "visible": True, "hiddenInLegend": True, "defaultState": {"visible": True},
					"data": {"source": "data", "x": "t_stamp", "y": "blank"}, "xAxis": "date", "yAxis": "y", "zIndex": 1, 
					"tooltip": {"enabled": True, "text": "", "cornerRadius": 3, "pointerLength": 4, "background": {"color": "", "opacity": 1}},
					"render": "column", "candlestick": {"open": {"x": "", "y": ""}, "high": {"x": "", "y": ""}, "low": {"x": "", "y": ""}, 
					"appearance": {"fill": {"color": "", "opacity": 1}, "stroke": {"color": "", "opacity": 1, "width": 1}, "stacked": False,
					"deriveFieldsFromData": {"fill": {"color": "", "opacity": ""}, "stroke": {"color": "", "opacity": "", "width": ""}}, 
					"heatRules": {"enabled": False, "max": "", "min": "", "dataField": ""}}}, "column": {"open": {"x": "", "y": ""},
					"appearance": {"fill": {"color": '', "opacity": 1}, "stroke": {"color": "", "opacity": 0, "width": 0}, "width": None, "height": None, "stacked": False,
					"deriveFieldsFromData": {"fill": {"color": "", "opacity": ""}, "stroke": {"color": "","opacity": "","width": ""}}, 
					"heatRules": {"enabled": False, "max": "", "min": "", "dataField": ""}}}, "line": {"open": {"x": "", "y": ""}, 
					"appearance": {"connect": True, "tensionX": 1, "tensionY": 1, "minDistance": 0.5, "stroke": {"width": 3, "opacity": 1, "color": "", "dashArray": ""},
					"fill": {"color": "", "opacity": 0}, "bullets": [{"enabled": False, "render": "circle", "width": 10, "height": 10,
					"label": {"text": "{value}","position": {"dx": 0, "dy": 0}}, "tooltip": {"enabled": True, "text": "{name}: [bold]{valueY}[/]", "cornerRadius": 3, "pointerLength": 4,
					"background": {"color": "", "opacity": 1}}, "fill": {"color": "", "opacity": 1}, "stroke": {"color": "", "width": 1, "opacity": 1}, "rotation": 0, 
					"deriveFieldsFromData": {"fill": {"color": "", "opacity": ""}, "stroke": {"color": "", "opacity": "", "width": ""}, "rotation": ""},
					"heatRules": {"enabled": False, "max": 100, "min": 2, "dataField": ""}}]}}, "stepLine": {"open": {"x": "", "y": ""},"appearance": {"connect": True, "tensionX": 1, 
					"tensionY": 1, "minDistance": 0.5, "stroke": {"width": 3, "opacity": 1, "color": "", "dashArray": ""}, "fill": {"color": "", "opacity": 0}, "bullets": [{
					"enabled": True, "render": "circle", "width": 10, "height": 10, "label": {"text": "{value}", "position": {"dx": 0, "dy": 0}}, "tooltip": {"enabled": True,
					"text": "{name}: [bold]{valueY}[/]", "cornerRadius": 3, "pointerLength": 4, "background": {"color": "", "opacity": 1}}, "fill": {"color": "", "opacity": 1},
					"stroke": {"color": "", "width": 1, "opacity": 1}, "rotation": 0, "deriveFieldsFromData": {"fill": {"color": "", "opacity": ""}, "stroke": {"color": "", "opacity": "",
					"width": ""}, "rotation": ""}, "heatRules": {"enabled": False, "max": 100, "min": 2, "dataField": ""}}]}}})
					
	return columns


def lineChartTags(self, value):
	"""Build the tag list (aggregate, alias, realtime path) for up to two tag paths."""
	def getTagName(tagPath):
		tagName = system.tag.read('{tagPath}.Documentation'.format(tagPath = tagPath)).value
		
		if not tagName:
			tagName = system.tag.read('{tagPath}.name'.format(tagPath = tagPath)).value
			
		engUnit = system.tag.read('{tagPath}.engUnit'.format(tagPath = tagPath)).value
		
		if engUnit:
			return '{tagName} ({engUnit})'.format(tagName = tagName, engUnit = engUnit)
		else:
			return tagName
			
	def getRealtimePath(historicalPath):
		tagDelim = ":/tag:"
		
		parts = historicalPath.rsplit(tagDelim, 1)
		
		extractedPath = ""
		
		if len(parts) > 1:
			extractedPath = parts[1]
		else:
			extractedPath = historicalPath
	
		provName = "default"
		
		if tagDelim in historicalPath:
			segBeforeTagDelim = historicalPath.split(tagDelim, 1)[0]
			lastColonIndex = segBeforeTagDelim.rfind(":")
			
			if lastColonIndex != -1:
				provName = segBeforeTagDelim[lastColonIndex + 1:]
			else:
				provName = segBeforeTagDelim.rsplit(":", 1)[-1]
				
				if provName.startswith("histprov"):
					provName = provName.split(":", 1)[-1]
				if not provName:
					provName = "default"
					
		return "[{}]{}".format(provName, extractedPath)
		
	tags = []
	
	tagPath1 = value.get('tagPath1')
	tagPath2 = value.get('tagPath2')
	
	realtimePath1 = getRealtimePath(tagPath1) if ":/tag:" in tagPath1 else tagPath1
	realtimePath2 = getRealtimePath(tagPath2) if ":/tag:" in tagPath2 else tagPath2
	
	if tagPath1:
		tags.append({"aggregate": value.get('aggMode'), "alias": getTagName(realtimePath1), "path": realtimePath1})
		
	if tagPath2:
		tags.append({"aggregate": value.get('aggMode'), "alias": getTagName(realtimePath2), "path": realtimePath2})
		
	return tags


def lineChartOpenHistoryPopup(self, event):
	"""Open the dual-tag history popup for this chart's first two tags, titled from the view parameter."""
	viewPath = 'Launchpad/Kpi/EmbeddedViews/PopupDualTag'
	tags = self.view.custom.tags
	if len(tags) == 0:
		path1 = ''
		path2 = ''
	elif len(tags) == 1:
		path1 = tags[0]['path']
		path2 = ''
	else:
		path1 = tags[0]['path']
		path2 = tags[1]['path']
	
	viewParams = {'path1': path1, 'path2': path2, 'historyProvider': self.session.custom.launchpad.historyProvider}
	popupTitle = self.view.params.title
	launchpad.util.popup(self, viewPath, viewParams, popupTitle)


def lineChartOpenHistoryPopupOnKey(self, event):
	"""On Enter or Space, open the dual-tag history popup, titled from the view parameter."""
	if event.key in ('Enter', ' '):
		viewPath = 'Launchpad/Kpi/EmbeddedViews/PopupDualTag'
		tags = self.view.custom.tags
		if len(tags) == 0:
			path1 = ''
			path2 = ''
		elif len(tags) == 1:
			path1 = tags[0]['path']
			path2 = ''
		else:
			path1 = tags[0]['path']
			path2 = tags[1]['path']
		
		viewParams = {'path1': path1, 'path2': path2, 'historyProvider': self.session.custom.launchpad.historyProvider}
		popupTitle = self.view.params.title
		launchpad.util.popup(self, viewPath, viewParams, popupTitle)


def lineChartTrendColumns(self, value):
	"""Build the trend column definitions for each tag, colouring the first two with the KPI theme colours."""
	columns = []
	
	colors = ["var(--kpi-primary)", "var(--kpi-highlight)"]
	index = 0
	
	for tag in value:
		try:
			color = colors[index]
		except:
			# Designed for two tags; beyond that let the chart pick a color.
			color = None
		
		column = {"key": tag.get('alias'), "color": color, "styles": {"normal": {"stroke": {"color": "", "width": 2, "opacity": None, "dashArray": None},
			"fill": {"color": "", "opacity": None}}, "highlighted": {"stroke": {"color": "", "width": 2, "opacity": None, "dashArray": None},
			"fill": {"color": "", "opacity": None}}, "selected": {"stroke": {"color": "", "width": 2, "opacity": None, "dashArray": None},
			"fill": {"color": "","opacity": None}}, "muted": {"stroke": {"color": "", "width": 2, "opacity": None, "dashArray": None},
			"fill": {"color": "", "opacity": None}}}}
			
		columns.append(column)
		
		index = index + 1
		
	return columns


def greyOutWhenEmptyStyle(self, value):
	"""Return a greyed-out, non-interactive style when the value is empty, otherwise an empty style."""
	if value == '':
		return {
			"filter": "contrast(0) brightness(0.26)",
			"pointer-events": "none"
		}
	else:
		return {}


def movingAnalogIndicatorLimits(self, value):
	"""Derive the indicator's min, max, desired and alarm limits from the tag's engineering range."""
	fullRange = value.engHigh - value.engLow
	rangeOffset = 0.1 * fullRange
	midPoint = (value.engHigh + value.engLow)/2.0
	return {
		'minValue': value.engLow
		,'maxValue': value.engHigh
		,'desiredHigh': midPoint + rangeOffset
		,'desiredLow': midPoint - rangeOffset
		,'highAlarm': value.engHigh - rangeOffset
		,'lowAlarm': value.engLow + rangeOffset
	}


def sparklineRealtimePath(self, value):
	"""Convert a historical tag path to a realtime [provider]path, leaving realtime paths unchanged."""
	def getRealtimePath(historicalPath):
		tagDelim = ":/tag:"
		
		parts = historicalPath.rsplit(tagDelim, 1)
		
		extractedPath = ""
		
		if len(parts) > 1:
			extractedPath = parts[1]
		else:
			extractedPath = historicalPath
	
		provName = "default"
		
		if tagDelim in historicalPath:
			segBeforeTagDelim = historicalPath.split(tagDelim, 1)[0]
			lastColonIndex = segBeforeTagDelim.rfind(":")
			
			if lastColonIndex != -1:
				provName = segBeforeTagDelim[lastColonIndex + 1:]
			else:
				provName = segBeforeTagDelim.rsplit(":", 1)[-1]
				
				if provName.startswith("histprov"):
					provName = provName.split(":", 1)[-1]
				if not provName:
					provName = "default"
					
		return "[{}]{}".format(provName, extractedPath)
	
	return getRealtimePath(value) if ":/tag:" in value else value


def sparklinePoints(self, value):
	"""Turn the history rows into a sorted list of floats for the first tag's column, skipping blanks."""
	# Without this step props.points receives the {history, tag} map itself and every tile
	# keeps the design-time placeholder.
	history = value['history']
	tags = value['tag']
	if not history or not tags:
		return []
	key = tags[0]['alias']
	rows = list(history)
	try:
		rows.sort(key = lambda r: r['t_stamp'])
	except:
		pass
	points = []
	for row in rows:
		try:
			v = row[key]
		except:
			continue
		# A cell can arrive as the bare number or as the qualified value that carries it.
		if hasattr(v, 'value'):
			v = v.value
		elif isinstance(v, dict):
			v = v.get('value')
		if v is None:
			continue
		try:
			points.append(float(v))
		except:
			continue
	return points


def sparklineTags(self, value):
	"""Build the single-tag list (path, alias, aggregate) for the sparkline, or an empty list if no path."""
	def getTagName(tagPath):
		tagName = system.tag.read('{tagPath}.Documentation'.format(tagPath = tagPath)).value
		
		if not tagName:
			splitByProv = tagPath.split(']')
			pathNoProv = splitByProv[len(splitByProv) - 1]
	
			splitByForwardSlash = pathNoProv.split('/')
			tagName = splitByForwardSlash[len(splitByForwardSlash) - 1]
			
		engUnit = system.tag.read('{tagPath}.engUnit'.format(tagPath = tagPath)).value
		
		if engUnit:
			return '{tagName} ({engUnit})'.format(tagName = tagName, engUnit = engUnit)
		else:
			return tagName
			
	def getRealtimePath(historicalPath):
		tag = ":/tag:"
	
		parts = historicalPath.rsplit(tag, 1)
	
		if len(parts) > 1:
			result = parts[1]
		else:
			result = historicalPath
		
		return result	
	
	tagPath = value["path"]
	
	if tagPath:
		realtimePath = getRealtimePath(tagPath)
		
		return [{"path": tagPath, "alias": getTagName(realtimePath), "aggregate": value["aggMode"]}]
	else:
		return []


def sparklineRange(self, value):
	"""Return the low and high of the points, widening a flat series to 50% and 150% of its value."""
	if not value:
		return {'low': '', 'high': ''}
	minVal = min(value)
	maxVal = max(value)
	if minVal != maxVal:
		return {'low': minVal, 'high': maxVal}
	# A flat series has no range; pad it so the line lands mid-tile.
	return {'low': minVal * 0.50, 'high': maxVal * 1.50}


def iconPickerIconList(self, value):
	"""Return the fixed list of icon names available in the picker."""
	icons = [
		"3d_rotation",
		"toggle_on",
		"toggle_off",
		"star_outline",
		"star_half",
		"star_border",
		"star",
		"radio_button_unchecked",
		"radio_button_checked",
		"indeterminate_check_box",
		"check_box_outline_blank",
		"check_box",
		"whatshot",
		"thumb_up_alt",
		"thumb_down_alt",
		"sports_volleyball",
		"sports_tennis",
		"sports_soccer",
		"sports_rugby",
		"sports_motorsports",
		"sports_mma",
		"sports_kabaddi",
		"sports_hockey",
		"sports_handball",
		"sports_golf",
		"sports_football",
		"sports_esports",
		"sports_cricket",
		"sports_basketball",
		"sports_baseball",
		"sports",
		"single_bed",
		"sick",
		"share",
		"sentiment_very_satisfied",
		"sentiment_very_dissatisfied",
		"sentiment_satisfied",
		"sentiment_dissatisfied",
		"self_improvement",
		"science",
		"school",
		"sanitizer",
		"reduce_capacity",
		"public_off",
		"public",
		"psychology",
		"poll",
		"plus_one",
		"person_remove_alt_1",
		"person_remove",
		"person_outline",
		"person_add_alt_1",
		"person_add",
		"person",
		"people_outline",
		"people_alt",
		"people",
		"party_mode",
		"pages",
		"outdoor_grill",
		"notifications_paused",
		"notifications_off",
		"notifications_none",
		"notifications_active",
		"notifications",
		"no_luggage",
		"nights_stay",
		"mood_bad",
		"mood",
		"military_tech",
		"masks",
		"luggage",
		"location_city",
		"king_bed",
		"history_edu",
		"groups",
		"group_add",
		"group",
		"follow_the_signs",
		"fireplace",
		"facebook",
		"engineering",
		"emoji_transportation",
		"emoji_symbols",
		"emoji_people",
		"emoji_objects",
		"emoji_nature",
		"emoji_food_beverage",
		"emoji_flags",
		"emoji_events",
		"emoji_emotions",
		"elderly",
		"domain",
		"deck",
		"coronavirus",
		"construction",
		"connect_without_contact",
		"clean_hands",
		"cake",
		"architecture",
		"6_ft_apart",
		"wheelchair_pickup",
		"water_damage",
		"wash",
		"umbrella",
		"tty",
		"tapas",
		"stroller",
		"storefront",
		"stairs",
		"sports_bar",
		"spa",
		"soap",
		"smoking_rooms",
		"smoke_free",
		"rv_hookup",
		"room_service",
		"room_preferences",
		"roofing",
		"rice_bowl",
		"pool",
		"no_stroller",
		"no_photography",
		"no_meeting_room",
		"no_food",
		"no_flash",
		"no_drinks",
		"no_cell",
		"no_backpack",
		"night_shelter",
		"microwave",
		"meeting_room",
		"kitchen",
		"house_siding",
		"house",
		"hot_tub",
		"grass",
		"golf_course",
		"free_breakfast",
		"foundation",
		"food_bank",
		"fitness_center",
		"fire_extinguisher",
		"fence",
		"family_restroom",
		"escalator_warning",
		"escalator",
		"elevator",
		"dry",
		"do_not_touch",
		"do_not_step",
		"countertops",
		"corporate_fare",
		"child_friendly",
		"child_care",
		"checkroom",
		"charging_station",
		"casino",
		"carpenter",
		"business_center",
		"bento",
		"beach_access",
		"bathtub",
		"backpack",
		"baby_changing_station",
		"apartment",
		"all_inclusive",
		"airport_shuttle",
		"ac_unit",
		"wifi_off",
		"wifi",
		"wc",
		"vpn_lock",
		"voice_chat",
		"vibration",
		"tv_off",
		"time_to_leave",
		"tap_and_play",
		"system_update",
		"sync_problem",
		"sync_disabled",
		"sync",
		"support_agent",
		"sms_failed",
		"sms",
		"sd_card",
		"priority_high",
		"power_off",
		"power",
		"phone_paused",
		"phone_missed",
		"phone_locked",
		"phone_in_talk",
		"phone_forwarded",
		"phone_callback",
		"phone_bluetooth_speaker",
		"personal_video",
		"ondemand_video",
		"no_encryption",
		"network_locked",
		"network_check",
		"more",
		"mms",
		"live_tv",
		"folder_special",
		"event_note",
		"event_busy",
		"event_available",
		"enhanced_encryption",
		"drive_eta",
		"disc_full",
		"directions_off",
		"confirmation_number",
		"bluetooth_audio",
		"airline_seat_recline_normal",
		"airline_seat_recline_extra",
		"airline_seat_legroom_reduced",
		"airline_seat_legroom_normal",
		"airline_seat_legroom_extra",
		"airline_seat_individual_suite",
		"airline_seat_flat_angled",
		"airline_seat_flat",
		"adb",
		"account_tree",
		"west",
		"unfold_more",
		"unfold_less",
		"switch_right",
		"switch_left",
		"subdirectory_arrow_right",
		"subdirectory_arrow_left",
		"south_west",
		"south_east",
		"south",
		"refresh",
		"payments",
		"north_west",
		"north_east",
		"north",
		"more_vert",
		"more_horiz",
		"menu_open",
		"menu",
		"legend_toggle",
		"last_page",
		"home_work",
		"fullscreen_exit",
		"fullscreen",
		"first_page",
		"expand_more",
		"expand_less",
		"east",
		"double_arrow",
		"close",
		"chevron_right",
		"chevron_left",
		"check",
		"cancel",
		"campaign",
		"arrow_upward",
		"arrow_right",
		"arrow_left",
		"arrow_forward_ios",
		"arrow_forward",
		"arrow_drop_up",
		"arrow_drop_down_circle",
		"arrow_drop_down",
		"arrow_downward",
		"arrow_back_ios",
		"arrow_back",
		"apps",
		"app_settings_alt",
		"zoom_out_map",
		"wrong_location",
		"wine_bar",
		"two_wheeler",
		"trip_origin",
		"transit_enterexit",
		"transfer_within_a_station",
		"tram",
		"train",
		"traffic",
		"terrain",
		"subway",
		"streetview",
		"store_mall_directory",
		"set_meal",
		"satellite",
		"run_circle",
		"restaurant_menu",
		"restaurant",
		"rate_review",
		"plumbing",
		"place",
		"pin_drop",
		"pest_control_rodent",
		"pest_control",
		"person_pin_circle",
		"person_pin",
		"pedal_bike",
		"not_listed_location",
		"no_transfer",
		"no_meals",
		"near_me_disabled",
		"near_me",
		"navigation",
		"my_location",
		"museum",
		"multiple_stop",
		"moped",
		"money",
		"miscellaneous_services",
		"menu_book",
		"medical_services",
		"maps_ugc",
		"map",
		"local_taxi",
		"local_shipping",
		"local_see",
		"local_printshop",
		"local_post_office",
		"local_police",
		"local_play",
		"local_pizza",
		"local_phone",
		"local_pharmacy",
		"local_parking",
		"local_offer",
		"local_movies",
		"local_mall",
		"local_library",
		"local_laundry_service",
		"local_hotel",
		"local_hospital",
		"local_grocery_store",
		"local_gas_station",
		"local_florist",
		"local_fire_department",
		"local_drink",
		"local_dining",
		"local_convenience_store",
		"local_car_wash",
		"local_cafe",
		"local_bar",
		"local_atm",
		"local_airport",
		"local_activity",
		"layers_clear",
		"layers",
		"hvac",
		"hotel",
		"home_repair_service",
		"handyman",
		"flight",
		"fastfood",
		"ev_station",
		"electrical_services",
		"electric_scooter",
		"electric_moped",
		"electric_car",
		"electric_bike",
		"edit_road",
		"edit_location",
		"edit_attributes",
		"directions_walk",
		"directions_transit",
		"directions_subway",
		"directions_run",
		"directions_railway",
		"directions_car",
		"directions_bus",
		"directions_boat",
		"directions_bike",
		"directions",
		"design_services",
		"departure_board",
		"compass_calibration",
		"cleaning_services",
		"category",
		"bike_scooter",
		"beenhere",
		"atm",
		"alt_route",
		"agriculture",
		"add_road",
		"add_location_alt",
		"add_location",
		"add_business",
		"360",
		"wb_sunny",
		"wb_iridescent",
		"wb_incandescent",
		"wb_cloudy",
		"wb_auto",
		"vignette",
		"view_compact",
		"view_comfy",
		"tune",
		"transform",
		"tonality",
		"timer_off",
		"timer_3",
		"timer_10",
		"timer",
		"timelapse",
		"texture",
		"tag_faces",
		"switch_video",
		"switch_camera",
		"style",
		"straighten",
		"slideshow",
		"shutter_speed",
		"rotate_right",
		"rotate_left",
		"rotate_90_degrees_ccw",
		"remove_red_eye",
		"receipt_long",
		"portrait",
		"picture_as_pdf",
		"photo_size_select_small",
		"photo_size_select_large",
		"photo_size_select_actual",
		"photo_library",
		"photo_filter",
		"photo_camera",
		"photo_album",
		"photo",
		"panorama_wide_angle",
		"panorama_vertical",
		"panorama_horizontal",
		"panorama_fish_eye",
		"panorama",
		"palette",
		"navigate_next",
		"navigate_before",
		"nature_people",
		"nature",
		"music_off",
		"music_note",
		"movie_filter",
		"movie_creation",
		"motion_photos_paused",
		"motion_photos_pause",
		"motion_photos_on",
		"monochrome_photos",
		"loupe",
		"looks_two",
		"looks_one",
		"looks_6",
		"looks_5",
		"looks_4",
		"looks_3",
		"looks",
		"linked_camera",
		"lens",
		"leak_remove",
		"leak_add",
		"landscape",
		"iso",
		"image_search",
		"image_not_supported",
		"image_aspect_ratio",
		"image",
		"healing",
		"hdr_weak",
		"hdr_strong",
		"hdr_on",
		"hdr_off",
		"grid_on",
		"grid_off",
		"grain",
		"gradient",
		"flip_camera_ios",
		"flip_camera_android",
		"flip",
		"flash_on",
		"flash_off",
		"flash_auto",
		"flare",
		"filter_vintage",
		"filter_tilt_shift",
		"filter_none",
		"filter_hdr",
		"filter_frames",
		"filter_drama",
		"filter_center_focus",
		"filter_b_and_w",
		"filter_9_plus",
		"filter_9",
		"filter_8",
		"filter_7",
		"filter_6",
		"filter_5",
		"filter_4",
		"filter_3",
		"filter_2",
		"filter_1",
		"filter",
		"exposure_zero",
		"exposure_plus_2",
		"exposure_plus_1",
		"exposure_neg_2",
		"exposure_neg_1",
		"exposure",
		"euro",
		"edit",
		"details",
		"dehaze",
		"crop_square",
		"crop_rotate",
		"crop_portrait",
		"crop_original",
		"crop_landscape",
		"crop_free",
		"crop_din",
		"crop_7_5",
		"crop_5_4",
		"crop_3_2",
		"crop_16_9",
		"crop",
		"control_point_duplicate",
		"control_point",
		"compare",
		"colorize",
		"color_lens",
		"collections_bookmark",
		"collections",
		"center_focus_weak",
		"center_focus_strong",
		"camera_roll",
		"camera_rear",
		"camera_front",
		"camera_alt",
		"camera",
		"burst_mode",
		"brush",
		"broken_image",
		"brightness_7",
		"brightness_6",
		"brightness_5",
		"brightness_4",
		"brightness_3",
		"brightness_2",
		"brightness_1",
		"blur_on",
		"blur_off",
		"blur_linear",
		"blur_circular",
		"bedtime",
		"audiotrack",
		"assistant_photo",
		"assistant",
		"adjust",
		"add_to_photos",
		"add_photo_alternate",
		"add_a_photo",
		"sensor_window",
		"sensor_door",
		"watch",
		"videogame_asset",
		"tv",
		"toys",
		"tablet_mac",
		"tablet_android",
		"tablet",
		"speaker_group",
		"speaker",
		"smartphone",
		"sim_card",
		"security",
		"scanner",
		"router",
		"power_input",
		"point_of_sale",
		"phonelink_off",
		"phonelink",
		"phone_iphone",
		"phone_android",
		"mouse",
		"memory",
		"laptop_windows",
		"laptop_mac",
		"laptop_chromebook",
		"laptop",
		"keyboard_voice",
		"keyboard_tab",
		"keyboard_return",
		"keyboard_hide",
		"keyboard_capslock",
		"keyboard_backspace",
		"keyboard_arrow_up",
		"keyboard_arrow_right",
		"keyboard_arrow_left",
		"keyboard_arrow_down",
		"keyboard",
		"headset_mic",
		"headset",
		"gamepad",
		"dock",
		"devices_other",
		"device_unknown",
		"device_hub",
		"developer_board",
		"desktop_windows",
		"desktop_mac",
		"computer",
		"cast_for_education",
		"cast_connected",
		"cast",
		"browser_not_supported",
		"topic",
		"text_snippet",
		"snippet_folder",
		"rule_folder",
		"request_quote",
		"folder_shared",
		"folder_open",
		"folder",
		"create_new_folder",
		"cloud_upload",
		"cloud_queue",
		"cloud_off",
		"cloud_download",
		"cloud_done",
		"cloud_circle",
		"cloud",
		"attachment",
		"attach_email",
		"wrap_text",
		"vertical_distribute",
		"vertical_align_top",
		"vertical_align_center",
		"vertical_align_bottom",
		"title",
		"text_fields",
		"table_rows",
		"table_chart",
		"superscript",
		"subscript",
		"strikethrough_s",
		"stacked_line_chart",
		"space_bar",
		"show_chart",
		"short_text",
		"score",
		"scatter_plot",
		"publish",
		"post_add",
		"pie_chart",
		"notes",
		"multiline_chart",
		"money_off",
		"monetization_on",
		"mode_comment",
		"merge_type",
		"linear_scale",
		"insert_photo",
		"insert_link",
		"insert_invitation",
		"insert_emoticon",
		"insert_drive_file",
		"insert_comment",
		"insert_chart_outlined",
		"insert_chart",
		"horizontal_rule",
		"horizontal_distribute",
		"highlight",
		"height",
		"functions",
		"format_underlined",
		"format_textdirection_r_to_l",
		"format_textdirection_l_to_r",
		"format_strikethrough",
		"format_size",
		"format_shapes",
		"format_quote",
		"format_paint",
		"format_list_numbered_rtl",
		"format_list_numbered",
		"format_list_bulleted",
		"format_line_spacing",
		"format_italic",
		"format_indent_increase",
		"format_indent_decrease",
		"format_color_reset",
		"format_clear",
		"format_bold",
		"format_align_right",
		"format_align_left",
		"format_align_justify",
		"format_align_center",
		"drag_handle",
		"bubble_chart",
		"border_vertical",
		"border_top",
		"border_style",
		"border_right",
		"border_outer",
		"border_left",
		"border_inner",
		"border_horizontal",
		"border_clear",
		"border_bottom",
		"border_all",
		"bar_chart",
		"attach_money",
		"attach_file",
		"align_vertical_top",
		"align_vertical_center",
		"align_vertical_bottom",
		"align_horizontal_right",
		"align_horizontal_left",
		"align_horizontal_center",
		"add_comment",
		"wifi_tethering",
		"wifi_lock",
		"widgets",
		"wallpaper",
		"usb",
		"storage",
		"signal_wifi_off",
		"signal_wifi_4_bar_lock",
		"signal_wifi_4_bar",
		"signal_cellular_off",
		"signal_cellular_null",
		"signal_cellular_no_sim",
		"signal_cellular_connected_no_internet_4_bar",
		"signal_cellular_alt",
		"signal_cellular_4_bar",
		"settings_system_daydream",
		"sd_storage",
		"screen_rotation",
		"screen_lock_rotation",
		"screen_lock_portrait",
		"screen_lock_landscape",
		"nfc",
		"mobile_off",
		"mobile_friendly",
		"location_searching",
		"location_disabled",
		"graphic_eq",
		"gps_off",
		"gps_not_fixed",
		"gps_fixed",
		"dvr",
		"devices",
		"developer_mode",
		"data_usage",
		"brightness_medium",
		"brightness_low",
		"brightness_high",
		"brightness_auto",
		"bluetooth_searching",
		"bluetooth_disabled",
		"bluetooth_connected",
		"bluetooth",
		"battery_unknown",
		"battery_std",
		"battery_full",
		"battery_charging_full",
		"battery_alert",
		"airplanemode_inactive",
		"airplanemode_active",
		"add_to_home_screen",
		"add_alarm",
		"ad_units",
		"access_time",
		"access_alarms",
		"access_alarm",
		"where_to_vote",
		"weekend",
		"waves",
		"undo",
		"unarchive",
		"text_format",
		"square_foot",
		"sort",
		"send",
		"select_all",
		"save_alt",
		"save",
		"report_off",
		"report",
		"reply_all",
		"reply",
		"remove_circle_outline",
		"remove_circle",
		"remove",
		"redo",
		"push_pin",
		"policy",
		"outlined_flag",
		"next_week",
		"move_to_inbox",
		"markunread",
		"mail",
		"low_priority",
		"link_off",
		"link",
		"insights",
		"inbox",
		"how_to_vote",
		"how_to_reg",
		"gesture",
		"forward",
		"font_download",
		"flag",
		"filter_list",
		"file_copy",
		"dynamic_feed",
		"drafts",
		"delete_sweep",
		"create",
		"content_paste",
		"content_cut",
		"content_copy",
		"clear",
		"calculate",
		"block",
		"biotech",
		"ballot",
		"backspace",
		"archive",
		"amp_stories",
		"add_circle_outline",
		"add_circle",
		"add_box",
		"add",
		"wifi_calling",
		"vpn_key",
		"voicemail",
		"unsubscribe",
		"textsms",
		"swap_calls",
		"stop_screen_share",
		"stay_primary_portrait",
		"stay_primary_landscape",
		"stay_current_portrait",
		"stay_current_landscape",
		"speaker_phone",
		"sentiment_satisfied_alt",
		"screen_share",
		"rss_feed",
		"ring_volume",
		"read_more",
		"qr_code_scanner",
		"qr_code_2",
		"qr_code",
		"print_disabled",
		"present_to_all",
		"portable_wifi_off",
		"phonelink_setup",
		"phonelink_ring",
		"phonelink_lock",
		"phonelink_erase",
		"phone_enabled",
		"phone_disabled",
		"phone",
		"person_search",
		"person_add_disabled",
		"pause_presentation",
		"no_sim",
		"nat",
		"more_time",
		"mobile_screen_share",
		"message",
		"mark_email_unread",
		"mark_email_read",
		"mark_chat_unread",
		"mark_chat_read",
		"mail_outline",
		"location_on",
		"location_off",
		"live_help",
		"list_alt",
		"invert_colors_off",
		"import_export",
		"import_contacts",
		"hourglass_top",
		"hourglass_bottom",
		"forward_to_inbox",
		"forum",
		"email",
		"duo",
		"domain_verification",
		"domain_disabled",
		"dialpad",
		"dialer_sip",
		"desktop_access_disabled",
		"contacts",
		"contact_phone",
		"contact_mail",
		"comment",
		"clear_all",
		"chat_bubble_outline",
		"chat_bubble",
		"chat",
		"cancel_presentation",
		"call_split",
		"call_received",
		"call_missed_outgoing",
		"call_missed",
		"call_merge",
		"call_made",
		"call_end",
		"call",
		"business",
		"alternate_email",
		"add_ic_call",
		"web_asset",
		"web",
		"volume_up",
		"volume_off",
		"volume_mute",
		"volume_down",
		"videocam_off",
		"videocam",
		"video_settings",
		"video_library",
		"video_label",
		"video_call",
		"surround_sound",
		"subtitles",
		"subscriptions",
		"stop_circle",
		"stop",
		"speed",
		"sort_by_alpha",
		"snooze",
		"slow_motion_video",
		"skip_previous",
		"skip_next",
		"shuffle",
		"replay_5",
		"replay_30",
		"replay_10",
		"replay",
		"repeat_one",
		"repeat",
		"remove_from_queue",
		"recent_actors",
		"radio",
		"queue_play_next",
		"queue_music",
		"queue",
		"playlist_play",
		"playlist_add_check",
		"playlist_add",
		"play_circle_outline",
		"play_circle_filled",
		"play_arrow",
		"pause_circle_outline",
		"pause_circle_filled",
		"pause",
		"note",
		"not_interested",
		"new_releases",
		"music_video",
		"movie",
		"missed_video_call",
		"mic_off",
		"mic_none",
		"mic",
		"loop",
		"library_music",
		"library_books",
		"library_add_check",
		"library_add",
		"high_quality",
		"hearing_disabled",
		"hearing",
		"hd",
		"games",
		"forward_5",
		"forward_30",
		"forward_10",
		"fiber_smart_record",
		"fiber_pin",
		"fiber_new",
		"fiber_manual_record",
		"fiber_dvr",
		"featured_video",
		"featured_play_list",
		"fast_rewind",
		"fast_forward",
		"explicit",
		"equalizer",
		"control_camera",
		"closed_caption_disabled",
		"closed_caption",
		"call_to_action",
		"branding_watermark",
		"av_timer",
		"art_track",
		"album",
		"airplay",
		"add_to_queue",
		"5g",
		"4k",
		"warning",
		"notification_important",
		"error_outline",
		"error",
		"auto_delete",
		"add_alert",
		"zoom_out",
		"zoom_in",
		"youtube_searched_for",
		"wysiwyg",
		"work_outline",
		"work_off",
		"work",
		"wifi_protected_setup",
		"watch_later",
		"voice_over_off",
		"visibility_off",
		"visibility",
		"view_week",
		"view_stream",
		"view_sidebar",
		"view_quilt",
		"view_module",
		"view_list",
		"view_headline",
		"view_day",
		"view_column",
		"view_carousel",
		"view_array",
		"view_agenda",
		"vertical_split",
		"verified_user",
		"verified",
		"upgrade",
		"update_disabled",
		"update",
		"unpublished",
		"turned_in_not",
		"turned_in",
		"trending_up",
		"trending_flat",
		"trending_down",
		"translate",
		"track_changes",
		"tour",
		"touch_app",
		"toll",
		"today",
		"toc",
		"timeline",
		"thumbs_up_down",
		"thumb_up",
		"thumb_down",
		"theaters",
		"text_rotation_none",
		"text_rotation_down",
		"text_rotation_angleup",
		"text_rotation_angledown",
		"text_rotate_vertical",
		"text_rotate_up",
		"table_view",
		"tab_unselected",
		"tab",
		"system_update_alt",
		"sync_alt",
		"swap_vertical_circle",
		"swap_vert",
		"swap_horizontal_circle",
		"swap_horiz",
		"support",
		"supervisor_account",
		"supervised_user_circle",
		"subtitles_off",
		"subject",
		"store",
		"sticky_note_2",
		"stars",
		"star_rate",
		"spellcheck",
		"speaker_notes_off",
		"speaker_notes",
		"source",
		"smart_button",
		"shopping_cart",
		"shopping_basket",
		"shopping_bag",
		"shop_two",
		"shop",
		"settings_voice",
		"settings_remote",
		"settings_power",
		"settings_phone",
		"settings_overscan",
		"settings_input_svideo",
		"settings_input_hdmi",
		"settings_input_composite",
		"settings_input_component",
		"settings_input_antenna",
		"settings_ethernet",
		"settings_cell",
		"settings_brightness",
		"settings_bluetooth",
		"settings_backup_restore",
		"settings_applications",
		"settings",
		"search_off",
		"search",
		"schedule",
		"rule",
		"rowing",
		"rounded_corner",
		"room",
		"restore_page",
		"restore_from_trash",
		"restore",
		"request_page",
		"report_problem",
		"reorder",
		"remove_shopping_cart",
		"redeem",
		"record_voice_over",
		"receipt",
		"quickreply",
		"question_answer",
		"query_builder",
		"published_with_changes",
		"privacy_tip",
		"print",
		"preview",
		"pregnant_woman",
		"power_settings_new",
		"polymer",
		"play_for_work",
		"plagiarism",
		"picture_in_picture_alt",
		"picture_in_picture",
		"pets",
		"perm_scan_wifi",
		"perm_phone_msg",
		"perm_media",
		"perm_identity",
		"perm_device_information",
		"perm_data_setting",
		"perm_contact_calendar",
		"perm_camera_mic",
		"pending_actions",
		"pending",
		"payment",
		"pan_tool",
		"pageview",
		"outlet",
		"outbond",
		"open_with",
		"open_in_new",
		"open_in_full",
		"open_in_browser",
		"opacity",
		"online_prediction",
		"offline_pin",
		"offline_bolt",
		"note_add",
		"not_started",
		"not_accessible",
		"next_plan",
		"model_training",
		"minimize",
		"mediation",
		"maximize",
		"markunread_mailbox",
		"loyalty",
		"login",
		"lock_open",
		"lock",
		"list",
		"line_weight",
		"line_style",
		"leaderboard",
		"launch",
		"language",
		"label_off",
		"label_important",
		"label",
		"invert_colors",
		"integration_instructions",
		"input",
		"info",
		"important_devices",
		"https",
		"http",
		"hourglass_full",
		"hourglass_empty",
		"hourglass_disabled",
		"horizontal_split",
		"home",
		"history_toggle_off",
		"history",
		"highlight_off",
		"highlight_alt",
		"help_outline",
		"help_center",
		"help",
		"group_work",
		"grading",
		"grade",
		"gif",
		"get_app",
		"gavel",
		"g_translate",
		"flip_to_front",
		"flip_to_back",
		"flight_takeoff",
		"flight_land",
		"flaky",
		"fingerprint",
		"find_replace",
		"find_in_page",
		"filter_alt",
		"feedback",
		"favorite_border",
		"favorite",
		"fact_check",
		"face",
		"extension",
		"explore_off",
		"explore",
		"exit_to_app",
		"event_seat",
		"event",
		"euro_symbol",
		"eject",
		"eco",
		"dynamic_form",
		"drag_indicator",
		"donut_small",
		"donut_large",
		"done_outline",
		"done_all",
		"done",
		"dns",
		"disabled_by_default",
		"description",
		"delete_outline",
		"delete_forever",
		"delete",
		"date_range",
		"dashboard",
		"credit_card",
		"copyright",
		"contactless",
		"contact_support",
		"contact_page",
		"compare_arrows",
		"commute",
		"comment_bank",
		"code",
		"close_fullscreen",
		"class",
		"chrome_reader_mode",
		"check_circle_outline",
		"check_circle",
		"change_history",
		"card_travel",
		"card_membership",
		"card_giftcard",
		"cancel_schedule_send",
		"camera_enhance",
		"calendar_view_day",
		"calendar_today",
		"cached",
		"build_circle",
		"build",
		"bug_report",
		"bookmarks",
		"bookmark_border",
		"bookmark",
		"book_online",
		"book",
		"batch_prediction",
		"backup_table",
		"backup",
		"autorenew",
		"assignment_turned_in",
		"assignment_returned",
		"assignment_return",
		"assignment_late",
		"assignment_ind",
		"assignment",
		"assessment",
		"aspect_ratio",
		"article",
		"arrow_right_alt",
		"arrow_circle_up",
		"arrow_circle_down",
		"app_blocking",
		"api",
		"announcement",
		"android",
		"anchor",
		"analytics",
		"all_out",
		"all_inbox",
		"alarm_on",
		"alarm_off",
		"alarm_add",
		"alarm",
		"admin_panel_settings",
		"addchart",
		"add_task",
		"add_shopping_cart",
		"account_circle",
		"account_box",
		"account_balance_wallet",
		"account_balance",
		"accessible_forward",
		"accessible",
		"accessibility_new",
		"accessibility"
		]
		
	return [{'icon': icon} for icon in icons]


def iconPickerSearchIcons(self, value):
	"""Filter the icon list to those whose name contains the search text."""
	icons = self.custom.icons
	search = value["search"]
	ret = []
	for i in range(len(icons)):
		icon = icons[i]
		if search == None or search == "" or search in icon["icon"]:
			ret.append(icon)
	return ret


def iconPickerPageInstances(self, value):
	"""Return the slice of icons for the current page of the icon grid."""
	icons = value["icons"]
	page = value["page"]
	total = value["total"]
	pageSize = value["pageSize"]
	startIdx = page * pageSize
	endIdx = startIdx + pageSize
	endIdx = total if endIdx > total else endIdx
	return icons[startIdx:endIdx]


def iconPickerPreviousPageOnKey(self, event):
	"""On Enter or Space, step the icon picker back one page, stopping at the first."""
	if event.key in ('Enter', ' '):
		page = self.view.getChild("root").custom.page
		
		if (page - 1) >= 0:
			page -= 1
		
		self.view.getChild("root").custom.page = page


def iconPickerNextPageOnKey(self, event):
	"""On Enter or Space, step the icon picker forward one page, stopping at the last."""
	if event.key in ('Enter', ' '):
		page = self.view.getChild("root").custom.page
		pages = self.view.getChild("root").custom.pages
		
		if (page + 1) <= (pages - 1):
			page += 1
		
		self.view.getChild("root").custom.page = page


def tagTreeItemClicked(self, event):
	"""Expand or collapse a tag tree node, browsing the tag or history provider for its children on first open."""
	currentLevel = {}
	
	self.props.interactable = False
	
	for item in event.itemPath:
		if currentLevel == {}:
			currentLevel = self.props.items[item]
		else:
			currentLevel = currentLevel["items"][item]
		
	if currentLevel["expanded"] and currentLevel["data"]["hasChildren"]:
		currentLevel["items"] = [{"label":"Fake Item","expanded":False,"data":{},"items":[]}]
	else:
		itemPath = "/".join(map(str,event.itemPath))
		tags = []
		
		if currentLevel["data"].has_key("folder"):
			baseTagFolder = currentLevel["data"]["folder"]
			if self.view.params.mode == 'history':
				results = system.tag.browseHistoricalTags(baseTagFolder).getResults()

				if results != None:
					for result in results:
						if result.hasChildren() == True:
							tag = {'label': result.path.lastPathComponent, 'expanded': False, 'data': {'folder': result.path, 'hasChildren':result.hasChildren}, "items":[{"label":"Fake Item","expanded":False,"data":{'hasChildren':False},"items":[]}]}
							tags.append(tag)
						else:
							tags.append({'label': result.path.lastPathComponent, 'data': {'tag': result.path, 'hasChildren':result.hasChildren}, 'expanded': False, "items":[]})
						
					currentLevel["items"] =  tags
			else:
				if currentLevel["data"].has_key("folder"):
					results = system.tag.browse(baseTagFolder).getResults()
					
					for result in results:
						if result["name"] != "_types_":
							if str(result["tagType"]) in ["Folder", "UdtInstance"]:
								tag = {'label': result["name"], 'expanded': False, 'data': {'folder':result["fullPath"], 'hasChildren':result["hasChildren"]}, "items":[]}
								
								if result["hasChildren"]:
									tag['items'].append({"label":"Fake Item","expanded":False,"data":{},"items":[]})
								
								tags.append(tag)
							else:
								tags.append({'label': result["name"], 'data': {'tag': result["fullPath"], 'hasChildren':result["hasChildren"]}, 'items': [], 'expanded': False})
				
					currentLevel["items"] =  tags
			
		self.props.selection = []
		self.props.selection.append(itemPath)
		self.props.selectionData = []
		self.props.selectionData.append({"itemPath":itemPath,"value":currentLevel["data"]})

	currentLevel["expanded"] = not currentLevel["expanded"]


def tagTreeSelect(self, event):
	"""Send the selected tag or folder path in a tagSelection message and close the tag tree popup."""
	id = self.view.params.id
	path = self.getSibling("Tags").props.selectionData[0].value.get('tag')
	
	if path == None:
		path = self.getSibling("Tags").props.selectionData[0].value.get('folder')
	
	system.perspective.sendMessage(messageType="tagSelection", payload={"id":id, "path":path})
	system.perspective.closePopup(id="tag-tree")


def confirmationYes(self, event):
	"""Run the confirmed function named in the view params with its params, then close the popup."""
	params = launchpad.dashboard.copyDictionary(self.view.params.function.params)
		
	if len(params):
		script = "%s(self, params)" % self.view.params.function.script
	else:
		script = "%s(self)" % self.view.params.function.script
	
	try:
		exec(script)
	except:
		pass
		
	system.perspective.closePopup(id="confirmation")


def dashboardWidgetGridRowCount(self, value):
	"""Return the grid row count, or the total rows the widgets span on mobile."""
	# On mobile the widgets form a single column, so the dashboard needs the total rows they span.
	
	mobile = value["mobile"]
	gridRows = value["gridRows"]
	widgets = value["widgets"]
	
	if mobile:
		return launchpad.dashboard.getWidgetsRows(widgets, gridRows)
	else:
		return gridRows


def dashboardHeaderSelectDashboard(self, event):
	"""Navigate to the URL of the dashboard chosen in the dropdown."""
	options = self.props.options
	selectedValue = self.props.value
	
	for option in options:
		if option.get('value') == selectedValue:
			dashboardUrl = option.get('url')
			break
			
	system.perspective.navigate(dashboardUrl)


def popupDualTagHeaderText(self, value):
	"""Build the popup title from each tag's documentation (or name) joined with 'and', plus 'Historical Data'."""
	title = ""
	for i in range(len(value.documentation)):
		if i > 0:
			title += " and "
		if len(value.documentation[i]) > 0:
			title += value.documentation[i]
	
		else:
			title +=  value.tagName[i]
	
	return title + " Historical Data"


def dashboardViewName(self, value):
	"""Take the last segment of the dashboard path, store it as the session's dashboard URL and return it."""
	dashboard = self.params.dashboard
	
	try:
		paths = value.split("/")
		dashboard = paths[-1]
	except:
		pass
	
	self.session.custom.launchpad.dashboard.options.url = dashboard 
	return dashboard


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


def settingsReseedHistory(self, event):
	"""Drop and rewrite the seeded tag history on a worker thread, reporting rows and tags seeded."""
	# force=1 rewrites the seeded samples; use after rescaling a tag so a series does not hold two units.
	view = self.view
	view.custom.maintResult = "re-seeding history..."
	def work():
		r = launchpad.init.backfill(force=True)
		view.custom.maintResult = ("re-seeded %s rows across %s tags"
			% (r.get("rows"), r.get("tagsSeeded"))) if not r.get("error") else r["error"]
	system.util.invokeAsynchronous(work)


def tagSetupExportPds(self, event):
	"""Download a CSV of the Launchpad OPC tags with a simulator function for each, by tag name and line."""
	tagProvider = "[Launchpad]"
	results = system.tag.browse(tagProvider, {"tagType":"AtomicTag", "valueSource":"opc", "recursive":True}).results
	data = []
	for result in results:
		pathList = str(result['fullPath']).split('/')
		tagName = pathList[-1]
		if 'Line' in pathList[-2]:
			line = int(pathList[-2].replace('Line',''))
		else:
			line = 0
		period = 3100.0-line*100
		if tagName == 'BatteryCapacity': function = 'cosine(%s, %s, %s, true)' % (18+line, 100, period)
		elif tagName == 'CoilTemperature': function = 'cosine(%s, %s, %s, true)' % (90+line, 147-line, period)
		elif tagName == 'OilPressure': function = 'random(%s, %s, true)' % (20+line, 21+line)	
		elif tagName == 'ProductionRate': function = 'random(%s, %s, true)' % (20+line, 21+line)
		elif tagName == 'Reserve2Pressure': function = 'random(%s, %s, true)' % (30+line, 31+line)
		elif tagName == 'ReserveOilPressure': function = 'random(%s, %s, true)' % (30+line, 31+line)
		elif tagName == 'ActivePower': function = 'random(%s, %s, true)' % (3300, 3500)
		
		elif tagName == 'AirPressure': function = 'random(%s, %s, true)' % (90, 95)
		elif tagName == 'AmbientHumidity': function = 'random(%s, %s, true)' % (44.6, 45.5)
		elif tagName == 'AmbientTemperature': function = 'random(%s, %s, true)' % (72.00, 72.06)
		elif tagName == 'Buffer': function = 'random(%s, %s, true)' % (80, 100)
		elif tagName == 'CycleTime': function = 'random(%s, %s, true)' % (2.1, 2.4)
		elif tagName == 'EnergyYesterday': function = 'random(%s, %s, true)' % (3.796, 3.806)
		elif tagName == 'SetupTime': function = 'random(%s, %s, true)' % (15.00, 15.06)
		elif tagName == 'WorkInProcess': function = 'random(%s, %s, true)' % (105, 120)
		
		else: function = 'random(0, 100, true)'
		
		data.append([0,str(result['fullPath']).replace(tagProvider,''),function,'Double'])
	headers = ['Time Interval', 'Browse Path', 'Value Source', 'Data Type']
	dataset = system.dataset.toDataSet(headers, data)
	
	filename = 'Launchpad-OPC-%s.csv' % system.date.now()
	data = system.dataset.toCSV(dataset)
	system.perspective.download(filename, data)


def tagSetupPointOpc(self, event):
	"""Set each OPC tag's item path in the Launchpad provider to its own ns=1 tag path."""
	tagProvider = "[Launchpad]"
	results = system.tag.browse(tagProvider, {"tagType":"AtomicTag", "valueSource":"opc", "recursive":True}).results
	
	for result in results:
		tagPath = str(result['fullPath'])
		opcPath = 'ns=1;s=[Launchpad]%s' % tagPath.replace(tagProvider,'')
		
		tag = system.tag.getConfiguration(tagPath, recursive = False)
		tag[0]['opcItemPath'] = opcPath
		basePath = tagPath[:tagPath.rfind('/')]
		system.tag.configure(basePath, tag[0])
