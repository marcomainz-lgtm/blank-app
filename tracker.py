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

UUID_PATTERN = re.compile(r'([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})')

PLAYER_CONFIG = {
    "first_name": "Marco",
    "last_name": "Mainz",
    "club": "FC Langenfeld",
    "patterns": [
        re.compile(r'\bMarco\s+Mainz\b', re.IGNORECASE),
        re.compile(r'\bMainz[,\s]+Marco\b', re.IGNORECASE)
    ]
}


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
    """Initialisiert Session und überwindet die Cookie-Wall von turnier.de offiziell."""
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
        print(f"Fehler beim Laden der Beschreibung für {tournament_url}: {e}")
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
    """
    Liest Spieltage (Samstag/Sonntag) und den Meldeschluss
    automatisch aus dem Ausschreibungstext aus.
    """
    detected = {}
    if not description_text:
        return detected
        
    d_lower = description_text.lower()

    deadline_match = re.search(r'meldeschluss(?:\s*ist)?(?:\s*am)?[:\s]+(?:[a-zäöüß]+,?\s*)?(\d{1,2}\.\d{1,2}\.(?:\d{4})?)', d_lower)
    if deadline_match:
        detected["deadline"] = deadline_match.group(1)

    # Doppel (HD / DD)
    if re.search(r'(?:samstag|sa\.?)[^\n\.\;]*\b(?:herrendoppel|damendoppel|doppel|hd|dd)\b', d_lower):
        detected["day_hd"] = "Samstag"
    elif re.search(r'(?:sonntag|so\.?)[^\n\.\;]*\b(?:herrendoppel|damendoppel|doppel|hd|dd)\b', d_lower):
        detected["day_hd"] = "Sonntag"

    # Mixed (MX)
    if re.search(r'(?:samstag|sa\.?)[^\n\.\;]*\b(?:mixed|gemischt|mx)\b', d_lower):
        detected["day_mx"] = "Samstag"
    elif re.search(r'(?:sonntag|so\.?)[^\n\.\;]*\b(?:mixed|gemischt|mx)\b', d_lower):
        detected["day_mx"] = "Sonntag"
    elif re.search(r'(?:freitag|fr\.?)[^\n\.\;]*\b(?:mixed|gemischt|mx)\b', d_lower):
        detected["day_mx"] = "Freitag"

    # Einzel (HE / DE)
    if re.search(r'(?:samstag|sa\.?)[^\n\.\;]*\b(?:herreneinzel|dameneinzel|einzel|he|de)\b', d_lower):
        detected["day_he"] = "Samstag"
    elif re.search(r'(?:sonntag|so\.?)[^\n\.\;]*\b(?:herreneinzel|dameneinzel|einzel|he|de)\b', d_lower):
        detected["day_he"] = "Sonntag"

    return detected


# --- DYNAMISCHES EVENT- & GEGNER-SCRAPING ---

def check_player_subpages(session, t_id, existing_entry):
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
                    
                    for tr in soup_ev.find_all('tr'):
                        tr_txt = tr.get_text(separator=' | ')
                        if any(p.search(tr_txt) for p in PLAYER_CONFIG["patterns"]):
                            cell_names = [a.get_text().strip() for a in tr.find_all('a') if a.get_text().strip()]
                            if not cell_names:
                                parts = [c.strip() for c in tr_txt.split('|') if c.strip()]
                                ignore_w = {'starterliste', 'status', 'auslosung', 'verein', 'verband', 'club', '1', '2', '3', '4', '5'}
                                cell_names = [p for p in parts if p.lower() not in ignore_w and len(p) > 3]

                            partner_cands = [name for name in cell_names if not any(p.search(name) for p in PLAYER_CONFIG["patterns"])]
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
                    
                    for tr in soup_ev.find_all('tr'):
                        tr_txt = tr.get_text(separator=' ')
                        if any(p.search(tr_txt) for p in PLAYER_CONFIG["patterns"]):
                            links = [a.get_text().strip() for a in tr.find_all('a') if a.get_text().strip()]
                            cur_partner = updates.get("partner_hd") or updates.get("partner_mx") or existing_entry.get("partner_hd", "")
                            opponents = [n for n in links if not any(p.search(n) for p in PLAYER_CONFIG["patterns"]) and n != cur_partner]
                            
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

    winners_url = f"https://dbv.turnier.de/sport/winners.aspx?id={t_id}"
    try:
        r_win = session.get(winners_url, headers=headers, timeout=8)
        if r_win.status_code == 200 and any(p.search(r_win.text) for p in PLAYER_CONFIG["patterns"]):
            soup_win = BeautifulSoup(r_win.content, 'html.parser')
            for table in soup_win.find_all('table'):
                t_text = table.get_text()
                if any(p.search(t_text) for p in PLAYER_CONFIG["patterns"]):
                    disc_key = "hd"
                    if re.search(r'\b(Einzel|HE|MS)\b', t_text, re.I):
                        disc_key = "he"
                    elif re.search(r'\b(Mixed|MX|XD)\b', t_text, re.I):
                        disc_key = "mx"

                    for row in table.find_all('tr'):
                        row_t = row.get_text()
                        if any(p.search(row_t) for p in PLAYER_CONFIG["patterns"]):
                            if re.search(r'\b1\b|Winner|Sieger', row_t, re.I):
                                updates[f"placement_{disc_key}"] = "🥇 1. Platz"
                            elif re.search(r'\b2\b|Runner|Zweiter', row_t, re.I):
                                updates[f"placement_{disc_key}"] = "🥈 2. Platz"
                            elif re.search(r'\b3\b|3/4|Semi|Dritter', row_t, re.I):
                                updates[f"placement_{disc_key}"] = "🥉 3. Platz"
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
                "last_match_result": ""
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

    today = datetime.date.today()
    yield f"Suche nach Turnieren für {today.year} & {today.year + 1} auf turnier.de..."
    session = init_session()
    
    try:
        current_list = scrape_tournaments(session)
        yield f"Gefunden: {len(current_list)} Turniere im 100km-Umkreis um Langenfeld."
    except Exception as e:
        yield f"Fehler beim Scraping: {e}"
        return

    new_tournaments = []
    found_registrations = 0
    
    yield f"Gleiche Konkurrenzen, Zeitpläne & Ergebnisse für Marco Mainz ab..."
    
    for idx, t in enumerate(current_list):
        t_id = t["id"]
        
        if t_id not in known_tournaments:
            t["description"] = get_tournament_description(session, t["link"])
            
            # Automatische Spieltage & Meldeschluss aus dem Text erkennen
            if t["description"]:
                sch = auto_detect_schedule_and_deadline(t["description"])
                for k in ["day_he", "day_hd", "day_mx", "deadline"]:
                    if sch.get(k) and not t.get(k):
                        t[k] = sch[k]
                        
            sub_updates = check_player_subpages(session, t_id, t)
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
            
            # Automatische Spieltage & Meldeschluss aus dem Text erkennen
            if desc:
                sch = auto_detect_schedule_and_deadline(desc)
                for k in ["day_he", "day_hd", "day_mx", "deadline"]:
                    if sch.get(k) and not old_t.get(k):
                        old_t[k] = sch[k]

            sub_updates = check_player_subpages(session, t_id, old_t)
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
        yield f"Fertig! Alle Meldungen & Ergebnisse synchronisiert ({found_registrations} automatische Meldungen aktiv)."


if __name__ == "__main__":
    check_for_updates()