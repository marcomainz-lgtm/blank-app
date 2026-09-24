import os
import json
import re
import requests
from bs4 import BeautifulSoup
import urllib.parse
from gist_db import load_gist_file, save_gist_file, DatabaseConnectionError

# Ihr stabiler ntfy-Push-Kanal
NTFY_TOPIC = "my_badminton_tournaments_40723_v2" 
DB_FILE = "known_tournaments.json"


def is_youth_tournament(title, tag_parts):
    """
    Filtert Jugendturniere basierend auf Altersklassen-Tags (U11-U19)
    und typischen Nachwuchs-Schlüsselwörtern zuverlässig heraus.
    """
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


def get_tournament_description(session, tournament_url):
    """Liest den Infokasten (Ausschreibungstext) direkt von der Hauptseite aus."""
    try:
        if "id=" in tournament_url:
            parsed = urllib.parse.urlparse(tournament_url)
            params = urllib.parse.parse_qs(parsed.query)
            t_id = params.get('id', [None])[0]
            if t_id:
                tournament_url = f"https://dbv.turnier.de/tournament/{t_id}"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Accept-Language": "de-DE,de;q=0.9"
        }
        r = session.get(tournament_url, headers=headers, timeout=10)
        if r.status_code == 200:
            soup = BeautifulSoup(r.content, 'html.parser')
            alert_box = soup.find(class_=re.compile(r'alert--info|alert__body'))
            if alert_box:
                return alert_box.get_text(separator="\n").strip()
            
            main_content = soup.find(id="main")
            if main_content:
                return main_content.get_text(separator="\n").strip()[:1000]
                
            return soup.get_text(separator="\n").strip()[:500]
    except Exception as e:
        print(f"Fehler beim Laden der Beschreibung für {tournament_url}: {e}")
    return ""


def scrape_tournaments(s):
    url = "https://dbv.turnier.de/find/tournament/DoSearch"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://dbv.turnier.de/find",
        "X-Requested-With": "XMLHttpRequest"
    }

    tournaments = []
    seen_ids = set()
    page = 1
    max_pages = 20

    while page <= max_pages:
        print(f"Scraping page {page}...")
        payload = {
            "Page": str(page),
            "TournamentExtendedFilter.SportID": "2",  # 2 = Badminton
            "TournamentFilter.Q": "",
            "TournamentFilter.DateFilterType": "0",
            "TournamentFilter.StartDate": "2026-01-01T00:00",
            "TournamentFilter.EndDate": "2026-12-31T00:00",
            "TournamentFilter.PostalCode": "40723",
            "TournamentFilter.Distance": "100"
        }

        try:
            response = s.post(url, data=payload, headers=headers, timeout=15)
            response.raise_for_status()
        except Exception as e:
            print(f"Failed to fetch data on page {page}: {e}")
            break

        soup = BeautifulSoup(response.content, 'html.parser')
        page_tournaments_count = 0

        for link in soup.find_all('a', href=True):
            href = link['href']
            
            if 'id=' in href and ('/tournament' in href or '/sport/' in href):
                title = link.text.strip()
                
                if not title:
                    continue

                parsed_url = urllib.parse.urlparse(href)
                params = urllib.parse.parse_qs(parsed_url.query)
                t_id = params.get('id', [None])[0]

                if not t_id or t_id in seen_ids:
                    continue
                    
                full_link = urllib.parse.urljoin("https://dbv.turnier.de", href)

                container = link.find_parent(['li', 'tr'])
                if not container:
                    container = link.find_parent('div')

                tag_parts = []
                city = "Unknown"
                distance = None
                organizer = "Unknown"
                start_date = None
                end_date = None
                logo_url = ""

                if container:
                    raw_text = container.get_text(separator=' | ').strip()
                    cleaned_parts = []
                    for part in raw_text.split('|'):
                        part_strip = part.strip()
                        if part_strip and part_strip != title and part_strip not in cleaned_parts:
                            cleaned_parts.append(part_strip)

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
                            
                            cleaned = re.sub(r'\(.*?\)', '', part)
                            cleaned = re.sub(r'\[.*?\]', '', cleaned)
                            city = cleaned.strip()
                            break

                    non_meta_parts = []
                    for part in cleaned_parts:
                        has_date = bool(re.search(r'\b\d{2}\.\d{2}\.\d{4}\b', part))
                        has_km = 'km' in part.lower()
                        if not has_date and not has_km:
                            non_meta_parts.append(part)
                    if non_meta_parts:
                        organizer = non_meta_parts[0]

                    for part in cleaned_parts:
                        if re.search(r'\b\d{2}\.\d{2}\.\d{4}\b', part):
                            continue

                        is_tag = (len(part) < 15 or 
                                  part.lower().startswith('u') or 
                                  part.lower().startswith('o') or 
                                  part == 'Open')
                        if is_tag:
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
                    "description": ""
                })
                page_tournaments_count += 1

        if page_tournaments_count == 0:
            break
            
        has_more = response.headers.get('HasMoreResults')
        if has_more and has_more.lower() == 'false':
            break

        page += 1

    print(f"Scraped {len(tournaments)} tournament(s) across {page} page(s).")
    return tournaments


