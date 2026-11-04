import os
import json
import re
import requests
from bs4 import BeautifulSoup
import urllib.parse
from gist_db import load_gist_file, save_gist_file
import datetime
from zoneinfo import ZoneInfo

NTFY_TOPIC = "my_badminton_tournaments_40764_v2" 
DB_FILE = "known_tournaments.json"
OPPONENTS_FILE = "opponent_history.json"
PLAYER_RECORDS_FILE = "player_records.json"

UUID_PATTERN = re.compile(r'([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})')

PLAYER_CONFIG = {
    "first_name": "Marco",
    "last_name": "Mainz",
    "club": "FC Langenfeld",
    "member_id": "01-166428",
    "org_code": "E3B0DC28-EDDE-426A-9DD9-600D26DCF680",
    "patterns": [
        re.compile(r'\bMarco\s+Mainz\b', re.IGNORECASE),
        re.compile(r'\bMainz[,\s]+Marco\b', re.IGNORECASE)
    ],
    "league_urls": [
        "https://dbv.turnier.de/sport/league/player?id=925D6245-1FA1-496D-9810-1439487E5801&player=18943",
        "https://dbv.turnier.de/sport/league/player?id=066F2F48-EF43-47A8-999F-A2021BE81D09&player=21844"
    ],
    "tournament_profile_urls": [
        "https://dbv.turnier.de/player-profile/68c830e9-afd8-4adb-bb6a-22a84a98a64b/tournaments",
        "https://dbv.turnier.de/player-profile/68c830e9-afd8-4adb-bb6a-22a84a98a64b/tournaments/2025"
    ]
}

IGNORE_OPPONENT_WORDS = {
    'gruppe', 'group', 'starterliste', 'status', 'auslosung', 'verein', 'verband',
    'club', 'team', 'punkte', 'setzplatz', 'seed', 'court', 'feld', 'runde',
    'hd', 'he', 'mx', 'dd', 'de', 'herrendoppel', 'herreneinzel', 'mixed',
    'damendoppel', 'dameneinzel', 'turnier', 'meisterschaft', 'liga', 'bezirksklasse',
    'kreisliga', 'bezirksliga', 'landesliga', 'verbandsliga', 'nrw', 'export calendar', 'h2h',
    'playoff', 'nachrückerliste'
}


def clean_player_name(raw_name):
    if not raw_name:
        return ""
    return re.sub(r'\[[A-Za-z]{2,4}\]\s*', '', raw_name).strip()


def is_real_player_name(name):
    c_name = clean_player_name(name)
    if not c_name or len(c_name) < 4:
        return False
    n_low = c_name.lower()
    if any(re.search(rf'\b{w}\b', n_low) for w in IGNORE_OPPONENT_WORDS):
        return False
    if any(p.search(c_name) for p in PLAYER_CONFIG["patterns"]):
        return False
    return True


def is_youth_tournament(title, tag_parts):
    u_pattern = re.compile(r'^u\d+$', re.IGNORECASE)
    for tag in tag_parts:
        if u_pattern.match(tag.strip()):
            return True
    if re.search(r'\b[uU]\d{1,2}\b', title):
        return True
    youth_keywords = ['junior', 'kids', 'küken', 'schüler', 'jugend', 'nachwuchs', 'mini-cup']
    if any(kw in title.lower() for kw in youth_keywords):
        return True
    return False


def get_headers():
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7"
    }


def init_session():
    session = requests.Session()
    headers = get_headers()
    try:
        post_data = {
            'ReturnUrl': '/',
            'SettingsOpen': 'false',
            'CookiePurposes': ['1', '2', '4', '16']
        }
        session.post('https://dbv.turnier.de/cookiewall/Save', data=post_data, headers=headers, timeout=8)
    except Exception as e:
        print(f"Hinweis Cookie-Wall Init: {e}")
    return session


def get_tournament_description(session, tournament_url):
    try:
        match = UUID_PATTERN.search(tournament_url)
        if match:
            tournament_url = f"https://dbv.turnier.de/tournament/{match.group(1).upper()}"
        
        r = session.get(tournament_url, headers=get_headers(), timeout=12)
        if r.status_code == 200:
            soup = BeautifulSoup(r.content, 'html.parser')
            alert_box = soup.find(class_=re.compile(r'alert--info|alert__body|alert'))
            if alert_box:
                return alert_box.get_text(separator="\n").strip()
            
            for selector in ['#main', '.media__body', '.content']:
                el = soup.select_one(selector)
                if el:
                    text = el.get_text(separator="\n").strip()
                    if len(text) > 50:
                        return text[:1200]
                        
            return soup.get_text(separator="\n").strip()[:500]
    except Exception as e:
        print(f"Fehler beim Laden der Beschreibung: {e}")
    return ""


def extract_field_name(text):
    t_up = text.upper()
    m_letter = re.search(r'\b([A-E])\b', t_up)
    if m_letter:
        return f"{m_letter.group(1)}-Feld"
    if "PREMIUM" in t_up:
        return "A-Feld"
    if "STANDARD" in t_up:
        return "B-Feld"
    if "BASIC" in t_up or "HOBBY" in t_up or "FUN" in t_up:
        return "C-Feld"
    m_age = re.search(r'\b(O\d{2})\b', t_up)
    if m_age:
        return m_age.group(1)
    return ""


