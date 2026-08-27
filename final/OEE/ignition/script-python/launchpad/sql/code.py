def sql_values(instances):
	values = {item['name']:itemizer(item) for item in instances if not item['autoIncrement']}
	return values
	
def itemizer(item):
	if item['dataType'] in ['date', 'time', 'datetime']:
		output = convertToDate(item['outputValue'], item['dateFormat'])
	else:
		output = item['outputValue']
	return output
	
def convertToDate(dateString, dateFormat):
	dateFormat = dateFormat.replace('DD', 'd').replace('Y', 'y')
	return system.date.parse(dateString, dateFormat)
	
def keyHasValue(key, dict):
	valid = 1
	msg = ""
	if key in dict.keys():
		if not dict[key]:
			valid = 0
	else:
		valid = 0
	return valid


def runDatabaseDelete(tableName, databaseName, idValue,idField):
	#build a sql delete statement for the given table name and then run on the given database connection
	logger = system.util.getLogger("launchpad.oee.sql-actions")
	
	sql =  "DELETE FROM  %s WHERE %s = ? " %(tableName, idField)
	logger.info("runDatabaseDelete.  %s  %s" %(sql, idValue))
	newId = system.db.runPrepUpdate(sql,[idValue], databaseName, getKey = 1)
	return 1

def runDatabaseSelect(tableName, databaseName, fields, keys):
	#build a sql select statement for the given table name and then run on the given database connection
	#fields:  string with comma separated field names
	#keys: dictionary with primary key field names and values
	whereString = ""
	fieldString = ""
	sql = ""
	params = []
	#values, fields and params are the building blocks for SQL SELECT statement.  
	# the sql statement will then be used in a runPrepQuery function system.db.runPrepQuery("SELECT a,b,c FROM mytable WHERE primaryKey = ?", [params])

	#whereString: SQL WHERE clause
	#fieldString: string with comma separated field names
	#params: list of parameter values
	
	#build field string	
	for f in fields:
		fieldString +=  f + ','
	#build where clause
	for key in keys:
		whereString  += key + "=? AND "
		params.append(keys[key])
	#whereString = "1=1 AND"
	if whereString:
		sql =  "SELECT  %s  FROM %s WHERE %s " %(fieldString[:-1] ,tableName, whereString[:4])
		data = system.db.runPrepQuery(sql, params, databaseName)
	else:
		data = []
	print sql
	print data
	
	return data
	

def runDatabaseInsert(tableName, databaseName, dict):
	#build a sql insert statement for the given table name  and then run on the given database connection
	#dict: dictionary with field name - value pairs
	values = ""
	fields = ""
	params = []
	#values, fields and params are the building blocks for SQL INSERT statement.  
	# the sql statement will then be used in a runPrepUpdate function system.db.runPrepUpdate("INSERT INTO mytable {fields} VALUES {?,?,?}", [params])
	#values: string with comma separated paramenter placeholders
	#fields: string with comma separated field names
	#params: python list of parameter values
		
	for key in dict:
		fields +=  key + ','
		params.append(dict[key])
		values += "?,"
			
	sql =  "INSERT INTO %s ( %s ) VALUES (%s) " %(tableName, fields[:-1], values[:-1])
	newId = system.db.runPrepUpdate(sql,params, databaseName, getKey = 1)
	return newId,  "New Record Added"

def runDatabaseUpdate(tableName, databaseName, dict, keys):
	#build a sql update statement and then run on the given table name on the given database connection
	#dict: dictionary with field name - value pairs
	#keys: dictionary with primary key field names and values
	logger = system.util.getLogger("launchpad.oee.sql-actions")
	fields = ""
	params = []
	whereString = ""

	rows = 0
	#values, fields and params are the building blocks for SQL UPDATE statement.  
	# the sql statement will then be used in a runPrepUpdate function system.db.runPrepUpdate("UPDATE mytable SET Field1=?, Field2=? WHERE ID=?", [params])
	#fields:  string with comma separated field names
	#params: python list of parameter values
	#whereString: SQL WHERE clause

	#build field string and parameters with values		
	for key in dict:
		fields +=  key + '=?,'
		params.append(dict[key])
	#build where clause
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
	query = 'SELECT %s as value, %s as label FROM %s ORDER BY %s' %(valueColumn, labelColumn, table, labelColumn)
	return system.db.runPrepQuery(query, [], database) # prep might not work due to dynamic column/table names
	#return system.db.runQuery(query, database)
	

					
