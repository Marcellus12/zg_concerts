import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
import json
import csv
from icalendar import Calendar, Event
import uuid
import re
import dateparser

# --- CONFIGURATION ---
SONGKICK_URL = "https://www.songkick.com/metro-areas/29037-croatia-zagreb"
TVORNICA_URL = "https://www.tvornicakulture.com/svi-dogadaji/"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
today = datetime.now(timezone.utc)

def clean_text(text):
    """Basic cleanup for names."""
    if not text: return ""
    return text.strip().replace('\xa0', ' ')

def extract_clean_artist(title):
    """Removes Croatian promotional fluff from event titles."""
    stop_phrases = [
        r'\s+u\s+', r'\s+priprema\s+', r'\s+najavljuje\s+', 
        r'\s+promocija\s+', r'\s+dolazi\s+', r'\s+-\s+', r'\s+:\s+'
    ]
    clean_name = title
    for pattern in stop_phrases:
        clean_name = re.split(pattern, clean_name, flags=re.IGNORECASE)[0]
    return clean_name.strip()

# --- INITIALIZATION ---
cal = Calendar()
cal.add('prodid', '-//Zagreb Events//EN')
cal.add('version', '2.0')

seen_event_ids = set() # Format: "YYYY-MM-DD-ArtistName"
all_rows = []

# --- PHASE 1: SONGKICK (Restored Original Logic) ---
try:
    print("--- Scraping Songkick ---")
    res = requests.get(SONGKICK_URL, headers=headers, timeout=15)
    soup = BeautifulSoup(res.text, "html.parser")
    
    for event_tag in soup.select("li.event-listings-element"):
        try:
            json_script = event_tag.select_one('script[type="application/ld+json"]')
            if not json_script: continue
            
            data = json.loads(json_script.string)
            event_data = data[0] if isinstance(data, list) else data
            
            # 1. Date Handling
            raw_date_str = event_data.get('startDate')
            # Standardize to YYYY-MM-DD
            clean_date = raw_date_str[:10] 
            event_date = datetime.fromisoformat(raw_date_str).replace(tzinfo=timezone.utc)
            if event_date < today: continue

            venue = event_data.get('location', {}).get('name', 'Venue TBD')
            link = event_data.get('url', '')
            e_type = "Festival" if "Festival" in event_data.get('name', '') else "Concert"
            
            # 2. Artist Extraction (Festival vs Concert)
            lineup_tag = event_tag.select_one("span.support")
            artists_to_add = []
            
            if e_type == "Festival" and lineup_tag:
                # Explosion: split by 'and' and ','
                raw_lineup = lineup_tag.text.replace(' and ', ', ')
                artists_to_add = [clean_text(a) for a in raw_lineup.split(',') if clean_text(a)]
            else:
                artist_name = extract_clean_artist(event_data.get('name', '').split('@')[0])
                artists_to_add = [artist_name]

            # 3. Add to Data
            for artist in artists_to_add:
                event_key = f"{clean_date}-{artist}".lower()
                if event_key not in seen_event_ids:
                    seen_event_ids.add(event_key)
                    all_rows.append({
                        "date": clean_date,
                        "artist": artist,
                        "venue": venue,
                        "type": e_type,
                        "link": link,
                        "source": "Songkick"
                    })
                    
                    # ICS Entry
                    v_event = Event()
                    v_event.add('summary', f"{artist} ({e_type})")
                    v_event.add('dtstart', event_date.date())
                    v_event.add('location', f"{venue}, Zagreb")
                    v_event.add('uid', f"{clean_date}-{uuid.uuid5(uuid.NAMESPACE_DNS, artist+link)}")
                    cal.add_component(v_event)

        except Exception as e:
            print(f"Songkick Item Error: {e}")
            continue

except Exception as e:
    print(f"Songkick Main Error: {e}")

# --- PHASE 2: TVORNICA KULTURE (Elementor Logic) ---
try:
    print("\n--- Scraping Tvornica Kulture ---")
    t_res = requests.get(TVORNICA_URL, headers=headers, timeout=15)
    t_res.encoding = 'utf-8'
    t_soup = BeautifulSoup(t_res.content, "html.parser")
    
    for item in t_soup.select(".e-loop-item"):
        title_link = item.select_one("h2.elementor-heading-title a")
        date_widget = item.select(".elementor-widget-text-editor")
        
        if title_link and len(date_widget) >= 2:
            artist = extract_clean_artist(title_link.text.strip())
            link = title_link.get('href', TVORNICA_URL)
            raw_date_text = date_widget[1].text.strip()
            
            # Use dateparser to handle Croatian cases safely
            dt = dateparser.parse(raw_date_text, languages=['hr', 'en'], settings={'PREFER_DATES_FROM': 'future'})
            if not dt: continue
            
            clean_date = dt.strftime('%Y-%m-%d')
            event_key = f"{clean_date}-{artist}".lower()
            
            # DUPLICATE CHECK: Skip if Songkick already added this show
            if event_key not in seen_event_ids:
                print(f"🌟 Unique to Tvornica: {artist} ({clean_date})")
                seen_event_ids.add(event_key)
                all_rows.append({
                    "date": clean_date,
                    "artist": artist,
                    "venue": "Tvornica Kulture",
                    "type": "Concert",
                    "link": link,
                    "source": "Tvornica"
                })
                
                # Add to Calendar
                v_event = Event()
                v_event.add('summary', artist)
                v_event.add('dtstart', dt.date())
                v_event.add('location', "Tvornica Kulture, Zagreb")
                v_event.add('uid', f"{clean_date}-{uuid.uuid5(uuid.NAMESPACE_DNS, artist+link)}")
                cal.add_component(v_event)
            else:
                print(f"Skipping duplicate: {artist}")

except Exception as e:
    print(f"Tvornica Scraper Error: {e}")

# --- PHASE 3: SAVE ---
fieldnames = ["date", "artist", "venue", "type", "link", "source"]
with open("events.csv", "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(all_rows)

with open("zagreb_gigs.ics", "wb") as f:
    f.write(cal.to_ical())
# --- Save to last_updated.js ---
with open("last_updated.js", "w") as f:
    now_str = datetime.now().strftime("%d.%m.%Y %H:%M")
    # This updated version actually finds the HTML element and fills it
    f.write(f"document.getElementById('update-time').textContent = '{now_str}';")
print(f"\nFinished! CSV saved with {len(all_rows)} rows.")

with open("last_updated.js", "w") as f:
    # Get the current time in Croatian/European format
    now_str = datetime.now().strftime("%d.%m.%Y %H:%M")
    
    # This writes the exact line of JavaScript your HTML is looking for
    f.write(f"document.getElementById('update-time').textContent = '{now_str}';")

print(f"Update time stamped: {now_str}")
