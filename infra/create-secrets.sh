#!/usr/bin/env bash
# Creates namespace trening and Secret trening-secrets (random values). Idempotent.
set -euo pipefail
NS=trening
kubectl get ns "$NS" >/dev/null 2>&1 || kubectl create ns "$NS"
if kubectl -n "$NS" get secret trening-secrets >/dev/null 2>&1; then
  echo "Secret trening-secrets already exists - skipping"
  exit 0
fi
PW=$(openssl rand -hex 16)
KEY=$(openssl rand -hex 32)
kubectl -n "$NS" create secret generic trening-secrets \
  --from-literal=POSTGRES_PASSWORD="$PW" \
  --from-literal=SECRET_KEY="$KEY" \
  --from-literal=DATABASE_URL="postgresql+psycopg://trening:${PW}@trening-postgres:5432/trening"
echo "Secret trening-secrets created"
