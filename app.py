import streamlit as st
import pandas as pd
import json
import os
import datetime
import re
from zoneinfo import ZoneInfo  # Für die deutsche Zeitzone

# --- HILFSFUNKTION FÜR SAUBERES HTML-RENDERING ---
def clean_html(html_str):
    """Entfernt Zeilenumbrüche und überschüssige Einrückungen, damit der
    Markdown-Parser von Streamlit das HTML nicht fälschlicherweise als Codeblock anzeigt.
    """
    return re.sub(r'\s+', ' ', html_str).strip()


# --- HILFSFUNKTIONEN FÜR DIE URLAUBS-DATENBANK ---
VACATION_FILE = "vacations.json"

def load_vacations():
    if os.path.exists(VACATION_FILE):
        try:
            with open(VACATION_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_vacations(vacations):
    try:
        with open(VACATION_FILE, "w", encoding="utf-8") as f:
            json.dump(vacations, f, ensure_ascii=False, indent=4)
    except Exception:
        pass

def add_vacation(start, end, note):
    vacations = load_vacations()
    v_id = str(int(datetime.datetime.now().timestamp()))
    vacations[v_id] = {
        "id": v_id,
        "start_date": start.strftime("%d.%m.%Y"),
        "end_date": end.strftime("%d.%m.%Y"),
        "note": note
    }
    save_vacations(vacations)

def delete_vacation(v_id):
    vacations = load_vacations()
    if v_id in vacations:
        del vacations[v_id]
        save_vacations(vacations)


# --- SICHERER IMPORT MIT AUTOMATISCHEM FALLBACK ---
try:
    from tracker import check_for_updates_generator, DB_FILE
except ImportError:
    try:
        from tracker import DB_FILE
    except ImportError:
        DB_FILE = "known_tournaments.json"
        
    # Fallback-Generator, falls tracker.py auf dem Server noch alt/gecasht ist
    def check_for_updates_generator():
        yield "⚠️ Hinweis: tracker.py ist auf dem Server noch nicht synchronisiert."
        yield "Führe Standard-Aktualisierung im Hintergrund aus..."
        try:
            from tracker import check_for_updates
            check_for_updates()
            yield "Standard-Aktualisierung erfolgreich beendet!"
        except Exception as e:
            yield f"Fehler bei der Aktualisierung: {e}"


st.set_page_config(page_title="Badminton Turniere für Marco", layout="wide")

# Custom-Logo für Turniere ohne eigenes Emblem
DEFAULT_LOGO = "https://content.tournamentsoftware.com/images/club/72FB92A4-34AF-41F1-8A4E-BBD56634E66E.jpg"

# Alphabetisch sortierte Spielerprofile für Herrendoppel
PARTNERS_HD = {
    "Jan Hammer": "https://dbv.turnier.de/player-profile/9070AF83-4EA3-40E0-B402-F41456147AB5",
    "Jesper Städtler": "https://dbv.turnier.de/player-profile/5CFDBFE1-E055-4479-B657-FD1CB6DEFF48",
    "Karl Olschewski": "https://dbv.turnier.de/player-profile/E2FB7DDF-AB7C-43EE-A78A-389874F1E440",
    "Matthias Knaupp": "https://dbv.turnier.de/player-profile/6DD055FA-B009-4A2B-BBDA-43D15F0F894F",
    "Pascal Ziehe": "https://dbv.turnier.de/player-profile/6c7076f7-d154-4a45-ad71-0b6e2d747b2b"
}

# Alphabetisch sortierte Spielerprofilen für Mixed
PARTNERS_MX = {
    "Thea Renate Sommer": "https://dbv.turnier.de/player-profile/033259D7-903F-4928-B87B-BB8896DBF827",
    "Vanessa Joppien": "https://dbv.turnier.de/player-profile/76DA93E6-43E2-45CE-B28F-FDA12433FDBA"
}

# Custom CSS zur Steuerung der Benutzeroberfläche und der neuen Kacheln
st.markdown(
    """
    <style>
    /* Passwort-Sichtbarkeits-Icon verbergen */
    button[data-testid="stTextInput-VisibilityButton"] {
        display: none !important;
    }
    
    /* Gemeinsame Basis für Static- und Collapsible-Tags */
    .status-tag-static, details.status-tag {
        display: inline-block;
        background-color: #f8fafc;
        border-radius: 6px;
        margin-bottom: 12px;
        font-size: 0.85em;
        line-height: 1.4;
        user-select: none;
    }
    
    /* Statisches Tag */
    .status-tag-static {
        padding: 5px 10px;
        font-weight: bold;
    }
    
    /* Ausklappbares Tag */
    details.status-tag {
        cursor: pointer;
        transition: background-color 0.15s ease-in-out;
    }
    details.status-tag:hover {
        background-color: #f1f5f9;
    }
    details.status-tag summary {
        list-style: none;
        font-weight: bold;
        outline: none;
        padding: 5px 10px;
        display: flex;
        align-items: center;
    }
    details.status-tag summary::-webkit-details-marker {
        display: none;
    }
    
    /* Inhalt des ausgeklappten Tags */
    details.status-tag .status-content {
        font-size: 0.95em;
        padding: 0 10px 8px 10px;
        cursor: default;
    }

    /* --- V3 GRAPHICAL CARD STYLING --- */
    .card-inner-container {
        font-family: 'Inter', -apple-system, sans-serif;
    }
    
    /* Pill Badges */
    .meta-badges-container {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        margin-bottom: 12px;
    }
    .meta-badge {
        font-size: 0.75rem;
        font-weight: 600;
        padding: 3px 8px;
        border-radius: 9999px;
        display: inline-flex;
        align-items: center;
        gap: 4px;
    }
    .loc-badge { background-color: #f1f5f9; color: #334155; }
    .dist-badge { background-color: #fef3c7; color: #b45309; }
    .org-badge { background-color: #ecfeff; color: #0891b2; }
    .date-badge { background-color: #f5f3ff; color: #6d28d9; }
    
    /* Sub-Boxes / Discipline Grid - CAROUSEL-SLIDER AUF MOBILGERÄTEN */
    .discipline-container {
        display: flex;
        gap: 12px;
        margin-top: 10px;
        margin-bottom: 10px;
        flex-wrap: nowrap;
        overflow-x: auto;
        scroll-snap-type: x mandatory;
        -webkit-overflow-scrolling: touch;
        align-items: stretch;
    }
    
    /* Scrollbalken in der Kachelzeile verstecken */
    .discipline-container::-webkit-scrollbar {
        display: none;
    }
    .discipline-container {
        -ms-overflow-style: none;
        scrollbar-width: none;
    }

    .discipline-card {
        flex: 0 1 calc(33.333% - 8px);
        scroll-snap-align: start;
        min-width: 140px;
        background-color: #ffffff !important; /* Reines Weiß für neutrale Kacheln */
        border: 1.5px dashed #cbd5e1 !important; /* Gestrichelter, sauberer Rahmen */
        border-radius: 8px;
        padding: 12px;
        text-align: center;
        box-sizing: border-box;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        min-height: 140px;
        transition: all 0.2s ease-in-out;
    }
    .discipline-card:hover {
        border-color: #94a3b8 !important;
        background-color: #fafafa !important;
        transform: translateY(-1px);
    }
    
    /* STARKES GRÜN bei Anmeldung mit Kontrast-Optimierung */
    .discipline-card.active-registered {
        border: 2.5px solid #16a34a !important;
        background-color: #dcfce7 !important;
        box-shadow: 0 4px 12px rgba(22, 163, 74, 0.25) !important;
        opacity: 1 !important;
    }
    .discipline-card.active-registered .discipline-title {
        color: #14532d !important;
    }
    .discipline-card.active-registered .discipline-day {
        background-color: #bbf7d0 !important;
        color: #15803d !important;
    }
    .discipline-card.active-registered .discipline-status {
        color: #166534 !important;
        font-weight: bold;
    }
    .discipline-card.active-registered .discipline-status a {
        color: #166534 !important;
        text-decoration: underline;
    }

    /* DEAKTIVIERTER / BLOCKIERTENLOOK BEI PARALLELTERMIN (grau) */
    .discipline-card.has-conflict {
        border: 1.5px solid #cbd5e1 !important;
        background-color: #f1f5f9 !important; /* Matt-grauer Hintergrund */
        opacity: 0.9 !important; /* Deutlich erhöhte Lesbarkeit */
    }
    .discipline-card.has-conflict .discipline-title {
        color: #475569 !important;
    }
    .discipline-card.has-conflict .discipline-day {
        background-color: #cbd5e1 !important;
        color: #475569 !important;
    }
    .discipline-card.has-conflict .discipline-status {
        color: #334155 !important; /* Deutlich dunklerer Text für hohen Kontrast */
        font-weight: 600;
    }

    /* KRITISCHER TERMINKONFLIKT BEI DOPPEL-MELDUNG (rot) */
    .discipline-card.has-double-booking {
        border: 2.5px solid #ef4444 !important;
        background-color: #fef2f2 !important;
        box-shadow: 0 4px 12px rgba(239, 68, 68, 0.15) !important;
        opacity: 1 !important;
    }
    .discipline-card.has-double-booking .discipline-title {
        color: #991b1b !important;
    }
    .discipline-card.has-double-booking .discipline-day {
        background-color: #fee2e2 !important;
        color: #991b1b !important;
    }
    .discipline-card.has-double-booking .discipline-status {
        color: #dc2626 !important;
        font-weight: bold;
    }

    /* URLAUBS-LOOK FÜR EINZELNE KACHELN (blau / soft) */
    .discipline-card.is-vacation {
        border: 1.5px dashed #60a5fa !important; /* Gestrichelte, weiche blaue Linie */
        background-color: #f0f7ff !important; /* Sanfteres Pastel-Blau */
        box-shadow: none !important; /* Aufdringlichen Schatten entfernt */
        opacity: 0.85 !important; /* Leicht transparent zur Signalisierung eines passiven Zustands */
    }
    .discipline-card.is-vacation .discipline-title {
        color: #2563eb !important;
    }
    .discipline-card.is-vacation .discipline-day {
        background-color: #dbeafe !important;
        color: #1e40af !important;
    }
    .discipline-status.vacation-status {
        color: #2563eb !important;
        font-weight: bold;
    }

    .discipline-icon {
        font-size: 1.15rem;
        margin-bottom: 2px;
    }
    .discipline-title {
        font-weight: 700;
        font-size: 0.8rem;
        color: #1e293b;
        text-transform: uppercase;
        letter-spacing: 0.3px;
    }
    
    /* Datum an erster Stelle (Badge) - ZEILENUMBRUCH ERZWUNGEN */
    .discipline-day {
        font-size: 0.75rem;
        color: #475569;
        font-weight: 700;
        margin-bottom: 6px;
        background-color: #e2e8f0;
        padding: 4px 8px;
        border-radius: 4px;
        display: inline-block;
        line-height: 1.25;
    }
    
    /* Neutraler TBA-Style für unklare Spieltage */
    .discipline-day.tba-day {
        background-color: #f1f5f9 !important;
        color: #94a3b8 !important;
        border: 1px dashed #cbd5e1;
    }

    .discipline-status {
        font-size: 0.75rem;
        color: #64748b; /* Aufgewertetes, lesbares Neutral-Grau für Nicht gemeldet */
    }
    .discipline-status a {
        color: #15803d;
        text-decoration: underline;
        font-weight: 600;
    }
    .discipline-status.registered {
        color: #15803d;
        font-weight: bold;
    }

    /* SMARTPHONE RESPONSIVE CAROUSEL SLIDER - EXTREM KOMPAKT */
    @media (max-width: 768px) {
        .discipline-container {
            gap: 8px !important;
        }
        .discipline-card {
            flex: 0 0 29% !important; /* Auf 29% verengt für maximale Übersicht */
            min-width: 85px !important;
            min-height: 100px !important;
            padding: 6px 4px !important;
        }
        .discipline-icon {
            font-size: 0.85rem !important;
        }
        .discipline-title {
            font-size: 0.65rem !important;
        }
        .discipline-day {
            font-size: 0.6rem !important;
            padding: 2px 4px !important;
            margin-bottom: 2px !important;
            line-height: 1.15 !important;
        }
        .discipline-status {
            font-size: 0.55rem !important;
            line-height: 1.1 !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Login-Session-State initialisieren
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

# Constrain the login field width by placing it in a top-right column
col_spacer, col_login = st.columns([4, 1])
with col_login:
    if st.session_state['logged_in']:
        if st.button("Abmelden", use_container_width=True, key="logout_btn"):
            st.session_state['logged_in'] = False
            if 'secret_login' in st.session_state:
                st.session_state['secret_login'] = ""
            st.rerun()
    else:
        admin_password = st.text_input(
            "", 
            type="password", 
            label_visibility="collapsed", 
            placeholder="Admin Login", 
            key="secret_login"
        )
        if admin_password == "marco2026":
            st.session_state['logged_in'] = True
            st.rerun()

IS_ADMIN = st.session_state['logged_in']

# Title & Subtitle
st.title("🏸 Badminton Turniere für Marco")
st.write("Auf dieser Seite findet ihr alle Seniorenturniere 2026, die im Umkreis von 100 Kilometern um Hilden (40723) stattfinden.")

# Retrieve DB modification timestamp (konvertiert in deutsche Uhrzeit)
last_retrieved_str = "Unbekannt"
if os.path.exists(DB_FILE):
    try:
        last_modified = os.path.getmtime(DB_FILE)
        last_retrieved_dt = datetime.datetime.fromtimestamp(last_modified, tz=ZoneInfo("Europe/Berlin"))
        last_retrieved_str = last_retrieved_dt.strftime("%d.%m.%Y um %H:%M Uhr")
    except Exception:
        pass

st.caption(f"🕒 Letztes Update der Datenbank: {last_retrieved_str}")

# --- ZENTRALER URLAUBSPLANER (NUR FÜR ADMINS SICHTBAR) ---
if IS_ADMIN:
    with st.expander("🌴 Urlaubsplaner (Admin)", expanded=False):
        st.subheader("Urlaubszeiträume verwalten")
        
        # Formular zum Hinzufügen von neuen Urlauben
        with st.form("add_vacation_form", clear_on_submit=True):
            col_start, col_end, col_note = st.columns(3)
            with col_start:
                new_start = st.date_input("Startdatum", value=datetime.date.today(), format="DD.MM.YYYY")
            with col_end:
                new_end = st.date_input("Enddatum", value=datetime.date.today(), format="DD.MM.YYYY")
            with col_note:
                new_note = st.text_input("Bezeichnung / Notiz (optional)", placeholder="z. B. Sommerurlaub")
            
            if st.form_submit_button("Urlaubszeitraum hinzufügen"):
                if new_start <= new_end:
                    add_vacation(new_start, new_end, new_note)
                    st.toast("Urlaub erfolgreich hinzugefügt!")
                    st.rerun()
                else:
                    st.error("Das Startdatum muss vor oder am Enddatum liegen.")
        
        # Liste aller eingetragenen Urlaube anzeigen mit Lösch-Button
        vacations_data = load_vacations()
        if vacations_data:
            st.markdown("---")
            st.markdown("Eingetragene Urlaubszeiträume:")
            for v_id, v in list(vacations_data.items()):
                v_col_info, v_col_btn = st.columns([5, 1])
                with v_col_info:
                    note_suffix = f" (*{v['note']}*)" if v['note'] else ""
                    st.markdown(f"🌴 **{v['start_date']}** bis **{v['end_date']}**{note_suffix}")
                with v_col_btn:
                    if st.button("Zeitraum löschen", key=f"del_v_{v_id}", use_container_width=True):
                        delete_vacation(v_id)
                        st.toast("Urlaub gelöscht!")
                        st.rerun()
        else:
            st.info("Noch keine Urlaubszeiträume eingetragen.")

# Database update trigger (mit robustem Aktivitätsprotokoll)
if IS_ADMIN:
    if st.button("Datenbank aktualisieren"):
        log_container = st.empty()
        logs = []
        with st.status("Verbindung zu turnier.de wird hergestellt...", expanded=True) as status:
            for log_line in check_for_updates_generator():
                logs.append(log_line)
                log_container.code("\n".join(logs))
            status.update(label="Datenbank erfolgreich aktualisiert!", state="complete", expanded=False)
        st.toast("Datenbank erfolgreich aktualisiert!")
        st.rerun()


# --- DYNAMISCHE HILFSFUNKTIONEN FÜR DATUM UND WOCHENTAGE ---
def get_tournament_day_options(start_date_obj, end_date_obj):
    """Generiert eine dynamische Liste aller echten Turniertage plus der Option 'Disziplin findet nicht statt'."""
    weekday_names = {
        0: "Montag", 1: "Dienstag", 2: "Mittwoch", 3: "Donnerstag",
        4: "Freitag", 5: "Samstag", 6: "Sonntag"
    }
    options = ["-- Tag wählen --", "Disziplin findet nicht statt"]
    if pd.isnull(start_date_obj) or pd.isnull(end_date_obj):
        return options
    
    current_date = start_date_obj
    limit = 0
    while current_date <= end_date_obj and limit < 20:
        day_name = weekday_names[current_date.weekday()]
        formatted_date = current_date.strftime("%d.%m.")
        options.append(f"{day_name}, {formatted_date}")
        current_date += datetime.timedelta(days=1)
        limit += 1
        
    return options


def get_date_for_weekday(day_selection, start_date_obj, end_date_obj):
    """Findet das erste Datum im Turnierzeitraum, das dem ausgewählten Wochentag entspricht."""
    if not day_selection or day_selection in ["-- Tag wählen --", "Keine Angabe", "Disziplin findet nicht statt", ""]:
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
            
            # Matcht entweder das neue präzise Datumsformat ODER das alte reine Wochentagsformat
            if day_selection == current_day_str or day_selection == day_name:
                return current_date
            current_date += datetime.timedelta(days=1)
            limit += 1
    except Exception:
        pass
    return None


def can_still_register(item, vacation_dates, occupied_dates):
    """Prüft, ob ein Turnier noch offen für Anmeldungen in mindestens einer angebotenen
    Disziplin ist, für die der Nutzer noch nicht gemeldet ist und an deren Spieltag er Zeit hat.
    """
    start_date_obj = item['Start_Date_Obj']
    end_date_obj = item['End_Date_Obj']
    if pd.isnull(start_date_obj) or pd.isnull(end_date_obj):
        return True

    # Wir prüfen alle drei Disziplinen
    disciplines = [
        ('he', item.get('day_he', ''), bool(item.get('reg_he', False)), bool(item.get('full_he', False))),
        ('hd', item.get('day_hd', ''), bool(item.get('reg_hd', False)), bool(item.get('full_hd', False))),
        ('mx', item.get('day_mx', ''), bool(item.get('reg_mx', False)), bool(item.get('full_mx', False))),
    ]

    for key, day_val, is_reg, is_full in disciplines:
        # 1. Wenn die Disziplin gar nicht stattfindet oder voll ist, überspringen
        if day_val == "Disziplin findet nicht statt" or is_full:
            continue
            
        # 2. Wenn wir für diese Disziplin bereits gemeldet sind, ist diese spezifische Disziplin nicht mehr "offen"
        if is_reg:
            continue
            
        # 3. Wenn noch kein Wochentag festgelegt ist (TBA), gehen wir davon aus, dass eine Anmeldung theoretisch möglich ist
        if not day_val or day_val in ["-- Tag wählen --", "TBA", "Keine Angabe"]:
            return True
            
        # 4. Wenn ein Spieltag feststeht, muss dieser Tag frei von Urlaub und anderen Turnieren sein
        dt = get_date_for_weekday(day_val, start_date_obj, end_date_obj)
        if dt:
            # Ist an diesem Tag Urlaub?
            if dt in vacation_dates:
                continue
                
            # Sind wir an diesem Tag bereits bei einem ANDEREN Turnier gemeldet?
            has_other_tournament_conflict = False
            if dt in occupied_dates:
                for conflict in occupied_dates[dt]:
                    if conflict["title"] != item["title"]:
                        has_other_tournament_conflict = True
                        break
            
            if has_other_tournament_conflict:
                continue
                
            # Wenn der Tag frei ist (kein Urlaub, kein anderes Turnier), können wir uns hier anmelden!
            return True
        else:
            # Fallback falls Datumsermittlung scheitert, aber Tag existiert
            return True

    return False


# --- V3 GRAPHICAL RENDERING ENGINE ---
def render_styled_tournament_card(item, occupied_dates, vacation_dates, vacation_notes):
    """Erzeugt eine visuell ansprechende Kachel mit dynamic SVGs, Pill-Badges und Sub-Boxes für Disziplinen."""
    city = item.get('city', 'Unbekannt')
    title = item.get('title', 'Turnier')
    dist = item.get('distance')
    dist_str = f"{dist} km" if dist is not None else "Keine Angabe"
    
    # 1. Gastgeber-Zusatz "NRW - " filtern
    org_str = item.get('organizer', 'Unbekannt')
    if org_str.startswith("NRW - "):
        org_str = org_str[len("NRW - "):].strip()
    
    # 2. Datumsbereich berechnen
    start_str = item.get('start_date')
    end_str = item.get('end_date')
    if start_str and end_str:
        if start_str == end_str:
            date_range_str = start_str
        else:
            try:
                s_parts = start_str.split('.')
                e_parts = end_str.split('.')
                if len(s_parts) == 3 and len(e_parts) == 3 and s_parts[2] == e_parts[2]:
                    date_range_str = f"{s_parts[0]}.{s_parts[1]}. - {e_parts[0]}.{e_parts[1]}.{e_parts[2]}"
                else:
                    date_range_str = f"{start_str} - {end_str}"
            except Exception:
                date_range_str = f"{start_str} - {end_str}"
    else:
        date_range_str = "Datum unbekannt"

    # Erstelle die Wochentag-Werte für die Cards
    day_he = item.get('day_he', '')
    day_hd = item.get('day_hd', '')
    day_mx = item.get('day_mx', '')

    # Status & Registrierungen
    reg_he = bool(item.get('reg_he', False))
    reg_hd = bool(item.get('reg_hd', False))
    reg_mx = bool(item.get('reg_mx', False))

    # Feld-Voll-Zustände auslesen
    he_full = bool(item.get('full_he', False))
    hd_full = bool(item.get('full_hd', False))
    mx_full = bool(item.get('full_mx', False))

    partner_hd = item.get('partner_hd', '').strip()
    partner_mx = item.get('partner_mx', '').strip()

    start_date_obj = item['Start_Date_Obj']
    end_date_obj = item['End_Date_Obj']

    # Backend-Abwahl direkt über das Zeitplan-Dropdown steuern
    has_he = (day_he != "Disziplin findet nicht statt")
    has_hd = (day_hd != "Disziplin findet nicht statt")
    has_mx = (day_mx != "Disziplin findet nicht statt")

    # Helper zur Formatierung des Kachel-Datum-Badges (erster Platz in Kachel mit Zeilenumbruch!)
    def format_day_badge(day_val, s_obj, e_obj):
        if not day_val or day_val == "-- Tag wählen --" or day_val == "TBA":
            return "TBA"
        if day_val == "Disziplin findet nicht statt":
            return "Gestrichen"
        
        # Versuche ein präzises Datum zu ermitteln
        dt = get_date_for_weekday(day_val, s_obj, e_obj)
        if dt:
            weekday_names = {
                0: "Montag", 1: "Dienstag", 2: "Mittwoch", 3: "Donnerstag",
                4: "Freitag", 5: "Samstag", 6: "Sonntag"
            }
            w_name = weekday_names[dt.weekday()]
            # Zeilenumbruch anstelle des Kommas für einheitliche Kachelhöhen
            return f"{w_name}<br>{dt.strftime('%d.%m.')}"
        
        # Fallback für manuelle Altdaten aus der Datenbank
        if isinstance(day_val, str) and "," in day_val:
            parts = day_val.split(",")
            return f"{parts[0].strip()}<br>{parts[1].strip()}"
        
        return day_val

    # Bestimme den anzuzeigenden Text für den Spieltag (TBA als Default)
    display_day_he = format_day_badge(day_he, start_date_obj, end_date_obj)
    display_day_hd = format_day_badge(day_hd, start_date_obj, end_date_obj)
    display_day_mx = format_day_badge(day_mx, start_date_obj, end_date_obj)

    day_class_he = "tba-day" if display_day_he == "TBA" else ""
    day_class_hd = "tba-day" if display_day_hd == "TBA" else ""
    day_class_mx = "tba-day" if display_day_mx == "TBA" else ""

    # Badges-Leiste aufbauen (Datum an erster Stelle!)
    badges_html = f"""
    <div class="meta-badges-container">
        <span class="meta-badge date-badge">📅 {date_range_str}</span>
        <span class="meta-badge loc-badge">📍 {city}</span>
        <span class="meta-badge dist-badge">🚗 {dist_str}</span>
        <span class="meta-badge org-badge">🛡️ {org_str}</span>
    </div>
    """

    # Sub-Boxen für Disziplinen mit globaler Belegungsprüfung, Doppel-Meldungs-Erkennung & feingranularem Urlaubsschutz
    
    # -- Einzel --
    he_class = "active-registered" if reg_he else ""
    he_status_class = "registered" if reg_he else ""
    he_status_text = "Gemeldet" if reg_he else "Nicht gemeldet"
    he_icon = "👤"
    
    if he_full:
        if reg_he:
            he_status_text = "Gemeldet (Feld voll)"
        else:
            he_status_text = "🔒 Feld voll"
            he_status_class = "conflict"
            he_class = "has-conflict"
    else:
        dt_he = get_date_for_weekday(day_he, start_date_obj, end_date_obj)
        
        if dt_he and dt_he in vacation_dates:
            vac_note = vacation_notes.get(dt_he, "")
            he_status_text = f"🏖️ Urlaub: {vac_note}" if vac_note else "🏖️ Urlaub"
            he_status_class = "vacation-status"
            he_class = "is-vacation"
        elif dt_he and dt_he in occupied_dates:
            other_regs = [c for c in occupied_dates[dt_he] if c["title"] != title]
            if other_regs:
                conflict = other_regs[0]
                p_suffix = f" mit {conflict['partner']}" if conflict['partner'] else ""
                if reg_he:
                    he_status_text = f"Terminkonflikt: {conflict['disc']} in {conflict['city']}{p_suffix}"
                    he_status_class = "double-booking"
                    he_class = "has-double-booking"
                else:
                    he_status_text = f"Paralleltermin: {conflict['disc']} in {conflict['city']}{p_suffix}"
                    he_status_class = "conflict"
                    he_class = "has-conflict"
    
    # -- Doppel --
    hd_class = "active-registered" if reg_hd else ""
    hd_status_class = "registered" if reg_hd else ""
    hd_icon = "👥"
    if reg_hd:
        if partner_hd and partner_hd in PARTNERS_HD:
            hd_status_text = f"Mit <a href='{PARTNERS_HD[partner_hd]}' target='_blank'>{partner_hd}</a>"
        elif partner_hd:
            hd_status_text = f"Mit {partner_hd}"
        else:
            hd_status_text = "Ohne Partner"
    else:
        hd_status_text = "Nicht gemeldet"
        
    if hd_full:
        if reg_hd:
            if partner_hd and partner_hd in PARTNERS_HD:
                hd_status_text = f"Mit <a href='{PARTNERS_HD[partner_hd]}' target='_blank'>{partner_hd}</a> (Feld voll)"
            elif partner_hd:
                hd_status_text = f"Mit {partner_hd} (Feld voll)"
            else:
                hd_status_text = "Ohne Partner (Feld voll)"
        else:
            hd_status_text = "🔒 Feld voll"
            hd_status_class = "conflict"
            hd_class = "has-conflict"
    else:
        dt_hd = get_date_for_weekday(day_hd, start_date_obj, end_date_obj)
        
        if dt_hd and dt_hd in vacation_dates:
            vac_note = vacation_notes.get(dt_hd, "")
            hd_status_text = f"🏖️ Urlaub: {vac_note}" if vac_note else "🏖️ Urlaub"
            hd_status_class = "vacation-status"
            hd_class = "is-vacation"
        elif dt_hd and dt_hd in occupied_dates:
            other_regs = [c for c in occupied_dates[dt_hd] if c["title"] != title]
            if other_regs:
                conflict = other_regs[0]
                p_suffix = f" mit {conflict['partner']}" if conflict['partner'] else ""
                if reg_hd:
                    hd_status_text = f"Terminkonflikt: {conflict['disc']} in {conflict['city']}{p_suffix}"
                    hd_status_class = "double-booking"
                    hd_class = "has-double-booking"
                else:
                    hd_status_text = f"Paralleltermin: {conflict['disc']} in {conflict['city']}{p_suffix}"
                    hd_status_class = "conflict"
                    hd_class = "has-conflict"

    # -- Mixed --
    mx_class = "active-registered" if reg_mx else ""
    mx_status_class = "registered" if reg_mx else ""
    mx_icon = "👥"
    if reg_mx:
        if partner_mx and partner_mx in PARTNERS_MX:
            mx_status_text = f"Mit <a href='{PARTNERS_MX[partner_mx]}' target='_blank'>{partner_mx}</a>"
        elif partner_mx:
            mx_status_text = f"Mit {partner_mx}"
        else:
            mx_status_text = "Ohne Partnerin"
    else:
        mx_status_text = "Nicht gemeldet"
        
    if mx_full:
        if reg_mx:
            if partner_mx and partner_mx in PARTNERS_MX:
                mx_status_text = f"Mit <a href='{PARTNERS_MX[partner_mx]}' target='_blank'>{partner_mx}</a> (Feld voll)"
            elif partner_mx:
                mx_status_text = f"Mit {partner_mx} (Feld voll)"
            else:
                mx_status_text = "Ohne Partnerin (Feld voll)"
        else:
            mx_status_text = "🔒 Feld voll"
            mx_status_class = "conflict"
            mx_class = "has-conflict"
    else:
        dt_mx = get_date_for_weekday(day_mx, start_date_obj, end_date_obj)
        
        if dt_mx and dt_mx in vacation_dates:
            vac_note = vacation_notes.get(dt_mx, "")
            mx_status_text = f"🏖️ Urlaub: {vac_note}" if vac_note else "🏖️ Urlaub"
            mx_status_class = "vacation-status"
            mx_class = "is-vacation"
        elif dt_mx and dt_mx in occupied_dates:
            other_regs = [c for c in occupied_dates[dt_mx] if c["title"] != title]
            if other_regs:
                conflict = other_regs[0]
                p_suffix = f" mit {conflict['partner']}" if conflict['partner'] else ""
                if reg_mx:
                    mx_status_text = f"Terminkonflikt: {conflict['disc']} in {conflict['city']}{p_suffix}"
                    mx_status_class = "double-booking"
                    mx_class = "has-double-booking"
                else:
                    mx_status_text = f"Paralleltermin: {conflict['disc']} in {conflict['city']}{p_suffix}"
                    mx_status_class = "conflict"
                    mx_class = "has-conflict"

    # Nur Kacheln rendern, die im Backend erlaubt sind (Datum steht an erster Stelle!)
    he_card = f"""
    <div class="discipline-card {he_class}">
        <div>
            <div class="discipline-day {day_class_he}">{display_day_he}</div>
            <div class="discipline-icon">{he_icon}</div>
            <div class="discipline-title">Einzel</div>
        </div>
        <div class="discipline-status {he_status_class}">{he_status_text}</div>
    </div>
    """ if has_he else ""

    hd_card = f"""
    <div class="discipline-card {hd_class}">
        <div>
            <div class="discipline-day {day_class_hd}">{display_day_hd}</div>
            <div class="discipline-icon">{hd_icon}</div>
            <div class="discipline-title">Doppel</div>
        </div>
        <div class="discipline-status {hd_status_class}">{hd_status_text}</div>
    </div>
    """ if has_hd else ""

    mx_card = f"""
    <div class="discipline-card {mx_class}">
        <div>
            <div class="discipline-day {day_class_mx}">{display_day_mx}</div>
            <div class="discipline-icon">{mx_icon}</div>
            <div class="discipline-title">Mixed</div>
        </div>
        <div class="discipline-status {mx_status_class}">{mx_status_text}</div>
    </div>
    """ if has_mx else ""

    disciplines_html = f"""
    <div class="discipline-container">
        {he_card}
        {hd_card}
        {mx_card}
    </div>
    """ if (has_he or has_hd or has_mx) else ""

    # HTML Output generieren (Ohne Überschrift / Emblem im HTML)
    html_out = f"""
    <div class="card-inner-container">
        {badges_html}
        {disciplines_html}
    </div>
    """
    st.markdown(clean_html(html_out), unsafe_allow_html=True)


# Load and present database
if os.path.exists(DB_FILE):
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}

    if data:
        # Build DataFrame
        df = pd.DataFrame(data.values())
        
        # Fallbacks für ältere oder neue Datenbank-Spalten
        fallback_cols = {
            'registered': False,
            'reg_he': False,
            'reg_hd': False,
            'reg_mx': False,
            'full_he': False,
            'full_hd': False,
            'full_mx': False,
            'partner_hd': '',
            'partner_mx': '',
            'day_he': '',
            'day_hd': '',
            'day_mx': '',
            'participation_day': 'Keine Angabe',
            'logo_url': '',
            'city': 'Unbekannt',
            'distance': None,
            'start_date': None,
            'end_date': None,
            'organizer': 'Unbekannt',
            'description': ''
        }
        for col, default in fallback_cols.items():
            if col not in df.columns:
                df[col] = default
            else:
                df[col] = df[col].fillna(default)
        
        # Datentypen für die Checkbox-Spalten erzwingen
        for col in ['registered', 'reg_he', 'reg_hd', 'reg_mx', 'full_he', 'full_hd', 'full_mx']:
            df[col] = df[col].astype(bool)

        # Convert dates for chronological sorting
        df['Start_Date_Obj'] = pd.to_datetime(df['start_date'], format='%d.%m.%Y', errors='coerce').dt.date
        df['End_Date_Obj'] = pd.to_datetime(df['end_date'], format='%d.%m.%Y', errors='coerce').dt.date

        # --- EXCLUDE FILTER FÜR AUSGEBLENDETE TURNIERE ---
        EXCLUDED_KEYWORDS = ["2. DBV-RLT O19 2026", "TEST"]
        df = df[~df['title'].str.contains('|'.join(EXCLUDED_KEYWORDS), case=False, na=False)]

        # --- DYNAMISCHE ERMITTLUNG ALLER ZENTRALEN URLAUBS-TERMINE ---
        vacation_dates = set()
        vacation_notes = {}
        
        vacations_data = load_vacations()
        for v in vacations_data.values():
            try:
                v_start_dt = datetime.datetime.strptime(v['start_date'], "%d.%m.%Y").date()
                v_end_dt = datetime.datetime.strptime(v['end_date'], "%d.%m.%Y").date()
                
                curr_date = v_start_dt
                limit_dt = 0
                while curr_date <= v_end_dt and limit_dt < 100:
                    vacation_dates.add(curr_date)
                    if v.get('note'):
                        vacation_notes[curr_date] = v['note']
                    curr_date += datetime.timedelta(days=1)
                    limit_dt += 1
            except Exception as e:
                pass

        # --- DYNAMISCHE ERMITTLUNG ALLER BELEGTEN SPIELTAGE ---
        occupied_dates = {}
        
        df_registered = df[df['registered'] == True].copy()
        for idx, r_item in df_registered.iterrows():
            r_start = r_item['Start_Date_Obj']
            r_end = r_item['End_Date_Obj']
            r_title = r_item['title']
            r_city = r_item['city']
            
            if pd.isnull(r_start) or pd.isnull(r_end):
                continue
                
            if r_item.get('reg_he') and r_item.get('day_he'):
                dt = get_date_for_weekday(r_item['day_he'], r_start, r_end)
                if dt: 
                    occupied_dates.setdefault(dt, []).append({
                        "disc": "Herreneinzel",
                        "city": r_city,
                        "title": r_title,
                        "partner": ""
                    })
            if r_item.get('reg_hd') and r_item.get('day_hd'):
                dt = get_date_for_weekday(r_item['day_hd'], r_start, r_end)
                if dt:
                    p_hd = r_item.get('partner_hd', '').strip()
                    if p_hd == "-- Kein Partner --": p_hd = ""
                    occupied_dates.setdefault(dt, []).append({
                        "disc": "Herrendoppel",
                        "city": r_city,
                        "title": r_title,
                        "partner": p_hd
                    })
            if r_item.get('reg_mx') and r_item.get('day_mx'):
                dt = get_date_for_weekday(r_item['day_mx'], r_start, r_end)
                if dt:
                    p_mx = r_item.get('partner_mx', '').strip()
                    if p_mx == "-- Kein Partner --": p_mx = ""
                    occupied_dates.setdefault(dt, []).append({
                        "disc": "Mixed",
                        "city": r_city,
                        "title": r_title,
                        "partner": p_mx
                    })
                    
            has_any_day = (r_item.get('day_he') or r_item.get('day_hd') or r_item.get('day_mx'))
            if not has_any_day:
                active_discs = []
                if r_item.get('reg_he'): 
                    active_discs.append({"name": "Herreneinzel", "partner": ""})
                if r_item.get('reg_hd'): 
                    p_hd = r_item.get('partner_hd', '').strip()
                    if p_hd == "-- Kein Partner --": p_hd = ""
                    active_discs.append({"name": "Herrendoppel", "partner": p_hd})
                if r_item.get('reg_mx'): 
                    p_mx = r_item.get('partner_mx', '').strip()
                    if p_mx == "-- Kein Partner --": p_mx = ""
                    active_discs.append({"name": "Mixed", "partner": p_mx})
                if not active_discs:
                    active_discs = [{"name": "Turnier", "partner": ""}]
                
                curr_date = r_start
                while curr_date <= r_end:
                    for disc_info in active_discs:
                        occupied_dates.setdefault(curr_date, []).append({
                            "disc": disc_info["name"], 
                            "city": r_city, 
                            "title": r_title,
                            "partner": disc_info["partner"]
                        })
                    curr_date += datetime.timedelta(days=1)

        # Aktuelles Datum in deutscher Zeitzone abrufen
        try:
            today = datetime.datetime.now(ZoneInfo("Europe/Berlin")).date()
        except Exception:
            today = datetime.date.today()

        # Split data chronologically
        df_upcoming = df[df['End_Date_Obj'] >= today].copy()
        df_upcoming = df_upcoming.sort_values(by='Start_Date_Obj', ascending=True)

        # Split data chronologically for past
        df_past = df[df['End_Date_Obj'] < today].copy()
        df_past = df_past.sort_values(by='Start_Date_Obj', ascending=False)


        # --- MELDUNGS- UND VERFÜGBARKEITSFILTER ---
        st.write("")
        st.markdown("### Filter")
        
        only_registered = st.toggle("Turniere, an denen ich angemeldet bin", value=False)
        only_available = st.toggle("Turniere, an denen ich mich noch anmelden kann", value=False)

        if only_registered or only_available:
            def row_passes_filter(row):
                is_reg = bool(row.get('registered', False))
                is_avail = can_still_register(row, vacation_dates, occupied_dates)
                if only_registered and only_available:
                    return is_reg or is_avail
                elif only_registered:
                    return is_reg
                elif only_available:
                    return is_avail
                return True

            df_upcoming = df_upcoming[df_upcoming.apply(row_passes_filter, axis=1)]
            df_past = df_past[df_past.apply(row_passes_filter, axis=1)]


        month_names = {
            1: "Januar", 2: "Februar", 3: "März", 4: "April",
            5: "Mai", 6: "Juni", 7: "Juli", 8: "August",
            9: "September", 10: "Oktober", 11: "November", 12: "Dezember"
        }

        # --- A. UPCOMING TOURNAMENTS ---
        st.subheader(f"📅 Anstehende Turniere ({len(df_upcoming)})")
        
        with st.expander("Anstehende Turniere anzeigen", expanded=True):
            if not df_upcoming.empty:
                current_month_str = ""
                for idx, item in df_upcoming.iterrows():
                    start_date = item['Start_Date_Obj']
                    
                    if pd.isnull(start_date):
                        item_month_str = "Datum unbekannt"
                    else:
                        item_month_str = f"{month_names[start_date.month]} {start_date.year}"
                    
                    if item_month_str != current_month_str:
                        current_month_str = item_month_str
                        st.write("")
                        st.markdown(f"#### 📆 {current_month_str}")
                    
                    with st.container(border=True):
                        col_logo, col_info, col_link = st.columns([1.5, 6, 2])
                        
                        with col_logo:
                            logo_to_show = item['logo_url']
                            if not logo_to_show or "no-photo" in logo_to_show:
                                logo_to_show = DEFAULT_LOGO
                            st.image(logo_to_show, width=140)
                                
                        with col_info:
                            # NATIVE ÜBERSCHRIFT WIEDER GEWÜNSCHT (OHNE BADMINTON-SCHLÄGER)
                            st.markdown(f"### {item['title']}")

                            # RENDERE DIE SPEZIELLE TURNIERKACHEL (DYNAMISCH)
                            render_styled_tournament_card(item, occupied_dates, vacation_dates, vacation_notes)
                            
                            # Admin-Ansicht
                            if IS_ADMIN:
                                st.write("---")
                                
                                # Collapsible für den Original-Ausschreibungstext
                                desc_text = item.get('description', '').strip()
                                if desc_text:
                                    with st.expander("📝 Ausschreibungstext von turnier.de anzeigen", expanded=False):
                                        st.write(desc_text)
                                
                                start_date_obj = item['Start_Date_Obj']
                                end_date_obj = item['End_Date_Obj']
                                day_options = get_tournament_day_options(start_date_obj, end_date_obj)

                                # Dropdowns zur Zuweisung des Zeitplans (Disziplin findet nicht statt direkt im Dropdown!)
                                st.markdown("**Allgemeiner Zeitplan (Für alle Kacheln sichtbar):**")
                                col_day_he, col_day_hd, col_day_mx = st.columns(3)
                                
                                with col_day_he:
                                    val_day_he_db = item.get('day_he', '')
                                    he_idx = 0
                                    if val_day_he_db:
                                        for o_idx, opt in enumerate(day_options):
                                            if opt == val_day_he_db or opt.startswith(val_day_he_db):
                                                he_idx = o_idx
                                                break
                                    selected_label_he = st.selectbox("Spieltag Einzel", options=day_options, index=he_idx, key=f"day_he_{item['id']}")
                                    val_day_he = selected_label_he if selected_label_he != "-- Tag wählen --" else ""
                                    
                                with col_day_hd:
                                    val_day_hd_db = item.get('day_hd', '')
                                    hd_idx = 0
                                    if val_day_hd_db:
                                        for o_idx, opt in enumerate(day_options):
                                            if opt == val_day_hd_db or opt.startswith(val_day_hd_db):
                                                hd_idx = o_idx
                                                break
                                    selected_label_hd = st.selectbox("Spieltag Doppel", options=day_options, index=hd_idx, key=f"day_hd_{item['id']}")
                                    val_day_hd = selected_label_hd if selected_label_hd != "-- Tag wählen --" else ""
                                    
                                with col_day_mx:
                                    val_day_mx_db = item.get('day_mx', '')
                                    mx_idx = 0
                                    if val_day_mx_db:
                                        for o_idx, opt in enumerate(day_options):
                                            if opt == val_day_mx_db or opt.startswith(val_day_mx_db):
                                                mx_idx = o_idx
                                                break
                                    selected_label_mx = st.selectbox("Spieltag Mixed", options=day_options, index=mx_idx, key=f"day_mx_{item['id']}")
                                    val_day_mx = selected_label_mx if selected_label_mx != "-- Tag wählen --" else ""

                                # Checkboxen für "Feld voll" (Sperren der Anmeldung bei laufendem Spieltag)
                                col_full_he, col_full_hd, col_full_mx = st.columns(3)
                                with col_full_he:
                                    val_full_he = st.checkbox("Feld voll (Einzel)", value=bool(item.get('full_he', False)), key=f"full_he_{item['id']}")
                                with col_full_hd:
                                    val_full_hd = st.checkbox("Feld voll (Doppel)", value=bool(item.get('full_hd', False)), key=f"full_hd_{item['id']}")
                                with col_full_mx:
                                    val_full_mx = st.checkbox("Feld voll (Mixed)", value=bool(item.get('full_mx', False)), key=f"full_mx_{item['id']}")

                                # Checkboxen für die persönliche Anmeldung
                                st.write("")
                                st.markdown("**Meine Anmeldung (Für das grüne Banner):**")
                                col_he, col_hd, col_mx = st.columns(3)
                                
                                with col_he:
                                    val_he = st.checkbox("Meldung Einzel", value=bool(item.get('reg_he', False)), key=f"he_{item['id']}")
                                        
                                with col_hd:
                                    val_hd = st.checkbox("Meldung Doppel", value=bool(item.get('reg_hd', False)), key=f"hd_{item['id']}")
                                    val_partner_hd = item.get('partner_hd', '')
                                    
                                    if val_hd:
                                        hd_options = ["-- Kein Partner --"] + list(PARTNERS_HD.keys())
                                        default_idx_hd = hd_options.index(val_partner_hd) if val_partner_hd in hd_options else 0
                                        val_partner_hd = st.selectbox("Partner Herrendoppel", options=hd_options, index=default_idx_hd, key=f"p_hd_{item['id']}")
                                        if val_partner_hd == "-- Kein Partner --":
                                            val_partner_hd = ""
                                    else:
                                        val_partner_hd = ""
                                        
                                with col_mx:
                                    val_mx = st.checkbox("Meldung Mixed", value=bool(item.get('reg_mx', False)), key=f"mx_{item['id']}")
                                    val_partner_mx = item.get('partner_mx', '')
                                    
                                    if val_mx:
                                        mx_options = ["-- Kein Partner --"] + list(PARTNERS_MX.keys())
                                        default_idx_mx = mx_options.index(val_partner_mx) if val_partner_mx in mx_options else 0
                                        val_partner_mx = st.selectbox("Partner Mixed", options=mx_options, index=default_idx_mx, key=f"p_mx_{item['id']}")
                                        if val_partner_mx == "-- Kein Partner --":
                                            val_partner_mx = ""
                                    else:
                                        val_partner_mx = ""
                                        
                                is_registered = (val_he or val_hd or val_mx)
                                
                                has_changed = (
                                    val_he != bool(item.get('reg_he', False)) or
                                    val_hd != bool(item.get('reg_hd', False)) or
                                    val_mx != bool(item.get('reg_mx', False)) or
                                    val_full_he != bool(item.get('full_he', False)) or
                                    val_full_hd != bool(item.get('full_hd', False)) or
                                    val_full_mx != bool(item.get('full_mx', False)) or
                                    val_partner_hd != item.get('partner_hd', '') or
                                    val_partner_mx != item.get('partner_mx', '') or
                                    val_day_he != item.get('day_he', '') or
                                    val_day_hd != item.get('day_hd', '') or
                                    val_day_mx != item.get('day_mx', '')
                                )
                                
                                if has_changed:
                                    data[item['id']]['registered'] = is_registered
                                    data[item['id']]['reg_he'] = val_he
                                    data[item['id']]['reg_hd'] = val_hd
                                    data[item['id']]['reg_mx'] = val_mx
                                    data[item['id']]['full_he'] = val_full_he
                                    data[item['id']]['full_hd'] = val_full_hd
                                    data[item['id']]['full_mx'] = val_full_mx
                                    data[item['id']]['partner_hd'] = val_partner_hd
                                    data[item['id']]['partner_mx'] = val_partner_mx
                                    data[item['id']]['day_he'] = val_day_he
                                    data[item['id']]['day_hd'] = val_day_hd
                                    data[item['id']]['day_mx'] = val_day_mx
                                    
                                    with open(DB_FILE, "w", encoding="utf-8") as f:
                                        json.dump(data, f, ensure_ascii=False, indent=4)
                                    st.rerun()
                            
                        with col_link:
                            st.write("")
                            st.write("")
                            st.link_button("Turnierseite", item['link'], use_container_width=True)
            else:
                st.info("Keine anstehenden Turniere gefunden.")

        st.write("")
        st.write("")

        # --- B. PAST TOURNAMENTS ---
        st.subheader(f"🕰️ Vergangene Turniere ({len(df_past)})")
        
        with st.expander("Vergangene Turniere anzeigen", expanded=False):
            if not df_past.empty:
                current_month_str = ""
                for idx, item in df_past.iterrows():
                    start_date = item['Start_Date_Obj']
                    
                    if pd.isnull(start_date):
                        item_month_str = "Datum unbekannt"
                    else:
                        item_month_str = f"{month_names[start_date.month]} {start_date.year}"
                    
                    if item_month_str != current_month_str:
                        current_month_str = item_month_str
                        st.write("")
                        st.markdown(f"#### 🕰️ {current_month_str}")
                    
                    with st.container(border=True):
                        col_logo, col_info, col_link = st.columns([1.5, 6, 2])
                        
                        with col_logo:
                            logo_to_show = item['logo_url']
                            if not logo_to_show or "no-photo" in logo_to_show:
                                logo_to_show = DEFAULT_LOGO
                            st.image(logo_to_show, width=140)
                                
                        with col_info:
                            # NATIVE ÜBERSCHRIFT BEENDET WIEDER GEWÜNSCHT (OHNE BADMINTON-SCHLÄGER)
                            st.markdown(f"### {item['title']} *(Beendet)*")

                            # RENDERE DIE SPEZIELLE TURNIERKACHEL (DYNAMISCH)
                            render_styled_tournament_card(item, occupied_dates, vacation_dates, vacation_notes)
                            
                            # Admin-Ansicht
                            if IS_ADMIN:
                                st.write("---")
                                start_date_obj = item['Start_Date_Obj']
                                end_date_obj = item['End_Date_Obj']
                                day_options = get_tournament_day_options(start_date_obj, end_date_obj)
                                
                                col_past_he, col_past_hd, col_past_mx = st.columns(3)

                                with col_past_he:
                                    st.markdown("**Herreneinzel**")
                                    val_he = st.checkbox("Herreneinzel", value=bool(item.get('reg_he', False)), key=f"he_past_{item['id']}")
                                    val_full_he = st.checkbox("Feld voll (Einzel)", value=bool(item.get('full_he', False)), key=f"full_he_past_{item['id']}")
                                    val_day_he_db = item.get('day_he', '')
                                    if val_he:
                                        he_idx = 0
                                        if val_day_he_db:
                                            for o_idx, opt in enumerate(day_options):
                                                if opt == val_day_he_db or opt.startswith(val_day_he_db):
                                                    he_idx = o_idx
                                                    break
                                        selected_label_he = st.selectbox("Spieltag Einzel", options=day_options, index=he_idx, key=f"day_he_past_{item['id']}")
                                        val_day_he = selected_label_he if selected_label_he != "-- Tag wählen --" else ""
                                    else:
                                        val_day_he = ""
                                
                                with col_past_hd:
                                    st.markdown("**Herrendoppel**")
                                    val_hd = st.checkbox("Herrendoppel", value=bool(item.get('reg_hd', False)), key=f"hd_past_{item['id']}")
                                    val_full_hd = st.checkbox("Feld voll (Doppel)", value=bool(item.get('full_hd', False)), key=f"full_hd_past_{item['id']}")
                                    val_partner_hd = item.get('partner_hd', '')
                                    val_day_hd_db = item.get('day_hd', '')
                                    
                                    if val_hd:
                                        hd_options = ["-- Kein Partner --"] + list(PARTNERS_HD.keys())
                                        default_idx_hd = hd_options.index(val_partner_hd) if val_partner_hd in hd_options else 0
                                        val_partner_hd = st.selectbox("Partner Herrendoppel", options=hd_options, index=default_idx_hd, key=f"p_hd_past_{item['id']}")
                                        if val_partner_hd == "-- Kein Partner --":
                                            val_partner_hd = ""
                                            
                                        hd_idx = 0
                                        if val_day_hd_db:
                                            for o_idx, opt in enumerate(day_options):
                                                if opt == val_day_hd_db or opt.startswith(val_day_hd_db):
                                                    hd_idx = o_idx
                                                    break
                                        selected_label_hd = st.selectbox("Spieltag Doppel", options=day_options, index=hd_idx, key=f"day_hd_past_{item['id']}")
                                        val_day_hd = selected_label_hd if selected_label_hd != "-- Tag wählen --" else ""
                                    else:
                                        val_partner_hd = ""
                                        val_day_hd = ""
                                
                                with col_past_mx:
                                    st.markdown("**Mixed**")
                                    val_mx = st.checkbox("Mixed", value=bool(item.get('reg_mx', False)), key=f"mx_past_{item['id']}")
                                    val_full_mx = st.checkbox("Feld voll (Mixed)", value=bool(item.get('full_mx', False)), key=f"full_mx_past_{item['id']}")
                                    val_partner_mx = item.get('partner_mx', '')
                                    val_day_mx_db = item.get('day_mx', '')
                                    
                                    if val_mx:
                                        mx_options = ["-- Kein Partner --"] + list(PARTNERS_MX.keys())
                                        default_idx_mx = mx_options.index(val_partner_mx) if val_partner_mx in mx_options else 0
                                        val_partner_mx = st.selectbox("Partner Mixed", options=mx_options, index=default_idx_mx, key=f"p_mx_past_{item['id']}")
                                        if val_partner_mx == "-- Kein Partner --":
                                            val_partner_mx = ""
                                            
                                        mx_idx = 0
                                        if val_day_mx_db:
                                            for o_idx, opt in enumerate(day_options):
                                                if opt == val_day_mx_db or opt.startswith(val_day_mx_db):
                                                    mx_idx = o_idx
                                                    break
                                        selected_label_mx = st.selectbox("Spieltag Mixed", options=day_options, index=mx_idx, key=f"day_mx_past_{item['id']}")
                                        val_day_mx = selected_label_mx if selected_label_mx != "-- Tag wählen --" else ""
                                    else:
                                        val_partner_mx = ""
                                        val_day_mx = ""
                                        
                                is_registered = (val_he or val_hd or val_mx)
                                
                                has_changed = (
                                    val_he != bool(item.get('reg_he', False)) or
                                    val_hd != bool(item.get('reg_hd', False)) or
                                    val_mx != bool(item.get('reg_mx', False)) or
                                    val_full_he != bool(item.get('full_he', False)) or
                                    val_full_hd != bool(item.get('full_hd', False)) or
                                    val_full_mx != bool(item.get('full_mx', False)) or
                                    val_partner_hd != item.get('partner_hd', '') or
                                    val_partner_mx != item.get('partner_mx', '') or
                                    val_day_he != item.get('day_he', '') or
                                    val_day_hd != item.get('day_hd', '') or
                                    val_day_mx != item.get('day_mx', '')
                                )
                                
                                if has_changed:
                                    data[item['id']]['registered'] = is_registered
                                    data[item['id']]['reg_he'] = val_he
                                    data[item['id']]['reg_hd'] = val_hd
                                    data[item['id']]['reg_mx'] = val_mx
                                    data[item['id']]['full_he'] = val_full_he
                                    data[item['id']]['full_hd'] = val_full_hd
                                    data[item['id']]['full_mx'] = val_full_mx
                                    data[item['id']]['partner_hd'] = val_partner_hd
                                    data[item['id']]['partner_mx'] = val_partner_mx
                                    data[item['id']]['day_he'] = val_day_he
                                    data[item['id']]['day_hd'] = val_day_hd
                                    data[item['id']]['day_mx'] = val_day_mx
                                    
                                    with open(DB_FILE, "w", encoding="utf-8") as f:
                                        json.dump(data, f, ensure_ascii=False, indent=4)
                                    st.rerun()
                            
                        with col_link:
                            st.write("")
                            st.write("")
                            st.link_button("Turnierseite", item['link'], use_container_width=True)
            else:
                st.info("Keine vergangenen Turniere gefunden.")
    else:
        st.info("Der Suchlauf war erfolgreich, aber es wurden keine Turniere in Ihrem Umkreis gefunden.")
else:
    st.warning("Keine Turnier-Datenbank gefunden. Bitte wenden Sie sich an den Administrator, um den ersten Suchlauf durchzuführen.")