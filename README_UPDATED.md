# MOSEF 2025 — Datastream Backend (POC → Cloud-Ready)
> Backend temps réel pour calculer la distance chauffeur↔client, déduire le prix selon confort, indexer/visualiser (Kibana) et alimenter un DWH (BigQuery) pour ML en quasi temps réel. 

Sources & exigences: projet v2 (PDF) — deux DAG Airflow, ES + Kibana, GCS + BigQuery, clustering KMeans (8 clusters), revenus par cluster & confort. 


---

## 0) TL;DR (Local Quickstart)
1) **Prérequis**: Docker Desktop + Compose, Python 3.10+, Git. 

2) **Clone**: `git clone <URL> && cd datastream` 

3) **Infra**: compléter `infra/.env` (copier depuis `.env.example`) → `docker compose -f infra/docker-compose.yml up -d` 

4) **Kafka**: créer topics `rides_raw`, `rides_result`, `rides_dlq` (Kafka-UI). 

5) **Producer**: `pip install -r producer/requirements.txt && python producer/producer.py` (events JSON → `rides_raw`). 

6) **Airflow**: http://localhost:8081 (admin/admin) → activer `dag_compute_cost` puis `dag_index_and_export`. 

7) **Kibana**: http://localhost:5601 → index pattern `rides*` (dashboards de base). 


---

## 1) Architecture cible (POC → Cloud)
```
Producer(JSON) → Kafka (rides_raw)
   └─ DAG#1 (ComputeCostTravel) → Kafka (rides_result)
        └─ DAG#2 (TransformJSON + Index + Export)
                ├─ Elasticsearch → Kibana (Discover + Dashboards)
                └─ GCS (Parquet/JSON) → BigQuery (external table + BQML)
```
- **Backend Core**: Python producer → Kafka → Airflow → ES/Kibana. 

- **Data Lake/DWH**: GCS (stockage) + BigQuery (requêtes & ML). 


---

