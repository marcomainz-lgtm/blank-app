import os
import sys
import datetime

print("--- GOOGLE CALENDAR DIAGNOSTIK-TOOL ---")

# Prüfe, ob secrets.toml existiert
secrets_path = ".streamlit/secrets.toml"
if not os.path.exists(secrets_path):
    print("❌ Fehler: '.streamlit/secrets.toml' existiert nicht in deinem Projektordner.")
    print("Bitte erstelle diese Datei lokal in deinem Codespace und trage deine Secrets dort ein, wie beschrieben.")
    sys.exit(1)

try:
    import tomllib  # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        print("Installiere 'tomli' für die Diagnose...")
        os.system(f"{sys.executable} -m pip install tomli")
        import tomli as tomllib

with open(secrets_path, "rb") as f:
    try:
        secrets = tomllib.load(f)
    except Exception as e:
        print(f"❌ Fehler beim Parsen von 'secrets.toml': {e}")
        sys.exit(1)

if "calendar_id" not in secrets:
    print("❌ Fehler: 'calendar_id' fehlt in den Secrets.")
else:
    print(f"✅ 'calendar_id' gefunden: {secrets['calendar_id']}")

if "gcp_service_account" not in secrets:
    print("❌ Fehler: '[gcp_service_account]' Sektion fehlt in den Secrets.")
    sys.exit(1)
else:
    print("✅ '[gcp_service_account]' Sektion gefunden.")

gcp = secrets["gcp_service_account"]
required_keys = ["type", "project_id", "private_key_id", "private_key", "client_email", "client_id"]
missing_keys = [k for k in required_keys if k not in gcp]
if missing_keys:
    print(f"❌ Fehler: Folgende Schlüssel fehlen im Service-Account: {missing_keys}")
    sys.exit(1)
else:
    print("✅ Alle erforderlichen Service-Account-Felder sind vorhanden.")

# Versuche benötigte Bibliotheken zu laden/installieren
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
except ImportError:
    print("Installiere benötigte Google-Bibliotheken...")
    os.system(f"{sys.executable} -m pip install google-api-python-client google-auth")
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

print("\nVerbinde mit der Google Calendar API...")
try:
    info = dict(gcp)
    if "private_key" in info:
        pk = info["private_key"]
        # Bereinige Windows-Zeilenumbrüche (\r\n) und maskierte Umbrüche (\\n)
        pk = pk.replace("\r\n", "\n").replace("\\n", "\n")
        # Entferne Leerzeichen am Zeilenanfang/-ende
        pk = "\n".join([line.strip() for line in pk.split("\n") if line.strip()])
        info["private_key"] = pk
        
    scopes = ["https://www.googleapis.com/auth/calendar"]
    creds = service_account.Credentials.from_service_account_info(info, scopes=scopes)
    service = build("calendar", "v3", credentials=creds)
    print("✅ Verbindung zur Google API erfolgreich aufgebaut.")
except Exception as e:
    print(f"❌ Authentifizierungsfehler bei Google: {e}")
    sys.exit(1)

calendar_id = secrets["calendar_id"]
print(f"Prüfe Zugriff auf den Kalender: '{calendar_id}'...")
try:
    cal = service.calendars().get(calendarId=calendar_id).execute()
    print(f"\n🎉 ERFOLG! Der Kalender wurde gefunden und ist erreichbar.")
    print(f"Kalendertitel: {cal.get('summary')}")
    print(f"Zeitzone: {cal.get('timeZone')}")
except Exception as e:
    print("\n❌ Fehler beim Zugriff auf den Kalender!")
    print(f"Fehlermeldung von Google: {e}")
    print("\n💡 Häufige Ursachen:")
    print("1. Google Calendar API ist in der GCP-Konsole nicht aktiviert.")
    print("   -> Gehe in die Google Cloud Console und klicke bei 'Google Calendar API' auf 'Aktivieren'.")
    print("2. Der Kalender wurde nicht mit dem Dienstkonto geteilt.")
    print(f"   -> Teile deinen Kalender in den Google Kalender-Einstellungen mit: {gcp.get('client_email')}")
    print("   -> Berechtigung MUSS auf 'Termine verwalten und Freigabe verwalten' stehen.")
    print("3. Die 'calendar_id' in den Secrets ist falsch.")
    print("   -> Nutze für deinen Hauptkalender deine persönliche Google E-Mail-Adresse.")
    print("   -> Nutze für einen separaten Kalender die ID aus den Kalendereinstellungen (endet auf @group.calendar.google.com).")