"""
Google Maps Scraper
--------------------
Production recommendation: Use the Google Places API (https://developers.google.com/maps/documentation/places/web-service)
for reliable, TOS-compliant data. The demo below simulates realistic data.

For real Selenium scraping:
1. Install ChromeDriver matching your Chrome version
2. Use selenium-stealth to avoid detection
3. Respect rate limits and robots.txt
"""
import asyncio
import random
from typing import List
from scrapers.base_scraper import BaseScraper, random_delay


# Realistic demo data generator
CATEGORIES = [
    "Restaurant", "Hotel", "Hospital", "Pharmacy", "Gym",
    "School", "Bank", "Supermarket", "Salon", "Garage"
]
SUFFIXES = ["Pvt Ltd", "& Sons", "Enterprises", "Trading Co", "Services", "Solutions", "Group"]


def fake_phone():
    prefix = random.choice(["98", "97", "96", "95", "94", "93", "91", "90", "88", "87", "86", "77", "76", "75", "74", "73", "72", "70"])
    return f"+91 {prefix}{random.randint(10000000, 99999999)}"


def fake_lead(keyword, location, idx):
    name_parts = [keyword.title(), random.choice(SUFFIXES)]
    if idx > 0:
        name_parts.insert(1, str(idx + 1))
    cat = random.choice(CATEGORIES)
    rating = round(random.uniform(3.0, 5.0), 1)
    areas = ["MG Road", "Koramangala", "Indiranagar", "BTM Layout", "HSR Layout", "Whitefield", "Electronic City"]
    area = random.choice(areas)
    return {
        "business_name": " ".join(name_parts),
        "phone": fake_phone(),
        "email": f"info@{keyword.lower().replace(' ', '')}{idx+1}.com" if random.random() > 0.4 else "",
        "address": f"{random.randint(1,200)}, {area}, {location}",
        "website": f"https://www.{keyword.lower().replace(' ', '')}{idx+1}.in" if random.random() > 0.5 else "",
        "rating": rating,
        "reviews": random.randint(5, 1200),
        "category": cat,
        "maps_url": f"https://maps.google.com/?q={keyword}+{location}+{idx+1}",
    }


class Scraper(BaseScraper):
    source_name = "google_maps"

    async def scrape(self, keyword, location, max_results, job_id, job_store, filters) -> List[dict]:
        """
        DEMO MODE: Returns realistic simulated data.
        
        PRODUCTION: Replace with Selenium + selenium-stealth:
        
        from selenium import webdriver
        from selenium_stealth import stealth
        from selenium.webdriver.common.by import By
        
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        driver = webdriver.Chrome(options=options)
        stealth(driver, ...)
        
        driver.get(f"https://www.google.com/maps/search/{keyword}+{location}")
        # Scroll and extract business cards
        """
        job_store.append_log(job_id, "⚠️  DEMO MODE: Using simulated Google Maps data. For production, use Google Places API.")
        
        leads = []
        pages = max(1, min(max_results // 10, 5))

        for page in range(pages):
            if job_store.is_cancelled(job_id):
                break

            self.update_progress(
                job_store, job_id,
                len(leads), max_results, page + 1,
                f"Scraping Google Maps page {page+1}/{pages}..."
            )

            # Simulate network delay
            await asyncio.sleep(random.uniform(1.0, 2.5))

            batch_size = min(10, max_results - len(leads))
            for i in range(batch_size):
                leads.append(fake_lead(keyword, location, len(leads)))

            if len(leads) >= max_results:
                break

        job_store.append_log(job_id, f"✅ Google Maps: collected {len(leads)} leads.")
        return leads[:max_results]
