-- location: EU
CREATE OR REPLACE VIEW `sorbonne-475119.projetdatastream.rides_external` AS
SELECT
  TIMESTAMP(date)          AS date,
  CAST(lat AS FLOAT64)     AS lat,
  CAST(lon AS FLOAT64)     AS lon,
  CAST(ID  AS STRING)      AS ID
FROM `sorbonne-475119.projetdatastream.uber_gcs_ext`;
