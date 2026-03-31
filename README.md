# zg_concerts

🎸 Zagreb Gig Calendar (ZG_CONCERTS)
Automated cultural intelligence for Zagreb, Croatia.

This project is a fully automated data pipeline that scrapes, cleans, and categorizes live events across Zagreb’s most iconic venues. It transforms messy web data into a synchronized Google/Apple Calendar feed and a clean CSV "Data Lake" for analytics.

🚀 What it does
Multi-Source Scraping: Aggregates events from Songkick, Tvornica Kulture, and Lisinski Hall.

Smart Classification: Uses a custom NLP-based logic to categorize events into Concerts, Festivals, Theater, Musical/Opera, Ballet, and Exhibitions.

Auto-Sync: Powered by GitHub Actions, the scraper runs twice daily to ensure the feeds are never stale.

Ready for Analytics: Generates a structured events.csv designed specifically for Power BI or Tableau reporting.

📅 How to use the Feed
You can subscribe to the live .ics calendar directly in your favorite app using this URL:
https://marcellus12.github.io/zg_concerts/zagreb_gigs.ics

🛠️ The Tech Stack
Python: The engine (BeautifulSoup4, Requests, Dateparser).

iCalendar: For generating RFC 5545 compliant calendar files.

GitHub Actions: For serverless automation and deployment.

Power BI: (Planned/In-progress) For visualizing venue "wars" and cultural trends.
