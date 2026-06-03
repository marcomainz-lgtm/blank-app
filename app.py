import streamlit as st
import pandas as pd
import json
import os
import datetime
from tracker import check_for_updates, DB_FILE

st.set_page_config(page_title="Badminton Turniere für Marco", layout="wide")

# Alphabetisch sortierte Spielerprofile für Herrendoppel (Matthias Knaupp hinzugefügt)
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
        # Wenn eingeloggt, unauffälligen Logout-Button anstelle des Passwortfeldes anzeigen
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

# Title & Subtitle (Wunschtext eingepflegt)
st.title("🏸 Badminton Turniere für Marco")
st.write("Auf dieser Seite findet ihr alle Seniorenturniere 2026, die im Umkreis von 100 Kilometern um Hilden (40723) stattfinden.")

# Retrieve DB modification timestamp
last_retrieved_str = "Unbekannt"
if os.path.exists(DB_FILE):
    try:
        last_modified = os.path.getmtime(DB_FILE)
        last_retrieved_dt = datetime.datetime.fromtimestamp(last_modified)
        last_retrieved_str = last_retrieved_dt.strftime("%d.%m.%Y um %H:%M Uhr")
    except Exception:
        pass

st.caption(f"🕒 Letztes Update der Datenbank: {last_retrieved_str}")

