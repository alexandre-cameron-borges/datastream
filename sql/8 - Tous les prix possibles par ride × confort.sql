-- location: EU
CREATE OR REPLACE TABLE `sorbonne-475119.projetdatastream.prices_per_ride_all_conforts` AS
WITH rides AS (
  SELECT p.date, p.ride_id, p.lon, p.lat, p.cluster_id,
         ST_DISTANCE(
           ST_GEOGPOINT(p.lon, p.lat),
           ST_GEOGPOINT(c.c_lon, c.c_lat)
         ) / 1000.0 AS distance_km
  FROM `sorbonne-475119.projetdatastream.predictions` p
  JOIN `sorbonne-475119.projetdatastream.kmeans8_centroids` c
    ON p.cluster_id = c.centroid_id
)
SELECT
  r.date,
  r.ride_id,
  r.cluster_id,
  r.lon, r.lat,
  r.distance_km,
  cp.confort,
  cp.price_per_km,
  ROUND(r.distance_km * cp.price_per_km, 2) AS price_eur
FROM rides r
CROSS JOIN `sorbonne-475119.projetdatastream.confort_pricing` cp;
