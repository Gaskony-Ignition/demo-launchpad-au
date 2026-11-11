def getDashboards(ds):
	"""Build a list of dashboard dicts, with their widgets, from the dashboards dataset `ds`."""
	dashboards = []
	
	for row in ds:
		id = row["id"]
		name = row["name"]
		icon = row["icon"]
		dashboardUrl = row["url"]
		username = row["username"]
		grid = row["grid"]
		cellSize = row["cell_size"]
		gridRows = row["grid_rows"]
		gridRowGutterSize = row["row_gutter_size"]
		gridCols = row["grid_cols"]
		gridColGutterSize = row["col_gutter_size"]	  
		
		d = {"id":id, "name":name, "url":dashboardUrl, "icon":icon, "allow_edit": True, "grid":grid, "cellSize":cellSize, "gridRows":gridRows, "gridRowGutterSize":gridRowGutterSize, "gridCols":gridCols, "gridColGutterSize":gridColGutterSize, "action":{"action":"edit"}}		
		sizes = []
		
		res = launchpad.store.dashboardWidgets(id)
		res = system.dataset.toPyDataSet(res)
			
		widgets = {}
		idx = 0
		
		for w in res:
			if w["id"] not in widgets:
				widgets[w["id"]] = {"id":w["id"], "widget_id":w["widget_id"], "idx":idx, "name":w["name"], "widget":w["widget"], "path":w["path"], "params":{}, "sizes":{}, "action":{"action":"", "params":[]}}
				idx += 1
				
			size = 0
			if size not in widgets[w["id"]]["sizes"]:
				widgets[w["id"]]["sizes"][size] = w["position"]
					
			if size not in sizes:
				sizes.append(size)
				
			param = w["parameter"]
			if param != None and param not in widgets[w["id"]]["params"]:
				paramValue = w["parameter_value"]					
				widgets[w["id"]]["params"][param] = paramValue
				widgets[w["id"]]["action"]["params"].append({"id":w["parameter_id"], "parameter":param, "parameter_type_id":w["parameter_type_id"], "label":w["parameter_name"], "value": paramValue, "path":w["parameter_type_path"], "configuration":launchpad.dashboard.encodeConfiguration(w["parameter_configuration"])})

		d["widgets"] = [w[1] for w in widgets.items()]	
		d["sizes"] = [0] if len(sizes) == 0 else sizes	
		dashboards.append(d)
		
	return dashboards
	
def encodeConfiguration(config):
	"""Return the decoded JSON configuration, {} if None."""
	return {} if config == None else system.util.jsonDecode(config)
	
def getConfiguration(config, key, default=""):
	"""Return config[key], or default on any failure."""
	try:
		return config.get(key, default)
	except:
		return default
	
def getWidgets(ds, mobile=False, rowCount=0, columnCount=0, configurable=False):
	"""Build the widget config list for a dashboard from `ds`; on mobile, stack them in one column."""
	rowIndex = 1
	
	widgets = []
	
	for row in ds:
		if row["action"]["action"] != "delete":
			sizeKeys = row["sizes"].keys()
			position = row["sizes"][sizeKeys[0]].split(",")
			numRows = int(position[1]) - int(position[0])
			numRowsMobile = round((float(numRows)/float(rowCount))*50.0)
			
			widget = {
			  "name": row["name"],
			  "viewPath": "Launchpad/Kpi/EmbeddedViews/Dashboard/Configuration/Widget Edit Wrapper" if configurable else row["path"],
			  "viewParams": {"id":row["id"], "configuring":False, "name":row["name"], "widgetId":row["widget_id"], "widgetName":row["widget"], "viewPath":row["path"], "viewParams":row["params"], "editParams":row["action"]["params"]} if configurable else row["params"],
			  "isConfigurable": configurable,
			  "header": {
				"enabled": False,
				"title": row["name"],
				"style": {
				  "classes": ""
				}
			  },
			  "body": {
				"style": {
				  "classes": "",
				  "padding": "5px"
				}
			  },
			  "minSize": {
				"columnSpan": 1,
				"rowSpan": 1
			  },
			  "position": {
				"rowStart": rowIndex if mobile else int(position[0]),
				"rowEnd": (rowIndex + numRowsMobile) if mobile else int(position[1]),
				"columnStart": 1 if mobile else int(position[2]),
				"columnEnd": 2 if mobile else int(position[3])
			  },
			  "style": {
				"classes": ""
			  }
			}
			
			if mobile:
				rowIndex += (numRowsMobile + 1)
			else:
				rowIndex += (numRows + 1)
				
			widgets.append(widget)
	return widgets
	
