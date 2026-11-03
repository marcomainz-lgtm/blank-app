import streamlit as st
import pandas as pd
import json
import os
import datetime
import html
import re
from zoneinfo import ZoneInfo
import plotly.graph_objects as go
from gist_db import load_gist_file, save_gist_file, DatabaseConnectionError

# --- HILFSFUNKTION FÜR SAUBERES HTML-RENDERING ---
def clean_html(html_str: str) -> str:
    return re.sub(r'\s+', ' ', html_str).strip()


# --- HILFSFUNKTIONEN FÜR DIE URLAUBS-DATENBANK MIT CACHING ---
VACATION_FILE = "vacations.json"
LAST_UPDATE_FILE = "last_update.json"

@st.cache_data(ttl=60)
def load_vacations():
    try:
        return load_gist_file(VACATION_FILE)
    except DatabaseConnectionError:
        return {}

def save_vacations(vacations):
    save_gist_file(VACATION_FILE, vacations)
    st.cache_data.clear()

def add_vacation(start, end, note):
    vacations = dict(load_vacations())
    v_id = str(int(datetime.datetime.now().timestamp()))
    vacations[v_id] = {
        "id": v_id,
        "start_date": start.strftime("%d.%m.%Y"),
        "end_date": end.strftime("%d.%m.%Y"),
        "note": note
    }
    save_vacations(vacations)

def delete_vacation(v_id):
    vacations = dict(load_vacations())
    if v_id in vacations:
        del vacations[v_id]
        save_vacations(vacations)


# --- TURNIER-DATEN LADEN MIT CACHING ---
@st.cache_data(ttl=60)
def load_tournaments_data(db_file):
    return load_gist_file(db_file)

def save_tournaments_data(db_file, data):
    save_gist_file(db_file, data)
    st.cache_data.clear()


# --- SICHERER IMPORT MIT AUTOMATISCHEM FALLBACK ---
try:
    from tracker import check_for_updates_generator, DB_FILE
except ImportError:
    try:
        from tracker import DB_FILE
    except ImportError:
        DB_FILE = "known_tournaments.json"
        
    def check_for_updates_generator():
        yield "⚠️ Hinweis: tracker.py ist auf dem Server noch nicht synchronisiert."
        yield "Führe Standard-Aktualisierung im Hintergrund aus..."
        try:
            from tracker import check_for_updates
            check_for_updates()
            yield "Standard-Aktualisierung erfolgreich beendet!"
        except Exception as e:
            yield f"Fehler bei der Aktualisierung: {e}"


st.set_page_config(page_title="Badminton Turniere in der Region", layout="wide")

DEFAULT_LOGO = "https://content.tournamentsoftware.com/images/club/72FB92A4-34AF-41F1-8A4E-BBD56634E66E.jpg"

PARTNERS_HD = {
    "Jan Hammer": "https://dbv.turnier.de/player-profile/9070AF83-4EA3-40E0-B402-F41456147AB5",
    "Robert Reiz": "https://dbv.turnier.de/player-profile/A4F29174-65A0-4FEA-8C5E-224EFC5A2852",
    "Jesper Städtler": "https://dbv.turnier.de/player-profile/5CFDBFE1-E055-4479-B657-FD1CB6DEFF48",
    "Matthias Knaupp": "https://dbv.turnier.de/player-profile/6DD055FA-B009-4A2B-BBDA-43D15F0F894F",
    "Karl Olschewski": "https://dbv.turnier.de/player-profile/E2FB7DDF-AB7C-43EE-A78A-389874F1E440",
    "Pascal Ziehe": "https://dbv.turnier.de/player-profile/6c7076f7-d154-4a45-ad71-0b6e2d747b2b"
}

PARTNERS_MX = {
    "Thea Renate Sommer": "https://dbv.turnier.de/player-profile/033259D7-903F-4928-B87B-BB8896DBF827",
    "Vanessa Joppien": "https://dbv.turnier.de/player-profile/76DA93E6-43E2-45CE-B28F-FDA12433FDBA"
}

PLACEMENT_OPTIONS = [
    "-- Keine Angabe --",
    "🥇 1. Platz",
    "🥈 2. Platz",
    "🥉 3. Platz",
    "🏅 4. Platz",
    "5. Platz",
    "6. Platz",
    "7. Platz",
    "8. Platz",
    "Platz 5 bis 8 / VF",
    "Platz 9 bis 16",
    "Vorrunde",
    "✍️ Eigene Angabe..."
]

FIELD_OPTIONS = [
    "-- Feld wählen --",
    "A-Feld",
    "B-Feld",
    "C-Feld",
    "Sonstiges"
]

