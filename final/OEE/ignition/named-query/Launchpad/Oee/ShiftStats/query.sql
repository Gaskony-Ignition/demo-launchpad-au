SELECT
line_name
,shift_start  as time_stamp
,shift
,avg(shift_oee_a) as oee_a
,avg(shift_oee_p) as oee_p
,avg(shift_oee_q) as oee_q
,avg(shift_oee_u) as oee_u
,avg(shift_oee) as oee
,sum(target_production_count) as target_production_count
,sum(shift_production_count) as production_count
,sum(shift_reject_count) as reject_count
,sum(shift_down_seconds)  as downtime
,sum(shift_idle_seconds)  as idletime
,sum(shift_running_seconds) as runtime
, avg(target_rate) as target_rate
,sum(shift_seconds_elapsed/60.0) as minutes_elapsed
,sum(shift_running_seconds/60.0) as minutes_running
,sum(shift_down_seconds/60.0)  as down_minutes
,sum(shift_idle_seconds/60.0)  as idle_minutes
FROM 
ex_launchpad_oee_shift
WHERE (line_name = :line_name or :line_name = '')
AND tag_folder = :tag_folder
AND shift_start BETWEEN :start_time and :stop_time
GROUP BY line_name, shift_start, shift
ORDER BY shift_start, line_name