def auto_detect_schedule_and_deadline(description_text):
    detected = {}
    if not description_text:
        return detected
        
    d_lower = description_text.lower()

    deadline_match = re.search(r'meldeschluss(?:\s*ist)?(?:\s*am)?[:\s]+(?:[a-zäöüß]+,?\s*)?(\d{1,2}\.\d{1,2}\.(?:\d{4})?)', d_lower)
    if deadline_match:
        detected["deadline"] = deadline_match.group(1)

    if re.search(r'(?:samstag|sa\.?)[^\n\.\;]*\b(?:herrendoppel|damendoppel|doppel|hd|dd)\b', d_lower):
        detected["day_hd"] = "Samstag"
    elif re.search(r'(?:sonntag|so\.?)[^\n\.\;]*\b(?:herrendoppel|damendoppel|doppel|hd|dd)\b', d_lower):
        detected["day_hd"] = "Sonntag"

    if re.search(r'(?:samstag|sa\.?)[^\n\.\;]*\b(?:mixed|gemischt|mx)\b', d_lower):
        detected["day_mx"] = "Samstag"
    elif re.search(r'(?:sonntag|so\.?)[^\n\.\;]*\b(?:mixed|gemischt|mx)\b', d_lower):
        detected["day_mx"] = "Sonntag"
    elif re.search(r'(?:freitag|fr\.?)[^\n\.\;]*\b(?:mixed|gemischt|mx)\b', d_lower):
        detected["day_mx"] = "Freitag"

    if re.search(r'(?:samstag|sa\.?)[^\n\.\;]*\b(?:herreneinzel|dameneinzel|einzel|he|de)\b', d_lower):
        detected["day_he"] = "Samstag"
    elif re.search(r'(?:sonntag|so\.?)[^\n\.\;]*\b(?:herreneinzel|dameneinzel|einzel|he|de)\b', d_lower):
        detected["day_he"] = "Sonntag"

    return detected


def clean_badminton_scores(text, won):
    raw_pairs = re.findall(r'\b(\d{1,2})\s*[-:\s]\s*(\d{1,2})\b', text)
    valid_sets = []
    for s1, s2 in raw_pairs:
        p1, p2 = int(s1), int(s2)
        if (20 <= p1 <= 30 or 20 <= p2 <= 30) and p1 != p2 and max(p1, p2) <= 30:
            if won:
                valid_sets.append(f"{max(p1, p2)}:{min(p1, p2)}")
            else:
                valid_sets.append(f"{min(p1, p2)}:{max(p1, p2)}")
    return ", ".join(valid_sets[:3])


# --- DIREKTER PROFIL-PFAD: BILANZ, VEREIN & LINKS AUSLESEN ---

def fetch_player_profile_details(session, player_name, tournament_id=None, tournament_player_id=None, cache=None):
    if cache is None:
        cache = {}
        
    c_name = clean_player_name(player_name)
    if c_name in cache and isinstance(cache[c_name], dict) and cache[c_name].get("record") not in ["0:0", "-", ""]:
        return cache[c_name]

    known_profiles = {
        "Michael Hansen": "https://dbv.turnier.de/player-profile/E3A6AB74-B6AB-4D7D-9F06-D0C75DCCA67C",
        "Marco Mainz": "https://dbv.turnier.de/player-profile/68c830e9-afd8-4adb-bb6a-22a84a98a64b"
    }

    profile_url = known_profiles.get(c_name)

    # 1. Klickpfad: Turnier-Spielerkarte -> Link /player/{OrgCode}/{Base64ID}
    if not profile_url and tournament_id and tournament_player_id:
        try:
            t_p_url = f"https://dbv.turnier.de/tournament/{tournament_id}/player/{tournament_player_id}"
            r_tp = session.get(t_p_url, headers=get_headers(), timeout=8)
            if r_tp.status_code == 200:
                soup_tp = BeautifulSoup(r_tp.content, 'html.parser')
                prof_a = soup_tp.find('a', href=re.compile(r'/player/[0-9a-fA-F-]+/[A-Za-z0-9_=+-]+', re.I))
                if prof_a:
                    profile_url = urllib.parse.urljoin("https://dbv.turnier.de", prof_a['href'])
        except Exception:
            pass

    # 2. Fallback: Suche per POST
    if not profile_url:
        try:
            search_url = "https://dbv.turnier.de/find/player/DoSearch"
            post_headers = {**get_headers(), 'X-Requested-With': 'XMLHttpRequest', 'Referer': 'https://dbv.turnier.de/find/player'}
            payload = {'Query': c_name, 'SportID': '2', 'Page': '1'}
            r_s = session.post(search_url, data=payload, headers=post_headers, timeout=8)
            if r_s.status_code == 200:
                soup_s = BeautifulSoup(r_s.content, 'html.parser')
                parts = [p.lower() for p in c_name.split() if len(p) >= 2]
                for a in soup_s.find_all('a', href=re.compile(r'/player-profile/[0-9a-fA-F-]+', re.I)):
                    txt = a.get_text().lower()
                    if all(p in txt for p in parts):
                        profile_url = urllib.parse.urljoin("https://dbv.turnier.de", a['href'])
                        break
        except Exception:
            pass

    record_str = "0:0"
    club_name = "-"
    club_url = ""
    member_id = ""
    detected_tier = ""

    if profile_url:
        try:
            r = session.get(profile_url, headers=get_headers(), timeout=8)
            if r.status_code == 200:
                # Echte finale Redirect-URL sichern
                profile_url = r.url

                # Mitgliedsnummer / Passnummer auslesen (z. B. 01-164149)
                m_mem = re.search(r'\((\d{2}-\d{4,8})\)', r.text)
                if m_mem:
                    member_id = m_mem.group(1)

                # Karriere-Bilanz abgreifen
                m = re.search(r'Karriere[^\d]*?(\d+)\s*/\s*(\d+)', r.text, re.I)
                if m:
                    record_str = f"{m.group(1)}:{m.group(2)}"

                soup_p = BeautifulSoup(r.content, 'html.parser')
                
                # Verein & Vereins-Link finden
                for a in soup_p.find_all('a', href=re.compile(r'/club/|/team/|club\.aspx|team\.aspx', re.I)):
                    c_txt = a.get_text().strip()
                    if len(c_txt) > 3 and not re.search(r'ausrichter|suche|find|deutschland|verband', c_txt, re.I):
                        club_name = re.sub(r'\s*\d+$', '', c_txt).strip()
                        club_url = urllib.parse.urljoin("https://dbv.turnier.de", a['href'])
                        break
                
                if club_name == "-":
                    for el in soup_p.find_all(class_=re.compile(r'media__title|media__sub', re.I)):
                        t = el.get_text().strip()
                        if len(t) > 3 and not re.search(r'ligen|karriere|verband|points', t, re.I):
                            club_name = re.sub(r'\s*\d+$', '', t).strip()
                            break

                # Liga-Level
                txt_low = r.text.lower()
                if "landesliga" in txt_low: detected_tier = "Landesliga"
                elif "bezirksliga" in txt_low: detected_tier = "Bezirksliga"
                elif "bezirksklasse" in txt_low: detected_tier = "Bezirksklasse"
                elif "kreisliga" in txt_low: detected_tier = "Kreisliga"
                elif "kreisklasse" in txt_low: detected_tier = "Kreisklasse"
        except Exception:
            pass

    details = {
        "record": record_str,
        "club": club_name if club_name else "-",
        "club_url": club_url,
        "profile_url": profile_url or "",
        "member_id": member_id,
        "league_tier": detected_tier
    }
    cache[c_name] = details
    return details


