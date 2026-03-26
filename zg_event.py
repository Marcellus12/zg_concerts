import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
import json
import csv
from icalendar import Calendar, Event
import uuid

URL = "https://www.songkick.com/metro-areas/29037-croatia-zagreb"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
CSV_FILE = "events.csv"
ICS_FILE = "zagreb_gigs.ics"

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

for event_tag in soup.select("li.event-listings-element"):
    try:
        json_script = event_tag.select_one('script[type="application/ld+json"]')
        if not json_script: continue
        
        data = json.loads(json_script.string)
        event_data = data[0] if isinstance(data, list) else data
        
        event_date_str = event_data.get('startDate')
        event_date = datetime.fromisoformat(event_date_str).replace(tzinfo=timezone.utc)
        if event_date < today: continue

        venue = event_data.get('location', {}).get('name', 'Venue TBD')
        link = event_data.get('url', '')
        e_type = "Festival" if "Festival" in event_data.get('name', '') else "Concert"
        
        lineup_tag = event_tag.select_one("span.support")
        
        artists_to_add = []
        if e_type == "Festival" and lineup_tag:
            raw_lineup = lineup_tag.text.replace(' and ', ', ')
            artists_to_add = [clean_text(a) for a in raw_lineup.split(',') if clean_text(a)]
        else:
            artist_name = event_data.get('name', '').split('@')[0].strip()
            artists_to_add = [artist_name]

        for artist in artists_to_add:
            # Add to CSV list
            all_rows.append({
                "date": event_date.strftime("%Y-%m-%d"),
                "artist": artist,
                "venue": venue,
                "type": e_type,
                "link": link
            })
            
            # Add to ICS Calendar
            v_event = Event()
            v_event.add('summary', f"{artist} ({e_type})")
            v_event.add('dtstart', event_date.date()) # All-day event
            v_event.add('location', f"{venue}, Zagreb")
            v_event.add('description', f"Tickets: {link}")
            # Unique ID prevents duplicates in Google Calendar
            v_event.add('uid', f"{event_date.strftime('%Y%m%d')}-{uuid.uuid5(uuid.NAMESPACE_DNS, artist+link)}")
            cal.add_component(v_event)

    except Exception as e:
        print(f"Error: {e}")
        continue

# 2. Save CSV
with open(CSV_FILE, "w", newline="", encoding="utf-8-sig") as file:
    writer = csv.DictWriter(file, fieldnames=["date", "artist", "venue", "type", "link"])
    writer.writeheader()
    writer.writerows(all_rows)

# 3. Save ICS
with open(ICS_FILE, "wb") as f:
    f.write(cal.to_ical())

print(f"Success! Saved {len(all_rows)} entries to {CSV_FILE} and {ICS_FILE}.")
