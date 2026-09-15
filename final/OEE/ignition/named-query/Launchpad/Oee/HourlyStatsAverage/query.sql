SELECT 
line_name
,avg(hour_oee_a) as oee_a
,avg(hour_oee_p) as oee_p
,avg(hour_oee_q) as oee_q
,avg(hour_oee_u) as oee_u
,avg(hour_oee) as oee
,sum(target_production_count) as target_production_count
,sum(hour_production_count) as production_count
,sum(hour_reject_count) as reject_count
,sum(hour_down_seconds)  as downtime
,sum(hour_idle_seconds)  as idletime
,sum(hour_seconds_running ) as runtime
, avg(target_rate) as target_rate
,sum(hour_seconds_elapsed/60.0) as minutes_elapsed
,sum(hour_seconds_running/60.0) as minutes_running
,sum(hour_down_seconds/60.0)  as down_minutes
,sum(hour_idle_seconds/60.0)  as idle_minutes
FROM 
ex_launchpad_oee_hour
WHERE (line_name = :line_name or :line_name = '')
AND tag_folder = :tag_folder
AND hour_timestamp BETWEEN :start_time and :stop_time
GROUP BY line_name
ORDER BY line_name

