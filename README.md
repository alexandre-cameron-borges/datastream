# Datastream (POC) — Kafka → Airflow → Spark → Elasticsearch/Kibana

> Pipeline évènementiel simple pour démontrer ingestion, enrichissement et recherche/visualisation.

---

## 🚀 TL;DR (Quickstart local)
1) **Prérequis**: Docker Desktop + Compose, Python 3.10+, Git.  
2) **Clone**: `git clone <URL> && cd datastream`  
3) **Infra**: copier `infra/.env.example` → `infra/.env`, puis  
   `docker compose -f infra/docker-compose.yml up -d`  
4) **Topics**: créer `rides_raw` & `rides_processed` (Kafka-UI ou script).  
5) **Producteur**:  
   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -r producer/requirements.txt
   python producer/producer.py
   ```
6) **Airflow UI**: http://localhost:8081 (admin/admin) → activer `rides_enrichment`, `es_sync`.  
7) **Kibana**: http://localhost:5601 → index pattern `rides*`.

---

## 🗂️ Structure du repo (minimaliste)
```
datastream/
├─ infra/                 # Docker & config (Kafka, ES, Kibana, Airflow)
│  ├─ .env.example
│  └─ docker-compose.yml
├─ airflow/
│  └─ dags/               # DAGs Airflow (Python)
├─ jobs/                  # Scripts Spark/Python appelés par Airflow
├─ producer/              # Générateur d’événements Kafka
├─ docs/                  # Guides (runbooks, schémas)
├─ .gitignore
└─ README.md
```

**.gitignore** (extrait recommandé) :
```
__pycache__/
*.pyc
*.log
.venv/
infra/.env
airflow/logs/
infra/datastream-sa-key.json
```

---

## 🧠 Architecture (vue d’ensemble)
```
Producer(JSON) → Kafka (rides_raw)
      └─(Airflow DAG)→ Spark enrichit → rides_processed
                         └─(Airflow DAG)→ Elasticsearch → Kibana
```
**Option cloud (plus tard)** : Kafka → GCS (Parquet) → BigQuery/ES.

---

## 📜 Contrat de données (Data Contract)

**Topic source** `rides_raw` (JSON minimal stable) :
```json
{
  "ride_id": "uuid",
  "ts": "ISO-8601 UTC",
  "origin": {"lat": 48.85, "lon": 2.35},
  "destination": {"lat": 48.90, "lon": 2.31},
  "comfort": "eco|comfort|business",
  "duration_min": 12,
  "price_base": 3.2,
  "price_per_km": 1.2,
  "price_per_min": 0.25
}
```
**Sortie** `rides_processed` (ajouts) :
- `distance_km: double (>=0)`  
- `price_total: double = base + km*price_per_km + min*price_per_min`  

**Règles** : champs ci-dessus **obligatoires** ; champs inconnus ignorés ; JSON invalide → **DLQ** (à ajouter).

---

## ⚙️ Déploiement local — pas à pas

### 1) Infra Docker
- Copier `infra/.env.example` → `infra/.env` (exemple) :
  ```env
  # Kafka
  KAFKA_BROKER_ID=1
  KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://kafka:9092,PLAINTEXT_HOST://localhost:29092
  KAFKA_LISTENERS=PLAINTEXT://kafka:9092,PLAINTEXT_HOST://0.0.0.0:29092
  KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR=1
  # Elasticsearch/Kibana
  ES_VERSION=8.14.3
  ELASTIC_PASSWORD=changeme
  # Airflow
  AIRFLOW_USER=admin
  AIRFLOW_PASSWORD=admin
  ```
- Lancer :
  ```bash
  docker compose -f infra/docker-compose.yml up -d
  ```
- Vérifs rapides :  
  Kafka-UI: http://localhost:8080 • Kibana: http://5601 • Airflow: http://8081

### 2) Topics Kafka
- Créer `rides_raw`, `rides_processed` via Kafka-UI ou script (docs/Runbook).

### 3) Producteur (échantillonnage de données)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r producer/requirements.txt
python producer/producer.py
```
→ Messages visibles dans Kafka-UI (topic `rides_raw`).

