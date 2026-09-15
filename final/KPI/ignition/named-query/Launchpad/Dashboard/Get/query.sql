SELECT 
	d.id,
	d.name,
	d.url,
	COALESCE(d.icon, '') icon,
	d.username,
	d.grid,
	d.cell_size,
	d.grid_rows,
	d.row_gutter_size,
	d.grid_cols,
	d.col_gutter_size
FROM 
	ex_lp_dashboards d