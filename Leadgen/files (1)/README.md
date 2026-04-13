# ⚡ LeadGen Pro — Business Lead Generation Platform

A full-stack platform for extracting structured business leads from multiple Indian business directories and Google Maps. Built with **FastAPI** + **Python** (backend) and vanilla **HTML/CSS/JS** (frontend).

---

## 📁 Project Structure

```
leadgen/
├── frontend/
│   └── index.html              # Complete single-file UI (no build step needed)
│
├── backend/
│   ├── main.py                 # FastAPI app & all API routes
│   ├── requirements.txt
│   ├── Dockerfile
│   │
│   ├── api/
│   │   ├── scraper_manager.py  # Dispatches jobs to scrapers
│   │   ├── job_store.py        # In-memory job tracking (swap Redis for prod)
│   │   ├── export_handler.py   # CSV / Excel / JSON export
│   │   ├── robots_checker.py   # robots.txt compliance utility
│   │   ├── scheduler.py        # Scheduled/recurring scraping (APScheduler)
│   │   └── auth.py             # Optional JWT authentication
│   │
│   ├── scrapers/
│   │   ├── base_scraper.py         # Base class (retry, UA rotation, delays)
│   │   ├── google_maps_scraper.py  # Demo + Selenium skeleton
│   │   ├── google_places_api.py    # ✅ Production: Google Places API
│   │   ├── indiamart_scraper.py    # Demo + BS4 skeleton
│   │   ├── justdial_scraper.py     # Demo + BS4 skeleton
│   │   ├── tradeindia_scraper.py   # Demo + BS4 skeleton
│   │   ├── sulekha_scraper.py      # Demo + BS4 skeleton
│   │   ├── yellowpages_scraper.py  # Demo + BS4 skeleton
│   │   └── selenium_base.py        # Selenium stealth driver factory
│   │
│   └── db/
│       └── mongo_client.py     # MongoDB client (in-memory fallback for demo)
│
├── docker-compose.yml          # One-command deployment
├── .env.example                # Environment variable template
└── README.md
```

---

## 🚀 Quick Start

### Option 1 — Frontend Only (Demo Mode)
No Python required. Just open the frontend:
```bash
open frontend/index.html
# or
python3 -m http.server 3000 --directory frontend
```
The UI auto-detects no backend and runs in demo mode with simulated data.

---

### Option 2 — Full Stack (Local)

**1. Set up Python environment:**
```bash
cd backend
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**2. Configure environment:**
```bash
cp ../.env.example ../.env
# Edit .env — add your API keys
```

**3. Start the backend:**
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**4. Open the frontend:**
```bash
# In a new terminal:
python3 -m http.server 3000 --directory ../frontend
open http://localhost:3000
```

**5. API docs available at:** http://localhost:8000/docs

---

### Option 3 — Docker (Recommended for Production)
```bash
docker-compose up --build
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# API docs: http://localhost:8000/docs
```

---

## 🔌 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/sources` | List supported scraping sources |
| POST | `/api/scrape/start` | Start a scraping job |
| GET | `/api/scrape/status/{job_id}` | Poll job progress |
| DELETE | `/api/scrape/cancel/{job_id}` | Cancel running job |
| GET | `/api/leads` | Fetch stored leads (filterable) |
| GET | `/api/leads/stats` | Dashboard statistics |
| DELETE | `/api/leads/{id}` | Delete a lead |
| POST | `/api/export?fmt=csv` | Export leads (csv/excel/json) |

### Example: Start a scraping job
```bash
curl -X POST http://localhost:8000/api/scrape/start \
  -H "Content-Type: application/json" \
  -d '{
    "source": "indiamart",
    "keyword": "steel manufacturers",
    "location": "Surat",
    "max_results": 50
  }'
```

### Example: Poll job status
```bash
curl http://localhost:8000/api/scrape/status/{job_id}
```

### Example: Export leads
```bash
# CSV
curl "http://localhost:8000/api/export?fmt=csv&source=indiamart" -o leads.csv

# Excel
curl "http://localhost:8000/api/export?fmt=excel" -o leads.xlsx
```

---

## 🗃️ MongoDB Setup (Production)