def getWidgetsRows(ds, gridRows, size=0):
	"""Return the total grid rows needed to stack the dashboard's widgets in one column on mobile."""
	
	rowIndex = 1	
	for row in ds:
		if row["action"]["action"] != "delete":
			position = row["sizes"][size].split(",")
			numRows = int(position[1]) - int(position[0])
			# Scale rows to a fixed 50 per grid so mobile heights are consistent across dashboards.
			numRows = (float(numRows)/float(gridRows))*50.0
			rowIndex += (numRows + 1)

	return round(rowIndex)
	
def getInstalledWidgets(ds, gridRows, gridColumns):
	"""Build the list of widget types available to add to a dashboard from `ds`."""
	widgets = {}
	
	defaultColSpan = round(0.23 * float(gridColumns))
	defaultRowSpan = round(0.23 * float(gridRows))
	
	for row in ds:
		if row["id"] not in widgets:
			widgets[row["id"]] = {
								  "name": row["widget"],
								  "viewPath": "Launchpad/Kpi/EmbeddedViews/Dashboard/Configuration/Widget Edit Wrapper",
								  "viewParams": {"id":None, "configuring":False, "name":row["widget"], "widgetId":row["id"], "widgetName":row["widget"], "viewPath":row["path"], "viewParams":{}, "editParams":[]},
								  "isConfigurable": True,
								  "header": {
									"enabled": True,
									"title": row["widget"],
									"style": {
									  "classes": ""
									}
								  },
								  "body": {
									"style": {
									  "classes": ""
									}
								  },
								  "defaultSize": {
									"columnSpan": defaultColSpan,
									"rowSpan": defaultRowSpan
								  },
								  "minSize": {
									"columnSpan": 1,
									"rowSpan": 1
								  },
								  "category":"Widgets",
								  "style": {
									"classes": ""
								  }
								}
		if row["parameter"] != None:
			widgets[row["id"]]["viewParams"]["viewParams"][row["parameter"]] = row["parameter_value"]
			widgets[row["id"]]["viewParams"]["editParams"].append({"id":row["parameter_id"], "parameter":row["parameter"], "parameter_type_id":row["parameter_type_id"], "label":row["parameter_name"], "value": row["parameter_value"], "path":row["parameter_type_path"], "configuration":launchpad.dashboard.encodeConfiguration(row["parameter_configuration"])})
	return [w[1] for w in widgets.items()]
	
def getCurrentDashboard(dashboards, url, sub=False):
	"""Return the dashboard whose url matches `url`, else the first one, else an empty dashboard."""
	d = None
	
	dbObj = dashboards
		
	for row in dbObj:
		if row["url"] == url:
			d = launchpad.dashboard.getDashboardObject(row)
			
		if d != None:
			break
	
	if d == None:
		if len(dbObj) == 0:
			d = launchpad.dashboard.getDashboardObject(False)
		else:
			d = launchpad.dashboard.getDashboardObject(dbObj[0])
			
	return d
	
def getDropdownOptions(dashboards, sub=False):
	"""Return dropdown options (label, value, url) for the dashboards."""
	dropdownOptions = []
	
	for row in dashboards:
		option = {'label': row["name"], 'value': row["name"], 'url': "/dashboard/%s" % row["url"]}
		dropdownOptions.append(option)
		
	return dropdownOptions

def getDashboardObject(dbObj):
	"""Return an empty dashboard for a bool (True: add, False: none), else a copy of `dbObj`."""
	if isinstance(dbObj, bool):
		if dbObj:
			return {"id":None, "name":"", "url":"", "icon":"dashboard", "allow_edit":True, "widgets":[], "grid":"stretch", "cellSize":100, "gridRows":20, "gridCols":20, "gridRowGutterSize":6, "gridColGutterSize":6, "sizes":[0], "action":{"action":"add"}}
		else:
			return {"id":None, "name":None, "url":None, "icon":None, "allow_edit":False, "widgets":[], "grid":"stretch", "cellSize":100, "gridRows":20, "gridCols":20, "gridRowGutterSize":6, "gridColGutterSize":6, "sizes":[0], "action":{"action":""}}
	elif dbObj != None:
		return launchpad.dashboard.copyDictionary(dbObj)

