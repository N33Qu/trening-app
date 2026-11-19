# BodyCommit – system wizualny

Nazwa produktu: **BodyCommit** („Każdy trening to commit.” / “Every workout is a commit.”).
Nazwy infrastruktury (namespace `trening`, host `trening.local`, chart Helm, obraz
`ghcr.io/n33qu/trening-app`, metryki `trening_*`, aplikacja Argo CD) pozostają bez zmian.

Kierunek: spokojny, przestronny interfejs w stylu natywnych aplikacji Apple – jednolite, miękkie tło,
półprzezroczyste („matowe szkło”) powierzchnie z cienką linią krawędzi i jeden akcent w kolorze
morskiej zieleni (teal). Bez tekstur, pasków i ozdobników; hierarchię budują typografia, odstępy
i kolor używany tylko tam, gdzie coś znaczy.

Całość to zwykły CSS (`app/static/css/style.css`) z tokenami w custom properties, szablony Jinja
i dwa małe skrypty (`app.js`, `charts.js`). Brak zewnętrznych fontów i hostów (CSP).

## Znak i logo

- Znak: sztanga (gryf + talerze) z węzłem commita pośrodku – rysowany w SVG na siatce 24×24
  (`icon("logo")` w `app/templates/_macros.html`), favicon `app/static/favicon.svg` (32×32).
- Na kafelku w kolorze akcentu, biały obrys 2,1 px; wnętrze węzła wypełnione kolorem kafelka.
- Logotyp: „Body**Commit**” – krój systemowy 700, „Commit” w kolorze `--accent-ink`.

## Tokeny

| Token | Jasny | Ciemny | Zastosowanie |
|---|---|---|---|
| `--bg` | `#f5f5f7` | `#0c0c0e` | tło strony (jednolite) |
| `--surface` | `#ffffff` | `#1c1c1f` | powierzchnia pełna / fallback szkła |
| `--glass` | `rgba(255,255,255,.72)` | `rgba(36,36,40,.62)` | karty, panele, komunikaty |
| `--glass-bar` | `rgba(255,255,255,.78)` | `rgba(22,22,25,.74)` | pasek nawigacji |
| `--glass-menu` | `rgba(255,255,255,.9)` | `rgba(30,30,34,.92)` | menu mobilne, lista wyboru ćwiczeń |
| `--blur` | `blur(24px) saturate(180%)` | j.w. | `backdrop-filter` szkła |
| `--hairline` / `--line` | `rgba(0,0,0,.08)` | `rgba(255,255,255,.09)` | krawędzie i separatory 1 px |
| `--ink` / `--ink-2` / `--ink-3` | `#1d1d1f` / `#57575e` / `#6b6b73` | `#f2f2f5` / `#a5a5ae` / `#8e8e98` | tekst: główny, drugorzędny, opisy |
| `--accent` | `#0e7c73` | `#0f7a71` | przyciski główne, znak (biały tekst ≥ 4,5:1) |
| `--accent-ink` | `#0b6e66` | `#5ad3c4` | linki i akcent w tekście |
| `--accent-soft` | teal 10% | teal 12% | aktywna zakładka, ikony, kafelki |
| `--accent-mark` | `#0e7c73` | `#34b5a6` | mapa mięśni, postęp planu, węzły rekordów |
| `--success` / `--danger` / `--info` | `#1f7a43` / `#c4281c` / `#3b5f9e` | `#5fd08f` / `#ff8a7e` / `#94b4ea` | stany |
| `--chart-*` | teal + szary | teal + szary | wykresy (czytane przez `charts.js`) |

Szkło ma rozwiązanie zastępcze: gdy przeglądarka nie obsługuje `backdrop-filter` albo użytkownik
ustawił `prefers-reduced-transparency: reduce`, wszystkie `--glass*` przyjmują wartość `--surface`.
Kontrast tekstu sprawdzono dla najgorszego przypadku (tekst na szkle nad tłem): WCAG AA w obu motywach.

## Typografia

Krój systemowy (`system-ui`, na Apple – SF Pro), liczby tabelaryczne (`tabular-nums`) w tabelach,
statystykach i seriach.

