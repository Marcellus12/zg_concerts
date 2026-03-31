import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
import json
import csv
from icalendar import Calendar, Event
import uuid

# --- CONFIGURATION ---
SONGKICK_URL = "https://www.songkick.com/metro-areas/29037-croatia-zagreb"
TVORNICA_URL = "https://www.tvornicakulture.com/svi-dogadaji/"

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
# Standard start times
VENUE_TIMES = {"Tvornica kulture": 20, "Močvara": 20, "Boogaloo": 19, "Vintage Industrial Bar": 20}

# Initialize a NEW Test Calendar
cal = Calendar()
cal.add('prodid', '-//Zagreb Test Calendar//EN')
cal.add('version', '2.0')
cal.add('x-wr-calname', 'TEST: Zagreb Gigs')

seen_event_ids = set()
all_rows = []
tvornica_only_rows = [] 
today = datetime.now(timezone.utc)

# --- PHASE 1: SCRAPE SONGKICK ---
try:
    print("--- Phase 1: Scraping Songkick Baseline ---")
    response = requests.get(SONGKICK_URL, headers=headers, timeout=15)
    response.encoding = 'utf-8'
    soup = BeautifulSoup(response.text, "html.parser")

    for event_tag in soup.select("li.event-listings-element"):
        json_script = event_tag.select_one('script[type="application/ld+json"]')
        if not json_script: continue
        
        data = json.loads(json_script.string)
        e = data[0] if isinstance(data, list) else data
        
        artist = e.get('name', 'Unknown Artist').split('@')[0].strip()
        date_str = e.get('startDate') # YYYY-MM-DD
        venue = e.get('location', {}).get('name', 'Unknown Venue')
        
        event_key = f"{date_str}-{artist}".lower()
        seen_event_ids.add(event_key)

        hour = VENUE_TIMES.get(venue, 20)
        start_dt = datetime.fromisoformat(date_str).replace(hour=hour, minute=0, second=0, tzinfo=timezone.utc)
        
        if start_dt >= today:
            # Add to calendar
            v_event = Event()
            v_event.add('summary', artist)
            v_event.add('dtstart', start_dt)
            v_event.add('location', f"{venue}, Zagreb")
            v_event.add('uid', str(uuid.uuid5(uuid.NAMESPACE_DNS, event_key)))
            cal.add_component(v_event)
            
            all_rows.append({"date": date_str, "artist": artist, "venue": venue, "source": "Songkick"})

except Exception as e:
    print(f"Songkick Scraper Error: {e}")

# --- PHASE 2: SCRAPE TVORNICA KULTURE ---
try:
    print("\n--- Phase 2: Scraping Tvornica Kulture Direct ---")
    t_res = requests.get(TVORNICA_URL, headers=headers, timeout=15)
    t_res.encoding = 'utf-8'
    t_soup = BeautifulSoup(t_res.content, "html.parser")
    
    items = t_soup.select(".tribe-events-calendar-list__event, .tribe-common-g-row")
    print(f"Found {len(items)} items on the Tvornica page.")

    for item in items:
        title_tag = item.select_one(".tribe-events-calendar-list__event-title, h3")
        date_tag = item.select_one("time.tribe-events-calendar-list__event-datetime")
        
        if title_tag and date_tag:
            artist = title_tag.text.strip()
            raw_date = date_tag.get('datetime')
            
            if not raw_date: continue
            
            # Ensure we only have the YYYY-MM-DD part
            clean_date = raw_date[:10]
            
            tvornica_only_rows.append({"date": clean_date, "artist": artist, "status": "Found on Page"})
            event_key = f"{clean_date}-{artist}".lower()
            
            if event_key not in seen_event_ids:
                start_dt = datetime.fromisoformat(clean_date).replace(hour=20, minute=0, second=0, tzinfo=timezone.utc)
                if start_dt > today:
                    print(f"🌟 Adding New Show: {artist}")
                    seen_event_ids.add(event_key)
                    
                    v_event = Event()
                    v_event.add('summary', f"[NEW] {artist}")
                    v_event.add('dtstart', start_dt)
                    v_event.add('location', "Tvornica Kulture, Zagreb")
                    v_event.add('uid', str(uuid.uuid5(uuid.NAMESPACE_DNS, event_key)))
                    cal.add_component(v_event)
                    
                    all_rows.append({"date": clean_date, "artist": artist, "venue": "Tvornica Kulture", "source": "Tvornica_Direct"})
            else:
                print(f"Skipping duplicate: {artist}")

except Exception as e:
    print(f"Tvornica Scraper Error: {e}")

# --- PHASE 3: SAVE ALL FILES ---
# 1. Merged CSV
with open("test_events.csv", "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(f, fieldnames=["date", "artist", "venue", "source"])
    writer.writeheader()
    writer.writerows(all_rows)

# 2. Tvornica Debug CSV
with open("tvornica_check.csv", "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(f, fieldnames=["date", "artist", "status"])
    writer.writeheader()
    writer.writerows(tvornica_only_rows)

# 3. Test iCal file
with open("test_zagreb_gigs.ics", "wb") as f:
    f.write(cal.to_ical())

# 4. Test Last Updated JS
now_str = datetime.now().strftime("%d.%m.%Y %H:%M")
with open("test_last_updated.js", "w") as f:
    f.write(f"console.log('Test Scraper last run: {now_str}');")

print(f"\nDone! Files updated: test_events.csv, tvornica_check.csv, test_zagreb_gigs.ics, test_last_updated.js")