def copyArray(items):
	"""Return a copy of the list, deep-copying dict items."""
	ret = []
	for value in items:
		if str(type(value)) == "<type 'com.inductiveautomation.perspective.gateway.script.PropertyTreeScriptWrapper$MapWrapper'>" or type(value) == dict:
			ret.append(launchpad.dashboard.copyDictionary(value))
		else:
			ret.append(value)
	return ret
		
def copyDictionary(items):
	"""Return a deep copy of the dict, including Perspective MapWrapper values."""
	ret = {}
	for key in items:
		value = items[key]
		
		if str(type(value)) == "<type 'com.inductiveautomation.perspective.gateway.script.PropertyTreeScriptWrapper$MapWrapper'>" or type(value) == dict:
			ret[key] = launchpad.dashboard.copyDictionary(value)
		else:
			ret[key] = value
	return ret
	
def editDashboard(self, add=True):
	"""Open the new-dashboard dock (add=True) or edit the current dashboard, then navigate to the editor."""
	if add:
		self.session.custom.launchpad.dashboard.objects.edit = launchpad.dashboard.getDashboardObject(True)
		maxId = launchpad.store.maxDashboardId() + 1
		self.session.custom.launchpad.dashboard.objects.edit.name = "Dashboard %d" % (maxId)
		self.session.custom.launchpad.dashboard.objects.edit.url = "dash%d" % (maxId)
		# Keep the pre-test settings so Cancel can restore them.
		currEdit = {key: value for key, value in self.session.custom.launchpad.dashboard.objects.edit.iteritems() if key != 'widgets'}
		system.perspective.openDock('editDashDetails',params={'currEdit':currEdit})
	else:
		if self.session.custom.launchpad.dashboard.objects.current.id == None:
			return
		
		self.session.custom.launchpad.dashboard.objects.edit = launchpad.dashboard.getDashboardObject(self.session.custom.launchpad.dashboard.objects.current)
	
	system.perspective.navigate(view="Launchpad/Kpi/EmbeddedViews/Dashboard/Configuration/AddEdit Dashboard", params = {'add': add})

def addUpdateWidget(self):
	"""Sync the edit dashboard's widgets with the grid: update positions, add new ones, mark missing ones for deletion."""
	from java.util import UUID
	size = 0
	sizes = self.session.custom.launchpad.dashboard.objects.edit.sizes
	sessionWidgets = self.session.custom.launchpad.dashboard.objects.edit.widgets
	
	foundIds = []
	for row in self.props.widgets:
		positionStr = "%s,%s,%s,%s" % (row.position.rowStart, row.position.rowEnd, row.position.columnStart, row.position.columnEnd)
		
		foundId = False
		for i in range(len(sessionWidgets)):
			if sessionWidgets[i]["id"] == row.viewParams.id:
				sessionWidgets[i]["sizes"][size] = positionStr
				foundIds.append(sessionWidgets[i]["id"])
				foundId = True
				break
			
		if not foundId:
			id = UUID.randomUUID()
			sessionWidgets.append({"id":id, "widget_id":row.viewParams.widgetId, "name":row.viewParams.name, "widget":row.viewParams.widgetName, "path":row.viewParams.viewPath, "params":launchpad.dashboard.copyDictionary(row.viewParams.viewParams), "sizes":{newSize:positionStr for newSize in sizes}, "action":{"action":"add", "params":launchpad.dashboard.copyArray(row.viewParams.editParams)}})
			foundIds.append(id)

	for i in range(len(sessionWidgets)):
		id = sessionWidgets[i]["id"]
		if id not in foundIds:
			sessionWidgets[i]["action"]["action"] = "delete"
		
def editWidget(self):
	"""Write the Widget Edit view's name and parameter values back to the widget in the edit dashboard."""
	id = self.view.params.id
	name = self.view.params.name
	editParams = self.view.params.editParams
	
	widgets = self.session.custom.launchpad.dashboard.objects.edit.widgets
	widget = None
	for i in range(len(widgets)):
		if widgets[i]["id"] == id:
			widget = widgets[i]
			break
	
	params = widget["params"]
	actionParams = widget["action"]["params"]
	
	for i in range(len(editParams)):
		paramValue = editParams[i]["value"]
		actionParams[i]["value"] = paramValue
		params[editParams[i]["parameter"]] = paramValue
		
	widget["name"] = name
	system.perspective.closePopup(id="widget-parameters")
	
