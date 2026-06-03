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

# Datenbank laden und visualisieren
if os.path.exists(DB_FILE):
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}

    if data:
        # DataFrame aufbauen
        df = pd.DataFrame(data.values())
        
        # Fallbacks für ältere Datensätze (Sicherheitshalber)
        fallback_cols = {
            'logo_url': '',
            'city': 'Unbekannt',
            'distance': None,
            'start_date': None,
            'end_date': None
        }
        for col, default in fallback_cols.items():
            if col not in df.columns:
                df[col] = default
            
        # Nur die angeforderten Spalten selektieren (Logo, Turnier, Stadt, Distanz, Startdatum, Enddatum, Link)
        df_display = df[['logo_url', 'title', 'city', 'distance', 'start_date', 'end_date', 'link']].copy()
        df_display.columns = [
            'Logo',
            'Turnier', 
            'Stadt', 
            'Distanz', 
            'Startdatum', 
            'Enddatum', 
            'Link'
        ]
        
        # Datumsfelder für korrekte chronologische Sortierung konvertieren
        df_display['Startdatum_Parsed'] = pd.to_datetime(df_display['Startdatum'], format='%d.%m.%Y', errors='coerce')
        
        # Sortierung: Chronologisch nach Startdatum
        df_display = df_display.sort_values(by='Startdatum_Parsed', ascending=True, na_position='last')
        
        # Hilfsspalte entfernen
        df_display = df_display.drop(columns=['Startdatum_Parsed'])
        
        # Tabelle im Browser rendern
        st.dataframe(
            df_display,
            column_config={
                "Logo": st.column_config.ImageColumn(
                    "Logo",
                    help="Vereins- / Verbandsemblem"
                ),
                "Distanz": st.column_config.NumberColumn(
                    "Distanz",
                    format="%d km"
                ),
                "Link": st.column_config.LinkColumn("Meldung / Info")
            },
            hide_index=True,
            use_container_width=True
        )
    else:
        st.info("Der Suchlauf war erfolgreich, aber es wurden keine Turniere in Ihrem Umkreis gefunden.")
else:
    st.warning("Keine Turnier-Datenbank gefunden. Bitte klicken Sie oben auf 'Datenbank aktualisieren' für den ersten Suchlauf.")