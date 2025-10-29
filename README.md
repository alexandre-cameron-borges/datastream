# 🚕 Projet Big Data Streaming : Calculateur de Coût de Trajet Taxi

Ce projet implémente le backend d'un pipeline de données en temps réel pour une application de taxi. Il calcule le coût d'un trajet en fonction de la distance et du confort, traite les données via **Kafka** et **Airflow**, puis les stocke dans **Elasticsearch**, **GCS** et **BigQuery** pour visualisation et analyse.

[![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/) [![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat&logo=docker&logoColor=white)](https://www.docker.com/) [![Apache Airflow](https://img.shields.io/badge/Apache%20Airflow-017CEE?style=flat&logo=apacheairflow&logoColor=white)](https://airflow.apache.org/) [![Apache Kafka](https://img.shields.io/badge/Apache%20Kafka-231F20?style=flat&logo=apachekafka&logoColor=white)](https://kafka.apache.org/) [![Elasticsearch](https://img.shields.io/badge/Elasticsearch-005571?style=flat&logo=elasticsearch&logoColor=white)](https://www.elastic.co/elasticsearch/) [![Kibana](https://img.shields.io/badge/Kibana-005571?style=flat&logo=kibana&logoColor=white)](https://www.elastic.co/kibana/) [![Google Cloud](https://img.shields.io/badge/Google%20Cloud-4285F4?style=flat&logo=googlecloud&logoColor=white)](https://cloud.google.com/)

---

## 🏛️ Architecture

Le pipeline de données utilise les technologies suivantes, orchestrées localement avec `docker-compose` :

* **Kafka :** Bus de messages pour l'ingestion et la communication entre les étapes.
* **Airflow :** Orchestrateur des workflows (DAGs) de traitement.
* **Elasticsearch :** Base de données NoSQL pour l'indexation et la recherche.
* **Kibana :** Outil de visualisation et de dashboarding pour les données Elasticsearch.
* **Google Cloud Storage (GCS) :** Stockage objet pour les données brutes (Data Lake).
* **Google BigQuery :** Data Warehouse pour l'analyse et le stockage structuré.

---

## 🌊 Flux de Données (DAGs Airflow)

Deux DAGs Airflow gèrent le traitement :

1.  **`dag1_travel_cost` :**
    * Consomme les données brutes depuis un topic Kafka (`source`).
    * Calcule la distance (via `geopy`) et le coût du trajet (`ComputCostTravel`).
    * Publie le résultat enrichi dans un autre topic Kafka (`result`).
2.  **`dag2_data_sink` :**
    * Consomme les données enrichies depuis le topic Kafka (`result`).
    * Transforme le message JSON en un format plat (`TransFormJson`).
    * Indexe le résultat dans Elasticsearch (`PutElasticSearch`).
    * Stocke les données brutes (JSON) dans **GCS** et les données transformées (lignes) dans **BigQuery** (`PutGCP`).

---

## 🚀 Démarrage Rapide (MVP Local)

1.  **Prérequis :** Assurez-vous que Docker Desktop est installé et en cours d'exécution.

2.  **Configuration GCP :**
    * Créez un compte de service GCP avec les rôles `BigQuery Data Editor` et `Storage Object Creator`.
    * Téléchargez sa clé JSON.
    * Créez le bucket GCS `my-taxi-bucket-eu`.
    * Créez le dataset BigQuery `travel_logs` (location `EU`) et la table `rides` avec le schéma approprié.

3.  **Configuration Airflow :**
    * Lancez les services une première fois : `docker compose up -d`.
    * Accédez à Airflow (`http://localhost:8080`). Trouvez le mot de passe `admin` avec `docker compose logs airflow-standalone | grep "password"`.
    * Allez dans **Admin > Connections > +** et créez une connexion :
        * **Conn Id :** `google_cloud_default`
        * **Conn Type :** `Google Cloud`
        * **Keyfile JSON :** Collez le contenu complet de votre clé JSON GCP.
        * Sauvegardez.
    * Arrêtez les services : `docker compose down`.

4.  **Lancement Complet :**
    * Placez votre fichier de données initiales dans `./data/data_projet.json`.
    * Lancez tous les services : `docker compose up -d --build`.

5.  **Accès aux Outils :**
    * **Airflow :** `http://localhost:8080`
    * **Kibana :** `http://localhost:5601`

6.  **Exécution du Pipeline :**
    * Dans Airflow, activez et déclenchez `dag1_travel_cost`, attendez le succès ✅.
    * Activez et déclenchez `dag2_data_sink`, attendez le succès ✅.

---

## 📊 Visualisation (Kibana)

* Créez une **Data View** dans Kibana pour l'index `travel_data`.
* Explorez les données brutes dans l'onglet **Discover**.
* Créez des visualisations (ex: Graphiques "CA par Confort", Carte des localisations) et assemblez-les dans un **Dashboard**.

---

## 💾 Stockage (GCP)

* **Google Cloud Storage :** Les messages bruts (après calcul du coût) sont stockés sous forme de fichiers JSON dans `gs://my-taxi-bucket-eu/rides_raw/`.
* **Google BigQuery :** Les données transformées et aplaties sont stockées dans la table `sorbonne-475119.travel_logs.rides`. Une table externe (`rides_external_json`) peut également être créée pour lire directement depuis GCS.

---

## 🤖 Analyse BQML (Clustering)

Une fois les données stockées dans BigQuery, elles peuvent être exploitées directement via **BigQuery Machine Learning (BQML)** pour des analyses avancées, sans nécessiter d'export de données.

* **Clustering KMeans :** Comme suggéré dans l'architecture de production, un modèle **KMeans** (par exemple, avec k=8) peut être entraîné directement dans BQML.
* **Objectif :** Segmenter les trajets en clusters basés sur des caractéristiques comme la localisation de départ/arrivée, le coût, ou l'heure.
* **Analyse :** Ces clusters permettent ensuite d'analyser des métriques business, telles que le **revenu par cluster** ou le **revenu par cluster et par type de confort**, afin d'identifier des zones géographiques ou des types de trajets à forte valeur ajoutée.

---

## 🏗️ Proposition d'Architecture (Production)

Pour un environnement de production, l'architecture Kafka suivante est recommandée :

* **Brokers :** 3 (minimum pour la haute disponibilité).
* **Disques :** 1 To SSD par broker (pour la performance et la rétention).
* **Partitions :** 6 pour `source` (parallélisme pour DAG1), 3 pour `result` (parallélisme pour DAG2).
* **Monitoring :** Stack Prometheus (JMX Exporter) + Grafana pour les métriques, et Kowl (ou Redpanda Console) pour l'exploration des topics/messages.

### Schéma de flux en production

```text
[Producer] -> Kafka (topic: source) -> Airflow DAG1 ----> Kafka (topic: result) -> Airflow DAG2
                                      (Calcul Coût)                              (Flatten/Sink)
                                                                                      |
                                            +---------------------+-------------------+
                                            |                     |                   |
                                            v                     v                   v
                                      Elasticsearch            GCS (JSON)         BigQuery (Table)
                                            |                     |
                                            v                     v
                                         Kibana            BQ (External Table)
                                                                  |
                                                                  v
                                                           BQML (KMeans)
                                                                  |
                                                                  v
                                                    (Analyse Revenus / Cluster)