### 4) Airflow (DAGs)
- UI: http://localhost:8081 (admin/admin)  
- **Connections** : `kafka_local` (kafka:9092), `es_local` (http://elastic:changeme@elasticsearch:9200)  
- **Variables** : `KAFKA_TOPIC_RAW=rides_raw`, `KAFKA_TOPIC_PROCESSED=rides_processed`  
- Activer les DAGs : `rides_enrichment` → `es_sync`.

### 5) Kibana (visualisation)
- Créer **index pattern** `rides*`.  
- Graphs de base : volume d’événements, `avg(distance_km)`, `avg(price_total)` par minute.

---

## 🔍 Observabilité & Qualité (POC)
- **Retries/SLA** : `default_args` des DAGs (retries=2, SLA 15 min).  
- **Logs** : Airflow UI + logs conteneurs.  
- **DLQ** : prévoir `rides_dlq` + opérateur d’envoi en cas de parse KO.  
- **Smoke tests** : petit script qui compare nb events `raw` vs `processed`.

---

## 🔐 Sécurité (POC vs Prod)
- **POC** : mots de passe par défaut, pas de TLS, utilisateurs minimes.  
- **Prod (hors scope repo)** :  
  - Secrets via vault (GitHub Secrets/HashiCorp), **TLS** Kafka/ES, **RBAC** Airflow,  
  - Réseaux Docker isolés, **scan d’images**, **CI/CD** avec scans SAST/DAST.

---

## ☁️ GCP — travaux **hors GitHub** (quand on bascule cloud)
1) **Projet & CLI** :  
   ```bash
   gcloud init
   gcloud config set project <PROJECT_ID>
   gcloud services enable storage.googleapis.com bigquery.googleapis.com
   ```
2) **Stockage** : `gsutil mb -l EU gs://<BUCKET_NAME>/`  
3) **BigQuery** : dataset `rides` (partitionné par date).  
4) **Service Account** : `datastream-sa` (rôles `storage.admin`, `bigquery.admin`) + clé JSON.  
5) **Airflow (cloud)** : monter la clé dans le worker (ou Secret Manager) + `GOOGLE_APPLICATION_CREDENTIALS`.  
6) **Flux cible recommandé** :  
   - Kafka → **GCS (Parquet)** via Spark/Kafka Connect (batch micro-batch)  
   - GCS → **BigQuery** (tables partitionnées/clusterisées)  
   - (Option) BigQuery/Parquet → **Elasticsearch** batché pour recherche rapide  
7) **Coûts & gouvernance** : lifecycle GCS, labels, IAM minimal, quotas BQ, VPC-SC (si sensible).

---

## 🧭 Roadmap
- **v0** : POC local fonctionnel (ce repo)  
- **v1** : DLQ + **Schema Registry** (Avro/JSON-Schema)  
- **v2** : Sink **GCS/BigQuery** + jobs batch  
- **v3** : Observabilité avancée (OpenLineage, métriques), **CI/CD**  
- **v4** : Sécurité & HA (TLS, RBAC, autoscaling)

---

## 🛠️ Dépannage rapide
- **Ports occupés** → modifier `infra/.env` (ports).  
- **DAGs non vus** → vérifier montages, timestamp fichiers, `AIRFLOW__CORE__LOAD_EXAMPLES=False`.  
- **ES vide** → relancer `es_sync`, checker logs Airflow et statut cluster ES.  
- **Producer en erreur** → vérifier `KAFKA_ADVERTISED_LISTENERS` et port `29092` côté host.

---

## 📎 Annexes
- **Make (optionnel)** : ajoute un `Makefile` avec `make up`, `make down`, `make topics`, `make clean`.  
- **ADR** : documente les choix (`docs/adr/0001-...md`).
