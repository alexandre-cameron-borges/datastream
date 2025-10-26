from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
from confluent_kafka import Producer, Consumer, KafkaError

KAFKA_BROKERS = "kafka-1:9092,kafka-2:9092,kafka-3:9092"
TOPIC_SRC = "source"
TOPIC_DST = "result"

def produce_message():
    producer = Producer({"bootstrap.servers": KAFKA_BROKERS})
    for i in range(5):
        message = f"message {i}"
        producer.produce(TOPIC_SRC, value=message)
        print(f"✅ Sent: {message}")
    producer.flush()

def consume_message():
    consumer = Consumer({
        "bootstrap.servers": KAFKA_BROKERS,
        "group.id": "airflow-test",
        "auto.offset.reset": "earliest"
    })
    consumer.subscribe([TOPIC_SRC])
    print("📥 Consuming messages...")
    while True:
        msg = consumer.poll(3.0)
        if msg is None:
            break
        if msg.error():
            if msg.error().code() != KafkaError._PARTITION_EOF:
                print(f"❌ Error: {msg.error()}")
            continue
        print(f"🟢 Received: {msg.value().decode('utf-8')}")
    consumer.close()

with DAG(
    "kafka_test_dag",
    start_date=datetime(2024, 1, 1),
    schedule_interval=None,
    catchup=False,
    tags=["kafka", "test"]
) as dag:

    t1 = PythonOperator(
        task_id="produce_messages",
        python_callable=produce_message
    )

    t2 = PythonOperator(
        task_id="consume_messages",
        python_callable=consume_message
    )

    t1 >> t2