def send_push_notification(new_items):
    if not new_items:
        return

    count = len(new_items)
    summary_lines = []
    for idx, item in enumerate(new_items[:5]):
        summary_lines.append(f"- {item['title']} in {item['city']} ({item['start_date']})")
        
    if count > 5:
        summary_lines.append(f"... sowie {count - 5} weitere neue Turniere.")
        
    summary_lines.append("\nDashboard öffnen: https://turniere.streamlit.app")
    message = "\n".join(summary_lines)
    
    try:
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode('utf-8'),
            headers={
                "Title": f"🏸 {count} neue(s) Badminton-Turnier(e) gefunden!",
                "Priority": "high",
                "Tags": "badminton,sports,tada"
            },
            timeout=10
        )
        print(f"Push-Benachrichtigung für {count} Turniere erfolgreich gesendet.")
    except Exception as e:
        print(f"Fehler beim Senden der Push-Nachricht: {e}")


def check_for_updates():
    """Fallback-Funktion."""
    for _ in check_for_updates_generator():
        pass


def check_for_updates_generator():
    """Generator-Funktion mit FAIL-SAFE Datenbankprüfung vor dem Scrapen."""
    yield "Verbinde mit zentraler Cloud-Datenbank (GitHub Gist)..."
    
    # 1. NOTBREMSE: Erst Datenbank prüfen
    try:
        known_tournaments = load_gist_file(DB_FILE)
        yield f"✅ Datenbank erfolgreich geladen ({len(known_tournaments)} bekannte Turniere in der Cloud)."
    except DatabaseConnectionError as e:
        yield f"🚨 KRITISCHER DATENBANKFEHLER: {e}"
        yield "❌ VORGANG ABGEBROCHEN! Es wurden weder Turniere gescrapt noch Push-Nachrichten versendet."
        return

    # 2. Erst nach erfolgreicher Datenbankprüfung auf turnier.de zugreifen
    yield "Suche nach neuen Turnieren auf turnier.de..."
    session = requests.Session()
    
    for dom in ["dbv.turnier.de", ".turnier.de", "www.turnier.de"]:
        session.cookies.set("st", "l=1031&exp=48244.9228685648&c=1", domain=dom, path="/")
    
    headers_init = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    }
    try:
        session.get("https://dbv.turnier.de/find", headers=headers_init, timeout=10)
        yield "Frische Session-Cookies geladen."
    except Exception as e:
        yield f"Warnung Session-Cookies: {e}."
    
    try:
        current_list = scrape_tournaments(session)
        yield f"Suche beendet: {len(current_list)} Turniere im 100km-Umkreis ermittelt."
    except Exception as e:
        yield f"Fehler beim Scraping: {e}"
        return

    new_tournaments = []
    for t in current_list:
        t_id = t["id"]
        if t_id not in known_tournaments:
            yield f"Neues Turnier erkannt: {t['title']}. Lade Ausschreibung..."
            t["description"] = get_tournament_description(session, t["link"])
            t["day_he"] = ""
            t["day_hd"] = ""
            t["day_mx"] = ""
            t["full_he"] = False
            t["full_hd"] = False
            t["full_mx"] = False
            
            new_tournaments.append(t)
            known_tournaments[t_id] = t
        else:
            # Bestehende Einstellungen erhalten
            old_t = known_tournaments[t_id]
            is_registered = old_t.get('registered', False)
            reg_he = old_t.get('reg_he', False)
            reg_hd = old_t.get('reg_hd', False)
            reg_mx = old_t.get('reg_mx', False)
            full_he = old_t.get('full_he', False)
            full_hd = old_t.get('full_hd', False)
            full_mx = old_t.get('full_mx', False)
            partner_hd = old_t.get('partner_hd', '')
            partner_mx = old_t.get('partner_mx', '')
            day_he = old_t.get('day_he', '')
            day_hd = old_t.get('day_hd', '')
            day_mx = old_t.get('day_mx', '')
            
            desc = old_t.get('description', '')
            if not desc:
                yield f"Lade Ausschreibungstext für '{t['title']}' nach..."
                desc = get_tournament_description(session, t["link"])

            known_tournaments[t_id] = t
            known_tournaments[t_id]['registered'] = is_registered
            known_tournaments[t_id]['reg_he'] = reg_he
            known_tournaments[t_id]['reg_hd'] = reg_hd
            known_tournaments[t_id]['reg_mx'] = reg_mx
            known_tournaments[t_id]['full_he'] = full_he
            known_tournaments[t_id]['full_hd'] = full_hd
            known_tournaments[t_id]['full_mx'] = full_mx
            known_tournaments[t_id]['partner_hd'] = partner_hd
            known_tournaments[t_id]['partner_mx'] = partner_mx
            known_tournaments[t_id]['day_he'] = day_he
            known_tournaments[t_id]['day_hd'] = day_hd
            known_tournaments[t_id]['day_mx'] = day_mx
            known_tournaments[t_id]['description'] = desc

    # Sicher speichern
    try:
        save_gist_file(DB_FILE, known_tournaments)
        yield "💾 Änderungen erfolgreich in GitHub Gist gespeichert."
    except DatabaseConnectionError as e:
        yield f"🚨 FEHLER BEIM SPEICHERN IM GIST: {e}"
        return

    if new_tournaments:
        yield f"Fertig! {len(new_tournaments)} neue(s) Turnier(e) gefunden."
        send_push_notification(new_tournaments)
    else:
        yield "Fertig! Keine neuen Turniere erkannt (Datenbestand unverändert)."