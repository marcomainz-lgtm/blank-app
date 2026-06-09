# --- START OF FILE tracker.py ---

import os
import json
import re
import requests
import base64
from bs4 import BeautifulSoup
import urllib.parse

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
            # Versuche den blauen Ausschreibungs-Infokasten (alert--info) zu finden
            alert_box = soup.find(class_=re.compile(r'alert--info|alert__body'))
            if alert_box:
                return alert_box.get_text(separator="\n").strip()
            
            # Fallback: Versuche den Haupt-Inhaltsbereich zu lesen
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
    max_pages = 20  # Sicherheitsgrenze für Scraper

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

                    # 1. Bild-Logo auslesen
                    img_el = container.find('img')
                    if img_el and img_el.get('src'):
                        logo_url = urllib.parse.urljoin("https://dbv.turnier.de", img_el['src'])

                    # 2. Start- und Enddatum extrahieren (Muster: DD.MM.YYYY)
                    dates = re.findall(r'\b\d{2}\.\d{2}\.\d{4}\b', raw_text)
                    if len(dates) >= 2:
                        start_date = dates[0]
                        end_date = dates[1]
                    elif len(dates) == 1:
                        start_date = dates[0]
                        end_date = dates[0]

                    # 3. Stadt und Kilometerzahl extrahieren
                    for part in cleaned_parts:
                        if 'km' in part.lower():
                            dist_match = re.search(r'(\d+)\s*km', part.lower())
                            if dist_match:
                                distance = int(dist_match.group(1))
                            
                            cleaned = re.sub(r'\(.*?\)', '', part)
                            cleaned = re.sub(r'\[.*?\]', '', cleaned)
                            city = cleaned.strip()
                            break

                    # 4. Ausrichter / Verein ("The Team") ermitteln
                    non_meta_parts = []
                    for part in cleaned_parts:
                        has_date = bool(re.search(r'\b\d{2}\.\d{2}\.\d{4}\b', part))
                        has_km = 'km' in part.lower()
                        if not has_date and not has_km:
                            non_meta_parts.append(part)
                    if non_meta_parts:
                        organizer = non_meta_parts[0]

                    # 5. Klassen (Tags) segmentieren
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

                # Jugendfilter anwenden
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
                    # Keine automatischen Disziplintage vorausfüllen - wir belassen diese leer
                    "registered": False,
                    "reg_he": False,
                    "reg_hd": False,
                    "reg_mx": False,
                    "partner_hd": "",
                    "partner_mx": "",
                    "day_he": "",
                    "day_hd": "",
                    "day_mx": "",
                    "description": ""
                })
                page_tournaments_count += 1

        print(f"Page {page} yielded {page_tournaments_count} tournament(s).")
        
        if page_tournaments_count == 0:
            break
            
        has_more = response.headers.get('HasMoreResults')
        if has_more and has_more.lower() == 'false':
            print("Server indicated no further results are available.")
            break

        page += 1

    print(f"Successfully scraped {len(tournaments)} tournament(s) in total across {page} page(s).")
    return tournaments


def send_push_notification(new_items):
    if not new_items:
        return

    count = len(new_items)
    
    summary_lines = ["Folgende neue Turniere wurden gefunden:"]
    for idx, item in enumerate(new_items[:5]):
        summary_lines.append(f"🏸 {item['title']} in {item['city']} ({item['start_date']})")
        
    if count > 5:
        summary_lines.append(f"... sowie {count - 5} weitere neue Turniere.")
        
    summary_lines.append("\nDashboard öffnen: https://turniere.streamlit.app")
    message = "\n".join(summary_lines)
    
    try:
        # UTF-8 Base64 Codierung für Emojis im Header-Titel (verhindert Darstellungsfehler)
        title_text = "Yeah, ein neues Turnier ist online! 🥳"
        encoded_title = f"=?utf-8?b?{base64.b64encode(title_text.encode('utf-8')).decode('utf-8')}?="

        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode('utf-8'),
            headers={
                "Title": encoded_title,
                "Priority": "high",
                "Tags": "badminton,party_popper"
            }
        )
        print(f"Consolidated notification sent for {count} tournament(s).")
    except Exception as e:
        print(f"Error sending notification: {e}")