# --- MATCH-ARCHIV FÜR H2H ---

def harvest_opponent_history(session):
    history = {}
    seen_matches = set()
    headers = get_headers()
    
    # 1. Ligaspiele erfassen
    for l_url in PLAYER_CONFIG["league_urls"]:
        try:
            r = session.get(l_url, headers=headers, timeout=10)
            if r.status_code == 200:
                soup = BeautifulSoup(r.content, 'html.parser')
                for tr in soup.find_all('tr'):
                    tds = tr.find_all('td')
                    if len(tds) >= 7:
                        match_code = tds[1].get_text().strip().upper()
                        league_name = tds[2].get_text().strip()
                        t1_text = tds[3].get_text(separator=' ')
                        t2_text = tds[5].get_text(separator=' ')
                        score_text = tds[6].get_text().strip()
                        
                        in_t1 = any(p.search(t1_text) for p in PLAYER_CONFIG["patterns"])
                        in_t2 = any(p.search(t2_text) for p in PLAYER_CONFIG["patterns"])
                        if not in_t1 and not in_t2:
                            continue
                            
                        disc = "HD"
                        if any(k in match_code for k in ['HE', 'EINZEL']): disc = "HE"
                        elif any(k in match_code for k in ['GD', 'MX', 'MIXED']): disc = "MX"
                        
                        opp_td = tds[3] if in_t2 else tds[5]
                        opp_links = [clean_player_name(a.get_text().strip()) for a in opp_td.find_all('a') if 'player.aspx' in a.get('href', '').lower()]
                        opponents = [n for n in opp_links if is_real_player_name(n)]
                        
                        opp_team_name = ""
                        tm_link = opp_td.find('a', href=re.compile(r'team', re.I))
                        if tm_link:
                            opp_team_name = re.sub(r'\s*\d+$', '', tm_link.get_text().strip())

                        set_pairs = re.findall(r'(\d{1,2})\s*-\s*(\d{1,2})', score_text)
                        my_sets = 0
                        opp_sets = 0
                        formatted_sets = []
                        for s1, s2 in set_pairs:
                            pts_t1, pts_t2 = int(s1), int(s2)
                            my_pts = pts_t2 if in_t2 else pts_t1
                            opp_pts = pts_t1 if in_t2 else pts_t2
                            if my_pts > opp_pts: my_sets += 1
                            else: opp_sets += 1
                            formatted_sets.append(f"{my_pts}:{opp_pts}")
                            
                        won = (my_sets > opp_sets)
                        score_str = ", ".join(formatted_sets)
                        
                        l_tier = "Kreisklasse"
                        if "bezirksliga" in league_name.lower(): l_tier = "Bezirksliga"
                        elif "bezirksklasse" in league_name.lower(): l_tier = "Bezirksklasse"
                        elif "kreisliga" in league_name.lower(): l_tier = "Kreisliga"
                        elif "landesliga" in league_name.lower(): l_tier = "Landesliga"

                        for opp in opponents:
                            sig = (opp, disc, score_str)
                            if sig in seen_matches:
                                continue
                            seen_matches.add(sig)
                            
                            history.setdefault(opp, []).append({
                                "opponent": opp,
                                "competition": f"Liga ({l_tier})",
                                "discipline": disc,
                                "league_tier": l_tier,
                                "club": opp_team_name,
                                "score": score_str,
                                "won": won
                            })
        except Exception as e:
            print(f"Fehler bei Liga-Erfassung: {e}")

    # 2. Turnierspiele erfassen
    for t_url in PLAYER_CONFIG["tournament_profile_urls"]:
        try:
            r = session.get(t_url, headers=headers, timeout=10)
            if r.status_code == 200:
                soup = BeautifulSoup(r.content, 'html.parser')
                for match_box in soup.find_all(class_=re.compile(r'\bmatch\b')):
                    txt = match_box.get_text(separator=' ')
                    if any(p.search(txt) for p in PLAYER_CONFIG["patterns"]):
                        rows = [el for el in match_box.find_all('div') if el.get('class') and 'match__row' in el.get('class') and 'match__row-wrapper' not in el.get('class') and 'match__row-title' not in el.get('class')]
                        if len(rows) >= 2:
                            r0_txt = rows[0].get_text(separator=' ')
                            marco_in_r0 = any(p.search(r0_txt) for p in PLAYER_CONFIG["patterns"])
                            my_row = rows[0] if marco_in_r0 else rows[1]
                            opp_row = rows[1] if marco_in_r0 else rows[0]
                            
                            my_row_txt = ' ' + my_row.get_text(separator=' ') + ' '
                            won = bool(' W ' in my_row_txt or 'match__row--winner' in (my_row.get('class') or []))
                            if ' L ' in my_row_txt:
                                won = False
                            
                            opp_links = [clean_player_name(a.get_text().strip()) for a in opp_row.find_all('a') if is_real_player_name(a.get_text().strip())]
                            score_str = clean_badminton_scores(txt, won)

                            if not score_str or len(score_str.split(':')) < 2:
                                continue

                            disc = "HD"
                            if any(k in txt.lower() for k in ['vanessa', 'joppien', 'thea', 'sommer', 'mixed', 'mx']):
                                disc = "MX"
                            elif len(my_row.find_all('a')) == 1:
                                disc = "HE"

                            core_score = ", ".join(score_str.split(', ')[:2])

                            for opp in opp_links:
                                sig = (opp, disc, core_score)
                                if sig in seen_matches:
                                    continue
                                seen_matches.add(sig)
                                
                                history.setdefault(opp, []).append({
                                    "opponent": opp,
                                    "competition": "Turnier",
                                    "discipline": disc,
                                    "league_tier": "",
                                    "club": "",
                                    "score": core_score,
                                    "won": won
                                })
        except Exception as e:
            print(f"Fehler bei Turnier-Erfassung: {e}")
            
    return history


