-- location: EU
-- V1. Prix possibles par ride × confort, calculés à la volée
CREATE OR REPLACE VIEW `sorbonne-475119.projetdatastream.v_prices_per_ride_all_conforts_rt` AS
WITH cents AS (
  SELECT
    centroid_id,
    MAX(IF(feature='lon', numerical_value, NULL)) AS c_lon,
    MAX(IF(feature='lat', numerical_value, NULL)) AS c_lat
  FROM ML.CENTROIDS(MODEL `sorbonne-475119.projetdatastream.kmeans8`)
  GROUP BY centroid_id
),
preds AS (
  -- on prédit directement depuis l'externe GCS : TOUT nouveau fichier est pris en compte
  SELECT
    r.date, r.ID AS ride_id, r.lon, r.lat,
    p.centroid_id AS cluster_id
  FROM ML.PREDICT(
    MODEL `sorbonne-475119.projetdatastream.kmeans8`,
    (SELECT CAST(lon AS FLOAT64) lon, CAST(lat AS FLOAT64) lat, date, ID
     FROM `sorbonne-475119.projetdatastream.rides_external`
     WHERE lon IS NOT NULL AND lat IS NOT NULL)
  ) p
  JOIN `sorbonne-475119.projetdatastream.rides_external` r
    ON r.ID = p.ID  -- selon ton schéma, sinon join sur (lon,lat,date)
),
base AS (
  SELECT
    preds.*,
    ST_DISTANCE(ST_GEOGPOINT(preds.lon, preds.lat),
                ST_GEOGPOINT(cents.c_lon, cents.c_lat)) / 1000.0 AS distance_km
  FROM preds
  JOIN cents ON preds.cluster_id = cents.centroid_id
)
SELECT
  b.*,
  cp.confort,
  cp.price_per_km,
  ROUND(b.distance_km * cp.price_per_km, 2) AS price_eur
FROM base b
CROSS JOIN `sorbonne-475119.projetdatastream.confort_pricing` cp;
