import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
import csv
import json
import os

URL = "https://www.songkick.com/metro-areas/29037-croatia-zagreb"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
CSV_FILE = "events.csv"

def clean_text(text):
    return " ".join(text.strip().split()) if text else ""

# 1. Fetch Page
response = requests.get(URL, headers=headers)
response.encoding = 'utf-8' 
soup = BeautifulSoup(response.text, "html.parser")

all_rows = []
today = datetime.now(timezone.utc)

for event_tag in soup.select("li.event-listings-element"):
    try:
        # Use JSON-LD first as it's the cleanest data source
        json_script = event_tag.select_one('script[type="application/ld+json"]')
        if not json_script: continue
        
        data = json.loads(json_script.string)
        event_data = data[0] if isinstance(data, list) else data
        
        # Date & Basic Info
        event_date_str = event_data.get('startDate')
        event_date = datetime.fromisoformat(event_date_str).replace(tzinfo=timezone.utc)
        if event_date < today: continue

        venue = event_data.get('location', {}).get('name', 'Venue TBD')
        link = event_data.get('url', '')
        e_type = "Festival" if "Festival" in event_data.get('name', '') else "Concert"
        
        # Get the raw list of artists
        # For Festivals, we look at the 'span.support' we found earlier
        lineup_tag = event_tag.select_one("span.support")
        
        if e_type == "Festival" and lineup_tag:
            # Split "Artist A, Artist B, and Artist C"
            raw_lineup = lineup_tag.text.replace(' and ', ', ') # Replace 'and' with comma
            artist_list = [clean_text(a) for a in raw_lineup.split(',') if clean_text(a)]
            
            # Create a separate row for EACH artist
            for artist in artist_list:
                all_rows.append({
                    "date": event_date.strftime("%Y-%m-%d"),
                    "artist": artist,
                    "venue": venue,
                    "type": e_type,
                    "link": link
                })
        else:
            # It's a concert, just one artist
            artist = event_data.get('name', '').split('@')[0].strip()
            all_rows.append({
                "date": event_date.strftime("%Y-%m-%d"),
                "artist": artist,
                "venue": venue,
                "type": e_type,
                "link": link
            })

    except Exception as e:
        print(f"Error: {e}")
        continue

# 2. Save (One artist per row)
with open(CSV_FILE, "w", newline="", encoding="utf-8-sig") as file:
    writer = csv.DictWriter(file, fieldnames=["date", "artist", "venue", "type", "link"])
    writer.writeheader()
    writer.writerows(all_rows)

print(f"Success! Generated {len(all_rows)} rows. INmusic artists now have their own entries.")