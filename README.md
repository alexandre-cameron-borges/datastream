# Big Data Streaming — Taxi Pricing & Real-Time Analytics

![Status](https://img.shields.io/badge/status-MVP-green) ![Kafka](https://img.shields.io/badge/stream-Kafka-black) ![Airflow](https://img.shields.io/badge/orchestrator-Airflow-blue) ![Elastic](https://img.shields.io/badge/search-Elasticsearch-005571) ![Kibana](https://img.shields.io/badge/viz-Kibana-3a3) ![GCP](https://img.shields.io/badge/datalake-GCS-1a73e8) ![BigQuery](https://img.shields.io/badge/warehouse-BigQuery-1a73e8)

> Backend temps réel pour calculer la **distance** chauffeur-client, **tarifer** selon le **confort**, **visualiser** dans Kibana, et **analyser/clusteriser** dans BigQuery ML (k-means k=8). Exigences issues du brief de projet.

---

## 1) Objectifs

- **Ingestion** d’événements taxi → Kafka.  
- **DAG1 Airflow** : consommer `source` → calcul du **coût** → publier sur `result`.  
- **DAG2 Airflow** : consommer `result` → **flatten JSON** + `agent_timestamp` → **Elasticsearch** + **GCS**.  
- **DWH** : table **External BigQuery** pointant vers GCS.  
- **ML** : **KMeans k=8** sur `longitude, latitude` via le CSV client.  
- **BI temps réel** : **CA par cluster et par confort** à partir du Data Lake.

---

## 2) Architecture (vue d’ensemble)

```
[Producer] --> Kafka(topic: source) --> Airflow DAG1 --> Kafka(topic: result) --> Airflow DAG2
                                                     |                                    |
                                                     v                                    v
                                             Price computation                    {Flatten + agent_timestamp}
                                                                                        |         |
                                                                                Elasticsearch     GCS (JSON)
                                                                                     |                 |
                                                                                  Kibana        BigQuery External
                                                                                                      |
                                                                                           BQML KMeans (k=8)
                                                                                                      |
                                                                                         Revenue by cluster x comfort
```

**Pile technique** : Python producer, Kafka, Airflow, Elasticsearch, Kibana, GCS, BigQuery ML.

---

## 3) Modèle de données (entrée Kafka)

- Aligné sur `data_projet.json` (cf. modèle fourni dans le brief).  
- Champs minimaux (ex.) : `ride_id`, `driver_id`, `client_id`, `latitude`, `longitude`, `comfort`, `timestamp`, etc.  
- Sortie **DAG1** : ajoute `distance_km`, `price`.  
- Sortie **DAG2** : JSON **aplati** + `agent_timestamp` pour l’indexation et le time-slicing Kibana.

---

## 4) Dossiers & fichiers

```
.
├─ infra/                     # Docker Compose: Kafka(+UI), ES, Kibana, Airflow
│  ├─ docker-compose.yml
│  └─ kafka/create-topics.sh  # rides.source, rides.result
├─ airflow/dags/
│  ├─ dag_compute_cost.py     # DAG1: source -> compute -> result
│  └─ dag_index_gcs_es.py     # DAG2: result -> flatten+ts -> ES + GCS
├─ apps/producer/producer.py  # Générateur d’événements
├─ kibana/dashboards.ndjson   # Exports Discover/Dashboard
├─ sql/
│  ├─ bq_external_table.sql   # External table sur GCS
│  ├─ bqml_kmeans.sql         # Modèle KMeans k=8 (lon, lat)
│  └─ bq_revenue_mv.sql       # Revenu par cluster x confort
├─ .env.example
└─ README.md
```

---

## 5) Démarrage rapide

1) **Pré-requis**  
- Docker / Docker Compose  
- Projet **GCP** + **Service Account** avec accès GCS & BigQuery  
- Variables `.env` (copier depuis `.env.example`)

2) **Lancer l’infra**  
```bash
cp .env.example .env
docker compose -f infra/docker-compose.yml up -d
bash infra/kafka/create-topics.sh
```

3) **Airflow**  
- Ouvre `http://localhost:8080`, active : `dag_compute_cost`, `dag_index_gcs_es`.

