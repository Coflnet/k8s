#!/usr/bin/env bash
# Thin wrapper: copies Kafka secrets for sky-player-state
# See copy-k8s-secrets-to-openbao.sh for the full generic version.

exec "$(dirname "$0")/copy-k8s-secrets-to-openbao.sh" \
    -n sky -s redpanda -s redpanda-credentials \
    -m brokers=KAFKA__BROKERS \
    -m username=KAFKA__USERNAME \
    -m password=KAFKA__PASSWORD \
    -p sky/sky-player-state \
    "$@"