Install MongoDB locally or use MongoDB Atlas (free tier):
```bash
# .env
MONGO_URI=mongodb+srv://user:pass@cluster.mongodb.net/
MONGO_DB=leadgen
```

Then uncomment the Motor (async MongoDB) lines in `db/mongo_client.py`.

---

## 🔑 Google Places API (Recommended for Google Maps)

For production Google Maps data (no scraping, no blocks):

1. Visit https://console.cloud.google.com/
2. Enable **Places API** and **Geocoding API**
3. Create an API key
4. Add to `.env`: `GOOGLE_PLACES_API_KEY=your_key_here`
5. In `api/scraper_manager.py`, change `google_maps` to import `google_places_api` instead of `google_maps_scraper`

**Free tier:** Google gives $200/month credit = ~11,000 Nearby Search calls free.

---

## ⚙️ Adding a New Source

1. Create `backend/scrapers/mysource_scraper.py`:
```python
from scrapers.base_scraper import BaseScraper

class Scraper(BaseScraper):
    source_name = "mysource"

    async def scrape(self, keyword, location, max_results, job_id, job_store, filters):
        leads = []
        # ... your scraping logic ...
        return leads
```

2. Register in `api/scraper_manager.py`:
```python
SCRAPER_MAP = {
    ...
    "mysource": "scrapers.mysource_scraper",
}
```

3. Add to `SUPPORTED_SOURCES` in `main.py` and to the source grid in `frontend/index.html`.

---

## 🔒 Optional: User Authentication

Uncomment the routes in `backend/api/auth.py` and add `Depends(get_current_user)` to protected endpoints.

```bash
# Register
curl -X POST http://localhost:8000/api/auth/register \
  -d '{"username":"admin","password":"secret"}'

# Login
curl -X POST http://localhost:8000/api/auth/login \
  -d '{"username":"admin","password":"secret"}'
```

---

## ⏰ Scheduled Scraping

```python
# Add to main.py
from api.scheduler import setup_scheduler, add_schedule

scheduler = setup_scheduler(scraper_manager, job_store, db_client)
scheduler.start()

# Schedule: scrape "restaurants" in "Mumbai" every 24 hours
add_schedule(scheduler, scraper_manager, job_store, db_client,
             source="justdial", keyword="restaurants",
             location="Mumbai", max_results=100,
             interval_hours=24)
```

---

## ⚖️ Legal & Ethical Usage

> **Important:** This platform is built for legitimate business research.

- ✅ Always check `robots.txt` before scraping (handled by `api/robots_checker.py`)
- ✅ Use official APIs where available (Google Places, IndiaMART, Justdial)
- ✅ Respect rate limits and crawl delays
- ✅ Do not scrape personal data without consent
- ✅ Comply with India's IT Act 2000 and applicable data protection laws
- ❌ Do not use for spam, harassment, or unsolicited marketing
- ❌ Do not resell scraped data without proper licensing

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | HTML5 + CSS3 + Vanilla JS |
| Backend API | FastAPI (Python 3.11) |
| Scraping | BeautifulSoup4, Selenium, httpx |
| Database | MongoDB (Motor async driver) |
| Export | Pandas + OpenPyXL |
| Container | Docker + Docker Compose |
| Scheduling | APScheduler |
| Auth | JWT (python-jose + passlib) |

---

## 📊 Data Fields Extracted

| Field | Google Maps | IndiaMART | Justdial | TradeIndia | Sulekha |
|-------|:-----------:|:---------:|:--------:|:----------:|:-------:|
| Business Name | ✅ | ✅ | ✅ | ✅ | ✅ |
| Phone | ✅ | ✅ | ✅ | ✅ | ✅ |
| Email | ⚠️ | ✅ | ⚠️ | ✅ | ⚠️ |
| Address | ✅ | ✅ | ✅ | ✅ | ✅ |
| Website | ✅ | ✅ | ❌ | ✅ | ❌ |
| Rating | ✅ | ❌ | ✅ | ❌ | ✅ |
| GST Number | ❌ | ✅ | ❌ | ✅ | ❌ |

⚠️ = Available on some listings only
