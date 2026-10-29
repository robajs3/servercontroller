"""Mikrousługa WoL: działa w network_mode: host, żeby broadcast wyszedł do LAN.
Wysyła magic packet WYŁĄCZNIE na MAC z .env (z requestu nie przyjmuje żadnych danych)."""
import hmac, os, socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TOKEN = os.environ["WOL_TOKEN"].encode()
MAC = bytes.fromhex(os.environ["MAIN_MAC"].replace(":", "").replace("-", ""))
BCAST = os.getenv("WOL_BROADCAST", "255.255.255.255")
BIND, PORT = os.getenv("WOL_BIND", "0.0.0.0"), int(os.getenv("WOL_PORT", 9009))
assert len(MAC) == 6, "MAIN_MAC musi mieć 6 bajtów"

def send_magic():
    pkt = b"\xff" * 6 + MAC * 16
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        for port in (9, 7):
            s.sendto(pkt, (BCAST, port))

class H(BaseHTTPRequestHandler):
    def do_POST(self):
        got = self.headers.get("X-Token", "").encode()
        if self.path != "/wake" or not hmac.compare_digest(got, TOKEN):
            self.send_response(403); self.end_headers(); return
        try:
            send_magic(); code = 200
        except OSError:
            code = 500
        self.send_response(code); self.end_headers()
    def log_message(self, *a): pass

ThreadingHTTPServer((BIND, PORT), H).serve_forever()
