# Panel sterowania serwerami (servercontroller)

Webowy panel do zdalnego zarządzania małą domową serwerownią: sprawdzasz, czy serwer działa, włączasz i wyłączasz go,
widzisz zużycie zasobów, sterujesz kontenerami Docker i oglądasz serwer przez kamerę, także z telefonu.

## O projekcie

**Dla kogo.** Dla administratora domowego laboratorium lub małej firmy, który ma dwa serwery w jednej sieci:
**główny** (mocny, wyłączany, gdy nie jest potrzebny, żeby oszczędzać prąd) i **dodatkowy** (mały, włączony
non stop, np. Dell OptiPlex). Panel działa na serwerze dodatkowym, więc jest dostępny także wtedy, gdy główny jest wyłączony.

**Co ma robić.**
- pokazywać, czy serwer główny jest dostępny, i rysować wykres opóźnień (ping),
- włączać go przez Wake-on-LAN i bezpiecznie wyłączać,
- pokazywać zasoby obu serwerów (procesor, RAM, zajęte GB na dyskach, temperatury) oraz ich historię,
- zarządzać kontenerami Docker (start/stop/restart, logi, oś czasu awarii) i stosami docker compose,
- dawać podgląd z kamery USB skierowanej na serwer,
- wysyłać powiadomienia push, gdy coś przestanie działać (planowane).

