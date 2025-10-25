-- location: EU
CREATE OR REPLACE TABLE `sorbonne-475119.projetdatastream.kmeans8_centroids` AS
SELECT
  centroid_id,
  MAX(IF(feature='lon', numerical_value, NULL)) AS c_lon,
  MAX(IF(feature='lat', numerical_value, NULL)) AS c_lat
FROM ML.CENTROIDS(MODEL `sorbonne-475119.projetdatastream.kmeans8`)
GROUP BY centroid_id;