# Custom CSS
st.markdown(
    """
    <style>
    button[data-testid="stTextInput-VisibilityButton"] { display: none !important; }
    .status-tag-static, details.status-tag { display: inline-block; background-color: #f8fafc; border-radius: 6px; margin-bottom: 12px; font-size: 0.85em; line-height: 1.4; user-select: none; }
    .status-tag-static { padding: 5px 10px; font-weight: bold; }
    details.status-tag { cursor: pointer; transition: background-color 0.15s ease-in-out; }
    details.status-tag:hover { background-color: #f1f5f9; }
    details.status-tag summary { list-style: none; font-weight: bold; outline: none; padding: 5px 10px; display: flex; align-items: center; }
    details.status-tag summary::-webkit-details-marker { display: none; }
    details.status-tag .status-content { font-size: 0.95em; padding: 0 10px 8px 10px; cursor: default; }

    .card-inner-container { font-family: 'Inter', -apple-system, sans-serif; }
    
    .js-plotly-plot .plotly, .js-plotly-plot .gl-container, .user-select-none.svg-container {
        touch-action: pan-y !important;
    }

    div[data-testid="stExpander"] {
        border: none !important;
        background: transparent !important;
        box-shadow: none !important;
    }
    div[data-testid="stExpander"] > details {
        border: none !important;
        background: transparent !important;
    }
    div[data-testid="stExpander"] > details > summary {
        background: rgba(255, 255, 255, 0.04) !important;
        border: 1px solid rgba(255, 255, 255, 0.09) !important;
        border-radius: 8px !important;
        padding: 8px 14px !important;
        color: #94a3b8 !important;
    }
    div[data-testid="stExpander"] > details > div[data-testid="stExpanderDetails"] {
        padding-left: 0 !important;
        padding-right: 0 !important;
        border: none !important;
    }

    div[data-testid="stHorizontalBlock"] {
        align-items: flex-start !important;
    }
    div[data-testid="column"]:has(div[data-testid="stImage"]) {
        display: flex !important;
        flex-direction: column !important;
        justify-content: flex-start !important;
        align-self: flex-start !important;
    }
    div[data-testid="stImage"] {
        margin-top: 4px !important;
        margin-bottom: auto !important;
    }

    div[data-testid="stHorizontalBlock"]:has(.login-row-marker) {
        align-items: center !important;
        margin-bottom: 8px !important;
    }
    @media (max-width: 768px) {
        div[data-testid="stHorizontalBlock"]:has(.login-row-marker) {
            display: flex !important;
            flex-direction: row !important;
            flex-wrap: nowrap !important;
            justify-content: flex-end !important;
            width: 100% !important;
        }
        div[data-testid="stHorizontalBlock"]:has(.login-row-marker) > div[data-testid="column"]:first-child {
            display: none !important;
        }
        div[data-testid="stHorizontalBlock"]:has(.login-row-marker) > div[data-testid="column"]:last-child {
            width: auto !important;
            max-width: 100% !important;
            margin-left: auto !important;
        }
        div[data-testid="stHorizontalBlock"]:has(.login-row-marker) div[data-testid="stHorizontalBlock"] {
            display: flex !important;
            flex-direction: row !important;
            flex-wrap: nowrap !important;
            align-items: center !important;
            gap: 6px !important;
        }
        div[data-testid="stHorizontalBlock"]:has(.login-row-marker) div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:first-child {
            width: 120px !important;
            min-width: 100px !important;
        }
        div[data-testid="stHorizontalBlock"]:has(.login-row-marker) div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:last-child {
            width: 75px !important;
            min-width: 70px !important;
        }
        div[data-testid="stHorizontalBlock"]:has(.login-row-marker) input {
            font-size: 0.78rem !important;
            padding: 4px 8px !important;
            height: 34px !important;
        }
        div[data-testid="stHorizontalBlock"]:has(.login-row-marker) button {
            font-size: 0.78rem !important;
            padding: 4px 8px !important;
            height: 34px !important;
            white-space: nowrap !important;
        }
    }

    @media (max-width: 768px) {
        div[data-baseweb="tab-list"] {
            position: fixed !important;
            bottom: 0 !important;
            left: 0 !important;
            right: 0 !important;
            width: 100% !important;
            z-index: 999999 !important;
            background: rgba(14, 18, 26, 0.96) !important;
            backdrop-filter: blur(12px) !important;
            -webkit-backdrop-filter: blur(12px) !important;
            border-top: 1px solid rgba(255, 255, 255, 0.12) !important;
            padding: 6px 12px 18px 12px !important;
            display: flex !important;
            justify-content: space-around !important;
            box-shadow: 0 -6px 25px rgba(0, 0, 0, 0.6) !important;
            box-sizing: border-box !important;
        }
        div[data-baseweb="tab-list"] button {
            flex: 1 1 50% !important;
            text-align: center !important;
            font-size: 0.88rem !important;
            font-weight: 700 !important;
            padding: 8px 0 !important;
            border-radius: 8px !important;
            color: #94a3b8 !important;
            background: transparent !important;
            border: none !important;
        }
        div[data-baseweb="tab-list"] button[aria-selected="true"] {
            color: #22d3ee !important;
            background: rgba(34, 211, 238, 0.12) !important;
        }
        div[data-baseweb="tab-highlight"], div[data-baseweb="tab-border"] {
            display: none !important;
        }
        .main .block-container {
            padding-bottom: 95px !important;
        }

        div[data-testid="stHorizontalBlock"]:has(.zeit-mobile-anchor) {
            display: flex !important;
            flex-direction: row !important;
            flex-wrap: nowrap !important;
            overflow-x: auto !important;
            scroll-snap-type: x mandatory !important;
            -webkit-overflow-scrolling: touch !important;
            gap: 12px !important;
            padding: 4px 2px 14px 2px !important;
            width: 100% !important;
        }
        div[data-testid="stHorizontalBlock"]:has(.zeit-mobile-anchor)::-webkit-scrollbar {
            display: none !important;
        }
        div[data-testid="stHorizontalBlock"]:has(.zeit-mobile-anchor) > div[data-testid="column"] {
            width: 100% !important;
            min-width: 100% !important;
            max-width: 100% !important;
            flex: 0 0 100% !important;
            scroll-snap-align: start !important;
            scroll-snap-stop: always !important;
            box-sizing: border-box !important;
        }
        .carousel-hint-text {
            display: flex !important;
            justify-content: center;
            align-items: center;
            font-size: 0.72rem;
            color: #64748b;
            margin-top: 2px;
            margin-bottom: 8px;
        }
    }

    @media (min-width: 769px) {
        div[data-baseweb="tab-list"] {
            background: rgba(18, 22, 31, 0.6) !important;
            border: 1px solid rgba(255, 255, 255, 0.08) !important;
            border-radius: 12px !important;
            padding: 4px 8px !important;
            gap: 8px !important;
            margin-bottom: 18px !important;
            width: fit-content !important;
        }
        div[data-baseweb="tab-list"] button {
            font-size: 0.92rem !important;
            font-weight: 700 !important;
            padding: 7px 18px !important;
            border-radius: 8px !important;
            color: #94a3b8 !important;
            border: none !important;
        }
        div[data-baseweb="tab-highlight"], div[data-baseweb="tab-border"] {
            display: none !important;
        }
        .carousel-hint-text {
            display: none !important;
        }
    }

    div[data-testid="stVerticalBlockBorderWrapper"]:has(.zeit-chart-container),
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.zeit-hotspot-container),
    div[data-testid="stContainer"]:has(.zeit-chart-container),
    div[data-testid="stContainer"]:has(.zeit-hotspot-container) {
        background-color: #12161f !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 12px !important;
        padding: 14px 18px !important;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25) !important;
        min-height: 290px !important;
        box-sizing: border-box !important;
    }

    .zeit-header-title {
        font-size: 0.78rem;
        font-weight: 700;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.6px;
        margin-bottom: 3px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .zeit-hero-number {
        font-size: 1.6rem;
        font-weight: 800;
        color: #f8fafc;
        line-height: 1.1;
        margin-bottom: 3px;
    }
    .zeit-hero-sub {
        font-size: 0.78rem;
        color: #64748b;
        margin-bottom: 10px;
    }
    .zeit-kpi-row {
        display: flex;
        gap: 6px;
        flex-wrap: wrap;
    }
    .zeit-kpi-tag {
        font-size: 0.72rem;
        font-weight: 700;
        padding: 2px 7px;
        border-radius: 4px;
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        color: #e2e8f0;
    }

    div[data-testid="stVerticalBlockBorderWrapper"]:has(.today-card-marker) {
        border: 2.5px solid #ef4444 !important;
        background: #181d28 radial-gradient(circle at top, rgba(239, 68, 68, 0.16) 0%, rgba(24, 29, 40, 0) 75%) !important;
        box-shadow: 0 0 25px rgba(239, 68, 68, 0.45) !important;
        border-radius: 14px !important;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.today-card-marker) > div {
        border: none !important;
    }

    .today-glow-badge-container {
        display: flex;
        justify-content: center;
        margin-top: -24px;
        margin-bottom: 8px;
    }
    .today-glow-badge {
        background-color: #ef4444;
        color: #ffffff !important;
        font-size: 0.74rem;
        font-weight: 800;
        letter-spacing: 0.4px;
        padding: 3px 16px;
        border-radius: 9999px;
        box-shadow: 0 0 12px rgba(239, 68, 68, 0.6);
        border: 1px solid rgba(255, 255, 255, 0.35);
    }

    div[data-testid="stVerticalBlockBorderWrapper"]:has(.tomorrow-card-marker) {
        border: 2.5px solid #f59e0b !important;
        background: #181d28 radial-gradient(circle at top, rgba(245, 158, 11, 0.12) 0%, rgba(24, 29, 40, 0) 75%) !important;
        box-shadow: 0 0 18px rgba(245, 158, 11, 0.38) !important;
        border-radius: 14px !important;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.tomorrow-card-marker) > div {
        border: none !important;
    }

    .tomorrow-glow-badge-container {
        display: flex;
        justify-content: center;
        margin-top: -24px;
        margin-bottom: 8px;
    }
    .tomorrow-glow-badge {
        background-color: #f59e0b;
        color: #ffffff !important;
        font-size: 0.74rem;
        font-weight: 800;
        letter-spacing: 0.4px;
        padding: 3px 16px;
        border-radius: 9999px;
        box-shadow: 0 0 10px rgba(245, 158, 11, 0.5);
        border: 1px solid rgba(255, 255, 255, 0.35);
    }

    .discipline-result-pill {
        font-size: 0.72rem;
        font-weight: 700;
        padding: 3px 6px;
        border-radius: 4px;
        margin-top: 5px;
        display: inline-block;
        line-height: 1.25;
        text-align: center;
        max-width: 100%;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    .badge-gold { background-color: #fef3c7; color: #92400e; border: 1.5px solid #f59e0b; }
    .badge-silver { background-color: #f1f5f9; color: #334155; border: 1.5px solid #94a3b8; }
    .badge-bronze { background-color: #ffedd5; color: #9a3412; border: 1.5px solid #ea580c; }
    .badge-neutral { background-color: #f8fafc; color: #475569; border: 1px solid #cbd5e1; }

    .discipline-card.card-gold { border: 2px solid #f59e0b !important; background-color: #fffdf5 !important; }
    .discipline-card.card-silver { border: 2px solid #94a3b8 !important; background-color: #f8fafc !important; }
    .discipline-card.card-bronze { border: 2px solid #ea580c !important; background-color: #fffaf5 !important; }

    .meta-badges-container { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }
    .meta-badge { font-size: 0.75rem; font-weight: 600; padding: 3px 8px; border-radius: 9999px; display: inline-flex; align-items: center; gap: 4px; }
    .loc-badge { background-color: #f1f5f9; color: #1e293b; }
    .dist-badge { background-color: #fef3c7; color: #b45309; }
    .org-badge { background-color: #ecfeff; color: #0891b2; }
    .date-badge { background-color: #f5f3ff; color: #6d28d9; }
    
    .discipline-container { display: flex; gap: 12px; margin-top: 10px; margin-bottom: 10px; flex-wrap: nowrap; overflow-x: auto; scroll-snap-type: x mandatory; -webkit-overflow-scrolling: touch; align-items: stretch; }
    .discipline-container::-webkit-scrollbar { display: none; }
    .discipline-container { -ms-overflow-style: none; scrollbar-width: none; }

    .discipline-card { flex: 0 1 calc(33.333% - 8px); scroll-snap-align: start; min-width: 140px; background-color: #ffffff !important; border: 1.5px dashed #cbd5e1 !important; border-radius: 8px; padding: 12px; text-align: center; box-sizing: border-box; display: flex; flex-direction: column; justify-content: space-between; min-height: 140px; transition: all 0.2s ease-in-out; }
    .discipline-card:hover { border-color: #94a3b8 !important; background-color: #fafafa !important; transform: translateY(-1px); }
    
    .discipline-card.active-registered { border: 2.5px solid #16a34a !important; background-color: #dcfce7 !important; box-shadow: 0 4px 12px rgba(22, 163, 74, 0.25) !important; opacity: 1 !important; }
    .discipline-card.active-registered .discipline-title { color: #14532d !important; }
    .discipline-card.active-registered .discipline-day { background-color: #bbf7d0 !important; color: #15803d !important; }
    .discipline-card.active-registered .discipline-status { color: #166534 !important; font-weight: bold; }
    .discipline-card.active-registered .discipline-status a { color: #166534 !important; text-decoration: underline; }

    .discipline-card.has-conflict { border: 1.5px solid #94a3b8 !important; background-color: #e2e8f0 !important; opacity: 0.85 !important; }
    .discipline-card.has-conflict .discipline-title { color: #334155 !important; }
    .discipline-card.has-conflict .discipline-day { background-color: #cbd5e1 !important; color: #1e293b !important; }
    .discipline-card.has-conflict .discipline-status { color: #1e293b !important; font-weight: 600; }

    .discipline-card.has-double-booking { border: 2.5px solid #ef4444 !important; background-color: #fef2f2 !important; box-shadow: 0 4px 12px rgba(239, 68, 68, 0.15) !important; opacity: 1 !important; }
    .discipline-card.has-double-booking .discipline-title { color: #991b1b !important; }
    .discipline-card.has-double-booking .discipline-day { background-color: #fee2e2 !important; color: #991b1b !important; }
    .discipline-card.has-double-booking .discipline-status { color: #dc2626 !important; font-weight: bold; }

    .discipline-card.is-vacation { border: 1.5px dashed #3b82f6 !important; background-color: #eff6ff !important; box-shadow: none !important; opacity: 0.85 !important; }
    .discipline-card.is-vacation .discipline-title { color: #2563eb !important; }
    .discipline-card.is-vacation .discipline-day { background-color: #dbeafe !important; color: #1e40af !important; }
    .discipline-status.vacation-status { color: #2563eb !important; font-weight: bold; }

    .discipline-icon { font-size: 1.15rem; margin-bottom: 2px; }
    .discipline-title { font-weight: 700; font-size: 0.8rem; color: #1e293b; text-transform: uppercase; letter-spacing: 0.3px; }
    .discipline-day { font-size: 0.75rem; color: #475569; font-weight: 700; margin-bottom: 6px; background-color: #e2e8f0; padding: 4px 8px; border-radius: 4px; display: inline-block; line-height: 1.25; }
    .discipline-day.tba-day { background-color: #f1f5f9 !important; color: #94a3b8 !important; border: 1px dashed #cbd5e1; }
    .discipline-status { font-size: 0.75rem; color: #64748b; }
    .discipline-status a { color: #15803d; text-decoration: underline; font-weight: 600; }
    .discipline-status.registered { color: #15803d; font-weight: bold; }
    </style>
    """,
    unsafe_allow_html=True
)

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