def syncDashboardDB(self):
	"""Validate and save the edit dashboard and its widgets through the store, then refresh and navigate."""
	
	d = self.session.custom.launchpad.dashboard.objects.edit
	
	username = self.session.custom.launchpad.dashboard.options.username
	
	if d.name == None or d.name == "":
		launchpad.dashboard.showError("Please enter in a name")
		return
	
	if d.url == None or d.url == "":
		launchpad.dashboard.showError("Please enter in a URL")
		return
	
	if d.cellSize == None or d.gridRows == None or d.gridCols == None or d.gridRowGutterSize == None or d.gridColGutterSize == None:
		launchpad.dashboard.showError("Please enter in grid data (cell size, rows, cols, gutter size)")
		return
	
	urlId = launchpad.store.dashboardIdForUrl(d.url)
	if urlId != None and (d.id == None or d.id != urlId):
		launchpad.dashboard.showError("URL '%s' already exists. Please try another." % d.url)
		return
	
	if d.action.action == "add":
		id = launchpad.store.addDashboard({"grid":d.grid, "cell_size":d.cellSize, "grid_rows":d.gridRows, "grid_cols":d.gridCols, "grid_row_gutter_size":d.gridRowGutterSize, "grid_col_gutter_size":d.gridColGutterSize, "icon":d.icon, "name":d.name, "url":d.url, "username":username})
	else:
		id = d.id
		launchpad.store.editDashboard({"id":id, "grid":d.grid, "cell_size":d.cellSize, "grid_rows":d.gridRows, "grid_cols":d.gridCols, "grid_row_gutter_size":d.gridRowGutterSize, "grid_col_gutter_size":d.gridColGutterSize, "icon":d.icon, "name":d.name, "url":d.url, "username":username})
	
	for widget in d.widgets:
		widgetId = None
		
		if widget.action.action == "delete":
			try:
				launchpad.store.deleteWidget(widget.id)
			except:
				pass
		elif widget.action.action == "add":
			widgetId = launchpad.store.addWidget({"dashboard_id":id, "widget_id":widget.widget_id, "name":widget.name, "position":widget.sizes[0]})
		else:
			widgetId = widget.id
			launchpad.store.editWidget({"id":widgetId, "dashboard_id":id, "widget_id":widget.widget_id, "name":widget.name, "position":widget.sizes[0]})
			
		if widgetId != None:
			for param in widget.action.params:
				launchpad.store.setWidgetParameter(widgetId, param.id, param.value, widget.action.action == "add")
	
	launchpad.dashboard.refresh(self)
	
	if d.action.action == "add":
		system.perspective.navigate(page="/dashboard/%s" % d.url)
	else:
		launchpad.dashboard.back(self)

def deleteDashboard(self):
	"""Delete the dashboard being edited, refresh and navigate to /dashboard."""
	
	id = self.session.custom.launchpad.dashboard.objects.edit.id
	launchpad.store.deleteDashboard(id)
	launchpad.dashboard.refresh(self)
	system.perspective.navigate(page="/dashboard")
	
def back(self):
	"""Navigate to the current page's path."""
	system.perspective.navigate(page=self.page.props.path)
	
def refresh(self, fromSession=False):
	"""Refresh the dbValid and dashboards session bindings; `self` is the session when fromSession."""
	if fromSession:
		obj = self
	else:
		obj = self.session
		
	obj.refreshBinding("custom.launchpad.dashboard.dbValid")
	obj.refreshBinding("custom.launchpad.dashboard.dashboards")
	
def showError(message):
	"""Show an error message in a popup."""
	launchpad.dashboard.popupMessage("error", message, "Error_Text")
	
def showMessage(message):
	"""Show an info message in a popup."""
	launchpad.dashboard.popupMessage("info", message, "Text")
	
def popupMessage(icon, message, displayClass):
	"""Open the message popup with an icon, message and style class."""
	params = {"icon":icon, "display":message, "class":displayClass}
	system.perspective.openPopup(id="message", view="Launchpad/Kpi/EmbeddedViews/Dashboard/Configuration/Popup/Message", params=params, showCloseIcon=True, draggable=False, resizable=True, modal=True, overlayDismiss=False)
	
def showConfirmation(message, function, params={}):
	"""Open a confirmation popup; `function` is called with `params` if the user presses Yes."""
	params = {"icon":"help", "display":message, "class":"Text", "function":{"script":function, "params":params}}
	system.perspective.openPopup(id="confirmation", view="Launchpad/Kpi/EmbeddedViews/Dashboard/Configuration/Popup/Confirmation", params=params, showCloseIcon=True, draggable=False, resizable=True, modal=True, overlayDismiss=False)
