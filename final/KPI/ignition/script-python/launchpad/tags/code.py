def browseTags(path="", filters=None):
	"""
	Browses tags and adds the results to objects to display
		in the tree.
			
	Args:
		path: Root path to browse.
		filters: Filters for the browse call.
			
	Returns:
		A list of tree objects that represent tags.
	"""
	tags = []
	results = system.tag.browse(path, {} if filters == None else filters)
	
	if results != None:
		for result in results.getResults():
			if result["name"] not in ["_types_"]:
				if str(result["tagType"]) in ["Folder", "UdtInstance", "Provider"]:
					tag = {'label': result["name"], 'expanded': False, 'data': {'folder':result["fullPath"], "hasChildren":result["hasChildren"]}, "items":[]}
				
					if result["hasChildren"]:
						# Add a fake item so that the tree renders this as a folder.
						tag['items'].append({"label":"Fake Item","expanded":False,"data":{"hasChildren":False},"items":[]})
				
					tags.append(tag)
				else:
					tags.append({'label': result["name"], 'data': {'tag': result["fullPath"], "hasChildren":result["hasChildren"]}, 'items': [], 'expanded': False})
	
	return tags
	
def browseHistoryTags(path="", filters=None):
	"""
	Browses historical tags and adds the results to objects 
		to display in the tree.
			
	Args:
		path: Root path to browse.
		filters: Filters for the browse call.
			
	Returns:
		A list of tree objects that represent tags.
	"""
	tags = []
	results = system.tag.browseHistoricalTags(path, {} if filters == None else filters)
	
	if results != None:
		for result in results.getResults():
			if result.hasChildren() == True:
				tag = {'label': result.path.lastPathComponent, 'expanded': False, 'data': {'folder': result.path, "hasChildren":result.hasChildren}, "items":[{"label":"Fake Item","expanded":False,"data":{"hasChildren":False},"items":[]}]}
			
				tags.append(tag)
			else:
				tags.append({'label': result.path.lastPathComponent, 'data': {'tag': result.path, "hasChildren":result.hasChildren}, 'expanded': False})
	
	return tags