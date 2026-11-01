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

UUID_PATTERN = re.compile(r'([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})')

PLAYER_CONFIG = {
    "first_name": "Marco",
    "last_name": "Mainz",
    "club": "FC Langenfeld",
    "member_id": "01-166428",
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
    'kreisliga', 'bezirksliga', 'landesliga', 'verbandsliga', 'nrw', 'export calendar', 'h2h'
}


def is_real_player_name(name):
    if not name or len(name) < 4:
        return False
    n_low = name.lower()
    if any(re.search(rf'\b{w}\b', n_low) for w in IGNORE_OPPONENT_WORDS):
        return False
    if any(p.search(name) for p in PLAYER_CONFIG["patterns"]):
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
    """
    Filtert echte Badminton-Satzstände heraus (mind. eine Zahl 20-30).
    Entfernt Hallennummern, Spieldauern (z.B. 40m) und Uhrzeiten.
    """
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


# --- DAS EXAKTE MATCH-ARCHIV (DEDUPLIZIERT & REIN ECHTE ERGEBNISSE) ---

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
                        opp_links = [a.get_text().strip() for a in opp_td.find_all('a') if 'player.aspx' in a.get('href', '').lower()]
                        opponents = [n for n in opp_links if is_real_player_name(n)]
                        
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
                        
                        for opp in opponents:
                            sig = (opp, disc, score_str)
                            if sig in seen_matches:
                                continue
                            seen_matches.add(sig)
                            
                            history.setdefault(opp, []).append({
                                "opponent": opp,
                                "competition": "Liga",
                                "discipline": disc,
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
                            
                            opp_links = [a.get_text().strip() for a in opp_row.find_all('a') if is_real_player_name(a.get_text().strip())]
                            score_str = clean_badminton_scores(txt, won)

                            # Geisterspiele ohne Sätze ignorieren!
                            if not score_str or len(score_str.split(':')) < 2:
                                continue

                            disc = "HD"
                            if any(k in txt.lower() for k in ['vanessa', 'joppien', 'thea', 'sommer', 'mixed', 'mx']):
                                disc = "MX"
                            elif len(my_row.find_all('a')) == 1:
                                disc = "HE"

                            # Kernsätze deduplizieren (z. B. '11:21, 17:21')
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
                                    "score": core_score,
                                    "won": won
                                })
        except Exception as e:
            print(f"Fehler bei Turnier-Erfassung: {e}")
            
    return history


# --- DYNAMISCHES EVENT-, GEGNER- & NIVEAU-SCRAPING ---

def check_player_subpages(session, t_id, existing_entry, opp_history=None):
    # Absicherung gegen NoneType!
    if not opp_history or not isinstance(opp_history, dict):
        opp_history = {}
        
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
                            p_links = [a.get_text().strip() for a in tr.find_all('a', href=re.compile(r'player', re.I))]
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

                    # 2. ECHTE GEGNER IM FELD ERFASSEN
                    all_field_players = []
                    seeds_count = 0
                    for tr in soup_ev.find_all('tr'):
                        t_txt = tr.get_text(separator=' | ')
                        if re.search(r'\[\d+\]|seed', t_txt, re.I):
                            seeds_count += 1
                        
                        p_links = [a.get_text().strip() for a in tr.find_all('a', href=re.compile(r'player', re.I))]
                        for pl in p_links:
                            if is_real_player_name(pl) and pl != updates.get("partner_hd") and pl != updates.get("partner_mx"):
                                if pl not in all_field_players:
                                    all_field_players.append(pl)

                    # H2H-Vergleich gegen echte Gegner
                    known_duels = []
                    total_wins = 0
                    total_losses = 0
                    
                    for opp in all_field_players:
                        if opp in opp_history:
                            matches_vs = opp_history[opp]
                            wins = sum(1 for m in matches_vs if m["won"])
                            losses = len(matches_vs) - wins
                            total_wins += wins
                            total_losses += losses
                            
                            scores_list = [m['score'] for m in matches_vs if m.get('score')]
                            last_disc = matches_vs[0]['discipline']
                            last_comp = matches_vs[0]['competition']
                            score_preview = "; ".join(scores_list[:2]) if scores_list else ""
                            detail_str = f"{score_preview} ({last_disc}, {last_comp})" if score_preview else f"{last_disc}, {last_comp}"
                            
                            known_duels.append({
                                "opponent": opp,
                                "wins": wins,
                                "losses": losses,
                                "detail": detail_str
                            })

                    # Matchup-Faktor
                    if not known_duels:
                        matchup_badge = "⚪ Unbekanntes Feld"
                        matchup_desc = "Noch keine bekannten Duelle gegen die gemeldeten Konkurrenten"
                    elif total_wins > total_losses:
                        matchup_badge = "🟢 Günstiges Feld"
                        matchup_desc = f"Positive Bilanz: {total_wins} Siege / {total_losses} Niederlagen ({len(known_duels)} bekannte Konkurrenten)"
                    elif total_wins == total_losses:
                        matchup_badge = "🟡 Ausgeglichenes Feld"
                        matchup_desc = f"Ausgeglichen: {total_wins} Siege / {total_losses} Niederlagen ({len(known_duels)} bekannte Konkurrenten)"
                    else:
                        matchup_badge = "🔴 Schweres Pflaster"
                        matchup_desc = f"Schwere Duelle: {total_wins} Siege / {total_losses} Niederlagen ({len(known_duels)} bekannte Konkurrenten)"

                    is_doubles = bool('hd' in event_name.lower() or 'mx' in event_name.lower())
                    teams_approx = max(len(all_field_players) // 2 if is_doubles else len(all_field_players), 1)
                    seed_info = f", {seeds_count} gesetzte Paarungen" if seeds_count > 0 else ""
                    field_level_str = f"Feld mit {teams_approx} gemeldeten {'Teams' if is_doubles else 'Spielern'}{seed_info}"

                    updates["field_analysis"] = {
                        "event_name": event_name,
                        "matchup_badge": matchup_badge,
                        "matchup_desc": matchup_desc,
                        "field_level": field_level_str,
                        "known_duels": known_duels,
                        "unknown_count": max(0, len(all_field_players) - len(known_duels))
                    }

                    # Nächstes / Letztes Spiel
                    for tr in soup_ev.find_all('tr'):
                        tr_txt = tr.get_text(separator=' ')
                        if any(p.search(tr_txt) for p in PLAYER_CONFIG["patterns"]):
                            p_links = [a.get_text().strip() for a in tr.find_all('a', href=re.compile(r'player', re.I))]
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
                        
            sub_updates = check_player_subpages(session, t_id, t, opp_history)
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

            sub_updates = check_player_subpages(session, t_id, old_t, opp_history)
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

    # Auch bereits in der DB gemeldete Turniere (wie Niederrhein Cup) mit frischem H2H versorgen
    for t_id, t_item in known_tournaments.items():
        if t_item.get('registered'):
            sub_up = check_player_subpages(session, t_id, t_item, opp_history)
            for k, val in sub_up.items():
                if val:
                    t_item[k] = val

    try:
        save_gist_file(DB_FILE, known_tournaments)
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