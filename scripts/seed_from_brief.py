# scripts/seed_from_brief.py
import json, time, uuid, os
from kafka import KafkaProducer

BOOTSTRAP = os.getenv("KAFKA_BROKERS", "broker:9092")
TOPIC = os.getenv("KAFKA_TOPIC_SOURCE", "rides.source")

def normalize(doc):
    c = doc["properties-client"]; d = doc["properties-driver"]
    return {
        "ride_id": str(uuid.uuid4()),
        "timestamp": int(time.time()*1000),
        "comfort": {"standard":"medium","premium":"high"}.get(doc["confort"], doc["confort"]),
        "base_rate_per_km": float(doc["prix_base_per_km"]),
        "latitude": float(c["latitude"]),
        "longitude": float(c["logitude"]),     # <- typo d'origine
        "driver_latitude": float(d["latitude"]),
        "driver_longitude": float(d["logitude"])
    }

if __name__ == "__main__":
    raw = json.load(open("data_projet.json"))
    events = [normalize(x) for x in raw["data"]]
    p = KafkaProducer(bootstrap_servers=BOOTSTRAP,
                      value_serializer=lambda v: json.dumps(v).encode())
    for e in events:
        p.send(TOPIC, e)
    p.flush()
    print(f"Sent {len(events)} seed event(s) to {TOPIC}")
