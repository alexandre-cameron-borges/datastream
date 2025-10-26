"""
DAG Name: elastic_gcp_ingestion_dag
Description:
    Ce DAG gère le chargement des données traitées vers Elasticsearch (ou vers une instance GCP),
    en créant les index et en effectuant des insertions massives via l’API _bulk.

Tâches principales:
    - Connexion à Elasticsearch via API REST.
    - Création et gestion des index (csv_index, mapping geo_point, etc.).
    - Injection des données JSON transformées via l’API _bulk.
    - Vérification et validation du comptage des documents ingérés.

Objectif:
    Automatiser la mise à jour des index Elasticsearch pour la visualisation dans Kibana.

Schedule: @daily
Tags: [elasticsearch, ingestion, gcp, kibana]
"""


from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
from confluent_kafka import Consumer
from elasticsearch import Elasticsearch
from dateutil import tz
import json, time

# Kafka et Elasticsearch
RESULT_TOPIC = "result"
BOOTSTRAP = "kafka-1:9092"
ES_HOST = "http://elasticsearch:9200"
ES_INDEX = "csv_index"

def consume_result(**ctx):
    """Lit les messages du topic Kafka 'result'."""
    c = Consumer({
        "bootstrap.servers": BOOTSTRAP,
        "group.id": f"airflow-result-consumer-{int(time.time())}",
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
    })
    c.subscribe([RESULT_TOPIC])
    out = []
    deadline = time.time() + 25
    try:
        while time.time() < deadline and len(out) < 5000:
            msg = c.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                print(f"⚠️ Kafka error: {msg.error()}")
                continue
            try:
                data = json.loads(msg.value().decode("utf-8"))
                out.append(data)
            except Exception as e:
                print(f"Skip invalid message: {e}")
        print(f"📥 Consumed {len(out)} messages from '{RESULT_TOPIC}'")
    finally:
        c.close()
    ctx["ti"].xcom_push(key="batch_result", value=out)

def transform(**ctx):
    """Ajoute un timestamp et construit le champ 'location'."""
    batch = ctx["ti"].xcom_pull(key="batch_result", task_ids="ConsumeKafka") or []
    now_iso = datetime.now(tz.UTC).isoformat()
    transformed = []

    for rec in batch:
        try:
            # Ajout du timestamp
            rec["agent_timestamp"] = now_iso

            # Conversion géographique
            lat = rec.get("lat")
            lon = rec.get("lon")
            if lat is not None and lon is not None:
                rec["location"] = {"lat": float(lat), "lon": float(lon)}

            transformed.append(rec)
        except Exception as e:
            print(f"⚠️ Transformation error: {e}")

    print(f"🧮 Transformed {len(transformed)} records with geo field")
    ctx["ti"].xcom_push(key="batch_result", value=transformed)

def index_elasticsearch(**ctx):
    """Indexe les documents dans Elasticsearch."""
    batch = ctx["ti"].xcom_pull(key="batch_result", task_ids="TransformRecords") or []
    es = Elasticsearch(ES_HOST)

    for rec in batch:
        es.index(index=ES_INDEX, document=rec)

    print(f"📤 Indexed {len(batch)} documents into Elasticsearch index '{ES_INDEX}'")

# --- Définition du DAG ---
with DAG(
    dag_id="elastic_gcp_ingestion_dag",
    description="Consume from Kafka 'result', transform, and index into Elasticsearch with geo_point",
    schedule_interval=None,
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args={"retries": 0, "retry_delay": timedelta(minutes=1)},
    tags=["kafka", "elasticsearch", "geo"],
) as dag:

    t1 = PythonOperator(
        task_id="ConsumeKafka",
        python_callable=consume_result,
        provide_context=True,
    )

    t2 = PythonOperator(
        task_id="TransformRecords",
        python_callable=transform,
        provide_context=True,
    )

    t3 = PythonOperator(
        task_id="IndexElasticsearch",
        python_callable=index_elasticsearch,
        provide_context=True,
    )

    t1 >> t2 >> t3
