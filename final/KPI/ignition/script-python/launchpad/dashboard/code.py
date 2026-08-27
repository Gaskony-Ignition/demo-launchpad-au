def getDashboards(ds):
	"""
	Utilizes the info from the 'ds' dataset arg to create a list
		of dashboard objects. The 'ds' arg contains info regarding
		the dashboards.
			
	Args:
		ds: Dataset that holds info regarding the dashboards.
			
	Returns:
		A list of dictionary objects that represent dashboards.
	"""
	# Create dashboards list.
	dashboards = []
	
	# Iterate through dataset, reading dashboard info and
	# storing the info in variables.
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
		
		# Create the object representing the dashboard.
		d = {"id":id, "name":name, "url":dashboardUrl, "icon":icon, "allow_edit": True, "grid":grid, "cellSize":cellSize, "gridRows":gridRows, "gridRowGutterSize":gridRowGutterSize, "gridCols":gridCols, "gridColGutterSize":gridColGutterSize, "action":{"action":"edit"}}		
		sizes = []
		
		# Get the widgets for this dashboard.
		res = system.db.runNamedQuery(path="Launchpad/Dashboard/Widget/Get", parameters={"dashboard":id})
		res = system.dataset.toPyDataSet(res)
			
		widgets = {}
		idx = 0
		
		# Iterate through the widgets dataset, decode the
		# widget params, create the widget object, and add
		# it to the widgets dictionary.
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

		# Add the widgets to the dashboard object.		
		d["widgets"] = [w[1] for w in widgets.items()]	
		d["sizes"] = [0] if len(sizes) == 0 else sizes	
		dashboards.append(d)
		
	return dashboards
	
def encodeConfiguration(config):
	return {} if config == None else system.util.jsonDecode(config)
	
def getConfiguration(config, key, default=""):
	try:
		return config.get(key, default)
	except:
		return default
	
def getWidgets(ds, mobile=False, rowCount=0, columnCount=0, configurable=False):
	"""
	Utilizes the info in the 'ds' dataset arg to create a list
		of dictionary objects that represent the widgets of a
		dashboard.
		
	Args:
		ds: Dataset containing info about a dashboard's widgets. 
		mobile: Bool denoting whether user is on mobile device.
		rowCount: Number of rows in the grid of the dashboard.
		columnCount: Number of cols in the grid of the dashboard.
		configurable: Bool denoting if widgets can be edited.
		
	Returns:
		A list of dictionary objects that represents the widgets
		of a dashboard.
	"""
	rowIndex = 1
	
	# Create widgets list.
	widgets = []
	
	# Iterate through the dataset, reading the info about each
	# widget and creating a widget dictionary object.
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
	"""
	The widgets of a dashboard are displayed in a single column
		on a mobile device. In this case, the dashboard needs
		to know the total number of rows required to display
		the widgets. This utilizes the position info in the 'ds'
		dataset arg to count the total number of rows for the
		widgets of the dashboard.
		
	Args:
		ds: Dataset containing info about a dashboard's widgets. 
		gridRows: Configured number of rows in the dashboard's grid. 
		
	Returns:
		The total number of rows of a dashboard's widgets.
	"""
	
	rowIndex = 1	
	for row in ds:
		if row["action"]["action"] != "delete":
			position = row["sizes"][size].split(",")
			numRows = int(position[1]) - int(position[0])
			# To keep a 'consistent ratio' regarding widget height
			# on mobile for dashboards that have varying amounts
			# of rows in the grid (and also for the calculated font
			# and icon size in the status widgets), the num rows
			# are divided by the num rows in the grid, and the res
			# is multiplied by 50.
			numRows = (float(numRows)/float(gridRows))*50.0
			rowIndex += (numRows + 1)

	return round(rowIndex)
	
