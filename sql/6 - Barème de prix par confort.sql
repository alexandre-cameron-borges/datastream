-- location: EU
CREATE OR REPLACE TABLE `sorbonne-475119.projetdatastream.confort_pricing` AS
SELECT 'Low' AS confort,    1.20 AS price_per_km UNION ALL
SELECT 'Medium',            2.00                 UNION ALL
SELECT 'High',              3.20;