| Token | Rozmiar | Użycie |
|---|---|---|
| `--text-display` | clamp 2,4–3,9 rem, 700, −0,035 em | nagłówek strony startowej |
| `--text-3xl` | 2,125 rem, 700 / 650 | tytuł strony, duże liczby |
| `--text-2xl` | 1,75 rem | tytuł na telefonie, logowanie |
| `--text-xl` | 1,375 rem | rekordy, sekcje |
| `--text-lg` | 1,125 rem, 600 | nagłówki kart, lead |
| `--text-md` | 1 rem | tekst, pola formularzy (≥ 16 px – brak zoomu na iOS) |
| `--text-sm` / `--text-xs` / `--text-2xs` | 0,875 / 0,8125 / 0,75 rem | tabele, opisy, etykiety |

## Odstępy, kształt, ruch

- Skala 4 px: `--s-1` … `--s-8` (0,25 → 4,5 rem); karty 1,5 rem wewnątrz, 1,5 rem między kartami,
  2 rem pod nagłówkiem strony.
- Promienie: 6 / 10 / 16 / 22 px (`--r-xs`, `--r-sm`, `--r`, `--r-lg`); nawigacja i przełącznik
  języka w formie „pigułek”.
- Ruch: `--ease-out` (cubic-bezier(.16,1,.3,1)), 150/250 ms; uniesienie karty o 2 px, wciśnięcie
  przycisku (scale .97), wjazd hero raz przy wczytaniu, wypełnienie paska planu. Przy
  `prefers-reduced-motion` animacje i przejścia są wyłączone, a zdjęcia ruchu ćwiczenia
  pokazywane obok siebie zamiast przenikania.

## Komponenty

- **Nagłówek** – przyklejony pasek ze szkła, nawigacja-pigułki (aktywna: `--accent-soft`),
  przełącznik PL/EN jako segment, motyw, użytkownik, wylogowanie. ≤ 960 px: menu rozwijane
  z ikonami; ≤ 520 px dla gościa ukryty przycisk rejestracji (jest w hero), więc pasek ma jeden rząd.
- **Karta** (`.card`) – szkło, linia 1 px, promień 16 px, delikatny cień. Nagłówek karty: tytuł
  po lewej, link „→” lub opis po prawej.
- **Pasek liczb** (`.figures`) – jedna powierzchnia z czterema wartościami oddzielonymi liniami.
- **Dziennik jako historia commitów** (`.commit-cell`, `.log-table`) – trening to węzeł na
  pionowej linii; trening z rekordem ma węzeł wypełniony akcentem. Na telefonie tabela zamienia
  się w listę wierszy.
- **Przyciski** – główny (akcent), drugorzędny (wypełnienie `--fill`), „ghost” (tekst akcentu),
  „danger” (tekst czerwony); rozmiary `btn-sm` / domyślny / `btn-lg`; zawsze ≥ 32 px wysokości,
  pola formularzy 44 px.
- **Formularze** – etykiety nad polami, pomoc i błędy pod polem, pierścień fokusu w kolorze akcentu.
- **Wybór ćwiczenia** (`.picker`) – pole wyszukiwania (wzorzec ARIA combobox) nad natywnym
  `<select>`: wyszukiwanie po nazwie PL i EN bez polskich znaków, filtry partii mięśniowych
  („pigułki”), miniatury, klawiatura ↑/↓/Enter/Esc. Dane z `GET /exercises/picker.json`, własne
  ćwiczenia na początku. Bez JavaScriptu działa zwykły `<select>` z grupami.
- **Puste stany** – ikona w kółku, jedno zdanie, jedna akcja.
- **Komunikaty** – szkło + ikona stanu; nowy rekord: pełny akcent.
- **Wykresy** – Chart.js; kolory, siatka, podpowiedzi i krój z custom properties, przerysowanie
  po zmianie motywu, liczby w lokalizacji strony (np. „2 500”). Bieżący tydzień w akcencie.
- **Ikony** – własny zestaw SVG 24×24, obrys 1,9 px, zaokrąglone końce (`icon()` w `_macros.html`).

## Zrzuty ekranu

`docs/img/ui/` – strona startowa, pulpit, szczegóły treningu, wybór ćwiczenia, biblioteka,
szczegóły ćwiczenia, statystyki (jasny i ciemny motyw, 1280 px i 375 px).
