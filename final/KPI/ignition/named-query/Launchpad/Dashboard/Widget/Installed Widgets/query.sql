SELECT 
	w.id,
	w.name widget,
	w.path,
	p.id parameter_id,
	p.parameter_name,
	p.parameter,
	p.default_value parameter_value,
	t.id parameter_type_id,
	t.path parameter_type_path,
	p.configuration parameter_configuration
FROM 
	ex_lp_widgets w
		LEFT JOIN ex_lp_widget_parameters p ON p.widget_id = w.id
		LEFT JOIN ex_lp_widget_parameter_types t ON t.id = p.parameter_type_id
ORDER BY 
	w.name ASC, w.id ASC, p.parameter ASC, p.id ASC