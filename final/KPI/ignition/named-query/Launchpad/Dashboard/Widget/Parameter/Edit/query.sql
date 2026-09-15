UPDATE ex_lp_dashboard_widget_parameters 
SET
	parameter_value = :parameter_value
WHERE 
	dashboard_widget_id = :widget_id AND 
	parameter_id = :parameter_id