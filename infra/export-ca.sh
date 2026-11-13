#!/usr/bin/env bash
# Exports the cluster CA certificate to ./certs/trening-ca.crt
set -euo pipefail
mkdir -p certs
kubectl -n cert-manager get secret trening-root-ca -o jsonpath='{.data.ca\.crt}' | base64 -d > certs/trening-ca.crt
cat <<MSG
Zapisano certs/trening-ca.crt

Zaufanie na macOS:
  sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain certs/trening-ca.crt
Albo: Keychain Access -> import -> Always Trust.

Wpis w /etc/hosts:
  echo "\$(minikube -p bpcicd ip) trening.local" | sudo tee -a /etc/hosts
  (z driverem docker na macOS: uruchom 'minikube -p bpcicd tunnel' i uzyj 127.0.0.1 trening.local)
MSG
