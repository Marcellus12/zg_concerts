import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
import json
import csv
from icalendar import Calendar, Event
import uuid

# --- CONFIGURATION ---
URL = "https://www.songkick.com/metro-areas/29037-croatia-zagreb"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
CSV_FILE = "events.csv"
ICS_FILE = "zagreb_gigs.ics"

# Typical "Doors Open" or "Start" hours for Zagreb venues (24h format)
VENUE_TIMES = {
    "Tvornica kulture": 20,
    "Močvara": 20,
    "Vintage Industrial Bar": 20,
    "Boogaloo": 19,
    "Arena Zagreb": 18,
    "Dom Sportova": 18,
    "Peti Kupe": 21,
    "Pogon Jedinstvo": 20,
    "Mala dvorana Vatroslava Lisinskog": 19,
    "Vatroslav Lisinski": 19,
    "Jarun": 17,        # Typical for INmusic / Festivals
    "Lake Jarun": 17,
    "Klub SAŠA": 21,
    "Sax!": 20
}

def clean_text(text):
    return " ".join(text.strip().split()) if text else ""

# 1. Fetch Page
response = requests.get(URL, headers=headers)
response.encoding = 'utf-8' 
soup = BeautifulSoup(response.text, "html.parser")

all_rows = []
today = datetime.now(timezone.utc)

# Setup iCalendar
cal = Calendar()
cal.add('prodid', '-//Zagreb Music Events//EN')
cal.add('version', '2.0')
cal.add('x-wr-calname', 'Zagreb Gigs')

# 2. Parse Events
for event_tag in soup.select("li.event-listings-element"):
    try:
        json_script = event_tag.select_one('script[type="application/ld+json"]')
        if not json_script: continue
        
        data = json.loads(json_script.string)
        event_data = data[0] if isinstance(data, list) else data
        
        # --- SMART TIME LOGIC ---
        event_date_str = event_data.get('startDate') # e.g. "2026-06-26" or "2026-06-26T20:00:00"
        venue_name = event_data.get('location', {}).get('name', 'Unknown Venue')
        
        # Check if Songkick provided a specific time (contains 'T')
        if "T" in event_date_str:
            base_date = datetime.fromisoformat(event_date_str).replace(tzinfo=timezone.utc)
        else:
            # Fallback: Look up venue in our list, default to 20:00 (8 PM)
            hour = VENUE_TIMES.get(venue_name, 20) 
            base_date = datetime.fromisoformat(event_date_str).replace(hour=hour, minute=0, second=0, tzinfo=timezone.utc)

        # Skip past events
        if base_date < today: continue

        link = event_data.get('url', '')
        e_type = "Festival" if "Festival" in event_data.get('name', '') else "Concert"
        
        # Get Lineup
        lineup_tag = event_tag.select_one("span.support")
        artists_to_add = []
        
        if e_type == "Festival" and lineup_tag:
            raw_lineup = lineup_tag.text.replace(' and ', ', ')
            artists_to_add = [clean_text(a) for a in raw_lineup.split(',') if clean_text(a)]
        else:
            # For concerts, name is usually "Artist Name @ Venue"
            artist_name = event_data.get('name', '').split('@')[0].strip()
            artists_to_add = [artist_name]

        # 3. Create Entries
        for index, artist in enumerate(artists_to_add):
            # Stagger festival artists by 30 mins so they don't overlap as "invitations"
            start_time = base_date + timedelta(minutes=30 * index)
            end_time = start_time + timedelta(hours=1)

            # Add to CSV list
            all_rows.append({
                "date": start_time.strftime("%Y-%m-%d"),
                "artist": artist,
                "venue": venue_name,
                "type": e_type,
                "link": link
            })
            
            # Add to ICS Calendar
            v_event = Event()
            v_event.add('summary', f"{artist} ({e_type})")
            v_event.add('dtstart', start_time)
            v_event.add('dtend', end_time)
            v_event.add('location', f"{venue_name}, Zagreb")
            v_event.add('description', f"Tickets & Info: {link}")
            
            # Generate a Stable Unique ID
            uid_payload = f"{start_time.strftime('%Y%m%d%H%M')}-{artist}-{venue_name}"
            v_event.add('uid', str(uuid.uuid5(uuid.NAMESPACE_DNS, uid_payload)))
            
            cal.add_component(v_event)

    except Exception as e:
        print(f"Error processing event: {e}")
        continue

# 4. Save Files
with open(CSV_FILE, "w", newline="", encoding="utf-8-sig") as file:
    writer = csv.DictWriter(file, fieldnames=["date", "artist", "venue", "type", "link"])
    writer.writeheader()
    writer.writerows(all_rows)

with open(ICS_FILE, "wb") as f:
    f.write(cal.to_ical())

print(f"Successfully generated {len(all_rows)} events.")
print(f"Calendar saved as {ICS_FILE} with 'invitation' style formatting.")

now_str = datetime.now().strftime("%d.%m.%Y %H:%M")
with open("last_updated.js", "w") as f:
    f.write(f"document.getElementById('update-time').innerHTML = '{now_str}';")
