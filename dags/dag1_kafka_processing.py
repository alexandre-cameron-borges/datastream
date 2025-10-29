"""
🎯 DAG 1 : Producteur Kafka

Ce DAG génère des données simulées de trajets de taxi
et les envoie dans le topic Kafka `result`.

➡️ Objectif : alimenter le pipeline temps réel.

Étapes :
1. Génère un message JSON (client, driver, distance, coût…)
2. Publie le message sur Kafka via un `KafkaProducer`.

Source : Simulation Python  
Destination : Kafka (`result`)
Fréquence : chaque minute
"""

from __future__ import annotations
import json
import logging
import time
from datetime import datetime
from math import radians, sin, cos, sqrt, atan2
from kafka import KafkaProducer, KafkaConsumer
from airflow.models.dag import DAG
from airflow.decorators import task

log = logging.getLogger(__name__)

# --- Fonctions utilitaires ---
def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlon, dlat = lon2 - lon1, lat2 - lat1
    a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))

def get_kafka_consumer(topic):
    return KafkaConsumer(
        topic,
        bootstrap_servers=['kafka:9092'],
        auto_offset_reset='earliest',
        group_id='airflow-consumers-dag1',
        enable_auto_commit=True
    )

def get_kafka_producer():
    return KafkaProducer(
        bootstrap_servers=['kafka:9092'],
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )

# --- Définition du DAG ---
with DAG(
    dag_id="dag1_calcul_trajet_kafka",
    start_date=datetime(2025, 1, 1),
    schedule="* * * * *",  # exécution chaque minute
    catchup=False,
    tags=["kafka", "streaming"],
) as dag:

    @task(task_id="ConsumKafka")
    def consume_from_kafka_source():
        """Attente jusqu’à 2 minutes pour recevoir un message."""
        consumer = get_kafka_consumer('source')
        log.info("✅ Consommateur Kafka créé pour le topic 'source'. En attente de messages...")

        message_data = None
        start_time = time.time()

        while (time.time() - start_time) < 120:  # 2 minutes max
            records = consumer.poll(timeout_ms=5000, max_records=1)
            if records:
                for msgs in records.values():
                    for record in msgs:
                        message_data = json.loads(record.value.decode('utf-8'))
                        log.info(f"📩 Message reçu : {message_data}")
                        break
            if message_data:
                break
            log.info("⏳ Aucun message encore... nouvelle tentative.")
            time.sleep(2)

        consumer.close()
        if not message_data:
            log.warning("⚠️ Aucun message reçu après 2 minutes. Fin du DAG.")
        return message_data

    @task(task_id="ComputCostTravel")
    def compute_cost_travel(message_data: dict | None):
        if not message_data:
            log.info("Aucune donnée à traiter.")
            return None

        comfort_multipliers = {"standard": 1.0, "medium": 1.5, "hight": 2.0}
        client = message_data["properties-client"]
        driver = message_data["properties-driver"]

        distance = haversine_distance(
            client["latitude"], client["logitude"],
            driver["latitude"], driver["logitude"]
        )
        cost = message_data["prix_base_per_km"] * distance * comfort_multipliers.get(message_data["confort"], 1.0)

        message_data["distance_km"] = round(distance, 2)
        message_data["travel_cost"] = round(cost, 2)

        log.info(f"✅ Calcul effectué : distance={distance:.2f} km, coût={cost:.2f} €")
        return message_data

    @task(task_id="PublishKafka")
    def publish_to_kafka_result(message_data: dict | None):
        if not message_data:
            log.info("Aucune donnée à publier.")
            return

        producer = get_kafka_producer()
        producer.send('result', value=message_data)
        producer.flush()
        producer.close()
        log.info(f"📤 Message publié dans 'result' : {message_data}")

    data = consume_from_kafka_source()
    processed = compute_cost_travel(data)
    publish_to_kafka_result(processed)
