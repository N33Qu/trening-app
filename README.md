# Trening – planowanie i monitorowanie treningu siłowego

Aplikacja webowa (Flask + PostgreSQL) do planowania treningów, prowadzenia dziennika
ćwiczeń, śledzenia rekordów osobistych i pomiarów ciała. Projekt zaliczeniowy z przedmiotu
„Bezpieczeństwo procesów CI/CD”: aplikacja jest budowana i skanowana w GitHub Actions,
a wdrażana na Kubernetes (minikube) metodą GitOps przez Argo CD, z monitoringiem
Prometheus/Grafana.

Zespół: **Mikołaj Stasz**, **Ewelina Sałata**.

## Funkcje aplikacji

- konta użytkowników (rejestracja, logowanie, hasła przechowywane jako skrót scrypt),
- katalog ćwiczeń (wbudowane + własne), plany treningowe z dniami i ćwiczeniami,
- dziennik treningów (serie `powt. x kg`, kardio: dystans i czas),
- automatyczne wykrywanie rekordów osobistych (max ciężar, szacowane 1RM) z komunikatem „Nowy rekord!”,
- pomiary ciała (masa, tkanka tłuszczowa, obwody) z importem,
- pulpit i statystyki z wykresami (jasny i ciemny motyw),
- wersja językowa polska i angielska (przełącznik PL/EN w nagłówku; wybór zapamiętywany w ciasteczku,
  domyślnie język z przeglądarki, a gdy nie jest obsługiwany – polski),
- pełna izolacja danych między użytkownikami (cudzy zasób = 404),
- konto demonstracyjne: `demo` / `demo1234` (dane przykładowe, `SEED_DEMO=true`).

## Architektura

```
                       GitHub (N33Qu/trening-app)
   git push ──►  GitHub Actions: ruff + pytest ─► build obrazu ─► Trivy ─► push GHCR
                                                         │
                                  commit: helm/trening/values.yaml (tag sha-xxxxxxx)
                                                         ▼
 ┌──────────────────────────── minikube (profil bpcicd) ─────────────────────────┐
 │  Argo CD ──(auto-sync, selfHeal, prune)──► ns trening                          │
 │                                                                                │
 │  Przeglądarka ─HTTPS─► ingress-nginx ─► Service trening-app ─► Deployment      │
 │   trening.local      (TLS z cert-manager,        :80→:8000      trening-app    │
 │                       CA własne, redirect 308)                  (HPA 2–6 pody) │
 │                                                                     │          │
 │                                              NetworkPolicy          ▼          │
 │                                                          StatefulSet postgres  │
 │                                                          (PVC 1Gi, Secret)     │
 │  ns monitoring: Prometheus (ServiceMonitor /metrics, PrometheusRule),          │
 │                 Grafana (dashboard „Trening App”), Alertmanager                │
 └────────────────────────────────────────────────────────────────────────────────┘
```

## Struktura repozytorium

```
app/                 aplikacja Flask (blueprints, modele, szablony, statyki)
tests/               testy pytest (jednostkowe i integracyjne, SQLite)
Dockerfile           obraz multi-stage, użytkownik non-root (uid 10001), gunicorn
helm/trening/        chart Helm: app, PostgreSQL, Ingress+TLS, HPA, PDB, NetworkPolicy, monitoring
argocd/              AppProject i Application (GitOps)
infra/               bootstrap.sh, create-secrets.sh, export-ca.sh, cert-manager, monitoring, k6, e2e_check.py
.github/workflows/   pipeline CI/CD (ci.yml)
docs/sprawozdanie/   sprawozdanie z testów, logi i zrzuty ekranu
```

## Szybki start (minikube, macOS)

Wymagania: Docker, minikube, kubectl, helm.

```bash
# 1. klaster (Calico, docker driver)
minikube start -p bpcicd --driver=docker --cni=calico

# 2. dodatki: ingress, metrics-server, cert-manager + CA, kube-prometheus-stack, Argo CD, Secret aplikacji
./infra/bootstrap.sh
#    (Secret trening-secrets z losowymi wartościami można też utworzyć osobno: ./infra/create-secrets.sh;
#     sekrety nie są przechowywane w repozytorium)

# 3. wdrożenie aplikacji przez Argo CD
kubectl apply -f argocd/application.yaml
kubectl -n argocd get app trening        # oczekiwane: Synced / Healthy
```

