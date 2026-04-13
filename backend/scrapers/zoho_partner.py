import random
import time

def scrape_zoho_partner(keyword, location, max_results=10):
    # Demo scraper for Zoho Partners
    results = []
    services = ["CRM", "ERP", "Accounting", "HR", "Project Management"]
    company_suffixes = ["Solutions", "Technologies", "Systems", "Consulting", "Services"]
    first = ["John", "Jane", "Mike", "Sarah", "David"]
    last = ["Smith", "Johnson", "Williams", "Brown", "Jones"]

    for i in range(min(max_results, 50)):
        service = random.choice(services)
        suffix = random.choice(company_suffixes)
        fname = random.choice(first)
        lname = random.choice(last)
        co = f"{fname} {lname} {service} {suffix}"
        email = f"contact@{fname.lower()}{lname.lower()}@{service.lower()}.com"
        results.append({
            "company_name": co,
            "contact_person": f"{fname} {lname}",
            "email": email,
            "phone": f"+1-{random.randint(200,999)}-{random.randint(100,999)}-{random.randint(1000,9999)}",
            "address": f"{random.randint(100,999)} Main St, {location}",
            "service": service,
            "specialization": f"Zoho {service} Implementation",
        })
        time.sleep(0.1)

    return results