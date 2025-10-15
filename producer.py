#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Producer Kafka pour le projet Taxi Streaming.
- Mode 1 (par défaut) : génère des événements aléatoires proches de Paris.
- Mode 2 (--from-brief) : normalise et envoie les lignes de data_projet.json.
Sortie : topic Kafka (par défaut rides.source) avec un JSON par message.
"""
import argparse, json, os, random, time, uuid, sys
from typing import Dict, Iterable, List

try:
    from kafka import KafkaProducer
except Exception as e:
    print("ERREUR: Le module 'kafka' est introuvable. Installe : pip install kafka-python", file=sys.stderr)
    raise

# --------------------------
# Helpers / modèles de données
# --------------------------
COMFORT_VALUES = ["low", "medium", "high"]

def now_ms() -> int:
    return int(time.time() * 1000)

def rand_coord_around(lat0: float, lon0: float, max_delta_deg: float = 0.02):
    """Retourne (lat, lon) ~ autour d'un point de référence."""
    return (
        lat0 + random.uniform(-max_delta_deg, max_delta_deg),
        lon0 + random.uniform(-max_delta_deg, max_delta_deg),
    )

def make_random_event() -> Dict:
    """
    Événement standard pour DAG1 (distance/pricing) & DAG2 (flatten+timestamp).
    - Client proche de Paris (48.8566, 2.3522)
    - Driver ~ à quelques centaines de mètres
    """
    base_lat, base_lon = 48.8566, 2.3522  # Paris
    lat, lon = rand_coord_around(base_lat, base_lon, 0.03)
    dlat, dlon = rand_coord_around(lat, lon, 0.02)

    comfort = random.choices(COMFORT_VALUES, weights=[0.3, 0.5, 0.2], k=1)[0]
    base_rate_per_km = round(random.uniform(1.1, 2.9), 2)

    return {
        "ride_id": str(uuid.uuid4()),
        "timestamp": now_ms(),                 # horodatage événement (ms epoch)
        "comfort": comfort,                    # low | medium | high
        "base_rate_per_km": base_rate_per_km,  # tarif de base par km
        "latitude": round(lat, 6),             # client
        "longitude": round(lon, 6),
        "driver_latitude": round(dlat, 6),     # chauffeur
        "driver_longitude": round(dlon, 6),
    }

def normalize_from_brief(doc: Dict) -> Dict:
    """
    Normalise 1 entrée du fichier 'data_projet.json' (brief).
    Hypothèses clés du brief: champs properties-client/logitude (typo) etc.
    """
    c = doc.get("properties-client", {})
    d = doc.get("properties-driver", {})

    # Map confort -> comfort
    confort = (doc.get("confort") or "").lower().strip()
    confort_map = {"standard": "medium", "premium": "high", "low": "low", "medium": "medium", "high": "high"}
    comfort = confort_map.get(confort, "medium")

    # Typos du brief : 'logitude' -> longitude
    def safe_float(x, default=0.0):
        try:
            return float(x)
        except Exception:
            return default

    base_rate_per_km = safe_float(doc.get("prix_base_per_km", 2.0), 2.0)
    lat = safe_float(c.get("latitude"))
    lon = safe_float(c.get("logitude") or c.get("longitude"))
    dlat = safe_float(d.get("latitude"))
    dlon = safe_float(d.get("logitude") or d.get("longitude"))

    # Si le brief n'a pas toutes les coords, fallback sur random
    if not (lat and lon and dlat and dlon):
        e = make_random_event()
        e["comfort"] = comfort
        e["base_rate_per_km"] = base_rate_per_km
        return e

    return {
        "ride_id": str(uuid.uuid4()),
        "timestamp": now_ms(),
        "comfort": comfort,
        "base_rate_per_km": round(base_rate_per_km, 2),
        "latitude": round(lat, 6),
        "longitude": round(lon, 6),
        "driver_latitude": round(dlat, 6),
        "driver_longitude": round(dlon, 6),
    }

def iter_from_brief(path: str) -> Iterable[Dict]:
    data = json.load(open(path, "r", encoding="utf-8"))
    # Supporte deux formats: {"data":[...]} ou liste directe [...]
    rows: List[Dict] = data["data"] if isinstance(data, dict) and "data" in data else data
    for doc in rows:
        yield normalize_from_brief(doc)

# --------------------------
# Envoi Kafka
# --------------------------
def new_producer(servers: str) -> KafkaProducer:
    return KafkaProducer(
        bootstrap_servers=[s.strip() for s in servers.split(",") if s.strip()],
        value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode("utf-8"),
        linger_ms=50, acks="all", retries=10, max_in_flight_requests_per_connection=1
    )

def main():
    parser = argparse.ArgumentParser(description="Producer Kafka - Taxi Streaming")
    parser.add_argument("--brokers", default=os.getenv("KAFKA_BROKERS", "localhost:9092"),
                        help="Bootstrap servers (ex: localhost:9092 ou broker:9092)")
    parser.add_argument("--topic", default=os.getenv("KAFKA_TOPIC_SOURCE", "rides.source"),
                        help="Topic Kafka cible")
    parser.add_argument("--n", type=int, default=300, help="Nombre total d'événements à envoyer")
    parser.add_argument("--rate", type=int, default=100, help="Débit approx. (événements/seconde)")
    parser.add_argument("--from-brief", dest="brief", default=None,
                        help="Chemin d'un data_projet.json pour envoyer des événements normalisés")
    parser.add_argument("--seed", type=int, default=None, help="Graine RNG (reproductibilité)")
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    producer = new_producer(args.brokers)
    topic = args.topic

    # Générateur de messages
    if args.brief:
        src_iter = iter_from_brief(args.brief)
    else:
        def gen():
            while True:
                yield make_random_event()
        src_iter = gen()

    # Throttling simple (rate events/s)
    delay = 1.0 / max(1, args.rate)
    sent = 0
    try:
        for msg in src_iter:
            producer.send(topic, msg)
            sent += 1
            if sent % max(1, args.rate) == 0:
                # flush périodique pour la latence
                producer.flush()
            if args.brief:
                # mode brief : on ne dépasse pas args.n si la source est finie
                if sent >= args.n:
                    break
            else:
                if sent >= args.n:
                    break
            time.sleep(delay)
    except KeyboardInterrupt:
        pass
    finally:
        producer.flush()
        producer.close()
        print(f"[producer] Envoyé {sent} message(s) sur '{topic}' via {args.brokers}")

if __name__ == "__main__":
    main()

