import os
import json
import requests
import streamlit as st

class DatabaseConnectionError(Exception):
    """Wird ausgelöst, wenn keine sichere Verbindung zur Cloud-Datenbank besteht."""
    pass

def get_gist_secrets():
    """Liest die Gist-Geheimnisse aus den Streamlit Secrets oder den Umgebungsvariablen."""
    token = os.environ.get("GIST_TOKEN")
    gist_id = os.environ.get("GIST_ID")
    
    if not token or not gist_id:
        try:
            if "github_token" in st.secrets:
                token = st.secrets["github_token"]
            if "gist_id" in st.secrets:
                gist_id = st.secrets["gist_id"]
        except Exception:
            pass
            
    return token, gist_id


def load_gist_file(filename):
    """
    Lädt eine JSON-Datei aus dem privaten GitHub Gist.
    Wirft DatabaseConnectionError bei fehlenden Secrets oder Verbindungsabbrüchen.
    """
    token, gist_id = get_gist_secrets()
    
    # 1. Haben wir gültige Secrets?
    if not token or not gist_id or gist_id in ["", "DEINE_GIST_ID_HIER"]:
        # Notfall: Existiert zumindest eine lokale Cache-Datei auf der Festplatte?
        if os.path.exists(filename):
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                raise DatabaseConnectionError(f"Lokale Datei '{filename}' beschädigt: {e}")
        raise DatabaseConnectionError(
            f"FEHLENDE SECRETS: Weder 'github_token' noch 'gist_id' gefunden und keine lokale Datei '{filename}' vorhanden."
        )

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # 2. Versuch, das Gist abzurufen
    try:
        r = requests.get(f"https://api.github.com/gists/{gist_id}", headers=headers, timeout=12)
        
        if r.status_code == 200:
            gist_data = r.json()
            file_info = gist_data.get("files", {}).get(filename)
            if file_info:
                content = file_info.get("content")
                # Große Dateien werden von GitHub gekürzt -> raw_url laden
                if content is None or file_info.get("truncated", False):
                    raw_url = file_info.get("raw_url")
                    if raw_url:
                        raw_r = requests.get(raw_url, headers=headers, timeout=12)
                        return raw_r.json()
                    raise DatabaseConnectionError(f"Datei '{filename}' im Gist hat keinen lesbaren Inhalt.")
                return json.loads(content)
            else:
                # Datei existiert im Gist noch nicht (z. B. initialer Start)
                return {}
        elif r.status_code in [401, 403]:
            raise DatabaseConnectionError(f"GitHub Auth-Fehler ({r.status_code}): Token ungültig, abgelaufen oder ohne 'gist'-Scope.")
        elif r.status_code == 404:
            raise DatabaseConnectionError(f"GitHub Gist-ID '{gist_id}' existiert nicht (404 Not Found).")
        else:
            raise DatabaseConnectionError(f"GitHub API meldet Fehler {r.status_code}: {r.text}")
            
    except requests.exceptions.RequestException as e:
        # Falls Internet/GitHub ausfällt, lokalen Cache als Notfalloption probieren
        if os.path.exists(filename):
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    print(f"⚠️ Netzwerkfehler ({e}). Verwende lokalen Notfall-Cache.")
                    return json.load(f)
            except Exception:
                pass
        raise DatabaseConnectionError(f"Netzwerkverbindung zum GitHub Gist fehlgeschlagen: {e}")


def save_gist_file(filename, data):
    """Speichert die JSON-Daten im privaten Gist und aktualisiert den lokalen Cache."""
    token, gist_id = get_gist_secrets()
    if not token or not gist_id or gist_id in ["", "DEINE_GIST_ID_HIER"]:
        raise DatabaseConnectionError("Speichern unmöglich: Keine Gist-Zugangsdaten konfiguriert!")

    # Immer auch lokal zur Sicherheit spiegeln
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Warnung lokaler Cache: {e}")

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
        r = requests.patch(f"https://api.github.com/gists/{gist_id}", headers=headers, json=payload, timeout=12)
        if r.status_code != 200:
            raise DatabaseConnectionError(f"Fehler beim Speichern im Gist ({r.status_code}): {r.text}")
    except requests.exceptions.RequestException as e:
        raise DatabaseConnectionError(f"Netzwerkfehler beim Speichern im Gist: {e}")