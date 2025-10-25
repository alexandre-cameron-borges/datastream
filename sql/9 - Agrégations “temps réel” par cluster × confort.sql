-- location: EU
CREATE OR REPLACE TABLE `sorbonne-475119.projetdatastream.revenue_by_cluster_minute` AS
SELECT
  TIMESTAMP_TRUNC(date, MINUTE) AS window_start,
  cluster_id,
  confort,
  SUM(price_eur) AS revenue_eur,
  COUNT(*)       AS rides
FROM `sorbonne-475119.projetdatastream.prices_per_ride_all_conforts`
GROUP BY window_start, cluster_id, confort
ORDER BY window_start;
