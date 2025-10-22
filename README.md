# Big Data Streaming — Taxi Pricing & Real-Time Analytics

![Status](https://img.shields.io/badge/status-MVP-green) ![Kafka](https://img.shields.io/badge/stream-Kafka-black) ![Airflow](https://img.shields.io/badge/orchestrator-Airflow-blue) ![Elastic](https://img.shields.io/badge/search-Elasticsearch-005571) ![Kibana](https://img.shields.io/badge/viz-Kibana-3a3) ![GCP](https://img.shields.io/badge/datalake-GCS-1a73e8) ![BigQuery](https://img.shields.io/badge/warehouse-BigQuery-1a73e8)

> Backend temps réel pour calculer la **distance** chauffeur–client, **tarifer** selon le **confort**, **visualiser** dans Kibana, et **analyser/clusteriser** dans BigQuery ML (**k-means k=8**). 
---

## 1) Objectifs

- **Ingestion** d’événements taxi → Kafka  
- **DAG1 Airflow** : consommer `source` → calcul **distance/prix** → publier sur `result`  
- **DAG2 Airflow** : consommer `result` → **flatten JSON** + `agent_timestamp` → **Elasticsearch** + **GCS**  
- **DWH** : **External Table BigQuery** pointant vers GCS  
- **ML** : **KMeans k=8** sur `longitude, latitude` (CSV client)  
- **BI temps réel** : **CA par cluster × confort** depuis le Data Lake

---

## 2) Architecture (vue d’ensemble)

```
[Producer] -> Kafka (topic: source) -> Airflow DAG1 -> Kafka (topic: result) -> Airflow DAG2
                                               |                                    |
                                               v                                    v
                                       Price computation                    {Flatten + agent_timestamp}
                                                                                  |           |
                                                                           Elasticsearch       GCS (JSON)
                                                                                |                 |
                                                                             Kibana        BigQuery External
                                                                                                   |
                                                                                        BQML KMeans (k=8)
                                                                                                   |
                                                                                  Revenue by cluster × comfort
```

**Pile technique** : Python, Kafka, Airflow, Elasticsearch, Kibana, GCS, BigQuery ML.

---

## 3) Modèle de données (entrée Kafka)

- Aligné sur `data_projet.json` (brief)  
- Champs minimaux (ex.) : `ride_id`, `driver_id`, `client_id`, `latitude`, `longitude`, `comfort`, `timestamp`  
- Sortie **DAG1** : `distance_km`, `price`  
- Sortie **DAG2** : JSON **aplati** + `agent_timestamp` (indexation & time-slicing Kibana)

---

## 4) Dossiers & fichiers

```
.
├─ infra/                         # Docker Compose: Kafka(+UI), ES, Kibana, Airflow
│  ├─ docker-compose.yml
│  └─ kafka-create-topics.sh      # rides.source, rides.result
├─ airflow/
│  └─ dags/
│     ├─ dag_compute_cost.py      # DAG1: source -> compute -> result
│     └─ dag_index_gcs_es.py      # DAG2: result -> flatten+ts -> ES + GCS
├─ producer.py                    # Générateur d’événements
├─ kibanadashboards.ndjson        # Export Kibana (Discover/Dashboard)
├─ sql/
│  ├─ bq_external_table.sql       # External table sur GCS
│  ├─ bqml_kmeans.sql             # Modèle KMeans k=8 (lon, lat)
│  └─ bq_revenue_mv.sql           # Revenu par cluster × confort
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
```

3) **Créer les topics**
```bash
chmod +x infra/kafka-create-topics.sh
BROKER=broker:9092 PARTITIONS=3 REPLICATION=1 TOPICS="rides.source rides.result" ./infra/kafka-create-topics.sh
```

4) **Airflow**
- Ouvre `http://localhost:8080`, active : `dag_compute_cost`, `dag_index_gcs_es`

5) **Générer des événements**
```bash
python producer.py --n 1000 --rate 100    # ex: 1000 events à 100 ev/s
```

6) **Kibana**
- `http://localhost:5601` → *Stack Management* → *Saved Objects* → **Import** → `kibanadashboards.ndjson`

7) **BigQuery / ML**
- Crée **External Table** pointant sur le bucket GCS  
- Charge le CSV client (`uber.csv`) et entraîne **KMeans(k=8)** sur `longitude, latitude`  
- Calcule le **CA par cluster × confort** (vue matérialisée / table d’agrégation)

---

## 6) Business Logic (pricing)

- **Distance** : haversine (ou équivalent) chauffeur ↔ client  
- **Tarif** : `price = base + km * rate * comfort_multiplier`  
  - `comfort ∈ {low, medium, high}` (multiplicateurs définis dans **DAG1**)  
- **Horodatage** : conserver `timestamp` source + `agent_timestamp` (traitement)

---

## 7) BigQuery ML — KMeans (k=8)

- **Données** : CSV client `uber-split2.csv`  
- **Features** : `longitude`, `latitude` (k=8 imposé)  
- **Pipeline** :
  1. External table GCS (événements enrichis)  
  2. Table externe/ingérée du CSV client  
  3. `CREATE MODEL … OPTIONS(model_type='kmeans', num_clusters=8)`  
  4. `ML.PREDICT` → attribution `cluster_id` par ride  
  5. Agrégation **SUM(price)** par `cluster_id × confort` (fenêtre minute/heure)

---

## 8) Tableaux de bord Kibana

- **Discover** : filtres `agent_timestamp`, `comfort`, `price`  
- **Dashboard** : volumétrie, prix moyen, **CA par confort**, **CA par cluster** (exemple fourni via `kibanadashboards.ndjson`)

---

## 9) Architecture Kafka (recommandation)

| Contexte     | Brokers | Partitions/topic (`source`,`result`) | RF | Disque/broker | Rétention | Monitoring |
|---|---:|---:|---:|---|---|---|
| Dev local    | 1       | 2–3                                 | 1  | 50–100 GB     | 24–72 h   | Kafka-UI   |
| PoC/Pré-prod | 3       | 4–6                                 | 3  | 2×1 TB NVMe   | 7–14 j    | Kafka-UI + JMX/Prom + Grafana (+Burrow) |

> À justifier : nb de brokers, disques, nb de partitions par topic, outils de monitoring.

---

## 10) Qualité, Observabilité & Tests

- **Qualité** : validation schéma (pydantic/jsonschema), tests unitaires distance/prix  
- **Observabilité** : logs structurés; métriques Airflow; lags Kafka; health Elasticsearch  
- **Smoke tests** :
  - Producer → Kafka OK  
  - **DAG1** → message `result` enrichi  
  - **DAG2** → doc indexé + fichier GCS  
  - External Table BQ lisible  
  - KMeans (k=8) entraîné  
  - Vue **CA** retourne des lignes

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

- **Code + DAGs** Airflow, **script topics**, **dashboards Kibana**, **SQL** (External, KMeans, revenue), **README**

---

## 13) Dépannage (FAQ)

- **Pas de docs dans ES** : vérifier `dag_index_gcs_es.py`, mapping index, droits ES  
- **BQ External vide** : chemin GCS, format JSON, droits du service account  
- **KMeans échoue** : caster lon/lat en `FLOAT64`, gérer valeurs manquantes  
- **Lags Kafka** : partitions insuffisantes ou consumer lent → augmenter partitions/threads

---

### Licence
Usage académique.