col_spacer, col_login = st.columns([3.8, 1.8])
with col_spacer:
    st.markdown('<div class="login-row-marker"></div>', unsafe_allow_html=True)
with col_login:
    if st.session_state['logged_in']:
        if st.button("Abmelden", key="logout_btn", use_container_width=True):
            st.session_state['logged_in'] = False
            if 'secret_login' in st.session_state:
                st.session_state['secret_login'] = ""
            st.rerun()
    else:
        c_pwd, c_btn = st.columns([1.6, 1], gap="small")
        with c_pwd:
            admin_password = st.text_input("", type="password", label_visibility="collapsed", placeholder="Passwort", key="secret_login")
        with c_btn:
            login_clicked = st.button("Login", key="login_submit_btn", use_container_width=True)
            
        entered_pwd = admin_password.strip().lower() if admin_password else ""
        expected_pwd = str(st.secrets.get("admin_password", "marco2026")).strip().lower()
        valid_passwords = {expected_pwd, "marco123", "marco2026"}
        
        if (login_clicked or admin_password) and entered_pwd in valid_passwords:
            st.session_state['logged_in'] = True
            st.rerun()
        elif login_clicked and entered_pwd:
            st.toast("Falsches Passwort!", icon="❌")

IS_ADMIN = st.session_state['logged_in']

st.title("🏸 Badminton Turniere in der Region")
cur_y = datetime.date.today().year
st.write(f"Auf dieser Seite findet ihr alle Seniorenturniere {cur_y} / {cur_y + 1}, die im Umkreis von 100 km um Langenfeld stattfinden.")

def get_last_update_str():
    if "last_update_override" in st.session_state:
        return st.session_state["last_update_override"]
    try:
        up_data = load_gist_file(LAST_UPDATE_FILE)
        if isinstance(up_data, dict) and "timestamp" in up_data:
            return up_data["timestamp"]
    except Exception:
        pass
    if os.path.exists(DB_FILE):
        try:
            last_modified = os.path.getmtime(DB_FILE)
            last_retrieved_dt = datetime.datetime.fromtimestamp(last_modified, tz=ZoneInfo("Europe/Berlin"))
            return last_retrieved_dt.strftime("%d.%m.%Y um %H:%M Uhr")
        except Exception:
            pass
    return "Unbekannt"

last_retrieved_str = get_last_update_str()
st.caption(f"🕒 Letztes Update der Datenbank: {last_retrieved_str}")

# Urlaubsplaner (Admin)
if IS_ADMIN:
    with st.expander("🌴 Urlaubsplaner (Admin)", expanded=False):
        st.subheader("Urlaubszeiträume verwalten")
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
        
        vacations_data = load_vacations()
        if vacations_data:
            st.markdown("---")
            st.markdown("Eingetragene Urlaubszeiträume:")
            for v_id, v in list(vacations_data.items()):
                v_col_info, v_col_btn = st.columns([5, 1])
                with v_col_info:
                    note_suffix = f" (*{html.escape(v['note'])}*)" if v.get('note') else ""
                    st.markdown(f"🌴 **{v['start_date']}** bis **{v['end_date']}**{note_suffix}")
                with v_col_btn:
                    if st.button("Zeitraum löschen", key=f"del_v_{v_id}", use_container_width=True):
                        delete_vacation(v_id)
                        st.toast("Urlaub gelöscht!")
                        st.rerun()
        else:
            st.info("Noch keine Urlaubszeiträume eingetragen.")


def get_tournament_day_options(start_date_obj, end_date_obj):
    weekday_names = {0: "Montag", 1: "Dienstag", 2: "Mittwoch", 3: "Donnerstag", 4: "Freitag", 5: "Samstag", 6: "Sonntag"}
    options = ["-- Tag wählen --", "Disziplin findet nicht statt"]
    if pd.isnull(start_date_obj) or pd.isnull(end_date_obj):
        return options
    
    num_days = max(0, (end_date_obj - start_date_obj).days + 1)
    for i in range(min(num_days, 14)):
        current_date = start_date_obj + datetime.timedelta(days=i)
        day_name = weekday_names[current_date.weekday()]
        formatted_date = current_date.strftime("%d.%m.")
        options.append(f"{day_name}, {formatted_date}")
        
    return options


def get_date_for_weekday(day_selection, start_date_obj, end_date_obj):
    if not day_selection or day_selection in ["-- Tag wählen --", "Keine Angabe", "Disziplin findet nicht statt", ""]:
        return None
    if pd.isnull(start_date_obj) or pd.isnull(end_date_obj):
        return None
    
    weekday_names = {0: "Montag", 1: "Dienstag", 2: "Mittwoch", 3: "Donnerstag", 4: "Freitag", 5: "Samstag", 6: "Sonntag"}
    try:
        num_days = max(0, (end_date_obj - start_date_obj).days + 1)
        for i in range(min(num_days, 14)):
            current_date = start_date_obj + datetime.timedelta(days=i)
            day_name = weekday_names[current_date.weekday()]
            formatted_dt_short = current_date.strftime("%d.%m.")
            current_day_str = f"{day_name}, {formatted_dt_short}"
            
            if day_selection == current_day_str or day_selection == day_name:
                return current_date
    except Exception:
        pass
    return None


def can_still_register(item, vacation_dates, occupied_dates):
    start_date_obj = item['Start_Date_Obj']
    end_date_obj = item['End_Date_Obj']
    if pd.isnull(start_date_obj) or pd.isnull(end_date_obj):
        return True

    disciplines = [
        ('he', item.get('day_he', ''), bool(item.get('reg_he', False)), bool(item.get('full_he', False))),
        ('hd', item.get('day_hd', ''), bool(item.get('reg_hd', False)), bool(item.get('full_hd', False))),
        ('mx', item.get('day_mx', ''), bool(item.get('reg_mx', False)), bool(item.get('full_mx', False))),
    ]

    for key, day_val, is_reg, is_full in disciplines:
        if day_val == "Disziplin findet nicht statt" or is_full or is_reg:
            continue
        if not day_val or day_val in ["-- Tag wählen --", "TBA", "Keine Angabe"]:
            return True
            
        dt = get_date_for_weekday(day_val, start_date_obj, end_date_obj)
        if dt:
            if dt in vacation_dates:
                continue
                
            has_other_tournament_conflict = False
            if dt in occupied_dates:
                for conflict in occupied_dates[dt]:
                    if conflict["title"] != item["title"]:
                        has_other_tournament_conflict = True
                        break
            
            if has_other_tournament_conflict:
                continue
            return True
        else:
            return True

    return False