def getInstalledWidgets(ds, gridRows, gridColumns):
	"""
	Utilizes the info in the 'ds' dataset arg to create a list
		of dictionary objects that represents widgets that are
		available to be added to a dashboard.
		
	Args:
		ds: Dataset containing info about widgets that are
			available to install.
		gridRows: Number of grid rows for the current edit dash.
		gridColumns: Number of grid columns for the current edit dash.
		
	Returns:
		A list of dictionary objects that represents widgets
		that are available to install.
	"""
	widgets = {}
	
	# Set default column and row span for the widgets (when adding a new widget to a dash).
	defaultColSpan = round(0.23 * float(gridColumns))
	defaultRowSpan = round(0.23 * float(gridRows))
	
	# Iterate through the dataset, reading the widget info and
	# creating an 'avaialable widget' dictionary object for
	# each row.
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
	"""
	Utilizes the 'url' arg to find the dashboard in the 'dashboards'
		list arg that should be currently displayed on the Systems
		Overview page (in the current session).
		
	Args:
		dashboards: List of the available dashboards. 
		url: String representing the dashboard that should be displayed
			 in the current session.
		sub: Boolean denoting whether the dashboards list is a sub-member  
			 of the 'dashboards' arg.
			 
	Returns:
		A dictionary object representing the current dashboard.
	"""
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
			# Current dashboard is first dashboard returned.
			d = launchpad.dashboard.getDashboardObject(dbObj[0])
			
	return d
	
def getDropdownOptions(dashboards, sub=False):
	dropdownOptions = []
	
	for row in dashboards:
		option = {'label': row["name"], 'value': row["name"], 'url': "/dashboard/%s" % row["url"]}
		dropdownOptions.append(option)
		
	return dropdownOptions

def getDashboardObject(dbObj):
	"""
	Returns a dictionary object that represents a dashboard. Either
		returns an empty dashboard if the 'dbObj' param is a bool,
		or returns a non-empty dashboard that represents the dashboard
		in the 'dbObj' arg.
		
	Args:
		dbObj: Either a boolean, which means that an empty dashboard
			   should be returned, or an object that contains the
			   properties and widgets of a dashboard. 
		
	Returns:
		A dictionary object representing a dashboard.
	"""
	if isinstance(dbObj, bool):
		if dbObj:
			return {"id":None, "name":"", "url":"", "icon":"dashboard", "allow_edit":True, "widgets":[], "grid":"stretch", "cellSize":100, "gridRows":20, "gridCols":20, "gridRowGutterSize":6, "gridColGutterSize":6, "sizes":[0], "action":{"action":"add"}}
		else:
			return {"id":None, "name":None, "url":None, "icon":None, "allow_edit":False, "widgets":[], "grid":"stretch", "cellSize":100, "gridRows":20, "gridCols":20, "gridRowGutterSize":6, "gridColGutterSize":6, "sizes":[0], "action":{"action":""}}
	elif dbObj != None:
		return launchpad.dashboard.copyDictionary(dbObj)

def copyArray(items):
	"""
	Copies the info in the 'items' arg and returns the copied list.
		
	Args:
		items: The list to be copied.
		
	Returns:
		A list that is a copy of the 'items' arg.
	"""
	ret = []
	for value in items:
		if str(type(value)) == "<type 'com.inductiveautomation.perspective.gateway.script.PropertyTreeScriptWrapper$MapWrapper'>" or type(value) == dict:
			ret.append(launchpad.dashboard.copyDictionary(value))
		else:
			ret.append(value)
	return ret
		
def copyDictionary(items):
	"""
	Copies the info in the 'items' arg and returns the copied dictionary.
		
	Args:
		items: The dictionary to be copied.
		
	Returns:
		A dictionary that is a copy of the 'items' arg.
	"""
	ret = {}
	for key in items:
		value = items[key]
		
		if str(type(value)) == "<type 'com.inductiveautomation.perspective.gateway.script.PropertyTreeScriptWrapper$MapWrapper'>" or type(value) == dict:
			ret[key] = launchpad.dashboard.copyDictionary(value)
		else:
			ret[key] = value
	return ret
	
