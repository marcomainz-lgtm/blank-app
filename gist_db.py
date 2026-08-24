import os
import json
import requests
import streamlit as st

def get_gist_secrets():
    """Liest die Gist-Geheimnisse aus den Streamlit Secrets."""
    token = st.secrets.get("github_token")
    gist_id = st.secrets.get("gist_id")
    return token, gist_id


def load_gist_file(filename, fallback_default=None):
    """Lädt eine JSON-Datei aus dem privaten GitHub Gist mit lokalem Fallback."""
    token, gist_id = get_gist_secrets()
    
    # Falls die Secrets noch nicht konfiguriert sind, lade die lokale Datei
    if not token or not gist_id or gist_id in ["", "DEINE_GIST_ID_HIER"]:
        if os.path.exists(filename):
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return fallback_default if fallback_default is not None else {}

    headers = {"Authorization": f"token {token}"}
    try:
        r = requests.get(f"https://api.github.com/gists/{gist_id}", headers=headers, timeout=10)
        if r.status_code == 200:
            gist_data = r.json()
            file_info = gist_data.get("files", {}).get(filename)
            if file_info:
                return json.loads(file_info.get("content", "{}"))
    except Exception as e:
        print(f"Fehler beim Laden von Gist-Datei {filename}: {e}")
    
    # Lokaler Cache/Fallback, falls API-Aufruf fehlschlägt
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return fallback_default if fallback_default is not None else {}


def save_gist_file(filename, data):
    """Speichert die JSON-Daten im privaten Gist und schreibt einen lokalen Cache."""
    # Immer auch lokal sichern (Cache)
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception:
        pass

    token, gist_id = get_gist_secrets()
    if not token or not gist_id or gist_id in ["", "DEINE_GIST_ID_HIER"]:
        return

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    payload = {
        "files": {
            filename: {
                "content": json.dumps(data, ensure_ascii=False, indent=4)
            }
        }
    }
    try:
        requests.patch(f"https://api.github.com/gists/{gist_id}", headers=headers, json=payload, timeout=10)
    except Exception as e:
        print(f"Fehler beim Schreiben auf Gist-Datei {filename}: {e}")