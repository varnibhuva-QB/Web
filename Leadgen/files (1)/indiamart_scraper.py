"""
IndiaMART Scraper
------------------
Production recommendation: Use IndiaMART's Lead Manager API
https://developer.indiamart.com/

The demo simulates realistic B2B manufacturer/supplier data.
Real scraping uses: requests + BeautifulSoup targeting
  https://dir.indiamart.com/search.mp?ss={keyword}&cq={location}
"""
import asyncio
import random
from typing import List
from scrapers.base_scraper import BaseScraper


PRODUCTS = ["Steel", "Plastic", "Rubber", "Textile", "Chemical", "Electronic", "Food", "Pharma", "Auto", "Agro"]
TYPES = ["Manufacturer", "Supplier", "Exporter", "Trader", "Wholesaler", "Distributor"]
FIRST = ["Raj", "Shri", "Anand", "Vikram", "Suresh", "Mahesh", "Deepak", "Ramesh", "Anil", "Sunil"]
LAST = ["Kumar", "Sharma", "Patel", "Gupta", "Singh", "Shah", "Verma", "Jain", "Mehta", "Agrawal"]


def indiamart_lead(keyword, location, idx):
    product = random.choice(PRODUCTS)
    type_ = random.choice(TYPES)
    fname = random.choice(FIRST)
    lname = random.choice(LAST)
    co = f"{fname} {lname} {keyword.title()} {type_}"
    phone_prefix = random.choice(["022", "011", "040", "044", "080", "033"])
    return {
        "company_name": co,
        "contact_person": f"{fname} {lname}",
        "phone": f"{phone_prefix}-{random.randint(10000000, 99999999)}",
        "mobile": f"+91 9{random.randint(100000000, 999999999)}",
        "email": f"contact@{fname.lower()}{lname.lower()}.com" if random.random() > 0.3 else "",
        "address": f"Plot {random.randint(1,500)}, Industrial Area, {location}",
        "product": f"{keyword.title()} ({product} based)",
        "business_type": type_,
        "website": f"https://www.{fname.lower()}{keyword.lower().replace(' ','')}.com" if random.random() > 0.5 else "",
        "gst": f"27AABC{random.randint(1000,9999)}M{random.randint(1,9)}Z{random.randint(1,9)}" if random.random() > 0.4 else "",
        "year_established": random.randint(1990, 2022),
    }


class Scraper(BaseScraper):
    source_name = "indiamart"

    async def scrape(self, keyword, location, max_results, job_id, job_store, filters) -> List[dict]:
        """
        DEMO MODE: Returns realistic IndiaMART-style B2B leads.
        
        PRODUCTION BeautifulSoup approach:
        
        from bs4 import BeautifulSoup
        url = f"https://dir.indiamart.com/search.mp?ss={keyword}&cq={location}"
        html = await self.fetch(url)
        soup = BeautifulSoup(html, 'lxml')
        
        for card in soup.select('.company-name-block'):
            name = card.select_one('h3.companyname').text.strip()
            phone = card.select_one('.mobile').text.strip()
            # etc.
        """
        job_store.append_log(job_id, "⚠️  DEMO MODE: Simulating IndiaMART B2B data. Use IndiaMART API for production.")
        leads = []
        pages = max(1, min(max_results // 8, 6))

        for page in range(pages):
            if job_store.is_cancelled(job_id):
                break
            self.update_progress(
                job_store, job_id, len(leads), max_results, page + 1,
                f"Scraping IndiaMART page {page+1}/{pages}..."
            )
            await asyncio.sleep(random.uniform(1.2, 2.8))
            batch = min(8, max_results - len(leads))
            for i in range(batch):
                leads.append(indiamart_lead(keyword, location, len(leads)))
            if len(leads) >= max_results:
                break

        job_store.append_log(job_id, f"✅ IndiaMART: collected {len(leads)} leads.")
        return leads[:max_results]
