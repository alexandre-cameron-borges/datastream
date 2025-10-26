"""
DAG Name: main_pipeline_dag
Description:
    Ce DAG orchestre l’ensemble de la pipeline de données : de la lecture CSV
    jusqu’à la visualisation dans Kibana. Il déclenche séquentiellement les
    autres DAGs (csv_to_kafka_source, kafka_processing_dag, elastic_gcp_ingestion_dag).

Tâches principales:
    - Exécution du DAG d’ingestion CSV vers Kafka.
    - Exécution du DAG de traitement Kafka.
    - Exécution du DAG d’ingestion vers Elasticsearch.

Objectif:
    Assurer un flux de données bout-à-bout automatisé, stable et reproductible
    dans un environnement Airflow.

Schedule: @daily
Tags: [orchestration, airflow, pipeline]
"""


from airflow import DAG
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from datetime import datetime

with DAG(
    dag_id='main_pipeline_dag',
    description='Full pipeline: CSV → Kafka → Processing → Elastic & GCP',
    schedule_interval=None,
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['pipeline', 'kafka', 'elasticsearch', 'gcp'],
) as dag:

    # Étape 1 : envoyer les données CSV dans Kafka
    trigger_csv = TriggerDagRunOperator(
        task_id='trigger_csv_to_kafka_source',
        trigger_dag_id='csv_to_kafka_source',
        reset_dag_run=True,
        wait_for_completion=True,
    )

    # Étape 2 : traitement Kafka (consommation + calcul du coût)
    trigger_processing = TriggerDagRunOperator(
        task_id='trigger_kafka_processing',
        trigger_dag_id='kafka_processing_dag',
        reset_dag_run=True,
        wait_for_completion=True,
    )

    # Étape 3 : ingestion dans ElasticSearch et GCP
    trigger_ingestion = TriggerDagRunOperator(
        task_id='trigger_elastic_gcp_ingestion',
        trigger_dag_id='elastic_gcp_ingestion_dag',
        reset_dag_run=True,
        wait_for_completion=True,
    )

    # Ordre d'exécution complet
    trigger_csv >> trigger_processing >> trigger_ingestion
