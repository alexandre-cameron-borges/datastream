from kafka import KafkaProducer
import json
import time
import random

# Connexion au serveur Kafka
producer = KafkaProducer(
    bootstrap_servers=['127.0.0.1:9092'],
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

comfort_levels = ['Low', 'Medium', 'High']

def generate_ride():
    """Simule un trajet Uber"""
    return {
        "ride_id": random.randint(1000, 9999),
        "client_lat": round(random.uniform(48.80, 48.90), 6),
        "client_long": round(random.uniform(2.30, 2.40), 6),
        "driver_lat": round(random.uniform(48.80, 48.90), 6),
        "driver_long": round(random.uniform(2.30, 2.40), 6),
        "comfort": random.choice(comfort_levels),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }

topic = 'uber_source'

while True:
    data = generate_ride()
    producer.send(topic, value=data)
    print(f"✅ Donnée envoyée : {data}")
    time.sleep(2)