# --- EINSTUFUNGS-LOGIK PRO EINZELNEM SPIELER ---

def evaluate_single_player(details, h2h_matches):
    # 1. H2H PRIORITÄT (Höchste Gewichtung)
    if len(h2h_matches) > 0:
        h2h_wins = sum(1 for m in h2h_matches if m["won"])
        h2h_losses = len(h2h_matches) - h2h_wins
        if h2h_wins > h2h_losses and h2h_losses == 0:
            return "🟢 Pflichtsieg", 20
        elif h2h_wins > h2h_losses:
            return "🟢 Pflichtsieg", 25
        elif h2h_wins >= 1:
            return "🟡 Schlagbar", 45
        elif h2h_losses > 0:
            return "🔴 Wird schwer", 75

    # 2. KEIN H2H VORHANDEN
    rec_str = details.get("record", "0:0")
    tier = details.get("league_tier", "")

    if rec_str in ["0:0", "-", ""]:
        return "⚪ Unbekannt", 10

    w_val, l_val = 0, 0
    if ":" in rec_str:
        try:
            parts = rec_str.split(":")
            w_val, l_val = int(parts[0]), int(parts[1])
        except ValueError:
            pass

    total_games = w_val + l_val

    if tier in ["Bezirksklasse", "Bezirksliga", "Landesliga", "Verbandsliga"]:
        return "🔴 Wird schwer", 70

    if total_games >= 30:
        win_ratio = w_val / total_games if total_games > 0 else 0
        if win_ratio > 0.55:
            return "🔴 Wird schwer", 65
        elif w_val < l_val:
            if w_val >= 100 and l_val <= (w_val * 2):
                return "🟡 Schlagbar", 50
            else:
                return "🟢 Pflichtsieg", 25
    else:
        if w_val > l_val and w_val >= 15:
            return "🟡 Schlagbar", 45
        else:
            return "🟢 Pflichtsieg", 25

    return "🟡 Schlagbar", 45


# --- DYNAMISCHES EVENT-, GEGNER- & NIVEAU-SCRAPING ---

