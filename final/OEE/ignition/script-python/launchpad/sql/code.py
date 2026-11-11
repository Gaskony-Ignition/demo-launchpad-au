"""SQL helpers: build and run parameterised select, insert, update and delete statements."""

def sqlValues(instances):
	"""Return {name: value} for the non-autoincrement items, converting date types."""
	values = {item['name']:itemizer(item) for item in instances if not item['autoIncrement']}
	return values
	
def itemizer(item):
	"""Return the item's outputValue, parsed to a date for date, time and datetime types."""
	if item['dataType'] in ['date', 'time', 'datetime']:
		output = convertToDate(item['outputValue'], item['dateFormat'])
	else:
		output = item['outputValue']
	return output
	
def convertToDate(dateString, dateFormat):
	"""Parse dateString, mapping DD to d and Y to y in the format first."""
	dateFormat = dateFormat.replace('DD', 'd').replace('Y', 'y')
	return system.date.parse(dateString, dateFormat)
	
def keyHasValue(key, dict):
	"""Return 1 if key is in the dict with a truthy value, else 0."""
	valid = 1
	if key in dict.keys():
		if not dict[key]:
			valid = 0
	else:
		valid = 0
	return valid


def runDatabaseDelete(tableName, databaseName, idValue,idField):
	"""Delete the row where idField equals idValue; returns 1."""
	logger = system.util.getLogger("launchpad.oee.sql-actions")
	
	sql =  "DELETE FROM  %s WHERE %s = ? " %(tableName, idField)
	logger.info("runDatabaseDelete.  %s  %s" %(sql, idValue))
	system.db.runPrepUpdate(sql,[idValue], databaseName, getKey = 1)
	return 1

def runDatabaseSelect(tableName, databaseName, fields, keys):
	"""Select the fields (a list of names) where every key equals its value; returns [] if keys is empty."""
	whereString = ""
	fieldString = ""
	sql = ""
	params = []
	for f in fields:
		fieldString +=  f + ','
	for key in keys:
		whereString  += key + "=? AND "
		params.append(keys[key])
	if whereString:
		sql =  "SELECT  %s  FROM %s WHERE %s " %(fieldString[:-1] ,tableName, whereString[:4])
		data = system.db.runPrepQuery(sql, params, databaseName)
	else:
		data = []
	
	return data
	

def runDatabaseInsert(tableName, databaseName, dict):
	"""Insert dict (field: value) into the table; returns (new id, message)."""
	values = ""
	fields = ""
	params = []
	for key in dict:
		fields +=  key + ','
		params.append(dict[key])
		values += "?,"
			
	sql =  "INSERT INTO %s ( %s ) VALUES (%s) " %(tableName, fields[:-1], values[:-1])
	newId = system.db.runPrepUpdate(sql,params, databaseName, getKey = 1)
	return newId,  "New Record Added"

def runDatabaseUpdate(tableName, databaseName, dict, keys):
	"""Set the dict's fields on the rows matching keys; returns (rows updated, message), 0 rows if either is empty."""
	fields = ""
	params = []
	whereString = ""

	rows = 0
	for key in dict:
		fields +=  key + '=?,'
		params.append(dict[key])
	for key in keys:
		whereString  += key + "=? AND "
		params.append(keys[key])

	if whereString:
		whereString = "WHERE " + whereString[:-4]

	if fields and whereString:	

		sql =  "UPDATE %s SET %s  %s" %(tableName, fields[:-1], whereString)

		rows = system.db.runPrepUpdate(sql,params, databaseName)
	return rows, "Update Successful"
		
def dropdownLookup(valueColumn, labelColumn, table, database):
	"""Return value/label rows from the table, ordered by label."""
	query = 'SELECT %s as value, %s as label FROM %s ORDER BY %s' %(valueColumn, labelColumn, table, labelColumn)
	return system.db.runPrepQuery(query, [], database)
	

					
