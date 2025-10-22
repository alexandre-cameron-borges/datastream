@echo off
title 🚀 Kafka Server - Mode KRaft
cd /d C:\kafka\kafka_2.13-4.1.0

echo ================================================
echo   Démarrage de Kafka en mode KRaft (local)
echo ================================================
echo.

REM Vérifie si les logs existent
if not exist "C:\kafka\kafka_2.13-4.1.0\kafka-logs" (
    echo 📦 Initialisation du stockage KRaft...
    bin\windows\kafka-storage.bat format -t 123456789abcdef -c config\kraft\server.properties
    echo ✅ Formatage terminé.
)

echo 🚀 Lancement du serveur Kafka...
bin\windows\kafka-server-start.bat config\kraft\server.properties

pause