### Dostęp: hosts, tunel, zaufanie do CA

```bash
./infra/export-ca.sh                      # zapisuje certs/trening-ca.crt
sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain certs/trening-ca.crt
echo "127.0.0.1 trening.local" | sudo tee -a /etc/hosts
minikube -p bpcicd tunnel                 # w osobnym terminalu (sterownik docker na macOS)
```

Aplikacja: <https://trening.local>. Bez sudo (port-forward):

```bash
kubectl -n ingress-nginx port-forward svc/ingress-nginx-controller 8443:443 8080:80
curl --resolve trening.local:8443:127.0.0.1 --cacert certs/trening-ca.crt https://trening.local:8443/healthz
```

## CI/CD i GitOps

1. **CI** (`.github/workflows/ci.yml`): `ruff` + `pytest` z pokryciem → budowa obrazu (arm64/amd64),
   push do `ghcr.io/n33qu/trening-app:sha-<commit>` → skan Trivy (bramka na CRITICAL, raport SARIF),
   skan konfiguracji Helm.
2. **Aktualizacja wersji**: ostatni job zapisuje nowy tag w `helm/trening/values.yaml` i pushuje commit
   (zmiana tego pliku nie uruchamia ponownie pipeline’u).
3. **CD**: Argo CD (auto-sync, selfHeal, prune) wykrywa commit i wdraża nowy tag; stopka aplikacji
   pokazuje wersję. Rollback = `git revert` + push.

## Zabezpieczenia

- kontener: użytkownik non-root (10001), `readOnlyRootFilesystem`, `drop ALL`, seccomp RuntimeDefault,
  brak tokenu ServiceAccount, obraz multi-stage,
- NetworkPolicy: do aplikacji tylko ingress-nginx i monitoring; do PostgreSQL tylko pody aplikacji,
- Secret `trening-secrets` tworzony poza repozytorium (losowe wartości), brak haseł w kodzie i obrazie,
- TLS na Ingress z własnego CA (cert-manager), przekierowanie HTTP → HTTPS,
- ochrona CSRF (Flask-WTF), hasła hashowane (scrypt), ograniczanie prób logowania, izolacja danych użytkowników,
- Trivy: skan obrazu i konfiguracji Helm w pipeline.

## Monitoring

```bash
kubectl -n monitoring port-forward svc/kube-prometheus-stack-grafana 3000:80       # Grafana, dashboard „Trening App”
kubectl -n monitoring get secret grafana-admin -o jsonpath='{.data.admin-password}' | base64 -d
kubectl -n monitoring port-forward svc/kube-prometheus-stack-prometheus 9090:9090  # Prometheus, alerty
kubectl -n argocd port-forward svc/argocd-server 8081:80                           # Argo CD
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d
```

Aplikacja udostępnia `/metrics` (m.in. `flask_http_request_total`, `trening_users_total`,
`trening_workouts_total`, `trening_personal_records_total`). Alert `TreningAppDown` zgłasza brak działających replik.

## Testy

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt -r requirements.txt
pybabel compile -d app/translations
ruff check .
pytest --cov=app
```

### Tłumaczenia

Teksty interfejsu są po polsku i oznaczone w kodzie (`_()`, `_l()`, `gettext`); katalogi
`app/translations/{pl,en}/LC_MESSAGES/messages.po` są w repozytorium, a pliki `.mo` powstają przy
budowie obrazu (`pybabel compile` w `Dockerfile`) i w pipeline przed testami. Po zmianie tekstów:

```bash
pybabel extract -F babel.cfg -k _l -k lazy_gettext -k N_plural:1,2 --no-location --sort-output -o messages.pot .
pybabel update -i messages.pot -d app/translations --no-fuzzy-matching
# uzupełnij msgstr w app/translations/en/LC_MESSAGES/messages.po (i formy mnogie w pl)
pybabel compile -d app/translations
```

Scenariusze testów akceptacyjnych na klastrze (wdrożenie, izolacja, trwałość, HPA, pipeline/GitOps/monitoring)
wraz z wynikami: [docs/sprawozdanie/README.md](docs/sprawozdanie/README.md).
Test obciążenia: `k6 run -e HOSTS_IP=127.0.0.1:8443 -e VUS=50 infra/loadtest/k6.js`.
