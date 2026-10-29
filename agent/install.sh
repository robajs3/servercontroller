#!/usr/bin/env bash
# Uruchom jako root z katalogu agent/:  sudo ./install.sh
set -euo pipefail
[ "$EUID" -eq 0 ] || { echo "Uruchom przez sudo"; exit 1; }
D=/opt/panel-agent
id panel-agent &>/dev/null || useradd --system --home "$D" --shell /usr/sbin/nologin panel-agent
mkdir -p "$D" && cp ./*.py requirements.txt "$D/"
apt-get install -y python3-venv >/dev/null
python3 -m venv "$D/venv" && "$D/venv/bin/pip" install -q -r "$D/requirements.txt"
if getent group docker >/dev/null; then usermod -aG docker panel-agent; else echo "UWAGA: brak grupy docker, funkcje Dockera nie zadziałają"; fi
docker compose version >/dev/null 2>&1 || echo "UWAGA: brak wtyczki 'docker compose' (sudo apt install docker-compose-v2)"
mkdir -p /opt/stacks && chown panel-agent:panel-agent /opt/stacks
if [ ! -f "$D/agent.env" ]; then
  TOKEN=$(python3 -c "import secrets;print(secrets.token_hex(24))")
  cat > "$D/agent.env" <<ENV
AGENT_TOKEN=$TOKEN
AGENT_BIND=0.0.0.0
AGENT_PORT=8765
# HTTPS (opcjonalnie), odkomentuj po wygenerowaniu certyfikatu:
# GUNICORN_CMD_ARGS=--certfile=/opt/panel-agent/cert.pem --keyfile=/opt/panel-agent/key.pem
ENV
  chmod 600 "$D/agent.env"
  echo ">>> TOKEN agenta (wklej do .env panelu): $TOKEN"
fi
cp panel-agent.service /etc/systemd/system/
grep -q AGENT_STACK_DIRS "$D/agent.env" || cat >> "$D/agent.env" <<ENV

# Stosy compose: nowe stosy tworzone są w AGENT_STACKS_ROOT, istniejące dodaj w AGENT_STACK_DIRS (lista po przecinku)
AGENT_STACKS_ROOT=/opt/stacks
AGENT_STACK_DIRS=
ENV
systemctl daemon-reload && systemctl enable panel-agent && systemctl restart panel-agent
systemctl --no-pager status panel-agent | head -5
