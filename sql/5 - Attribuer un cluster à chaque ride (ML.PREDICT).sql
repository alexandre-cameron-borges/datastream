-- location: EU
CREATE OR REPLACE TABLE `sorbonne-475119.projetdatastream.predictions` AS
SELECT
  date,
  ID AS ride_id,
  lon, lat,
  centroid_id AS cluster_id
FROM ML.PREDICT(
  MODEL `sorbonne-475119.projetdatastream.kmeans8`,
  (
    SELECT
      CAST(lon AS FLOAT64) AS lon,
      CAST(lat AS FLOAT64) AS lat,
      date, ID
    FROM `sorbonne-475119.projetdatastream.rides_external`
    WHERE lon IS NOT NULL AND lat IS NOT NULL
  )
);
