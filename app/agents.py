import os
import requests

def _load():
    out = {}
    for k in filter(None, (x.strip().lower() for x in os.getenv("AGENT_KEYS", "").split(","))):
        K = k.upper()
        out[k] = {"key": k, "name": os.getenv(f"AGENT_{K}_NAME", k),
                  "url": os.environ[f"AGENT_{K}_URL"].rstrip("/"),
                  "token": os.environ[f"AGENT_{K}_TOKEN"],
                  "verify": os.getenv(f"AGENT_{K}_VERIFY", "1") == "1"}
    return out

AGENTS = _load()

def fetch(a):
    r = requests.get(a["url"] + "/metrics", timeout=3, verify=a["verify"],
                     headers={"Authorization": "Bearer " + a["token"]})
    r.raise_for_status()
    return r.json()