def editDashboard(self, add=True):
	"""
	Initiates the process of adding, editing, or deleting a dashboard.
		
	Args:
		self: Instance object containing session properties and
			  properties from the view from which this was called.
		add: Boolean denoting whether a dashboard is being added.
		
	Returns:
		This function does not have a return value.
	"""
	if add:
		# Create a new empty dashboard object and set the 'edit dashboard'
		# object equal to it.
		self.session.custom.launchpad.dashboard.objects.edit = launchpad.dashboard.getDashboardObject(True)
		maxId = system.db.runNamedQuery(path="Launchpad/Dashboard/Get URL", parameters={}) + 1
		self.session.custom.launchpad.dashboard.objects.edit.name = "Dashboard %d" % (maxId)
		self.session.custom.launchpad.dashboard.objects.edit.url = "dash%d" % (maxId)
		# Get the current dash settings to pass into dash details side panel,
		# so that if user clicks Cancel button after testing out different
		# settings then we can set the dash settings back.
		currEdit = {key: value for key, value in self.session.custom.launchpad.dashboard.objects.edit.iteritems() if key != 'widgets'}
		system.perspective.openDock('editDashDetails',params={'currEdit':currEdit})
	else:
		if self.session.custom.launchpad.dashboard.objects.current.id == None:
			return
		
		# Set the 'edit dashboard' object equal to the current dashboard and
		# then open the 'add edit dashboard' page.
		self.session.custom.launchpad.dashboard.objects.edit = launchpad.dashboard.getDashboardObject(self.session.custom.launchpad.dashboard.objects.current)
	
	system.perspective.navigate(view="Launchpad/Kpi/EmbeddedViews/Dashboard/Configuration/AddEdit Dashboard", params = {'add': add})

def addUpdateWidget(self):
	"""
	Either updates the position of an existing widget, or creates a
		new widget and appends it to the widgets of the dashboard
		that is currently being edited.
		
	Args:
		self: Instance object containing session properties and
			  properties from the view from which this was called.
		
	Returns:
		This function does not have a return value.
	"""
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
				# Updating the widget's position string.
				sessionWidgets[i]["sizes"][size] = positionStr
				foundIds.append(sessionWidgets[i]["id"])
				foundId = True
				break
			
		if not foundId:
			# Creating a new widget object and appending it to the
			# sessionWidgets list.
			id = UUID.randomUUID()
			sessionWidgets.append({"id":id, "widget_id":row.viewParams.widgetId, "name":row.viewParams.name, "widget":row.viewParams.widgetName, "path":row.viewParams.viewPath, "params":launchpad.dashboard.copyDictionary(row.viewParams.viewParams), "sizes":{newSize:positionStr for newSize in sizes}, "action":{"action":"add", "params":launchpad.dashboard.copyArray(row.viewParams.editParams)}})
			foundIds.append(id)

	# Mark the widgets to be removed (when 'save' button is pressed
	# we know which widgets need to be deleted).
	for i in range(len(sessionWidgets)):
		id = sessionWidgets[i]["id"]
		if id not in foundIds:
			sessionWidgets[i]["action"]["action"] = "delete"
		
def editWidget(self):
	"""
	Sets the new params on the widget object after editing a widget.
		
	Args:
		self: Instance object containing session properties and
			  properties from the view from which this was called.
		
	Returns:
		This function does not have a return value.
	"""
	# Get the widget id, name, and param values from the Widget Edit view.
	id = self.view.params.id
	name = self.view.params.name
	editParams = self.view.params.editParams
	
	# Find the widget that was just edited.
	widgets = self.session.custom.launchpad.dashboard.objects.edit.widgets
	widget = None
	for i in range(len(widgets)):
		if widgets[i]["id"] == id:
			widget = widgets[i]
			break
	
	params = widget["params"]
	actionParams = widget["action"]["params"]
	
	# Update the widget params.
	for i in range(len(editParams)):
		paramValue = editParams[i]["value"]
		actionParams[i]["value"] = paramValue
		params[editParams[i]["parameter"]] = paramValue
		
	widget["name"] = name
	system.perspective.closePopup(id="widget-parameters")
	