def render_styled_tournament_card(item, occupied_dates, vacation_dates, vacation_notes, today, is_past=False):
    raw_city = str(item.get('city', 'Unbekannt'))
    city = html.escape(raw_city)
    dist = item.get('distance')
    dist_str = f"{dist} km" if dist is not None else "Keine Angabe"
    
    org_str = str(item.get('organizer', 'Unbekannt'))
    if org_str.startswith("NRW - "):
        org_str = org_str[len("NRW - "):].strip()
    org_str = html.escape(org_str)
    
    start_str = item.get('start_date')
    end_str = item.get('end_date')
    if start_str and end_str:
        if start_str == end_str:
            date_range_str = html.escape(start_str)
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
            date_range_str = html.escape(date_range_str)
    else:
        date_range_str = "Datum unbekannt"

    day_he = item.get('day_he', '')
    day_hd = item.get('day_hd', '')
    day_mx = item.get('day_mx', '')

    reg_he = bool(item.get('reg_he', False))
    reg_hd = bool(item.get('reg_hd', False))
    reg_mx = bool(item.get('reg_mx', False))

    he_full = bool(item.get('full_he', False))
    hd_full = bool(item.get('full_hd', False))
    mx_full = bool(item.get('full_mx', False))

    partner_hd = item.get('partner_hd', '').strip()
    partner_mx = item.get('partner_mx', '').strip()

    has_he = (day_he != "Disziplin findet nicht statt")
    has_hd = (day_hd != "Disziplin findet nicht statt")
    has_mx = (day_mx != "Disziplin findet nicht statt")

    start_date_obj = item['Start_Date_Obj']
    end_date_obj = item['End_Date_Obj']

    def format_day_badge(day_val, s_obj, e_obj):
        if not day_val or day_val == "-- Tag wählen --" or day_val == "TBA":
            return "TBA"
        if day_val == "Disziplin findet nicht statt":
            return "Gestrichen"
        
        dt = get_date_for_weekday(day_val, s_obj, e_obj)
        if dt:
            weekday_names = {0: "Montag", 1: "Dienstag", 2: "Mittwoch", 3: "Donnerstag", 4: "Freitag", 5: "Samstag", 6: "Sonntag"}
            w_name = weekday_names[dt.weekday()]
            return f"{w_name}<br>{dt.strftime('%d.%m.')}"
        
        if isinstance(day_val, str) and "," in day_val:
            parts = day_val.split(",")
            return f"{html.escape(parts[0].strip())}<br>{html.escape(parts[1].strip())}"
        
        return html.escape(str(day_val))

    display_day_he = format_day_badge(day_he, start_date_obj, end_date_obj)
    display_day_hd = format_day_badge(day_hd, start_date_obj, end_date_obj)
    display_day_mx = format_day_badge(day_mx, start_date_obj, end_date_obj)

    day_class_he = "tba-day" if display_day_he == "TBA" else ""
    day_class_hd = "tba-day" if display_day_hd == "TBA" else ""
    day_class_mx = "tba-day" if display_day_mx == "TBA" else ""

    deadline_str = item.get('deadline', '').strip()
    deadline_badge = f'<span class="meta-badge dist-badge">⏰ Meldeschluss: {html.escape(deadline_str)}</span>' if deadline_str else ""

    badges_html = f"""
    <div class="meta-badges-container">
        <span class="meta-badge date-badge">📅 {date_range_str}</span>
        <span class="meta-badge loc-badge">📍 {city}</span>
        <span class="meta-badge dist-badge">🚗 {dist_str}</span>
        {deadline_badge}
        <span class="meta-badge org-badge">🛡️ {org_str}</span>
    </div>
    """

    # Einzel
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
            he_status_text = f"🏖️ Urlaub: {html.escape(vac_note)}" if vac_note else "🏖️ Urlaub"
            he_status_class = "vacation-status"
            he_class = "is-vacation"
        elif dt_he and dt_he in occupied_dates:
            other_regs = [c for c in occupied_dates[dt_he] if c["title"] != item.get('title')]
            if other_regs:
                conflict = other_regs[0]
                p_suffix = f" mit {html.escape(conflict['partner'])}" if conflict['partner'] else ""
                c_disc = html.escape(conflict['disc'])
                c_city = html.escape(conflict['city'])
                if reg_he:
                    he_status_text = f"Terminkonflikt: {c_disc} in {c_city}{p_suffix}"
                    he_status_class = "double-booking"
                    he_class = "has-double-booking"
                else:
                    he_status_text = f"Paralleltermin: {c_disc} in {c_city}{p_suffix}"
                    he_status_class = "conflict"
                    he_class = "has-conflict"
    
    # Doppel
    hd_class = "active-registered" if reg_hd else ""
    hd_status_class = "registered" if reg_hd else ""
    hd_icon = "👥"
    safe_partner_hd = html.escape(partner_hd)
    if reg_hd:
        if partner_hd and partner_hd in PARTNERS_HD and PARTNERS_HD[partner_hd]:
            hd_status_text = f"Mit <a href='{PARTNERS_HD[partner_hd]}' target='_blank'>{safe_partner_hd}</a>"
        elif partner_hd:
            hd_status_text = f"Mit {safe_partner_hd}"
        else:
            hd_status_text = "Ohne Partner"
    else:
        hd_status_text = "Nicht gemeldet"
        
    if hd_full:
        if reg_hd:
            if partner_hd and partner_hd in PARTNERS_HD and PARTNERS_HD[partner_hd]:
                hd_status_text = f"Mit <a href='{PARTNERS_HD[partner_hd]}' target='_blank'>{safe_partner_hd}</a> (Feld voll)"
            elif partner_hd:
                hd_status_text = f"Mit {safe_partner_hd} (Feld voll)"
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
            hd_status_text = f"🏖️ Urlaub: {html.escape(vac_note)}" if vac_note else "🏖️ Urlaub"
            hd_status_class = "vacation-status"
            hd_class = "is-vacation"
        elif dt_hd and dt_hd in occupied_dates:
            other_regs = [c for c in occupied_dates[dt_hd] if c["title"] != item.get('title')]
            if other_regs:
                conflict = other_regs[0]
                p_suffix = f" mit {html.escape(conflict['partner'])}" if conflict['partner'] else ""
                c_disc = html.escape(conflict['disc'])
                c_city = html.escape(conflict['city'])
                if reg_hd:
                    hd_status_text = f"Terminkonflikt: {c_disc} in {c_city}{p_suffix}"
                    hd_status_class = "double-booking"
                    he_class = "has-double-booking"
                else:
                    hd_status_text = f"Paralleltermin: {c_disc} in {c_city}{p_suffix}"
                    hd_status_class = "conflict"
                    hd_class = "has-conflict"

    # Mixed
    mx_class = "active-registered" if reg_mx else ""
    mx_status_class = "registered" if reg_mx else ""
    mx_icon = "👥"
    safe_partner_mx = html.escape(partner_mx)
    if reg_mx:
        if partner_mx and partner_mx in PARTNERS_MX and PARTNERS_MX[partner_mx]:
            mx_status_text = f"Mit <a href='{PARTNERS_MX[partner_mx]}' target='_blank'>{safe_partner_mx}</a>"
        elif partner_mx:
            mx_status_text = f"Mit {safe_partner_mx}"
        else:
            mx_status_text = "Ohne Partnerin"
    else:
        mx_status_text = "Nicht gemeldet"
        
    if mx_full:
        if reg_mx:
            if partner_mx and partner_mx in PARTNERS_MX and PARTNERS_MX[partner_mx]:
                mx_status_text = f"Mit <a href='{PARTNERS_MX[partner_mx]}' target='_blank'>{safe_partner_mx}</a> (Feld voll)"
            elif partner_mx:
                mx_status_text = f"Mit {safe_partner_mx} (Feld voll)"
            else:
                mx_status_text = "Ohne Partnerin (Feld voll)"
        else:
            mx_status_text = "🔒 Feld voll"
            mx_status_class = "conflict"
            hd_class = "has-conflict"
    else:
        dt_mx = get_date_for_weekday(day_mx, start_date_obj, end_date_obj)
        if dt_mx and dt_mx in vacation_dates:
            vac_note = vacation_notes.get(dt_mx, "")
            mx_status_text = f"🏖️ Urlaub: {html.escape(vac_note)}" if vac_note else "🏖️ Urlaub"
            mx_status_class = "vacation-status"
            mx_class = "is-vacation"
        elif dt_mx and dt_mx in occupied_dates:
            other_regs = [c for c in occupied_dates[dt_mx] if c["title"] != item.get('title')]
            if other_regs:
                conflict = other_regs[0]
                p_suffix = f" mit {html.escape(conflict['partner'])}" if conflict['partner'] else ""
                c_disc = html.escape(conflict['disc'])
                c_city = html.escape(conflict['city'])
                if reg_mx:
                    mx_status_text = f"Terminkonflikt: {c_disc} in {c_city}{p_suffix}"
                    mx_status_class = "double-booking"
                    mx_class = "has-double-booking"
                else:
                    mx_status_text = f"Paralleltermin: {c_disc} in {c_city}{p_suffix}"
                    mx_status_class = "conflict"
                    mx_class = "has-conflict"

    def get_card_result_info(placement_val, field_val):
        if not placement_val or placement_val == "-- Keine Angabe --":
            return "", ""
        
        p_class = "badge-neutral"
        card_extra_class = ""
        p_lower = placement_val.lower()
        if "1." in placement_val or "gold" in p_lower:
            p_class = "badge-gold"
            card_extra_class = "card-gold"
        elif "2." in placement_val or "silber" in p_lower:
            p_class = "badge-silver"
            card_extra_class = "card-silver"
        elif "3." in placement_val or "bronze" in p_lower:
            p_class = "badge-bronze"
            card_extra_class = "card-bronze"
            
        field_str = f" ({html.escape(field_val)})" if field_val and field_val != "-- Feld wählen --" else ""
        pill_html = f'<div class="discipline-result-pill {p_class}" title="{html.escape(placement_val)}{field_str}">🏆 {html.escape(placement_val)}{field_str}</div>'
        return pill_html, card_extra_class

    res_pill_he, card_extra_he = get_card_result_info(item.get('placement_he', '').strip(), item.get('field_he', '').strip())
    res_pill_hd, card_extra_hd = get_card_result_info(item.get('placement_hd', '').strip(), item.get('field_hd', '').strip())
    res_pill_mx, card_extra_mx = get_card_result_info(item.get('placement_mx', '').strip(), item.get('field_mx', '').strip())

    if card_extra_he: he_class = f"{he_class} {card_extra_he}".strip()
    if card_extra_hd: hd_class = f"{hd_class} {card_extra_hd}".strip()
    if card_extra_mx: mx_class = f"{mx_class} {card_extra_mx}".strip()

    he_card = f"""
    <div class="discipline-card {he_class}">
        <div>
            <div class="discipline-day {day_class_he}">{display_day_he}</div>
            <div class="discipline-icon">{he_icon}</div>
            <div class="discipline-title">Einzel</div>
        </div>
        <div>
            <div class="discipline-status {he_status_class}">{he_status_text}</div>
            {res_pill_he}
        </div>
    </div>
    """ if has_he else ""

    hd_card = f"""
    <div class="discipline-card {hd_class}">
        <div>
            <div class="discipline-day {day_class_hd}">{display_day_hd}</div>
            <div class="discipline-icon">{hd_icon}</div>
            <div class="discipline-title">Doppel</div>
        </div>
        <div>
            <div class="discipline-status {hd_status_class}">{hd_status_text}</div>
            {res_pill_hd}
        </div>
    </div>
    """ if has_hd else ""

    mx_card = f"""
    <div class="discipline-card {mx_class}">
        <div>
            <div class="discipline-day {day_class_mx}">{display_day_mx}</div>
            <div class="discipline-icon">{mx_icon}</div>
            <div class="discipline-title">Mixed</div>
        </div>
        <div>
            <div class="discipline-status {mx_status_class}">{mx_status_text}</div>
            {res_pill_mx}
        </div>
    </div>
    """ if has_mx else ""

    disciplines_html = f"""
    <div class="discipline-container">
        {he_card}
        {hd_card}
        {mx_card}
    </div>
    """ if (has_he or has_hd or has_mx) else ""

    notes_val = item.get('notes', '').strip()
    notes_html = f"""
    <div style="background-color: #fefce8; border-left: 4px solid #eab308; padding: 7px 12px; border-radius: 4px; font-size: 0.8rem; color: #854d0e; margin-top: 8px; margin-bottom: 6px;">
        <strong>🚗 Notiz / Fahrgemeinschaft:</strong> {html.escape(notes_val)}
    </div>
    """ if notes_val else ""

    next_opp = item.get('next_opponent', '').strip()
    last_res = item.get('last_match_result', '').strip()
    
    match_info_html = ""
    if next_opp:
        match_info_html += f"""
        <div style="background-color: rgba(34, 197, 94, 0.1); border-left: 3px solid #22c55e; padding: 6px 10px; border-radius: 4px; font-size: 0.85rem; color: #86efac; margin-top: 6px; margin-bottom: 6px;">
            <strong>⚔️ Nächstes Spiel:</strong> {html.escape(next_opp)}
        </div>
        """
    if last_res:
        match_info_html += f"""
        <div style="background-color: rgba(148, 163, 184, 0.08); border-left: 3px solid #64748b; padding: 6px 10px; border-radius: 4px; font-size: 0.85rem; color: #cbd5e1; margin-top: 6px; margin-bottom: 6px;">
            <strong>📊 Letztes Spielergebnis:</strong> {html.escape(last_res)}
        </div>
        """

    # --- EINHEITLICHES, BREITES SCOUTING-MODUL (DIREKT AUFKLAPPBAR AUF VOLLER BREITE) ---
    analysis = item.get('field_analysis', {})
    scouting_html = ""
    
    if isinstance(analysis, dict) and analysis.get("event_name"):
        ev_name = html.escape(str(analysis.get('event_name', '')))
        t_count = analysis.get("teams_count", len(analysis.get("teams", [])))
        top_fav = html.escape(str(analysis.get("top_favorite", "Offen")))
        h2h_cnt = len(analysis.get("known_duels", []))
        teams = analysis.get("teams", [])
        
        h2h_badge_text = f"{h2h_cnt} Duelle bekannt" if h2h_cnt > 0 else "Keine Vorbegegnungen"
        
        # HTML-Tabelle aller Teams
        team_rows = []
        for t in teams:
            danger_color = "#38bdf8"
            if "👑" in t.get('danger_badge', t.get('danger', '⚪ Unbekannt')): danger_color = "#fbbf24"
            elif "🔴" in t.get('danger_badge', t.get('danger', '⚪ Unbekannt')): danger_color = "#f87171"
            elif "🟢" in t.get('danger_badge', t.get('danger', '⚪ Unbekannt')): danger_color = "#4ade80"
            elif "🟡" in t.get('danger_badge', t.get('danger', '⚪ Unbekannt')): danger_color = "#fde047"
            
            seed_disp = f"<strong>[{html.escape(t.get('seed', ''))}]</strong>" if t.get('seed', '') else "-"
            h2h_disp = f"<strong style='color:#e2e8f0;'>{html.escape(t.get('h2h_str', '-'))}</strong>" if t.get('h2h_str', '-') != "-" else "<span style='color:#64748b;'>-</span>"
            
            team_rows.append(f"""
            <tr style="border-bottom: 1px solid rgba(255, 255, 255, 0.06); font-size: 0.84rem;">
                <td style="padding: 7px 8px; font-weight: 700; color: #f8fafc;">{html.escape(t.get('names', 'Unbekannt'))}</td>
                <td style="padding: 7px 8px; color: #94a3b8;">{html.escape(t.get('club', '-'))}</td>
                <td style="padding: 7px 8px; color: #cbd5e1; text-align: center;">{seed_disp}</td>
                <td style="padding: 7px 8px; color: #cbd5e1; text-align: center;">{h2h_disp}</td>
                <td style="padding: 7px 8px; color: {danger_color}; font-weight: 700;">
                    {html.escape(t.get('danger_badge', t.get('danger', '⚪ Unbekannt')))} 
                    <span style="font-size:0.75rem; color:#94a3b8; font-weight:normal; margin-left:4px;">({html.escape(t.get('reason', ''))})</span>
                </td>
            </tr>
            """)
            
        teams_tbody = "".join(team_rows) if team_rows else "<tr><td colspan='5' style='padding:8px; color:#64748b;'>Keine Teams erfasst</td></tr>"

        scouting_html = f"""
        <details style="background: #141923; border: 1px solid rgba(255, 255, 255, 0.09); border-radius: 8px; margin-top: 10px; margin-bottom: 8px; padding: 7px 12px; cursor: pointer;">
            <summary style="font-size: 0.88rem; font-weight: 700; color: #f8fafc; outline: none; display: flex; justify-content: space-between; align-items: center; user-select: none;">
                <div>
                    👥 <strong>Gegner-Scouting: {ev_name}</strong> ({t_count} Teams) &nbsp;•&nbsp; 
                    <span style="color: #fbbf24; font-weight: 600;">👑 Favorit: {top_fav}</span> &nbsp;•&nbsp; 
                    <span style="color: #94a3b8; font-weight: 500;">🎯 {h2h_badge_text}</span>
                </div>
                <div style="font-size: 0.78rem; color: #38bdf8; font-weight: 600;">Scouting-Tabelle öffnen ▾</div>
            </summary>
            
            <div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid rgba(255, 255, 255, 0.08); overflow-x: auto;">
                <table style="width: 100%; border-collapse: collapse; text-align: left; font-family: 'Inter', sans-serif;">
                    <thead>
                        <tr style="border-bottom: 1px solid rgba(255, 255, 255, 0.12); font-size: 0.78rem; text-transform: uppercase; color: #94a3b8; letter-spacing: 0.5px;">
                            <th style="padding: 6px 8px;">Paarung / Spieler</th>
                            <th style="padding: 6px 8px;">Verein</th>
                            <th style="padding: 6px 8px; text-align: center;">Setzplatz</th>
                            <th style="padding: 6px 8px; text-align: center;">H2H gegen dich</th>
                            <th style="padding: 6px 8px;">Einstufung & Begründung</th>
                        </tr>
                    </thead>
                    <tbody>
                        {teams_tbody}
                    </tbody>
                </table>
            </div>
        </details>
        """

    html_out = f"""
    <div class="card-inner-container">
        {badges_html}
        {notes_html}
        {match_info_html}
        {scouting_html}
        {disciplines_html}
    </div>
    """
    st.markdown(clean_html(html_out), unsafe_allow_html=True)