# Database update trigger
if st.button("Datenbank aktualisieren"):
    with st.spinner("Suche nach neuen Turnieren auf turnier.de..."):
        check_for_updates()
    st.toast("Datenbank erfolgreich aktualisiert!")

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

        # --- A. UPCOMING TOURNAMENTS ---
        st.subheader(f"📅 Anstehende Turniere ({len(df_upcoming)})")
        
        # Anstehende Turniere im einklappbaren Akkordeon (standardmäßig geöffnet)
        with st.expander("Anstehende Turniere anzeigen", expanded=True):
            if not df_upcoming.empty:
                for idx, item in df_upcoming.iterrows():
                    with st.container(border=True):
                        col_logo, col_info, col_link = st.columns([1.5, 6, 2])
                        
                        with col_logo:
                            logo_to_show = item['logo_url']
                            if not logo_to_show or "no-photo" in logo_to_show:
                                logo_to_show = DEFAULT_LOGO
                            st.image(logo_to_show, width=140)
                                
                        with col_info:
                            # Formatierte Details
                            if bool(item.get('registered', False)):
                                parts = []
                                if bool(item.get('reg_he', False)):
                                    parts.append("Herreneinzel")
                                
                                if bool(item.get('reg_hd', False)):
                                    p_hd = item.get('partner_hd', '').strip()
                                    if p_hd in PARTNERS_HD:
                                        parts.append(f"Herrendoppel mit <a href='{PARTNERS_HD[p_hd]}' target='_blank' style='color: #15803d; text-decoration: underline; font-weight: bold;'>{p_hd}</a>")
                                    else:
                                        parts.append(f"Herrendoppel mit {p_hd}" if p_hd else "Herrendoppel")
                                
                                if bool(item.get('reg_mx', False)):
                                    p_mx = item.get('partner_mx', '').strip()
                                    if p_mx in PARTNERS_MX:
                                        parts.append(f"Mixed mit <a href='{PARTNERS_MX[p_mx]}' target='_blank' style='color: #15803d; text-decoration: underline; font-weight: bold;'>{p_mx}</a>")
                                    else:
                                        parts.append(f"Mixed mit {p_mx}" if p_mx else "Mixed")
                                    
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
                            
                            # Admin-Ansicht
                            if IS_ADMIN:
                                st.write("---")
                                col_he, col_hd, col_mx = st.columns(3)
                                with col_he:
                                    val_he = st.checkbox("Herreneinzel", value=bool(item.get('reg_he', False)), key=f"he_{item['id']}")
                                with col_hd:
                                    val_hd = st.checkbox("Herrendoppel", value=bool(item.get('reg_hd', False)), key=f"hd_{item['id']}")
                                with col_mx:
                                    val_mx = st.checkbox("Mixed", value=bool(item.get('reg_mx', False)), key=f"mx_{item['id']}")
                                
                                p_col1, p_col2 = st.columns(2)
                                val_partner_hd = item.get('partner_hd', '')
                                val_partner_mx = item.get('partner_mx', '')
                                
                                hd_options = ["-- Kein Partner --"] + list(PARTNERS_HD.keys())
                                mx_options = ["-- Kein Partner --"] + list(PARTNERS_MX.keys())
                                
                                with p_col1:
                                    if val_hd:
                                        default_idx_hd = hd_options.index(val_partner_hd) if val_partner_hd in hd_options else 0
                                        val_partner_hd = st.selectbox("Partner Herrendoppel", options=hd_options, index=default_idx_hd, key=f"p_hd_{item['id']}")
                                        if val_partner_hd == "-- Kein Partner --":
                                            val_partner_hd = ""
                                    else:
                                        val_partner_hd = ""
                                        
                                with p_col2:
                                    if val_mx:
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
                                    val_partner_hd != item.get('partner_hd', '') or
                                    val_partner_mx != item.get('partner_mx', '')
                                )
                                
                                if has_changed:
                                    data[item['id']]['registered'] = is_registered
                                    data[item['id']]['reg_he'] = val_he
                                    data[item['id']]['reg_hd'] = val_hd
                                    data[item['id']]['reg_mx'] = val_mx
                                    data[item['id']]['partner_hd'] = val_partner_hd
                                    data[item['id']]['partner_mx'] = val_partner_mx
                                    
                                    with open(DB_FILE, "w", encoding="utf-8") as f:
                                        json.dump(data, f, ensure_ascii=False, indent=4)
                                    st.rerun()
                            
                        with col_link:
                            st.write("")
                            st.write("")
                            st.link_button("Turnierseite", item['link'], use_container_width=True)
            else:
                st.info("Aktuell gibt es keine anstehenden Turniere mehr in der Liste.")

        st.write("")
        st.write("")

        # --- B. PAST TOURNAMENTS ---
        st.subheader(f"🕰️ Vergangene Turniere ({len(df_past)})")
        
        # Vergangene Turniere im einklappbaren Akkordeon (standardmäßig geschlossen)
        with st.expander("Vergangene Turniere anzeigen", expanded=False):
            if not df_past.empty:
                for idx, item in df_past.iterrows():
                    with st.container(border=True):
                        col_logo, col_info, col_link = st.columns([1.5, 6, 2])
                        
                        with col_logo:
                            logo_to_show = item['logo_url']
                            if not logo_to_show or "no-photo" in logo_to_show:
                                logo_to_show = DEFAULT_LOGO
                            st.image(logo_to_show, width=140)
                                
                        with col_info:
                            if bool(item.get('registered', False)):
                                parts = []
                                if bool(item.get('reg_he', False)):
                                    parts.append("Herreneinzel")
                                if bool(item.get('reg_hd', False)):
                                    p_hd = item.get('partner_hd', '').strip()
                                    if p_hd in PARTNERS_HD:
                                        parts.append(f"Herrendoppel mit <a href='{PARTNERS_HD[p_hd]}' target='_blank' style='color: #166534; text-decoration: underline; font-weight: bold;'>{p_hd}</a>")
                                    else:
                                        parts.append(f"Herrendoppel mit {p_hd}" if p_hd else "Herrendoppel")
                                if bool(item.get('reg_mx', False)):
                                    p_mx = item.get('partner_mx', '').strip()
                                    if p_mx in PARTNERS_MX:
                                        parts.append(f"Mixed mit <a href='{PARTNERS_MX[p_mx]}' target='_blank' style='color: #166534; text-decoration: underline; font-weight: bold;'>{p_mx}</a>")
                                    else:
                                        parts.append(f"Mixed mit {p_mx}" if p_mx else "Mixed")
                                    
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
                            
                            if IS_ADMIN:
                                st.write("---")
                                col_he, col_hd, col_mx = st.columns(3)
                                with col_he:
                                    val_he = st.checkbox("Herreneinzel", value=bool(item.get('reg_he', False)), key=f"he_past_{item['id']}")
                                with col_hd:
                                    val_hd = st.checkbox("Herrendoppel", value=bool(item.get('reg_hd', False)), key=f"hd_past_{item['id']}")
                                with col_mx:
                                    val_mx = st.checkbox("Mixed", value=bool(item.get('reg_mx', False)), key=f"mx_past_{item['id']}")
                                
                                p_col1, p_col2 = st.columns(2)
                                val_partner_hd = item.get('partner_hd', '')
                                val_partner_mx = item.get('partner_mx', '')
                                
                                hd_options = ["-- Kein Partner --"] + list(PARTNERS_HD.keys())
                                mx_options = ["-- Kein Partner --"] + list(PARTNERS_MX.keys())
                                
                                with p_col1:
                                    if val_hd:
                                        default_idx_hd = hd_options.index(val_partner_hd) if val_partner_hd in hd_options else 0
                                        val_partner_hd = st.selectbox("Partner Herrendoppel", options=hd_options, index=default_idx_hd, key=f"p_hd_past_{item['id']}")
                                        if val_partner_hd == "-- Kein Partner --":
                                            val_partner_hd = ""
                                    else:
                                        val_partner_hd = ""
                                        
                                with p_col2:
                                    if val_mx:
                                        default_idx_mx = mx_options.index(val_partner_mx) if val_partner_mx in mx_options else 0
                                        val_partner_mx = st.selectbox("Partner Mixed", options=mx_options, index=default_idx_mx, key=f"p_mx_past_{item['id']}")
                                        if val_partner_mx == "-- Kein Partner --":
                                            val_partner_mx = ""
                                    else:
                                        val_partner_mx = ""
                                        
                                is_registered = (val_he or val_hd or val_mx)
                                
                                has_changed = (
                                    val_he != bool(item.get('reg_he', False)) or
                                    val_hd != bool(item.get('reg_hd', False)) or
                                    val_mx != bool(item.get('reg_mx', False)) or
                                    val_partner_hd != item.get('partner_hd', '') or
                                    val_partner_mx != item.get('partner_mx', '')
                                )
                                
                                if has_changed:
                                    data[item['id']]['registered'] = is_registered
                                    data[item['id']]['reg_he'] = val_he
                                    data[item['id']]['reg_hd'] = val_hd
                                    data[item['id']]['reg_mx'] = val_mx
                                    data[item['id']]['partner_hd'] = val_partner_hd
                                    data[item['id']]['partner_mx'] = val_partner_mx
                                    
                                    with open(DB_FILE, "w", encoding="utf-8") as f:
                                        json.dump(data, f, ensure_ascii=False, indent=4)
                                    st.rerun()
                            
                        with col_link:
                            st.write("")
                            st.write("")
                            st.link_button("Turnierseite", item['link'], use_container_width=True)
            else:
                st.write("Keine vergangenen Turniere in der Datenbank.")

    else:
        st.info("Der Suchlauf war erfolgreich, aber es wurden keine Turniere in Ihrem Umkreis gefunden.")
else:
    st.warning("Keine Turnier-Datenbank gefunden. Bitte klicken Sie oben auf 'Datenbank aktualisieren' für den ersten Suchlauf.")