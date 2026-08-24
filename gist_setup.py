import os
import json
import requests
import sys

print("--- AUTOMATISCHER GIST SETUP GENERATOR ---")

token = input("Bitte gib deinen soeben erstellten GitHub Token (PAT) ein: ").strip()
if not token:
    print("❌ Fehler: Token darf nicht leer sein.")
    sys.exit(1)

# Lese bestehende JSON-Dateien ein, um sie in die Cloud zu migrieren
known_tournaments = {}
if os.path.exists("known_tournaments.json"):
    try:
        with open("known_tournaments.json", "r", encoding="utf-8") as f:
            known_tournaments = json.load(f)
    except Exception:
        pass

vacations = {}
if os.path.exists("vacations.json"):
    try:
        with open("vacations.json", "r", encoding="utf-8") as f:
            vacations = json.load(f)
    except Exception:
        pass

print("\nErstelle privates GitHub Gist...")
headers = {
    "Authorization": f"token {token}",
    "Accept": "application/vnd.github.v3+json"
}
payload = {
    "description": "Zentrale Cloud-Datenbank fuer Badminton Turniere App",
    "public": False,
    "files": {
        "known_tournaments.json": {
            "content": json.dumps(known_tournaments, ensure_ascii=False, indent=4)
        },
        "vacations.json": {
            "content": json.dumps(vacations, ensure_ascii=False, indent=4)
        }
    }
}

try:
    r = requests.post("https://api.github.com/gists", headers=headers, json=payload, timeout=10)
    if r.status_code == 201:
        gist_id = r.json()["id"]
        print(f"🎉 ERFOLG! Privates Gist erfolgreich erstellt.")
        print(f"Deine neue Gist-ID lautet: {gist_id}")
        
        # Lokale secrets.toml anpassen
        secrets_path = ".streamlit/secrets.toml"
        os.makedirs(".streamlit", exist_ok=True)
        
        existing_lines = []
        if os.path.exists(secrets_path):
            with open(secrets_path, "r", encoding="utf-8") as f:
                existing_lines = f.readlines()
                
        # Alte github_token / gist_id Zeilen entfernen, um Duplikate zu vermeiden
        cleaned_lines = [line for line in existing_lines if not (line.startswith("github_token") or line.startswith("gist_id"))]
        
        with open(secrets_path, "w", encoding="utf-8") as f:
            f.write(f'github_token = "{token}"\n')
            f.write(f'gist_id = "{gist_id}"\n')
            f.writelines(cleaned_lines)
            
        print(f"\n✅ Secrets wurden erfolgreich lokal in '{secrets_path}' eingetragen!")
        print("\n💡 Wichtige nächste Schritte:")
        print("1. Kopiere diese beiden neuen Zeilen aus deiner lokalen 'secrets.toml':")
        print(f'   github_token = "{token}"')
        print(f'   gist_id = "{gist_id}"')
        print("   und füge sie online in deine Streamlit Cloud Secrets ein (unter den GCP Service Account).")
        print("2. Führe im Terminal den Git-Push-Befehl aus, um die Code-Anpassungen hochzuladen.")
    else:
        print(f"❌ Fehler beim Erstellen des Gists: {r.status_code}")
        print(r.text)
except Exception as e:
    print(f"❌ Netzwerkfehler beim API-Aufruf: {e}")