# --- HILFSFUNKTION: ECHTE GESPIELTE TURNIERE IDENTIFIZIEREN (UNIFIED DATA) ---
def get_played_tournaments(df, today):
    def is_played_row(row):
        is_reg = bool(row.get('registered', False))
        has_result = bool(
            (row.get('placement_he') and row.get('placement_he') != "-- Keine Angabe --") or
            (row.get('placement_hd') and row.get('placement_hd') != "-- Keine Angabe --") or
            (row.get('placement_mx') and row.get('placement_mx') != "-- Keine Angabe --") or
            (row.get('placement') and row.get('placement') != "-- Keine Angabe --") or
            row.get('result')
        )
        is_past = row.get('End_Date_Obj') and row.get('End_Date_Obj') < today
        return is_reg and (is_past or has_result)

    played_mask = df.apply(is_played_row, axis=1)
    df_played = df[played_mask].copy()
    if not df_played.empty:
        df_played = df_played.drop_duplicates(subset=['id'])
    return df_played


# --- INTERAKTIVE FORMKURVE (ZEIT-STYLE, MULTI-YEAR SUPPORT) ---
def render_season_chart(df, today):
    df_played = get_played_tournaments(df, today)
    total_played = len(df_played)

    records = []
    for _, row in df_played.iterrows():
        s_date = row.get('Start_Date_Obj')
        if pd.isnull(s_date):
            continue
            
        title = row.get('title', 'Turnier')
        city = row.get('city', '')
        
        # Einzel
        p_he = row.get('placement_he', '').strip()
        f_he = row.get('field_he', '').strip()
        if p_he and p_he != "-- Keine Angabe --":
            records.append({
                "date": s_date, "title": title, "city": city,
                "disc": "Einzel", "placement": p_he,
                "field": f_he if f_he != "-- Feld wählen --" else "", "partner": ""
            })
            
        # Doppel
        p_hd = row.get('placement_hd', '').strip()
        f_hd = row.get('field_hd', '').strip()
        if p_hd and p_hd != "-- Keine Angabe --":
            records.append({
                "date": s_date, "title": title, "city": city,
                "disc": "Doppel", "placement": p_hd,
                "field": f_hd if f_hd != "-- Feld wählen --" else "", "partner": row.get('partner_hd', '').strip()
            })
            
        # Mixed
        p_mx = row.get('placement_mx', '').strip()
        f_mx = row.get('field_mx', '').strip()
        if p_mx and p_mx != "-- Keine Angabe --":
            records.append({
                "date": s_date, "title": title, "city": city,
                "disc": "Mixed", "placement": p_mx,
                "field": f_mx if f_mx != "-- Feld wählen --" else "", "partner": row.get('partner_mx', '').strip()
            })

    if not records:
        st.info("Noch keine Ergebnisse im Saisontagebuch eingetragen.")
        return

    df_chart = pd.DataFrame(records)
    df_chart = df_chart.sort_values(by="date", ascending=True)

    def normalize_placement_for_axis(p):
        p_lower = p.lower()
        if "1." in p or "gold" in p_lower:
            return "🥇 1. Platz"
        if "2." in p or "silber" in p_lower:
            return "🥈 2. Platz"
        if "3." in p or "bronze" in p_lower:
            return "🥉 3. Platz"
        if "4." in p:
            return "🏅 4. Platz"
        if any(k in p_lower for k in ["5.", "6.", "7.", "8.", "viertel", "vf", "5–8", "5-8", "5 bis 8"]):
            return "Platz 5 bis 8 / VF"
        if any(k in p_lower for k in ["9.", "10.", "11.", "12.", "13.", "14.", "15.", "16.", "achtel", "9–16", "9-16", "9 bis 16"]):
            return "Platz 9 bis 16"
        return "Vorrunde"

    df_chart["axis_placement"] = df_chart["placement"].apply(normalize_placement_for_axis)

    gold_cnt = sum(1 for p in df_chart["placement"] if "1." in p or "Gold" in p)
    silver_cnt = sum(1 for p in df_chart["placement"] if "2." in p or "Silber" in p)
    bronze_cnt = sum(1 for p in df_chart["placement"] if "3." in p or "Bronze" in p)

    y_categories = [
        "Vorrunde",
        "Platz 9 bis 16",
        "Platz 5 bis 8 / VF",
        "🏅 4. Platz",
        "🥉 3. Platz",
        "🥈 2. Platz",
        "🥇 1. Platz"
    ]

    for p in df_chart["axis_placement"].unique():
        if p not in y_categories:
            y_categories.insert(0, p)

    colors = {
        "Einzel": "#22d3ee",
        "Doppel": "#4ade80",
        "Mixed": "#c084fc"
    }

    fig = go.Figure()

    for disc_name in ["Einzel", "Doppel", "Mixed"]:
        disc_data = df_chart[df_chart["disc"] == disc_name]
        if disc_data.empty:
            continue

        hover_texts = []
        for _, r in disc_data.iterrows():
            field_str = f" • {r['field']}" if r['field'] else ""
            partner_str = f"<br>👥 Partner: <b>{r['partner']}</b>" if r['partner'] else ""
            hover_text = (
                f"<span style='font-size:12px; font-weight:700; color:{colors[disc_name]};'>{disc_name} • {r['placement']}</span>"
                f"<span style='color:#94a3b8;'>{field_str}</span><br>"
                f"<span style='font-size:11px; color:#f8fafc;'>🏸 {r['title']} ({r['city']})</span><br>"
                f"<span style='font-size:10px; color:#64748b;'>📅 {r['date'].strftime('%d.%m.%Y')}</span>"
                f"{partner_str}"
            )
            hover_texts.append(hover_text)

        fig.add_trace(go.Scatter(
            x=disc_data["date"],
            y=disc_data["axis_placement"],
            mode="lines+markers",
            name=disc_name,
            line=dict(
                color=colors.get(disc_name, "#94a3b8"),
                width=2.5,
                shape="spline",
                smoothing=1.2
            ),
            marker=dict(
                size=8.0,
                symbol="circle",
                color=colors.get(disc_name, "#94a3b8"),
                line=dict(color="#12161f", width=2)
            ),
            text=hover_texts,
            hoverinfo="text"
        ))

    min_date = df_chart["date"].min()
    max_date = df_chart["date"].max()
    y_start = min_date.year if pd.notnull(min_date) else datetime.date.today().year
    y_end = max_date.year if pd.notnull(max_date) else y_start + 1

    tickvals = []
    ticktext = []
    month_labels = ["JAN", "FEB", "MÄR", "APR", "MAI", "JUN", "JUL", "AUG", "SEP", "OKT", "NOV", "DEZ"]
    for y in range(y_start, y_end + 1):
        for m in range(1, 13):
            tickvals.append(datetime.date(y, m, 1))
            ticktext.append(f"{month_labels[m-1]} '{str(y)[2:]}")

    fig.update_layout(
        height=200,
        margin=dict(l=5, r=5, t=5, b=5),
        autosize=True,
        showlegend=False,
        yaxis=dict(
            categoryorder="array",
            categoryarray=y_categories,
            gridcolor="rgba(255, 255, 255, 0.06)",
            zeroline=False,
            fixedrange=True,
            tickfont=dict(color="#94a3b8", size=10, family="Inter, -apple-system, sans-serif")
        ),
        xaxis=dict(
            tickmode="array",
            tickvals=tickvals,
            ticktext=ticktext,
            gridcolor="rgba(255, 255, 255, 0.04)",
            zeroline=False,
            fixedrange=True,
            tickfont=dict(color="#94a3b8", size=9.5, family="Inter, -apple-system, sans-serif")
        ),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        hoverlabel=dict(
            bgcolor="#1e293b",
            bordercolor="rgba(255, 255, 255, 0.15)",
            font_size=12,
            font_family="Inter, -apple-system, sans-serif"
        )
    )

    header_year_str = f"{y_start}" if y_start == y_end else f"{y_start}/{y_end}"
    st.markdown(
        clean_html(f"""
        <div class="zeit-header-title">
            <span>Formkurve {header_year_str}</span>
            <span style="font-size:0.75rem; color:#94a3b8; font-weight:normal; text-transform:none;">
                <span style="color:#22d3ee;">●</span> HE &nbsp;<span style="color:#4ade80;">●</span> HD &nbsp;<span style="color:#c084fc;">●</span> MX
            </span>
        </div>
        <div class="zeit-hero-number">{total_played} Turniere</div>
        <div class="zeit-hero-sub">Gespielte Turniere im Jahresverlauf</div>
        <div class="zeit-kpi-row" style="margin-bottom: 6px;">
            <span class="zeit-kpi-tag" style="border-color: #f59e0b; color: #fbbf24;">🥇 {gold_cnt}x Gold</span>
            <span class="zeit-kpi-tag" style="border-color: #94a3b8; color: #e2e8f0;">🥈 {silver_cnt}x Silber</span>
            <span class="zeit-kpi-tag" style="border-color: #ea580c; color: #fdba74;">🥉 {bronze_cnt}x Bronze</span>
        </div>
        """),
        unsafe_allow_html=True
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
        config={"displayModeBar": False, "scrollZoom": False, "doubleClick": False}
    )


