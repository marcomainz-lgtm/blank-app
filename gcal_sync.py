import streamlit as st
import datetime
import hashlib
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Hilfsfunktion zur Ermittlung des konkreten Datums
def get_date_for_weekday(day_selection, start_date_str, end_date_str):
    if not day_selection or day_selection in ["-- Tag wählen --", "Keine Angabe", "Disziplin findet nicht statt", ""]:
        return None
    try:
        start_date_obj = pd.to_datetime(start_date_str, format='%d.%m.%Y', errors='coerce').date()
        end_date_obj = pd.to_datetime(end_date_str, format='%d.%m.%Y', errors='coerce').date()
    except Exception:
        return None
        
    if pd.isnull(start_date_obj) or pd.isnull(end_date_obj):
        return None
    
    weekday_names = {
        0: "Montag", 1: "Dienstag", 2: "Mittwoch", 3: "Donnerstag",
        4: "Freitag", 5: "Samstag", 6: "Sonntag"
    }
    
    try:
        current_date = start_date_obj
        limit = 0
        while current_date <= end_date_obj and limit < 20:
            day_name = weekday_names[current_date.weekday()]
            formatted_dt_short = current_date.strftime("%d.%m.")
            current_day_str = f"{day_name}, {formatted_dt_short}"
            
            if day_selection == current_day_str or day_selection == day_name:
                return current_date
            current_date += datetime.timedelta(days=1)
            limit += 1
    except Exception:
        pass
    return None


def get_gcal_service():
    """Initialisiert den Google Calendar API Client mithilfe von Streamlit Secrets."""
    if "gcp_service_account" not in st.secrets:
        return None
    try:
        info = dict(st.secrets["gcp_service_account"])
        if "private_key" in info:
            info["private_key"] = info["private_key"].replace("\\n", "\n")
            
        scopes = ["https://www.googleapis.com/auth/calendar"]
        creds = service_account.Credentials.from_service_account_info(info, scopes=scopes)
        return build("calendar", "v3", credentials=creds)
    except Exception as e:
        print(f"Fehler bei Google Service-Account Initialisierung: {e}")
        return None


def sync_tournament_to_gcal(item):
    """Synchronisiert alle Disziplinen eines Turniers mit dem Google Kalender."""
    service = get_gcal_service()
    if not service:
        raise Exception("Google Service Account konnte nicht initialisiert werden. Überprüfe die Secrets.")
        
    calendar_id = st.secrets.get("calendar_id")
    if not calendar_id:
        raise Exception("'calendar_id' fehlt in den Streamlit Secrets.")

    t_id = item.get("id")
    title = item.get("title", "Turnier")
    city = item.get("city", "Unbekannt")
    dist = item.get("distance")
    dist_str = f"{dist} km" if dist is not None else "Keine Angabe"
    organizer = item.get("organizer", "Unbekannt")
    link = item.get("link", "")

    # Definition der drei Disziplinen
    disciplines = [
        ("he", "Herreneinzel", bool(item.get("reg_he", False)), item.get("day_he", ""), ""),
        ("hd", "Herrendoppel", bool(item.get("reg_hd", False)), item.get("day_hd", ""), item.get("partner_hd", "")),
        ("mx", "Mixed", bool(item.get("reg_mx", False)), item.get("day_mx", ""), item.get("partner_mx", ""))
    ]

    for disc_key, disc_name, is_registered, day_selection, partner in disciplines:
        # Erzeuge eine eindeutige ID für diesen Event
        event_id = hashlib.md5(f"{t_id}_{disc_key}".encode()).hexdigest()
        
        # Bestimme das konkrete Datum für den Spieltag
        dt = get_date_for_weekday(day_selection, item.get("start_date"), item.get("end_date"))
        
        # Falls gemeldet UND Spieltag bekannt -> Event eintragen oder aktualisieren
        if is_registered and dt:
            start_date_str = dt.strftime("%Y-%m-%d")
            end_date_str = (dt + datetime.timedelta(days=1)).strftime("%Y-%m-%d")

            description_lines = [
                f"Ausrichter: {organizer}",
                f"Turnierseite: {link}"
            ]
            if partner:
                description_lines.append(f"Partner: {partner}")
                
            event_payload = {
                "summary": f"🏸 {disc_name} - {title}",
                "location": f"{city} ({dist_str})",
                "description": "\n".join(description_lines),
                "start": {
                    "date": start_date_str
                },
                "end": {
                    "date": end_date_str
                }
            }

            try:
                # Prüfe ob Event bereits existiert
                service.events().get(calendarId=calendar_id, eventId=event_id).execute()
                # Update
                service.events().update(calendarId=calendar_id, eventId=event_id, body=event_payload).execute()
            except HttpError as e:
                if e.resp.status == 404:
                    # Neu erstellen mit der deterministischen ID
                    event_payload["id"] = event_id
                    service.events().insert(calendarId=calendar_id, body=event_payload).execute()
                else:
                    raise e
            except Exception as e:
                raise e
                
        else:
            # Falls nicht gemeldet -> Event löschen falls vorhanden
            try:
                service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
            except HttpError as e:
                if e.resp.status != 404:  # Ignoriere Fehler, wenn Event sowieso nicht existierte
                    raise e
            except Exception as e:
                raise e