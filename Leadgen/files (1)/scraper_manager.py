"""
ScraperManager — dispatches scraping jobs to the correct scraper.
All scrapers follow the same interface: scrape(keyword, location, max_results, job_id, job_store) -> List[dict]
"""
import asyncio
import importlib
from datetime import datetime
from typing import Optional


SCRAPER_MAP = {
    "google_maps":   "scrapers.google_maps_scraper",
    "indiamart":     "scrapers.indiamart_scraper",
    "justdial":      "scrapers.justdial_scraper",
    "tradeindia":    "scrapers.tradeindia_scraper",
    "sulekha":       "scrapers.sulekha_scraper",
    "yellowpages_in":"scrapers.yellowpages_scraper",
}


class ScraperManager:

    async def run_scraper(
        self, job_id, source, keyword, location,
        max_results, filters, job_store, db_client
    ):
        job_store.update_job(job_id, status="running", message="Starting scraper...")
        job_store.append_log(job_id, f"Launching {source} scraper for '{keyword}' in '{location}'")

        try:
            module_path = SCRAPER_MAP.get(source)
            if not module_path:
                raise ValueError(f"No scraper for source: {source}")

            mod = importlib.import_module(module_path)
            scraper_cls = getattr(mod, "Scraper")
            scraper = scraper_cls()

            leads = await scraper.scrape(
                keyword=keyword,
                location=location,
                max_results=max_results,
                job_id=job_id,
                job_store=job_store,
                filters=filters or {}
            )

            if job_store.is_cancelled(job_id):
                job_store.update_job(job_id, status="cancelled", message="Cancelled by user.")
                return

            # Tag each lead with metadata
            now = datetime.utcnow().isoformat()
            for lead in leads:
                lead["source"] = source
                lead["keyword"] = keyword
                lead["location"] = location
                lead["job_id"] = job_id
                lead["scraped_at"] = now

            # Deduplicate & store
            saved, dupes = db_client.upsert_leads(leads)
            job_store.append_log(job_id, f"Saved {saved} new leads, {dupes} duplicates skipped.")
            job_store.update_job(
                job_id,
                status="done",
                progress=100,
                leads_found=len(leads),
                leads_saved=saved,
                duplicates_skipped=dupes,
                message=f"Complete. {saved} leads saved.",
                finished_at=now
            )

        except Exception as exc:
            job_store.update_job(
                job_id,
                status="error",
                error=str(exc),
                message=f"Error: {exc}",
                finished_at=datetime.utcnow().isoformat()
            )
            job_store.append_log(job_id, f"ERROR: {exc}")
