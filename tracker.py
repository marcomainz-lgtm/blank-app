import os
import json
import re
import requests
from bs4 import BeautifulSoup
import urllib.parse
import datetime

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


def detect_discipline_days(tournament_url, start_date_str, end_date_str):
    """
    Sucht auf der Turnierseite und deren relevanten Navigations-Unterseiten nach Informationen,
    welche Disziplin an welchem Tag (Samstag/Sonntag) stattfindet. Unterstützt Deutsch & Englisch.
    """
    days = {"he": "", "hd": "", "mx": ""}
    weekday_names = {
        0: "Montag", 1: "Dienstag", 2: "Mittwoch", 3: "Donnerstag",
        4: "Freitag", 5: "Samstag", 6: "Sonntag"
    }

    # --- REGEL 1: Eintägige Turniere automatisch zuweisen ---
    if start_date_str and end_date_str and start_date_str == end_date_str:
        try:
            dt = datetime.datetime.strptime(start_date_str, "%d.%m.%Y").date()
            day_name = weekday_names[dt.weekday()]
            print(f" -> {tournament_url}: Eintägiges Turnier am {day_name}. Automatische Zuweisung durchgeführt.")
            return {"he": day_name, "hd": day_name, "mx": day_name}
        except Exception:
            pass

    # --- REGEL 2: Heuristische Suche auf Turnier.de ---
    try:
        session = requests.Session()
        # Sprach-Cookies setzen, damit wir die deutsche Version erzwingen und Cookie-Einwilligungen umgehen
        session.cookies.set("st", "l=1031&exp=48244.9228685648&c=1", domain="dbv.turnier.de", path="/")
        session.cookies.set("st", "l=1031&exp=48244.9228685648&c=1", domain=".turnier.de", path="/")
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Accept-Language": "de-DE,de;q=0.9"
        }
        r = session.get(tournament_url, headers=headers, timeout=10)
        if r.status_code != 200:
            return days
        
        soup = BeautifulSoup(r.content, 'html.parser')
        
        # Haupttext extrahieren (Zeilenumbrüche erhalten!)
        text = soup.get_text(separator="\n").lower()
        
        # Navigation nach relevanten Unterseiten durchsuchen
        sub_links = []
        for a in soup.find_all('a', href=True):
            a_text = a.get_text().lower().strip()
            a_href = a['href']
            # Relevante Keywords für Zeitpläne, Bestimmungen, Disziplinen oder Klassen
            keywords = ["bestimmungen", "ausschreibung", "zeitplan", "programm", "ablauf", "informationen", "info", "disziplinen", "klassen", "meldungen"]
            if any(k in a_text for k in keywords) or any(k in a_href.lower() for k in keywords):
                full_sub_link = urllib.parse.urljoin(tournament_url, a_href)
                sub_links.append(full_sub_link)
        
        # Bis zu 5 interne Unterseiten scannen (PDFs ausklammern)
        sub_links = list(set(sub_links))[:5]
        for sub_link in sub_links:
            try:
                if sub_link.endswith(".pdf"):
                    continue
                r_sub = session.get(sub_link, headers=headers, timeout=5)
                if r_sub.status_code == 200:
                    soup_sub = BeautifulSoup(r_sub.content, 'html.parser')
                    text_sub = soup_sub.get_text(separator="\n").lower()
                    text += "\n" + text_sub
            except Exception:
                pass
        
        # Text zeilenweise verarbeiten, um logische Einheiten nicht zu zerreißen
        raw_lines = text.split("\n")
        clauses = []
        for line in raw_lines:
            line_clean = re.sub(r'\s+', ' ', line).strip()
            if not line_clean:
                continue
            # Trenne nach typischen Abgrenzungen (aber NICHT nach Komma oder Punkt!)
            sub_parts = re.split(r'[|•;–-]', line_clean)
            for part in sub_parts:
                part_clean = part.strip()
                if part_clean:
                    clauses.append(part_clean)
        
        found_he = []
        found_hd = []
        found_mx = []
        
        for c in clauses:
            c_lower = c.strip()
            if len(c_lower) < 5:
                continue
            
            # Wochentage prüfen (Deutsch & Englisch)
            is_sat = "samstag" in c_lower or "saturday" in c_lower or re.search(r'\bsa\b', c_lower) or re.search(r'\bsat\b', c_lower)
            is_sun = "sonntag" in c_lower or "sunday" in c_lower or re.search(r'\bso\b', c_lower) or re.search(r'\bsun\b', c_lower)
            
            if is_sat and not is_sun:
                day_val = "Samstag"
            elif is_sun and not is_sat:
                day_val = "Sonntag"
            else:
                continue
                
            # Disziplinen erkennen (Deutsch & Englisch)
            is_he = ("einzel" in c_lower or "single" in c_lower or "he" in c_lower.split() or "de" in c_lower.split() or "ms" in c_lower.split() or "ws" in c_lower.split())
            is_hd = ("doppel" in c_lower or "double" in c_lower or "hd" in c_lower.split() or "dd" in c_lower.split() or "md" in c_lower.split() or "wd" in c_lower.split())
            is_mx = ("mixed" in c_lower or "gemischt" in c_lower or "mx" in c_lower.split() or "gd" in c_lower.split() or "xd" in c_lower.split())

            # Einzel (Herreneinzel / Dameneinzel)
            if is_he and not is_hd and not is_mx:
                found_he.append(day_val)
                
            # Doppel (Herrendoppel / Damendoppel)
            if is_hd and not is_he and not is_mx:
                found_hd.append(day_val)
                
            # Mixed
            if is_mx:
                found_mx.append(day_val)
        
        # Wenn eine Disziplin eindeutig an genau einem Tag gefunden wurde, eintragen
        if found_he and len(set(found_he)) == 1:
            days["he"] = found_he[0]
        if found_hd and len(set(found_hd)) == 1:
            days["hd"] = found_hd[0]
        if found_mx and len(set(found_mx)) == 1:
            days["mx"] = found_mx[0]
            
        # Logging der Heuristik-Ergebnisse im Terminal
        if days["he"] or days["hd"] or days["mx"]:
            print(f" -> Heuristik-Ergebnis für '{tournament_url}':")
            if days["he"]: print(f"    * Herreneinzel: {days['he']}")
            if days["hd"]: print(f"    * Herrendoppel: {days['hd']}")
            if days["mx"]: print(f"    * Mixed: {days['mx']}")
            
    except Exception as e:
        print(f"Fehler bei der Zeitplan-Heuristik für {tournament_url}: {e}")
        
    return days


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
                    # Frisch gefundene Turniere mit sauberen Default-Datenfeldern initialisieren
                    "registered": False,
                    "reg_he": False,
                    "reg_hd": False,
                    "reg_mx": False,
                    "partner_hd": "",
                    "partner_mx": "",
                    "day_he": "",
                    "day_hd": "",
                    "day_mx": ""
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
                "Title": "Letztes Update der Datenbank",
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
            # 1. Neues Turnier gefunden -> Heuristische Zeitplananalyse durchführen!
            print(f"Neues Turnier gefunden: {t['title']}. Analysiere Zeitplan...")
            detected_days = detect_discipline_days(t["link"], t["start_date"], t["end_date"])
            t["day_he"] = detected_days["he"]
            t["day_hd"] = detected_days["hd"]
            t["day_mx"] = detected_days["mx"]
            
            new_tournaments.append(t)
            known_tournaments[t_id] = t
        else:
            # 2. Bestehendes Turnier -> Daten bewahren und ggf. fehlende Spieltage analysieren
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

            # Falls Felder noch den alten Default-Wert "gesamt" haben, leeren
            if day_he == "gesamt": day_he = ""
            if day_hd == "gesamt": day_hd = ""
            if day_mx == "gesamt": day_mx = ""

            # Falls der Zeitplan noch komplett unbeschrieben ist, versuchen wir ihn nachträglich zu bestimmen (Migration)
            if not day_he and not day_hd and not day_mx:
                print(f"Analysiere Zeitplan für bestehendes Turnier: {t['title']}...")
                detected_days = detect_discipline_days(t["link"], t["start_date"], t["end_date"])
                day_he = detected_days["he"]
                day_hd = detected_days["hd"]
                day_mx = detected_days["mx"]

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

    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(known_tournaments, f, ensure_ascii=False, indent=4)

    if new_tournaments:
        print(f"Found {len(new_tournaments)} new tournament(s)!")
        send_push_notification(new_tournaments)
    else:
        print("No new tournaments detected.")


if __name__ == "__main__":
    check_for_updates()git add . && git commit -m "Eintaegige Turniere und dynamische Wochentage implementiert" && git pull --rebase && git push && python tracker.py