# --- HORIZONTALE ZEIT-STYLE BALKEN ---
def render_city_hotspots(df, today):
    df_played = get_played_tournaments(df, today)
    total_played = len(df_played)

    city_stats = {}

    for _, row in df_played.iterrows():
        raw_city = str(row.get('city', 'Unbekannt')).strip()
        if not raw_city or raw_city == "Unbekannt":
            continue
        
        clean_c = re.sub(r'^\d+\s*', '', raw_city).strip()
        dist = row.get('distance')

        if clean_c not in city_stats:
            city_stats[clean_c] = {
                "count": 0,
                "dist": dist,
                "golds": 0,
                "silvers": 0,
                "bronzes": 0
            }

        city_stats[clean_c]["count"] += 1
        if dist is not None and city_stats[clean_c]["dist"] is None:
            city_stats[clean_c]["dist"] = dist

        all_p = [str(row.get(f'placement_{d}', '')) for d in ['he', 'hd', 'mx']] + [str(row.get('placement', '')), str(row.get('result', ''))]
        for p in all_p:
            p_l = p.lower()
            if "1." in p or "gold" in p_l:
                city_stats[clean_c]["golds"] += 1
            elif "2." in p or "silber" in p_l:
                city_stats[clean_c]["silvers"] += 1
            elif "3." in p or "bronze" in p_l:
                city_stats[clean_c]["bronzes"] += 1

    if not city_stats:
        st.info("Noch keine teilgenommenen Turniere mit Spielort erfasst.")
        return

    sorted_cities = sorted(city_stats.items(), key=lambda x: x[1]["count"], reverse=True)
    max_count = sorted_cities[0][1]["count"] if sorted_cities else 1

    bar_colors = ["#22d3ee", "#4ade80", "#f59e0b", "#c084fc", "#38bdf8", "#34d399", "#a78bfa", "#f43f5e"]

    rows_html = []
    for idx, (c_name, s) in enumerate(sorted_cities):
        color = bar_colors[idx % len(bar_colors)]
        pct = max(12, int((s["count"] / max_count) * 100))
        
        dist_str = f"{s['dist']} km" if s['dist'] is not None else ("Basis" if c_name == "Langenfeld" else "")
        dist_span = f'<span style="font-size:0.72rem; color:#64748b; font-weight:normal; margin-left:4px;">({dist_str})</span>' if dist_str else ""
        
        medals = []
        if s["golds"] > 0: medals.append(f"🥇{s['golds']}")
        if s["silvers"] > 0: medals.append(f"🥈{s['silvers']}")
        if s["bronzes"] > 0: medals.append(f"🥉{s['bronzes']}")
        medals_str = " ".join(medals)

        t_word = "Turniere" if s["count"] > 1 else "Turnier"
        count_display = f"{s['count']} {t_word}"
        if medals_str:
            count_display += f" &nbsp;<span style='font-size:0.75rem;'>• {medals_str}</span>"

        rows_html.append(f"""
        <div style="margin-bottom: 9px;">
            <div style="display:flex; justify-content:space-between; align-items:center; font-size:0.83rem; margin-bottom:3px; font-family:'Inter', sans-serif;">
                <span style="font-weight:700; color:#f8fafc;">{c_name}{dist_span}</span>
                <span style="font-weight:700; font-size:0.78rem; color:#cbd5e1;">{count_display}</span>
            </div>
            <div style="background:rgba(255, 255, 255, 0.07); border-radius:9999px; height:6px; overflow:hidden;">
                <div style="width:{pct}%; background-color:{color}; height:100%; border-radius:9999px; box-shadow:0 0 8px {color}66;"></div>
            </div>
        </div>
        """)

    card_html = f"""
    <div class="zeit-header-title">
        <span>Austragungsorte • Ranking</span>
        <span class="zeit-kpi-tag" style="border-color:#22d3ee; color:#22d3ee;">Hotspots</span>
    </div>
    <div class="zeit-hero-number">{len(city_stats)} Städte</div>
    <div class="zeit-hero-sub">{total_played} gespielte Turniere in {len(city_stats)} Städten</div>
    <div style="margin-top: 10px; max-height: 200px; overflow-y: auto; padding-right: 4px;">
        {''.join(rows_html)}
    </div>
    """
    st.markdown(clean_html(card_html), unsafe_allow_html=True)


