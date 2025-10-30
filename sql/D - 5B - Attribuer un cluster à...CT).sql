-- location: EU
CREATE OR REPLACE TABLE `sorbonne-475119.projetdatastream.predictions_B` AS
SELECT
  date,
  ID AS ride_id,
  lon, lat,
  centroid_id AS cluster_id
FROM ML.PREDICT(
  MODEL `sorbonne-475119.projetdatastream.kmeans8`,
  (
    SELECT
      CAST(substring(locationClient,1,6) AS FLOAT64)     AS lon,
      CAST(substring(locationClient,8,8) AS FLOAT64)     AS lat,
      TIMESTAMP(agent_timestamp)          AS date,
      GENERATE_UUID()      AS ID
    FROM `sorbonne-475119.projetdatastream.uber_gcs_json_ext`
    WHERE substring(locationClient,1,6) IS NOT NULL AND substring(locationClient,8,8) IS NOT NULL
  )
);

-- select * from sorbonne-475119.projetdatastream.uber_gcs_json_ext
-- select * from sorbonne-475119.projetdatastream.predictions_B
