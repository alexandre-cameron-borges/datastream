from airflow.decorators import dag, task
from datetime import datetime
import math, os, json

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0; p = math.pi/180
    a = 0.5 - math.cos((lat2-lat1)*p)/2 + math.cos(lat1*p)*math.cos(lat2*p)*(1-math.cos((lon2-lon1)*p))/2
    return 2*R*math.asin(math.sqrt(a))

@dag(
    dag_id="dag_compute_cost",
    start_date=datetime(2024, 1, 1),
    schedule=None, catchup=False,
    description="Consomme rides.source, calcule distance/prix, publie sur rides.result"
)
def compute_cost():
    @task
    def consume_source():
        from kafka import KafkaConsumer
        brokers = os.getenv("KAFKA_BROKERS","broker:9092")
        topic = os.getenv("KAFKA_TOPIC_SOURCE","rides.source")
        c = KafkaConsumer(topic, bootstrap_servers=brokers,
                          value_deserializer=lambda v: json.loads(v.decode()))
        msg = next(c)  # MVP: lit 1 message
        return msg.value

    @task
    def compute(payload: dict):
        # Ex: payload contient latitude/longitude du client + du driver si dispo
        lat1 = float(payload.get("driver_lat", payload["latitude"]))
        lon1 = float(payload.get("driver_lon", payload["longitude"]))
        lat2 = float(payload["latitude"]); lon2 = float(payload["longitude"])
        dist = haversine_km(lat1, lon1, lat2, lon2)
        comfort_mult = {"low":1.0,"medium":1.2,"high":1.5}.get(payload.get("comfort","medium"),1.2)
        price = round(2.0 + dist * 1.2 * comfort_mult, 2)
        payload.update({"distance_km": round(dist,3), "price": price})
        return payload

    @task
    def publish_result(enriched: dict):
        from kafka import KafkaProducer
        brokers = os.getenv("KAFKA_BROKERS","broker:9092")
        topic = os.getenv("KAFKA_TOPIC_RESULT","rides.result")
        p = KafkaProducer(bootstrap_servers=brokers,
                          value_serializer=lambda v: json.dumps(v).encode())
        p.send(topic, enriched); p.flush()

    publish_result(compute(consume_source()))

compute_cost()
