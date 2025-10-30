-- location: EU
CREATE OR REPLACE MODEL `sorbonne-475119.projetdatastream.kmeans8`
OPTIONS(
  model_type='kmeans',
  num_clusters=8,
  kmeans_init_method='kmeans++',
  standardize_features=TRUE
) AS
SELECT lon, lat
FROM `sorbonne-475119.projetdatastream.rides_external`
WHERE lon IS NOT NULL AND lat IS NOT NULL;
