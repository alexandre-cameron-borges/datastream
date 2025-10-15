from airflow.decorators import dag, task
from datetime import datetime
import os, json, time

@dag(
    dag_id="dag_index_gcs_es",
    start_date=datetime(2024, 1, 1),
    schedule=None, catchup=False,
    description="Consomme rides.result, aplatit + agent_timestamp, vers ES + GCS"
)
def index_gcs_es():
    @task
    def consume_result():
        from kafka import KafkaConsumer
        brokers = os.getenv("KAFKA_BROKERS","broker:9092")
        topic = os.getenv("KAFKA_TOPIC_RESULT","rides.result")
        c = KafkaConsumer(topic, bootstrap_servers=brokers,
                          value_deserializer=lambda v: json.loads(v.decode()))
        return next(c).value

    @task
    def transform(doc: dict):
        doc["agent_timestamp"] = int(time.time() * 1000)
        # aplatir si besoin (ex: doc.update(doc.pop("nested",{})))
        return doc

    @task
    def put_es(doc: dict):
        from elasticsearch import Elasticsearch
        es = Elasticsearch(os.getenv("ES_HOST","http://elasticsearch:9200"))
        index = os.getenv("ES_INDEX","rides-result")
        es.index(index=index, document=doc)

    @task
    def put_gcs(doc: dict):
        from google.cloud import storage
        bkt = os.getenv("GCS_BUCKET"); assert bkt, "GCS_BUCKET manquant"
        client = storage.Client(project=os.getenv("GCP_PROJECT"))
        blob = client.bucket(bkt).blob(f"rides/{doc.get('ride_id','noid')}-{doc['agent_timestamp']}.json")
        blob.upload_from_string(json.dumps(doc), content_type="application/json")

    d = transform(consume_result())
    put_es(d); put_gcs(d)

index_gcs_es()
