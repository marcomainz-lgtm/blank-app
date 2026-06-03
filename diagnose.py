import requests
from bs4 import BeautifulSoup

url = "https://dbv.turnier.de/find?DateFilterType=0&StartDate=2026-01-01&EndDate=2026-12-31&Distance=100&page=1&PostalCode=40723"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://dbv.turnier.de/"
}
cookies = {
    "st": "l=1031&exp=48244.9228685648&c=1"
}

try:
    response = requests.get(url, headers=headers, cookies=cookies, timeout=15)
    print("=== Diagnostic Results ===")
    print(f"Status Code: {response.status_code}")
    print(f"Final URL: {response.url}")
    print(f"Response Length: {len(response.text)} characters")
    
    soup = BeautifulSoup(response.content, 'html.parser')
    print(f"Page Title: {soup.title.text.strip() if soup.title else 'No title tag found'}")
    
    html_sample = response.text.lower()
    if "cloudflare" in html_sample or "challenge-platform" in html_sample or "waiting room" in html_sample:
        print("\n[!] Detection: Cloudflare anti-bot protection or challenge page detected.")
    elif "cookie" in html_sample and ("permission" in html_sample or "accept" in html_sample or "zustimmung" in html_sample):
        print("\n[!] Detection: The cookie consent wall is still blocking the request.")
    elif "0 ergebnisse" in html_sample or "no results" in html_sample or "keine turniere" in html_sample:
        print("\n[!] Detection: The page loaded successfully, but literally returned 0 search results on the server.")
    else:
        print("\n[!] Detection: The page loaded but the parser missed the elements. Here is a snippet:")
        print(response.text[:500])
        
    # Save the file to examine the raw HTML
    with open("debug_page.html", "w", encoding="utf-8") as f:
        f.write(response.text)
    print("\nSaved full response page to 'debug_page.html' for inspection.")
    
except Exception as e:
    print(f"An error occurred: {e}")