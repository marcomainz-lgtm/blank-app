import streamlit as st
import pandas as pd
import json
import os
import datetime
from zoneinfo import ZoneInfo  # Für die deutsche Zeitzone

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
    "Dominik Gric": "https://dbv.turnier.de/player-profile/B6646621-C82C-4FEF-B7F1-42FC2A947DCD",
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

# Custom CSS to hide the password visibility button (the eye icon)
st.markdown(
    """
    <style>
    button[data-testid="stTextInput-VisibilityButton"] {
        display: none !important;
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

# Database update trigger (mit robustem Aktivitätsprotokoll-Fallback)
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

# --- MELDUNGSFILTER (TOGGLE) ---
only_registered = st.toggle("Nur gemeldete Turniere anzeigen", value=False)


# --- DYNAMISCHE HILFSFUNKTIONEN FÜR DATUM UND WOCHENTAGE ---
def get_tournament_day_options(start_date_obj, end_date_obj):
    """Generiert eine dynamische Liste aller echten Turniertage (z. B. nur Samstag, wenn das Turnier eintägig ist)."""
    weekday_names = {
        0: "Montag", 1: "Dienstag", 2: "Mittwoch", 3: "Donnerstag",
        4: "Freitag", 5: "Samstag", 6: "Sonntag"
    }
    if pd.isnull(start_date_obj) or pd.isnull(end_date_obj):
        return ["-- Tag wählen --"]
    
    day_options = ["-- Tag wählen --"]
    current_date = start_date_obj
    limit = 0
    while current_date <= end_date_obj and limit < 10:
        day_name = weekday_names[current_date.weekday()]
        formatted_date = current_date.strftime("%d.%m.")
        day_options.append(f"{day_name}, {formatted_date}")
        current_date += datetime.timedelta(days=1)
        limit += 1
        
    return day_options


def get_date_for_weekday(day_selection, start_date_obj, end_date_obj):
    """Findet das erste Datum im Turnierzeitraum, das dem ausgewählten Wochentag entspricht."""
    if not day_selection or day_selection in ["-- Tag wählen --", "Keine Angabe", ""]:
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
        while current_date <= end_date_obj and limit < 10:
            day_name = weekday_names[current_date.weekday()]
            if day_name == day_selection:
                return current_date
            current_date += datetime.timedelta(days=1)
            limit += 1
    except Exception:
        pass
    return None


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
            'organizer': 'Unbekannt'
        }
        for col, default in fallback_cols.items():
            if col not in df.columns:
                df[col] = default
            else:
                df[col] = df[col].fillna(default)
        
        # Datentypen für die Checkbox-Spalten erzwingen
        for col in ['registered', 'reg_he', 'reg_hd', 'reg_mx']:
            df[col] = df[col].astype(bool)

        # Convert dates for chronological sorting
        df['Start_Date_Obj'] = pd.to_datetime(df['start_date'], format='%d.%m.%Y', errors='coerce').dt.date
        df['End_Date_Obj'] = pd.to_datetime(df['end_date'], format='%d.%m.%Y', errors='coerce').dt.date

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

        # Filter anwenden, wenn der Toggle aktiv ist
        if only_registered:
            df_upcoming = df_upcoming[df_upcoming['registered'] == True]
            df_past = df_past[df_past['registered'] == True]

        # Deutsche Monatsnamen-Mapping
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
                            # Automatische Formatierung der Disziplinen und Partner-Details für das grüne Banner
                            if bool(item.get('registered', False)):
                                start_date_obj = item['Start_Date_Obj']
                                end_date_obj = item['End_Date_Obj']
                                
                                date_groups = {}
                                unassigned_parts = []
                                
                                # 1. Einzel
                                if bool(item.get('reg_he', False)):
                                    day_val = item.get('day_he', '')
                                    dt = get_date_for_weekday(day_val, start_date_obj, end_date_obj)
                                    text_part = "Herreneinzel"
                                    if dt:
                                        date_groups.setdefault(dt, []).append(text_part)
                                    else:
                                        unassigned_parts.append(text_part + (f" ({day_val})" if day_val else ""))
                                
                                # 2. Doppel
                                if bool(item.get('reg_hd', False)):
                                    p_hd = item.get('partner_hd', '').strip()
                                    if p_hd == "-- Kein Partner --":
                                        p_hd = ""
                                    
                                    partner_str = ""
                                    if p_hd in PARTNERS_HD:
                                        partner_str = f" mit <a href='{PARTNERS_HD[p_hd]}' target='_blank' style='color: #15803d; text-decoration: underline; font-weight: bold;'>{p_hd}</a>"
                                    elif p_hd:
                                        partner_str = f" mit {p_hd}"
                                        
                                    day_val = item.get('day_hd', '')
                                    dt = get_date_for_weekday(day_val, start_date_obj, end_date_obj)
                                    text_part = f"Herrendoppel{partner_str}"
                                    if dt:
                                        date_groups.setdefault(dt, []).append(text_part)
                                    else:
                                        unassigned_parts.append(text_part + (f" ({day_val})" if day_val else ""))
                                
                                # Mixed
                                if bool(item.get('reg_mx', False)):
                                    p_mx = item.get('partner_mx', '').strip()
                                    if p_mx == "-- Kein Partner --":
                                        p_mx = ""
                                        
                                    partner_str = ""
                                    if p_mx in PARTNERS_MX:
                                        partner_str = f" mit <a href='{PARTNERS_MX[p_mx]}' target='_blank' style='color: #15803d; text-decoration: underline; font-weight: bold;'>{p_mx}</a>"
                                    elif p_mx:
                                        partner_str = f" mit {p_mx}"
                                        
                                    day_val = item.get('day_mx', '')
                                    dt = get_date_for_weekday(day_val, start_date_obj, end_date_obj)
                                    text_part = f"Mixed{partner_str}"
                                    if dt:
                                        date_groups.setdefault(dt, []).append(text_part)
                                    else:
                                        unassigned_parts.append(text_part + (f" ({day_val})" if day_val else ""))
                                        
                                # Baue die HTML-Zeilen chronologisch auf (Gruppiert nach Datum)
                                sorted_dates = sorted(date_groups.keys())
                                weekday_names = {
                                    0: "Montag", 1: "Dienstag", 2: "Mittwoch", 3: "Donnerstag",
                                    4: "Freitag", 5: "Samstag", 6: "Sonntag"
                                }
                                
                                html_lines = []
                                for dt in sorted_dates:
                                    w_name = weekday_names[dt.weekday()]
                                    formatted_dt = dt.strftime("%d.%m.%Y")
                                    disciplines_str = ", ".join(date_groups[dt])
                                    html_lines.append(f"<div style='margin-top: 3px;'>🗓️ <strong>{formatted_dt} ({w_name}):</strong> {disciplines_str}</div>")
                                    
                                if unassigned_parts:
                                    html_lines.append(f"<div style='margin-top: 3px;'>📋 <strong>Noch ohne Tag:</strong> {', '.join(unassigned_parts)}</div>")
                                    
                                details_html = ""
                                if html_lines:
                                    details_html = f"<div style='font-weight: normal; font-size: 0.9em; margin-top: 5px; color: #166534;'>{ ''.join(html_lines) }</div>"

                                st.markdown(
                                    f"""
                                    <div style="
                                        background-color: #f0fdf4;
                                        border-left: 5px solid #22c55e;
                                        padding: 8px 12px;
                                        border-radius: 6px;
                                        margin-bottom: 12px;
                                        color: #15803d;
                                        font-weight: bold;
                                    ">
                                        <span style="font-style: normal; margin-right: 6px;">✅</span>
                                        Ich bin für dieses Turnier gemeldet!
                                        {details_html}
                                    </div>
                                    """,
                                    unsafe_allow_html=True
                                )

                            st.markdown(f"### {item['title']}")
                            
                            # --- ORT & STRUKTURIERTE ZEITPLANZEILEN AUF DER KARTE ---
                            dist_str = f" ({item['distance']} km)" if item['distance'] is not None else ""
                            st.markdown(f"📍 **{item['city']}**{dist_str}")
                            
                            # Gruppiere allgemeine Turnierdisziplinen nach Datum für die Karte
                            general_date_groups = {}
                            start_date_obj = item['Start_Date_Obj']
                            end_date_obj = item['End_Date_Obj']
                            
                            if item.get('day_he'):
                                dt_he = get_date_for_weekday(item['day_he'], start_date_obj, end_date_obj)
                                if dt_he: general_date_groups.setdefault(dt_he, []).append("Einzel")
                            if item.get('day_hd'):
                                dt_hd = get_date_for_weekday(item['day_hd'], start_date_obj, end_date_obj)
                                if dt_hd: general_date_groups.setdefault(dt_hd, []).append("Doppel")
                            if item.get('day_mx'):
                                dt_mx = get_date_for_weekday(item['day_mx'], start_date_obj, end_date_obj)
                                if dt_mx: general_date_groups.setdefault(dt_mx, []).append("Mixed")
                                
                            weekday_names_german = {
                                0: "Montag", 1: "Dienstag", 2: "Mittwoch", 3: "Donnerstag",
                                4: "Freitag", 5: "Samstag", 6: "Sonntag"
                            }
                            
                            if general_date_groups:
                                # Zeitplan chronologisch auflisten (eng beieinander in einem Block)
                                schedule_html = ""
                                for dt in sorted(general_date_groups.keys()):
                                    w_name = weekday_names_german[dt.weekday()]
                                    formatted_dt = dt.strftime("%d.%m.%Y")
                                    disciplines_str = ", ".join(general_date_groups[dt])
                                    schedule_html += f"<div style='margin-bottom: 2px;'>🗓️ <strong>{formatted_dt} ({w_name}):</strong> {disciplines_str}</div>"
                                st.markdown(f"<div style='line-height: 1.35; margin-bottom: 4px;'>{schedule_html}</div>", unsafe_allow_html=True)
                            else:
                                # Fallback, falls kein detaillierter Zeitplan bekannt ist
                                st.markdown(f"🗓️ **{item['start_date']}** bis **{item['end_date']}**")
                            
                            st.markdown(f"🏢 *Ausrichter: {item['organizer']}*")
                            
                            # Admin-Ansicht
                            if IS_ADMIN:
                                st.write("---")
                                col_he, col_hd, col_mx = st.columns(3)
                                day_options = get_tournament_day_options(start_date_obj, end_date_obj)
                                
                                with col_he:
                                    st.markdown("**Herreneinzel**")
                                    val_he = st.checkbox("Meldung Einzel", value=bool(item.get('reg_he', False)), key=f"he_{item['id']}")
                                    val_day_he_db = item.get('day_he', '')
                                    if val_he:
                                        # Index für vorausgewählten Wert dynamisch suchen
                                        he_idx = 0
                                        if val_day_he_db:
                                            for o_idx, opt in enumerate(day_options):
                                                if opt.startswith(val_day_he_db):
                                                    he_idx = o_idx
                                                    break
                                        selected_label_he = st.selectbox("Spieltag Einzel", options=day_options, index=he_idx, key=f"day_he_{item['id']}")
                                        val_day_he = selected_label_he.split(",")[0].strip() if selected_label_he != "-- Tag wählen --" else ""
                                    else:
                                        val_day_he = ""
                                        
                                with col_hd:
                                    st.markdown("**Herrendoppel**")
                                    val_hd = st.checkbox("Meldung Doppel", value=bool(item.get('reg_hd', False)), key=f"hd_{item['id']}")
                                    val_partner_hd = item.get('partner_hd', '')
                                    val_day_hd_db = item.get('day_hd', '')
                                    
                                    if val_hd:
                                        hd_options = ["-- Kein Partner --"] + list(PARTNERS_HD.keys())
                                        default_idx_hd = hd_options.index(val_partner_hd) if val_partner_hd in hd_options else 0
                                        val_partner_hd = st.selectbox("Partner Herrendoppel", options=hd_options, index=default_idx_hd, key=f"p_hd_{item['id']}")
                                        if val_partner_hd == "-- Kein Partner --":
                                            val_partner_hd = ""
                                            
                                        # Index für vorausgewählten Wert dynamisch suchen
                                        hd_idx = 0
                                        if val_day_hd_db:
                                            for o_idx, opt in enumerate(day_options):
                                                if opt.startswith(val_day_hd_db):
                                                    hd_idx = o_idx
                                                    break
                                        selected_label_hd = st.selectbox("Spieltag Doppel", options=day_options, index=hd_idx, key=f"day_hd_{item['id']}")
                                        val_day_hd = selected_label_hd.split(",")[0].strip() if selected_label_hd != "-- Tag wählen --" else ""
                                    else:
                                        val_partner_hd = ""
                                        val_day_hd = ""
                                        
                                with col_mx:
                                    st.markdown("**Mixed**")
                                    val_mx = st.checkbox("Meldung Mixed", value=bool(item.get('reg_mx', False)), key=f"mx_{item['id']}")
                                    val_partner_mx = item.get('partner_mx', '')
                                    val_day_mx_db = item.get('day_mx', '')
                                    
                                    if val_mx:
                                        mx_options = ["-- Kein Partner --"] + list(PARTNERS_MX.keys())
                                        default_idx_mx = mx_options.index(val_partner_mx) if val_partner_mx in mx_options else 0
                                        val_partner_mx = st.selectbox("Partner Mixed", options=mx_options, index=default_idx_mx, key=f"p_mx_{item['id']}")
                                        if val_partner_mx == "-- Kein Partner --":
                                            val_partner_mx = ""
                                            
                                        # Index für vorausgewählten Wert dynamisch suchen
                                        mx_idx = 0
                                        if val_day_mx_db:
                                            for o_idx, opt in enumerate(day_options):
                                                if opt.startswith(val_day_mx_db):
                                                    mx_idx = o_idx
                                                    break
                                        selected_label_mx = st.selectbox("Spieltag Mixed", options=day_options, index=mx_idx, key=f"day_mx_{item['id']}")
                                        val_day_mx = selected_label_mx.split(",")[0].strip() if selected_label_mx != "-- Tag wählen --" else ""
                                    else:
                                        val_partner_mx = ""
                                        val_day_mx = ""
                                        
                                is_registered = (val_he or val_hd or val_mx)
                                
                                has_changed = (
                                    val_he != bool(item.get('reg_he', False)) or
                                    val_hd != bool(item.get('reg_hd', False)) or
                                    val_mx != bool(item.get('reg_mx', False)) or
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
                            # Sanftes grünes Alert-Banner für vergangene Turniere mit denselben Verlinkungen
                            if bool(item.get('registered', False)):
                                start_date_obj = item['Start_Date_Obj']
                                end_date_obj = item['End_Date_Obj']
                                
                                date_groups = {}
                                unassigned_parts = []
                                
                                # 1. Einzel
                                if bool(item.get('reg_he', False)):
                                    day_val = item.get('day_he', '')
                                    dt = get_date_for_weekday(day_val, start_date_obj, end_date_obj)
                                    text_part = "Herreneinzel"
                                    if dt:
                                        date_groups.setdefault(dt, []).append(text_part)
                                    else:
                                        unassigned_parts.append(text_part + (f" ({day_val})" if day_val else ""))
                                
                                # 2. Doppel
                                if bool(item.get('reg_hd', False)):
                                    p_hd = item.get('partner_hd', '').strip()
                                    if p_hd == "-- Kein Partner --":
                                        p_hd = ""
                                        
                                    partner_str = ""
                                    if p_hd in PARTNERS_HD:
                                        partner_str = f" mit <a href='{PARTNERS_HD[p_hd]}' target='_blank' style='color: #166534; text-decoration: underline; font-weight: bold;'>{p_hd}</a>"
                                    elif p_hd:
                                        partner_str = f" mit {p_hd}"
                                        
                                    day_val = item.get('day_hd', '')
                                    dt = get_date_for_weekday(day_val, start_date_obj, end_date_obj)
                                    text_part = f"Herrendoppel{partner_str}"
                                    if dt:
                                        date_groups.setdefault(dt, []).append(text_part)
                                    else:
                                        unassigned_parts.append(text_part + (f" ({day_val})" if day_val else ""))
                                        
                                # Mixed
                                if bool(item.get('reg_mx', False)):
                                    p_mx = item.get('partner_mx', '').strip()
                                    if p_mx == "-- Kein Partner --":
                                        p_mx = ""
                                        
                                    partner_str = ""
                                    if p_mx in PARTNERS_MX:
                                        partner_str = f" mit <a href='{PARTNERS_MX[p_mx]}' target='_blank' style='color: #166534; text-decoration: underline; font-weight: bold;'>{p_mx}</a>"
                                    elif p_mx:
                                        partner_str = f" mit {p_mx}"
                                        
                                    day_val = item.get('day_mx', '')
                                    dt = get_date_for_weekday(day_val, start_date_obj, end_date_obj)
                                    text_part = f"Mixed{partner_str}"
                                    if dt:
                                        date_groups.setdefault(dt, []).append(text_part)
                                    else:
                                        unassigned_parts.append(text_part + (f" ({day_val})" if day_val else ""))
                                        
                                # Baue die HTML-Zeilen chronologisch auf (past)
                                sorted_dates = sorted(date_groups.keys())
                                weekday_names = {
                                    0: "Montag", 1: "Dienstag", 2: "Mittwoch", 3: "Donnerstag",
                                    4: "Freitag", 5: "Samstag", 6: "Sonntag"
                                }
                                
                                html_lines = []
                                for dt in sorted_dates:
                                    w_name = weekday_names[dt.weekday()]
                                    formatted_dt = dt.strftime("%d.%m.%Y")
                                    disciplines_str = ", ".join(date_groups[dt])
                                    html_lines.append(f"<div style='margin-top: 3px;'>🗓️ <strong>{formatted_dt} ({w_name}):</strong> {disciplines_str}</div>")
                                    
                                if unassigned_parts:
                                    html_lines.append(f"<div style='margin-top: 3px;'>📋 <strong>Noch ohne Tag:</strong> {', '.join(unassigned_parts)}</div>")
                                    
                                details_html = ""
                                if html_lines:
                                    details_html = f"<div style='font-weight: normal; font-size: 0.9em; margin-top: 5px; color: #166534;'>{ ''.join(html_lines) }</div>"

                                st.markdown(
                                    f"""
                                    <div style="
                                        background-color: #f4fbf7;
                                        border-left: 5px solid #86efac;
                                        padding: 6px 10px;
                                        border-radius: 6px;
                                        margin-bottom: 12px;
                                        color: #166534;
                                        font-weight: bold;
                                    ">
                                        <span style="color: #86efac; font-style: normal; margin-right: 5px;">✅</span>
                                        Teilgenommen
                                        {details_html}
                                    </div>
                                    """,
                                    unsafe_allow_html=True
                                )

                            st.markdown(f"### {item['title']} *(Beendet)*")
                            
                            # --- ORT & STRUKTURIERTE ZEITPLANZEILEN AUF DER KARTE (past) ---
                            dist_str = f" ({item['distance']} km)" if item['distance'] is not None else ""
                            st.markdown(f"📍 **{item['city']}**{dist_str}")
                            
                            # Gruppiere allgemeine Turnierdisziplinen nach Datum für die Karte (past)
                            general_date_groups = {}
                            start_date_obj = item['Start_Date_Obj']
                            end_date_obj = item['End_Date_Obj']
                            
                            if item.get('day_he'):
                                dt_he = get_date_for_weekday(item['day_he'], start_date_obj, end_date_obj)
                                if dt_he: general_date_groups.setdefault(dt_he, []).append("Einzel")
                            if item.get('day_hd'):
                                dt_hd = get_date_for_weekday(item['day_hd'], start_date_obj, end_date_obj)
                                if dt_hd: general_date_groups.setdefault(dt_hd, []).append("Doppel")
                            if item.get('day_mx'):
                                dt_mx = get_date_for_weekday(item['day_mx'], start_date_obj, end_date_obj)
                                if dt_mx: general_date_groups.setdefault(dt_mx, []).append("Mixed")
                                
                            weekday_names_german = {
                                0: "Montag", 1: "Dienstag", 2: "Mittwoch", 3: "Donnerstag",
                                4: "Freitag", 5: "Samstag", 6: "Sonntag"
                            }
                            
                            if general_date_groups:
                                # Zeitplan chronologisch auflisten (eng beieinander in einem Block)
                                schedule_html = ""
                                for dt in sorted(general_date_groups.keys()):
                                    w_name = weekday_names_german[dt.weekday()]
                                    formatted_dt = dt.strftime("%d.%m.%Y")
                                    disciplines_str = ", ".join(general_date_groups[dt])
                                    schedule_html += f"<div style='margin-bottom: 2px;'>🗓️ <strong>{formatted_dt} ({w_name}):</strong> {disciplines_str}</div>"
                                st.markdown(f"<div style='line-height: 1.35; margin-bottom: 4px;'>{schedule_html}</div>", unsafe_allow_html=True)
                            else:
                                # Fallback (past)
                                st.markdown(f"🗓️ **{item['start_date']}** bis **{item['end_date']}**")
                            
                            st.markdown(f"🏢 *Ausrichter: {item['organizer']}*")
                            
                            # Admin-Ansicht
                            if IS_ADMIN:
                                st.write("---")
                                col_he, col_hd, col_mx = st.columns(3)
                                start_date_obj = item['Start_Date_Obj']
                                end_date_obj = item['End_Date_Obj']
                                day_options = get_tournament_day_options(start_date_obj, end_date_obj)
                                
                                with col_he:
                                    st.markdown("**Herreneinzel**")
                                    val_he = st.checkbox("Herreneinzel", value=bool(item.get('reg_he', False)), key=f"he_past_{item['id']}")
                                    val_day_he_db = item.get('day_he', '')
                                    if val_he:
                                        he_idx = 0
                                        if val_day_he_db:
                                            for o_idx, opt in enumerate(day_options):
                                                if opt.startswith(val_day_he_db):
                                                    he_idx = o_idx
                                                    break
                                        selected_label_he = st.selectbox("Spieltag Einzel", options=day_options, index=he_idx, key=f"day_he_past_{item['id']}")
                                        val_day_he = selected_label_he.split(",")[0].strip() if selected_label_he != "-- Tag wählen --" else ""
                                    else:
                                        val_day_he = ""
                                
                                with col_hd:
                                    st.markdown("**Herrendoppel**")
                                    val_hd = st.checkbox("Herrendoppel", value=bool(item.get('reg_hd', False)), key=f"hd_past_{item['id']}")
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
                                                if opt.startswith(val_day_hd_db):
                                                    hd_idx = o_idx
                                                    break
                                        selected_label_hd = st.selectbox("Spieltag Doppel", options=day_options, index=hd_idx, key=f"day_hd_past_{item['id']}")
                                        val_day_hd = selected_label_hd.split(",")[0].strip() if selected_label_hd != "-- Tag wählen --" else ""
                                    else:
                                        val_partner_hd = ""
                                        val_day_hd = ""
                                
                                with col_mx:
                                    st.markdown("**Mixed**")
                                    val_mx = st.checkbox("Mixed", value=bool(item.get('reg_mx', False)), key=f"mx_past_{item['id']}")
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
                                                if opt.startswith(val_day_mx_db):
                                                    mx_idx = o_idx
                                                    break
                                        selected_label_mx = st.selectbox("Spieltag Mixed", options=day_options, index=mx_idx, key=f"day_mx_past_{item['id']}")
                                        val_day_mx = selected_label_mx.split(",")[0].strip() if selected_label_mx != "-- Tag wählen --" else ""
                                    else:
                                        val_partner_mx = ""
                                        val_day_mx = ""
                                        
                                is_registered = (val_he or val_hd or val_mx)
                                
                                has_changed = (
                                    val_he != bool(item.get('reg_he', False)) or
                                    val_hd != bool(item.get('reg_hd', False)) or
                                    val_mx != bool(item.get('reg_mx', False)) or
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
                st.write("Keine vergangenen Turniere gefunden.")

    else:
        st.info("Der Suchlauf war erfolgreich, aber es wurden keine Turniere in Ihrem Umkreis gefunden.")
else:
    st.warning("Keine Turnier-Datenbank gefunden. Bitte wenden Sie sich an den Administrator, um den ersten Suchlauf durchzuführen.")