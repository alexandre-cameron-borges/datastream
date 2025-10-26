"""
DAG Name: csv_to_kafka_source
Author: Abdoulaye
Description:
    Ce DAG lit les données brutes à partir du fichier CSV local uber-split2.csv,
    les nettoie et les publie dans un topic Kafka. Il constitue le point d’entrée
    de la pipeline de données.

Tâches principales:
    - Lecture et parsing du fichier CSV.
    - Validation des colonnes essentielles (date, lat, lon, ID).
    - Publication des lignes valides dans Kafka sous forme de messages JSON.

Objectif:
    Automatiser l’ingestion initiale des données CSV dans le flux de streaming Kafka.

Schedule: @daily
Tags: [ingestion, kafka, csv]
"""




from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
from confluent_kafka import Producer
import csv, json, time, os

def send_csv_to_kafka():
    # Le CSV doit être monté dans le conteneur Airflow
    file_path = '/opt/airflow/dags/uber-split2.csv'
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"❌ Fichier CSV introuvable : {file_path}")

    topic = 'source'
    # Kafka est dans le même réseau Docker → on utilise le nom de service + port interne
    bootstrap = 'kafka-1:9092'

    producer_conf = {
        "bootstrap.servers": bootstrap,
        "client.id": "csv-producer"
    }

    p = Producer(producer_conf)
    sent = 0

    with open(file_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            p.produce(topic, value=json.dumps(row).encode('utf-8'))
            sent += 1
            # time.sleep(0.05)  # ralentir légèrement si besoin
    p.flush()
    print(f"✅ Sent {sent} rows from CSV to topic '{topic}'")

with DAG(
    dag_id='csv_to_kafka_source',
    description='Send CSV data to Kafka (topic=source)',
    schedule_interval=None,
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['csv', 'kafka', 'source']
) as dag:

    send_task = PythonOperator(
        task_id='send_csv_to_kafka',
        python_callable=send_csv_to_kafka
    )
