"""Spoločný pomocník pre testy: vytvorenie/prihlásenie účtu cez MAS (mas-cli + compat /login)."""
import subprocess
from pathlib import Path

SERVER = Path(__file__).resolve().parents[2] / "server"


def ensure_user(session, base, user, password):
    """Vytvorí účet v MAS (alebo mu nastaví heslo) a vráti odpoveď compat /login (access_token, user_id)."""
    def mas(*args):
        return subprocess.run(["docker", "compose", "exec", "-T", "mas", "mas-cli", "manage", *args,
                               "--config", "/config/config.yaml"], cwd=SERVER, capture_output=True, text=True)
    p = mas("register-user", "--yes", user, "--password", password, "--ignore-password-complexity")
    if p.returncode != 0:
        if "already exists" not in p.stderr:
            raise RuntimeError(p.stderr[-300:])
        mas("set-password", user, password, "--ignore-complexity")
    r = session.post(f"{base}/_matrix/client/v3/login", json={
        "type": "m.login.password", "identifier": {"type": "m.id.user", "user": user}, "password": password})
    r.raise_for_status()
    return r.json()