def syncDashboardDB(self):
	"""
	After the user has finished making modifications to a dashboard,
		this handles saving all of the changes to the db (editing
		dashboard details, adding widgets, etc).
		
	Args:
		self: Instance object containing session properties and
			  properties from the view from which this was called.
		
	Returns:
		This function does not have a return value.
	"""
	
	# Get the current 'edit dashboard' object.
	d = self.session.custom.launchpad.dashboard.objects.edit
	
	# Get the username of the author.
	username = self.session.custom.launchpad.dashboard.options.username
	
	# Inform user that dashboard must have a name.
	if d.name == None or d.name == "":
		launchpad.dashboard.showError("Please enter in a name")
		return
	
	# Inform user that dashboard must have a url.
	if d.url == None or d.url == "":
		launchpad.dashboard.showError("Please enter in a URL")
		return
	
	# Inform user that grid data must be entered.
	if d.cellSize == None or d.gridRows == None or d.gridCols == None or d.gridRowGutterSize == None or d.gridColGutterSize == None:
		launchpad.dashboard.showError("Please enter in grid data (cell size, rows, cols, gutter size)")
		return
	
	# Ensure that url is unique.
	urlId = system.db.runNamedQuery(path="Launchpad/Dashboard/Check URL", parameters={"url":d.url})
	if urlId != None and (d.id == None or d.id != urlId):
		launchpad.dashboard.showError("URL '%s' already exists. Please try another." % d.url)
		return
	
	if d.action.action == "add":
		# Execute 'add' named query to add the new dashboard.
		id = system.db.runNamedQuery(path="Launchpad/Dashboard/Add", parameters={"grid":d.grid, "cell_size":d.cellSize, "grid_rows":d.gridRows, "grid_cols":d.gridCols, "grid_row_gutter_size":d.gridRowGutterSize, "grid_col_gutter_size":d.gridColGutterSize, "icon":d.icon, "name":d.name, "url":d.url, "username":username}, getKey=True)
	else:
		# Execute the 'edit' named query to edit the dashboard.
		id = d.id
		system.db.runNamedQuery(path="Launchpad/Dashboard/Edit", parameters={"id":id, "grid":d.grid, "cell_size":d.cellSize, "grid_rows":d.gridRows, "grid_cols":d.gridCols, "grid_row_gutter_size":d.gridRowGutterSize, "grid_col_gutter_size":d.gridColGutterSize, "icon":d.icon, "name":d.name, "url":d.url, "username":username})
	
	# Add, edit, and delete the widgets based on the changes
	# made by the user.
	for widget in d.widgets:
		widgetId = None
		
		if widget.action.action == "delete":
			try:
				system.db.runNamedQuery(path="Launchpad/Dashboard/Widget/Delete", parameters={"id":widget.id})
			except:
				pass
		elif widget.action.action == "add":
			widgetId = system.db.runNamedQuery(path="Launchpad/Dashboard/Widget/Add", parameters={"dashboard_id":id, "widget_id":widget.widget_id, "name":widget.name, "position":widget.sizes[0]}, getKey=True)
		else:
			widgetId = widget.id
			system.db.runNamedQuery(path="Launchpad/Dashboard/Widget/Edit", parameters={"id":widgetId, "dashboard_id":id, "widget_id":widget.widget_id, "name":widget.name, "position":widget.sizes[0]})
			
		if widgetId != None:
			for param in widget.action.params:
				system.db.runNamedQuery(path="Launchpad/Dashboard/Widget/Parameter/Add" if widget.action.action == "add" else "Launchpad/Dashboard/Widget/Parameter/Edit", parameters={"widget_id":widgetId, "parameter_id":param.id, "parameter_value":param.value})
	
	# Now that the info regarding this dashboard has been updated
	# in the db, tell the dashboard to refresh itself.
	launchpad.dashboard.refresh(self)
	
	if d.action.action == "add":
		# New dashboard added, navigate to it.
		system.perspective.navigate(page="/dashboard/%s" % d.url)
	else:
		# Current dashboard was edited, so nav back to it.
		launchpad.dashboard.back(self)

