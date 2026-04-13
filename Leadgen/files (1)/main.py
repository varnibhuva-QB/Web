"""
LeadGen Platform - FastAPI Backend
Main application entry point
"""
from fastapi import FastAPI, BackgroundTasks, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from typing import Optional, List
import asyncio
import json
import uuid
import os
from datetime import datetime

from api.scraper_manager import ScraperManager
from api.job_store import JobStore
from db.mongo_client import MongoClient
from api.export_handler import ExportHandler

app = FastAPI(
    title="LeadGen Platform API",
    description="Multi-source business lead generation platform",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

scraper_manager = ScraperManager()
job_store = JobStore()
db_client = MongoClient()
export_handler = ExportHandler()


# ── Models ──────────────────────────────────────────────────────────────────

class ScrapeRequest(BaseModel):
    source: str           # "google_maps" | "indiamart" | "justdial" | "tradeindia" | "sulekha"
    keyword: str
    location: str
    max_results: Optional[int] = 50
    filters: Optional[dict] = {}

class LeadFilter(BaseModel):
    source: Optional[str] = None
    keyword: Optional[str] = None
    location: Optional[str] = None
    min_rating: Optional[float] = None
    has_email: Optional[bool] = None
    has_phone: Optional[bool] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None


# ── Sources ──────────────────────────────────────────────────────────────────

SUPPORTED_SOURCES = {
    "google_maps": {
        "name": "Google Maps",
        "icon": "🗺️",
        "fields": ["business_name", "phone", "address", "rating", "website", "category"],
        "status": "active",
        "method": "selenium",
        "tos_note": "Use Google Places API for production. Demo uses public search."
    },
    "indiamart": {
        "name": "IndiaMART",
        "icon": "🏭",
        "fields": ["company_name", "contact_person", "phone", "email", "product", "address"],
        "status": "active",
        "method": "requests+bs4",
        "tos_note": "Respect IndiaMART robots.txt. Use their API where available."
    },
    "justdial": {
        "name": "Justdial",
        "icon": "📞",
        "fields": ["business_name", "phone", "address", "rating", "category"],
        "status": "active",
        "method": "requests+bs4",
        "tos_note": "Justdial has strict anti-scraping. Use their API for production."
    },
    "tradeindia": {
        "name": "TradeIndia",
        "icon": "🤝",
        "fields": ["company_name", "phone", "email", "product", "address", "website"],
        "status": "active",
        "method": "requests+bs4",
        "tos_note": "Refer to TradeIndia API documentation for production use."
    },
    "sulekha": {
        "name": "Sulekha",
        "icon": "🔍",
        "fields": ["business_name", "phone", "address", "rating", "service"],
        "status": "active",
        "method": "requests+bs4",
        "tos_note": "Check Sulekha Terms of Service before scraping."
    },
    "yellowpages_in": {
        "name": "Yellow Pages India",
        "icon": "📒",
        "fields": ["business_name", "phone", "address", "email", "website"],
        "status": "active",
        "method": "requests+bs4",
        "tos_note": "Review Yellow Pages data usage policy."
    }
}


# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"message": "LeadGen Platform API", "version": "1.0.0", "docs": "/docs"}


@app.get("/api/sources")
def get_sources():
    """Return list of supported scraping sources."""
    return {"sources": SUPPORTED_SOURCES}


@app.post("/api/scrape/start")
async def start_scraping(req: ScrapeRequest, background_tasks: BackgroundTasks):
    """Kick off a scraping job and return a job ID for polling."""
    if req.source not in SUPPORTED_SOURCES:
        raise HTTPException(status_code=400, detail=f"Source '{req.source}' not supported.")

    job_id = str(uuid.uuid4())
    job_store.create_job(job_id, {
        "source": req.source,
        "keyword": req.keyword,
        "location": req.location,
        "max_results": req.max_results,
        "filters": req.filters,
        "started_at": datetime.utcnow().isoformat()
    })

    background_tasks.add_task(
        scraper_manager.run_scraper,
        job_id, req.source, req.keyword, req.location,
        req.max_results, req.filters, job_store, db_client
    )

    return {
        "job_id": job_id,
        "status": "started",
        "message": f"Scraping {SUPPORTED_SOURCES[req.source]['name']} for '{req.keyword}' in '{req.location}'"
    }


@app.get("/api/scrape/status/{job_id}")
def get_job_status(job_id: str):
    """Poll job status and progress."""
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.delete("/api/scrape/cancel/{job_id}")
def cancel_job(job_id: str):
    """Cancel a running scraping job."""
    job_store.cancel_job(job_id)
    return {"job_id": job_id, "status": "cancelled"}


@app.get("/api/leads")
def get_leads(
    source: Optional[str] = None,
    keyword: Optional[str] = None,
    location: Optional[str] = None,
    min_rating: Optional[float] = None,
    has_email: Optional[bool] = None,
    has_phone: Optional[bool] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
):
    """Retrieve stored leads with optional filtering and pagination."""
    filters = {}
    if source:     filters["source"] = source
    if keyword:    filters["keyword"] = {"$regex": keyword, "$options": "i"}
    if location:   filters["location"] = {"$regex": location, "$options": "i"}
    if min_rating: filters["rating"] = {"$gte": min_rating}
    if has_email is not None:
        filters["email"] = {"$ne": None, "$ne": ""} if has_email else {"$in": [None, ""]}
    if has_phone is not None:
        filters["phone"] = {"$ne": None, "$ne": ""} if has_phone else {"$in": [None, ""]}

    leads, total = db_client.get_leads(filters, page, page_size)
    return {
        "leads": leads,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }


@app.get("/api/leads/stats")
def get_stats():
    """Dashboard statistics."""
    return db_client.get_stats()


@app.delete("/api/leads/{lead_id}")
def delete_lead(lead_id: str):
    db_client.delete_lead(lead_id)
    return {"deleted": True}


@app.post("/api/export")
def export_leads(
    fmt: str = Query(default="csv", enum=["csv", "excel", "json"]),
    source: Optional[str] = None,
    keyword: Optional[str] = None,
    location: Optional[str] = None,
    job_id: Optional[str] = None,
):
    """Export leads to CSV / Excel / JSON."""
    filters = {}
    if source:   filters["source"] = source
    if keyword:  filters["keyword"] = {"$regex": keyword, "$options": "i"}
    if location: filters["location"] = {"$regex": location, "$options": "i"}
    if job_id:   filters["job_id"] = job_id

    leads, _ = db_client.get_leads(filters, page=1, page_size=10000)
    filename, content, media_type = export_handler.export(leads, fmt)

    return StreamingResponse(
        iter([content]),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
