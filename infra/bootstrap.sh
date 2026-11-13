#!/usr/bin/env bash
# Idempotent cluster add-ons for minikube profile bpcicd.
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"
cd "$(dirname "$0")"
PROFILE=${PROFILE:-bpcicd}

echo "==> minikube addons"
minikube -p "$PROFILE" addons enable ingress
minikube -p "$PROFILE" addons enable metrics-server

helm repo add jetstack https://charts.jetstack.io >/dev/null 2>&1 || true
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts >/dev/null 2>&1 || true
helm repo add argo https://argoproj.github.io/argo-helm >/dev/null 2>&1 || true
helm repo update >/dev/null

echo "==> cert-manager"
helm upgrade --install cert-manager jetstack/cert-manager -n cert-manager --create-namespace \
  --set crds.enabled=true \
  --set resources.requests.cpu=10m --set resources.requests.memory=32Mi \
  --set cainjector.resources.requests.cpu=10m --set cainjector.resources.requests.memory=32Mi \
  --set webhook.resources.requests.cpu=10m --set webhook.resources.requests.memory=32Mi \
  --wait --timeout 5m
# webhook may need a moment before accepting resources
for i in 1 2 3 4 5 6; do
  kubectl apply -f cert-manager/cluster-issuers.yaml && break || sleep 10
done
kubectl wait --for=condition=Ready clusterissuer/trening-ca-issuer --timeout=120s

echo "==> monitoring"
kubectl get ns monitoring >/dev/null 2>&1 || kubectl create ns monitoring
if ! kubectl -n monitoring get secret grafana-admin >/dev/null 2>&1; then
  kubectl -n monitoring create secret generic grafana-admin \
    --from-literal=admin-user=admin \
    --from-literal=admin-password="$(openssl rand -hex 12)"
fi
kubectl -n monitoring create configmap trening-dashboard --from-file=trening-app.json=monitoring/dashboard.json \
  --dry-run=client -o yaml | kubectl label --local -f - grafana_dashboard=1 -o yaml | kubectl apply -f -
helm upgrade --install kube-prometheus-stack prometheus-community/kube-prometheus-stack -n monitoring \
  -f monitoring/values.yaml --wait --timeout 10m

echo "==> argocd"
helm upgrade --install argocd argo/argo-cd -n argocd --create-namespace \
  --set configs.params.'server\.insecure'=true \
  --set global.domain=argocd.local \
  --set dex.enabled=false --set notifications.enabled=false \
  --set server.resources.requests.cpu=50m --set server.resources.requests.memory=64Mi \
  --set repoServer.resources.requests.cpu=50m --set repoServer.resources.requests.memory=64Mi \
  --set controller.resources.requests.cpu=100m --set controller.resources.requests.memory=128Mi \
  --set applicationSet.resources.requests.cpu=10m --set applicationSet.resources.requests.memory=32Mi \
  --set redis.resources.requests.cpu=10m --set redis.resources.requests.memory=16Mi \
  --wait --timeout 10m

echo "==> secrets"
./create-secrets.sh
echo "Done."
