UPDATE ex_lp_dashboards 
SET
	grid = :grid,
	cell_size = :cell_size,
	grid_rows = :grid_rows,
	grid_cols = :grid_cols,
	row_gutter_size = :grid_row_gutter_size,
	col_gutter_size = :grid_col_gutter_size,
	icon = :icon, 
	name = :name, 
	url = :url, 
	username = :username, 
	last_modified = CURRENT_TIMESTAMP 
WHERE 
	id = :id