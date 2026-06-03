import os
import json
import re
import requests
from bs4 import BeautifulSoup
import urllib.parse

# Wir ändern das Topic leicht auf '_v2', um die heutige ntfy-Sperre sofort zu umgehen
NTFY_TOPIC = "my_badminton_tournaments_40723_v2" 

DB_FILE = "known_tournaments.json"

def is_youth_tournament(title, tag_parts):
    """
    Prüft, ob es sich um ein Jugendturnier handelt.
    """
    u_pattern = re.compile(r'^u\d+$', re.IGNORECASE)
    for tag in tag_parts:
        if u_pattern.match(tag.strip()):
            return True
            
    if re.search(r'\b[uU]\d{1,2}\b', title):
        return True
        
    youth_keywords = ['junior', 'kids', 'küken', 'schüler', 'jugend', 'nachwuchs', 'mini-cup']
    title_lower = title.lower()
    if any(kw in title_lower for kw in youth_keywords):
        return True
        
    return False

def scrape_tournaments():
    url = "https://dbv.turnier.de/find/tournament/DoSearch"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://dbv.turnier.de/find",
        "X-Requested-With": "XMLHttpRequest"
    }

    s = requests.Session()
    s.cookies.set("st", "l=1031&exp=48244.9228685648&c=1", domain="dbv.turnier.de", path="/")
    s.cookies.set("st", "l=1031&exp=48244.9228685648&c=1", domain=".turnier.de", path="/")

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
                    "tags": tags
                })
                page_tournaments_count += 1

        print(f"Page {page} yielded {page_tournaments_count} tournament(s).")
        
        if page_tournaments_count == 0:
            pass
            
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
    
    # 1. Zusammenfassung bauen
    summary_lines = []
    for idx, item in enumerate(new_items[:5]):  # Zeigt maximal die ersten 5 Turniere direkt an
        summary_lines.append(f"- {item['title']} in {item['city']} ({item['start_date']})")
        
    if count > 5:
        summary_lines.append(f"... sowie {count - 5} weitere neue Turniere.")
        
    summary_lines.append("\nDashboard öffnen: https://turniere.streamlit.app")
    message = "\n".join(summary_lines)
    
    try:
        # Sendet genau EINE Anfrage für die gesamte Liste
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode('utf-8'),
            headers={
                "Title": f"🏸 {count} neue(s) Turnier(e) gefunden",
                "Priority": "high",
                "Tags": "badminton,sports,exclamation"
            }
        )
        print(f"Consolidated notification sent for {count} tournament(s).")
    except Exception as e:
        print(f"Error sending notification: {e}")

def check_for_updates():
    print("Checking for tournament updates...")
    current_list = scrape_tournaments()
    
    known_tournaments = {}
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                known_tournaments = json.load(f)
        except Exception:
            print("Could not read database. Re-initializing.")

    new_tournaments = []
    for t in current_list:
        t_id = t["id"]
        if t_id not in known_tournaments:
            new_tournaments.append(t)
            known_tournaments[t_id] = t

    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(known_tournaments, f, ensure_ascii=False, indent=4)

    if new_tournaments:
        print(f"Found {len(new_tournaments)} new tournament(s)!")
        send_push_notification(new_tournaments)
    else:
        print("No new tournaments detected.")

if __name__ == "__main__":
    check_for_updates()