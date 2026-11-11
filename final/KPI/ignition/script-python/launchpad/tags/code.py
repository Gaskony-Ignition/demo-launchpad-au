def browseTags(path="", filters=None):
	"""Return tree items for the tags and folders under path."""
	tags = []
	results = system.tag.browse(path, {} if filters == None else filters)
	
	if results != None:
		for result in results.getResults():
			if result["name"] not in ["_types_"]:
				if str(result["tagType"]) in ["Folder", "UdtInstance", "Provider"]:
					tag = {'label': result["name"], 'expanded': False, 'data': {'folder':result["fullPath"], "hasChildren":result["hasChildren"]}, "items":[]}
				
					if result["hasChildren"]:
						tag['items'].append({"label":"Fake Item","expanded":False,"data":{"hasChildren":False},"items":[]})
				
					tags.append(tag)
				else:
					tags.append({'label': result["name"], 'data': {'tag': result["fullPath"], "hasChildren":result["hasChildren"]}, 'items': [], 'expanded': False})
	
	return tags
	
def browseHistoryTags(path="", filters=None):
	"""Return tree items for the historical tags and folders under path."""
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