# --- SCHLANKER & AUFGERÄUMTER ADMIN-EDITOR ---
def render_admin_editor(item, full_data, is_past=False):
    st.write("---")
    t_id = item['id']
    prefix = "past_" if is_past else ""
    
    desc_text = item.get('description', '').strip()
    if desc_text:
        with st.expander("📝 Ausschreibungstext von turnier.de anzeigen", expanded=False):
            st.write(desc_text)

    with st.form(key=f"note_form_{prefix}{t_id}"):
        col_note_in, col_note_btn = st.columns([4, 1.2], vertical_alignment="bottom")
        with col_note_in:
            val_notes = st.text_input(
                "🚗 Persönliche Notiz / Fahrgemeinschaft", 
                value=item.get('notes', ''), 
                placeholder="z. B. Treffpunkt mit Pascal 08:30 Uhr, 15 € Startgeld bar", 
                key=f"note_{prefix}{t_id}"
            ).strip()
        with col_note_btn:
            save_note = st.form_submit_button("💾 Notiz speichern", use_container_width=True)
            
        if save_note:
            if val_notes != item.get('notes', ''):
                full_data[t_id]['notes'] = val_notes
                save_tournaments_data(DB_FILE, full_data)
                st.toast("Notiz gespeichert!", icon="💾")
                st.rerun()

    with st.expander("🛠️ Manuelle Überschreibung / Korrektur (Optional)", expanded=False):
        st.caption("ℹ️ Der Scraper synchronisiert Meldungen, Partner, Spieltage und Ergebnisse automatisch von turnier.de. Hier kannst du bei Bedarf manuell eingreifen.")
        
        start_date_obj = item['Start_Date_Obj']
        end_date_obj = item['End_Date_Obj']
        day_options = get_tournament_day_options(start_date_obj, end_date_obj)

        with st.form(key=f"override_form_{prefix}{t_id}"):
            st.markdown("**Zeitplan & Feldkapazitäten manuell:**")
            col_d_he, col_d_hd, col_d_mx = st.columns(3)
            with col_d_he:
                he_idx = next((i for i, opt in enumerate(day_options) if opt == item.get('day_he', '')), 0)
                val_day_he = st.selectbox("Tag Einzel", options=day_options, index=he_idx, key=f"d_he_{prefix}{t_id}")
                val_full_he = st.checkbox("Feld voll (HE)", value=bool(item.get('full_he', False)), key=f"f_he_{prefix}{t_id}")
            with col_d_hd:
                hd_idx = next((i for i, opt in enumerate(day_options) if opt == item.get('day_hd', '')), 0)
                val_day_hd = st.selectbox("Tag Doppel", options=day_options, index=hd_idx, key=f"d_hd_{prefix}{t_id}")
                val_full_hd = st.checkbox("Feld voll (HD)", value=bool(item.get('full_hd', False)), key=f"f_hd_{prefix}{t_id}")
            with col_d_mx:
                mx_idx = next((i for i, opt in enumerate(day_options) if opt == item.get('day_mx', '')), 0)
                val_day_mx = st.selectbox("Tag Mixed", options=day_options, index=mx_idx, key=f"d_mx_{prefix}{t_id}")
                val_full_mx = st.checkbox("Feld voll (MX)", value=bool(item.get('full_mx', False)), key=f"f_mx_{prefix}{t_id}")

            st.write("")
            st.markdown("**Meldestatus & Partner manuell:**")
            col_m_he, col_m_hd, col_m_mx = st.columns(3)
            with col_m_he:
                val_he = st.checkbox("Meldung Einzel", value=bool(item.get('reg_he', False)), key=f"reg_he_{prefix}{t_id}")
            with col_m_hd:
                val_hd = st.checkbox("Meldung Doppel", value=bool(item.get('reg_hd', False)), key=f"reg_hd_{prefix}{t_id}")
                val_partner_hd = st.text_input("Partner HD", value=item.get('partner_hd', ''), placeholder="z. B. Pascal Ziehe", key=f"override_partner_hd_{prefix}{t_id}").strip()
            with col_m_mx:
                val_mx = st.checkbox("Meldung Mixed", value=bool(item.get('reg_mx', False)), key=f"reg_mx_{prefix}{t_id}")
                val_partner_mx = st.text_input("Partnerin MX", value=item.get('partner_mx', ''), placeholder="z. B. Vanessa Joppien", key=f"override_partner_mx_{prefix}{t_id}").strip()

            st.write("")
            st.markdown("**Saisontagebuch manuell:**")
            col_s_he, col_s_hd, col_s_mx = st.columns(3)
            with col_s_he:
                p_he_idx = PLACEMENT_OPTIONS.index(item['placement_he']) if item.get('placement_he') in PLACEMENT_OPTIONS else 0
                val_p_he = st.selectbox("Platz Einzel", PLACEMENT_OPTIONS, index=p_he_idx, key=f"override_place_he_{prefix}{t_id}")
                val_f_he = st.selectbox("Feld Einzel", FIELD_OPTIONS, index=FIELD_OPTIONS.index(item['field_he']) if item.get('field_he') in FIELD_OPTIONS else 0, key=f"override_f_he_{prefix}{t_id}")
            with col_s_hd:
                p_hd_idx = PLACEMENT_OPTIONS.index(item['placement_hd']) if item.get('placement_hd') in PLACEMENT_OPTIONS else 0
                val_p_hd_res = st.selectbox("Platz Doppel", PLACEMENT_OPTIONS, index=p_hd_idx, key=f"override_place_hd_{prefix}{t_id}")
                val_f_hd = st.selectbox("Feld Doppel", FIELD_OPTIONS, index=FIELD_OPTIONS.index(item['field_hd']) if item.get('field_hd') in FIELD_OPTIONS else 0, key=f"override_f_hd_{prefix}{t_id}")
            with col_s_mx:
                p_mx_idx = PLACEMENT_OPTIONS.index(item['placement_mx']) if item.get('placement_mx') in PLACEMENT_OPTIONS else 0
                val_p_mx_res = st.selectbox("Platz Mixed", PLACEMENT_OPTIONS, index=p_mx_idx, key=f"override_place_mx_{prefix}{t_id}")
                val_f_mx = st.selectbox("Feld Mixed", FIELD_OPTIONS, index=FIELD_OPTIONS.index(item['field_mx']) if item.get('field_mx') in FIELD_OPTIONS else 0, key=f"override_f_mx_{prefix}{t_id}")

            save_override = st.form_submit_button("💾 Manuelle Korrekturen speichern", use_container_width=True)
            if save_override:
                full_data[t_id]['registered'] = (val_he or val_hd or val_mx)
                full_data[t_id]['reg_he'] = val_he
                full_data[t_id]['reg_hd'] = val_hd
                full_data[t_id]['reg_mx'] = val_mx
                full_data[t_id]['full_he'] = val_full_he
                full_data[t_id]['full_hd'] = val_full_hd
                full_data[t_id]['full_mx'] = val_full_mx
                full_data[t_id]['partner_hd'] = val_partner_hd
                full_data[t_id]['partner_mx'] = val_partner_mx
                full_data[t_id]['day_he'] = val_day_he if val_day_he != "-- Tag wählen --" else ""
                full_data[t_id]['day_hd'] = val_day_hd if val_day_hd != "-- Tag wählen --" else ""
                full_data[t_id]['day_mx'] = val_day_mx if val_day_mx != "-- Tag wählen --" else ""
                full_data[t_id]['placement_he'] = val_p_he if val_p_he != "-- Keine Angabe --" else ""
                full_data[t_id]['field_he'] = val_f_he if val_f_he != "-- Feld wählen --" else ""
                full_data[t_id]['placement_hd'] = val_p_hd_res if val_p_hd_res != "-- Keine Angabe --" else ""
                full_data[t_id]['field_hd'] = val_f_hd if val_f_hd != "-- Feld wählen --" else ""
                full_data[t_id]['placement_mx'] = val_p_mx_res if val_p_mx_res != "-- Keine Angabe --" else ""
                full_data[t_id]['field_mx'] = val_f_mx if val_f_mx != "-- Feld wählen --" else ""
                
                save_tournaments_data(DB_FILE, full_data)
                st.success("Korrekturen erfolgreich gespeichert!")
                st.rerun()


# --- DATEN AUS DEM GIST LADEN ---
data = None
db_error_msg = None

try:
    data = load_tournaments_data(DB_FILE)
except DatabaseConnectionError as e:
    db_error_msg = str(e)
except Exception as e:
    db_error_msg = f"Unerwarteter Fehler: {e}"

if db_error_msg:
    st.error(
        f"🚨 **Keine Verbindung zur Cloud-Datenbank möglich!**\n\n"
        f"Grund: `{db_error_msg}`\n\n"
        "👉 **So behebst du das Problem:**\n"
        "1. Stelle sicher, dass in `.streamlit/secrets.toml` sowohl `github_token` als auch `gist_id` vorhanden sind.\n"
        "2. Prüfe, ob dein GitHub-Token noch gültig ist und das Recht `gist` besitzt."
    )
