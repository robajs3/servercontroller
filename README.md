# Panel serwerów (etapy 1–2)
1. `cp .env.example .env` i uzupełnij (SECRET_KEY, DB_PASSWORD, MAIN_HOST).
2. `docker compose up -d --build`
3. Utwórz konto: `docker compose exec web flask --app app create-user ADMIN` (zeskanuj QR w apce 2FA).
4. Udostępnij: `tailscale funnel 8000` (panel nasłuchuje tylko na 127.0.0.1:8000).
Test lokalny bez HTTPS: `COOKIE_SECURE=0` w .env i http://localhost:8000
