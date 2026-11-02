# Biblioteki frontendu (serwowane lokalnie)

Panel steruje serwerem, więc nie ładuje skryptów z CDN (brak zależności od zewnętrznego hosta
i ryzyka podmiany pliku). Pliki pochodzą bez zmian z paczek npm; wersje przypięte.

| Plik | Pakiet npm | Licencja | SHA-256 pliku |
|---|---|---|---|
| htmx-1.9.12.min.js | htmx.org@1.9.12 (dist/htmx.min.js) | 0BSD | `449317ade7881e949510db614991e195c3a099c4c791c24dacec55f9f4a2a452` |
| chart-4.4.1.umd.js | chart.js@4.4.1 (dist/chart.umd.js) | MIT | `74401d738dd3e03ee5dfb3b6841210fe2c4ead8a960c4011ca4ba0b78a9fd8f3` |

Integralność paczek w rejestrze npm (`npm view <pakiet> dist.integrity`):
- htmx.org@1.9.12: `sha512-VZAohXyF7xPGS52IM8d1T1283y+X4D+Owf3qY1NZ9RuBypyu9l8cGsxUMAG5fEAb/DhT7rDoJ9Hpu5/HxFD3cw==`
- chart.js@4.4.1: `sha512-C74QN1bxwV1v2PEujhmKjOZ7iUM4w6BWs23Md/6aOZZSlwMzeCIDGuZay++rBgChYru7/+QFeoQW0fQoP534Dg==`

Aktualizacja: `npm pack <pakiet>@<wersja>`, podmień plik, zaktualizuj nazwę w szablonach i sumy powyżej.