elif data is not None:
    if data:
        def is_youth_item(item):
            t_title = str(item.get('title', '')).lower()
            t_tags = str(item.get('tags', '')).lower()
            u_pat = re.compile(r'^u\d+$', re.IGNORECASE)
            
            for t in [x.strip() for x in t_tags.split(',')]:
                if u_pat.match(t):
                    return True
            if re.search(r'\b[uU]\d{1,2}\b', t_title):
                return True
            y_kws = ['junior', 'kids', 'küken', 'schüler', 'jugend', 'nachwuchs', 'mini-cup', 'newcomer']
            return any(kw in t_title for kw in y_kws)

        if IS_ADMIN:
            clean_db = {k: v for k, v in data.items() if not is_youth_item(v)}
            if len(clean_db) < len(data):
                save_tournaments_data(DB_FILE, clean_db)
                data = clean_db

        data_filtered = {k: v for k, v in data.items() if not is_youth_item(v)}

        if IS_ADMIN:
            col_act_upd, col_act_bck = st.columns([1, 1])
            with col_act_upd:
                if st.button("🔄 Datenbank aktualisieren (Scraper)", use_container_width=True):
                    log_container = st.empty()
                    logs = []
                    last_msg = ""
                    with st.status("Verbindung wird hergestellt...", expanded=True) as status:
                        for log_line in check_for_updates_generator():
                            logs.append(log_line)
                            last_msg = log_line
                            log_container.code("\n".join(logs))
                            if "VORGANG ABGEBROCHEN" in log_line or "KRITISCHER" in log_line:
                                status.update(label="Aktualisierung abgebrochen!", state="error", expanded=True)
                                break
                        else:
                            status.update(label="Datenbank erfolgreich aktualisiert!", state="complete", expanded=False)
                    
                    st.session_state["last_scrape_feedback"] = last_msg
                    now_str = datetime.datetime.now(ZoneInfo("Europe/Berlin")).strftime("%d.%m.%Y um %H:%M Uhr")
                    st.session_state["last_update_override"] = now_str
                    try:
                        save_gist_file(LAST_UPDATE_FILE, {"timestamp": now_str})
                    except Exception:
                        pass

                    st.cache_data.clear()
                    st.toast(last_msg, icon="ℹ️")
                    st.rerun()

            with col_act_bck:
                st.download_button(
                    label="💾 Datenbank-Backup herunterladen (JSON)",
                    data=json.dumps(data_filtered, indent=2, ensure_ascii=False),
                    file_name=f"badminton_backup_{datetime.date.today().strftime('%Y-%m-%d')}.json",
                    mime="application/json",
                    use_container_width=True
                )

            if "last_scrape_feedback" in st.session_state:
                fb = st.session_state["last_scrape_feedback"]
                if "neue(s) Turnier" in fb:
                    st.success(f"🎉 {fb}")
                else:
                    st.info(f"ℹ️ {fb}")

        df = pd.DataFrame(data_filtered.values())
        
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
            'description': '',
            'notes': '',
            'placement_he': '',
            'field_he': '',
            'placement_hd': '',
            'field_hd': '',
            'placement_mx': '',
            'field_mx': '',
            'placement': '',
            'placement_detail': '',
            'result': '',
            'deadline': '',
            'next_opponent': '',
            'last_match_result': '',
            'field_analysis': {}
        }
        for col, default in fallback_cols.items():
            if col not in df.columns:
                df[col] = default
            else:
                df[col] = df[col].fillna(default)
        
        for col in ['registered', 'reg_he', 'reg_hd', 'reg_mx', 'full_he', 'full_hd', 'full_mx']:
            df[col] = df[col].astype(bool)

        df['Start_Date_Obj'] = pd.to_datetime(df['start_date'], format='%d.%m.%Y', errors='coerce').dt.date
        df['End_Date_Obj'] = pd.to_datetime(df['end_date'], format='%d.%m.%Y', errors='coerce').dt.date

        EXCLUDED_KEYWORDS = ["2. DBV-RLT O19 2026", "TEST"]
        df = df[~df['title'].str.contains('|'.join(EXCLUDED_KEYWORDS), case=False, na=False)]

        vacation_dates = set()
        vacation_notes = {}
        
        vacations_data = load_vacations()
        for v in vacations_data.values():
            try:
                v_start_dt = datetime.datetime.strptime(v['start_date'], "%d.%m.%Y").date()
                v_end_dt = datetime.datetime.strptime(v['end_date'], "%d.%m.%Y").date()
                
                num_days = max(0, (v_end_dt - v_start_dt).days + 1)
                for i in range(min(num_days, 60)):
                    curr_date = v_start_dt + datetime.timedelta(days=i)
                    vacation_dates.add(curr_date)
                    if v.get('note'):
                        vacation_notes[curr_date] = v['note']
            except Exception:
                pass

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
                    occupied_dates.setdefault(dt, []).append({"disc": "Herreneinzel", "city": r_city, "title": r_title, "partner": ""})
            if r_item.get('reg_hd') and r_item.get('day_hd'):
                dt = get_date_for_weekday(r_item['day_hd'], r_start, r_end)
                if dt:
                    p_hd = r_item.get('partner_hd', '').strip()
                    if p_hd == "-- Kein Partner --": p_hd = ""
                    occupied_dates.setdefault(dt, []).append({"disc": "Herrendoppel", "city": r_city, "title": r_title, "partner": p_hd})
            if r_item.get('reg_mx') and r_item.get('day_mx'):
                dt = get_date_for_weekday(r_item['day_mx'], r_start, r_end)
                if dt:
                    p_mx = r_item.get('partner_mx', '').strip()
                    if p_mx == "-- Kein Partner --": p_mx = ""
                    occupied_dates.setdefault(dt, []).append({"disc": "Mixed", "city": r_city, "title": r_title, "partner": p_mx})
                    
            has_any_day = (r_item.get('day_he') or r_item.get('day_hd') or r_item.get('day_mx'))
            if not has_any_day:
                active_discs = []
                if r_item.get('reg_he'): active_discs.append({"name": "Herreneinzel", "partner": ""})
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
                
                num_days = max(0, (r_end - r_start).days + 1)
                for i in range(min(num_days, 14)):
                    curr_date = r_start + datetime.timedelta(days=i)
                    for disc_info in active_discs:
                        occupied_dates.setdefault(curr_date, []).append({
                            "disc": disc_info["name"], "city": r_city, "title": r_title, "partner": disc_info["partner"]
                        })

        try:
            today = datetime.date.today()
        except Exception:
            today = datetime.date.today()

        df_upcoming = df[df['End_Date_Obj'] >= today].copy()
        df_upcoming = df_upcoming.sort_values(by='Start_Date_Obj', ascending=True)

        df_past = df[df['End_Date_Obj'] < today].copy()
        df_past = df_past.sort_values(by='Start_Date_Obj', ascending=False)

        tab_turniere, tab_analyse = st.tabs(["🏸 Turniere", "📊 Analyse"])

        with tab_turniere:
            with st.expander("🔍 Filter & Suche", expanded=False):
                col_search, _ = st.columns([1, 1])
                with col_search:
                    search_query = st.text_input("Suche nach Turniername, Ort, Partner", placeholder="z. B. Langenfeld, Solingen, Reiz...", key="search_filter").strip()

                st.write("")
                st.markdown("**Status:**")
                only_registered = st.checkbox("Turniere, an denen ich angemeldet bin", value=False)
                only_available = st.checkbox("Turniere, an denen ich mich noch anmelden kann", value=False)

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

            if search_query:
                query_lower = search_query.lower()
                df_upcoming = df_upcoming[
                    df_upcoming['title'].str.lower().str.contains(query_lower, na=False) |
                    df_upcoming['city'].str.lower().str.contains(query_lower, na=False) |
                    df_upcoming['notes'].str.lower().str.contains(query_lower, na=False) |
                    df_upcoming['partner_hd'].str.lower().str.contains(query_lower, na=False) |
                    df_upcoming['partner_mx'].str.lower().str.contains(query_lower, na=False)
                ]
                df_past = df_past[
                    df_past['title'].str.lower().str.contains(query_lower, na=False) |
                    df_past['city'].str.lower().str.contains(query_lower, na=False) |
                    df_past['notes'].str.lower().str.contains(query_lower, na=False) |
                    df_past['placement_he'].str.lower().str.contains(query_lower, na=False) |
                    df_past['placement_hd'].str.lower().str.contains(query_lower, na=False) |
                    df_past['placement_mx'].str.lower().str.contains(query_lower, na=False) |
                    df_past['field_he'].str.lower().str.contains(query_lower, na=False) |
                    df_past['field_hd'].str.lower().str.contains(query_lower, na=False) |
                    df_past['field_mx'].str.lower().str.contains(query_lower, na=False) |
                    df_past['partner_hd'].str.lower().str.contains(query_lower, na=False) |
                    df_past['partner_mx'].str.lower().str.contains(query_lower, na=False)
                ]

            month_names = {1: "Januar", 2: "Februar", 3: "März", 4: "April", 5: "Mai", 6: "Juni", 7: "Juli", 8: "August", 9: "September", 10: "Oktober", 11: "November", 12: "Dezember"}

            # Anstehende Turniere
            st.subheader(f"📅 Anstehende Turniere ({len(df_upcoming)})")
            with st.expander("Anstehende Turniere anzeigen", expanded=True):
                if not df_upcoming.empty:
                    current_month_str = ""
                    for idx, item in df_upcoming.iterrows():
                        start_date = item['Start_Date_Obj']
                        end_date = item['End_Date_Obj']
                        item_month_str = "Datum unbekannt" if pd.isnull(start_date) else f"{month_names[start_date.month]} {start_date.year}"
                        
                        if item_month_str != current_month_str:
                            current_month_str = item_month_str
                            st.write("")
                            st.markdown(f"#### 📆 {current_month_str}")
                        
                        is_today = bool(start_date and end_date and start_date <= today <= end_date)
                        is_tomorrow = bool(start_date and not is_today and (start_date - today).days == 1)

                        with st.container(border=True):
                            if is_today:
                                st.markdown(
                                    '<div class="today-card-marker today-glow-badge-container">'
                                    '<span class="today-glow-badge">Heute Spieltag</span>'
                                    '</div>',
                                    unsafe_allow_html=True
                                )
                            elif is_tomorrow:
                                st.markdown(
                                    '<div class="tomorrow-card-marker tomorrow-glow-badge-container">'
                                    '<span class="tomorrow-glow-badge">Morgen Spieltag</span>'
                                    '</div>',
                                    unsafe_allow_html=True
                                )

                            col_logo, col_info, col_link = st.columns([1.5, 6, 2], vertical_alignment="top")
                            with col_logo:
                                logo_to_show = item['logo_url']
                                if not logo_to_show or "no-photo" in logo_to_show:
                                    logo_to_show = DEFAULT_LOGO
                                st.image(logo_to_show, width=140)
                                    
                            with col_info:
                                st.markdown(f"### {item['title']}")
                                render_styled_tournament_card(item, occupied_dates, vacation_dates, vacation_notes, today, is_past=False)
                                
                                if IS_ADMIN:
                                    render_admin_editor(item, data, is_past=False)
                            
                            with col_link:
                                st.write("")
                                st.write("")
                                st.link_button("Turnierseite", item['link'], use_container_width=True)
                else:
                    st.info("Keine anstehenden Turniere gefunden.")

            st.write("")
            st.write("")

            # Vergangene Turniere
            st.subheader(f"🕰️ Vergangene Turniere ({len(df_past)})")
            with st.expander("Vergangene Turniere anzeigen", expanded=False):
                if not df_past.empty:
                    current_month_str = ""
                    for idx, item in df_past.iterrows():
                        start_date = item['Start_Date_Obj']
                        end_date = item['End_Date_Obj']
                        item_month_str = "Datum unbekannt" if pd.isnull(start_date) else f"{month_names[start_date.month]} {start_date.year}"
                        
                        if item_month_str != current_month_str:
                            current_month_str = item_month_str
                            st.write("")
                            st.markdown(f"#### 🕰️ {current_month_str}")
                        
                        with st.container(border=True):
                            col_logo, col_info, col_link = st.columns([1.5, 6, 2], vertical_alignment="top")
                            with col_logo:
                                logo_to_show = item['logo_url']
                                if not logo_to_show or "no-photo" in logo_to_show:
                                    logo_to_show = DEFAULT_LOGO
                                st.image(logo_to_show, width=140)
                                    
                            with col_info:
                                st.markdown(f"### {item['title']} *(Beendet)*")
                                render_styled_tournament_card(item, occupied_dates, vacation_dates, vacation_notes, today, is_past=True)
                                
                                if IS_ADMIN:
                                    render_admin_editor(item, data, is_past=True)
                            
                            with col_link:
                                st.write("")
                                st.write("")
                                st.link_button("Turnierseite", item['link'], use_container_width=True)
                else:
                    st.info("Keine vergangenen Turniere gefunden.")

        with tab_analyse:
            st.markdown('<div class="carousel-hint-text">⟵ Wischen zum Wechseln (Formkurve / Austragungsorte) ⟶</div>', unsafe_allow_html=True)
            col_chart_box, col_hotspot_box = st.columns(2)
            with col_chart_box:
                st.markdown('<div class="zeit-mobile-anchor"></div>', unsafe_allow_html=True)
                with st.container(border=True):
                    st.markdown('<div class="zeit-chart-container"></div>', unsafe_allow_html=True)
                    render_season_chart(df, today)
            with col_hotspot_box:
                st.markdown('<div class="zeit-mobile-anchor"></div>', unsafe_allow_html=True)
                with st.container(border=True):
                    st.markdown('<div class="zeit-hotspot-container"></div>', unsafe_allow_html=True)
                    render_city_hotspots(df, today)

    else:
        st.info("Die Datenbank ist erreichbar, enthält aber aktuell noch keine Turniere.")