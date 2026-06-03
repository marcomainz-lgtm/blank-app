import streamlit as st
import pandas as pd
import json
import os
from tracker import check_for_updates, DB_FILE

st.set_page_config(page_title="Badminton-Turnier-Tracker", layout="wide")

st.title("🏸 Badminton-Turniere (Umkreis 100km um 40723)")
st.write("Zeigt Turniere von turnier.de basierend auf Ihren Filtereinstellungen.")

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
            
        # Datumsfelder für korrekte chronologische Sortierung temporär konvertieren
        df['Startdatum_Parsed'] = pd.to_datetime(df['start_date'], format='%d.%m.%Y', errors='coerce')
        
        # Sortierung: Chronologisch nach Startdatum
        df_sorted = df.sort_values(by='Startdatum_Parsed', ascending=True, na_position='last')
        
        st.write(f"Insgesamt **{len(df_sorted)}** Turniere gefunden:")
        st.divider()

        # Jedes Turnier als native Karte direkt auf der Seite rendern
        for idx, item in df_sorted.iterrows():
            # Ein schicker nativer Container mit feinem Rand für jedes Turnier
            with st.container(border=True):
                # Spalten-Layout aufteilen: [Logo, Infos, Link-Button]
                col_logo, col_info, col_link = st.columns([1, 6, 2])
                
                with col_logo:
                    # Logo zentriert anzeigen
                    if item['logo_url']:
                        st.image(item['logo_url'], width=70)
                    else:
                        # Hübsches Fallback-Icon, falls kein Logo vorhanden ist
                        st.markdown("<h2 style='text-align: center; margin-top: 10px;'>🏸</h2>", unsafe_allow_html=True)
                        
                with col_info:
                    # Titel des Turniers
                    st.markdown(f"### {item['title']}")
                    
                    # Wichtigste Infos (Ort, Distanz, Datum)
                    dist_str = f" ({item['distance']} km)" if item['distance'] is not None else ""
                    st.markdown(f"📍 **{item['city']}**{dist_str} &nbsp;|&nbsp; 🗓️ **{item['start_date']}** bis **{item['end_date']}**")
                    
                    # Ausrichtender Verein / Verband
                    st.markdown(f"🏢 *Ausrichter: {item['organizer']}*")
                    
                with col_link:
                    # Großer Link-Button zur Turnieranmeldung (für Handys leicht nach unten versetzt)
                    st.write("")
                    st.write("")
                    st.link_button("Meldung / Info", item['link'], use_container_width=True)

    else:
        st.info("Der Suchlauf war erfolgreich, aber es wurden keine Turniere in Ihrem Umkreis gefunden.")
else:
    st.warning("Keine Turnier-Datenbank gefunden. Bitte klicken Sie oben auf 'Datenbank aktualisieren' für den ersten Suchlauf.")