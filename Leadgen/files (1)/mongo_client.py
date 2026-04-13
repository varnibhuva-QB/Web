"""
MongoDB client — swap URI in .env for production.
Falls back to an in-memory list for local demo (no Mongo required).
"""
import os
import hashlib
import json
from typing import List, Tuple, Optional
from datetime import datetime


def _lead_hash(lead: dict) -> str:
    """Dedup key: source + business_name + phone + address."""
    key = "|".join([
        str(lead.get("source", "")),
        str(lead.get("business_name", lead.get("company_name", ""))).lower().strip(),
        str(lead.get("phone", "")).strip(),
        str(lead.get("address", "")).lower().strip()[:60],
    ])
    return hashlib.md5(key.encode()).hexdigest()


class MongoClient:
    """
    Production: uncomment motor/pymongo blocks.
    Demo: uses an in-memory list.
    """

    def __init__(self):
        self._leads: List[dict] = []   # in-memory store
        self._hashes: set = set()
        self._next_id = 1

        # --- Production Mongo (uncomment) ---
        # from motor.motor_asyncio import AsyncIOMotorClient
        # uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
        # self.client = AsyncIOMotorClient(uri)
        # self.db = self.client["leadgen"]
        # self.col = self.db["leads"]

    def upsert_leads(self, leads: List[dict]) -> Tuple[int, int]:
        saved = 0
        dupes = 0
        for lead in leads:
            h = _lead_hash(lead)
            if h in self._hashes:
                dupes += 1
                continue
            lead["_id"] = str(self._next_id)
            lead["_hash"] = h
            self._next_id += 1
            self._leads.append(lead)
            self._hashes.add(h)
            saved += 1
        return saved, dupes

    def get_leads(self, filters: dict, page: int, page_size: int) -> Tuple[List[dict], int]:
        results = self._leads

        # Apply simple string/equality filters
        for key, val in filters.items():
            if key.startswith("_"):
                continue
            if isinstance(val, dict):
                # Handle $regex, $gte, $ne, $in operators
                filtered = []
                for lead in results:
                    field_val = lead.get(key, "")
                    match = True
                    for op, operand in val.items():
                        if op == "$regex":
                            import re
                            flags = re.IGNORECASE if "$options" in val and "i" in val["$options"] else 0
                            if not re.search(operand, str(field_val), flags):
                                match = False
                        elif op == "$gte":
                            try:
                                if float(field_val or 0) < float(operand):
                                    match = False
                            except:
                                match = False
                        elif op == "$ne":
                            if field_val == operand:
                                match = False
                        elif op == "$in":
                            if field_val not in operand:
                                match = False
                    if match:
                        filtered.append(lead)
                results = filtered
            else:
                results = [l for l in results if str(l.get(key, "")) == str(val)]

        total = len(results)
        start = (page - 1) * page_size
        end = start + page_size
        page_leads = results[start:end]

        # Remove internal fields
        clean = []
        for lead in page_leads:
            l = {k: v for k, v in lead.items() if not k.startswith("_")}
            l["id"] = lead.get("_id", "")
            clean.append(l)

        return clean, total

    def get_stats(self) -> dict:
        from collections import Counter
        sources = Counter(l.get("source") for l in self._leads)
        keywords = Counter(l.get("keyword") for l in self._leads)
        with_email = sum(1 for l in self._leads if l.get("email"))
        with_phone = sum(1 for l in self._leads if l.get("phone"))
        return {
            "total_leads": len(self._leads),
            "with_email": with_email,
            "with_phone": with_phone,
            "by_source": dict(sources),
            "top_keywords": dict(keywords.most_common(10)),
        }

    def delete_lead(self, lead_id: str):
        for i, lead in enumerate(self._leads):
            if str(lead.get("_id")) == lead_id:
                h = lead.get("_hash")
                self._leads.pop(i)
                if h:
                    self._hashes.discard(h)
                return
