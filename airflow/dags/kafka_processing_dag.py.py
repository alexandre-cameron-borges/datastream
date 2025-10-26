"""
DAG Name: kafka_processing_dag
Description:
    Ce DAG consomme les messages produits par Kafka, applique des transformations et
    enrichissements sur les données, puis les prépare pour l’indexation dans Elasticsearch.

Tâches principales:
    - Lecture des messages Kafka depuis le topic source.
    - Transformation des coordonnées (lat, lon) en format géospatial (geo_point).
    - Ajout de champs calculés ou dérivés.
    - Export des données transformées vers un fichier JSON ou un topic Kafka de sortie.

Objectif:
    Nettoyer et enrichir les données issues de Kafka avant l’étape d’indexation.

Schedule: @hourly
Tags: [kafka, transformation, preprocessing]
"""




from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
from confluent_kafka import Consumer, Producer
import json, time

SOURCE_TOPIC = "source"
RESULT_TOPIC = "result"
BOOTSTRAP = "kafka-1:9092"  # ✅ interne Docker

def _haversine(lat1, lon1, lat2, lon2):
    """Calcul de la distance haversine en km."""
    from math import radians, sin, cos, asin, sqrt
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    return 2 * R * asin(sqrt(a))

def consume_source(**ctx):
    """Consomme les messages du topic 'source'."""
    c = Consumer({
        "bootstrap.servers": BOOTSTRAP,
        "group.id": f"airflow-source-consumer-{int(time.time())}",  # unique par run
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
    })
    c.subscribe([SOURCE_TOPIC])
    out = []
    start = time.time()
    timeout = 30  # ne reste pas bloqué trop longtemps
    max_msgs = 5000

    try:
        while time.time() - start < timeout and len(out) < max_msgs:
            msg = c.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                print(f"⚠️ Kafka error: {msg.error()}")
                continue
            try:
                val = msg.value().decode("utf-8")
                data = json.loads(val) if val.startswith("{") else {"raw": val}
                out.append(data)
            except Exception as e:
                print(f"Skip invalid message: {e}")
        print(f"📥 Consumed {len(out)} messages from '{SOURCE_TOPIC}'")
    finally:
        c.close()

    # Éviter blocage si aucun message
    if not out:
        print("⚠️ No messages consumed — skipping further tasks.")
        ctx["ti"].xcom_push(key="batch", value=[])
        return

    ctx["ti"].xcom_push(key="batch", value=out)

def compute_cost(**ctx):
    """Calcule la distance et le coût du trajet."""
    batch = ctx["ti"].xcom_pull(key="batch", task_ids="ConsumeKafka") or []
    if not batch:
        print("⚠️ No data to enrich.")
        ctx["ti"].xcom_push(key="batch_enriched", value=[])
        return

    for rec in batch:
        try:
            if all(k in rec for k in ("pickup_lat", "pickup_lon", "dropoff_lat", "dropoff_lon")):
                d = _haversine(
                    float(rec["pickup_lat"]), float(rec["pickup_lon"]),
                    float(rec["dropoff_lat"]), float(rec["dropoff_lon"])
                )
                rec["distance_km"] = round(d, 3)
                rec["cost"] = round(2.50 + 1.2 * d, 2)
            else:
                rec.setdefault("distance_km", None)
                rec["cost"] = 5.00
        except Exception as e:
            print(f"Cost error: {e}")
            rec["cost"] = 5.00
    ctx["ti"].xcom_push(key="batch_enriched", value=batch)
    print(f"🧮 Enriched {len(batch)} messages with cost")

def publish_result(**ctx):
    """Publie les messages enrichis dans le topic 'result'."""
    batch = ctx["ti"].xcom_pull(key="batch_enriched", task_ids="ComputeCostTravel") or []
    if not batch:
        print("⚠️ No messages to publish.")
        return

    p = Producer({"bootstrap.servers": BOOTSTRAP, "client.id": "airflow-publisher"})
    sent = 0
    for rec in batch:
        p.produce(RESULT_TOPIC, value=json.dumps(rec).encode("utf-8"))
        sent += 1
    p.flush()
    print(f"📤 Published {sent} messages to '{RESULT_TOPIC}'")

with DAG(
    dag_id="kafka_processing_dag",
    description="Consume from Kafka 'source', compute cost, publish to 'result'",
    schedule_interval=None,
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args={"retries": 0, "retry_delay": timedelta(minutes=1)},
    tags=["kafka", "compute", "result"],
) as dag:

    t1 = PythonOperator(task_id="ConsumeKafka", python_callable=consume_source, provide_context=True)
    t2 = PythonOperator(task_id="ComputeCostTravel", python_callable=compute_cost, provide_context=True)
    t3 = PythonOperator(task_id="PublishKafka", python_callable=publish_result, provide_context=True)

    t1 >> t2 >> t3
