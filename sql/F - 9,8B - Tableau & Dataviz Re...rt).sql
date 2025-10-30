-- location: EU
WITH last_day AS (
  SELECT DATE(MAX(agent_timestamp)) AS d
  FROM `sorbonne-475119.projetdatastream.uber_gcs_json_ext`
)
SELECT
  window_start,
  confort,
  cluster_id,
  SUM(revenue_eur) AS revenue_eur
FROM `sorbonne-475119.projetdatastream.revenue_by_cluster_hour_B`, last_day
WHERE DATE(window_start) = last_day.d
GROUP BY window_start, cluster_id, confort
ORDER BY window_start;

