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
# Standard start times if not specified
VENUE_TIMES = {"Tvornica kulture": 20, "Močvara": 20, "Boogaloo": 19, "Vintage Industrial Bar": 20}

# Initialize Calendar
cal = Calendar()
cal.add('prodid', '-//Zagreb Gig Calendar//EN')
cal.add('version', '2.0')
cal.add('x-wr-calname', 'Zagreb Gigs')

seen_event_ids = set()
all_rows = []
today = datetime.now(timezone.utc)

# --- SECTION 1: SCRAPE SONGKICK ---
try:
    print("Scraping Songkick (Zagreb Metro)...")
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
        
        # Create unique key to prevent duplicates
        event_key = f"{date_str}-{artist}".lower()
        seen_event_ids.add(event_key)

        # Set start time
        hour = VENUE_TIMES.get(venue, 20)
        start_dt = datetime.fromisoformat(date_str).replace(hour=hour, minute=0, second=0, tzinfo=timezone.utc)
        
        if start_dt < today: continue

        v_event = Event()
        v_event.add('summary', artist)
        v_event.add('dtstart', start_dt)
        v_event.add('dtend', start_dt + timedelta(hours=3))
        v_event.add('location', f"{venue}, Zagreb")
        v_event.add('uid', str(uuid.uuid5(uuid.NAMESPACE_DNS, event_key)))
        cal.add_component(v_event)
        
        all_rows.append({"date": date_str, "artist": artist, "venue": venue})

except Exception as e:
    print(f"Songkick Error: {e}")

# --- SECTION 2: SCRAPE TVORNICA KULTURE (DIRECT) ---
try:
    print("Scraping Tvornica Kulture official site...")
    t_response = requests.get(TVORNICA_URL, headers=headers, timeout=15)
    t_response.encoding = 'utf-8'
    t_soup = BeautifulSoup(t_response.content, "html.parser")
    
    # Target the specific event blocks on Tvornica's site
    for item in t_soup.select(".tribe-events-calendar-list__event, .tribe-common-g-row"):
        title_tag = item.select_one(".tribe-events-calendar-list__event-title, h3")
        date_tag = item.select_one("time.tribe-events-calendar-list__event-datetime")
        
        if title_tag and date_tag:
            artist = title_tag.text.strip()
            # The 'datetime' attribute is usually clean YYYY-MM-DD
            raw_date = date_tag.get('datetime')
            
            if not raw_date: continue
            
            # Check for duplicates before adding
            event_key = f"{raw_date}-{artist}".lower()
            if event_key in seen_event_ids:
                print(f"Skipping duplicate: {artist}")
                continue
            
            seen_event_ids.add(event_key)
            start_dt = datetime.fromisoformat(raw_date).replace(hour=20, minute=0, second=0, tzinfo=timezone.utc)
            
            if start_dt > today:
                v_event = Event()
                v_event.add('summary', artist)
                v_event.add('dtstart', start_dt)
                v_event.add('dtend', start_dt + timedelta(hours=3))
                v_event.add('location', "Tvornica Kulture, Šubićeva 2, Zagreb")
                v_event.add('uid', str(uuid.uuid5(uuid.NAMESPACE_DNS, event_key)))
                cal.add_component(v_event)
                
                all_rows.append({"date": raw_date, "artist": artist, "venue": "Tvornica Kulture"})
                print(f"Added from Tvornica site: {artist}")

except Exception as e:
    print(f"Tvornica Scraper Error: {e}")

# --- SECTION 3: SAVE FILES ---
# 1. Save iCal file
with open("zagreb_gigs.ics", "wb") as f:
    f.write(cal.to_ical())

# 2. Save CSV file
with open("events.csv", "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(f, fieldnames=["date", "artist", "venue"])
    writer.writeheader()
    writer.writerows(all_rows)

# 3. Save Last Updated JS for website
now_str = datetime.now().strftime("%d.%m.%Y %H:%M")
with open("last_updated.js", "w") as f:
    f.write(f"document.getElementById('update-time').innerHTML = '{now_str}';")

print(f"Success! Found {len(all_rows)} upcoming events.")
