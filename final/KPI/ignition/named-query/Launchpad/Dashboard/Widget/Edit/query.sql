UPDATE ex_lp_dashboard_widgets
SET
	dashboard_id = :dashboard_id, 
	widget_id = :widget_id, 
	name = :name,
	position = :position
WHERE 
	id = :id