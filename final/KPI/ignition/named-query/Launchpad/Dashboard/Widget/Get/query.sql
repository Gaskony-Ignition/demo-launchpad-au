SELECT 
    dw.id,
    dw.name,
    w.id widget_id,
    w.name widget,
    w.path,
    p.id parameter_id,
    p.parameter_name,
    p.parameter,
    COALESCE(dp.parameter_value, p.default_value) parameter_value,
    t.id parameter_type_id,
    t.path parameter_type_path,
    p.configuration parameter_configuration,
    dw.position
FROM 
    ex_lp_dashboard_widgets dw 
        JOIN ex_lp_widgets w ON w.id = dw.widget_id
        LEFT JOIN ex_lp_widget_parameters p ON p.widget_id = dw.widget_id
        LEFT JOIN ex_lp_widget_parameter_types t ON t.id = p.parameter_type_id
        LEFT JOIN ex_lp_dashboard_widget_parameters dp ON dp.dashboard_widget_id = dw.id AND dp.parameter_id = p.id  
WHERE 
    dw.dashboard_id = :dashboard
ORDER BY
    dw.id ASC, p.parameter ASC, p.id ASC