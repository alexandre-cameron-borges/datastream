#!/usr/bin/env bash
set -euo pipefail

# ------------------------------------------------------------
# Kafka/Redpanda topic creator (idempotent)
# Utilisation (depuis la racine du repo) :
#   chmod +x infra/kafka-create-topics.sh
#   SERVICE=broker TOPICS="rides.source rides.result" ./infra/kafka-create-topics.sh
#
# Variables (avec valeurs par défaut raisonnables) :
#   COMPOSE_FILE=infra/docker-compose.yml
#   SERVICE=broker                 # nom du service broker dans docker-compose
#   TOPICS="rides.source rides.result"
#   PARTITIONS=3                   # nb de partitions
#   RF=1                           # replication factor (1 en local, 3 en prod)
#   BOOTSTRAP=localhost:19092      # si vous voulez créer depuis l’hôte (dual listeners)
#
# Le script essaie dans l’ordre :
#   1) rpk dans le conteneur docker (Redpanda)
#   2) kafka-topics.sh dans le conteneur (Kafka classique)
#   3) rpk en local (si BOOTSTRAP défini, sans docker)
#   4) kafka-topics.sh en local (si BOOTSTRAP défini, sans docker)
# ------------------------------------------------------------

COMPOSE_FILE="${COMPOSE_FILE:-infra/docker-compose.yml}"
SERVICE="${SERVICE:-broker}"
TOPICS="${TOPICS:-rides.source rides.result}"
PARTITIONS="${PARTITIONS:-3}"
RF="${RF:-1}"
BOOTSTRAP="${BOOTSTRAP:-}"

log() { printf "\033[1;34m[topics]\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[warn]\033[0m %s\n" "$*"; }
err() { printf "\033[1;31m[err]\033[0m %s\n" "$*"; }

# -------- helpers
in_docker_rpk() {
  docker compose -f "$COMPOSE_FILE" exec -T "$SERVICE" rpk cluster info >/dev/null 2>&1
}
in_docker_kafka_topics() {
  docker compose -f "$COMPOSE_FILE" exec -T "$SERVICE" bash -lc 'command -v kafka-topics.sh >/dev/null' 2>/dev/null
}
local_rpk() {
  command -v rpk >/dev/null 2>&1
}
local_kafka_topics() {
  command -v kafka-topics.sh >/dev/null 2>&1 || command -v kafka-topics >/dev/null 2>&1
}

create_with_docker_rpk() {
  for t in $TOPICS; do
    if docker compose -f "$COMPOSE_FILE" exec -T "$SERVICE" rpk topic list -b "broker:9092" | grep -q "^$t$"; then
      log "Topic '$t' existe déjà (rpk/docker)."
    else
      log "Création topic '$t' (rpk/docker)…"
      docker compose -f "$COMPOSE_FILE" exec -T "$SERVICE" \
        rpk topic create "$t" -p "$PARTITIONS" -r "$RF" -b "broker:9092"
    fi
  done
}

create_with_docker_kafka_topics() {
  for t in $TOPICS; do
    if docker compose -f "$COMPOSE_FILE" exec -T "$SERVICE" bash -lc "kafka-topics.sh --bootstrap-server broker:9092 --list | grep -qx $t"; then
      log "Topic '$t' existe déjà (kafka-topics/docker)."
    else
      log "Création topic '$t' (kafka-topics/docker)…"
      docker compose -f "$COMPOSE_FILE" exec -T "$SERVICE" \
        bash -lc "kafka-topics.sh --bootstrap-server broker:9092 --create --if-not-exists --topic $t --partitions $PARTITIONS --replication-factor $RF"
    fi
  done
}

create_with_local_rpk() {
  : "${BOOTSTRAP:?BOOTSTRAP doit être défini pour créer en local (ex: localhost:19092)}"
  for t in $TOPICS; do
    if rpk topic list -b "$BOOTSTRAP" | grep -q "^$t$"; then
      log "Topic '$t' existe déjà (rpk/local)."
    else
      log "Création topic '$t' (rpk/local)…"
      rpk topic create "$t" -p "$PARTITIONS" -r "$RF" -b "$BOOTSTRAP"
    fi
  done
}

create_with_local_kafka_topics() {
  : "${BOOTSTRAP:?BOOTSTRAP doit être défini pour créer en local (ex: localhost:19092)}"
  for t in $TOPICS; do
    if kafka-topics.sh --bootstrap-server "$BOOTSTRAP" --list 2>/dev/null | grep -qx "$t"; then
      log "Topic '$t' existe déjà (kafka-topics/local)."
    else
      log "Création topic '$t' (kafka-topics/local)…"
      kafka-topics.sh --bootstrap-server "$BOOTSTRAP" --create --if-not-exists --topic "$t" --partitions "$PARTITIONS" --replication-factor "$RF" 2>/dev/null \
      || kafka-topics --bootstrap-server "$BOOTSTRAP" --create --if-not-exists --topic "$t" --partitions "$PARTITIONS" --replication-factor "$RF"
    fi
  done
}

# -------- stratégie
log "Topics ciblés : $TOPICS | partitions=$PARTITIONS, rf=$RF"
if in_docker_rpk; then
  log "Mode: rpk dans le conteneur '$SERVICE'."
  create_with_docker_rpk
  exit 0
fi

if in_docker_kafka_topics; then
  log "Mode: kafka-topics.sh dans le conteneur '$SERVICE'."
  create_with_docker_kafka_topics
  exit 0
fi

if [[ -n "$BOOTSTRAP" ]] && local_rpk; then
  log "Mode: rpk local (BOOTSTRAP=$BOOTSTRAP)."
  create_with_local_rpk
  exit 0
fi

if [[ -n "$BOOTSTRAP" ]] && local_kafka_topics; then
  log "Mode: kafka-topics.sh local (BOOTSTRAP=$BOOTSTRAP)."
  create_with_local_kafka_topics
  exit 0
fi

err "Aucun outil trouvé (ni rpk/kafka-topics dans docker '$SERVICE', ni en local)."
warn "Solutions :"
warn "- Lancer le broker docker puis relancer : docker compose -f $COMPOSE_FILE up -d"
warn "- Ou définir BOOTSTRAP=localhost:19092 (si dual listeners) et installer rpk/kafka-topics localement."
exit 1

