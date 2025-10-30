# Architecture Backend

## 1. Python/Simple pour l'intégration des données dans Kafka : 

- lancer 'start_kafka' pour lancer kafka
- créer un topic en ligne de commande : docker exec -it kafka /opt/kafka/bin/kafka-topics.sh --create --topic uber --bootstrap-server localhost:9092
- pour voir les topic : 'cd C:\kafka\kafka_2.13-4.1.0' puis '.\bin\windows\kafka-topics.bat --list --bootstrap-server localhost:9092'
- pour voir en tant réel tous les messages envoyés dans mon topic : '.\bin\windows\kafka-console-consumer.bat --topic uber_source --from-beginning --bootstrap-server localhost:9092'
- lancer producer_kafka.py

## 2. Airflow pour la transformation des données et l’ingestion dans Elasticsearch : 

- installation de Airflow avec Docker
- lancer Airflow : docker compose up
- se connecter : http://127.0.0.1:8080/ ((login: airflow, password: airflow par défaut))
- éxécuter : 
docker exec -it airflow-airflow-scheduler-1 bash -c "pip install --user kafka-python elasticsearch"
docker exec -it airflow-airflow-worker-1 bash -c "pip install --user kafka-python elasticsearch"
docker exec -it airflow-airflow-scheduler-1 python -c "import kafka, elasticsearch; print('✅ Kafka & Elastic installés !')"



- lancer docker compose
- éxécuter : 
docker exec -it airflow-airflow-scheduler-1 bash -c "pip install --user kafka-python elasticsearch"
docker exec -it airflow-airflow-worker-1 bash -c "pip install --user kafka-python elasticsearch"
docker exec -it airflow-airflow-scheduler-1 python -c "import kafka, elasticsearch; print('✅ Kafka & Elastic installés !')"
- se connecter : http://127.0.0.1:8080/ ((login: airflow, password: airflow par défaut))
- vérifier que le topic existe : docker exec -it kafka /opt/kafka/bin/kafka-topics.sh --create --topic uber --bootstrap-server localhost:9092
- sinon le créer : docker exec -it kafka /opt/kafka/bin/kafka-topics.sh --list --bootstrap-server localhost:9092
- lancer :
docker exec -it airflow-airflow-scheduler-1 bash
python /opt/airflow/dags/producer_kafka.py
- vérifier que kafka recoit bien les donnéeds : docker exec -it kafka /opt/kafka/bin/kafka-console-consumer.sh --topic uber --from-beginning --bootstrap-server localhost:9092


