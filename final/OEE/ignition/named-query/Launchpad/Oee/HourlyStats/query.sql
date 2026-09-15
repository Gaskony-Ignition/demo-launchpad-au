SELECT 
line_name
,hour_timestamp as time_stamp
,hour_oee_a as oee_a
,hour_oee_p as oee_p
,hour_oee_q as oee_q
,hour_oee_u as oee_u
,hour_oee as oee
,target_rate
,target_production_count
,hour_production_count as production_count
,hour_reject_count as reject_count
,hour_seconds_elapsed as seconds_elapsed
,hour_seconds_running as seconds_running
,hour_down_seconds  as down_seconds
,hour_idle_seconds  as idle_seconds
,hour_seconds_elapsed/60.0 as minutes_elapsed
,hour_seconds_running/60.0 as minutes_running
,hour_down_seconds/60.0  as down_minutes
,hour_idle_seconds/60.0  as idle_minutes
,day_timestamp
FROM 
ex_launchpad_oee_hour
WHERE (line_name = :line_name or :line_name = '')
AND hour_timestamp BETWEEN :start_time and :stop_time
AND tag_folder = :tag_folder
ORDER BY hour_timestamp

