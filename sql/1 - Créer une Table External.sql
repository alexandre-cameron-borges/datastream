-- location: EU
CREATE OR REPLACE EXTERNAL TABLE `sorbonne-475119.projetdatastream.uber_gcs_ext`
OPTIONS (
  format = 'CSV',
  uris = ['gs://my-taxi-bucket-eu/uber.csv'],
  skip_leading_rows = 1
);
