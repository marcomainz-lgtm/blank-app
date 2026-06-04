import streamlit as st
import pandas as pd
import json
import os
import datetime
import urllib.parse
from zoneinfo import ZoneInfo  # Ermöglicht präzise Zeitzonen-Konvertierung (Python 3.9+)
from tracker import check_for_updates, DB_FILE

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

# Retrieve DB modification timestamp & convert from UTC to Europe/Berlin timezone
last_retrieved_str = "Unbekannt"
if os.path.exists(DB_FILE):
    try:
        last_modified = os.path.getmtime(DB_FILE)
        # Erstelle ein bewusstes UTC-datetime Objekt
        last_retrieved_dt = datetime.datetime.fromtimestamp(last_modified, tz=datetime.timezone.utc)
        # In deutsche Ortzeit Europe/Berlin umrechnen (berücksichtigt Sommer-/Winterzeit automatisch!)
        berlin_tz = ZoneInfo("Europe/Berlin")
        last_retrieved_berlin = last_retrieved_dt.astimezone(berlin_tz)
        last_retrieved_str = last_retrieved_berlin.strftime("%d.%m.%Y um %H:%M Uhr")
    except Exception:
        pass

st.caption(f"🕒 Letztes Update der Datenbank: {last_retrieved_str}")

# --- MELDUNGSFILTER (TOGGLE) ---
only_registered = st.toggle("Nur gemeldete Turniere anzeigen", value=False)

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
        
        # Fallbacks for older databases
        fallback_cols = {
            'registered': False,
            'reg_he': False,
            'reg_hd': False,
            'reg_mx': False,
            'partner_hd': '',
            'partner_mx': '',
            'day_he': 'gesamt',
            'day_hd': 'gesamt',
            'day_mx': 'gesamt',
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

        # Retrieve current date (dynamic)
        today = datetime.date.today()

        # Split data chronologically
        df_upcoming = df[df['End_Date_Obj'] >= today].copy()
        df_upcoming = df_upcoming.sort_values(by='Start_Date_Obj', ascending=True)

        df_past = df[df['End_Date_Obj'] < today].copy()
        df_past = df_past.sort_values(by='Start_Date_Obj', ascending=False)

        # Robusten Filter über die JSON-Rohdaten anwenden, um Pandas NaN-Fehler auszuschließen
        if only_registered:
            registered_ids = {t_id for t_id, val in data.items() if val.get('registered', False)}
            df_upcoming = df_upcoming[df_upcoming['id'].isin(registered_ids)]
            df_past = df_past[df_past['id'].isin(registered_ids)]

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
                    
                    # --- DIREKTE PYTHON-DATENABFRAGE (BYPASS PANDAS) ---
                    t_id = item['id']
                    raw_item = data.get(t_id, {})
                    is_registered = bool(raw_item.get('registered', False))
                    reg_he = bool(raw_item.get('reg_he', False))
                    reg_hd = bool(raw_item.get('reg_hd', False))
                    reg_mx = bool(raw_item.get('reg_mx', False))
                    p_hd = raw_item.get('partner_hd', '').strip()
                    p_mx = raw_item.get('partner_mx', '').strip()
                    
                    # Wochentage auslesen
                    day_he = raw_item.get('day_he', 'gesamt')
                    day_hd = raw_item.get('day_hd', 'gesamt')
                    day_mx = raw_item.get('day_mx', 'gesamt')
                    
                    with st.container(border=True):
                        col_logo, col_info, col_link = st.columns([1.5, 6, 2])
                        
                        with col_logo:
                            logo_to_show = item['logo_url']
                            if not logo_to_show or "no-photo" in logo_to_show:
                                logo_to_show = DEFAULT_LOGO
                            st.image(logo_to_show, width=140)
                                
                        with col_info:
                            # Das Haken-Banner wird nur gerendert, wenn der Status in den JSON-Rohdaten TRUE ist
                            if is_registered:
                                parts = []
                                if reg_he:
                                    day_str = " (Samstag)" if day_he == "tag1" else " (Sonntag)" if day_he == "tag2" else ""
                                    parts.append(f"Herreneinzel{day_str}")
                                
                                if reg_hd:
                                    p_hd_cleaned = p_hd
                                    if p_hd_cleaned == "-- Kein Partner --":
                                        p_hd_cleaned = ""
                                    day_str = " (Samstag)" if day_hd == "tag1" else " (Sonntag)" if day_hd == "tag2" else ""
                                    
                                    if p_hd_cleaned in PARTNERS_HD:
                                        parts.append(f"Herrendoppel{day_str} mit <a href='{PARTNERS_HD[p_hd_cleaned]}' target='_blank' style='color: #15803d; text-decoration: underline; font-weight: bold;'>{p_hd_cleaned}</a>")
                                    elif p_hd_cleaned:
                                        parts.append(f"Herrendoppel{day_str} mit {p_hd_cleaned}")
                                    else:
                                        parts.append("Herrendoppel")
                                
                                if reg_mx:
                                    p_mx_cleaned = p_mx
                                    if p_mx_cleaned == "-- Kein Partner --":
                                        p_mx_cleaned = ""
                                    day_str = " (Samstag)" if day_mx == "tag1" else " (Sonntag)" if day_mx == "tag2" else ""
                                    
                                    if p_mx_cleaned in PARTNERS_MX:
                                        parts.append(f"Mixed{day_str} mit <a href='{PARTNERS_MX[p_mx_cleaned]}' target='_blank' style='color: #15803d; text-decoration: underline; font-weight: bold;'>{p_mx_cleaned}</a>")
                                    elif p_mx_cleaned:
                                        parts.append(f"Mixed{day_str} mit {p_mx_cleaned}")
                                    else:
                                        parts.append("Mixed")
                                        
                                    details_text = ", ".join(parts)
                                    details_html = ""
                                    if details_text:
                                        details_html = f"<div style='font-weight: normal; font-size: 0.9em; margin-top: 5px; color: #166534;'>Disziplinen: {details_text}</div>"
                                        
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
                            dist_str = f" ({item['distance']} km)" if item['distance'] is not None else ""
                            st.markdown(f"📍 **{item['city']}**{dist_str} &nbsp;|&nbsp; 🗓️ **{item['start_date']}** bis **{item['end_date']}**")
                            st.markdown(f"🏢 *Ausrichter: {item['organizer']}*")
                            
                        with col_link:
                            st.write("")
                            st.write("")
                            st.link_button("Turnierseite", item['link'], use_container_width=True)

                        # --- ADMIN-BEDIENELEMENTE DIREKT AUF CONTAINER-EBENE (UNGESTAUCHT) ---
                        if IS_ADMIN:
                            st.write("---")
                            col_he, col_hd, col_mx = st.columns(3)
                            with col_he:
                                val_he = st.checkbox("Herreneinzel", value=reg_he, key=f"he_{t_id}")
                            with col_hd:
                                val_hd = st.checkbox("Herrendoppel", value=reg_hd, key=f"hd_{t_id}")
                            with col_mx:
                                val_mx = st.checkbox("Mixed", value=reg_mx, key=f"mx_{t_id}")
                            
                            p_col1, p_col2 = st.columns(2)
                            hd_options = ["-- Kein Partner --"] + list(PARTNERS_HD.keys())
                            mx_options = ["-- Kein Partner --"] + list(PARTNERS_MX.keys())
                            
                            # Tag-Auswahloptionen für 2-Tages-Turniere berechnen
                            day_options_labels = {
                                "gesamt": f"Ganzes Turnier ({item['start_date']} - {item['end_date']})",
                                "tag1": f"Nur Samstag ({item['start_date']})",
                                "tag2": f"Nur Sonntag ({item['end_date']})"
                            }
                            day_options_keys = {v: k for k, v in day_options_labels.items()}
                            
                            with p_col1:
                                if val_hd:
                                    default_idx_hd = hd_options.index(p_hd) if p_hd in hd_options else 0
                                    val_partner_hd = st.selectbox("Partner Herrendoppel", options=hd_options, index=default_idx_hd, key=f"p_hd_{t_id}")
                                    if val_partner_hd == "-- Kein Partner --":
                                        val_partner_hd = ""
                                else:
                                    val_partner_hd = ""
                                    
                            with p_col2:
                                if val_mx:
                                    default_idx_mx = mx_options.index(p_mx) if p_mx in mx_options else 0
                                    val_partner_mx = st.selectbox("Partner Mixed", options=mx_options, index=default_idx_mx, key=f"p_mx_{t_id}")
                                    if val_partner_mx == "-- Kein Partner --":
                                        val_partner_mx = ""
                                else:
                                    val_partner_mx = ""
                            
                            # Wochentags-Dropdowns rendern, wenn Disziplin gewählt ist und es ein echtes 2-Tages-Turnier ist
                            val_day_he = day_he
                            val_day_hd = day_hd
                            val_day_mx = day_mx
                            
                            if item['start_date'] != item['end_date']:
                                day_col1, day_col2, day_col3 = st.columns(3)
                                with day_col1:
                                    if val_he:
                                        default_idx = list(day_options_labels.keys()).index(val_day_he) if val_day_he in day_options_labels else 0
                                        sel_he = st.selectbox("Spieltag Herreneinzel", options=list(day_options_labels.values()), index=default_idx, key=f"day_he_{t_id}")
                                        val_day_he = day_options_keys[sel_he]
                                with day_col2:
                                    if val_hd:
                                        default_idx = list(day_options_labels.keys()).index(val_day_hd) if val_day_hd in day_options_labels else 0
                                        sel_hd = st.selectbox("Spieltag Herrendoppel", options=list(day_options_labels.values()), index=default_idx, key=f"day_hd_{t_id}")
                                        val_day_hd = day_options_keys[sel_hd]
                                with day_col3:
                                    if val_mx:
                                        default_idx = list(day_options_labels.keys()).index(val_day_mx) if val_day_mx in day_options_labels else 0
                                        sel_mx = st.selectbox("Spieltag Mixed", options=list(day_options_labels.values()), index=default_idx, key=f"day_mx_{t_id}")
                                        val_day_mx = day_options_keys[sel_mx]
                            else:
                                val_day_he = "gesamt"
                                val_day_hd = "gesamt"
                                val_day_mx = "gesamt"
                                    
                            is_registered_calc = (val_he or val_hd or val_mx)
                            
                            has_changed = (
                                val_he != reg_he or
                                val_hd != reg_hd or
                                val_mx != reg_mx or
                                val_partner_hd != p_hd or
                                val_partner_mx != p_mx or
                                val_day_he != day_he or
                                val_day_hd != day_hd or
                                val_day_mx != day_mx
                            )
                            
                            if has_changed:
                                data[t_id]['registered'] = is_registered_calc
                                data[t_id]['reg_he'] = val_he
                                data[t_id]['reg_hd'] = val_hd
                                data[t_id]['reg_mx'] = val_mx
                                data[t_id]['partner_hd'] = val_partner_hd
                                data[t_id]['partner_mx'] = val_partner_mx
                                data[t_id]['day_he'] = val_day_he
                                data[t_id]['day_hd'] = val_day_hd
                                data[t_id]['day_mx'] = val_day_mx
                                
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
                    
                    # --- DIREKTE PYTHON-DATENABFRAGE (BYPASS PANDAS) ---
                    t_id = item['id']
                    raw_item = data.get(t_id, {})
                    is_registered = bool(raw_item.get('registered', False))
                    reg_he = bool(raw_item.get('reg_he', False))
                    reg_hd = bool(raw_item.get('reg_hd', False))
                    reg_mx = bool(raw_item.get('reg_mx', False))
                    p_hd = raw_item.get('partner_hd', '').strip()
                    p_mx = raw_item.get('partner_mx', '').strip()
                    
                    day_he = raw_item.get('day_he', 'gesamt')
                    day_hd = raw_item.get('day_hd', 'gesamt')
                    day_mx = raw_item.get('day_mx', 'gesamt')
                    
                    with st.container(border=True):
                        col_logo, col_info, col_link = st.columns([1.5, 6, 2])
                        
                        with col_logo:
                            logo_to_show = item['logo_url']
                            if not logo_to_show or "no-photo" in logo_to_show:
                                logo_to_show = DEFAULT_LOGO
                            st.image(logo_to_show, width=140)
                                
                        with col_info:
                            # FIX: Auch im Archiv nutzen wir konsequent die direkte, saubere Variable is_registered!
                            if is_registered:
                                parts = []
                                if reg_he:
                                    day_str = " (Samstag)" if day_he == "tag1" else " (Sonntag)" if day_he == "tag2" else ""
                                    parts.append(f"Herreneinzel{day_str}")
                                if reg_hd:
                                    p_hd_cleaned = p_hd
                                    if p_hd_cleaned == "-- Kein Partner --":
                                        p_hd_cleaned = ""
                                    day_str = " (Samstag)" if day_hd == "tag1" else " (Sonntag)" if day_hd == "tag2" else ""
                                    
                                    if p_hd_cleaned in PARTNERS_HD:
                                        parts.append(f"Herrendoppel{day_str} mit <a href='{PARTNERS_HD[p_hd_cleaned]}' target='_blank' style='color: #166534; text-decoration: underline; font-weight: bold;'>{p_hd_cleaned}</a>")
                                    elif p_hd_cleaned:
                                        parts.append(f"Herrendoppel{day_str} mit {p_hd_cleaned}")
                                    else:
                                        parts.append("Herrendoppel")
                                        
                                if bool(item.get('reg_mx', False)):
                                    p_mx_cleaned = p_mx
                                    if p_mx_cleaned == "-- Kein Partner --":
                                        p_mx_cleaned = ""
                                    day_str = " (Samstag)" if day_mx == "tag1" else " (Sonntag)" if day_mx == "tag2" else ""
                                    
                                    if p_mx_cleaned in PARTNERS_MX:
                                        parts.append(f"Mixed{day_str} mit <a href='{PARTNERS_MX[p_mx_cleaned]}' target='_blank' style='color: #166534; text-decoration: underline; font-weight: bold;'>{p_mx_cleaned}</a>")
                                    elif p_mx_cleaned:
                                        parts.append(f"Mixed{day_str} mit {p_mx_cleaned}")
                                    else:
                                        parts.append("Mixed")
                                    
                                details_text = ", ".join(parts)
                                details_html = ""
                                if details_text:
                                    details_html = f"<div style='font-weight: normal; font-size: 0.9em; margin-top: 5px; color: #166534;'>Disziplinen: {details_text}</div>"

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
                            dist_str = f" ({item['distance']} km)" if item['distance'] is not None else ""
                            st.markdown(f"📍 **{item['city']}**{dist_str} &nbsp;|&nbsp; 🗓️ **{item['start_date']}** bis **{item['end_date']}**")
                            st.markdown(f"🏢 *Ausrichter: {item['organizer']}*")
                            
                            # Admin-Ansicht
                            if IS_ADMIN:
                                st.write("---")
                                col_he, col_hd, col_mx = st.columns(3)
                                with col_he:
                                    val_he = st.checkbox("Herreneinzel", value=reg_he, key=f"he_past_{t_id}")
                                with col_hd:
                                    val_hd = st.checkbox("Herrendoppel", value=bool(item.get('reg_hd', False)), key=f"hd_past_{t_id}")
                                with col_mx:
                                    val_mx = st.checkbox("Mixed", value=bool(item.get('reg_mx', False)), key=f"mx_past_{t_id}")
                                
                                p_col1, p_col2 = st.columns(2)
                                hd_options = ["-- Kein Partner --"] + list(PARTNERS_HD.keys())
                                mx_options = ["-- Kein Partner --"] + list(PARTNERS_MX.keys())
                                
                                day_options_labels = {
                                    "gesamt": f"Ganzes Turnier ({item['start_date']} - {item['end_date']})",
                                    "tag1": f"Nur Samstag ({item['start_date']})",
                                    "tag2": f"Nur Sonntag ({item['end_date']})"
                                }
                                day_options_keys = {v: k for k, v in day_options_labels.items()}
                                
                                with p_col1:
                                    if val_hd:
                                        default_idx_hd = hd_options.index(p_hd) if p_hd in hd_options else 0
                                        val_partner_hd = st.selectbox("Partner Herrendoppel", options=hd_options, index=default_idx_hd, key=f"p_hd_past_{t_id}")
                                        if val_partner_hd == "-- Kein Partner --":
                                            val_partner_hd = ""
                                    else:
                                        val_partner_hd = ""
                                        
                                with p_col2:
                                    if val_mx:
                                        default_idx_mx = mx_options.index(p_mx) if p_mx in mx_options else 0
                                        val_partner_mx = st.selectbox("Partner Mixed", options=mx_options, index=default_idx_mx, key=f"p_mx_past_{t_id}")
                                        if val_partner_mx == "-- Kein Partner --":
                                            val_partner_mx = ""
                                    else:
                                        val_partner_mx = ""
                                
                                val_day_he = day_he
                                val_day_hd = day_hd
                                val_day_mx = day_mx
                                
                                if item['start_date'] != item['end_date']:
                                    day_col1, day_col2, day_col3 = st.columns(3)
                                    with day_col1:
                                        if val_he:
                                            default_idx = list(day_options_labels.keys()).index(val_day_he) if val_day_he in day_options_labels else 0
                                            sel_he = st.selectbox("Spieltag Herreneinzel", options=list(day_options_labels.values()), index=default_idx, key=f"day_he_past_{t_id}")
                                            val_day_he = day_options_keys[sel_he]
                                    with day_col2:
                                        if val_hd:
                                            default_idx = list(day_options_labels.keys()).index(val_day_hd) if val_day_hd in day_options_labels else 0
                                            sel_hd = st.selectbox("Spieltag Herrendoppel", options=list(day_options_labels.values()), index=default_idx, key=f"day_hd_past_{t_id}")
                                            val_day_hd = day_options_keys[sel_hd]
                                    with day_col3:
                                        if val_mx:
                                            default_idx = list(day_options_labels.keys()).index(val_day_mx) if val_day_mx in day_options_labels else 0
                                            sel_mx = st.selectbox("Spieltag Mixed", options=list(day_options_labels.values()), index=default_idx, key=f"day_mx_past_{t_id}")
                                            val_day_mx = day_options_keys[sel_mx]
                                else:
                                    val_day_he = "gesamt"
                                    val_day_hd = "gesamt"
                                    val_day_mx = "gesamt"
                                        
                                is_registered_calc = (val_he or val_hd or val_mx)
                                
                                has_changed = (
                                    val_he != reg_he or
                                    val_hd != reg_hd or
                                    val_mx != reg_mx or
                                    val_partner_hd != p_hd or
                                    val_partner_mx != p_mx or
                                    val_day_he != day_he or
                                    val_day_hd != day_hd or
                                    val_day_mx != day_mx
                                )
                                
                                if has_changed:
                                    data[t_id]['registered'] = is_registered_calc
                                    data[t_id]['reg_he'] = val_he
                                    data[t_id]['reg_hd'] = val_hd
                                    data[t_id]['reg_mx'] = val_mx
                                    data[t_id]['partner_hd'] = val_partner_hd
                                    data[t_id]['partner_mx'] = val_partner_mx
                                    data[t_id]['day_he'] = val_day_he
                                    data[t_id]['day_hd'] = val_day_hd
                                    data[t_id]['day_mx'] = val_day_mx
                                    
                                    with open(DB_FILE, "w", encoding="utf-8") as f:
                                        json.dump(data, f, ensure_ascii=False, indent=4)
                                    st.rerun()
                            
                        with col_link:
                            st.write("")
                            st.write("")
                            st.link_button("Turnierseite", item['link'], use_container_width=True)
            else:
                st.write("Keine vergangenen Turniere gefunden.")

        # --- BEREICH: BACKUP-TOOL (FÜR ADMINS SICHTBAR) ---
        if IS_ADMIN:
            st.write("---")
            with st.expander("💾 Backup & GitHub-Synchronisation", expanded=False):
                st.write(
                    "Da Streamlit-Server flüchtigen (ephemeren) Speicher nutzen, gehen "
                    "online eingetragene Meldungen bei zukünftigen App-Updates verloren. "
                    "Um Ihre Haken dauerhaft zu sichern, kopieren Sie einfach diesen gesamten JSON-Code block, "
                    "fügen ihn in Ihre lokale Datei `known_tournaments.json` in VS Code ein und pushen diese zu GitHub:"
                )
                st.code(json.dumps(data, indent=4, ensure_ascii=False), language="json")

# --- DER NEUE MINIMALISTISCHE LOGIN-BEREICH GANZ UNTEN (VOLLE BREITE, KEINE STAUCHUNG) ---
st.write("")
st.write("")
st.divider()

if st.session_state['logged_in']:
    # Wenn eingeloggt, Abmelde-Button ganz unten vollflächig anzeigen
    if st.button("Abmelden (Logout)", use_container_width=True, key="logout_bottom"):
        st.session_state['logged_in'] = False
        if 'secret_login' in st.session_state:
            st.session_state['secret_login'] = ""
        st.rerun()
else:
    # Unauffälliger Login ganz unten über die volle Breite
    admin_password = st.text_input(
        "Admin-Bereich zur Bearbeitung freischalten:", 
        type="password", 
        placeholder="Passwort eingeben...", 
        key="secret_login"
    )
    if admin_password == "marco2026":
        st.session_state['logged_in'] = True
        st.rerun()