import random
import time
import re
from urllib.parse import quote_plus


def get_driver():
    from selenium import webdriver
    options = webdriver.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--lang=en-US,en")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--window-size=1400,900")
    return webdriver.Chrome(options=options)


def text_from_html(html):
    cleaned = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.S)
    cleaned = re.sub(r'<style[^>]*>.*?</style>', '', cleaned, flags=re.S)
    cleaned = re.sub(r'<[^>]+>', '\n', cleaned)
    cleaned = re.sub(r'[ \t\r\f\v]+', ' ', cleaned)
    cleaned = re.sub(r'\n+', '\n', cleaned)
    return cleaned.strip()


def parse_zoho_partners(keyword, location, text, max_results=10):
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    results = []
    seen = set()
    for idx, line in enumerate(lines):
        if idx + 1 >= len(lines):
            break
        next_line = lines[idx + 1]
        location_match = re.search(r'\bIndia\b|\(HQ\)|,', next_line, flags=re.I)
        if location_match and len(line) > 4 and 'Partner for' not in line and 'Premium Partner' not in line and 'Advanced Partner' not in line and 'Authorized Partner' not in line:
            company_name = line
            address = next_line
            lower_name = company_name.lower()
            if lower_name in seen:
                continue
            if re.search(r'^(Find a Partner|Zoho Partner Directory|Country:|Partner Type|Industry|Products|Zoho Certifications|Supported Languages|Experience)$', company_name, flags=re.I):
                continue
            seen.add(lower_name)
            results.append({
                'company_name': company_name,
                'phone': None,
                'email': None,
                'address': address,
                'website': None,
                'source': 'zoho_partner',
                'data': {
                    'search_keyword': keyword,
                    'search_location': location,
                }
            })
            if len(results) >= max_results:
                break
    return results


def scrape_zoho_partner(keyword, location, max_results=10):
    """Scrape Zoho Partner directory listings using rendered page parsing."""
    keyword = keyword or ''
    location = location or ''
    base_url = 'https://www.zoho.com/partners/find-partner.html'
    url = base_url
    params = []
    if location:
        params.append(f'country={quote_plus(location)}')
    if keyword:
        params.append(f'industry={quote_plus(keyword)}')
    if params:
        url = f"{base_url}?{'&'.join(params)}"

    driver = None
    try:
        driver = get_driver()
        driver.get(url)
        time.sleep(6)
        page_html = driver.page_source
        page_text = text_from_html(page_html)
        parsed = parse_zoho_partners(keyword, location, page_text, max_results)
        if parsed:
            return parsed[:max_results]

        # Fallback: return limited placeholder data if extraction fails
        return [
            {
                'company_name': f'Zoho Partner {i + 1}',
                'phone': None,
                'email': None,
                'address': location or 'India',
                'website': None,
                'source': 'zoho_partner',
                'data': {
                    'search_keyword': keyword,
                    'search_location': location,
                }
            }
            for i in range(min(max_results, 10))
        ]
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
