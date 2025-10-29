"""
🚀 DAG 2 : Kafka → Elasticsearch + Google Cloud Storage

Ce DAG consomme les messages Kafka produits par le DAG 1,
les transforme, puis les envoie vers :
- Elasticsearch → pour la visualisation sur Kibana
- GCS → pour l’archivage des données JSON

Étapes :
1. ConsumeKafka → lit un message du topic `result`
2. TransformJson → nettoie et structure les données
3. PutElasticSearch → indexe dans `taxi_rides`
4. PutGCP → sauvegarde le JSON dans le bucket `laye2025`

Objectif : pipeline temps réel (Kafka → Airflow → Elastic + GCS)
"""



from __future__ import annotations
import json
import logging
from datetime import datetime
from airflow.decorators import dag, task
from kafka import KafkaConsumer
from airflow.providers.elasticsearch.hooks.elasticsearch import ElasticsearchHook
from airflow.providers.google.cloud.hooks.gcs import GCSHook
from elasticsearch import Elasticsearch  # ✅ import en haut

log = logging.getLogger(__name__)

# -------------------------------------------------------------------
# 🔧 Configuration
# -------------------------------------------------------------------
KAFKA_BOOTSTRAP = "kafka:9092"
TOPIC_RESULT = "result"
ELASTIC_CONN_ID = "elasticsearch_default"
ELASTIC_INDEX = "taxi_rides"
GCP_CONN_ID = "google_cloud_default"
GCS_BUCKET = "laye2025"


# -------------------------------------------------------------------
# 🧩 Fonction utilitaire
# -------------------------------------------------------------------
def create_kafka_consumer(topic: str) -> KafkaConsumer:
    """Crée un consommateur Kafka sans group_id (lit tout à chaque run)."""
    return KafkaConsumer(
        topic,
        bootstrap_servers=[KAFKA_BOOTSTRAP],
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        group_id=None,
        consumer_timeout_ms=10000,
    )


# -------------------------------------------------------------------
# 🚀 DAG Principal
# -------------------------------------------------------------------
@dag(
    dag_id="dag2_kafka_elastic_gcs",
    start_date=datetime(2025, 1, 1),
    schedule_interval="* * * * *",  # toutes les minutes
    catchup=False,
    tags=["kafka", "elasticsearch", "gcs", "big_data"],
)
def dag2_kafka_elastic_gcs():

    # 1️⃣ Consommer depuis Kafka
    @task(task_id="ConsumeKafka")
    def consume_kafka_result():
        log.info("📥 Démarrage de la consommation du topic Kafka 'result'...")
        consumer = create_kafka_consumer(TOPIC_RESULT)
        message = next(consumer, None)
        consumer.close()

        if message is None:
            log.warning("⚠️ Aucun message reçu depuis Kafka.")
            return None

        msg_data = json.loads(message.value.decode("utf-8"))
        log.info(f"✅ Message consommé depuis Kafka: {msg_data}")
        return msg_data

    # 2️⃣ Transformation JSON
    @task(task_id="TransformJson")
    def transform_for_elastic(data: dict | None):
        if not data:
            log.warning("Aucune donnée à transformer.")
            return None

        transformed = {
            "confort": data.get("confort"),
            "prix_base_per_km": data.get("prix_base_per_km"),
            "client_nom": data.get("properties-client", {}).get("nomclient"),
            "driver_nom": data.get("properties-driver", {}).get("nomDriver"),
            "distance_km": data.get("distance_km"),
            "travel_cost": data.get("travel_cost"),
            "agent_timestamp": datetime.utcnow().isoformat(),
            "client_location": {
                "lat": data.get("properties-client", {}).get("latitude"),
                "lon": data.get("properties-client", {}).get("logitude"),
            },
            "driver_location": {
                "lat": data.get("properties-driver", {}).get("latitude"),
                "lon": data.get("properties-driver", {}).get("logitude"),
            },
        }
        log.info(f"🧩 Données transformées: {transformed}")
        return transformed

    # 3️⃣ Envoi vers Elasticsearch
    @task(task_id="PutElasticSearch")
    def put_elasticsearch(data: dict | None):
        if not data:
            log.warning("Aucune donnée reçue pour Elasticsearch.")
            return

        es_hook = ElasticsearchHook(elasticsearch_conn_id=ELASTIC_CONN_ID)
        conn = es_hook.get_connection(ELASTIC_CONN_ID)

        # ✅ Corrigé : bloc bien indenté
        es = Elasticsearch(
            hosts=[{"host": conn.host, "port": conn.port, "scheme": "http"}],
            basic_auth=(conn.login, conn.password) if conn.login else None,
            verify_certs=False
        )

        try:
            if not es.indices.exists(index=ELASTIC_INDEX):
                es.indices.create(index=ELASTIC_INDEX)
                log.info(f"✅ Index '{ELASTIC_INDEX}' créé.")

            es.index(index=ELASTIC_INDEX, document=data)
            log.info(f"📤 Donnée indexée dans '{ELASTIC_INDEX}': {data}")

        except Exception as e:
            log.error(f"❌ Erreur d’insertion Elasticsearch : {e}")

    # 4️⃣ Envoi vers Google Cloud Storage
    @task(task_id="PutGCP")
    def put_gcs(data: dict | None):
        if not data:
            log.warning("Aucune donnée reçue pour GCS.")
            return

        gcs_hook = GCSHook(gcp_conn_id=GCP_CONN_ID)
        file_name = f"rides/{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}.json"
        json_data = json.dumps(data)

        gcs_hook.upload(bucket_name=GCS_BUCKET, object_name=file_name, data=json_data)
        log.info(f"✅ Donnée sauvegardée sur GCS: gs://{GCS_BUCKET}/{file_name}")

    # -------------------------------------------------------------------
    # 🔗 Orchestration des tâches
    # -------------------------------------------------------------------
    raw = consume_kafka_result()
    transformed = transform_for_elastic(raw)
    put_elasticsearch(transformed)
    put_gcs(transformed)


dag2_kafka_elastic_gcs()