4) **Générer des événements**  
```bash
python apps/producer/producer.py --n 1000 --rate 100  # ex: 1000 events à 100 ev/s
```

5) **Kibana**  
- `http://localhost:5601` → **importe** `kibana/dashboards.ndjson` → vérifie Discover + dashboard.

6) **BigQuery / ML**  
- Crée **External Table** pointant sur le bucket GCS.  
- Charge le CSV client (`uber-split2.csv`) et entraîne **KMeans(k=8)** sur `longitude, latitude`.  
- Calcule le **CA par cluster & confort** (vue matérialisée ou table d’agrégation).

---

## 6) Business Logic (pricing)

- **Distance** : haversine (ou équivalent) à partir de la position **chauffeur ↔ client**.  
- **Tarif** : `price = base + km * rate * comfort_multiplier`  
  - `comfort ∈ {low, medium, high}` (ou équivalents), multiplicateurs documentés dans le DAG1.  
- **Timestamps** : conserver l’horodatage événement + `agent_timestamp` (traitement).

---

## 7) BigQuery ML — KMeans(k=8)

- **Données** : CSV client fourni (`uber-split2.csv`).  
- **Features** : `longitude`, `latitude`. **k=8** imposé par le brief.  
- **Usage** :  
  1) External table sur GCS (événements enrichis),  
  2) Table externe/ingérée sur le CSV client,  
  3) `CREATE MODEL … OPTIONS(model_type='kmeans', num_clusters=8)`,  
  4) `ML.PREDICT` pour attribuer un **cluster_id** à chaque ride (selon coordonnées client),  
  5) Agréger **SUM(price)** par `cluster_id × comfort` (fenêtre minute/heure) pour le **CA temps réel**.

---

## 8) Tableaux de bord Kibana

- **Discover** : inspection rapide des documents indexés (filtre par `agent_timestamp`, `comfort`, `price`).  
- **Dashboard** : tuiles clés (volumétrie d’événements, prix moyen, CA par confort, CA par cluster). Exigence : fournir un **exemple**.

---

## 9) Architecture Kafka recommandée (à justifier dans le rendu)

| Contexte     | Brokers | Partitions/topic (`source`,`result`) | RF | Disque/broker | Rétention | Monitoring |
|---|---:|---:|---:|---|---|---|
| Dev local    | 1       | 2–3                                 | 1  | 50–100 GB     | 24–72 h   | Kafka-UI   |
| PoC/Pré-prod | 3       | 4–6                                 | 3  | 2×1 TB NVMe   | 7–14 j    | Kafka-UI + JMX/Prom + Grafana (+Burrow) |

> Le brief demande de **proposer** : nb de brokers, disques, nb de partitions par topic, outils de monitoring.

---

## 10) Qualité, Observabilité & Tests

- **Qualité** : schéma JSON validé (pydantic / jsonschema), tests unitaires prix/distance.  
- **Observabilité** : logs structurés; métriques Airflow; lags Kafka; index health Elasticsearch.  
- **Tests rapides** :  
  - Producer → Kafka OK,  
  - DAG1 → record `result` enrichi,  
  - DAG2 → doc indexé + fichier GCS,  
  - BQ External lisible,  
  - KMeans entraîné (k=8),  
  - Vue CA renvoie des lignes.

---

## 11) Variables d’environnement (exemple)

```
KAFKA_BROKERS=broker:9092
KAFKA_TOPIC_SOURCE=rides.source
KAFKA_TOPIC_RESULT=rides.result
ES_HOST=http://elasticsearch:9200
GCP_PROJECT=your-project
GCS_BUCKET=your-bucket
BQ_DATASET=taxi
```

---

## 12) Livrables attendus

- **Code + DAGs** Airflow, **script topics**, **dashboards Kibana**, **SQL** (External, KMeans, revenue) et **README**.

---

## 13) Dépannage (FAQ)

- **Pas de docs dans ES** : vérifier `dag_index_gcs_es.py`, mapping index, droits ES.  
- **BQ External vide** : chemin GCS, format JSON, droits SA.  
- **KMeans échoue** : types numériques (CAST lon/lat → FLOAT64), valeurs manquantes.  
- **Lags Kafka** : partitions insuffisantes ou consumer trop lent → augmenter partitions/threads.

---

### Licence
Usage académique.
