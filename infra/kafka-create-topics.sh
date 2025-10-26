#!/usr/bin/env bash
set -euo pipefail

# ------------------------------------------------------------
# Kafka/Redpanda topic creator (idempotent)
# Utilisation :
#   chmod +x infra/kafka-create-topics.sh
#   SERVICE=broker TOPICS="rides.source rides.result" ./infra/kafka-create-topics.sh
#
# Variables :
#   COMPOSE_FILE=infra/docker-compose.yml
#   SERVICE=broker
#   TOPICS="rides.source rides.result"
#   PARTITIONS=3
#   RF=1
#   BOOTSTRAP=localhost:19092
# ------------------------------------------------------------

COMPOSE_FILE="${COMPOSE_FILE:-infra/docker-compose.yml}"
SERVICE="${SERVICE:-broker}"
TOPICS="${TOPICS:-rides.source rides.result}"
PARTITIONS="${PARTITIONS:-3}"
RF="${RF:-1}"
BOOTSTRAP="${BOOTSTRAP:-}"

log()  { printf "\033[1;34m[topics]\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[warn]\033[0m %s\n" "$*"; }
err()  { printf "\033[1;31m[err]\033[0m %s\n" "$*"; }

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

# -------- méthodes corrigées pour Redpanda v24+
create_with_docker_rpk() {
  for t in $TOPICS; do
    if docker compose -f "$COMPOSE_FILE" exec -T "$SERVICE" rpk topic list | grep -q "^$t$"; then
      log "Topic '$t' existe déjà (rpk/docker)."
    else
      log "Création topic '$t' (rpk/docker)…"
      docker compose -f "$COMPOSE_FILE" exec -T "$SERVICE" \
        rpk topic create "$t" --partitions "$PARTITIONS" --replicas "$RF"
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
    if rpk topic list --brokers "$BOOTSTRAP" | grep -q "^$t$"; then
      log "Topic '$t' existe déjà (rpk/local)."
    else
      log "Création topic '$t' (rpk/local)…"
      rpk topic create "$t" --partitions "$PARTITIONS" --replicas "$RF" --brokers "$BOOTSTRAP"
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
warn "-
