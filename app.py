import streamlit as st
import pandas as pd
import json
import os
import datetime
from tracker import check_for_updates, DB_FILE

st.set_page_config(page_title="Badminton Turniere für Marco", layout="wide")

# Custom-Logo für Turniere ohne eigenes Emblem
DEFAULT_LOGO = "https://content.tournamentsoftware.com/images/club/72FB92A4-34AF-41F1-8A4E-BBD56634E66E.jpg"

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

# Constrain the login field width by placing it in a top-right column
col_spacer, col_login = st.columns([4, 1])
with col_login:
    admin_password = st.text_input(
        "", 
        type="password", 
        label_visibility="collapsed", 
        placeholder="Admin Login", 
        key="secret_login"
    )

IS_ADMIN = (admin_password == "marco2026")

# Title & Subtitle
st.title("🏸 Badminton Turniere für Marco")
st.write("Diese Seite zeigt alle Turniere an, die sich im Umkreis von 100 Kilometern von Hilden (40723) befinden.")

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
        
        # Fallbacks für older databases (schützt vor NaN-Werten)
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
                        # Automatische Formatierung der Disziplinen und Partner-Details für das grüne Banner
                        if bool(item.get('registered', False)):
                            parts = []
                            if bool(item.get('reg_he', False)):
                                parts.append("Herren-Einzel")
                            if bool(item.get('reg_hd', False)):
                                p_hd = item.get('partner_hd', '').strip()
                                parts.append(f"Herren-Doppel mit {p_hd}" if p_hd else "Herren-Doppel")
                            if bool(item.get('reg_mx', False)):
                                p_mx = item.get('partner_mx', '').strip()
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
                                    <span style="color: #22c55e; font-weight: 900; font-size: 1.25em; font-style: normal; margin-right: 6px;">#</span>
                                    <i>Ich bin für dieses Turnier gemeldet!</i>
                                    {details_html}
                                </div>
                                """,
                                unsafe_allow_html=True
                            )

                        st.markdown(f"### {item['title']}")
                        dist_str = f" ({item['distance']} km)" if item['distance'] is not None else ""
                        st.markdown(f"📍 **{item['city']}**{dist_str} &nbsp;|&nbsp; 🗓️ **{item['start_date']}** bis **{item['end_date']}**")
                        st.markdown(f"🏢 *Ausrichter: {item['organizer']}*")
                        
                        # Admin-Ansicht: Strukturierte Eingabe
                        if IS_ADMIN:
                            st.write("---")
                            # 1. Reihe: Drei Checkboxen nebeneinander
                            col_he, col_hd, col_mx = st.columns(3)
                            with col_he:
                                val_he = st.checkbox("Herren-Einzel", value=bool(item.get('reg_he', False)), key=f"he_{item['id']}")
                            with col_hd:
                                val_hd = st.checkbox("Herren-Doppel", value=bool(item.get('reg_hd', False)), key=f"hd_{item['id']}")
                            with col_mx:
                                val_mx = st.checkbox("Mixed", value=bool(item.get('reg_mx', False)), key=f"mx_{item['id']}")
                            
                            # 2. Reihe: Dynamische Partner-Eingabefelder (erscheinen nur wenn HD oder MX angehakt ist)
                            p_col1, p_col2 = st.columns(2)
                            val_partner_hd = item.get('partner_hd', '')
                            val_partner_mx = item.get('partner_mx', '')
                            
                            with p_col1:
                                if val_hd:
                                    val_partner_hd = st.text_input("Doppelpartner", value=val_partner_hd, key=f"p_hd_{item['id']}", placeholder="Name des Partners")
                                else:
                                    val_partner_hd = ""
                                    
                            with p_col2:
                                if val_mx:
                                    val_partner_mx = st.text_input("Mixedpartner", value=val_partner_mx, key=f"p_mx_{item['id']}", placeholder="Name des Partners")
                                else:
                                    val_partner_mx = ""
                                    
                            # Allgemeiner Status ermitteln (mindestens eine Disziplin muss gewählt sein)
                            is_registered = (val_he or val_hd or val_mx)
                            
                            # Überprüfung auf Änderungen
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
                        st.link_button("Meldung / Info", item['link'], use_container_width=True)
        else:
            st.info("Aktuell gibt es keine anstehenden Turniere mehr in der Liste.")

        st.write("")
        st.write("")

        # --- B. PAST TOURNAMENTS ---
        st.subheader(f"🕰️ Vergangene Turniere ({len(df_past)})")
        
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
                            # Muted grünes Alert-Banner für vergangene Turniere mit denselben dynamischen Details
                            if bool(item.get('registered', False)):
                                parts = []
                                if bool(item.get('reg_he', False)):
                                    parts.append("Herren-Einzel")
                                if bool(item.get('reg_hd', False)):
                                    p_hd = item.get('partner_hd', '').strip()
                                    parts.append(f"Herren-Doppel mit {p_hd}" if p_hd else "Herren-Doppel")
                                if bool(item.get('reg_mx', False)):
                                    p_mx = item.get('partner_mx', '').strip()
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
                                        <span style="color: #86efac; font-weight: 900; font-size: 1.15em; font-style: normal; margin-right: 5px;">#</span>
                                        <i>Teilgenommen</i>
                                        {details_html}
                                    </div>
                                    """,
                                    unsafe_allow_html=True
                                )

                            st.markdown(f"### {item['title']} *(Beendet)*")
                            dist_str = f" ({item['distance']} km)" if item['distance'] is not None else ""
                            st.markdown(f"📍 **{item['city']}**{dist_str} &nbsp;|&nbsp; 🗓️ **{item['start_date']}** bis **{item['end_date']}**")
                            st.markdown(f"🏢 *Ausrichter: {item['organizer']}*")
                            
                        with col_link:
                            st.write("")
                            st.write("")
                            st.link_button("Ergebnisse / Details", item['link'], use_container_width=True)
            else:
                st.write("Keine vergangenen Turniere in der Datenbank.")

    else:
        st.info("Der Suchlauf war erfolgreich, aber es wurden keine Turniere in Ihrem Umkreis gefunden.")
else:
    st.warning("Keine Turnier-Datenbank gefunden. Bitte klicken Sie oben auf 'Datenbank aktualisieren' für den ersten Suchlauf.")