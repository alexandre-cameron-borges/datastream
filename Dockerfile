# Utilise l'image officielle d'Airflow comme base
FROM apache/airflow:2.8.1

# Copie le fichier des dépendances dans le conteneur
COPY requirements.txt /

# Installe les dépendances Python listées dans le fichier
RUN pip install --no-cache-dir -r /requirements.txt