## 2) Structure du repo (simplifiée & alignée v2)
```
datastream/
├─ infra/                  # Docker & config locale
│  ├─ .env.example
│  └─ docker-compose.yml
├─ airflow/
│  ├─ dags/
│  │  ├─ dag_compute_cost.py        # DAG#1: consume raw → compute → publish result
│  │  └─ dag_index_and_export.py    # DAG#2: consume result → flatten+timestamp → ES + GCS
│  └─ plugins/
│     ├─ operators/
│     │  ├─ compute_cost_operator.py    # “ComputCostTravel”
│     │  └─ transform_json_operator.py  # “TransformJSON” (+ agent_timestamp)
│     └─ hooks/ (si besoin: Kafka/ES/GCS personnalisés)
├─ jobs/                    # Scripts Spark/Python (enrichissement, batch export)
│  └─ spark_enrich.py
├─ producer/
│  ├─ producer.py
│  └─ requirements.txt
├─ docs/
│  ├─ runbook_kafka.md         # création topics, DLQ
│  ├─ dashboards_kibana.md     # captures & saved objects (JSON)
│  └─ bqml_playbook.md         # recettes BigQuery ML (kmeans + revenues)
├─ .gitignore
└─ README.md
```
> On réintroduit **plugins/** (opérateurs custom) pour coller au besoin “ComputeCostTravel” + “TransformJSON”. Les **logs** et **data** ne sont pas versionnés. 


---

## 3) Modèle de données (Kafka)
- **Topic source** `rides_raw` (JSON minimal stable): 

  - `ride_id: uuid`, `ts: ISO-8601 UTC` 

  - `origin.lat, origin.lon`, `destination.lat, destination.lon` 

  - `comfort: low|medium|high` (alias eco/comfort/business si besoin) 

  - `duration_min`, `price_base`, `price_per_km`, `price_per_min` 

- **Topic résultat** `rides_result`: champs précédents **+**: 

  - `distance_km: double`, `price_total: double` 

- **Règles**: schéma strict, champs inconnus ignorés, JSON invalide → `rides_dlq`. 


---

## 4) Airflow — DAGs & connexions
### Connexions & Variables
- `kafka_local`: `kafka://kafka:9092` 

- `es_local`: `http://elastic:changeme@elasticsearch:9200` 

- `gcp_default`: clé GCP montée dans le conteneur (ou Secret Manager). 

- Variables: `RAW_TOPIC=rides_raw`, `RESULT_TOPIC=rides_result`, `DLQ_TOPIC=rides_dlq`, `GCS_BUCKET=<bucket>`, `GCS_PREFIX=rides/processed/` 


### DAG#1 — `dag_compute_cost.py`
- **Tasks**: `ConsumeKafka` → `ComputeCostTravel` → `PublishKafka`. 

- **Logique**: 

  - Distance (approx) `haversine` ou `geodesic` (km). 

  - `price_total = base + km*price_per_km + min*price_per_min`. 

- **Sortie**: push JSON vers `rides_result`. 


### DAG#2 — `dag_index_and_export.py`
- **Tasks**: `ConsumeKafka` → `TransformJSON` (flatten + `agent_timestamp`) → `PutElasticSearch` + `PutGCP`. 

- **ES**: index `rides` (template simple, date_nanos si besoin). 

- **GCS**: écrire fichiers **Parquet** (recommandé) partitionnés par date (`YYYY/MM/DD/HH`). 


---

## 5) Kibana — Discover & Dashboards
- **Index pattern**: `rides*`. 

- **Visualisations**: 

  - Volume/minute, `avg(distance_km)`, `avg(price_total)`, distribution par `comfort`. 

  - Carto (tile map) si on indexe geo-point (`origin`, `destination`). 

- **Dashboards**: importer les saved objects (JSON) depuis `docs/dashboards_kibana.md`. 


---

## 6) GCP & BigQuery (hors repo, playbook inclus)
### 6.1 External Table sur GCS
- GCS: `gs://<bucket>/rides/processed/` (Parquet partitionné). 

- BQ: dataset `rides`; external table `rides_processed_ext` (format Parquet, autodetect schema). 


### 6.2 BigQuery ML — KMeans (8 clusters)
- **Dataset d’amorçage**: `uber-split2.csv` déposé dans `gs://<bucket>/reference/uber-split2.csv`. 

- **Modèle**: `CREATE OR REPLACE MODEL rides.kmeans8 OPTIONS(MODEL_TYPE='KMEANS', NUM_CLUSTERS=8) AS SELECT longitude, latitude FROM rides.reference_uber;` 


### 6.3 Revenus en temps (quasi) réel par cluster & confort
- **Feature assignation**: `ML.PREDICT(rides.kmeans8, SELECT longitude, latitude FROM rides_processed_ext)` pour attribuer `cluster_id`. 

- **Agrégat**: `SELECT cluster_id, comfort, SUM(price_total) AS revenue, COUNT(*) AS n FROM (...) GROUP BY 1,2 ORDER BY revenue DESC;` 


> Alternative: matérialiser une table partitionnée **native** BQ depuis GCS (LOAD/STREAM) pour réduire latence de requêtes. 


---

## 7) Observabilité & Qualité
- **DLQ**: `rides_dlq` + métriques Airflow. 

- **Logs**: Airflow + containers; corrélation via `ride_id`. 

- **Tests**: smoke test de volume (`raw` vs `result`), valide schema. 


---

## 8) Sécurité & CI/CD (roadmap)
- **POC**: dev passwords, pas de TLS. 

- **Prod**: TLS Kafka/ES, RBAC Airflow, GitHub Actions (lint/tests), IaC (Terraform GCP), secrets vault. 


---

## 9) Sizing & Monitoring Kafka (proposition)
- **Brokers**: 3 (HA minimale). 

- **Stockage**: 2× NVMe par broker, 1–2 To/broker (retenue 7–14 jours selon débit). 

- **Partitions**: `rides_*` → 6–12 (dépend du débit; viser 50–100k msg/s -> ajuster). 

- **Monitoring**: Prometheus + Grafana + Kafka Exporter, Alerting (lag consumer, ISR, under-replicated). 


---

## 10) Dépannage rapide
- **DAGs invisibles**: mauvais volume/montage; désactiver samples Airflow. 

- **ES non indexé**: mapping incompatible; revalider types (`double`, `date`). 

- **Export GCS**: droits SA manquants; vérifier `GOOGLE_APPLICATION_CREDENTIALS` et ACL bucket. 

- **Skew**: messages “gros” → compaction ou compression; revoir batch size producteurs/consumers. 


---

## Annexes
- `.env.example` (extrait): ports Kafka/UI/ES/Kibana/Airflow; mots de passe dev; bucket GCS. 

- `docs/runbook_kafka.md`: commandes pour topics + DLQ, schémas. 

- `docs/bqml_playbook.md`: pas-à-pas BQ (external table, KMeans, revenue). 


---
