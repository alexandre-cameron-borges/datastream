from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
from kafka import KafkaConsumer, KafkaProducer
import json
import math

# --- Fonctions du pipeline ---

def consume_from_kafka(**context):
    consumer = KafkaConsumer(
        'uber_source',
        bootstrap_servers='localhost:9092',
        auto_offset_reset='earliest',
        group_id='airflow-group',
        value_deserializer=lambda m: json.loads(m.decode('utf-8'))
    )
    for message in consumer:
        context['ti'].xcom_push(key='kafka_message', value=message.value)
        break
    consumer.close()

def compute_cost_travel(**context):
    msg = context['ti'].xcom_pull(key='kafka_message')
    distance = msg.get('distance', 0)
    confort = msg.get('confort', 'standard')

    # Prix par km selon confort
    prix_base = 2 if confort == 'standard' else 3.5

    prix_total = round(distance * prix_base, 2)

    result = {
        "data": [{
            "properties-client": msg.get("properties-client", {}),
            "properties-driver": msg.get("properties-driver", {}),
            "distance": distance,
            "prix_base_per_km": prix_base,
            "confort": confort,
            "prix_travel": prix_total
        }]
    }

    context['ti'].xcom_push(key='result_message', value=result)

def publish_to_kafka(**context):
    producer = KafkaProducer(
        bootstrap_servers='localhost:9092',
        value_serializer=lambda m: json.dumps(m).encode('utf-8')
    )
    result = context['ti'].xcom_pull(key='result_message')
    producer.send('result', value=result)
    producer.flush()
    producer.close()


# --- Définition du DAG ---
default_args = {
    'owner': 'airflow',
    'start_date': datetime(2025, 10, 22),
    'retries': 1
}

with DAG(
    'kafka_dag1_compute_cost',
    default_args=default_args,
    schedule_interval=None,
    catchup=False,
    description='DAG 1: Consomme depuis Kafka (source), calcule le coût du trajet et publie dans Kafka (result)'
) as dag:

    consume_kafka = PythonOperator(
        task_id='ConsumeKafka',
        python_callable=consume_from_kafka
    )

    compute_cost = PythonOperator(
        task_id='ComputCostTravel',
        python_callable=compute_cost_travel
    )

    publish_kafka = PythonOperator(
        task_id='PublishKafka',
        python_callable=publish_to_kafka
    )

    consume_kafka >> compute_cost >> publish_kafka
