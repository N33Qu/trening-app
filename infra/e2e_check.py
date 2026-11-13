"""Scenariusz testu funkcjonalnego przez Ingress (HTTPS, własne CA).

Użycie:
  python infra/e2e_check.py setup  --ca certs/trening-ca.crt [--port 8443]
  python infra/e2e_check.py verify --ca certs/trening-ca.crt [--port 8443]

Wymaga: requests; port-forward ingress-nginx na 127.0.0.1:<port>.
Stan (nazwy użytkowników) jest zapisywany w pliku e2e_state.json.
"""
import argparse
import json
import re
import socket
import sys
import time
from datetime import date, timedelta

import requests

HOST = "trening.local"
STATE = "e2e_state.json"

_orig = socket.getaddrinfo


def _patched(host, *args, **kwargs):
    return _orig("127.0.0.1" if host == HOST else host, *args, **kwargs)


socket.getaddrinfo = _patched


class Client:
    def __init__(self, base, ca):
        self.base, self.s = base, requests.Session()
        self.s.verify = ca
        self.s.headers["Referer"] = base + "/"

    def csrf(self, path):
        r = self.s.get(self.base + path)
        m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', r.text) or re.search(
            r'value="([^"]+)"[^>]*name="csrf_token"', r.text)
        return m.group(1)

    def post(self, path, data, form_path=None):
        data = {**data, "csrf_token": self.csrf(form_path or path)}
        return self.s.post(self.base + path, data=data, allow_redirects=True)

    def get(self, path):
        return self.s.get(self.base + path)

    def register(self, u, p):
        return self.post("/register", {"username": u, "password": p, "confirm": p})

    def login(self, u, p):
        return self.post("/login", {"username": u, "password": p})


def flashes(html):
    return re.findall(r'class="flash[^"]*"[^>]*>\s*(?:<[^>]+>\s*)*([^<]+)', html)


def check(name, cond, extra=""):
    print(f"[{'OK' if cond else 'FAIL'}] {name} {extra}")
    if not cond:
        check.failed = True


check.failed = False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=["setup", "verify"])
    ap.add_argument("--ca", required=True)
    ap.add_argument("--port", default="8443")
    a = ap.parse_args()
    base = f"https://{HOST}:{a.port}"
    pw = "Haslo-testowe-123"

    if a.phase == "setup":
        sfx = str(int(time.time()))[-6:]
        ua, ub = f"test_a_{sfx}", f"test_b_{sfx}"
        A, B = Client(base, a.ca), Client(base, a.ca)
        r = A.register(ua, pw)
        check("rejestracja A", "Konto utworzone" in r.text)
        r = B.register(ub, pw)
        check("rejestracja B", "Konto utworzone" in r.text)

        r = A.post("/plans/new", {"name": "Plan testowy A", "description": "FBW", "is_active": "y"})
        check("A tworzy plan", "Utworzono plan" in r.text, r.url)
        plan_url = r.url.replace(base, "")
        # catalogue: take first strength exercise id from workout form
        form = A.get("/workouts/new").text
        m = re.search(r'<option value="(\d+)"[^>]*>\s*Wyciskanie sztangi le', form)
        ex_id = m.group(1)
        d = (date.today() - timedelta(days=1)).isoformat()
        data = {"date": d, "plan_day_id": "0", "notes": "test",
                "entries-0-exercise_id": ex_id, "entries-0-sets": "5x100, 5x100",
                "entries-0-distance_km": "", "entries-0-duration_min": ""}
        r = A.post("/workouts/new", data, form_path="/workouts/new")
        check("A zapisuje trening", "Zapisano trening" in r.text, r.url)
        check("flash 'Nowy rekord!'", "Nowy rekord!" in r.text)
        workout_url = r.url.replace(base, "")
        r = A.post("/body/new", {"date": d, "weight_kg": "82.5"})
        check("A dodaje pomiar masy ciała", "Zapisano pomiar" in r.text)
        r = A.get("/body/")
        check("pomiar 82.5 widoczny", "82.5" in r.text)

        r = B.get(workout_url)
        check(f"B -> trening A {workout_url} = 404", r.status_code == 404, str(r.status_code))
        r = B.get(workout_url + "/edit")
        check(f"B -> {workout_url}/edit = 404", r.status_code == 404, str(r.status_code))
        r = B.get(plan_url)
        check(f"B -> plan A {plan_url} = 404", r.status_code == 404, str(r.status_code))
        r = B.get("/plans/")
        check("lista planów B nie zawiera planu A", "Plan testowy A" not in r.text)
        r = B.get("/workouts/")
        check("lista treningów B pusta", "test_a_" not in r.text and "Nowy rekord" not in r.text)
        r = requests.get(base + "/workouts/", verify=a.ca, allow_redirects=False, timeout=10)
        check("bez logowania -> redirect do /login", r.status_code in (301, 302, 303, 308)
              and "login" in r.headers.get("Location", ""), str(r.status_code))
        r = requests.post(base + "/plans/new", data={"name": "x"}, verify=a.ca, allow_redirects=False, timeout=10)
        check("POST bez CSRF/sesji odrzucony", r.status_code in (302, 400, 401, 403), str(r.status_code))
        json.dump({"a": ua, "b": ub, "pw": pw, "workout": workout_url, "plan": plan_url}, open(STATE, "w"))
        print("state:", ua, ub)
    else:
        st = json.load(open(STATE))
        A = Client(base, a.ca)
        r = A.login(st["a"], st["pw"])
        check("A loguje się ponownie", "Witaj" in r.text)
        r = A.get(st["workout"])
        check("trening A nadal istnieje", r.status_code == 200 and "Wyciskanie" in r.text)
        check("rekord nadal widoczny", "rekord" in r.text.lower() or "PR" in r.text)
        r = A.get(st["plan"])
        check("plan A nadal istnieje", r.status_code == 200 and "Plan testowy A" in r.text)
        r = A.get("/body/")
        check("pomiar masy 82.5 nadal istnieje", "82.5" in r.text)
    sys.exit(1 if check.failed else 0)


main()
