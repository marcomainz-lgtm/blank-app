import os
import json
import re
import requests
from bs4 import BeautifulSoup
import urllib.parse
from gist_db import load_gist_file, save_gist_file
import datetime
from zoneinfo import ZoneInfo

NTFY_TOPIC = "my_badminton_tournaments_40723_v2" 
DB_FILE = "known_tournaments.json"

UUID_PATTERN = re.compile(r'([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})')


def is_youth_tournament(title, tag_parts):
    """
    Filtert reine Jugendturniere heraus, BEHÄLT aber Turniere mit 
    Erwachsenen-/Seniorenklassen (O19, O35, O40 etc.) auch bei Mischturnieren.
    """
    t_lower = title.lower()
    
    # Wenn Senioren/Erwachsene explizit vorkommen -> DEFINITIV BEHALTEN!
    senior_keywords = ['o19', 'o30', 'o35', 'o40', 'o45', 'o50', 'o55', 'o60', 'o65', 'o70', 'o75', 'senioren', 'erwachsene', 'masters', 'veteran']
    has_senior_tag = any(any(tag.lower().startswith(sk) for sk in ['o19', 'o3', 'o4', 'o5', 'o6', 'o7']) for tag in tag_parts)
    
    if any(sk in t_lower for sk in senior_keywords) or has_senior_tag:
        return False

    # Reine Jugend-Kennzeichnungen prüfen
    u_pattern = re.compile(r'^u(9|11|13|15|17|19)$', re.IGNORECASE)
    has_youth_tag = any(u_pattern.match(tag.strip()) for tag in tag_parts)
    has_youth_title = bool(re.search(r'\b[uU](9|11|13|15|17|19)\b', title))
    youth_keywords = ['junior', 'kids', 'küken', 'schüler', 'jugend', 'nachwuchs']
    has_youth_kw = any(kw in t_lower for kw in youth_keywords)
    
    return has_youth_tag or has_youth_title or has_youth_kw


def get_tournament_description(session, tournament_url):
    """Liest den Ausschreibungstext von turnier.de zuverlässig aus."""
    try:
        match = UUID_PATTERN.search(tournament_url)
        if match:
            tournament_url = f"https://dbv.turnier.de/tournament/{match.group(1).upper()}"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Accept-Language": "de-DE,de;q=0.9"
        }
        r = session.get(tournament_url, headers=headers, timeout=12)
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
    max_pages = 25

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
            print(f"Fehler beim Laden von Seite {page}: {e}")
            break

        soup = BeautifulSoup(response.content, 'html.parser')
        page_tournaments_count = 0

        for link in soup.find_all('a', href=True):
            href = link['href']
            
            # Erkennt sowohl alte (?id=UUID) als auch neue (/tournament/UUID) Links
            match = UUID_PATTERN.search(href)
            if not match:
                continue
                
            if not ('/tournament' in href or '/sport/' in href):
                continue

            title = link.text.strip()
            if not title:
                continue

            t_id = match.group(1).upper()
            if t_id in seen_ids:
                continue

            full_link = f"https://dbv.turnier.de/tournament/{t_id}"

            container = link.find_parent(['li', 'tr'])
            if not container:
                container = link.find_parent('div')

            tag_parts = []
            city = "Unbekannt"
            distance = None
            organizer = "Unbekannt"
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

                # Stadt und Distanz sauber trennen
                for part in cleaned_parts:
                    if 'km' in part.lower():
                        dist_match = re.search(r'(\d+)\s*km', part.lower())
                        if dist_match:
                            distance = int(dist_match.group(1))
                        
                        cleaned = re.sub(r'\(.*?\)', '', part)
                        cleaned = re.sub(r'\[.*?\]', '', cleaned)
                        cleaned = re.sub(r'\d+\s*km', '', cleaned, flags=re.IGNORECASE)
                        clean_city = cleaned.strip(' -|,\t\n')
                        if clean_city:
                            city = clean_city
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
                "notes": "",
                "placement_he": "",
                "field_he": "",
                "placement_hd": "",
                "field_hd": "",
                "placement_mx": "",
                "field_mx": "",
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
                "Title": f"{count} neue(s) Badminton-Turnier(e) gefunden!",
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
    """Generator-Funktion mit FAIL-SAFE Datenbankprüfung und absolutem Erhalt aller Nutzereingaben."""
    yield "Verbinde mit zentraler Cloud-Datenbank (GitHub Gist)..."
    
    try:
        known_tournaments = load_gist_file(DB_FILE, fallback_default={})
        yield f"✅ Datenbank erfolgreich geladen ({len(known_tournaments)} bekannte Turniere in der Cloud)."
    except Exception as e:
        yield f"🚨 KRITISCHER DATENBANKFEHLER: {e}"
        yield "❌ VORGANG ABGEBROCHEN! Es wurden weder Turniere gescrapt noch Push-Nachrichten versendet."
        return

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
            new_tournaments.append(t)
            known_tournaments[t_id] = t
        else:
            # Bestehendes Turnier: Metadaten aktualisieren, aber ALLE Marco-Eingaben 100% erhalten!
            old_t = known_tournaments[t_id]
            desc = old_t.get('description', '')
            if not desc:
                yield f"Lade Ausschreibungstext für '{t['title']}' nach..."
                desc = get_tournament_description(session, t["link"])

            # Aktualisiert nur die vom Scraper kommenden Stammdaten:
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
                "description": desc or old_t.get("description", "")
            })
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
        yield "Fertig! Keine neuen Turniere erkannt (Datenbestand unverändert)."


if __name__ == "__main__":
    check_for_updates()