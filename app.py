import streamlit as st
import pandas as pd
import json
import os
from tracker import check_for_updates, DB_FILE

st.set_page_config(page_title="Badminton Tournament Tracker", layout="wide")

st.title("🏸 Badminton Tournaments (Within 100km of 40723)")
st.write("Displays tournaments tracked via `turnier.de` based on your search filters.")

# Check now Button
if st.button("Check and Refresh Database"):
    with st.spinner("Checking for changes on turnier.de..."):
        check_for_updates()
    st.toast("Database updated!")

# Datenbank laden und anzeigen
if os.path.exists(DB_FILE):
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}

    if data:
        # DataFrame bauen
        df = pd.DataFrame(data.values())
        
        # Fallback für Felder, falls ältere Datensätze geladen werden
        fallback_cols = {
            'logo_url': '',
            'organizer': 'Unknown',
            'city': 'Unknown',
            'distance': None,
            'start_date': None,
            'end_date': None
        }
        for col, default in fallback_cols.items():
            if col not in df.columns:
                df[col] = default
            
        # Spalten anordnen (Logo ganz nach vorne) und umbenennen
        df_display = df[['logo_url', 'title', 'organizer', 'city', 'distance', 'start_date', 'end_date', 'tags', 'link']].copy()
        df_display.columns = [
            'Logo',
            'Competition', 
            'The Team', 
            'Location', 
            'Distance (km)', 
            'Start Date', 
            'End Date', 
            'Categories', 
            'Direct URL'
        ]
        
        # Datumsfelder für korrekte chronologische Sortierung temporär konvertieren
        df_display['Start Date Parsed'] = pd.to_datetime(df_display['Start Date'], format='%d.%m.%Y', errors='coerce')
        
        # Standard-Sortierung: Chronologisch nach Startdatum
        df_display = df_display.sort_values(by='Start Date Parsed', ascending=True, na_position='last')
        
        # Hilfsspalte entfernen
        df_display = df_display.drop(columns=['Start Date Parsed'])
        
        # Tabelle anzeigen
        st.dataframe(
            df_display,
            column_config={
                "Logo": st.column_config.ImageColumn(
                    "Logo",
                    help="Tournament / Association Logo"
                ),
                "Distance (km)": st.column_config.NumberColumn(
                    "Distance",
                    format="%d km"
                ),
                "Direct URL": st.column_config.LinkColumn("Register / View")
            },
            hide_index=True,
            use_container_width=True
        )
    else:
        st.info("The scan completed successfully, but no tournaments were found within your search range. We will notify you when one appears.")
else:
    st.warning("No tournament database found. Please click 'Check and Refresh Database' above to run the initial scan.")