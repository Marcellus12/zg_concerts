import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
import json
import csv
from icalendar import Calendar, Event
import uuid

# --- CONFIGURATION ---
# We still use Songkick as the "Base"
SONGKICK_URL = "https://www.songkick.com/metro-areas/29037-croatia-zagreb"
# New direct source to test
TVORNICA_URL = "https://www.tvornicakulture.com/svi-dogadaji/"

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
VENUE_TIMES = {"Tvornica kulture": 20, "Močvara": 20, "Boogaloo": 19, "Vintage Industrial Bar": 20}

# Initialize a NEW Test Calendar
cal = Calendar()
cal.add('prodid', '-//Zagreb Test Calendar//EN')
cal.add('version', '2.0')
cal.add('x-wr-calname', 'TEST: Zagreb Gigs')

seen_event_ids = set()
all_rows = []
new_found_count = 0
today = datetime.now(timezone.utc)

# --- PHASE 1: SCRAPE SONGKICK (The Baseline) ---
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
        date_str = e.get('startDate') 
        venue = e.get('location', {}).get('name', 'Unknown Venue')
        
        event_key = f"{date_str}-{artist}".lower()
        seen_event_ids.add(event_key)

        hour = VENUE_TIMES.get(venue, 20)
        start_dt = datetime.fromisoformat(date_str).replace(hour=hour, minute=0, second=0, tzinfo=timezone.utc)
        
        if start_dt < today: continue

        v_event = Event()
        v_event.add('summary', artist)
        v_event.add('dtstart', start_dt)
        v_event.add('location', f"{venue}, Zagreb")
        v_event.add('uid', str(uuid.uuid5(uuid.NAMESPACE_DNS, event_key)))
        cal.add_component(v_event)
        all_rows.append({"date": date_str, "artist": artist, "venue": venue, "source": "Songkick"})

except Exception as e:
    print(f"Songkick Scraper Error: {e}")

# --- PHASE 2: SCRAPE TVORNICA KULTURE (The Test) ---
try:
    print("\n--- Phase 2: Scraping Tvornica Kulture Direct ---")
    t_res = requests.get(TVORNICA_URL, headers=headers, timeout=15)
    t_res.encoding = 'utf-8'
    t_soup = BeautifulSoup(t_res.content, "html.parser")
    
    for item in t_soup.select(".tribe-events-calendar-list__event, .tribe-common-g-row"):
        title_tag = item.select_one(".tribe-events-calendar-list__event-title, h3")
        date_tag = item.select_one("time.tribe-events-calendar-list__event-datetime")
        
        if title_tag and date_tag:
            artist = title_tag.text.strip()
            raw_date = date_tag.get('datetime')
            
            if not raw_date: continue
            
            event_key = f"{raw_date}-{artist}".lower()
            
            # This is where we see if Tvornica has something Songkick missed
            if event_key not in seen_event_ids:
                print(f"🌟 NEW UNIQUE SHOW FOUND: {artist} on {raw_date}")
                new_found_count += 1
                seen_event_ids.add(event_key)
                
                start_dt = datetime.fromisoformat(raw_date).replace(hour=20, minute=0, second=0, tzinfo=timezone.utc)
                
                if start_dt > today:
                    v_event = Event()
                    v_event.add('summary', f"[NEW] {artist}")
                    v_event.add('dtstart', start_dt)
                    v_event.add('location', "Tvornica Kulture, Zagreb")
                    v_event.add('uid', str(uuid.uuid5(uuid.NAMESPACE_DNS, event_key)))
                    cal.add_component(v_event)
                    all_rows.append({"date": raw_date, "artist": artist, "venue": "Tvornica Kulture", "source": "Tvornica_Direct"})
            else:
                print(f"Skipping duplicate: {artist}")

except Exception as e:
    print(f"Tvornica Scraper Error: {e}")

# --- PHASE 3: SAVE TO TEST FILES ---
print(f"\n--- Phase 3: Saving Test Results ---")

# Save the TEST Calendar
with open("test_zagreb_gigs.ics", "wb") as f:
    f.write(cal.to_ical())

# Save the TEST CSV (with Source column so you can see where it came from)
with open("test_events.csv", "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(f, fieldnames=["date", "artist", "venue", "source"])
    writer.writeheader()
    writer.writerows(all_rows)

# ... (rest of your script above)

# Create a TEST timestamp
now_str = datetime.now().strftime("%d.%m.%Y %H:%M")
with open("test_last_updated.js", "w") as f:
    f.write(f"console.log('Test Scraper last run: {now_str}');")

print(f"\n--- Phase 3: Saving Test Results ---")
print(f"Done! Found {new_found_count} shows on Tvornica that were NOT on Songkick.")
print(f"Files created: test_zagreb_gigs.ics, test_events.csv")