Panel steruje sprzętem, więc jest zabezpieczony jak system wystawiony do internetu (przez Tailscale Funnel):
hasło + kod 2FA, blokada konta, CSRF, Content-Security-Policy, dziennik zdarzeń. Szczegóły w sekcji [Bezpieczeństwo](#bezpieczeństwo).

## Zespół

| Imię i nazwisko | GitHub | Zakres |
|---|---|---|
| **[uzupełnij: Imię Nazwisko]** | [@robajs3](https://github.com/robajs3) | projekt indywidualny: całość (backend, frontend, infrastruktura) |

## Technologie

| Warstwa | Technologia |
|---|---|
| **Frontend (decyzja)** | **React 18 + Vite + TypeScript** jako SPA, React Router, TanStack Query (odpytywanie API), Chart.js przez `react-chartjs-2` (wykresy), PWA (manifest + service worker) |
| Frontend (stan obecny) | prototyp w szablonach Jinja2 + htmx + Chart.js (biblioteki serwowane lokalnie), **do zastąpienia przez SPA** wg planu poniżej |
| Backend / API | Python 3.12, Flask, Flask-Login, Flask-WTF (CSRF), Flask-Limiter, argon2, pyotp (2FA) |
| Baza danych | PostgreSQL 16, SQLAlchemy, migracje Alembic (Flask-Migrate) |
| Zadania w tle | APScheduler (ping, metryki, stan kontenerów, retencja danych) |
| Agent na serwerach | Flask + psutil + Docker SDK, usługa systemd na hoście |
| Wake-on-LAN | mikrousługa w `network_mode: host` |
| Kamera | go2rtc (USB → MJPEG), proxy w Flasku za logowaniem |
| Infrastruktura | Docker Compose, Tailscale Funnel (HTTPS) |

### Frontend: React (SPA), plan migracji

Wybrałem React, bo panel składa się z powtarzalnych, odświeżanych na żywo widżetów (status, wykresy, tabela
kontenerów, przyciski sterujące), które naturalnie dzielą się na komponenty i współdzielą stan z API.
SPA będzie budowane przez Vite, a gotowy bundle serwowany przez Flaska z tego samego origin (to upraszcza sesję i CSRF).

Planowane komponenty:

| Komponent | Odpowiada za |
|---|---|
| `LoginPage` | logowanie: login, hasło, kod 2FA; obsługa blokady konta |
| `Dashboard` | układ strony głównej, składa poniższe karty |
| `ServerStatusCard` | status ONLINE/OFFLINE, opóźnienie, czas od ostatniej zmiany |
| `ControlButtons` + `ConfirmDialog` | przyciski „Włącz (WoL)” i „Wyłącz” z potwierdzeniem i hasłem |
| `PingChart` | wykres pingu z wyborem zakresu |
| `ResourceCard`, `ResourceChart` | CPU, RAM, dyski, temperatury oraz wykres historii |
| `ContainerTable`, `LogViewer` | lista kontenerów z akcjami i podgląd logów |
| `ContainerTimeline` | oś czasu awarii |
| `StackList`, `StackEditor`, `JobOutput` | stosy compose, edytor, wynik operacji |
| `CameraView` | zdjęcie i podgląd na żywo |
| `NotificationSettings` | zgoda na push, progi alertów |

Etapy migracji: **F1** JSON API `/api/v1/*` dla wszystkich widoków (dziś część endpointów zwraca fragmenty HTML dla htmx);
**F2** szkielet Vite + React + TS, logowanie, routing, klient API; **F3** Dashboard (status, sterowanie, wykresy, zasoby);
**F4** Docker, stosy, kamera, PWA i usunięcie szablonów Jinja.

## Funkcje

Właścicielem wszystkich funkcji jest **@robajs3** (projekt indywidualny). Status: ✅ działa u mnie, 🧪 zaimplementowane i przetestowane automatycznie, ale bez potwierdzenia na docelowym sprzęcie, ⬜ planowane.

| Funkcja | Status | Właściciel |
|---|---|---|
| [Logowanie, 2FA i dziennik zdarzeń](#logowanie-2fa-i-dziennik-zdarzeń) | ✅ działa | @robajs3 |
| [Status serwera głównego](#status-serwera-głównego) | ✅ działa | @robajs3 |
| [Wykres pingów](#wykres-pingów) | ✅ działa | @robajs3 |
| [Włączanie serwera (Wake-on-LAN)](#włączanie-serwera-wake-on-lan) | 🧪 zaimplementowane, do potwierdzenia na sprzęcie | @robajs3 |
| [Wyłączanie serwera](#wyłączanie-serwera) | 🧪 zaimplementowane, do potwierdzenia na sprzęcie | @robajs3 |
| [Zasoby serwerów](#zasoby-serwerów) | ✅ działa | @robajs3 |
| [Wykresy zasobów](#wykresy-zasobów) | ✅ działa | @robajs3 |
| [Kontenery Docker](#kontenery-docker) | 🧪 zaimplementowane, do potwierdzenia na sprzęcie | @robajs3 |
| [Oś czasu awarii kontenerów](#oś-czasu-awarii-kontenerów) | 🧪 zaimplementowane, do potwierdzenia na sprzęcie | @robajs3 |
| [Stosy docker compose](#stosy-docker-compose) | 🧪 zaimplementowane, do potwierdzenia na sprzęcie | @robajs3 |
| [Podgląd z kamery](#podgląd-z-kamery) | 🧪 zaimplementowane, do potwierdzenia na sprzęcie | @robajs3 |
| [Powiadomienia push i alerty (PWA)](#powiadomienia-push-i-alerty-pwa) | ⬜ planowane | @robajs3 |
| [Interfejs w React (SPA)](#interfejs-w-react-spa) | ⬜ planowane | @robajs3 |

### Logowanie, 2FA i dziennik zdarzeń

**Właściciel:** @robajs3 · **Status:** ✅ działa

- **Co robi użytkownik:** wpisuje login, hasło i 6-cyfrowy kod z aplikacji 2FA; po 5 błędnych próbach konto blokuje się na 10 minut.
- **Widok:** formularz logowania (login, hasło, kod), przycisk „Wyloguj” w nagłówku.
- **Dane:** `users` (hash argon2, sekret TOTP, ostatni użyty krok TOTP, licznik błędów, czas blokady), `audit_log` (kto, IP, akcja, czas).
- **Najtrudniejsze:** panel jest publiczny (Funnel): kod TOTP można użyć tylko raz (atomowy zapis kroku czasowego), blokada konta nie może zdradzać, czy login istnieje, do tego CSRF i limit prób per IP.
- **Gotowe, gdy:** poprawne dane logują, ten sam kod nie zadziała drugi raz, piąty błąd blokuje konto, każda próba trafia do `audit_log`.

### Status serwera głównego

**Właściciel:** @robajs3 · **Status:** ✅ działa

- **Co robi użytkownik:** otwiera dashboard i widzi, czy serwer jest ONLINE, OFFLINE, w trakcie uruchamiania lub wyłączania.
- **Widok:** karta statusu odświeżana co 5 s: kolorowa etykieta, opóźnienie ICMP i TCP, czas od ostatniej zmiany.
- **Dane:** `ping_samples` (ping + test portu co `PING_INTERVAL`), `status_events` (zmiany stanu).
- **Najtrudniejsze:** odróżnienie awarii od chwilowej utraty pakietu (próg `FAIL_THRESHOLD`) oraz stany przejściowe z limitami czasu; gdy worker stoi, panel pokazuje „brak danych” zamiast starego statusu.
- **Gotowe, gdy:** po wyłączeniu serwera status zmienia się na OFFLINE w czasie `FAIL_THRESHOLD × PING_INTERVAL`, a pojedynczy zgubiony pakiet nie daje fałszywego alarmu.

### Wykres pingów

**Właściciel:** @robajs3 · **Status:** ✅ działa

- **Co robi użytkownik:** wybiera zakres 1h, 6h, 24h, 7d lub 30d i ogląda opóźnienia oraz utratę pakietów.
- **Widok:** wykres liniowy (średni i maksymalny ping w ms) ze słupkami utraty pakietów w %.
- **Dane:** `ping_samples` (surowe, `RETENTION_DAYS_RAW`) i `ping_agg` (średnie minutowe, `RETENTION_DAYS_AGG`); endpoint `GET /api/ping`.
- **Najtrudniejsze:** retencja i agregacja bez obciążania bazy, sprowadzenie dowolnego zakresu do ok. 300 punktów, obsługa wygasłej sesji przy odświeżaniu.
- **Gotowe, gdy:** każdy zakres rysuje się poniżej sekundy, a dane starsze niż okres surowych próbek pochodzą z agregatów.

### Włączanie serwera (Wake-on-LAN)

**Właściciel:** @robajs3 · **Status:** 🧪 zaimplementowane, do potwierdzenia na sprzęcie

- **Co robi użytkownik:** klika „Włącz (WoL)” i potwierdza; status przechodzi na „uruchamianie…”, a po starcie na ONLINE.
- **Widok:** przycisk na karcie serwera i komunikat z wynikiem.
- **Dane:** pakiet UDP wysyłany wyłącznie na MAC z konfiguracji, `status_events` (BOOTING), `audit_log`.
- **Najtrudniejsze:** broadcast z kontenera (osobna usługa `wol` w `network_mode: host`) oraz konfiguracja BIOS i karty sieciowej, która bywa kapryśna.
- **Gotowe, gdy:** z całkowitego wyłączenia serwer wstaje po kliknięciu, a brak odpowiedzi po `BOOT_TIMEOUT` kończy się statusem OFFLINE i komunikatem.

### Wyłączanie serwera

**Właściciel:** @robajs3 · **Status:** 🧪 zaimplementowane, do potwierdzenia na sprzęcie

- **Co robi użytkownik:** klika „Wyłącz”, podaje hasło i potwierdza w oknie dialogowym.
- **Widok:** pole hasła z przyciskiem, komunikat wyniku, status „wyłączanie…”.
- **Dane:** stałe polecenie SSH (klucz ograniczony przez `command=` w `authorized_keys`), `status_events`, `audit_log`.
- **Najtrudniejsze:** bezpieczeństwo: żadna wartość z żądania HTTP nie trafia do powłoki, klucz może tylko wyłączyć serwer, host jest weryfikowany po kluczu.
- **Gotowe, gdy:** serwer się wyłącza; złe hasło lub brak tokenu CSRF nie uruchamia SSH, a każda próba jest w `audit_log`.

### Zasoby serwerów

**Właściciel:** @robajs3 · **Status:** ✅ działa

- **Co robi użytkownik:** widzi na dashboardzie karty obu serwerów.
- **Widok:** karta na serwer: model procesora, rdzenie i wątki, paski CPU, RAM i dysków (GB użyte z łącznych), temperatury, sieć, GPU (jeśli jest), uptime.
- **Dane:** agent `GET /metrics` (psutil) → `agent_state` (ostatni znany stan w JSONB).
- **Najtrudniejsze:** agent musi działać na hoście, żeby widzieć prawdziwe dyski i czujniki; filtrowanie pseudo-dysków (snap, overlay); pokazanie ostatnich danych, gdy serwer jest wyłączony.
- **Gotowe, gdy:** wartości zgodne z `htop` i `df`, a przy wyłączonym serwerze karta pokazuje „agent nie odpowiada” z godziną ostatnich danych.

### Wykresy zasobów

**Właściciel:** @robajs3 · **Status:** ✅ działa

- **Co robi użytkownik:** wybiera serwer i zakres i ogląda CPU, RAM (%) oraz temperaturę w czasie.
- **Widok:** wykres liniowy z przełącznikami serwera i zakresu.
- **Dane:** `metric_samples` (surowe) i `metric_agg` (średnie minutowe); `GET /api/metrics`.
- **Najtrudniejsze:** agregacja ważona liczbą próbek i wspólny format dla surowych i zagregowanych danych.
- **Gotowe, gdy:** wykres jest ciągły przy przejściu z surowych próbek na agregaty i pokazuje przerwę, gdy serwer był wyłączony.

### Kontenery Docker

**Właściciel:** @robajs3 · **Status:** 🧪 zaimplementowane, do potwierdzenia na sprzęcie

- **Co robi użytkownik:** przegląda kontenery, uruchamia, zatrzymuje i restartuje je (z potwierdzeniem) oraz czyta logi.
- **Widok:** tabela: nazwa, projekt, obraz, porty, stan, CPU, RAM, restarty, akcje; panel logów pod tabelą.
- **Dane:** agent `/docker/containers` (Docker SDK) → `docker_state`; akcje i logi przez agenta; `audit_log`.
- **Najtrudniejsze:** wydajność przy dużej liczbie kontenerów (równoległy odczyt), liczenie CPU z statystyk Dockera oraz ochrona kontenerów samego panelu (`PROTECTED_PROJECTS`).
- **Gotowe, gdy:** lista zgadza się z `docker ps -a`, akcja zmienia stan w kilka sekund, a kontenera panelu nie da się zatrzymać z panelu.

### Oś czasu awarii kontenerów

**Właściciel:** @robajs3 · **Status:** 🧪 zaimplementowane, do potwierdzenia na sprzęcie

- **Co robi użytkownik:** wybiera zakres 6h–30d i widzi, kiedy które kontenery działały, padły albo zostały zatrzymane.
- **Widok:** poziome paski per kontener (zielony, czerwony, szary) z markerami restartów i OOM oraz lista ostatnich zdarzeń.
- **Dane:** `container_events` (rodzaj, stan po zdarzeniu, kod wyjścia, szczegóły).
- **Najtrudniejsze:** Docker nie przechowuje historii, więc zdarzenia wykrywam porównując kolejne odczyty; trzeba odróżnić awarię (kod wyjścia, OOM) od celowego zatrzymania i obsłużyć pętle restartów.
- **Gotowe, gdy:** ubity kontener pojawia się jako czerwony pas najpóźniej po jednym cyklu odczytu, a zatrzymany świadomie jako szary.

### Stosy docker compose

**Właściciel:** @robajs3 · **Status:** 🧪 zaimplementowane, do potwierdzenia na sprzęcie

- **Co robi użytkownik:** edytuje plik compose i `.env` stosu (po podaniu hasła), uruchamia Up, Pull, Restart, Down i tworzy nowe stosy.
- **Widok:** lista stosów, edytor tekstowy z zakładkami compose i `.env`, okno z przebiegiem operacji odświeżane na żywo.
- **Dane:** pliki na dysku serwera w katalogach z `AGENT_STACK_DIRS` i `AGENT_STACKS_ROOT`, zadania w pamięci agenta, `audit_log`.
- **Najtrudniejsze:** bezpieczny zapis (walidacja `docker compose config`, kopie `.bak`), długie operacje wykonywane asynchronicznie i uprawnienia agenta do katalogów stosów.
- **Gotowe, gdy:** niepoprawny YAML się nie zapisuje, „Up” uruchamia kontenery, a przebieg operacji jest widoczny, dopóki się nie skończy.

### Podgląd z kamery

**Właściciel:** @robajs3 · **Status:** 🧪 zaimplementowane, do potwierdzenia na sprzęcie

- **Co robi użytkownik:** widzi zdjęcie z kamery na dashboardzie, a na stronie „Kamera” włącza podgląd na żywo i pobiera zdjęcie.
- **Widok:** karta ze zdjęciem odświeżanym co 10 s oraz osobna strona z obrazem MJPEG (5 klatek/s).
- **Dane:** go2rtc (kamera USB → MJPEG), proxy we Flasku za logowaniem; `audit_log` dla podglądu i pobrania.
- **Najtrudniejsze:** strumień przez Funnel bez WebRTC (stąd MJPEG) oraz to, że każdy podgląd zajmuje wątek serwera, więc limit jednoczesnych podglądów i czasu.
- **Gotowe, gdy:** podgląd działa na telefonie, zatrzymuje się po zmianie karty lub po limicie czasu, a trzeci równoległy podgląd dostaje komunikat zamiast blokować serwer.

### Powiadomienia push i alerty (PWA)

**Właściciel:** @robajs3 · **Status:** ⬜ planowane

- **Co robi użytkownik:** instaluje panel jako aplikację na telefonie, włącza powiadomienia i dostaje push, gdy serwer przestanie odpowiadać, kontener padnie albo CPU, RAM, dysk lub temperatura przekroczą progi.
- **Widok:** ekran „Powiadomienia”: włącz/wyłącz, progi alertów, test powiadomienia; baner „Zainstaluj aplikację”.
- **Dane:** `push_subscriptions`, stan alertów (z histerezą), klucze VAPID; dane źródłowe z `status_events`, `container_events` i metryk.
- **Najtrudniejsze:** iOS wymaga dodania aplikacji do ekranu głównego, alerty nie mogą się dublować, a gdy padnie sam serwer z panelem, powiadomi o tym zewnętrzny heartbeat.
- **Gotowe, gdy:** po wyłączeniu serwera głównego telefon dostaje push w ciągu minuty, a ten sam alert nie przychodzi wielokrotnie.

### Interfejs w React (SPA)

**Właściciel:** @robajs3 · **Status:** ⬜ planowane

- **Co robi użytkownik:** korzysta z tego samego panelu, ale jako szybkiej aplikacji jednostronicowej bez przeładowań strony.
- **Widok:** komponenty z tabeli w sekcji „Frontend: React (SPA)”: dashboard, wykresy, przyciski sterujące, tabela kontenerów.
- **Dane:** JSON API `/api/v1/*` (dziś część widoków zwraca fragmenty HTML dla htmx).
- **Najtrudniejsze:** przepisanie widoków z zachowaniem sesji, CSRF i obsługi wygasłej sesji oraz pogodzenie CSP z bundlem.
- **Gotowe, gdy:** wszystkie widoki działają w React, szablony Jinja są usunięte, a testy komponentów przechodzą.

## Uruchomienie

Wymagania: serwer dodatkowy z Dockerem (compose v2), serwer główny z Ubuntu, opcjonalnie Tailscale (Funnel).

1. **Konfiguracja:** `cp .env.example .env` i uzupełnij (`SECRET_KEY`, `DB_PASSWORD`, `MAIN_HOST`, `MAIN_MAC`, tokeny). `.env` nie trafia do repo.
2. **Start:** `docker compose up -d --build`. Kontener `web` przy starcie stosuje migracje bazy (`flask --app app init-db`),
   a `worker` czeka, aż schemat będzie gotowy. Bazę z wcześniejszych etapów (bez migracji) migracje przejmują automatycznie.
3. **Konto:** `docker compose exec web flask --app app create-user LOGIN`, potem zeskanuj kod QR w aplikacji 2FA.
   Odblokowanie konta: `docker compose exec web flask --app app unlock-user LOGIN`.
4. **Dostęp z internetu:** `sudo tailscale funnel --bg 8000` (flaga `--bg` zostawia Funnel włączony po zamknięciu terminala i po restarcie;
   sprawdzisz przez `tailscale funnel status`). Panel nasłuchuje tylko na `127.0.0.1:8000`. Test lokalny bez HTTPS: `COOKIE_SECURE=0` w `.env`.
5. **Agenci** (metryki, Docker, stosy) na obu serwerach: [agent/README.md](agent/README.md).
6. **Włączanie i wyłączanie serwera głównego** (poniżej).
7. **Kamera (opcjonalnie):** podłącz kamerę USB do serwera dodatkowego, w `.env` ustaw `COMPOSE_PROFILES=camera` i `CAMERA_URL=http://camera:1984`.
   Rozdzielczość i liczbę klatek zmienisz w `go2rtc/go2rtc.yaml`.
8. **Aktualizacja:** `git pull && docker compose up -d --build`; nowe migracje zastosują się same.

### Włączanie i wyłączanie serwera głównego

**WoL:** włącz Wake on LAN w BIOS (także PCIe wake), w netplanie ustaw `wakeonlan: true` dla karty i wykonaj `sudo netplan apply`.
Sprawdź: `ethtool eth0 | grep Wake-on` (powinno być `g`). W `.env` ustaw `WOL_BROADCAST` na adres broadcast podsieci (np. `192.168.1.255`).
Usługa `wol` słucha na `0.0.0.0:9009` (chroni ją token); przy ufw: `sudo ufw allow from 172.16.0.0/12 to any port 9009 proto tcp`
i nie otwieraj tego portu dla reszty LAN.

**Wyłączanie** wykonuje wyłącznie stałe polecenie `sudo -n /usr/sbin/shutdown -h now` przez SSH. Przygotowanie na głównym serwerze:

```bash
sudo adduser --disabled-password --gecos "" panel
echo 'panel ALL=(root) NOPASSWD: /usr/sbin/shutdown -h now' | sudo tee /etc/sudoers.d/panel
sudo visudo -cf /etc/sudoers.d/panel
```

Na serwerze panelu wygeneruj osobny klucz: `mkdir -p secrets && ssh-keygen -t ed25519 -N "" -f secrets/id_ed25519` (katalog `secrets/` jest w `.gitignore`).
Do `~panel/.ssh/authorized_keys` na głównym wpisz klucz publiczny **z ograniczeniami**, tak by nawet skradziony klucz mógł tylko wyłączyć serwer:

```
from="IP_SERWERA_PANELU",command="sudo -n /usr/sbin/shutdown -h now",no-pty,no-port-forwarding,no-agent-forwarding,no-X11-forwarding ssh-ed25519 AAAA... panel
```

Odcisk klucza hosta zapisz (i sprawdź ręcznie): `ssh-keyscan -t ed25519 IP_GLOWNEGO > secrets/known_hosts`. Panel odrzuca nieznane hosty.

## Bezpieczeństwo

Panel potrafi wyłączyć serwer i sterować kontenerami (co daje uprawnienia zbliżone do roota), a przez Funnel jest widoczny w internecie.

- **Konto:** hasło (argon2) + kod TOTP, który działa tylko raz, blokada konta po 5 błędach (`LOGIN_MAX_FAILED`, `LOGIN_LOCK_MINUTES`),
  limit prób per IP, ciasteczko sesji `Secure`, `HttpOnly`, `SameSite=Lax`.
- **Przeglądarka:** ochrona CSRF, `Content-Security-Policy` ze skryptami tylko z własnego origin i z nonce (bez `unsafe-inline` i `unsafe-eval`),
  HSTS, brak zasobów z CDN (htmx i Chart.js są w `app/static/vendor/` z zapisanymi sumami kontrolnymi). Gdyby CSP coś blokowało,
  ustaw `CSP_REPORT_ONLY=1` w `.env`: przeglądarka tylko zgłosi naruszenia w konsoli.
- **Akcje sterujące:** wyłączanie to stałe polecenie bez parametrów z żądania, klucz SSH ograniczony przez `command=`, weryfikacja klucza hosta,
  ponowne podanie hasła i potwierdzenie w UI. WoL idzie wyłącznie na MAC z konfiguracji. Kontenery i stosy wskazuje się identyfikatorami z listy
  (walidacja wzorcem), a kontenery samego panelu są chronione (`PROTECTED_PROJECTS`). Zapis plików compose przechodzi walidację i tworzy kopię `.bak`.
- **Agent:** token Bearer i dostęp po zaporze tylko z serwera panelu; członkostwo w grupie `docker` oznacza uprawnienia roota, więc chroń token i port.
- **Dziennik:** każda akcja sterująca i próba logowania trafia do tabeli `audit_log` (kto, IP, co, kiedy).
- **Sekrety:** `.env`, `secrets/`, klucze i `*.patch` są w `.gitignore`; w repo jest tylko `.env.example`. Jeśli sekret kiedyś trafił do commita,
  traktuj go jako wyciekły i zmień (samo usunięcie pliku nie czyści historii).

## Praca z repozytorium

Zmiany wprowadzam małymi commitami, jeden logiczny krok na commit, z prefiksem typu: `feat`, `fix`, `refactor`, `docs`, `chore`
(np. `fix(auth): kod TOTP można użyć tylko raz`). Dzięki temu historia pokazuje postęp prac, a pojedynczy krok można łatwo wycofać.
