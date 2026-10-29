# Agent metryk
Instalacja na KAŻDYM serwerze (Ubuntu/Debian, Python 3): skopiuj katalog `agent/`, potem `sudo ./install.sh`.
Skrypt wypisze token; wpisz go do `.env` panelu (AGENT_MAIN_TOKEN / AGENT_LOCAL_TOKEN). Test: `curl -H "Authorization: Bearer TOKEN" localhost:8765/metrics`.

## Sieć
- Agent słucha na `AGENT_BIND:AGENT_PORT` (domyślnie 0.0.0.0:8765) i wymaga tokenu. Nie wystawiaj go do internetu.
- **Serwer dodatkowy (ten z panelem):** worker łączy się przez `host.docker.internal`. Przy ufw:
  `sudo ufw allow from 172.16.0.0/12 to any port 8765 proto tcp`
- **Serwer główny:** `sudo ufw allow from IP_SERWERA_DODATKOWEGO to any port 8765 proto tcp`

## HTTPS przez Tailscale (opcjonalnie)
Tunel Tailscale (WireGuard) już szyfruje ruch, więc HTTPS jest dodatkiem. Jeśli chcesz:
1. Na głównym: `sudo tailscale cert main.TAILNET.ts.net` (pliki .crt/.key), skopiuj do `/opt/panel-agent/cert.pem` i `key.pem`, `chown panel-agent`.
2. W `/opt/panel-agent/agent.env` odkomentuj `GUNICORN_CMD_ARGS=...`, potem `sudo systemctl restart panel-agent`.
3. W `.env` panelu: `AGENT_MAIN_URL=https://main.TAILNET.ts.net:8765` (certyfikat jest publicznie zaufany, więc `VERIFY=1`).
Uwaga: kontener `worker` musi rozwiązać nazwę `*.ts.net`. Jeśli nie potrafi, użyj `extra_hosts` z IP Tailscale serwera
albo zostań przy HTTP po IP z LAN. Certyfikaty `tailscale cert` wygasają po ~90 dniach, odnawiaj je (cron).

## Etap 5: Docker i stosy compose
Po zaktualizowaniu plików agenta uruchom ponownie `sudo ./install.sh` (idempotentny: zachowuje token, dodaje agenta do grupy `docker`, tworzy `/opt/stacks`, restartuje usługę).
Wymagane: `docker compose` (wtyczka v2). Członkostwo w grupie `docker` daje agentowi uprawnienia równoważne rootowi, więc pilnuj tokenu i portu 8765.

Stosy compose:
- Nowe stosy tworzone z panelu trafiają do `AGENT_STACKS_ROOT` (domyślnie `/opt/stacks/<nazwa>/docker-compose.yml`).
- Istniejące, w różnych katalogach: dopisz je do `AGENT_STACK_DIRS` w `/opt/panel-agent/agent.env` (lista po przecinku, każdy katalog z plikiem compose), potem `sudo systemctl restart panel-agent`.
- Agent musi móc zapisywać w tych katalogach i czytać `.env`. Najprościej przez ACL (`sudo apt install acl`):
  `sudo setfacl -R -m u:panel-agent:rwX /ścieżka/stosu && sudo setfacl -R -d -m u:panel-agent:rwX /ścieżka/stosu`
- Edytować można tylko plik compose i `.env` stosu. Zapis compose jest poprzedzony `docker compose config` i kopią `.bak` (ostatnie 5).
