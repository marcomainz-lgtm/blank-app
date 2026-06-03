import streamlit as st
import pandas as pd
import json
import os
import datetime
from tracker import check_for_updates, DB_FILE

st.set_page_config(page_title="Badminton Turniere für Marco", layout="wide")

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
        
        # Fallbacks for older databases
        fallback_cols = {
            'registered': False,
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

        # Convert dates for chronological sorting
        df['Start_Date_Obj'] = pd.to_datetime(df['start_date'], format='%d.%m.%Y', errors='coerce').dt.date
        df['End_Date_Obj'] = pd.to_datetime(df['end_date'], format='%d.%m.%Y', errors='coerce').dt.date

        # Retrieve current date (dynamic)
        today = datetime.date.today()

        # Split data chronologically
        # 1. Upcoming / Ongoing (End Date is today or in the future)
        df_upcoming = df[df['End_Date_Obj'] >= today].copy()
        df_upcoming = df_upcoming.sort_values(by='Start_Date_Obj', ascending=True)

        # 2. Past Tournaments (End Date is in the past)
        df_past = df[df['End_Date_Obj'] < today].copy()
        df_past = df_past.sort_values(by='Start_Date_Obj', ascending=False)

        # --- A. UPCOMING TOURNAMENTS ---
        st.subheader(f"📅 Anstehende Turniere ({len(df_upcoming)})")
        
        if not df_upcoming.empty:
            for idx, item in df_upcoming.iterrows():
                with st.container(border=True):
                    col_logo, col_info, col_link = st.columns([1, 6, 2])
                    
                    with col_logo:
                        if item['logo_url']:
                            st.image(item['logo_url'], width=70)
                        else:
                            st.markdown("<h2 style='text-align: center; margin-top: 10px;'>🏸</h2>", unsafe_allow_html=True)
                            
                    with col_info:
                        # Display registered badge if applicable
                        if item.get('registered', False):
                            st.markdown("💚 **Ich bin für dieses Turnier gemeldet!**")

                        st.markdown(f"### {item['title']}")
                        dist_str = f" ({item['distance']} km)" if item['distance'] is not None else ""
                        st.markdown(f"📍 **{item['city']}**{dist_str} &nbsp;|&nbsp; 🗓️ **{item['start_date']}** bis **{item['end_date']}**")
                        st.markdown(f"🏢 *Ausrichter: {item['organizer']}*")
                        
                        # Admin view: show toggle checkbox inside the card
                        if IS_ADMIN:
                            reg_key = f"reg_toggle_{item['id']}"
                            is_reg = st.checkbox("Meldestatus", value=item.get('registered', False), key=reg_key)
                            if is_reg != item.get('registered', False):
                                data[item['id']]['registered'] = is_reg
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
                        col_logo, col_info, col_link = st.columns([1, 6, 2])
                        
                        with col_logo:
                            if item['logo_url']:
                                st.image(item['logo_url'], width=70)
                            else:
                                st.markdown("<h2 style='text-align: center; margin-top: 10px;'>🏸</h2>", unsafe_allow_html=True)
                                
                        with col_info:
                            if item.get('registered', False):
                                st.markdown("💚 *Teilgenommen*")

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
        st.