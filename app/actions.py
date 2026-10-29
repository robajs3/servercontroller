import os, urllib.request
import paramiko

HOST = os.environ["MAIN_HOST"]
SSH_PORT = int(os.getenv("MAIN_SSH_PORT", 22))
SSH_USER = os.getenv("MAIN_SSH_USER", "panel")
SSH_KEY = os.getenv("SSH_KEY_PATH", "/secrets/id_ed25519")
KNOWN_HOSTS = os.getenv("SSH_KNOWN_HOSTS", "/secrets/known_hosts")
WOL_URL = os.getenv("WOL_URL", "http://host.docker.internal:9009")

def wake():
    req = urllib.request.Request(WOL_URL + "/wake", method="POST",
                                 headers={"X-Token": os.environ["WOL_TOKEN"]})
    with urllib.request.urlopen(req, timeout=5):
        pass

def shutdown():
    c = paramiko.SSHClient()
    c.load_host_keys(KNOWN_HOSTS)
    c.set_missing_host_key_policy(paramiko.RejectPolicy())  # tylko znany klucz hosta
    try:
        c.connect(HOST, port=SSH_PORT, username=SSH_USER, key_filename=SSH_KEY,
                  timeout=5, banner_timeout=5, auth_timeout=5,
                  look_for_keys=False, allow_agent=False)
        _, out, err = c.exec_command("sudo -n /usr/sbin/shutdown -h now", timeout=10)
        if out.channel.recv_exit_status() != 0:
            raise RuntimeError(err.read().decode(errors="replace").strip() or "shutdown nie powiódł się")
    finally:
        c.close()
