# Panel serwerów (etapy 1–2)
1. `cp .env.example .env` i uzupełnij (SECRET_KEY, DB_PASSWORD, MAIN_HOST).
2. `docker compose up -d --build`
3. Utwórz konto: `docker compose exec web flask --app app create-user ADMIN` (zeskanuj QR w apce 2FA).
4. Udostępnij: `tailscale funnel 8000` (panel nasłuchuje tylko na 127.0.0.1:8000).
Test lokalny bez HTTPS: `COOKIE_SECURE=0` w .env i http://localhost:8000

## Etap 3: WoL i wyłączanie
**Główny serwer (Ubuntu):**
- WoL: włącz w BIOS (Wake on LAN / PCIe wake), w netplanie `wakeonlan: true` dla karty, `sudo netplan apply`. Sprawdź: `ethtool eth0 | grep Wake-on` (ma być `g`).
- Użytkownik do wyłączania: `sudo adduser --disabled-password --gecos "" panel`, potem `sudo visudo -f /etc/sudoers.d/panel`:
  `panel ALL=(root) NOPASSWD: /usr/sbin/shutdown -h now`
- Klucz: na serwerze panelu `mkdir secrets && ssh-keygen -t ed25519 -N "" -f secrets/id_ed25519`, zawartość `.pub` do `~panel/.ssh/authorized_keys` na głównym
  (opcjonalnie z prefiksem `from="IP_PANELU",no-pty,no-port-forwarding `).
- Klucz hosta: `ssh-keyscan -t ed25519 IP_GLOWNEGO > secrets/known_hosts` (zweryfikuj odcisk!).
**Serwer panelu:** uzupełnij nowe zmienne w `.env`, potem `docker compose up -d --build`.
Usługa `wol` słucha na 0.0.0.0:9009 (token). Przy ufw: `sudo ufw allow from 172.16.0.0/12 to any port 9009 proto tcp`
i nie otwieraj tego portu dla LAN (albo ustaw `WOL_BIND` na IP mostu dockera).
