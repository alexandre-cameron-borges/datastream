import time
import json
import socket
import random
from kafka import KafkaProducer


def get_kafka_bootstrap():
    """
    Retourne l'adresse du broker Kafka selon l'environnement.
    - Si le host 'kafka' est résolvable, on est dans Docker.
    - Sinon, on utilise localhost:9093 pour l'environnement local.
    """
    try:
        socket.gethostbyname("kafka")
        print("🐳 Environnement Docker détecté — utilisation de kafka:9092")
        return "kafka:9092"
    except socket.gaierror:
        print("💻 Environnement local détecté — utilisation de localhost:9093")
        return "localhost:9093"


producer = KafkaProducer(
    bootstrap_servers=get_kafka_bootstrap(),
    api_version=(3, 3, 1),
    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
)

topic_name = "source"

sample_data = {
    "confort": "standard",
    "prix_base_per_km": 2,
    "properties-client": {
        "logitude": 2.3522,
        "latitude": 48.8566,
        "nomclient": "FALL",
        "telephoneClient": "060786575",
    },
    "properties-driver": {
        "logitude": 3.7038,
        "latitude": 40.4168,
        "nomDriver": "DIOP",
        "telephoneDriver": "0760786575",
    },
}

print("🚗 Démarrage du producteur Kafka... (Ctrl+C pour arrêter)")

try:
    while True:
        data_to_send = json.loads(json.dumps(sample_data))
        data_to_send["properties-client"]["logitude"] += random.uniform(-0.05, 0.05)
        data_to_send["properties-client"]["latitude"] += random.uniform(-0.05, 0.05)
        data_to_send["properties-driver"]["logitude"] += random.uniform(-0.05, 0.05)
        data_to_send["properties-driver"]["latitude"] += random.uniform(-0.05, 0.05)
        data_to_send["confort"] = random.choice(["standard", "medium", "hight"])

        producer.send(topic_name, value=data_to_send)
        print(f"📤 Message envoyé au topic '{topic_name}': {data_to_send}")
        time.sleep(5)

except KeyboardInterrupt:
    print("\n🛑 Arrêt du producteur.")
finally:
    producer.flush()
    producer.close()