def check_player_subpages(session, t_id, existing_entry, opp_history=None, player_records=None):
    if not opp_history or not isinstance(opp_history, dict):
        opp_history = {}
    if player_records is None:
        player_records = {}
        
    updates = {}
    headers = get_headers()
    
    events_url = f"https://dbv.turnier.de/sport/events.aspx?id={t_id}"
    try:
        r_events = session.get(events_url, headers=headers, timeout=10)
        if r_events.status_code == 200 and 'cookiewall' not in r_events.url:
            soup_all = BeautifulSoup(r_events.content, 'html.parser')
            event_links = soup_all.find_all('a', href=lambda h: h and 'event.aspx' in h)
            
            for a_el in event_links:
                event_name = a_el.get_text().strip()
                if event_name.startswith(('DD', 'DE', 'Damendoppel', 'Dameneinzel')):
                    continue
                
                ev_href = a_el.get('href')
                full_ev_url = urllib.parse.urljoin("https://dbv.turnier.de/sport/", ev_href)
                
                r_ev = session.get(full_ev_url, headers=headers, timeout=8)
                if r_ev.status_code == 200 and any(p.search(r_ev.text) for p in PLAYER_CONFIG["patterns"]):
                    updates["registered"] = True
                    field_name = extract_field_name(event_name)
                    soup_ev = BeautifulSoup(r_ev.content, 'html.parser')
                    
                    # 1. Marco & Partner erkennen
                    for tr in soup_ev.find_all('tr'):
                        tr_txt = tr.get_text(separator=' | ')
                        if any(p.search(tr_txt) for p in PLAYER_CONFIG["patterns"]):
                            p_links = [clean_player_name(a.get_text().strip()) for a in tr.find_all('a', href=re.compile(r'player', re.I))]
                            partner_cands = [n for n in p_links if is_real_player_name(n)]
                            found_partner = partner_cands[0] if partner_cands else ""
                            
                            if re.search(r'\b(HD|Herrendoppel|MD)\b', event_name, re.I):
                                updates["reg_hd"] = True
                                if field_name: updates["field_hd"] = field_name
                                if found_partner: updates["partner_hd"] = found_partner
                                
                            elif re.search(r'\b(HE|Herreneinzel|MS)\b', event_name, re.I):
                                updates["reg_he"] = True
                                if field_name: updates["field_he"] = field_name
                                
                            elif re.search(r'\b(MX|Mixed|XD)\b', event_name, re.I):
                                updates["reg_mx"] = True
                                if field_name: updates["field_mx"] = field_name
                                if found_partner: updates["partner_mx"] = found_partner

                    # 2. AUSSCHLIESSLICH ECHTE STARTERLISTE AUSLESEN
                    tables = soup_ev.find_all('table')
                    target_table = None
                    for tbl in tables:
                        h_txt = tbl.get_text().lower()
                        if 'spieler' in h_txt:
                            target_table = tbl
                            break
                    if not target_table and len(tables) >= 2:
                        target_table = tables[1]
                    elif not target_table and tables:
                        target_table = tables[0]

                    raw_teams = []
                    seen_team_keys = set()
                    seeds_count = 0

                    if target_table:
                        for tr in target_table.find_all('tr'):
                            tds = tr.find_all('td')
                            if len(tds) >= 2:
                                status_txt = tds[0].get_text().strip().lower()
                                
                                if 'starterliste' not in status_txt:
                                    continue
                                
                                p_tags = tds[1].find_all('a', href=re.compile(r'player', re.I))
                                team_players_raw = []
                                for a in p_tags:
                                    p_name = clean_player_name(a.get_text().strip())
                                    m_pid = re.search(r'player=(\d+)', a.get('href', ''))
                                    pid = m_pid.group(1) if m_pid else None
                                    if p_name and (is_real_player_name(p_name) or any(p.search(p_name) for p in PLAYER_CONFIG["patterns"])):
                                        team_players_raw.append({"name": p_name, "pid": pid})
                                
                                if not team_players_raw:
                                    continue
                                    
                                player_names = [p["name"] for p in team_players_raw]
                                team_key = tuple(sorted(player_names))
                                if team_key in seen_team_keys:
                                    continue
                                seen_team_keys.add(team_key)
                                
                                is_my_team = any(any(p.search(pl) for p in PLAYER_CONFIG["patterns"]) for pl in player_names)
                                
                                seed_str = ""
                                if len(tds) >= 3:
                                    seed_raw = tds[2].get_text().strip()
                                    seed_str = re.sub(r'\[|\]', '', seed_raw).strip()
                                if seed_str:
                                    seeds_count += 1

                                team_opponents = [p for p in team_players_raw if not any(pat.search(p["name"]) for pat in PLAYER_CONFIG["patterns"]) and p["name"] != updates.get("partner_hd") and p["name"] != updates.get("partner_mx")]
                                
                                if not is_my_team and team_opponents:
                                    raw_teams.append({
                                        "opponents": team_opponents,
                                        "seed": seed_str
                                    })

                    # 3. DETAILS, PROFILE & H2H PRO SPIELER ERMITTELN
                    scored_teams = []
                    overall_h2h_wins = 0
                    overall_h2h_losses = 0
                    known_duels_summary = []

                    for t_item in raw_teams:
                        players_info = []
                        team_evals = []
                        max_player_score = 0
                        team_has_loss = False
                        team_has_win = False

                        for p_obj in t_item["opponents"]:
                            p_name = p_obj["name"]
                            p_pid = p_obj["pid"]
                            
                            p_details = fetch_player_profile_details(
                                session, 
                                p_name, 
                                tournament_id=t_id, 
                                tournament_player_id=p_pid, 
                                cache=player_records
                            )
                            
                            # Individuelle H2H-Bilanz dieses Spielers gegen Marco
                            p_h2h = opp_history.get(p_name, [])
                            p_w = sum(1 for m in p_h2h if m["won"])
                            p_l = len(p_h2h) - p_w
                            overall_h2h_wins += p_w
                            overall_h2h_losses += p_l
                            
                            if p_l > 0: team_has_loss = True
                            if p_w > 0: team_has_win = True

                            # Saubere H2H-Zahl (ohne Satzklammern!)
                            p_h2h_str = f"{p_w}-{p_l}" if len(p_h2h) > 0 else "-"

                            # Direkter H2H-Vergleichslink
                            h2h_link = ""
                            opp_mid = p_details.get("member_id", "")
                            if opp_mid and PLAYER_CONFIG.get("member_id"):
                                h2h_link = f"https://dbv.turnier.de/head-2-head?OrganizationCode={PLAYER_CONFIG['org_code']}&T1P1MemberID={opp_mid}&T2P1MemberID={PLAYER_CONFIG['member_id']}"

                            badge, p_score = evaluate_single_player(p_details, p_h2h)
                            team_evals.append((badge, p_score))
                            if p_score > max_player_score:
                                max_player_score = p_score

                            club_found = p_details.get("club", "-")
                            if club_found in ["-", ""]:
                                for m in p_h2h:
                                    if m.get("club"):
                                        club_found = m["club"]
                                        break

                            players_info.append({
                                "name": p_name,
                                "profile_url": p_details.get("profile_url", ""),
                                "club": club_found,
                                "club_url": p_details.get("club_url", ""),
                                "record": p_details.get("record", "0:0"),
                                "h2h_str": p_h2h_str,
                                "h2h_link": h2h_link
                            })

                        # Setzplatz-Bonus
                        team_final_score = max_player_score
                        if t_item["seed"] == "1": team_final_score += 35
                        elif t_item["seed"] == "2": team_final_score += 25
                        elif t_item["seed"] in ["3", "4", "3/4"]: team_final_score += 18

                        # Karriere-Siege als Tiebreaker
                        for p in players_info:
                            rec = p.get("record", "0:0")
                            if ":" in rec:
                                try:
                                    w_cnt = int(rec.split(":")[0])
                                    team_final_score += min(35, w_cnt // 8)
                                except ValueError:
                                    pass

                        # KONSERVATIVE KOMBINATION FÜR DAS TEAM
                        badges_in_team = [e[0] for e in team_evals]
                        
                        if team_has_loss and not team_has_win:
                            team_badge = "🔴 Wird schwer"
                        elif team_has_win and not team_has_loss:
                            team_badge = "🟢 Pflichtsieg"
                        elif team_has_win and team_has_loss:
                            team_badge = "🟡 Schlagbar"
                        elif "🔴 Wird schwer" in badges_in_team:
                            team_badge = "🔴 Wird schwer"
                        elif "🟡 Schlagbar" in badges_in_team:
                            team_badge = "🟡 Schlagbar"
                        elif "🟢 Pflichtsieg" in badges_in_team:
                            team_badge = "🟢 Pflichtsieg"
                        else:
                            team_badge = "⚪ Unbekannt"

                        scored_teams.append({
                            "players_info": players_info,
                            "seed": t_item["seed"],
                            "threat_score": team_final_score,
                            "danger_badge": team_badge
                        })

                    # Sortierung: Höchster Score an die Spitze
                    def get_team_sorting_weight(team_item):
                        score = team_item.get("threat_score", 0)
                        career_wins = 0
                        for p in team_item.get("players_info", []):
                            rec = p.get("record", "0:0")
                            if ":" in rec:
                                try:
                                    career_wins += int(rec.split(":")[0])
                                except ValueError:
                                    pass
                        return (score + career_wins, career_wins)

                    scored_teams.sort(key=get_team_sorting_weight, reverse=True)

                    # GENAU 1 TOP-FAVORIT!
                    if scored_teams and (scored_teams[0]["threat_score"] >= 45 or scored_teams[0]["seed"] in ["1", "2"]):
                        scored_teams[0]["danger_badge"] = "👑 Top-Favorit"

                    top_fav_name = " / ".join([p["name"] for p in scored_teams[0]["players_info"]]) if scored_teams and "👑" in scored_teams[0]["danger_badge"] else "Ausgeglichen"
                    teams_total = len(scored_teams) + (1 if updates.get("registered") else 0)

                    # Zusammenfassung
                    h2h_known_count = sum(1 for t in scored_teams if any(p["h2h_str"] != "-" for p in t["players_info"]))
                    if h2h_known_count == 0:
                        matchup_badge = "⚪ Unbekanntes Feld"
                        matchup_desc = "Noch keine bisherigen Duelle"
                    elif overall_h2h_wins > overall_h2h_losses:
                        matchup_badge = "🟢 Günstig"
                        matchup_desc = f"{overall_h2h_wins} Siege / {overall_h2h_losses} Niederlagen"
                    elif overall_h2h_wins == overall_h2h_losses:
                        matchup_badge = "🟡 Ausgeglichen"
                        matchup_desc = f"{overall_h2h_wins} Siege / {overall_h2h_losses} Niederlagen"
                    else:
                        matchup_badge = "🔴 Schwer"
                        matchup_desc = f"{overall_h2h_wins} Siege / {overall_h2h_losses} Niederlagen"

                    updates["field_analysis"] = {
                        "event_name": event_name,
                        "teams_count": teams_total,
                        "seeds_count": seeds_count,
                        "top_favorite": top_fav_name,
                        "h2h_known_count": h2h_known_count,
                        "matchup_badge": matchup_badge,
                        "matchup_desc": matchup_desc,
                        "teams": scored_teams
                    }

                    # Nächstes / Letztes Spiel
                    for tr in soup_ev.find_all('tr'):
                        tr_txt = tr.get_text(separator=' ')
                        if any(p.search(tr_txt) for p in PLAYER_CONFIG["patterns"]):
                            p_links = [clean_player_name(a.get_text().strip()) for a in tr.find_all('a', href=re.compile(r'player', re.I))]
                            cur_partner = updates.get("partner_hd") or updates.get("partner_mx") or existing_entry.get("partner_hd", "")
                            opponents = [n for n in p_links if is_real_player_name(n) and n != cur_partner]
                            
                            score_m = re.search(r'\b\d{1,2}-\d{1,2}\b(?:\s+\d{1,2}-\d{1,2})*', tr_txt)
                            time_m = re.search(r'\b(?:Mo|Di|Mi|Do|Fr|Sa|So)?\s*\d{1,2}\.\d{1,2}\.?\s+\d{1,2}:\d{2}\b', tr_txt)
                            court_m = re.search(r'Court\s*\d+|Feld\s*\d+', tr_txt, re.I)
                            
                            opp_str = " / ".join(opponents[:2]) if opponents else "Noch offen"
                            score_str = score_m.group(0) if score_m else ""
                            time_str = time_m.group(0) if time_m else ""
                            court_str = court_m.group(0) if court_m else ""
                            
                            if score_str:
                                updates["last_match_result"] = f"{score_str} vs. {opp_str}"
                            elif opp_str != "Noch offen":
                                t_info = f" ({time_str}" if time_str else ""
                                c_info = f", {court_str})" if (court_str and t_info) else (f" ({court_str})" if court_str else ")")
                                suffix = f"{t_info}{c_info}" if (t_info or c_info != ")") else ""
                                updates["next_opponent"] = f"vs. {opp_str}{suffix}"
                                
    except Exception as e:
        print(f"Fehler bei Konkurrenz-Prüfung ({t_id}): {e}")

    # Treppchenplätze / Winners
    winners_url = f"https://dbv.turnier.de/sport/winners.aspx?id={t_id}"
    try:
        r_win = session.get(winners_url, headers=headers, timeout=8)
        if r_win.status_code == 200 and any(p.search(r_win.text) for p in PLAYER_CONFIG["patterns"]):
            soup_win = BeautifulSoup(r_win.content, 'html.parser')
            for table in soup_win.find_all('table'):
                t_text = table.get_text()
                if any(p.search(t_text) for p in PLAYER_CONFIG["patterns"]):
                    disc_key = "hd"
                    if re.search(r'\b(Einzel|HE|MS)\b', t_text, re.I): disc_key = "he"
                    elif re.search(r'\b(Mixed|MX|XD)\b', t_text, re.I): disc_key = "mx"

                    for row in table.find_all('tr'):
                        row_t = row.get_text()
                        if any(p.search(row_t) for p in PLAYER_CONFIG["patterns"]):
                            if re.search(r'\b1\b|Winner|Sieger', row_t, re.I): updates[f"placement_{disc_key}"] = "🥇 1. Platz"
                            elif re.search(r'\b2\b|Runner|Zweiter', row_t, re.I): updates[f"placement_{disc_key}"] = "🥈 2. Platz"
                            elif re.search(r'\b3\b|3/4|Semi|Dritter', row_t, re.I): updates[f"placement_{disc_key}"] = "🥉 3. Platz"
    except Exception as e:
        print(f"Fehler bei Winners-Prüfung ({t_id}): {e}")

    return updates


# --- HAUPT-SCRAPER ---

def scrape_tournaments(s):
    url = "https://dbv.turnier.de/find/tournament/DoSearch"
    headers = {
        **get_headers(),
        "Referer": "https://dbv.turnier.de/find",
        "X-Requested-With": "XMLHttpRequest"
    }

    tournaments = []
    seen_ids = set()
    page = 1
    max_pages = 25

    today = datetime.date.today()
    start_filter = f"{today.year}-01-01T00:00"
    end_filter = f"{today.year + 1}-12-31T23:59"

    while page <= max_pages:
        print(f"Scraping Seite {page} ({today.year} - {today.year + 1})...")
        payload = {
            "Page": str(page),
            "TournamentExtendedFilter.SportID": "2",
            "TournamentFilter.Q": "",
            "TournamentFilter.DateFilterType": "0",
            "TournamentFilter.StartDate": start_filter,
            "TournamentFilter.EndDate": end_filter,
            "TournamentFilter.PostalCode": "40764",
            "TournamentFilter.Distance": "100"
        }

        try:
            response = s.post(url, data=payload, headers=headers, timeout=15)
            response.raise_for_status()
        except Exception as e:
            print(f"Fehler beim Laden von Seite {page}: {e}")
            break

        soup = BeautifulSoup(response.content, 'html.parser')
        page_tournaments_count = 0

        for link in soup.find_all('a', href=True):
            href = link['href']
            match = UUID_PATTERN.search(href)
            if not match or not ('/tournament' in href or '/sport/' in href):
                continue

            title = link.text.strip()
            if not title:
                continue

            t_id = match.group(1).upper()
            if t_id in seen_ids:
                continue

            full_link = f"https://dbv.turnier.de/tournament/{t_id}"
            container = link.find_parent(['li', 'tr']) or link.find_parent('div')

            tag_parts = []
            city = "Unbekannt"
            distance = None
            organizer = "Unbekannt"
            start_date = None
            end_date = None
            logo_url = ""

            if container:
                raw_text = container.get_text(separator=' | ').strip()
                cleaned_parts = [p.strip() for p in raw_text.split('|') if p.strip() and p.strip() != title]

                img_el = container.find('img')
                if img_el and img_el.get('src'):
                    logo_url = urllib.parse.urljoin("https://dbv.turnier.de", img_el['src'])

                dates = re.findall(r'\b\d{2}\.\d{2}\.\d{4}\b', raw_text)
                if len(dates) >= 2:
                    start_date = dates[0]
                    end_date = dates[1]
                elif len(dates) == 1:
                    start_date = dates[0]
                    end_date = dates[0]

                for part in cleaned_parts:
                    if 'km' in part.lower():
                        dist_match = re.search(r'(\d+)\s*km', part.lower())
                        if dist_match:
                            distance = int(dist_match.group(1))
                        
                        cleaned = re.sub(r'\(.*?\)|\[.*?\]|\d+\s*km', '', part, flags=re.IGNORECASE)
                        clean_city = cleaned.strip(' -|,\t\n')
                        if clean_city:
                            city = clean_city
                        break

                non_meta_parts = [p for p in cleaned_parts if not re.search(r'\b\d{2}\.\d{2}\.\d{4}\b', p) and 'km' not in p.lower()]
                if non_meta_parts:
                    organizer = non_meta_parts[0]

                for part in cleaned_parts:
                    if not re.search(r'\b\d{2}\.\d{2}\.\d{4}\b', part):
                        if len(part) < 15 or part.lower().startswith(('u', 'o')) or part == 'Open':
                            tag_parts.append(part)

                tags = ", ".join(tag_parts) if tag_parts else ""
            else:
                tags = ""

            if is_youth_tournament(title, tag_parts):
                continue

            seen_ids.add(t_id)
            tournaments.append({
                "id": t_id,
                "title": title,
                "link": full_link,
                "logo_url": logo_url,
                "organizer": organizer,
                "city": city,
                "distance": distance,
                "start_date": start_date,
                "end_date": end_date,
                "tags": tags,
                "registered": False,
                "reg_he": False,
                "reg_hd": False,
                "reg_mx": False,
                "full_he": False,
                "full_hd": False,
                "full_mx": False,
                "partner_hd": "",
                "partner_mx": "",
                "day_he": "",
                "day_hd": "",
                "day_mx": "",
                "notes": "",
                "placement_he": "",
                "field_he": "",
                "placement_hd": "",
                "field_hd": "",
                "placement_mx": "",
                "field_mx": "",
                "description": "",
                "deadline": "",
                "next_opponent": "",
                "last_match_result": "",
                "field_analysis": {}
            })
            page_tournaments_count += 1

        if page_tournaments_count == 0:
            break
            
        has_more = response.headers.get('HasMoreResults')
        if has_more and has_more.lower() == 'false':
            break

        page += 1

    print(f"Scraped {len(tournaments)} Turniere über {page} Seiten hinweg.")
    return tournaments


def send_push_notification(new_items):
    if not new_items:
        return

    count = len(new_items)
    summary_lines = [f"- {item['title']} in {item['city']} ({item['start_date']})" for item in new_items[:5]]
        
    if count > 5:
        summary_lines.append(f"... sowie {count - 5} weitere neue Turniere.")
        
    summary_lines.append("\nDashboard öffnen: https://turniere.streamlit.app")
    message = "\n".join(summary_lines)
    
    try:
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode('utf-8'),
            headers={
                "Title": f"{count} neue(s) Badminton-Turnier(e) gefunden!",
                "Priority": "high",
                "Tags": "badminton,sports,tada"
            },
            timeout=10
        )
    except Exception as e:
        print(f"Fehler beim Senden der Push-Nachricht: {e}")