def check_for_updates():
    """Fallback-Funktion für Kompatibilität."""
    for _ in check_for_updates_generator():
        pass


def check_for_updates_generator():
    """Generator-Funktion für das Echtzeit-Web-Aktivitätsprotokoll."""
    yield "Suche nach neuen Turnieren auf turnier.de..."
    session = requests.Session()
    
    # Setze Sprach- und Consent-Cookies für alle Subdomains von turnier.de
    for dom in ["dbv.turnier.de", ".turnier.de", "www.turnier.de"]:
        session.cookies.set("st", "l=1031&exp=48244.9228685648&c=1", domain=dom, path="/")
    
    headers_init = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    }
    try:
        session.get("https://dbv.turnier.de/find", headers=headers_init, timeout=10)
        yield "Frische Session-Cookies erfolgreich geladen."
    except Exception as e:
        yield f"Warnung beim Laden der Session-Cookies: {e}."
    
    try:
        current_list = scrape_tournaments(session)
        yield f"Suche beendet. {len(current_list)} Turniere im Umkreis von 100km ermittelt."
    except Exception as e:
        yield f"Fehler beim Laden der Turnierliste: {e}"
        return

    known_tournaments = {}
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                known_tournaments = json.load(f)
        except Exception:
            yield "Konnte bestehende Datenbank nicht lesen, initialisiere neu."

    # Neue Turniere aus dem Suchlauf in die Datenbank integrieren
    new_tournaments = []
    for t in current_list:
        t_id = t["id"]
        if t_id not in known_tournaments:
            yield f"Neues Turnier gefunden: {t['title']}. Lade Ausschreibungstext..."
            t["description"] = get_tournament_description(session, t["link"])
            t["day_he"] = ""
            t["day_hd"] = ""
            t["day_mx"] = ""
            
            new_tournaments.append(t)
            known_tournaments[t_id] = t
        else:
            # Sicherheits-Sync (Meldungen, Spieltage und Partner werden sicher beibehalten)
            old_t = known_tournaments[t_id]
            is_registered = old_t.get('registered', False)
            reg_he = old_t.get('reg_he', False)
            reg_hd = old_t.get('reg_hd', False)
            reg_mx = old_t.get('reg_mx', False)
            partner_hd = old_t.get('partner_hd', '')
            partner_mx = old_t.get('partner_mx', '')
            day_he = old_t.get('day_he', '')
            day_hd = old_t.get('day_hd', '')
            day_mx = old_t.get('day_mx', '')
            
            # Fehlenden Beschreibungstext bei bestehenden Turnieren nachladen
            desc = old_t.get('description', '')
            if not desc:
                yield f"Lade Ausschreibungstext für '{t['title']}' nach..."
                desc = get_tournament_description(session, t["link"])

            known_tournaments[t_id] = t
            known_tournaments[t_id]['registered'] = is_registered
            known_tournaments[t_id]['reg_he'] = reg_he
            known_tournaments[t_id]['reg_hd'] = reg_hd
            known_tournaments[t_id]['reg_mx'] = reg_mx
            known_tournaments[t_id]['partner_hd'] = partner_hd
            known_tournaments[t_id]['partner_mx'] = partner_mx
            known_tournaments[t_id]['day_he'] = day_he
            known_tournaments[t_id]['day_hd'] = day_hd
            known_tournaments[t_id]['day_mx'] = day_mx
            known_tournaments[t_id]['description'] = desc

    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(known_tournaments, f, ensure_ascii=False, indent=4)

    if new_tournaments:
        yield f"Fertig! {len(new_tournaments)} neue(s) Turnier(e) gefunden."
        send_push_notification(new_tournaments)
    else:
        yield "Fertig! Keine neuen Turniere erkannt."


if __name__ == "__main__":
    check_for_updates()

# --- END OF FILE tracker.py ---