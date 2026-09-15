INSERT INTO ex_lp_dashboards 
( 
	grid,
	cell_size,
	grid_rows,
	grid_cols,
	row_gutter_size,
	col_gutter_size,
	icon, name, 
	url, 
	username, 
	last_modified
) 
VALUES 
(  
	:grid,
	:cell_size,
	:grid_rows,
	:grid_cols,
	:grid_row_gutter_size,
	:grid_col_gutter_size,
	:icon, 
	:name, 
	:url, 
	:username,
	CURRENT_TIMESTAMP
)