def check_for_updates():
    for _ in check_for_updates_generator():
        pass


def check_for_updates_generator():
    yield "Verbinde mit zentraler Cloud-Datenbank (GitHub Gist)..."
    
    try:
        known_tournaments = load_gist_file(DB_FILE)
        if not isinstance(known_tournaments, dict):
            known_tournaments = {}
        yield f"✅ Datenbank geladen ({len(known_tournaments)} bekannte Turniere)."
    except Exception as e:
        yield f"🚨 KRITISCHER DATENBANKFEHLER: {e}"
        return

    session = init_session()
    
    yield "Lade persönliche Match-Historie (Liga & Turniere) für Marco Mainz..."
    try:
        opp_history = harvest_opponent_history(session)
        save_gist_file(OPPONENTS_FILE, opp_history)
        with open(OPPONENTS_FILE, 'w') as f:
            json.dump(opp_history, f, indent=2, ensure_ascii=False)
        yield f"🎯 Match-Archiv aktiv: {len(opp_history)} verschiedene Konkurrenten erfasst!"
    except Exception as e:
        yield f"Hinweis Match-Archiv: {e}. Nutze bestehende Daten."
        try:
            opp_history = load_gist_file(OPPONENTS_FILE) or {}
        except Exception:
            opp_history = {}

    try:
        player_records = load_gist_file(PLAYER_RECORDS_FILE) or {}
    except Exception:
        player_records = {}

    today = datetime.date.today()
    yield f"Suche nach Turnieren für {today.year} & {today.year + 1} auf turnier.de..."
    
    try:
        current_list = scrape_tournaments(session)
        yield f"Gefunden: {len(current_list)} Turniere im 100km-Umkreis um Langenfeld."
    except Exception as e:
        yield f"Fehler beim Scraping: {e}"
        return

    new_tournaments = []
    found_registrations = 0
    
    yield f"Gleiche Konkurrenzen, Zeitpläne & H2H-Gegner für Marco Mainz ab..."
    
    for idx, t in enumerate(current_list):
        t_id = t["id"]
        
        if t_id not in known_tournaments:
            t["description"] = get_tournament_description(session, t["link"])
            
            if t["description"]:
                sch = auto_detect_schedule_and_deadline(t["description"])
                for k in ["day_he", "day_hd", "day_mx", "deadline"]:
                    if sch.get(k) and not t.get(k):
                        t[k] = sch[k]
                        
            sub_updates = check_player_subpages(session, t_id, t, opp_history, player_records)
            t.update(sub_updates)
            
            if sub_updates.get("registered"):
                found_registrations += 1
                disc_info = []
                if sub_updates.get("reg_hd"): disc_info.append(f"HD ({sub_updates.get('field_hd', '')})")
                if sub_updates.get("reg_he"): disc_info.append(f"HE ({sub_updates.get('field_he', '')})")
                if sub_updates.get("reg_mx"): disc_info.append(f"MX ({sub_updates.get('field_mx', '')})")
                yield f"🎯 Treffer bei '{t['title']}': Gemeldet für {', '.join(disc_info)}!"
            
            new_tournaments.append(t)
            known_tournaments[t_id] = t
        else:
            old_t = known_tournaments[t_id]
            desc = old_t.get('description', '') or get_tournament_description(session, t["link"])

            old_t.update({
                "title": t["title"],
                "link": t["link"],
                "logo_url": t["logo_url"] or old_t.get("logo_url", ""),
                "organizer": t["organizer"],
                "city": t["city"],
                "distance": t["distance"],
                "start_date": t["start_date"],
                "end_date": t["end_date"],
                "tags": t["tags"],
                "description": desc
            })
            
            if desc:
                sch = auto_detect_schedule_and_deadline(desc)
                for k in ["day_he", "day_hd", "day_mx", "deadline"]:
                    if sch.get(k) and not old_t.get(k):
                        old_t[k] = sch[k]

            sub_updates = check_player_subpages(session, t_id, old_t, opp_history, player_records)
            if sub_updates.get("registered") and not old_t.get("registered"):
                found_registrations += 1
                disc_info = []
                if sub_updates.get("reg_hd"): disc_info.append(f"HD ({sub_updates.get('field_hd', '')})")
                if sub_updates.get("reg_he"): disc_info.append(f"HE ({sub_updates.get('field_he', '')})")
                if sub_updates.get("reg_mx"): disc_info.append(f"MX ({sub_updates.get('field_mx', '')})")
                yield f"🎯 Treffer bei '{t['title']}': Gemeldet für {', '.join(disc_info)}!"

            for k, val in sub_updates.items():
                if val:
                    old_t[k] = val
                    
            known_tournaments[t_id] = old_t

    for t_id, t_item in known_tournaments.items():
        if t_item.get('registered'):
            sub_up = check_player_subpages(session, t_id, t_item, opp_history, player_records)
            for k, val in sub_up.items():
                if val:
                    t_item[k] = val

    try:
        save_gist_file(DB_FILE, known_tournaments)
        save_gist_file(PLAYER_RECORDS_FILE, player_records)
        now_str = datetime.datetime.now(ZoneInfo("Europe/Berlin")).strftime("%d.%m.%Y um %H:%M Uhr")
        save_gist_file("last_update.json", {"timestamp": now_str})
        yield "💾 Änderungen erfolgreich in GitHub Gist gespeichert."
    except Exception as e:
        yield f"🚨 FEHLER BEIM SPEICHERN IM GIST: {e}"
        return

    if new_tournaments:
        yield f"Fertig! {len(new_tournaments)} neue(s) Turnier(e) gefunden."
        send_push_notification(new_tournaments)
    else:
        yield f"Fertig! Alle Meldungen, Zeitpläne & H2H-Duelle synchronisiert."


if __name__ == "__main__":
    check_for_updates()