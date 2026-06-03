import streamlit as st
import pandas as pd
import json
import os
import datetime
from tracker import check_for_updates, DB_FILE

st.set_page_config(page_title="Badminton Turniere für Marco", layout="wide")

# 1. Überschrift & Neue Texte
st.title("🏸 Badminton Turniere für Marco")
st.write(
    "Diese Seite zeigt alle Turniere an, die sich im Umkreis von 100 Kilometern von Hilden (40723) befinden"
    )

# Datenbank aktualisieren per Button
if st.button("Datenbank aktualisieren"):
    with st.spinner("Suche nach neuen Turnieren auf turnier.de..."):
        check_for_updates()
    st.toast("Datenbank erfolgreich aktualisiert!")

# Datenbank laden und als Karten visualisieren
if os.path.exists(DB_FILE):
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}

    if data:
        # DataFrame aufbauen
        df = pd.DataFrame(data.values())
        
        # Fallbacks für ältere Datensätze
        fallback_cols = {
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

        # Datumsfelder für die chronologische Einteilung konvertieren
        df['Start_Date_Obj'] = pd.to_datetime(df['start_date'], format='%d.%m.%Y', errors='coerce').dt.date
        df['End_Date_Obj'] = pd.to_datetime(df['end_date'], format='%d.%m.%Y', errors='coerce').dt.date

        # Aktuelles Datum ermitteln (Mittwoch, 3. Juni 2026)
        today = datetime.date.today()

        # Datensätze aufsplitten:
        # 1. Anstehend / Laufend (Enddatum liegt heute oder in der Zukunft)
        df_upcoming = df[df['End_Date_Obj'] >= today].copy()
        # Sortierung: Nächstes Turnier zuerst (Chronologisch aufsteigend)
        df_upcoming = df_upcoming.sort_values(by='Start_Date_Obj', ascending=True)

        # 2. Archiv / Vergangen (Enddatum liegt in der Vergangenheit)
        df_past = df[df['End_Date_Obj'] < today].copy()
        # Sortierung: Zuletzt beendetes Turnier zuerst (Chronologisch absteigend)
        df_past = df_past.sort_values(by='Start_Date_Obj', ascending=False)

        # --- A. ANSTEHENDE TURNIERE (RELEVANT) ---
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
                        st.markdown(f"### {item['title']}")
                        dist_str = f" ({item['distance']} km)" if item['distance'] is not None else ""
                        st.markdown(f"📍 **{item['city']}**{dist_str} &nbsp;|&nbsp; 🗓️ **{item['start_date']}** bis **{item['end_date']}**")
                        st.markdown(f"🏢 *Ausrichter: {item['organizer']}*")
                        
                    with col_link:
                        st.write("")
                        st.write("")
                        st.link_button("Meldung / Info", item['link'], use_container_width=True)
        else:
            st.info("Aktuell gibt es keine anstehenden Turniere mehr in der Liste.")

        st.write("")
        st.write("")

        # --- B. VERGANGENE TURNIERE (ARCHIV) ---
        st.subheader(f"📁 Archiv & Vergangene Turniere ({len(df_past)})")
        
        # Packt alte Turniere in einen einklappbaren Expander, damit sie den Bildschirm nicht verstopfen
        with st.expander("Vergangene Turniere & Archiv anzeigen", expanded=False):
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