def deleteDashboard(self):
	"""
	Deletes a dashboard.
		
	Args:
		self: Instance object containing session properties and
			  properties from the view from which this was called.
		
	Returns:
		This function does not have a return value.
	"""
	
	# Get the id of the 'edit dashboard' and execute 'delete'
	# named query to delete this dashboard from the db.
	id = self.session.custom.launchpad.dashboard.objects.edit.id
	system.db.runNamedQuery(path="Launchpad/Dashboard/Delete", parameters={"id":id})
	launchpad.dashboard.refresh(self)
	system.perspective.navigate(page="/dashboard")
	
def back(self):
	"""
	Navigates back to the previous page.
		
	Args:
		self: Instance object containing session properties and
			  properties from the view from which this was called.
		
	Returns:
		This function does not have a return value.
	"""
	system.perspective.navigate(page=self.page.props.path)
	
def refresh(self, fromSession=False):
	"""
	Refreshes the binding on the dbValid and dashboard.dashboards
		session custom properties. Called when a dashboard has
		been modified.
		
	Args:
		self: Instance object containing session properties and
			  properties from the view from which this was called.
		fromSession: Bool denoting whether this was called from
					 a session.
		
	Returns:
		This function does not have a return value.
	"""
	if fromSession:
		obj = self
	else:
		obj = self.session
		
	obj.refreshBinding("custom.launchpad.dashboard.dbValid")
	obj.refreshBinding("custom.launchpad.dashboard.dashboards")
	
def showError(message):
	"""
	Shows an error message in a popup.
		
	Args:
		message: The message to be displayed.
		
	Returns:
		This function does not have a return value.
	"""
	launchpad.dashboard.popupMessage("error", message, "Error_Text")
	
def showMessage(message):
	"""
	Shows a general message in a popup.
		
	Args:
		message: The message to be displayed.
		
	Returns:
		This function does not have a return value.
	"""
	launchpad.dashboard.popupMessage("info", message, "Text")
	
def popupMessage(icon, message, displayClass):
	"""
	Shows a message and icon in a popup.
		
	Args:
		icon: The icon to be displayed.
		message: The message to be displayed.
		displayClass: Style class to be used.
		
	Returns:
		This function does not have a return value.
	"""
	params = {"icon":icon, "display":message, "class":displayClass}
	system.perspective.openPopup(id="message", view="Launchpad/Kpi/EmbeddedViews/Dashboard/Configuration/Popup/Message", params=params, showCloseIcon=True, draggable=False, resizable=True, modal=True, overlayDismiss=False)
	
def showConfirmation(message, function, params={}):
	"""
	Shows a confirmation message in a popup. Allows for a
		function to be called if the 'Yes' button is pressed.
		
	Args:
		message: The message to be displayed.
		function: The function to execute if the user
				  presses the 'Yes' button.
		params: The params to pass to the function if
				the user presses the 'Yes' button.
		
	Returns:
		This function does not have a return value.
	"""
	params = {"icon":"help", "display":message, "class":"Text", "function":{"script":function, "params":params}}
	system.perspective.openPopup(id="confirmation", view="Launchpad/Kpi/EmbeddedViews/Dashboard/Configuration/Popup/Confirmation", params=params, showCloseIcon=True, draggable=False, resizable=True, modal=True, overlayDismiss=False)
